"""BUG-020, аудит: применить правки плана буквально к копии кода (база + DEBT-030).

Копия — vault/issues/bug-020/probes/impl/numerical_solver: пакет, тесты,
прототип (без OUTPUT), примеры (без output), pyproject.toml. Файлы, которые
меняет ветка DEBT-030 (refactor/debt-030/rejected-step-report), сливаются в
копию через `git merge-file` (база слияния — merge-base с HEAD); репозиторий
и рабочее дерево не меняются. Затем — правки плана BUG-020 по шагам; тексты
«было/стало», методы и тесты извлекаются из файла плана (блоки ```python по
порядку внутри разделов). Каждый якорь «было» должен встречаться ровно один раз.

Аргумент — до какого шага применять: base | step1 | step2 | step3 | step4.

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\bug-020\\probes\\apply_plan.py step4
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC = ROOT / "numerical_solver"
DST = HERE / "impl" / "numerical_solver"
PLAN = ROOT / "vault" / "plans" / "bug-020 shutin-phase-switching-newton.md"
DEBT030 = "refactor/debt-030/rejected-step-report"
PROTO = "HydroSolverPrototype/Prototype_1.0.3"
BLACKOIL = f"{PROTO}/radial_blackoil/blackoil.py"
UPTO = sys.argv[1] if len(sys.argv) > 1 else "step4"
ORDER = ["base", "step1", "step2", "step3", "step4"]
# --bug021: до плана BUG-020 применить правку BUG-021 (решение пользователя: BUG-021
# вливается раньше) — метод из vault/issues/bug-021/probes/planned_code.py (NEW_V2)
# и строка docstring из шага 3.1 плана BUG-021
WITH_BUG021 = "--bug021" in sys.argv
if "--dst" in sys.argv:
    DST = HERE / sys.argv[sys.argv.index("--dst") + 1] / "numerical_solver"

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def git_bytes(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


# ── 1. Копия ──
if DST.exists():
    shutil.rmtree(DST)
ign = shutil.ignore_patterns("__pycache__", ".pytest_cache", "OUTPUT", "output", "*.egg-info")
for d in ("gpn_multiphase_solver", "tests", "examples", PROTO):
    shutil.copytree(SRC / d, DST / d, ignore=ign)
shutil.copy2(SRC / "pyproject.toml", DST / "pyproject.toml")

# ── 2. Слияние DEBT-030 ──
mb = git("merge-base", "HEAD", DEBT030).strip()
changed = git("diff", "--name-only", mb, DEBT030, "--", "numerical_solver").split()
tmp = HERE / "impl" / "_merge"
tmp.mkdir(parents=True, exist_ok=True)
for path in changed:
    rel = path[len("numerical_solver/"):]
    out = DST / rel
    theirs = git_bytes("show", f"{DEBT030}:{path}")
    try:
        base = git_bytes("show", f"{mb}:{path}")
    except subprocess.CalledProcessError:
        base = None
    # «наш» вариант — из HEAD, не из рабочего дерева: там CRLF, в объектах git LF
    # (иначе весь файл — один конфликт)
    try:
        ours = git_bytes("show", f"HEAD:{path}")
    except subprocess.CalledProcessError:
        ours = None
    if base is None or ours is None or ours == base:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(theirs)
        print(f"DEBT-030: {rel} — взят из ветки")
        continue
    for name, data in (("ours", ours), ("base", base), ("theirs", theirs)):
        (tmp / name).write_bytes(data)
    r = subprocess.run(["git", "merge-file", "-p", str(tmp / "ours"), str(tmp / "base"), str(tmp / "theirs")],
                       capture_output=True)
    merged = r.stdout.decode("utf-8")
    if r.returncode != 0:
        # конфликты — только соседние вставки (докстринг модуля, CHANGELOG): берём обе стороны
        merged = re.sub(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", r"\1\2", merged, flags=re.S)
        print(f"DEBT-030: {rel} — слит, конфликтов {r.returncode} (обе стороны)")
    else:
        print(f"DEBT-030: {rel} — слит без конфликтов")
    out.write_text(merged, encoding="utf-8", newline="\n")
shutil.rmtree(tmp)
for d in ("configs", "doc"):
    shutil.copytree(SRC / d, DST / d, ignore=ign)

if WITH_BUG021:
    sys.path.insert(0, str(ROOT / "vault" / "issues" / "bug-021" / "probes"))
    import planned_code  # noqa: E402
    f = DST / BLACKOIL
    src = f.read_text(encoding="utf-8")
    src = planned_code.patch_text(src, 2)
    old_doc = 'fields of the original algorithm, not those of the last fallback attempt.\n"""'
    new_doc = ('fields of the original algorithm, not those of the last fallback attempt.\n'
               'BUG-021: _newton_fixed_active_set tests convergence on every new iterate, the\n'
               'last one included, on the residual its line search has evaluated; no Jacobian\n'
               'is built only to detect convergence.\n"""')
    assert src.count(old_doc) == 1, src.count(old_doc)
    f.write_text(src.replace(old_doc, new_doc), encoding="utf-8", newline="\n")
    print("BUG-021: метод и docstring — ok")

if ORDER.index(UPTO) < 1:
    sys.exit(0)

# ── 3. Блоки плана ──
plan = PLAN.read_text(encoding="utf-8")


def blocks(start, end):
    """Блоки ```python ... ``` между маркерами start и end (по порядку)."""
    i = plan.index(start)
    j = plan.index(end, i + 1)
    return re.findall(r"```python\n(.*?)```", plan[i:j], flags=re.S)


def replace_once(rel, old, new, label):
    f = DST / rel
    text = f.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: якорь найден {n} раз в {rel}")
    f.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    print(f"{label}: ok")


def strip_nl(s):
    return s[:-1] if s.endswith("\n") else s


# Шаг 1: данные и тесты A, B
for name in ("bug020_rs300", "bug020_rs150"):
    d = DST / "tests" / "data" / name
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "data" / f"{name}.json", d / "config.json")
test_ab = blocks("### Шаг 1:", "**Проверка после шага:**")
assert len(test_ab) == 1, len(test_ab)
(DST / "tests" / "test_prototype_phase_switching.py").write_text(test_ab[0], encoding="utf-8", newline="\n")
print("шаг 1: данные и тесты A, B — ok")
# Проверка путей импорта в копии
(DST / "tests" / "test_zz_audit_paths.py").write_text(
    "def test_imports_from_copy():\n"
    "    import gpn_multiphase_solver, radial_blackoil\n"
    "    assert 'probes' in gpn_multiphase_solver.__file__, gpn_multiphase_solver.__file__\n"
    "    assert 'probes' in radial_blackoil.__file__, radial_blackoil.__file__\n",
    encoding="utf-8")

if ORDER.index(UPTO) < 2:
    sys.exit(0)

# Шаг 2
for tag, nxt in (("**2.1", "**2.2"), ("**2.2", "**2.3"), ("**2.3", "**Проверка после шага:**")):
    old, new = blocks(tag, nxt)
    replace_once(BLACKOIL, strip_nl(old), strip_nl(new), f"шаг {tag[2:]}")

if ORDER.index(UPTO) < 3:
    sys.exit(0)

# Шаг 3
# 3.1 — докстринг модуля: вставка перед закрывающими """ первого докстринга
(ins,) = blocks("**3.1", "**3.2")
f = DST / BLACKOIL
text = f.read_text(encoding="utf-8")
k = text.index('"""', 3)
text = text[:k] + ins + text[k:]
f.write_text(text, encoding="utf-8", newline="\n")
print("шаг 3.1: ok")
for tag, nxt in (("**3.2", "**3.3"), ("**3.3", "**3.4")):
    old, new = blocks(tag, nxt)
    replace_once(BLACKOIL, strip_nl(old), strip_nl(new), f"шаг {tag[2:]}")
(methods,) = blocks("**3.4", "**3.5")
replace_once(BLACKOIL, "    def well_rates(self,state):", methods + "    def well_rates(self,state):", "шаг 3.4")
old, new = blocks("**3.5", "**3.6")
replace_once(BLACKOIL, strip_nl(old), strip_nl(new), "шаг 3.5")
# 3.6 — по описанию плана: try третьей ступени без return, ступень 4, блок DEBT-030 вынесен из try
b36 = blocks("**3.6", "**Проверка после шага:**")
was1, was2, became, _final = b36
text = f.read_text(encoding="utf-8")
i = text.index(strip_nl(was1))
j = text.index(strip_nl(was2), i) + len(strip_nl(was2))
segment = text[i:j]
m = re.search(r"            if not rep\.converged:\n(.*?)            return new,rep\n", segment, flags=re.S)
debt030 = m.group(1)
debt030_dedent = "\n".join(line[4:] if line.startswith("    ") else line for line in debt030.split("\n"))
tail = strip_nl(became) + "\n" + debt030_dedent + "        return new,rep\n"
text = text[:i] + tail + text[j + 1:]
f.write_text(text, encoding="utf-8", newline="\n")
print("шаг 3.6: ok")

if ORDER.index(UPTO) < 4:
    sys.exit(0)

# Шаг 4
old, new = blocks("**4.1", "**4.2")
replace_once("gpn_multiphase_solver/factory.py", strip_nl(old), strip_nl(new), "шаг 4.1")
o1, n1, o2, n2 = blocks("**4.2", "**4.3")
replace_once("gpn_multiphase_solver/hydro/prototype_adapter.py", strip_nl(o1), strip_nl(n1), "шаг 4.2а")
replace_once("gpn_multiphase_solver/hydro/prototype_adapter.py", strip_nl(o2), strip_nl(n2), "шаг 4.2б")
cd, cap = blocks("**4.3", "**Проверка после шага:**")
t = DST / "tests" / "test_prototype_phase_switching.py"
t.write_text(t.read_text(encoding="utf-8") + "\n\n" + cd, encoding="utf-8", newline="\n")
replace_once("tests/test_prototype_activation_cap.py", '    assert "малоподвижны" not in msg\n',
             '    assert "малоподвижны" not in msg\n' + cap, "шаг 4.3 (сообщение)")
print("шаг 4: ok")
