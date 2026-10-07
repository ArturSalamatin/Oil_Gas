import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, r"D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\HydroSolverPrototype\Prototype_1.0.3")
sys.path.append(r"D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\examples")          # общие модули examples/ — после копии

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

EXAMPLES_DIR = Path(r"D:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\feat-023\probes\r2\examples")


def _pvt_of_config(cfg):
    from gpn_multiphase_solver.factory import _create_pvt
    return _create_pvt(cfg)


@pytest.fixture(scope="session")
def results():
    name = "13b_pwf_alternating"
    cfg = load_config(EXAMPLES_DIR / name / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)
    history = simulator.run(initial)
    final = history.states[-1]
    return {name: {
        "history": history, "grid": simulator._grid, "config": cfg,
        "Rs0": cfg.initial_conditions.Rs0, "p": final.p, "T": final.T,
        "Sg": final.Sg, "Rs": final.Rs, "T_well": float(final.T[0]),
        "q_o": np.array([w.q_o_std for w in history.well_data]),
        "q_g": np.array([w.q_g_std for w in history.well_data]),
    }}


def test_steady_state_false_skips_steady_analytics(tmp_path, monkeypatch):
    """steady_state=False снимает стационарную аналитику, проверку R_s — нет.

    Решения пользователя: 2026-09-29 (FEAT-022, реш. 7) — стационарные
    наложения и сверки отключаются флагом run_example; 2026-09-30
    (FEAT-023) — проверка R_s остаётся. Стационар и асимптотика
    температуры — пределы t -> inf при удержании одного режима; у 13b
    режим меняется каждые сутки, и сверки печатали бы 7085 % и 0.94 К.

    Функции проверок подменяются шпионами: тест смотрит, что они НЕ
    вызываются, а не разбирает PNG. Пример 05 — самый быстрый двухфазный
    (~5 с). Путь по умолчанию (steady_state=True) покрыт
    test_energy_balance_reported_for_all_examples («Асимптотика
    температуры» в выводе).
    Ловит: флаг снимает не всё (наложение или один из отчётов остался)
    или снимает лишнее (report_rs).
    """
    import contextlib
    import io
    import sys
    sys.path.insert(0, str(EXAMPLES_DIR))
    import example_runner

    called = []

    def spy(name):
        def f(*args, **kwargs):
            called.append(name)
            # make_overlay_* вернули бы функцию рисования; None — «без наложения»
            return None
        return f

    for name in ("make_overlay_pressure", "make_overlay_saturation",
                 "report_closed", "report_asymptotics", "report_rs"):
        monkeypatch.setattr(example_runner, name, spy(name))

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        example_runner.run_example(
            config_path=EXAMPLES_DIR / "05_standing_table_rp" / "config.json",
            output_dir=tmp_path,
            title="тест steady_state",
            steady_state=False,
        )

    assert called == ["report_rs"], f"вызваны: {called}"
    assert "Стационарная аналитика отключена" in buf.getvalue()


# ═══════════════════════════════════════════════════════════
# Q. Сценарий 13b: чередование p_wf 6 <-> 10.75 МПа (FEAT-023)
# ═══════════════════════════════════════════════════════════

class TestPwfAlternating:
    """Сценарий 13b: конфиг 12, p_wf по суткам 6 / 10.75 МПа, 30 сут.

    Сутки d = 1..30: нечётные 6 МПа, чётные 10.75 МПа = (6 + 15.5)/2.
    Запись каждые 0.5 сут: 60 интервалов, 61 запись; запись n >= 1 —
    конец интервала n, сутки d = (n + 1) // 2; середина суток d —
    запись 2d - 1, конец — 2d. Скачок вверх поднимает p_wf выше давления
    у забоя (6.13 МПа): прототип закрывает скважину (обратный клапан,
    eq:bc_pwf_shutin), но закрытие длится 2-3 мин и при шаге 3600 с на
    принятых шагах не видно (замер FEAT-023).
    """

    NAME = "13b_pwf_alternating"

    @staticmethod
    def _pwf_of_day(d):
        """Заданное p_wf суток d, Па: нечётные 6 МПа, чётные 10.75 МПа."""
        return 6.0e6 if d % 2 == 1 else 10.75e6

    def test_pwf_follows_schedule(self, results):
        """Фактическое p_wf каждой записи совпадает с расписанием.

        WellData.p_wf — фактическое давление шага (FEAT-020): у закрытой
        скважины оно равно p[0] и ниже заданного. Совпадение на всех 60
        записях значит заодно, что на моментах записи скважина открыта.
        Замер: отклонение 0 Па.
        Ловит: сдвиг расписания на интервал, опечатку в конфиге, закрытую
        скважину на конце интервала.
        """
        wd = results[self.NAME]["history"].well_data
        assert len(wd) == 61
        for n in range(1, 61):
            expected = self._pwf_of_day((n + 1) // 2)
            assert wd[n].p_wf == pytest.approx(expected, abs=1e-3), \
                f"запись {n}: p_wf = {wd[n].p_wf}, ожидалось {expected}"

    def test_high_pwf_days_produce_less(self, results):
        """Конец суток при 10.75 МПа: q_o и S_g(r_w) ниже, чем в конце предыдущих при 6 МПа.

        Физика: депрессия 4.75 МПа против 9.5 — приток меньше, давление у
        забоя выше, газа выделяется меньше и часть его растворяется
        обратно. Пары k = 1..15: конец суток 2k-1 — запись 4k-2, конец
        суток 2k — запись 4k. Замер: q_o 1.73-1.86e-3 против 3.18-3.35e-3
        м³ст/с, S_g(r_w) 0.0029-0.0174 против 0.0247-0.0483.
        Ловит: потерю чередования режимов (p_wf не меняется).
        """
        r = results[self.NAME]
        q = r["q_o"]
        sg_w = np.array([st.Sg[0] for st in r["history"].states])
        for k in range(1, 16):
            lo, hi = 4 * k - 2, 4 * k
            assert q[hi] < q[lo], f"пара {k}: q_o {q[hi]:.4e} >= {q[lo]:.4e}"
            assert sg_w[hi] < sg_w[lo], \
                f"пара {k}: S_g(r_w) {sg_w[hi]:.4f} >= {sg_w[lo]:.4f}"

    def test_rate_approaches_regime_from_opposite_sides(self, results):
        """Внутри суток дебит спадает после скачка вниз и растёт после скачка вверх.

        После скачка 10.75 -> 6 МПа перепад у забоя максимален, воронка
        расширяется, дебит убывает к режиму 6 МПа сверху. После скачка
        6 -> 10.75 МПа профиль, сложившийся при 6 МПа, заполняется
        притоком от контура, перепад p[0] - p_wf растёт, дебит растёт к
        режиму 10.75 МПа снизу. Замер: на всех 30 сутках (сутки 1:
        3.383 -> 3.235e-3; сутки 2: 1.698 -> 1.746e-3 м³ст/с).
        Ловит: неверный знак отклика на скачок ГУ.
        """
        q = results[self.NAME]["q_o"]
        for d in range(1, 31):
            mid, end = q[2 * d - 1], q[2 * d]
            if d % 2 == 1:
                assert mid > end, f"сутки {d} (6 МПа): q_o не спадает: {mid:.4e} -> {end:.4e}"
            else:
                assert mid < end, f"сутки {d} (10.75 МПа): q_o не растёт: {mid:.4e} -> {end:.4e}"

    def test_repressurization_leaves_undersaturated_oil(self, results):
        """Обратное растворение газа ограничено его запасом.

        Финал (30 сут, 10.75 МПа): есть однофазные ячейки ниже p_b — нефть
        недонасыщена, R_s < R_s^eq(p) (замер: 30 ячеек на 0.9-75 м, зазор
        0.18-2.44 м³ст/м³ст). В двухфазных ячейках R_s = R_s^eq(p) —
        равновесие Black Oil (замер 1e-13). Концы суток при 6 МПа (записи
        2, 6, ..., 58): однофазных ячеек ниже p_b нет — давление ниже
        прежнего, газ снова выделился всюду.
        Отбор по regime, а не по S_g == 0: прототип обнуляет крошечную
        отрицательную S_g, оставляя ячейку двухфазной (blackoil.py:275).
        Ловит: мгновенное пересыщение нефти газом «из ниоткуда» или
        залипание ячеек в двухфазном режиме при росте давления.
        """
        r = results[self.NAME]
        pvt = _pvt_of_config(r["config"])
        pb = float(pvt.pb(np.array([r["Rs0"]]))[0])
        states = r["history"].states

        final = states[-1]
        rs_eq = pvt.Rs_eq(final.p)
        under = (final.regime == 2) & (final.p < pb)
        assert np.count_nonzero(under) > 0, "на финале нет недонасыщенной нефти ниже p_b"
        assert np.all(final.Rs[under] < rs_eq[under] - 1e-6), \
            "однофазная ячейка ниже p_b с R_s >= R_s^eq(p)"
        two = final.regime == 1
        np.testing.assert_allclose(final.Rs[two], rs_eq[two], rtol=0.0, atol=1e-10)

        for n in range(2, 61, 4):
            st = states[n]
            bad = (st.regime == 2) & (st.p < pb)
            assert not np.any(bad), (
                f"запись {n} (конец суток при 6 МПа): "
                f"{np.count_nonzero(bad)} однофазных ячеек ниже p_b")

    def test_main_plots_seven_moments(self):
        """main.py 13b рисует профили на 7 моментах: 0, 5, ..., 30 сут.

        Решение пользователя 2026-09-30: 5, 15, 25 сут — концы суток при
        6 МПа, 10, 20, 30 сут — при 10.75 МПа.
        """
        text = (EXAMPLES_DIR / self.NAME / "main.py").read_text(encoding="utf-8")
        assert "n_profiles=7" in text

    def test_main_disables_steady_state(self):
        """main.py 13b отключает стационарную аналитику (решение 2026-09-29)."""
        text = (EXAMPLES_DIR / self.NAME / "main.py").read_text(encoding="utf-8")
        assert "steady_state=False" in text
