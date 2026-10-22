"""Проба DEBT-008: мёртвые поля конфига — до и после правки.

Запуск из numerical_solver/ (основной каталог или worktree):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-008\\probes\\red_state.py
Пакет берётся из текущего каталога (SOLVER = Path.cwd()), путь печатается.
Каждый пункт — на свежем конфиге; отказы перехватываются и печатаются, поэтому
одна и та же проба даёт исходное состояние (red_state.out.txt) и итоговое
(green_state.out.txt).
"""
import logging
import sys
from pathlib import Path

SOLVER = Path.cwd()
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.io.config import load_config, _validate  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.log import setup_logging  # noqa: E402

print("пакет:", Path(gpn_multiphase_solver.__file__).parent)
BASELINE = SOLVER / "configs" / "baseline.json"
TABLE = SOLVER / "configs" / "table_pvt" / "config.json"
# Конфиг пробы BUG-019 — со старыми ключами start_day, dt_min, dt_max
OLD = SOLVER.parent / "vault" / "issues" / "bug-019" / "probes" / "frozen" / "config.json"
if not OLD.is_file():   # worktree: vault — в основном каталоге
    OLD = Path(r"D:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\bug-019\probes\frozen\config.json")


def refusal(fn):
    """None, если fn прошла; иначе текст отказа ValueError."""
    try:
        fn()
        return None
    except ValueError as e:
        return str(e)


# ── 1. Абсурдные значения 12 полей ──
# Присваивание атрибута объекту dataclass проходит и для удалённого поля
# (у dataclass нет __slots__): _validate увидит только оставшиеся поля.
cfg = load_config(BASELINE)
cfg.grid.type = "ЭТО_ЧУШЬ_А_НЕ_СЕТКА"
cfg.output.format = "xlsx"
cfg.time.start_day = -1e6
cfg.rock.p_ref = -5.0
cfg.numerics.dt_min = cfg.numerics.dt_max = -1.0
cfg.numerics.newton_max_iter = -3
cfg.numerics.max_active_set_iter = 0
cfg.numerics.newton_rtol = cfg.numerics.newton_atol = -1.0
cfg.numerics.rs_switch_tol = cfg.numerics.sg_switch_tol = -1.0
r = refusal(lambda: _validate(cfg))
if r is None:
    sim, _ = SimulatorFactory.from_config(cfg)
    m = sim._hydro._model
    print("1. 12 абсурдных значений: _validate и фабрика — OK; сетка", type(sim._grid).__name__)
    print(f"   прототип: rs_switch_tol = {m.rs_switch_tol:g}, sg_switch_tol = {m.sg_switch_tol:g}, "
          f"p_ref_bar = {m.rock.p_ref_bar:g} (p0 = {cfg.initial_conditions.p0 / 1e5:g} бар)")
else:
    print("1. 12 абсурдных значений: отказ —", r)

# ── 2. NaN в dt_min: DEBT-051 отвергал и мёртвое поле ──
cfg = load_config(BASELINE)
cfg.numerics.dt_min = float("nan")
r = refusal(lambda: _validate(cfg))
print("2. dt_min = NaN:", "проходит" if r is None else "отказ — " + r)

# ── 3. Опечатка в log_level ──
setup_logging("DEBG")
lvl = logging.getLevelName(logging.getLogger("gpn_multiphase_solver").level)
cfg = load_config(BASELINE)
cfg.output.log_level = "DEBG"
r = refusal(lambda: _validate(cfg))
print(f"3. log_level = 'DEBG': setup_logging ставит {lvl}; _validate —",
      "проходит" if r is None else "отказ — " + r)
setup_logging("INFO")

# ── 4. Допуск пересыщения старта ──
# p0 на 1 Па ниже p_b(30) = 15 МПа: избыток R_s ~3e-6 (test_p0_1pa_below_pb_passes)
cfg = load_config(TABLE)
cfg.initial_conditions.p0 = 15e6 - 1.0
cfg.numerics.rs_switch_tol = 1e-6
r = refusal(lambda: SimulatorFactory.from_config(cfg))
print("4. rs_switch_tol = 1e-6, избыток ~3e-6:",
      "старт принят" if r is None else "отказ — " + r[:60] + "…")

# ── 5. Передача полей Ньютона ──
cfg = load_config(TABLE)
cfg.numerics.newton_max_iter, cfg.numerics.max_active_set_iter = 7, 5
cfg.numerics.rs_switch_tol, cfg.numerics.sg_switch_tol = 2e-5, 3e-9
sim, _ = SimulatorFactory.from_config(cfg)
h = sim._hydro
print(f"5. конфиг 7/5/2e-5/3e-9: адаптер max_newton = {getattr(h, '_max_newton', 'нет поля')}, "
      f"max_active_iter = {getattr(h, '_max_active_iter', 'нет поля')}; модель "
      f"rs_switch_tol = {h._model.rs_switch_tol:g}, sg_switch_tol = {h._model.sg_switch_tol:g}")

# ── 6. Старый конфиг с удалёнными ключами ──
records = []
handler = logging.Handler()
handler.emit = records.append
log = logging.getLogger("gpn_multiphase_solver")
log.addHandler(handler)
cfg = load_config(OLD)
log.removeHandler(handler)
warns = [x.getMessage() for x in records if x.levelno >= logging.WARNING]
print(f"6. {OLD.parent.name}/config.json: загружен, предупреждений {len(warns)}")
for w in warns:
    print("   ", w[:110] + ("…" if len(w) > 110 else ""))
