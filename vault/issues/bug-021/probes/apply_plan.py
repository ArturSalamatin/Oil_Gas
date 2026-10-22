"""BUG-021, проверка текста плана: блоки «было/стало» шагов 2–6 применяются к копиям файлов.

Каждый блок «было» должен найтись в своём файле ровно один раз. Метод _newton_fixed_active_set
после правки — ровно planned_code.NEW_V2. Тесты прототипа в копии (с новым тестом шага 2) — passed.
Копии — probes/applied_plan/ (в .gitignore вместе с vault/issues).

Запуск — из каталога numerical_solver основного дерева:
    .venv\\Scripts\\python <P>\\apply_plan.py
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PLAN = ROOT / "vault" / "plans" / "bug-021 newton-final-iterate-check.md"
NS = Path.cwd()
PROTO = NS / "HydroSolverPrototype" / "Prototype_1.0.3"
DST = HERE / "applied_plan"
sys.path.insert(0, str(HERE))
import planned_code  # noqa: E402

text = PLAN.read_text(encoding="utf-8")
steps = text[text.index("## 6. Шаги"):text.index("## 7. Тестовая стратегия")]
blocks = re.findall(r"```(?:python|markdown)\n(.*?)```", steps, flags=re.S)
assert len(blocks) == 18, f"блоков кода в шагах: {len(blocks)}, ожидалось 18"
inline = re.findall(r"- было: `(.*?)`\n- стало: `(.*?)`\n", steps)
assert len(inline) == 3, f"строчных пар было/стало: {len(inline)}, ожидалось 3"

if DST.exists():
    shutil.rmtree(DST)
dp = DST / "Prototype_1.0.3"
dp.mkdir(parents=True)
for name in ("radial_blackoil", "tests", "docs"):
    shutil.copytree(PROTO / name, dp / name, ignore=shutil.ignore_patterns("__pycache__"))
# test_failure_report.py (DEBT-030) читает regression/inputs/T04.xlsx
shutil.copytree(PROTO / "regression" / "inputs", dp / "regression" / "inputs")
for f in PROTO.iterdir():
    if f.is_file():
        shutil.copy2(f, dp / f.name)
other = {
    "glob": NS / "tests" / "test_prototype_globalization.py",
    "wb": NS / "tests" / "test_prototype_well_branch.py",
    "em": NS / "tests" / "test_energy_matrix_examples.py",
    "r13b": NS / "examples" / "13b_pwf_alternating" / "README.md",
    "r05": NS / "examples" / "05_standing_table_rp" / "README.md",
}
copies = {}
for k, src in other.items():
    copies[k] = DST / k / src.name
    copies[k].parent.mkdir(parents=True)
    shutil.copy2(src, copies[k])
bo = dp / "radial_blackoil" / "blackoil.py"
cl = dp / "CHANGELOG_1.0.3.md"


def replace(path, before, after, label):
    src = path.read_text(encoding="utf-8")
    n = src.count(before)
    assert n == 1, f"{label}: блок «было» найден {n} раз в {path.name}:\n{before}"
    path.write_text(src.replace(before, after), encoding="utf-8")
    print(f"{label}: применён ({path.name})")


# Шаг 2 — новый тест; сверка с проверенной копией
(dp / "tests" / "test_newton_last_iteration.py").write_text(blocks[0], encoding="utf-8")
same = blocks[0] == (HERE / "planned_tests" / "test_newton_last_iteration.py").read_text(encoding="utf-8")
print(f"шаг 2: тест {'совпадает' if same else 'ОТЛИЧАЕТСЯ'} с planned_tests/")
# Шаг 3
replace(bo, blocks[1], blocks[2], "3.1 docstring модуля")
replace(bo, blocks[3], blocks[4], "3.2 метод")
m = planned_code.METHOD_RE.findall(bo.read_text(encoding="utf-8"))
print(f"3.2: метод {'= NEW_V2' if m == [planned_code.NEW_V2] else 'НЕ РАВЕН NEW_V2'}")
# Шаг 4
replace(copies["glob"], blocks[5], blocks[6], "4.1 docstring теста")
replace(copies["glob"], blocks[7], blocks[8], "4.2 перехват Ньютона")
replace(copies["wb"], blocks[9], blocks[10], "4.3 комментарий")
# Шаг 5 — раздел CHANGELOG в конец
cl.write_text(cl.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + blocks[11], encoding="utf-8")
print("5: CHANGELOG — раздел добавлен; последний раздел до него:",
      re.findall(r"^## .*$", cl.read_text(encoding="utf-8"), flags=re.M)[-2])
# Шаг 6
replace(copies["r13b"], inline[0][0] + "\n", inline[0][1] + "\n", "6.1 строка 1.5 сут")
replace(copies["r13b"], inline[1][0] + "\n", inline[1][1] + "\n", "6.1 строка 2 сут")
replace(copies["r13b"], blocks[12], blocks[13], "6.2 абзац")
replace(copies["r13b"], inline[2][0] + "\n", inline[2][1] + "\n", "6.3 баланс")
replace(copies["r05"], blocks[14], blocks[15], "6.4 README 05")
replace(copies["em"], blocks[16], blocks[17], "6.5 комментарий теста")

r = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
                   cwd=dp, capture_output=True, text=True)
print("тесты прототипа в копии:", r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-2000:])
