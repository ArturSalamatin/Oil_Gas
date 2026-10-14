"""DEBT-027, проба при /issue: пример 04 при p_wf = 2 МПа (газовая таблица от 5 МПа) и штатных 8 МПа.

Расчёт 1 сут; печатает предупреждения журнала решателя и pvt_range_warnings
прототипа на каждой записи истории. Ожидание по реестру: журнал без
предупреждений, диагностика прототипа при 2 МПа — 'GAS_PVT pressure below table'.
Штатный случай 8 МПа — проверка, не шумит ли диагностика без выхода за таблицы.
Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\debt-027\\probes\\repro_pwf2.py
"""
import logging
from pathlib import Path

import numpy as np

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.units import BAR_TO_PA
import gpn_multiphase_solver

from radial_blackoil.state import BlackOilState
from radial_blackoil.diagnostics import pvt_range_warnings, unique_warnings

SOLVER = Path.cwd()
print("пакет:", Path(gpn_multiphase_solver.__file__).parent)
CONFIG = SOLVER / "examples" / "04_table_table" / "config.json"

# Журнал: только WARNING и выше пакета решателя
records = []


class Collect(logging.Handler):
    def emit(self, record):
        records.append(record)


logging.getLogger("gpn_multiphase_solver").addHandler(Collect(level=logging.WARNING))

for p_wf in (2e6, 8e6):
    records.clear()
    config = load_config(CONFIG)
    # load_config разворачивает {duration, dt_out} в интервалы по dt_out (DEBT-014):
    # первые 24 интервала по 1 ч = 1 сут, на каждом — своё p_wf
    config.time.history = config.time.history[:24]
    for h in config.time.history:
        h.p_wf = p_wf
    sim, state0 = SimulatorFactory.from_config(config)
    history = sim.run(state0)

    print(f"\n=== p_wf = {p_wf / 1e6:g} МПа, интервалов {len(config.time.history)}, "
          f"t_end = {history.times[-1] / 86400:g} сут ===")
    print("предупреждений журнала решателя:", len(records))
    for r in records:
        print("  ", r.getMessage())

    model = sim._hydro._model
    all_w = []
    first_t = {}
    for t, s in zip(history.times, history.states):
        proto = BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                              sg=s.Sg.copy(), gas_active=(s.regime == 1))
        w = pvt_range_warnings(model, proto)
        for x in w:
            first_t.setdefault(x.split(":", 1)[0], t)
        all_w.extend(w)
    print("pvt_range_warnings на записях истории (уникальные):")
    for w in unique_warnings(all_w):
        print(f"   [впервые t = {first_t[w.split(':', 1)[0]] / 3600:g} ч] {w}")

    s = history.states[-1]
    ga = s.regime == 1
    print(f"конец: p(r_w) = {s.p[0] / 1e6:.3f} МПа, S_g(r_w) = {s.Sg[0]:.4f}, "
          f"R_s(r_w) = {s.Rs[0]:.4f}, ячеек ниже 5 МПа: {int(np.sum(s.p < 5e6))}, "
          f"газовых ячеек выше 15 МПа: {int(np.sum(s.p[ga] > 15e6))}")
    if np.any(ga & (s.p > 15e6)):
        j = np.flatnonzero(ga & (s.p > 15e6))
        print(f"   они: j = {j.tolist()}, p = {(s.p[j] / 1e6).round(4).tolist()} МПа, "
              f"S_g = {s.Sg[j].round(6).tolist()}, R_s = {s.Rs[j].round(4).tolist()}")
