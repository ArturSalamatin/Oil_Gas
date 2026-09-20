"""Аудит BUG-010: если осреднение неверно, то в чём настоящая причина?

Установлено: по мгновенному потоку поток последнего подшага БЛИЖЕ к эталону,
чем среднее. Значит P4 прав и осреднение -- подгонка.

Новая гипотеза. Энергия использует ДВА рода величин:
  (1) потоки Q, G  -- мгновенные при t^{n+1}  (P4: так и надо для неявной схемы)
  (2) разности (p - p_old)/dt и (Rs - Rs_old)/dt -- средние за ВЕСЬ dt

При n_sub = 1 обе величины относятся к одному интервалу dt -- согласовано.
При A-retry состояние проходит через подшаги, но p_old остаётся началом
ПОЛНОГО шага. Это по-прежнему корректно (средняя скорость за интервал).

Тогда откуда 0.48 К? Проверим, где именно расходятся прогоны:
сравним состояние и температуру после ОДНОГО шага dt=450 (с retry)
против эталонной траектории мелким шагом.

Ключевой вопрос: аномалия в ГИДРО-состоянии или в ЭНЕРГИИ?
Реестр утверждал "не гидродинамика" -- перепроверим прямым сравнением,
насколько p, Sg, Rs после аномального шага отличаются от эталона,
и сравним это с чистым шагом близкой длины.
"""

import copy
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(r"d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver")
_PROTO = _ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
for _p in (str(_PROTO), str(_ROOT / "examples")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CFG = _ROOT / "examples" / "07_degassing_adiabatic_only" / "config.json"


def run(dt, n_intervals=1):
    cfg = copy.deepcopy(load_config(CFG))
    cfg.time.dt_integration = float(dt)
    cfg.time.history = cfg.time.history[:n_intervals]
    sim, s0 = SimulatorFactory.from_config(cfg)
    h = sim.run(s0)
    return h.states[-1]


def main():
    ref = run(50.0)

    print("Состояние в конце первого интервала (3600 с) против эталона dt=50 с")
    print(f"{'dt':>6} {'retry':>6} {'max|dp|, Па':>13} {'max|dSg|':>11} "
          f"{'max|dRs|':>11} {'max|dT|, К':>12}")
    print("-" * 66)

    for dt in (600.0, 450.0, 400.0, 360.0):
        st = run(dt)
        dp = float(np.max(np.abs(st.p - ref.p)))
        dsg = float(np.max(np.abs(st.Sg - ref.Sg)))
        drs = float(np.max(np.abs(st.Rs - ref.Rs)))
        dT = float(np.max(np.abs(st.T - ref.T)))
        n_sub = int(np.ceil(3600.0 / dt))
        retry = "да" if n_sub in (3, 5, 8, 9) else "нет"
        print(f"{dt:6.0f} {retry:>6} {dp:13.4e} {dsg:11.4e} {drs:11.4e} {dT:12.4e}")

    print()
    print("Если dp/dSg/dRs у аномальных шагов НЕ выделяются, а dT выделяется --")
    print("дефект в энергии. Если выделяются и гидро -- дефект в гидро-траектории.")


if __name__ == "__main__":
    main()
