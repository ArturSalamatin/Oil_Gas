"""BUG-020: трассировка отказа первого шага останова по ступеням advance.

Добыча n_prod суток по конфигу примера, затем из конечного состояния — один
model.advance прототипа (без A-retry адаптера) в режиме A (p_wf = p_ext) и
B (q_oil = 0). Ньютон при фиксированном наборе фаз заменён копией
_newton_fixed_active_set (blackoil.py:270-293) с журналом итераций: невязка,
принятый шаг линейного поиска и причина отказа пробных точек, min S_g и число
ячеек с S_g < 0 среди двухфазных, число двухфазных ячеек с отрицательным
определителем блока накопления (det < 0 <=> c_t < 0, кандидат К2 issue #63).

det блока накопления ячейки: a = PV So/Bo, b = PV (Rs So/Bo + Sg/Bg) по (p, Sg),
det = a_p b_S - a_S b_p = PV^2/(Bo Bg) * c_t, c_t = (1-Sg) c_ot + Sg c_g (+ c_r).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-020\\probes\\trace_stages.py 20 10 > ..\\vault\\issues\\bug-020\\probes\\trace_stages_20.out.txt
"""

import copy
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples", SOLVER / "tests",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.blackoil import BlackOilNewtonReport  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

DAY = 86400.0
BASES = {"12": "12_large_drainage_radius", "20": "20_rs300_cooling",
         "19": "19_rs150_cooling", "21": "21_rs100_cooling",
         "14": "14_high_gor_cooling"}
base_key, n_prod = sys.argv[1], int(sys.argv[2])
DTS = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [60.0, 169.0, 600.0, 3600.0]
BASE = SOLVER / "examples" / BASES[base_key] / "config.json"

cfg = load_config(BASE)
cfg.output.log_level = "ERROR"
iv = cfg.time.history[0]
hist = []
for _ in range(n_prod):
    x = copy.deepcopy(iv)
    x.dt = DAY
    hist.append(x)
cfg.time.history = hist
sim, init = SimulatorFactory.from_config(cfg)
h = sim.run(init)
st = h.states[-1]
model = sim._hydro._model
p_ext = cfg.initial_conditions.p0
n = model.grid.n


def proto(s):
    return BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                         sg=s.Sg.copy(), gas_active=(s.regime == 1))


def accum_det(z, mask):
    """det блока накопления по (p, Sg) для двухфазных ячеек; c_t = det Bo Bg / PV^2, 1/бар."""
    s = model.unpack(z, mask)
    p, sg = s.pressure_bar, s.sg
    hp = np.maximum(1e-4, 1e-6 * np.abs(p))
    hs = 1e-7

    def inv(pp, ss):
        st2 = BlackOilState(pp, model.pvt.rs_sat(pp), ss, mask.copy())
        return model.component_inventories(st2)

    a0, b0 = inv(p, sg)
    ap, bp = inv(p + hp, sg)
    as_, bs = inv(p, sg + hs)
    a_p, b_p = (ap - a0) / hp, (bp - b0) / hp
    a_s, b_s = (as_ - a0) / hs, (bs - b0) / hs
    det = a_p * b_s - a_s * b_p
    rs = model.pvt.rs_sat(p)
    bo = model.pvt.bo(p, rs)
    bg = model.pvt.bg(p)
    pv = model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, p)
    ct = det * bo * bg / pv**2
    return np.where(mask, ct, np.nan)


log = []


def traced(z0, state_old, dt_s, gas_active, max_iter=15, rtol=1e-8, atol_sm3s=1e-11):
    """Копия _newton_fixed_active_set (blackoil.py:270-293) с журналом итераций."""
    self = model
    stage = (f"lo={self._sg_lower_bound} branch={self._well_branch} "
             f"l2={self._line_search_l2} dsg_max={self._sg_step_max}")
    rec = {"stage": stage, "n2": int(np.count_nonzero(gas_active)), "its": []}
    log.append(rec)
    z = np.asarray(z0, float).copy()
    f_initial = self.residual(z, state_old, dt_s, gas_active)
    scale = max(np.linalg.norm(f_initial, np.inf), 1e-9)
    merit = (lambda v: np.linalg.norm(v)) if self._line_search_l2 else (lambda v: np.linalg.norm(v, np.inf))
    for it in range(1, max_iter + 1):
        J, f = self.finite_difference_jacobian(z, state_old, dt_s, gas_active)
        nrm = np.linalg.norm(f, np.inf)
        x = z[n:]
        sgx = x[gas_active]
        ct = accum_det(z, gas_active)
        info = {"it": it, "nrm": nrm, "minsg": float(sgx.min()) if sgx.size else np.nan,
                "nneg": int(np.count_nonzero(sgx < 0)),
                "nct": int(np.count_nonzero(ct[gas_active] < 0)),
                "p0": float(z[0]), "pmax": float(z[:n].max())}
        if nrm <= atol_sm3s + rtol * scale:
            info["end"] = "сошёлся"
            rec["its"].append(info)
            rec["ok"] = True
            return z, BlackOilNewtonReport(True, it - 1, float(nrm))
        try:
            dz = self._linear_solve(J, -f)
        except Exception as e:
            info["end"] = f"линейный решатель: {e}"
            rec["its"].append(info)
            rec["ok"] = False
            return z, BlackOilNewtonReport(False, it, float(nrm))
        info["dp_max"] = float(np.abs(dz[:n]).max())
        dsg_all = np.abs(dz[n:][gas_active])
        info["dsg_max"] = float(dsg_all.max()) if dsg_all.size else 0.0
        if self._sg_step_max is not None:
            dsg = np.abs(dz[self.grid.n:][gas_active])
            if dsg.size and dsg.max() > self._sg_step_max:
                dz = dz * (self._sg_step_max / dsg.max())
        mf = merit(f)
        alpha = 1.0
        accepted = False
        n_unreas = n_nodec = 0
        for _ in range(12):
            trial = z + alpha * dz
            if self._trial_is_reasonable(trial, gas_active):
                ft = self.residual(trial, state_old, dt_s, gas_active)
                if merit(ft) < mf:
                    z = trial
                    accepted = True
                    break
                n_nodec += 1
            else:
                n_unreas += 1
            alpha *= 0.5
        info["alpha"] = alpha if accepted else 0.0
        info["unreas"] = n_unreas
        info["nodec"] = n_nodec
        rec["its"].append(info)
        if not accepted:
            info["end"] = "линейный поиск: нет шага"
            rec["ok"] = False
            return z, BlackOilNewtonReport(False, it, float(nrm))
    f = self.residual(z, state_old, dt_s, gas_active)
    rec["its"].append({"it": max_iter + 1, "nrm": float(np.linalg.norm(f, np.inf)), "end": "лимит итераций",
                       "minsg": float(z[n:][gas_active].min()) if gas_active.any() else np.nan,
                       "nneg": int(np.count_nonzero(z[n:][gas_active] < 0)),
                       "nct": int(np.count_nonzero(accum_det(z, gas_active)[gas_active] < 0)),
                       "p0": float(z[0]), "pmax": float(z[:n].max())})
    rec["ok"] = False
    return z, BlackOilNewtonReport(False, max_iter, float(np.linalg.norm(f, np.inf)))


model._newton_fixed_active_set = traced


def show(label):
    for k, rec in enumerate(log):
        print(f"  решение {k+1}: {rec['stage']}; 2ф = {rec['n2']}; итог: {'✓' if rec.get('ok') else '✗'}")
        for i in rec["its"]:
            s = (f"    it {i['it']:2d}: |F| = {i['nrm']:.2e}  p0 = {i['p0']:6.1f}  pmax = {i['pmax']:6.1f} бар  "
                 f"minSg = {i['minsg']:+.3f}  Sg<0: {i['nneg']:3d}  c_t<0: {i['nct']:3d}")
            if "alpha" in i:
                s += (f"  |dp| = {i['dp_max']:7.2f}  |dSg| = {i['dsg_max']:.3f}  "
                      f"alpha = {i['alpha']:.2e} (отказов: вне области {i['unreas']}, без убывания {i['nodec']})")
            if "end" in i:
                s += f"  → {i['end']}"
            print(s)


print(f"=== {BASES[base_key]}: {n_prod} сут добычи; p[0] = {st.p[0]/1e6:.3f} МПа, "
      f"max S_g = {st.Sg.max():.4f}, 2ф = {int(np.count_nonzero(st.regime == 1))} из {n}; p_ext = {p_ext/1e6:.2f} МПа ===")
ct0 = accum_det(model.pack(proto(st)), proto(st).gas_active)
print(f"исходное состояние: c_t < 0 в {int(np.nansum(ct0 < 0))} двухфазных ячейках; "
      f"min c_t = {np.nanmin(ct0):.3e} 1/бар")

MODES = {
    "A (p_wf = p_ext)": lambda: model.set_bhp_control(p_ext / BAR_TO_PA),
    "B (q_oil = 0)": lambda: model.set_oil_rate_control(0.0, 101325.0 / BAR_TO_PA),
}
for mode, setc in MODES.items():
    for dt in DTS:
        log.clear()
        setc()
        t1 = time.perf_counter()
        new, rep = model.advance(proto(st), dt)
        el = time.perf_counter() - t1
        tag = "✓" if rep.converged else "✗"
        print(f"\n── режим {mode}, dt = {dt:.0f} с: {tag} ({el:.1f} с); отчёт: it = {rep.iterations}, "
              f"res = {rep.residual_inf:.1e}, fallback = {rep.fallback}, globalized = {rep.globalized}, "
              f"branch = '{rep.well_branch}' ──")
        show(mode)
        if rep.converged:
            ct = accum_det(model.pack(new), new.gas_active)
            print(f"  принятое состояние: p0 = {new.pressure_bar[0]:.2f} бар, 2ф = {int(np.count_nonzero(new.gas_active))}, "
                  f"c_t < 0: {int(np.nansum(ct < 0))}")
