"""DEBT-027, проба при /plan-improve: README 04, таблица «Сходимость Newton» — при каких p_wf давление у забоя ниже газовой таблицы.

Пример 04 (N = 50), p_wf из таблицы README (14 … 0.5 МПа), 1 сут по 1 ч, с эмуляцией кода плана
(emulate_debt027.install): печать min p(r_w) за расчёт и записей журнала «вне таблиц».
Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\debt-027\\probes\\readme04_pwf.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import emulate_debt027  # noqa: E402

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402

emulate_debt027.install()
records = []


class Collect(logging.Handler):
    def emit(self, record):
        records.append(record)


logger = logging.getLogger("gpn_multiphase_solver")
logger.addHandler(Collect(level=logging.WARNING))
CONFIG = Path.cwd() / "examples" / "04_table_table" / "config.json"
for p_wf in (14e6, 12e6, 10e6, 8e6, 6e6, 4e6, 3e6, 2e6, 1e6, 0.5e6):
    records.clear()
    cfg = load_config(CONFIG)
    cfg.time.history = cfg.time.history[:24]
    for h in cfg.time.history:
        h.p_wf = p_wf
    sim, s0 = SimulatorFactory.from_config(cfg)
    logger.setLevel(logging.WARNING)
    hist = sim.run(s0)
    pmin = min(float(s.p[0]) for s in hist.states)
    cats = [r.getMessage().split("вне таблиц: ", 1)[1].split(":", 1)[0] for r in records]
    print(f"p_wf = {p_wf / 1e6:4g} МПа: min p(r_w) = {pmin / 1e6:.3f} МПа; «вне таблиц»: {cats or 'нет'}", flush=True)
