"""BUG-010: скан температуры по dt_integration на табличном PVT.

Воспроизводит аномалию: ошибка T против опорного решения не убывает
монотонно с dt, а при отдельных значениях шага подскакивает на ~0.48 К.

Эталон — прогон при dt_integration = 50 с (n_sub = 72 на интервале 3600 с).
Считается ТОЛЬКО первый интервал истории: по записи реестра ошибка
вносится именно на нём (резкое приложение депрессии 20 -> 8 МПа),
а дальше монотонно релаксирует.

Запуск (из numerical_solver/):
    .venv/Scripts/python examples/07_degassing_adiabatic_only/dt_anomaly_scan.py
"""

import copy
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_EXAMPLES = _HERE.parent
_ROOT = _EXAMPLES.parent

# radial_blackoil (прототип) не установлен в venv — подключаем как в conftest.py
_PROTO_ROOT = _ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
for _p in (str(_PROTO_ROOT), str(_EXAMPLES)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


def run_one(config, dt_integration: float) -> np.ndarray:
    """Прогон ОДНОГО интервала истории при заданном dt_integration -> T [N]."""
    cfg = copy.deepcopy(config)
    cfg.time.dt_integration = float(dt_integration)
    # Только первый интервал: ошибка вносится на нём.
    cfg.time.history = cfg.time.history[:1]

    simulator, initial_state = SimulatorFactory.from_config(cfg)
    history = simulator.run(initial_state)
    return np.asarray(history.states[-1].T, float)


def main() -> None:
    config = load_config(_HERE / "config.json")
    dt_hist = config.time.history[0].dt

    # Опорное решение — самый мелкий шаг.
    dt_ref = 50.0
    T_ref = run_one(config, dt_ref)
    print(f"Эталон: dt = {dt_ref:g} с, n_sub = {int(np.ceil(dt_hist / dt_ref))}, "
          f"T[0] = {T_ref[0]:.6f} К")
    print()

    # Шаги из записи реестра: аномальные n_sub = 3, 5, 8, 9; чистые 2, 4, 6, 10, 12, 24.
    dt_list = [1800.0, 1200.0, 900.0, 720.0, 600.0, 450.0, 400.0, 360.0, 300.0, 150.0]

    print(f"{'dt, с':>8} {'n_sub':>6} {'max|dT|, К':>13} {'к тренду O(dt)':>16}")
    print("-" * 48)

    rows = []
    for dt in dt_list:
        T = run_one(config, dt)
        n_sub = int(np.ceil(dt_hist / dt))
        err = float(np.max(np.abs(T - T_ref)))
        rows.append((dt, n_sub, err))

    # Тренд O(dt) нормируем по самому крупному шагу — как в записи реестра.
    dt0, _, err0 = rows[0]
    for dt, n_sub, err in rows:
        expected = err0 * dt / dt0          # линейный тренд
        ratio = err / expected if expected > 0 else float("nan")
        flag = "  <-- АНОМАЛИЯ" if ratio > 2.0 else ""
        print(f"{dt:8.0f} {n_sub:6d} {err:13.4e} {ratio:16.2f}{flag}")


if __name__ == "__main__":
    main()
