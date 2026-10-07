"""FEAT-024, аудит раунд 2: исполнить тесты и main.py плана дословно.

Код класса TestHighGorCooling и main.py извлекается из файла плана
(блоки ```python), данные — make_14_config.py в папку audit2/. Фикстура
results — та же _run из tests/test_examples.py, EXAMPLES_DIR подменён.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-024\\probes\\audit2_plan_tests.py
"""

import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
NS = ROOT / "numerical_solver"
PLAN = ROOT / "vault" / "plans" / "feat-024 high-gor-cooling-example.md"
EX_DIR = HERE / "audit2"
NAME = "14_high_gor_cooling"

sys.path.insert(0, str(NS / "tests"))
sys.path.insert(0, str(NS / "HydroSolverPrototype" / "Prototype_1.0.3"))
import test_examples as te  # noqa: E402

# ── Данные — генератором плана (шаг 2) ──
subprocess.run([sys.executable, str(HERE / "make_14_config.py"), str(EX_DIR / NAME)],
               check=True)

# ── Блоки python из плана ──
blocks = re.findall(r"```python\n(.*?)```", PLAN.read_text(encoding="utf-8"), re.S)
main_src = next(b for b in blocks if "run_example(" in b)
cls_src = next(b for b in blocks if "class TestHighGorCooling" in b)
(EX_DIR / NAME / "main.py").write_text(main_src, encoding="utf-8")

# ── Фикстура results: _run тестового модуля на папке пробы ──
te.EXAMPLES_DIR = EX_DIR
t0 = time.perf_counter()
results = {NAME: te._run(NAME)}
print(f"_run: {time.perf_counter() - t0:.1f} с, записей {len(results[NAME]['history'].states)}")

ns = {"np": np, "pytest": pytest, "EXAMPLES_DIR": EX_DIR,
      "_pvt_of_config": te._pvt_of_config}
exec(compile(cls_src, "plan:TestHighGorCooling", "exec"), ns)
T = ns["TestHighGorCooling"]()

ok = True
for name in sorted(n for n in dir(T) if n.startswith("test_")):
    fn = getattr(T, name)
    try:
        fn(results) if fn.__code__.co_argcount == 2 else fn()
        print(f"PASS {name}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL {name}: {type(e).__name__}: {e}")

# ── README шага 6 и общие тесты test_examples.py на примере 14 ──
# Циклы по ALL_EXAMPLES / TWO_PHASE берут глобалы модуля в момент вызова —
# сужаем их до 14, чтобы не пересчитывать 15 остальных примеров.
readme = re.search(r"````markdown\n(.*?)````", PLAN.read_text(encoding="utf-8"), re.S).group(1)
(EX_DIR / NAME / "README.md").write_text(readme, encoding="utf-8")
sys.path.insert(0, str(NS / "examples"))
te.ALL_EXAMPLES, te.TWO_PHASE, te.ANALYTIC_PVT = [NAME], [NAME], []
tmp = EX_DIR / "tmp"
tmp.mkdir(exist_ok=True)
shared = [
    (te.TestStructure, "test_required_files", (NAME,)),
    (te.TestConfigs, "test_load_config_passes", (NAME,)),
    (te.TestConfigs, "test_referenced_csv_present", (NAME,)),
    (te.TestConfigs, "test_no_dead_output_format", (NAME,)),
    (te.TestRunAll, "test_completes", (results, NAME)),
    (te.TestRunAll, "test_no_nan_inf", (results, NAME)),
    (te.TestRunAll, "test_physical_bounds", (results, NAME)),
    (te.TestRunAll, "test_oil_production", (results, NAME)),
    (te.TestTwoPhase, "test_gas_appears", (results, NAME)),
    (te.TestTwoPhase, "test_rs_decreased", (results, NAME)),
    (te.TestTwoPhase, "test_gas_produced", (results, NAME)),
    (te.TestReadme, "test_has_modification_section", (NAME,)),
    (te.TestReadme, "test_has_saturation_section", (NAME,)),
    (te.TestReadme, "test_documents_module_combination", (NAME,)),
    (te.TestSharedChecks, "test_energy_balance_all_examples", (results,)),
    (te.TestSharedChecks, "test_conduction_term_always_computed", (results,)),
    (te.TestSharedChecks, "test_full_key_set_always_returned", (results,)),
    (te.TestPvtPlot, "test_plot_pvt_all_examples", (results, tmp)),
    (te.TestPvtPlot, "test_report_pb_matches_pvt", (results,)),
    (te.TestPvtPlot, "test_full_key_set_always_returned", (results,)),
    (te.TestPvtPlot, "test_physical_branch_matches_rs_analytics", (results,)),
    (te.TestPvtPlot, "test_rho_matches_formula", (results,)),
]
for cls, meth, args in shared:
    try:
        getattr(cls(), meth)(*args)
        print(f"PASS {cls.__name__}.{meth}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL {cls.__name__}.{meth}: {type(e).__name__}: {e}")

# ── Запасы порогов: насколько тесты далеко от границ ──
r = results[NAME]
T0 = r["config"].initial_conditions.T0
dT = np.array([st.T[0] - T0 for st in r["history"].states[1:]])
gor = r["q_g"][1:] / r["q_o"][1:]
print(f"dT(r_w): {dT.min():.4f} … {dT.max():.4f} К; T_well = {r['T_well']:.5f}")
print(f"GOR: {gor[0]:.3f} … {gor[-1]:.3f}; min diff {np.diff(gor).min():.4f}")
print(f"Sg(r_w) = {float(r['Sg'][0]):.5f}")
print(f"q_o[0] = {r['q_o'][0]}, q_g[0] = {r['q_g'][0]}")
print("ИТОГ:", "все тесты плана проходят" if ok else "есть падения")
