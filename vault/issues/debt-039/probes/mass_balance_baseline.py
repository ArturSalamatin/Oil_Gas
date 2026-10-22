"""DEBT-039: замер накопленного баланса массы компонентов на всех примерах, до реализации.

Обёртка EnergySolver.solve (как проба FEAT-019, plan_numbers.py) пишет каждый
ПРИНЯТЫЙ подшаг: dt, потоки компонентов через забой G[0] и контур G[N],
n_substeps результата гидродинамики. n_substeps > 1 на этом уровне — вложенное
дробление (simulator.py, allow_subdivision=False): HydroResult несёт потоки
только последнего внутреннего подшага адаптера, и интеграл dt*G по нему неверен.

Запас компонентов — функцией прототипа component_inventories (phi(p) по
rock.py, B_o, B_g той же PVT, что в невязке Ньютона), а не своими формулами.

Невязка на момент записи k (конвенция: G > 0 — от скважины):
    res_a(t_k) = M_a(t_k) - M_a(0) + sum_{подшаги до t_k} dt * (G_a[N] - G_a[0])
Нормировки: (1) сумма модулей членов |dM| + |int G[0]| + |int G[N]| (как у
баланса энергии); (2) накопленная добыча -int G[0] (как в пробе FEAT-019);
(3) начальный запас M(0).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-039\\probes\\mass_balance_baseline.py [пример ...]
"""

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

ALL = ["01_single_phase_no_jt", "02_single_phase_jt", "03_standing_corey",
       "04_table_table", "04a_high_gas_saturation", "05_standing_table_rp",
       "06_table_corey_rp", "07_degassing_adiabatic_only", "08_degassing_jt",
       "09_degassing_latent_heat", "10_deep_degassing", "11_degassing_at_boundary",
       "12_large_drainage_radius", "13a_pwf_ramp_down", "13b_pwf_alternating",
       "14_high_gor_cooling", "15_oil_rate_ramp_up", "16_well_shut_in",
       "19_rs150_cooling", "20_rs300_cooling", "21_rs100_cooling"]


class Recording:
    """Обёртка EnergySolver.solve: пишет каждый принятый подшаг, физику не трогает."""

    def __init__(self, inner, rows):
        self._inner = inner
        self._rows = rows

    def solve(self, hr, sp, dt, bc, collect=None):
        self._rows.append((hr.state.t, dt, float(hr.G_o[0]), float(hr.G_o[-1]),
                           float(hr.G_g[0]), float(hr.G_g[-1]), int(hr.n_substeps)))
        return self._inner.solve(hr, sp, dt, bc, collect)

    def __getattr__(self, k):
        return getattr(self._inner, k)


def inventories(model, st):
    """Запас нефти и газа в области, м3ст — функцией прототипа."""
    ps = BlackOilState(pressure_bar=st.p / BAR_TO_PA, rs_sm3_sm3=st.Rs.copy(),
                       sg=st.Sg.copy(), gas_active=(st.regime == 1))
    oi, gi = model.component_inventories(ps)
    return float(np.sum(oi)), float(np.sum(gi))


def probe(name):
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    cfg.output.log_level = "WARNING"
    sim, init = SimulatorFactory.from_config(cfg)
    rows = []
    sim._energy = Recording(sim._energy, rows)
    t0 = time.perf_counter()
    h = sim.run(init)
    elapsed = time.perf_counter() - t0
    model = sim._hydro._model

    R = np.array(rows)
    t_end, dt = R[:, 0], R[:, 1]
    Go0, GoN, Gg0, GgN, nsub = R[:, 2], R[:, 3], R[:, 4], R[:, 5], R[:, 6]
    M0 = inventories(model, h.states[0])

    worst = {"o_abs": 0.0, "g_abs": 0.0, "o_prod": 0.0, "g_prod": 0.0}
    final = None
    for k in range(1, len(h.states)):
        sel = t_end <= h.times[k] * (1 + 1e-12) + 1e-9
        M = inventories(model, h.states[k])
        out = {}
        for a, (G0, GN, Ma0, Ma) in (("o", (Go0, GoN, M0[0], M[0])),
                                     ("g", (Gg0, GgN, M0[1], M[1]))):
            iw = float(np.sum(dt[sel] * G0[sel]))     # int G[0] dt, < 0 при добыче
            ie = float(np.sum(dt[sel] * GN[sel]))     # int G[N] dt, < 0 при притоке
            dM = Ma - Ma0
            res = dM + ie - iw
            scale = abs(dM) + abs(iw) + abs(ie)
            out[a] = dict(res=res, dM=dM, iw=iw, ie=ie, M0=Ma0,
                          rel_abs=abs(res) / scale if scale > 0 else 0.0,
                          rel_prod=abs(res) / abs(iw) if iw != 0 else 0.0)
            worst[f"{a}_abs"] = max(worst[f"{a}_abs"], out[a]["rel_abs"])
            worst[f"{a}_prod"] = max(worst[f"{a}_prod"], out[a]["rel_prod"])
        final = out

    n_nested = int(np.count_nonzero(nsub > 1))
    print(f"\n=== {name}: {len(h.states)} записей, {len(rows)} принятых подшагов, "
          f"вложенное дробление: {n_nested}, расчёт {elapsed:.1f} с ===")
    for a, lab in (("o", "нефть"), ("g", "газ")):
        f = final[a]
        print(f"  {lab:5s}: dM = {f['dM']:+.6e}, int G[0] = {f['iw']:+.6e}, "
              f"int G[N] = {f['ie']:+.6e}, M0 = {f['M0']:.6e} м3ст")
        print(f"         невязка {f['res']:+.3e} м3ст; финал: /sum|членов| {f['rel_abs']:.2e}, "
              f"/добыча {f['rel_prod']:.2e}, /M0 {abs(f['res'])/f['M0'] if f['M0'] else 0:.2e}; "
              f"max по записям: /sum|членов| {worst[a + '_abs']:.2e}, /добыча {worst[a + '_prod']:.2e}")
    return name, final, worst, n_nested, elapsed


if __name__ == "__main__":
    names = sys.argv[1:] or ALL
    summary = [probe(n) for n in names]
    print("\n=== Сводка: max по записям, нормировка на сумму модулей членов ===")
    print(f"{'пример':28s} {'нефть':>10s} {'газ':>10s} {'/добыча н':>10s} {'/добыча г':>10s} {'влож.':>6s} {'с':>6s}")
    for name, final, worst, n_nested, el in summary:
        print(f"{name:28s} {worst['o_abs']:10.2e} {worst['g_abs']:10.2e} "
              f"{worst['o_prod']:10.2e} {worst['g_prod']:10.2e} {n_nested:6d} {el:6.1f}")
    allo = max(w["o_abs"] for _, _, w, _, _ in summary)
    allg = max(w["g_abs"] for _, _, w, _, _ in summary)
    print(f"\nмаксимум по всем: нефть {allo:.2e}, газ {allg:.2e}")
