"""BUG-010: измерение рассогласования потоков при A-retry.

⚠️ ВНИМАНИЕ: этот скрипт измеряет величину, которая ПРИЧИНОЙ НЕ ЯВЛЯЕТСЯ.

Первая редакция плана BUG-010 считала причиной то, что адаптер отдаёт
потоки последнего подшага вместо средних за шаг, и предлагала осреднение.
Аудит это опроверг: мгновенный поток при n+1 ближе к эталону (расхождение
1.59e-04), чем среднее по подшагам (5.43e-04), — неявная схема требует
именно потоков на слое n+1 (см. P4-адаптивный-шаг).

Настоящая причина: энергия решается ОДНИМ шагом по полному dt там, где
гидро раздробило шаг. См. dt_anomaly_energy_substeps.py.

Скрипт оставлен как воспроизводимое опровержение отвергнутого варианта.

Механизм, который здесь измеряется: при A-retry адаптер дробит dt на n_sub
подшагов и возвращает HydroResult ПОСЛЕДНЕГО подшага. Потоки в нём —
мгновенные, в финальном состоянии. Энергия применяет их на ПОЛНОМ dt.

Здесь измеряем, насколько поток последнего подшага отличается от среднего
за шаг. Средний поток за dt восстанавливаем по балансу массы:
    G_средний = (накопленная масса за dt) / dt,
а проще и надёжнее — сравнить G последнего подшага при дроблении
с G, полученным на том же dt без дробления (мелкий эталонный прогон).

Запуск (из numerical_solver/):
    .venv/Scripts/python examples/07_degassing_adiabatic_only/dt_anomaly_fluxes.py
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
from gpn_multiphase_solver.state import SimulationState  # noqa: E402


def build(config, dt_integration, max_retries=None):
    cfg = copy.deepcopy(config)
    cfg.time.dt_integration = float(dt_integration)
    cfg.time.history = cfg.time.history[:1]
    if max_retries is not None:
        cfg.numerics.max_retries = int(max_retries)
    return SimulatorFactory.from_config(cfg)


def main() -> None:
    config = load_config(_HERE / "config.json")

    # Берём аномальный шаг 450 с: A-retry дробит его на 2 подшага по 225 с.
    dt = 450.0
    simulator, state0 = build(config, dt)
    bc = simulator._schedule.intervals[0].bc
    hydro = simulator._hydro

    # (а) Один шаг dt = 450 с через адаптер — внутри произойдёт дробление на 2.
    res_retry = hydro.solve(state0, dt, bc)

    # (б) Тот же путь вручную: два подшага по 225 с. Собираем поток
    # ПЕРВОГО подшага и ПОСЛЕДНЕГО, чтобы увидеть, насколько они разные.
    half = dt / 2.0
    res_first = hydro.solve(state0, half, bc)
    state_mid = SimulationState(
        p=res_first.state.p, Sg=res_first.state.Sg, Rs=res_first.state.Rs,
        T=state0.T.copy(), regime=res_first.state.regime, t=res_first.state.t)
    res_last = hydro.solve(state_mid, half, bc)

    # Забойный поток нефти — самая наглядная величина (дебит).
    g_first = res_first.G_o[0]
    g_last = res_last.G_o[0]
    g_retry = res_retry.G_o[0]
    g_mean = 0.5 * (g_first + g_last)   # среднее за полный шаг

    # Без надстрочных символов: консоль Windows в cp1251 их не печатает (BUG-009).
    print("Забойный поток нефти G_o[0], ст.куб.м/с (отрицателен = приток к скважине)")
    print(f"  подшаг 1 (0 -> 225 с):      {g_first:.6e}")
    print(f"  подшаг 2 (225 -> 450 с):    {g_last:.6e}")
    print(f"  среднее за шаг 450 с:       {g_mean:.6e}")
    print(f"  что отдал адаптер наружу:   {g_retry:.6e}")
    print()
    print(f"  адаптер отдал поток последнего подшага: "
          f"{'ДА' if np.isclose(g_retry, g_last) else 'нет'}")
    rel = abs(g_last - g_mean) / abs(g_mean)
    print(f"  занижение относительно среднего: {rel:>6.1%}")
    print()

    # Тот же замер по всему полю внутренних граней.
    rel_field = np.max(np.abs(res_last.G_o[1:-1] - 0.5 * (res_first.G_o[1:-1]
                       + res_last.G_o[1:-1]))) / np.max(np.abs(res_last.G_o[1:-1]))
    print(f"  макс. относительное расхождение по внутренним граням: {rel_field:.1%}")


if __name__ == "__main__":
    main()
