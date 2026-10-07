"""BUG-021, аудит раунд 1: утверждения плана, которые при планировании были выводом, а не замером.

1. Пример 14, первые шаги: какой ступенью advance принят шаг 2 (план и CHANGELOG: «третьей ступенью»).
2. Пример 05, первый шаг при p_wf = 8, 7, 6, 5, 4, 3, 2 МПа: число подшагов A-retry (README 05 после правки
   шага 6.4 говорит «только при 5 МПа»).
Каждое — на текущем коде и на варианте 2 (planned_code.apply(2)).

Запуск — из каталога numerical_solver: .venv\\Scripts\\python <P>\\audit_checks.py
"""
import copy
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(HERE))
logging.disable(logging.INFO)

import radial_blackoil.blackoil as bo  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

EX = SOLVER_ROOT / "examples"


def stages_14():
    """Первые 3 вызова advance примера 14: сошлось, ступень (fallback/globalized), ветка, итерации."""
    cfg = load_config(EX / "14_high_gor_cooling" / "config.json")
    cfg.output.log_level = "ERROR"
    iv = copy.deepcopy(cfg.time.history[0]); iv.dt = 3 * 86400.0
    cfg.time.history = [iv]
    sim, init = SimulatorFactory.from_config(cfg)
    out = []
    orig = bo.RadialBlackOilModel.advance

    def advance(self, state_old, dt_s, *a, **k):
        new, rep = orig(self, state_old, dt_s, *a, **k)
        stage = "третья" if rep.globalized else ("запасной" if rep.fallback else "исходный")
        out.append(f"dt={dt_s:g} conv={rep.converged} ступень={stage} ветка={rep.well_branch!r} it={rep.iterations}")
        return new, rep

    bo.RadialBlackOilModel.advance = advance
    try:
        sim.run(init)
    finally:
        bo.RadialBlackOilModel.advance = orig
    return out[:3]


def first_step_05(pwf_MPa):
    cfg = load_config(EX / "05_standing_table_rp" / "config.json")
    cfg.output.log_level = "ERROR"
    for iv in cfg.time.history:
        iv.p_wf = pwf_MPa * 1e6
    sim, init = SimulatorFactory.from_config(cfg)
    _, dt = sim._schedule.substeps(0)
    try:
        return sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc).n_substeps
    except RuntimeError as e:
        return f"отказ: {e}"


PWF = (8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0)
cfg05 = load_config(EX / "05_standing_table_rp" / "config.json")
print(f"05: штатное p_wf = {cfg05.time.history[0].p_wf / 1e6:g} МПа, первый шаг {cfg05.time.dt_integration} с")
res = {}
for label in ("текущий код", "вариант 2"):
    if label == "вариант 2":
        import planned_code
        planned_code.apply(2)
    print(f"== {label}")
    for line in stages_14():
        print("  14:", line)
    res[label] = [first_step_05(p) for p in PWF]
for p, a, b in zip(PWF, res["текущий код"], res["вариант 2"]):
    print(f"05, p_wf = {p:g} МПа: подшагов {a} -> {b}")
