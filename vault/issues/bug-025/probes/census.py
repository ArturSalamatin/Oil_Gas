"""BUG-025 (планирование): где предел округления в допуске max(1e-11, KAPPA*eps*M_max/dt) меняет допуск.

Предел округления меняет допуск решения Ньютона, только если KAPPA > kappa* = atol*dt/(eps*M_max):
при меньшем KAPPA max() возвращает atol тем же числом и решение побитово прежнее.
Скрипт считает все решения Ньютона (обе функции, все ступени advance) во всех примерах
и сценариях тестов с мелкими шагами и печатает наименьший kappa* по сценарию и число
решений с kappa* < 1, 4, 16, 64. Методы не меняются: обёртка только записывает
(вызов _old_inventories берёт тот же кэш, что невязка, — значения побитово те же).

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-025\\probes\\census.py [имя ...]
"""
import copy
import sys
import time
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory   # noqa: E402
from gpn_multiphase_solver.io.config import load_config       # noqa: E402
import radial_blackoil                                         # noqa: E402
from radial_blackoil import blackoil as bo                     # noqa: E402

print(f"Код: {SOLVER}")
print(f"Прототип: {radial_blackoil.__file__}")

EPS = float(np.finfo(float).eps)
ATOL = 1e-11
KAPPAS = (1, 4, 16, 64)
REC = []   # (dt, M_max, функция) каждого решения Ньютона


def m_max(model, state_old):
    oi0, gi0 = model._old_inventories(state_old)
    return max(float(np.max(np.abs(oi0))), float(np.max(np.abs(gi0))) / model.gas_residual_scale)


_fixed, _switching = bo.RadialBlackOilModel._newton_fixed_active_set, bo.RadialBlackOilModel._newton_switching


def fixed(self, z0, state_old, dt_s, gas_active, *a, **k):
    REC.append((float(dt_s), m_max(self, state_old), 1))
    return _fixed(self, z0, state_old, dt_s, gas_active, *a, **k)


def switching(self, state_old, dt_s, *a, **k):
    REC.append((float(dt_s), m_max(self, state_old), 4))
    return _switching(self, state_old, dt_s, *a, **k)


bo.RadialBlackOilModel._newton_fixed_active_set = fixed
bo.RadialBlackOilModel._newton_switching = switching


def _cfg(path):
    return lambda: load_config(path)


def _bug018():
    cfg = load_config(SOLVER / "tests" / "data" / "bug018_rs500" / "config.json")
    cfg.grid.N = 350
    return cfg


def _daily_shutin():
    # TestDailyShutin (tests/test_prototype_phase_switching.py): 10 сут добычи + 3 сут q_oil = 0
    cfg = load_config(SOLVER / "tests" / "data" / "bug020_rs300" / "config.json")
    hist = list(cfg.time.history)
    for _ in range(3):
        x = copy.deepcopy(hist[0])
        x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    return cfg


SCENARIOS = {p.parent.name: _cfg(p) for p in sorted((SOLVER / "examples").glob("*/config.json"))}
SCENARIOS.update({
    "test:bug018_n350": _bug018,
    "test:bug020_rs150": _cfg(SOLVER / "tests" / "data" / "bug020_rs150" / "config.json"),
    "test:daily_shutin_rs300": _daily_shutin,
})


def run(name):
    cfg = SCENARIOS[name]()
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    REC.clear()
    t0 = time.perf_counter()
    try:
        sim.run(init)
        status = "ok"
    except Exception as exc:   # отказ сценария — тоже факт, перепись по сделанным решениям
        status = f"ОТКАЗ {type(exc).__name__}"
    el = time.perf_counter() - t0
    if not REC:
        print(f"{name}: решений 0 ({status}, {el:.1f} с)", flush=True)
        return
    r = np.array(REC)
    ks = ATOL * r[:, 0] / (EPS * r[:, 1])
    i = int(np.argmin(ks))
    counts = ", ".join(f"<{k}: {int(np.sum(ks < k))}" for k in KAPPAS)
    print(f"{name}: решений {len(r)} ({status}, {el:.1f} с); min dt {r[:, 0].min():.4g} с; "
          f"M_max {r[:, 1].min():.3g}..{r[:, 1].max():.3g} м³ст; min kappa* = {ks[i]:.3g} "
          f"(dt {r[i, 0]:.4g} с, ступень {'4' if r[i, 2] == 4 else '1-3'}); решений с kappa* {counts}",
          flush=True)


if __name__ == "__main__":
    for name in (sys.argv[1:] or SCENARIOS):
        run(name)
