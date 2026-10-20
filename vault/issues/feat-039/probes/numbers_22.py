"""FEAT-039 (планирование): числа README примера 22 до и после нарастания на пуске.

Таблица «Ожидаемое поведение» (q_o, GOR, T(r_w) - T_0 на моментах записи), двухфазная
зона и S_g у забоя на 5, 15, 30 сут, члены баланса энергии за 30 сут. Аргумент emul –
эмуляция FEAT-039 (feat039_emul): интервал 0 – смена управления.

Запуск из numerical_solver/ (P – путь к скрипту): .venv\\Scripts\\python P [emul]
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from start_series import config_path, fingerprint  # noqa: E402

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

DAY = 86400.0


def main():
    # [emul] [имя примера]; без имени – 22 (для 16, 17 – дебиты q_o записей таблиц README)
    args = sys.argv[1:]
    emul = args[:1] == ["emul"]
    if emul:
        import feat039_emul
        feat039_emul.pytest_configure(None)
        args = args[1:]
    name = args[0] if args else "22_workbook_input"
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}; {name}; "
          f"{'эмуляция FEAT-039' if emul else 'как есть'}", flush=True)
    cfg = load_config(config_path(name))
    cfg.output.log_level = "ERROR"
    sim, s0 = SimulatorFactory.from_config(cfg)
    h = sim.run(s0)
    print(f"отпечаток {fingerprint(h)}", flush=True)
    T0 = cfg.initial_conditions.T0
    r = sim._grid.r_centers
    for i, t in enumerate(h.times):
        if i == 0:
            continue
        w, st = h.well_data[i], h.states[i]
        q_o = w.q_o_std * DAY
        gor = w.q_g_std / w.q_o_std if w.q_o_std > 0 else float("nan")
        zone = float(r[np.nonzero(st.Sg > 0)[0].max()]) if np.any(st.Sg > 0) else 0.0
        print(f"t = {t / DAY:9.5f} сут: q_o {q_o:.4g} ({w.q_o_std:.5e} м³ст/с), GOR {gor:.4g}, T(r_w)-T0 {st.T[0] - T0:+.4f} К, "
              f"S_g(r_w) {st.Sg[0]:.4f}, зона до {zone:.3f} м, p(r_w) {st.p[0] / 1e5:.4f} бар", flush=True)
    b = h.balance[-1]
    print("баланс энергии на конце, Дж: " + ", ".join(f"{k} {v:.4g}" for k, v in b.items()), flush=True)


if __name__ == "__main__":
    main()
