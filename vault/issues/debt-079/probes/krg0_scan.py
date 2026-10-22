"""DEBT-079: что делает расчёт с таблицей ОФП, у которой k_rg > 0 в первой строке.

Вывод issue #127 (из кода, не замерен): газовый фактор у забоя = R_s[0] + λ_g/λ_o(S_g = 0)
в ячейке 0, если она недонасыщена; R_s растёт к забою. Здесь — замер.

Сценарий A — configs/table_pvt (таблицы примера 04, N = 20, R_ext = 50 м, p0 = 20 МПа,
R_s0 = 30, p_b(30) = 15 МПа), 24 ч по 1 ч; первая строка ОФП `0.0,1.0,k` при
k = 0 / 1e-4 / 1e-3 / 1e-2, p_wf = 15 МПа (конфиг) и 17 МПа (вся область недонасыщена).
Сценарий B — пример 05 (Стендинг), 6 ч, таблица теста DEBT-071
test_initial_below_table_not_repeated: первая строка `0.05,0.9,0.005` (как в тесте)
и `0.05,0.9,0.0` (предлагаемая правка теста).

Запуск из numerical_solver/ (код базы):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-079\\probes\\krg0_scan.py
"""
import logging
from pathlib import Path

import numpy as np

import gpn_multiphase_solver
import radial_blackoil
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.units import BAR_TO_PA

SOLVER = Path.cwd()
HERE = Path(__file__).resolve().parent
DAY = 86400.0
print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
print(f"прототип: {Path(radial_blackoil.__file__).parent}", flush=True)

TABLE_RP_ROWS = ["0.1,0.8,0.01", "0.2,0.6,0.05", "0.4,0.3,0.2", "0.6,0.1,0.5", "0.8,0.0,0.8"]
DEBT071_ROWS = ["0.1,0.8,0.01", "0.2,0.6,0.05", "0.4,0.3,0.2", "0.6,0.1,0.5", "0.8,0.0,0.8"]


class Collect(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


def run(cfg):
    """Фабрика + расчёт; (simulator, history, записи WARNING, текст отказа или None)."""
    logger = logging.getLogger("gpn_multiphase_solver")
    h = Collect()
    logger.addHandler(h)
    sim = history = None
    err = None
    try:
        sim, s0 = SimulatorFactory.from_config(cfg)
        logger.setLevel(logging.WARNING)
        history = sim.run(s0)
    except Exception as exc:  # noqa: BLE001 — проба: печать причины
        err = f"{type(exc).__name__}: {str(exc)[:160]}"
    finally:
        logger.removeHandler(h)
    return sim, history, h.records, err


def ratio_sg0(sim, p_pa, rs):
    """λ_g/λ_o при S_g = 0 (поверхностные подвижности прототипа), м³ст/м³ст."""
    lo, lg = sim._hydro._model._phase_mobilities_surface(p_pa / BAR_TO_PA, rs, 0.0)
    return float(lg) / float(lo)


def report(sim, history, k_out):
    st = history.states[k_out]
    w = history.well_data[k_out]
    gor = w.q_g_std / w.q_o_std
    pred = (st.Rs[0] + ratio_sg0(sim, st.p[0], st.Rs[0])) if st.regime[0] == 0 else float("nan")
    n_gas = int(np.sum(st.regime == 1))
    return (f"t = {history.times[k_out] / 3600:4.0f} ч: q_o = {w.q_o_std * DAY:8.3f} м³ст/сут, "
            f"ГФ = {gor:9.4f}, R_s[0] + λg/λo(S_g=0) = {pred:9.4f}, "
            f"S_g[0] = {st.Sg[0]:.3g}, R_s[0] = {st.Rs[0]:.4f}, max R_s = {st.Rs.max():.4f}, "
            f"ячеек с газом {n_gas}, max S_g = {st.Sg.max():.3g}, T[0] = {st.T[0]:.4f} К")


def scenario_a():
    print("\n═══ A: configs/table_pvt, 24 ч, первая строка ОФП 0.0,1.0,k ═══")
    for p_wf in (15e6, 17e6):
        ref_T = None
        for k in (0.0, 1e-4, 1e-3, 1e-2):
            csv = HERE / f"relperm_krg0_{k:g}.csv"
            csv.write_text("Sg,kro,krg\n" + "\n".join([f"0.0,1.0,{k:g}"] + TABLE_RP_ROWS) + "\n",
                           encoding="utf-8")
            cfg = load_config(SOLVER / "configs" / "table_pvt" / "config.json")
            for interval in cfg.time.history:
                interval.p_wf = p_wf
            cfg.relperm.file = str(csv)
            sim, history, msgs, err = run(cfg)
            print(f"\n--- p_wf = {p_wf / 1e6:g} МПа, k_rg[0] = {k:g} ---")
            if err:
                print(f"  отказ: {err}")
            if history is None:
                continue
            # λg/λo(S_g = 0) на контуре (p0, R_s0) и у забоя (p_wf, R_s0) — масштаб фиктивного ГФ
            print(f"  λg/λo(S_g=0): контур {ratio_sg0(sim, 20e6, 30.0):.4g}, "
                  f"забой {ratio_sg0(sim, p_wf, 30.0):.4g} м³ст/м³ст")
            # запись 0 — начальное состояние (дебитов нет); 1 — конец первого часа
            for k_out in (1, len(history.times) - 1):
                print("  " + report(sim, history, k_out))
            T0 = history.states[-1].T[0]
            if k == 0.0:
                ref_T = T0
            else:
                print(f"  ΔT[0] против k_rg[0] = 0: {T0 - ref_T:+.4f} К")
            for m in sorted(set(msgs)):
                print(f"  журнал: {m[:200]}")


def scenario_b():
    print("\n═══ B: пример 05 (Стендинг), 6 ч, таблица теста DEBT-071 ═══")
    for first in ("0.05,0.9,0.005", "0.05,0.9,0.0"):
        csv = HERE / f"relperm_debt071_{first.split(',')[-1]}.csv"
        csv.write_text("Sg,kro,krg\n" + "\n".join([first] + DEBT071_ROWS) + "\n", encoding="utf-8")
        cfg = load_config(SOLVER / "examples" / "05_standing_table_rp" / "config.json")
        cfg.time.history = cfg.time.history[:6]
        cfg.relperm.file = str(csv)
        sim, history, msgs, err = run(cfg)
        print(f"\n--- первая строка {first} ---")
        if err:
            print(f"  отказ: {err}")
        if history is None:
            continue
        print("  " + report(sim, history, len(history.times) - 1))
        # утверждения теста test_initial_below_table_not_repeated
        print(f"  Sg.min() последнего состояния == 0.0: {history.states[-1].Sg.min() == 0.0}")
        print(f"  записи WARNING ({len(msgs)}): {msgs}")


if __name__ == "__main__":
    scenario_a()
    scenario_b()
