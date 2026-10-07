"""DEBT-043, аудит плана: код шагов 1–3 исполняется подменой в памяти, рабочие файлы не меняются.

1. Накопитель: round_bound по блокам «После:» шага 1 (поле, add_accumulation,
   snapshot), _BALANCE_KEYS с round_bound.
2. compute_balance: round_bound, round_ratio по блоку шага 2.
3. Тело test_round_bound_accumulates_eps_heat_stock — как описано в шаге 1.7.
4. Тело test_round_ratio_detects_bug007_defect — как описано в шаге 3.3 (03, 04).
5. Укороченные сценарии (шаг 3.2) и полные 03, 21 — round_ratio по записям,
   round_ratio[0] на t = 0, сверка с замером плана (03 — 0.0035, 21 — 0.20).
6. Структура истории (test_balance_independent_of_history_structure): round_bound
   разреженной и почасовой истории равны.

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-043\\probes\\audit_planned_code.py
"""

import copy
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = (HERE.parents[3] / "numerical_solver").resolve()
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver.state as state_mod  # noqa: E402
from gpn_multiphase_solver.energy import balance as bal_mod  # noqa: E402
from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator  # noqa: E402
from gpn_multiphase_solver.grid.log_radial import LogRadialGrid  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
import energy_balance  # noqa: E402

print(f"код: {Path(bal_mod.__file__).parent.parent}")

# ── Шаг 1: накопитель (подмена по блокам «После:») ──
_EPS = float(np.finfo(float).eps)
_init0 = EnergyBalanceAccumulator.__init__
_acc0 = EnergyBalanceAccumulator.add_accumulation
_snap0 = EnergyBalanceAccumulator.snapshot


def _init(self, grid):
    _init0(self, grid)
    self.round_bound = 0.0


def _acc(self, T_new, T_prev, rho_cp_eff, dt):
    _acc0(self, T_new, T_prev, rho_cp_eff, dt)
    V = self._grid.volumes
    self.round_bound += _EPS * float(np.sum(rho_cp_eff * V * T_new))


def _snap(self):
    d = _snap0(self)
    d["round_bound"] = self.round_bound
    return d


EnergyBalanceAccumulator.__init__ = _init
EnergyBalanceAccumulator.add_accumulation = _acc
EnergyBalanceAccumulator.snapshot = _snap
state_mod._BALANCE_KEYS = ("delta_E", "cum_adiab", "cum_conv",
                           "cum_jt", "cum_deg", "cum_cond", "round_bound")

# ── Шаг 2: compute_balance ──
_cb0 = energy_balance.compute_balance


def compute_balance(history, grid, config):
    out = _cb0(history, grid, config)
    out["round_bound"] = np.array([s["round_bound"] for s in history.balance])
    bound = np.where(out["round_bound"] > 0.0, out["round_bound"], 1.0)
    out["round_ratio"] = np.abs(out["residual"]) / bound
    return out


# ── 3. Тело модульного теста шага 1.7 ──
grid = LogRadialGrid(0.1, 100.0, 10.0, 5, 1e-14)
acc = EnergyBalanceAccumulator(grid)
T_new = np.linspace(340.0, 350.0, 5)
T_prev = T_new + 0.5
rho_cp_eff = np.full(5, 2.0e6)
expected = np.finfo(float).eps * np.sum(rho_cp_eff * grid.volumes * T_new)


def substep():
    acc.add_substep(None, None, 3600.0, {}, Phi_o=np.zeros(6), Phi_g=np.zeros(6),
                    Q_T_ext=0.0, J_jt=np.zeros(5), Q_ad=np.zeros(5), Q_deg=np.zeros(5),
                    T_ext=350.0)
    acc.add_accumulation(T_new, T_prev, rho_cp_eff, dt=3600.0)


substep()
r1 = acc.round_bound
substep()
print(f"\n[1.7] expected {expected:.6e}; после 1 подшага {r1:.6e} (rel {abs(r1/expected-1):.1e}), "
      f"snapshot == поле: {acc.snapshot()['round_bound'] == acc.round_bound}; "
      f"после 2: {acc.round_bound/expected:.15f}×; "
      f"_zero_balance: {state_mod._zero_balance().get('round_bound')}")
print(f"      по T_prev отличалось бы на rel "
      f"{abs(np.sum(rho_cp_eff*grid.volumes*T_prev)/np.sum(rho_cp_eff*grid.volumes*T_new)-1):.1e}")


# ── 4–6. Сценарии ──
def short_cfg(example, p_wf=None):
    cfg = load_config(SOLVER / "examples" / example / "config.json")
    cfg.grid.N = 25
    cfg.time.history = cfg.time.history[:1]
    cfg.time.history[0].dt = 21600.0
    cfg.output.log_level = "WARNING"
    if p_wf is not None:
        cfg.time.history[0].p_wf = p_wf
    return cfg


def run(cfg):
    sim, init = SimulatorFactory.from_config(cfg)
    h = sim.run(init)
    return compute_balance(h, sim._grid, cfg), h


def defective(self, T_new, T_prev, rho_cp_eff, dt):
    # Ровно текст шага 3.3: коэффициенты до вызова, вызов, пересчёт по T_prev
    Pp, Pm, dts, Text = self._Phi_plus, self._Phi_minus, self._dt_substep, self._T_ext
    conv0 = self.cum_conv
    _acc(self, T_new, T_prev, rho_cp_eff, dt)
    N = len(T_prev)
    TL = np.concatenate(([T_prev[0]], T_prev[:-1]))
    TR = np.concatenate((T_prev[1:], [Text]))
    F = Pp[0:N] * (T_prev - TL) + Pm[1:N + 1] * (TR - T_prev)
    self.cum_conv = conv0 - float(np.sum(F)) * dts


print("\n[3.2] укороченные сценарии (6 ч, N = 25):")
for ex, pwf in (("03_standing_corey", None), ("04_table_table", None), ("04_table_table", 16e6)):
    b, _ = run(short_cfg(ex, pwf))
    print(f"  {ex} p_wf={pwf}: rel {b['rel_residual'][-1]:.2e}, round_ratio {b['round_ratio'][-1]:.3e}, "
          f"ratio[0] {b['round_ratio'][0]}, bound[0] {b['round_bound'][0]}")

print("\n[3.3] дефект BUG-007 (тело теста):")
for ex in ("03_standing_corey", "04_table_table"):
    EnergyBalanceAccumulator.add_accumulation = defective
    try:
        b, _ = run(short_cfg(ex))
    finally:
        EnergyBalanceAccumulator.add_accumulation = _acc
    print(f"  {ex}: rel {b['rel_residual'][-1]:.2e} (> 1e-4: {b['rel_residual'][-1] > 1e-4}), "
          f"round_ratio {b['round_ratio'][-1]:.2e} (> 1e6: {b['round_ratio'][-1] > 1e6})")

print("\n[3.2] структура истории (03, 04): round_bound разреженной и почасовой")
for ex in ("03_standing_corey", "04_table_table"):
    vals = []
    for n_int in (1, 6):
        cfg = load_config(SOLVER / "examples" / ex / "config.json")
        cfg.grid.N = 25
        iv = copy.deepcopy(cfg.time.history[0])
        cfg.time.history = [copy.deepcopy(iv) for _ in range(n_int)]
        for hh in cfg.time.history:
            hh.dt = 21600.0 / n_int
        cfg.output.log_level = "WARNING"
        b, _ = run(cfg)
        vals.append(b["round_bound"][-1])
    print(f"  {ex}: {vals[0]!r} vs {vals[1]!r}, равны: {vals[0] == vals[1]}")

print("\n[4] полные конфиги:")
for ex in ("03_standing_corey", "21_rs100_cooling"):
    cfg = load_config(SOLVER / "examples" / ex / "config.json")
    cfg.output.log_level = "ERROR"
    b, h = run(cfg)
    print(f"  {ex}: rel {b['rel_residual'][-1]:.2e}, round_ratio финал {b['round_ratio'][-1]:.4f}, "
          f"max по записям {np.max(b['round_ratio'][1:]):.4f}, записей {len(h.times)}, "
          f"ключи снимка {sorted(h.balance[-1])}")
