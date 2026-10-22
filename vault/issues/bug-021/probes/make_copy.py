"""BUG-021, проба при планировании: копия прототипа с исправленным _newton_fixed_active_set.

Копия — probes/applied_v<вариант>/Prototype_1.0.3/ (radial_blackoil, tests, regression без OUTPUT,
файлы верхнего уровня). На ней — тесты прототипа и регрессия против эталона копии
(= эталон основного дерева на момент копирования).

Запуск — из каталога numerical_solver основного дерева:
    .venv\\Scripts\\python <P>\\make_copy.py [1|2]          # по умолчанию 2
Затем из копии:
    ..\\..\\..\\..\\..\\numerical_solver\\.venv\\Scripts\\python -m pytest tests -q
    ... regression\\run_regression.py [--quick | --case T05S_N200_DT5m]
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import planned_code  # noqa: E402

variant = int(sys.argv[1]) if len(sys.argv) > 1 else 2
SRC = Path.cwd() / "HydroSolverPrototype" / "Prototype_1.0.3"
DST = HERE / f"applied_v{variant}" / "Prototype_1.0.3"
if not (SRC / "radial_blackoil").is_dir():
    raise SystemExit("запускать из каталога numerical_solver")

if DST.exists():
    shutil.rmtree(DST)
DST.mkdir(parents=True)
skip = shutil.ignore_patterns("__pycache__", "OUTPUT")
for name in ("radial_blackoil", "tests", "regression", "docs", "INPUT"):
    shutil.copytree(SRC / name, DST / name, ignore=skip)
for f in SRC.iterdir():
    if f.is_file():   # run_prototype.py, VERSION.txt, BUILD.txt, ... (test_output_contract их проверяет)
        shutil.copy2(f, DST / f.name)

bo = DST / "radial_blackoil" / "blackoil.py"
if variant:   # 0 — копия без правки (текущий код), для проверки, что новые тесты на нём падают
    bo.write_text(planned_code.patch_text(bo.read_text(encoding="utf-8"), variant), encoding="utf-8")
# Новые тесты плана — в копию
for t in (HERE / "planned_tests").glob("test_*.py"):
    shutil.copy2(t, DST / "tests" / t.name)
print(f"копия: {DST}\nвариант {variant} применён к {bo.name}")
