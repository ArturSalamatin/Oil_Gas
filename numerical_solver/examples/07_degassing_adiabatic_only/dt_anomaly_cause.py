"""BUG-010: проверка корневой причины — A-retry и рассогласование потоков.

Гипотеза: при срабатывании A-retry гидро-адаптер дробит dt на n_sub
подшагов, но наружу отдаёт HydroResult ПОСЛЕДНЕГО подшага (потоки Q_o,
Q_g, G_o за dt_sub = dt/n_sub). Энергия затем применяет эти потоки на
ПОЛНОМ шаге dt. На переходном участке потоки последнего подшага меньше
средних за dt -> недобор конвективного переноса -> недобор охлаждения.

Проверка: прогнать один и тот же dt с max_retries = 0 (A-retry запрещён,
шаг обязан пройти целиком или упасть) и с обычным max_retries.
Если гипотеза верна — при запрете retry аномалия должна исчезнуть либо
шаг должен упасть, но НЕ дать тихо смещённый результат.

Запуск (из numerical_solver/):
    .venv/Scripts/python examples/07_degassing_adiabatic_only/dt_anomaly_cause.py
"""

import copy
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_EXAMPLES = _HERE.parent
_ROOT = _EXAMPLES.parent

_PROTO_ROOT = _ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
for _p in (str(_PROTO_ROOT), str(_EXAMPLES)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


def run_one(config, dt_integration, max_retries=None):
    """Один интервал истории -> (T [N], сработал ли A-retry)."""
    cfg = copy.deepcopy(config)
    cfg.time.dt_integration = float(dt_integration)
    cfg.time.history = cfg.time.history[:1]
    if max_retries is not None:
        cfg.numerics.max_retries = int(max_retries)

    simulator, initial_state = SimulatorFactory.from_config(cfg)
    history = simulator.run(initial_state)
    return np.asarray(history.states[-1].T, float)


def main() -> None:
    config = load_config(_HERE / "config.json")

    T_ref = run_one(config, 50.0)
    print(f"Эталон dt = 50 с: T[0] = {T_ref[0]:.6f} К\n")

    # 450 и 400 — аномальные (A-retry срабатывает);
    # 600 и 360 — чистые (retry не нужен). Сравниваем поведение.
    print(f"{'dt, с':>7} {'max_retries':>12} {'max|dT|, К':>13}  результат")
    print("-" * 60)

    for dt in (600.0, 450.0, 400.0, 360.0):
        # Штатный прогон (A-retry разрешён)
        T = run_one(config, dt)
        err = float(np.max(np.abs(T - T_ref)))
        print(f"{dt:7.0f} {'по умолчанию':>12} {err:13.4e}  штатно")

        # A-retry запрещён: шаг обязан пройти целиком либо упасть
        try:
            T0 = run_one(config, dt, max_retries=0)
            err0 = float(np.max(np.abs(T0 - T_ref)))
            print(f"{dt:7.0f} {0:>12} {err0:13.4e}  retry запрещён")
        except RuntimeError as exc:
            msg = str(exc).splitlines()[0][:50]
            print(f"{dt:7.0f} {0:>12} {'—':>13}  ОТКАЗ: {msg}")
        print()


if __name__ == "__main__":
    main()
