"""VAL-005, аудит: применить тексты плана §5.1–§5.6 к копии tests/ + examples/.

Копия — probes/impl/numerical_solver/{tests, examples, pyproject.toml};
HydroSolverPrototype, gpn_multiphase_solver, configs — ссылки-переходы (junction)
на основной каталог (тесты ищут их рядом с tests/). Тексты берутся из файла
плана дословно; каждая правка «Было → Стало» проверяет, что «Было» найдено
ровно один раз. §5.7 (сводный README) не применяется — только проверка, что
исходные строки на месте. Конвертация книги — запуском prototype_input.py
копии, как в шаге 2 плана.

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\val-005\\probes\\apply_plan.py
Удаление копии: cmd /c rmdir (только ссылки!), затем Remove-Item -Recurse.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC = ROOT / "numerical_solver"
PLAN = ROOT / "vault" / "plans" / "val-005 prototype-template-example.md"
DST = HERE / "impl" / "numerical_solver"
NAME = "18_prototype_input"

plan = PLAN.read_text(encoding="utf-8")


def section(title: str) -> str:
    """Текст подраздела плана от заголовка '### <title>' до следующего '### ' или '## '."""
    i = plan.index(f"### {title}")
    m = re.search(r"\n(### |## )", plan[i + 4:])
    return plan[i: i + 4 + m.start()] if m else plan[i:]


def blocks(text: str, lang: str) -> list[str]:
    """Блоки кода ```lang … ``` с учётом отступа (пункты списка — 3 пробела)."""
    out = []
    for m in re.finditer(rf"^( *)```{lang}\n(.*?)^\1```", text, re.S | re.M):
        ind = len(m.group(1))
        out.append("\n".join(l[ind:] for l in m.group(2).splitlines()) + "\n")
    return out


def replace_once(path: Path, old: str, new: str, what: str) -> None:
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        print(f"  ✗ {what}: «Было» найдено {n} раз")
        return
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"  ✓ {what}")


# ── Копия ──
if DST.exists():
    print("копия уже есть — удалите её (см. docstring) и запустите снова")
    sys.exit(1)
DST.mkdir(parents=True)
ign = shutil.ignore_patterns("output", "__pycache__", ".pytest_cache")
shutil.copytree(SRC / "tests", DST / "tests", ignore=ign)
shutil.copytree(SRC / "examples", DST / "examples", ignore=ign)
shutil.copy2(SRC / "pyproject.toml", DST / "pyproject.toml")
for link in ("HydroSolverPrototype", "gpn_multiphase_solver", "configs"):
    subprocess.run(["cmd", "/c", "mklink", "/J", str(DST / link), str(SRC / link)],
                   check=True, capture_output=True)
print(f"копия: {DST}")

# ── §5.1: модуль — черновик с заменой строки PROTO_ROOT ──
ex = DST / "examples" / NAME
ex.mkdir()
s51 = section("5.1.")
old_root, new_root = blocks(s51, "python")[:2]
draft = (HERE / "draft_18" / "prototype_input.py").read_text(encoding="utf-8")
n = draft.count(old_root)
(ex / "prototype_input.py").write_text(draft.replace(old_root, new_root), encoding="utf-8")
print(f"  {'✓' if n == 1 else '✗'} §5.1 prototype_input.py (замена PROTO_ROOT найдена {n} раз)")

# ── Шаг 2, п. 2: конвертация книги запуском модуля копии ──
r = subprocess.run([str(SRC / ".venv" / "Scripts" / "python.exe"), str(ex / "prototype_input.py")],
                   cwd=DST, capture_output=True, text=True, encoding="utf-8")
print(f"  конвертация: код {r.returncode}; {r.stdout.strip()} {r.stderr.strip()[-300:]}")

# ── §5.2, §5.3: main.py и README ──
(ex / "main.py").write_text(blocks(section("5.2."), "python")[0], encoding="utf-8")
i53 = plan.index("### 5.3.")
md = re.search(r"````markdown\n(.*?)\n````", plan[i53:], re.S).group(1) + "\n"
(ex / "README.md").write_text(md, encoding="utf-8")
print("  ✓ §5.2–5.3: main.py, README.md")

# ── §5.4: списки и комментарии ──
s54 = section("5.4.")
py = blocks(s54, "python")
te = DST / "tests" / "test_examples.py"
tm = DST / "tests" / "test_energy_matrix_examples.py"
replace_once(te, '    "17_shut_in_strong_cooling",\n    "19_rs150_cooling",',
             '    "17_shut_in_strong_cooling",\n    "18_prototype_input",\n    "19_rs150_cooling",',
             "§5.4.1 ALL_EXAMPLES (test_examples)")
replace_once(te, '    "16_well_shut_in",\n]',
             '    "16_well_shut_in",\n    "18_prototype_input",\n]', "§5.4.2 NEEDS_SG_SECTION")
replace_once(te, "стоит одного расчёта, а не двадцати двух (~5 мин)",
             "стоит одного расчёта, а не двадцати трёх (~5.5 мин)", "§5.4.3 комментарий фикстуры")
replace_once(te, "все 21 — около 255 с", "все 23 — около 5.5 мин", "§5.4.4 docstring модуля")
replace_once(tm, "# Те же 22 сценария", "# Те же 23 сценария", "§5.4.5 комментарий списка")
replace_once(tm, '    "17_shut_in_strong_cooling",\n    "19_rs150_cooling",',
             '    "17_shut_in_strong_cooling",\n    "18_prototype_input",\n    "19_rs150_cooling",',
             "§5.4.5 ALL_EXAMPLES (матрица)")
replace_once(tm, py[0], py[1].replace("<замер>", "~30"), "§5.4.6 комментарий slow")

# ── §5.5: класс в конец test_examples.py ──
cls = blocks(section("5.5."), "python")[0]
with te.open("a", encoding="utf-8") as f:
    f.write("\n\n" + cls)
print("  ✓ §5.5 фикстура prototype_18 и класс TestPrototypeInput")

# ── §5.6: conftest ──
s56 = blocks(section("5.6."), "python")
cf = DST / "tests" / "conftest.py"
replace_once(cf, s56[0], s56[1], "§5.6 _HEAVY_FIXTURES")
replace_once(cf, "17 — около 100 с; все 22 — ~5 мин", "17 — около 100 с; все 23 — ~5.5 мин",
             "§5.6 комментарий времени")

# ── §5.7: только проверка исходных строк сводного README ──
readme = (SRC / "examples" / "README.md").read_text(encoding="utf-8")
for frag in ("Охлаждение забоя на корреляциях PVT и ОФП Кори: горячий пласт",
             "`dt_integration` = 3600 с; стационарная аналитика отключена.\n\n### Охлаждение",
             "| 21 | 14 с | **17** | **112 с** |",
             "у 13b и 16 — на семи: 0, 5, …, 30 сут)",
             "| 17 | Standing / Corey | — | — | не строится (`steady_state=False`) |",
             "тривиален ($p \\equiv p_0$ всюду), флаг тот же.",
             "| 17 | Standing | 79.51 … 332.41 | 51 | 0 | 0 | 0 |",
             "кондукция — в 10, 11, 12, 13a, 13b, 14, 15, 16, 17 и 19–21",
             "| **17** | **2.5 / 0.13 / 0.05** | $1.5\\cdot10^{-15}$ | $+6.86\\cdot10^{6}$ |",
             "| 10 | $2.6\\cdot10^{-9}$ | $4.9\\cdot10^{-9}$ | | 19 | $1.0\\cdot10^{-11}$ | $4.4\\cdot10^{-11}$ |",
             "У 13b, 14, 16, 17 и 19–21 она", "Сценарии 17 и 19–21 задают параметры",
             "кроме 10, 11, 12, 13a, 13b, 14, 15, 16, 17 и 19–21", "У 10–17 и 19–21 $\\lambda$",
             "`closed_form_convergence` (05)."):
    print(f"  {'✓' if frag in readme else '✗'} §5.7 «{frag[:60]}»")
