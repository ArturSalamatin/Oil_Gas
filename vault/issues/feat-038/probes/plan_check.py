"""Проба плана FEAT-038: функции plan_code/release.py без изменения репозитория.

    numerical_solver\\.venv\\Scripts\\python -X utf8 vault/issues/feat-038/probes/plan_check.py [ПУТЬ_К_RELEASE_PY]

Без аргумента — код плана plan_code/release.py; в /implement — скрипт
worktree: .worktrees/feat-038/tools/release.py. Запуск — из основного
каталога на базовой ветке (preflight проверяет её; репозиторий проба не меняет).

1. Чистые функции: литералы, номера, журнал (CRLF сохраняется).
2. preflight("1.0.0") на настоящем репозитории — только чтение (git fetch
   обновляет лишь origin/*): ожидается прототип 1.0.3+gpn.1 → +gpn.2 от 29a1ffa.
3. Сборка из дерева HEAD в dist/plan-check-feat-038/: архив примеров без 18,
   самопроверка до и после правки номеров выпуска, два колеса 1.0.0 и
   1.0.3+gpn.2 (METADATA), номер разработки, порча требования ловится.
4. Откат — на учебном репозитории в dist/plan-check-feat-038/rb: коммиты и
   метка скрипта уходят, незакоммиченный файл вне EDITED остаётся.
Сборке нужен доступ к PyPI или кеш pip (изолированная сборка, setuptools).
Каталог dist/plan-check-feat-038/ удаляется в конце.
"""

import importlib.util
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).parent / "plan_code" / "release.py"
print(f"Скрипт: {SCRIPT}\nРепозиторий: {ROOT}")
spec = importlib.util.spec_from_file_location("release", SCRIPT)
rel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rel)
rel.ROOT = ROOT          # в plan_code/ корень по __file__ — не корень репозитория

ok_all = True


def check(cond, msg):
    global ok_all
    ok_all &= bool(cond)
    print(("ОК     " if cond else "ОШИБКА ") + msg)


def raises(fn, *a):
    try:
        fn(*a)
    except rel.ReleaseError as e:
        return str(e)
    return None


# ── 1. Чистые функции ──
print("── 1. Чистые функции")
check(rel.read_version(ROOT / rel.SOLVER_INIT) == "1.0.0.dev0", "литерал решателя 1.0.0.dev0")
check(rel.read_version(ROOT / rel.PROTO_INIT) == "1.0.3+gpn.1", "литерал прототипа 1.0.3+gpn.1")
check(rel.next_gpn("1.0.3+gpn.1") == "1.0.3+gpn.2", "next_gpn: +gpn.1 → +gpn.2")
check(rel.next_gpn("1.0.3+gpn.9") == "1.0.3+gpn.10", "next_gpn: +gpn.9 → +gpn.10")
check(raises(rel.next_gpn, "1.0.3") is not None, "next_gpn: номер без +gpn — отказ")
check(rel.next_dev("1.0.0") == "1.0.1.dev0", "next_dev: 1.0.0 → 1.0.1.dev0")
check(rel.next_dev("1.2.9") == "1.2.10.dev0", "next_dev: 1.2.9 → 1.2.10.dev0")
check(raises(rel.check_new_version, "1.0.0", "1.0.0.dev0", []) is None, "1.0.0 после 1.0.0.dev0 — принят")
for bad, cur, released in [("1.0", "1.0.0.dev0", []), ("1.0.0.dev1", "1.0.0.dev0", []),
                           ("01.0.0", "1.0.0.dev0", []), ("1.0.0rc1", "1.0.0.dev0", []),
                           ("0.9.0", "1.0.0.dev0", []), ("1.0.0", "1.0.0", []),
                           ("1.0.0", "0.9.1.dev0", [Version("1.0.0")])]:
    check(raises(rel.check_new_version, bad, cur, released) is not None,
          f"номер {bad!r} при текущем {cur}, выпусках {[str(v) for v in released]} — отказ")
check(rel.released_versions() == [], "меток v* нет")
check(rel.prototype_changed(rel.FIRST_BASE), f"прототип изменился с {rel.FIRST_BASE}")
check(not rel.prototype_changed("HEAD"), "с HEAD прототип не изменился")

text = rel.read_text(ROOT / rel.CHANGELOG)
crlf = text.count("\r\n")
body = rel.section_body(text, rel.UNRELEASED)
check(any(s.startswith("- ") for s in body.splitlines()), "в «Не выпущено» есть пункты")
released_text = rel.changelog_release(text, "1.0.0", "2026-10-18")
check("## 1.0.0 — 2026-10-18" in released_text.splitlines() and rel.UNRELEASED not in released_text,
      "журнал выпуска: заголовок 1.0.0, «Не выпущено» нет")
check(released_text.count("\r\n") == crlf, f"журнал выпуска: CRLF сохранены ({crlf})")
check(rel.section_body(released_text, "## 1.0.0 — ") == body, "раздел выпуска = прежний «Не выпущено»")
dev_text = rel.changelog_new_unreleased(released_text, "1.0.0")
lines = dev_text.splitlines()
check(lines.count(rel.UNRELEASED) == 1 and lines.index(rel.UNRELEASED) < lines.index("## 1.0.0 — 2026-10-18"),
      "журнал разработки: пустой «Не выпущено» над разделом 1.0.0")
check(rel.section_body(dev_text, rel.UNRELEASED) == "", "новый «Не выпущено» пуст")
check(dev_text.count("\r\n") == crlf + 2, "журнал разработки: +2 строки, CRLF")
check(raises(rel.changelog_release, released_text, "1.0.1", "2026-10-19") is not None,
      "повторный выпуск без «Не выпущено» — отказ")

# ── 2. preflight на настоящем репозитории (только чтение) ──
print("── 2. preflight")
head_before = rel.git("rev-parse", "HEAD")
try:
    p = rel.preflight("1.0.0")
    check(p == {"version": "1.0.0", "current": "1.0.0.dev0", "base": rel.FIRST_BASE,
                "proto_old": "1.0.3+gpn.1", "proto_new": "1.0.3+gpn.2"}, f"preflight('1.0.0') → {p}")
except rel.ReleaseError as e:
    check(False, f"preflight('1.0.0'): {e}")
check(raises(rel.preflight, "1.0.0.dev0") is not None, "preflight('1.0.0.dev0') — отказ")
check(rel.git("rev-parse", "HEAD") == head_before and not rel.git("tag", "--list"),
      "preflight не изменил HEAD и не создал меток")

# ── 3. Сборка из дерева HEAD ──
print("── 3. Сборка из HEAD")
work = ROOT / "dist" / "plan-check-feat-038"
if work.exists():
    shutil.rmtree(work)
tree = rel.extract("HEAD", work / "src")
n_examples = len(rel.git("ls-files", f"{rel.SOLVER}/examples").splitlines())
n_18 = len(rel.git("ls-files", f"{rel.SOLVER}/examples/18_prototype_input").splitlines())
z = work / "examples-v1.0.0.zip"
n = rel.zip_examples(tree / "examples", z)
with zipfile.ZipFile(z) as zf:
    names = zf.namelist()
check(n == n_examples - n_18 == len(names), f"архив: {n} файлов = {n_examples} отслеживаемых − {n_18} примера 18")
check(all(s.startswith("examples/") for s in names), "все пути архива — examples/…")
check(not any(s.startswith("examples/18_prototype_input/") for s in names), "примера 18 в архиве нет")
check({"examples/run_all.py", "examples/README.md", "examples/06_table_corey_rp/config.json"} <= set(names),
      "в архиве run_all.py, README.md, конфиг примера 06")
check(rel.selfcheck(tree).startswith("11 passed"), "самопроверка дерева HEAD: 11 passed")

eol = {f: rel.read_text(work / "src" / f).count("\r\n") for f in rel.EDITED}
rel.apply_release_edits(work / "src", "1.0.0", "2026-10-18", "1.0.3+gpn.1", "1.0.3+gpn.2")
check(rel.read_version(work / "src" / rel.SOLVER_INIT) == "1.0.0"
      and rel.read_version(work / "src" / rel.PROTO_INIT) == "1.0.3+gpn.2", "правка выпуска: 1.0.0 и +gpn.2")
check('"radial-blackoil==1.0.3+gpn.2"' in rel.read_text(work / "src" / rel.SOLVER_PYPROJECT),
      "требование решателя → ==1.0.3+gpn.2")
check({f: rel.read_text(work / "src" / f).count("\r\n") for f in rel.EDITED} == eol,
      f"окончания строк четырёх файлов не изменились {eol}")
check(rel.selfcheck(tree).startswith("11 passed"), "самопроверка после правки выпуска: 11 passed")
notes = rel.section_body(rel.read_text(tree / "CHANGELOG.md"), "## 1.0.0 — ")
check(notes == body, "заметки выпуска = раздел журнала")

wheels = rel.build_wheels(tree, work / "wheels", "1.0.0", "1.0.3+gpn.2")
check([w.name for w in wheels] == ["gpn_multiphase_solver-1.0.0-py3-none-any.whl",
                                   "radial_blackoil-1.0.3+gpn.2-py3-none-any.whl"], f"колёса {[w.name for w in wheels]}")
for w, ver in zip(wheels, ["1.0.0", "1.0.3+gpn.2"]):
    with zipfile.ZipFile(w) as zf:
        members = zf.namelist()
        # METADATA setuptools на Windows — с CRLF: сверка по строкам
        meta = zf.read(next(s for s in members if s.endswith(".dist-info/METADATA"))).decode().splitlines()
    check(f"Version: {ver}" in meta, f"{w.name}: METADATA Version {ver}")
    if w.name.startswith("gpn"):
        check("Requires-Dist: radial-blackoil==1.0.3+gpn.2" in meta, "решатель требует radial-blackoil==1.0.3+gpn.2")
        check(not any(s.startswith(("tests/", "examples/", "HydroSolverPrototype/")) for s in members),
              "в колесе решателя нет tests/, examples/, прототипа")
    else:
        check(all(s.startswith(("radial_blackoil/", "radial_blackoil-")) for s in members),
              "в колесе прототипа только radial_blackoil")

dev = rel.apply_dev_edits(work / "src", "1.0.0")
check(dev == "1.0.1.dev0" and rel.read_version(work / "src" / rel.SOLVER_INIT) == dev, "номер разработки 1.0.1.dev0")
check(rel.selfcheck(tree).startswith("11 passed"), "самопроверка после номера разработки: 11 passed")

# Порча: требование решателя не совпадает с литералом прототипа — самопроверка ловит
rel.write_proto_pin(work / "src" / rel.SOLVER_PYPROJECT, "1.0.3+gpn.2", "1.0.3+gpn.1")
check(raises(rel.selfcheck, tree) is not None, "порча требования прототипа — самопроверка отказывает")
check(raises(rel.build_wheels, tree, work / "wheels2", "1.0.0", "1.0.3+gpn.2") is not None,
      "колесо с другим номером — проверка имён отказывает")

# ── 4. Откат на учебном репозитории ──
print("── 4. Откат")
rb = work / "rb"
rb.mkdir()
def g(*a):
    return subprocess.run(["git", *a], cwd=rb, capture_output=True, text=True, check=True).stdout.strip()
g("init", "-q", "-b", "main")
g("config", "user.email", "probe@example.invalid"); g("config", "user.name", "probe")
g("config", "core.autocrlf", "true")
for f in rel.EDITED:
    (rb / f).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / f, rb / f)
(rb / "vault").mkdir()
(rb / "vault" / "note.md").write_text("исходная заметка\n", encoding="utf-8")
g("add", "."); g("commit", "-q", "-m", "старт")
start = g("rev-parse", "HEAD")
(rb / "vault" / "note.md").write_text("незакоммиченная правка\n", encoding="utf-8")   # как общие файлы vault
rel.ROOT = rb
rel.apply_release_edits(rb, "1.0.0", "2026-10-18", "1.0.3+gpn.1", "1.0.3+gpn.2")
rel.git("commit", "-m", "release: 1.0.0", "--", *rel.EDITED)
rel.git("tag", "-a", "v1.0.0", "-m", "Выпуск 1.0.0")
rel.apply_dev_edits(rb, "1.0.0")                       # не закоммичено: отказ между правкой и коммитом
check(g("log", "-1", "--format=%s") == "release: 1.0.0" and "vault/note.md" not in g("show", "--name-only", "--format="),
      "коммит выпуска — только четыре файла, vault не попал")
rel.rollback(start, "v1.0.0")
check(g("rev-parse", "HEAD") == start, "откат: HEAD на старте")
check(g("tag", "--list") == "", "откат: метки нет")
check(g("status", "--porcelain", "--", *rel.EDITED) == "", "откат: четыре файла как на старте")
check((rb / "vault" / "note.md").read_text(encoding="utf-8") == "незакоммиченная правка\n",
      "откат: незакоммиченная правка vault осталась")
rel.ROOT = ROOT

# ── 5. Печать в канал без PYTHONIOENCODING (cp1251) ──
print("── 5. Печать в канал cp1251")
import os
env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, env=env)   # без аргумента — докстринг с «→»
check(r.returncode == 2, f"вызов без аргумента в канал cp1251: код {r.returncode} (2 — докстринг напечатан, не UnicodeEncodeError)")

import stat
# Объекты git — только для чтения: rmtree на Windows без снятия атрибута отказывает
shutil.rmtree(work, onexc=lambda f, p, e: (os.chmod(p, stat.S_IWRITE), f(p)))
print("ИТОГ: " + ("все проверки ОК" if ok_all else "ЕСТЬ ОШИБКИ"))
sys.exit(0 if ok_all else 1)
