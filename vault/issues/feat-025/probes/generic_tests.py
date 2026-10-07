"""FEAT-025: общие тесты test_examples.py и сверка матрицы на конфигах probes/final/.

Модуль tests/test_examples.py импортируется, его списки примеров подменяются
тремя папками probes/final/ (examples/ не трогается). Вызываются методы классов
TestRunAll, TestTwoPhase, TestSharedChecks, TestPvtPlot, которым нужны только
results / name / tmp_path. Тесты структуры и README здесь не проверяются — им
нужны main.py и README.md в папке примера.

Сверка матрицы — логика test_matrix_matches_reference с допуском варианта Б
плана: a, b, c — rtol = RTOL, atol = 0; d — atol = RTOL·max|d_ref|.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\generic_tests.py
"""

import inspect
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "tests", SOLVER / "examples",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import test_examples as te  # noqa: E402
import test_energy_matrix_examples as tm  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

FINAL = HERE / "final"
NAMES = ["19_rs150_cooling", "20_rs500_cooling", "21_rs100_cooling"]
TMP = HERE / "generic_tmp"

# ── Подмена списков модуля: только три новых примера ──
te.EXAMPLES_DIR = FINAL
te.ALL_EXAMPLES = NAMES
te.SINGLE_PHASE = []
te.TWO_PHASE = NAMES
te.TABLE_PVT = []
te.ANALYTIC_PVT = NAMES


def run_generic():
    t0 = time.perf_counter()
    results = {n: te._run(n) for n in NAMES}
    print(f"расчёт трёх примеров: {time.perf_counter() - t0:.1f} с")
    ok = fail = 0
    for cls in (te.TestRunAll, te.TestTwoPhase, te.TestSharedChecks, te.TestPvtPlot):
        obj = cls()
        for mname, meth in inspect.getmembers(obj, inspect.ismethod):
            if not mname.startswith("test_"):
                continue
            params = list(inspect.signature(meth).parameters)
            if set(params) - {"results", "name", "tmp_path"}:
                print(f"   пропуск {cls.__name__}.{mname}: параметры {params}")
                continue
            for nm in (NAMES if "name" in params else [None]):
                kw = {}
                if "results" in params:
                    kw["results"] = results
                if "name" in params:
                    kw["name"] = nm
                if "tmp_path" in params:
                    d = TMP / f"{mname}_{nm or 'all'}"
                    d.mkdir(parents=True, exist_ok=True)
                    kw["tmp_path"] = d
                label = f"{cls.__name__}.{mname}" + (f"[{nm}]" if nm else "")
                try:
                    meth(**kw)
                    ok += 1
                except Exception:  # noqa: BLE001 — проба: печатаем и идём дальше
                    fail += 1
                    print(f"   ПАДАЕТ {label}:\n{traceback.format_exc(limit=2)}")
    print(f"общие тесты: прошло {ok}, упало {fail}")


def run_matrix():
    for nm in NAMES:
        cfg = load_config(FINAL / nm / "config.json")
        cfg.output.log_level = "ERROR"
        sim, init = SimulatorFactory.from_config(cfg)
        n = [0]

        def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
            ra, rb, rc, rd = tm.build_reference(sim._grid, sim._pvt, cfg.rock,
                                                hydro_result, state_prev, dt, bc)
            np.testing.assert_allclose(a, ra, rtol=tm.RTOL, atol=0.0)
            np.testing.assert_allclose(b, rb, rtol=tm.RTOL, atol=0.0)
            np.testing.assert_allclose(c, rc, rtol=tm.RTOL, atol=0.0)
            np.testing.assert_allclose(d, rd, rtol=tm.RTOL,
                                       atol=tm.RTOL * float(np.max(np.abs(rd))))
            assert a[0] == 0.0 and c[-1] == 0.0
            n[0] += 1

        sim._energy.matrix_probe = probe
        t0 = time.perf_counter()
        try:
            sim.run(init)
            print(f"   матрица {nm}: {n[0]} вызовов — OK, {time.perf_counter() - t0:.1f} с")
        except AssertionError as e:
            print(f"   матрица {nm}: ПАДАЕТ на вызове {n[0]}: {str(e)[:300]}")


if __name__ == "__main__":
    run_generic()
    run_matrix()
