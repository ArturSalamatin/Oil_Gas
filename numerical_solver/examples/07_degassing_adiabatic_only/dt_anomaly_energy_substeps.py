"""BUG-010: доказательство причины — энергия не дробится вместе с гидро.

Установлено аудитом плана: причина аномалии НЕ в величине потоков, а в том,
что при срабатывании A-retry гидродинамика дробит шаг на подшаги, а энергия
по-прежнему решается ОДНИМ шагом по полному dt. Расщепление «гидро -> энергия»
имеет порядок O(dt) и применяется на интервале, который сама гидродинамика
признала слишком крупным.

Решающее измерение: пройти первый шаг dt = 450 с двумя способами
  (а) энергия 1 x 450 с  -- как сейчас (гидро внутри дробит на 2);
  (б) энергия 2 x 225 с  -- дробление вместе с гидро.
Гидро-состояние в обоих случаях ИДЕНТИЧНО (p совпадает побитово), поэтому
разница в T вызвана только числом шагов энергии.

Ожидаемый результат: (б) точнее (а) примерно в 12 раз.

Запуск (из numerical_solver/):
    .venv/Scripts/python examples/07_degassing_adiabatic_only/dt_anomaly_energy_substeps.py
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
from gpn_multiphase_solver.state import SimulationState  # noqa: E402


def build(dt_integration: float):
    cfg = copy.deepcopy(load_config(_HERE / "config.json"))
    cfg.time.dt_integration = float(dt_integration)
    cfg.time.history = cfg.time.history[:1]
    return SimulatorFactory.from_config(cfg)


def advance(sim, state, dt: float, n_energy: int) -> SimulationState:
    """Продвинуть на dt, разбив на n_energy шагов ГИДРО+ЭНЕРГИЯ вместе.

    n_energy = 1 воспроизводит текущее поведение решателя: гидро может
    раздробить шаг внутри себя, но энергия решается один раз на полном dt.
    """
    bc = sim._schedule.intervals[0].bc
    hydro, energy = sim._hydro, sim._energy
    sub = dt / n_energy
    for _ in range(n_energy):
        hr = hydro.solve(state, sub, bc)
        T = energy.solve(hr, state, sub, bc)
        # Расщепление: T из энергии, остальное из гидро
        state = SimulationState(p=hr.state.p, Sg=hr.state.Sg, Rs=hr.state.Rs,
                                T=T, regime=hr.state.regime, t=hr.state.t)
    return state


def main() -> None:
    dt = 450.0   # аномальный шаг: A-retry дробит его на 2 подшага по 225 с

    # Эталон: тот же интервал 0..450 с, пройденный шагами по 50 с
    sim_ref, s_ref = build(50.0)
    st_ref = advance(sim_ref, s_ref, dt, n_energy=9)

    # (а) текущее поведение
    sim_a, s_a = build(dt)
    st_a = advance(sim_a, s_a, dt, n_energy=1)

    # (б) энергия дробится вместе с гидро
    sim_b, s_b = build(dt)
    st_b = advance(sim_b, s_b, dt, n_energy=2)

    print(f"Первый шаг истории, t: 0 -> {dt:g} с. Эталон — 9 шагов по 50 с.\n")
    print(f"  эталон               T[0] = {st_ref.T[0]:.6f} К")
    print(f"  (а) энергия 1 x 450 с T[0] = {st_a.T[0]:.6f} К   "
          f"ошибка {st_a.T[0] - st_ref.T[0]:+.6f} К")
    print(f"  (б) энергия 2 x 225 с T[0] = {st_b.T[0]:.6f} К   "
          f"ошибка {st_b.T[0] - st_ref.T[0]:+.6f} К")
    print()

    err_a = float(np.max(np.abs(st_a.T - st_ref.T)))
    err_b = float(np.max(np.abs(st_b.T - st_ref.T)))
    print(f"  max|dT| по полю (а) = {err_a:.4e} К")
    print(f"  max|dT| по полю (б) = {err_b:.4e} К")
    if err_b > 0:
        print(f"  улучшение в {err_a / err_b:.1f} раз")
    print()

    # Контроль: гидро-состояние обязано совпасть, иначе сравнение некорректно.
    same = np.allclose(st_a.p, st_b.p, rtol=1e-12)
    print(f"  гидро-состояние (а) и (б) совпадает: {same}")
    if not same:
        print("  ВНИМАНИЕ: состояния разошлись — вывод о причине некорректен!")


if __name__ == "__main__":
    main()
