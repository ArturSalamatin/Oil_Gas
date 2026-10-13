"""DEBT-055, проба планирования: числа тестов плана на эмуляции поля cell_floor.

План: отчёт отказа Ньютона прототипа несёт cell_floor — меру ячеек вектора |J| @ ulp(z),
J — последний якобиан решения, z — возвращённое приближение. Код прототипа не меняется:
обёртка finite_difference_jacobian запоминает последнюю пару (J, z), обёртка _newton_report
дописывает в отчёт отказа атрибут cell_floor по ней. Для выходов 'line_search',
'linear_solver' и ступени 4 z якобиана — возвращённое приближение (как в плане); для
'max_iter' ступеней 1-3 план берёт ulp возвращённого z, эмуляция — z якобиана (разница —
на шаг Ньютона, для чисел тестов не нужна: эти тесты на выход 'max_iter' не опираются).

Сценарии — тесты плана (шаг 3):
  B — BUG-018 при N = 350, _advance_phases на шаге dt = 86400 с и dt/2 (ступень 1 отказывает
      по линейному поиску, только по ячейке): мера, предел, их отношение, отношение пределов;
  C — фикстура shutin (rs300 после 10 сут добычи, q_oil = 0), _newton_switching на 168.75 с
      при недостижимом пороге 1e-30: мера и предел;
  D — сошедшееся решение: предела нет.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-055\\probes\\plan_check.py
"""
import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
HERE = Path(__file__).resolve().parent

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config      # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA            # noqa: E402
from radial_blackoil import blackoil as bo                    # noqa: E402
from radial_blackoil.state import BlackOilState               # noqa: E402

OUT = open(HERE / "plan_check.out.txt", "w", encoding="utf-8")


def out(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


out(f"SOLVER = {SOLVER}; radial_blackoil: {Path(bo.__file__).parent}")

# ── Эмуляция поля cell_floor ──
cls = bo.RadialBlackOilModel
_jac0, _rep0 = cls.finite_difference_jacobian, cls._newton_report


def jac(self, z, *a, **k):
    J, f = _jac0(self, z, *a, **k)
    self._probe_last = (J, np.asarray(z, float).copy())
    return J, f


def report(self, converged, iterations, nrm, tol, f, w, reason, **fields):
    rep = _rep0(self, converged, iterations, nrm, tol, f, w, reason, **fields)
    last = getattr(self, "_probe_last", None)
    rep.cell_floor = None
    if not converged and w is not None and last is not None:
        J, z = last
        rep.cell_floor = self._cell_measure(abs(J) @ np.spacing(np.abs(z)), w)
    return rep


cls.finite_difference_jacobian = jac
cls._newton_report = report

# ── B. BUG-018 при N = 350 ──
cfg = load_config(SOLVER / "tests" / "data" / "bug018_rs500" / "config.json")
cfg.output.log_level = "ERROR"
cfg.grid.N = 350
sim, init = SimulatorFactory.from_config(cfg)
_, dt = sim._schedule.substeps(0)
model = sim._hydro._model
model.set_bhp_control(sim._schedule.intervals[0].bc.well.p_wf / BAR_TO_PA)
ps = BlackOilState(pressure_bar=init.p / BAR_TO_PA, rs_sm3_sm3=init.Rs.copy(),
                   sg=init.Sg.copy(), gas_active=(init.regime == 1))
out(f"\nB. BUG-018, N = 350, cell_tol = {model.cell_tol}")
floors = []
for h in (dt, dt / 2):
    model._probe_last = None
    _, rep = model._advance_phases(ps, h)
    floors.append(rep.cell_floor)
    out(f"  dt = {h:g} с: сошлось {rep.converged}, выход {rep.exit_reason}, итераций {rep.iterations}, "
        f"невязка {rep.residual_inf:.3e} (допуск {rep.residual_tol:.3e}), мера {rep.cell_measure:.4e}, "
        f"предел {rep.cell_floor:.4e}, мера/предел {rep.cell_measure / rep.cell_floor:.3f}")
out(f"  предел(dt/2)/предел(dt) = {floors[1] / floors[0]:.5f}")

# ── C. Ступень 4 на недостижимом пороге ──
cfg = load_config(SOLVER / "tests" / "data" / "bug020_rs300" / "config.json")
sim, init = SimulatorFactory.from_config(cfg)
s = sim.run(init).states[-1]
model = sim._hydro._model
model.set_oil_rate_control(0.0, 101325.0 / 1e5)
ps = BlackOilState(pressure_bar=s.p / 1e5, rs_sm3_sm3=s.Rs.copy(), sg=s.Sg.copy(),
                   gas_active=(s.regime == 1))
out(f"\nC. shutin (rs300, 10 сут добычи), p(r_w) = {ps.pressure_bar[0]:.4f} бар")
for ct in (1e-30,):
    tol0 = model.cell_tol
    try:
        model.cell_tol = ct
        model._probe_last = None
        _, rep = model._newton_switching(ps, 168.75)
    finally:
        model.cell_tol = tol0
    out(f"  порог {ct:g}: сошлось {rep.converged}, выход {rep.exit_reason}, итераций {rep.iterations}, "
        f"мера {rep.cell_measure:.4e}, предел {rep.cell_floor:.4e}, "
        f"мера/предел {rep.cell_measure / rep.cell_floor:.3f}")

# ── D. Сошедшееся решение ступени 4 при пороге 1e-8 ──
model._probe_last = None
_, rep = model._newton_switching(ps, 168.75)
out(f"\nD. ступень 4 при пороге {model.cell_tol}: сошлось {rep.converged}, выход {rep.exit_reason}, "
    f"мера {rep.cell_measure:.3e}, предел {rep.cell_floor}")
