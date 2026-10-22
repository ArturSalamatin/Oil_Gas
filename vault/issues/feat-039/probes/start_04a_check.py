"""FEAT-039 (планирование): числа и время теста точности на пуске – пример 04a, только первый интервал.

Как будущий тест tests/test_dt_convergence.py::TestRampOnProductionStart: история
урезана до первого интервала (300 с), поле = h0. Аргумент emul – эмуляция FEAT-039
(без неё поле на интервале 0 не действует, h0 = 0.11 совпадёт с None).

Запуск из numerical_solver/ (P – путь к скрипту): .venv\\Scripts\\python P [emul]
"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from start_series import SOLVER_ROOT  # noqa: E402

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

# Пределы равномерного сгущения T(r_w) первой записи – octave.out.txt: Ричардсон
# при q = 1 по j = 4, 5. У 04a давление на пуске ниже таблицы PVT (свойства по
# крайней точке), поэтому тест – на 20 (Стендинг); 04a – для сравнения.
T_LIM = {"04a_high_gas_saturation": 350.5052, "20_rs300_cooling": 367.4061}

args = sys.argv[1:]
if args[:1] == ["emul"]:
    import feat039_emul
    feat039_emul.pytest_configure(None)
    args = args[1:]
name = args[0] if args else "20_rs300_cooling"

for h0 in (None, 0.11, 1.76):
    cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    cfg.time.history = cfg.time.history[:1]
    cfg.time.dt_after_control_change = h0
    t0 = time.perf_counter()
    sim, s0 = SimulatorFactory.from_config(cfg)
    T = float(sim.run(s0).states[-1].T[0])
    print(f"{name} h0={h0}: T(r_w) {T:.6f} К, T_LIM - T {T_LIM[name] - T:+.6f} К, "
          f"время {time.perf_counter() - t0:.2f} с", flush=True)
