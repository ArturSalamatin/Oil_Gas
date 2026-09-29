"""FEAT-022: тождество Дарси у Кори — точная формула против таблицы, которую видит решатель.

darcy_identity_all_examples.py: у табличной ОФП тождество с местным G^g/G^o
выполняется до 2e-16, у Кори (03, 04a, 06) — только до ~2e-3. Гипотеза:
factory._get_or_create_proto_rp табулирует CoreyRP на 101 узле по Sg
(шаг 0.01) с линейной интерполяцией, и гидродинамика считает с таблицей,
а closed_form и relperm_plot — с точной формулой.

Проверка: то же тождество с ОФП = та самая таблица (через PrototypeRPAdapter).
Плюс — прямое сравнение krg таблицы и формулы у порога S_gc.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-022\\probes\\corey_tabulation_check.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import (  # noqa: E402
    SimulatorFactory, _create_relperm, _get_or_create_proto_rp, PrototypeRPAdapter)
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from closed_form import Closure  # noqa: E402

for name in ("03_standing_corey", "06_table_corey_rp"):
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    h = sim.run(init)
    pvt = sim._energy._pvt
    exact = _create_relperm(cfg)
    table = PrototypeRPAdapter(_get_or_create_proto_rp(exact))
    st, hr = h.states[-1], h.hydro_results[-1]
    N = len(st.p)
    two = np.nonzero(st.Sg > 0)[0]
    gor = hr.G_g[:N] / hr.G_o[:N]
    res = {}
    for label, rp in (("формула", exact), ("таблица 101 узел", table)):
        mob = [j for j in two if rp.krg(np.array([st.Sg[j]]))[0] > 0.0]
        res[label] = max(abs(Closure(pvt, rp, gor[j]).Sg(st.p[j]) - st.Sg[j]) for j in mob)
    print(f"{name}: Sg в 2ф зоне {st.Sg[two].min():.4f} … {st.Sg[two].max():.4f}; "
          f"тождество: формула {res['формула']:.2e}, таблица {res['таблица 101 узел']:.2e}")

    S = np.array([0.051, 0.055, 0.06, 0.07, 0.08, 0.10])
    ke, kt = exact.krg(S), table.krg(S)
    print("   Sg     krg формула   krg таблица   отношение")
    for s, a, b in zip(S, ke, kt):
        print(f"   {s:.3f}  {a:12.4e}  {b:12.4e}  {b / a if a else float('nan'):9.3f}")
