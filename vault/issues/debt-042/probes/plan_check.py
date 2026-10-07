r"""DEBT-042: проверка кода плана подменой — тесты шага 2 на текущих и на новых ридерах.

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-042\probes\plan_check.py
                              ... plan_check.py --pytest   # быстрый уровень на подменённых ридерах
Код берётся из плана (блоки ```python шагов 2 и 3), файлы проекта не меняются:
реализация шага 3 исполняется в пространстве имён модуля factory (подмена в памяти).
"""
import json
import re
import shutil
import sys
from pathlib import Path

# Проверяемый код — из текущего каталога (numerical_solver/ основного каталога
# или worktree), а не от расположения пробы: см. tables_check.py
SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

import pytest                                                     # noqa: E402
from gpn_multiphase_solver import factory                         # noqa: E402
from gpn_multiphase_solver.io.config import load_config          # noqa: E402

print(f"Код: {Path(factory.__file__).resolve()}")

PLAN = Path(__file__).resolve().parents[3] / "plans" / "debt-042 strict-csv-readers.md"
WORK = Path(__file__).resolve().parent / "plan_check_tmp"
PROBES = Path(__file__).resolve().parent

blocks = re.findall(r"```python\n(.*?)```", PLAN.read_text(encoding="utf-8"), re.S)
tests_src = next(b for b in blocks if "class TestCSVStrictParsing" in b)
impl_src = next(b for b in blocks if "def _read_numeric_csv" in b)


def run_tests(label):
    """Исполнить блок тестов плана против текущих функций factory."""
    ns = {
        "pytest": pytest, "shutil": shutil, "load_config": load_config,
        "SimulatorFactory": factory.SimulatorFactory,
        "TABLE_CONFIG": SOLVER / "configs" / "table_pvt" / "config.json",
        "OIL_HEADER": "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n",
        "OIL_BRANCH_0": "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n",
        "OIL_BRANCH_30": "30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n",
        "_read_oil_pvt_csv": factory._read_oil_pvt_csv,
        "_read_gas_pvt_csv": factory._read_gas_pvt_csv,
        "_read_relperm_csv": factory._read_relperm_csv,
    }
    exec(tests_src, ns)
    cls = ns["TestCSVStrictParsing"]
    names = [n for n in dir(cls) if n.startswith("test_")]
    passed, failed = [], []
    for n in names:
        tmp = WORK / f"{label}_{n}"
        tmp.mkdir(parents=True)
        try:
            getattr(cls(), n)(tmp)
            passed.append(n)
        except BaseException as e:            # pytest.fail — BaseException
            failed.append((n, type(e).__name__, str(e).splitlines()[0][:90] if str(e) else ""))
    print(f"== {label}: {len(passed)} passed, {len(failed)} failed из {len(names)}")
    for n, t, m in failed:
        print(f"   FAIL {n}: {t}: {m}")
    for n in passed:
        print(f"   ok   {n}")


def snapshot_compare():
    ref = json.loads((PROBES / "tables_snapshot.json").read_text(encoding="utf-8"))
    readers = {"oil_pvt.csv": factory._read_oil_pvt_csv, "gas_pvt.csv": factory._read_gas_pvt_csv,
               "relperm.csv": factory._read_relperm_csv}
    diff = []
    for rel, rows in ref.items():
        p = SOLVER / rel
        out = readers[p.name](p)
        if [list(r) for r in out] != rows:
            diff.append(rel)
    print(f"== Снимок 47 таблиц новыми ридерами: {len(ref)} таблиц, "
          + ("побитово совпадает" if not diff else f"РАСХОЖДЕНИЯ: {diff}"))


def show_messages():
    """Тексты сообщений нового разборщика — для чтения глазами."""
    cases = {
        "oil_pvt.csv": "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n0.0,5000000,1,05,0.003\n",
        "gas_pvt.csv": "pressure_Pa;Bg;mu_g_Pa_s\n5000000;0,02;0,000012\n",
        "relperm.csv": "Sg,kro,krg\n0.0,1.0,0.0\n0.4,nan,0.2\n",
    }
    print("== Сообщения")
    for name, text in cases.items():
        d = WORK / "msg"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(text, encoding="utf-8")
        reader = {"oil_pvt.csv": factory._read_oil_pvt_csv, "gas_pvt.csv": factory._read_gas_pvt_csv,
                  "relperm.csv": factory._read_relperm_csv}[name]
        try:
            reader(d / name)
        except ValueError as e:
            print(f"   {e}")


if __name__ == "__main__" and "--pytest" in sys.argv:
    # Быстрый уровень существующих тестов на подменённых ридерах: модули тестов
    # импортируют _read_*_csv после подмены и получают новые функции
    exec(impl_src, factory.__dict__)
    sys.exit(pytest.main(["tests/", "-m", "not slow", "-q", "-p", "no:cacheprovider"]))

if __name__ == "__main__":
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()
    try:
        run_tests("до_правки")
        exec(impl_src, factory.__dict__)       # подмена ридеров кодом шага 3
        run_tests("после_правки")
        snapshot_compare()
        show_messages()
    finally:
        shutil.rmtree(WORK)
