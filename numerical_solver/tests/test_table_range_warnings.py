"""Выход состояния за PVT- и ОФП-таблицы в ходе расчёта (DEBT-027).

Прототип берёт свойства за краями таблиц с краёв, без экстраполяции; его
pvt_range_warnings называет категорию выхода. Адаптер зовёт её после каждого
сошедшегося шага и пишет каждую категорию в журнал один раз за расчёт; начальное
состояние проверяет фабрика тем же методом (категория при t = 0 не повторяется).
«Кривая насыщения выше таблицы» — только по свободному газу (FREE_GAS_SG): ячейка
фронта с флагом газа при S_g ≈ 0 давала её в 12 из 15 табличных примеров.

Конфиг — configs/table_pvt: таблицы примера 04 (газ 5–30 МПа, ветви R_s = 0 и 30,
p_b(30) = 15 МПа), N = 20, p0 = 20 МПа, 24 интервала по 1 ч, ~0.3 с на расчёт.
Числа ожиданий — эмуляция плана (vault/issues/debt-027/probes/emulate_debt027.out.txt).

PVT Стендинга (DEBT-071): проверяется только таблица ОФП — relperm_range_warnings.
Конфиг — пример 05 (Стендинг + таблица ОФП до S_g = 0.8), первые часы; таблицы ОФП
сценариев — во временном каталоге теста. Числа — эмуляция плана
(vault/issues/debt-071/probes/plan_tests_emulate.out.txt, scenarios.out.txt).
"""

import logging
from pathlib import Path

import pytest

from radial_blackoil.diagnostics import pvt_range_warnings, warning_category
from radial_blackoil.state import BlackOilState

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.hydro.prototype_adapter import FREE_GAS_SG
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.units import BAR_TO_PA

ROOT = Path(__file__).parent.parent
TABLE_CONFIG = ROOT / "configs" / "table_pvt" / "config.json"
BASELINE = ROOT / "configs" / "baseline.json"
EXAMPLE_04A = ROOT / "examples" / "04a_high_gas_saturation" / "config.json"
ABOVE = "OIL_PVT saturated locus above table"
EXAMPLE_05 = ROOT / "examples" / "05_standing_table_rp" / "config.json"
RELPERM_ABOVE = "RELPERM Sg above table"


def _table_config(p_wf=None, p0=None):
    """configs/table_pvt; p_wf — на всех 24 интервалах, p0 — начальное давление."""
    config = load_config(TABLE_CONFIG)
    if p_wf is not None:
        for interval in config.time.history:
            interval.p_wf = p_wf
    if p0 is not None:
        config.initial_conditions.p0 = p0
    return config


def _run(config, caplog):
    """Фабрика и расчёт; (simulator, history, тексты записей журнала уровня WARNING)."""
    with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
        simulator, state0 = SimulatorFactory.from_config(config)
        history = simulator.run(state0)
    messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    return simulator, history, messages


def _proto(state):
    """SimulationState (Па) → BlackOilState прототипа (бар), как в адаптере."""
    return BlackOilState(pressure_bar=state.p / BAR_TO_PA, rs_sm3_sm3=state.Rs.copy(),
                         sg=state.Sg.copy(), gas_active=(state.regime == 1))


def _category(message):
    """Категория записи журнала «… вне таблиц: <текст прототипа>»."""
    return warning_category(message.split("вне таблиц: ", 1)[1])


def _standing_config(tmp_path, rows=None, hours=6):
    """Пример 05 (Стендинг + ОФП до S_g = 0.8), первые hours часов; rows — своя таблица ОФП."""
    # load_config разворачивает историю примера 05 в 72 интервала по 1 ч; абсолютный
    # путь в relperm.file фабрика берёт как есть (config_dir / абсолютный = абсолютный).
    config = load_config(EXAMPLE_05)
    config.time.history = config.time.history[:hours]
    if rows is not None:
        csv = tmp_path / "relperm.csv"
        csv.write_text("Sg,kro,krg\n" + "\n".join(rows) + "\n", encoding="utf-8")
        config.relperm.file = str(csv)
    return config


class TestFreeGasFilter:
    """pvt_range_warnings с free_gas_sg: ячейка фронта — не выход, свободный газ — выход."""

    def _cell_above_locus(self, sg):
        """Модель configs/table_pvt и одна ячейка в газовом режиме на 1 бар выше max p_b (150 бар)."""
        simulator, _ = SimulatorFactory.from_config(_table_config())
        model = simulator._hydro._model
        state = BlackOilState.undersaturated(1, model.pvt.pb[-1] + 1.0, model.pvt.rs_values[-1])
        state.gas_active[0] = True
        state.sg[0] = sg
        return model, state

    def test_front_cell_not_reported(self):
        """S_g = 0, R_s = 30 при 151 бар: прежняя проверка (без параметра) сообщает, с порогом — нет.

        Так выглядит ячейка фронта в 12 табличных примерах: флаг газа, свободного
        газа нет, обрезка R_s^sat на последней ветви ничего не меняет.
        """
        model, state = self._cell_above_locus(0.0)
        assert any(w.startswith(ABOVE) for w in pvt_range_warnings(model, state))
        assert not any(w.startswith(ABOVE)
                       for w in pvt_range_warnings(model, state, free_gas_sg=FREE_GAS_SG))

    def test_free_gas_reported(self):
        """S_g = 0.02 при 151 бар: газ, который не может раствориться, — выход за таблицу."""
        model, state = self._cell_above_locus(0.02)
        warnings = pvt_range_warnings(model, state, free_gas_sg=FREE_GAS_SG)
        assert any(w.startswith(f"{ABOVE}: free gas Sg up to 0.02") for w in warnings)


class TestRunWarnings:
    """Журнал расчёта: категория — одна запись за расчёт, с моментом первого выхода."""

    def test_inside_tables_silent(self, caplog):
        """Штатный конфиг (p_wf = 15 МПа = p_b): все состояния в таблицах — записей нет."""
        _, _, messages = _run(_table_config(), caplog)
        assert messages == []

    def test_front_cell_not_reported(self, caplog):
        """p_wf = 8 МПа: ячейка фронта выше p_b есть, но свободного газа в ней нет — записей нет.

        Предусловие: прежняя проверка (без free_gas_sg) на записях истории сообщает
        о кривой насыщения выше таблицы — тест проверяет именно фильтр, а не пустой расчёт.
        """
        simulator, history, messages = _run(_table_config(p_wf=8e6), caplog)
        model = simulator._hydro._model
        assert any(w.startswith(ABOVE)
                   for s in history.states for w in pvt_range_warnings(model, _proto(s)))
        assert messages == []

    def test_below_gas_table_reported_once(self, caplog):
        """p_wf = 2 МПа: у забоя p ниже газовой таблицы (от 5 МПа) на всех 24 шагах — две записи за расчёт.

        Газовая таблица и ветвь R_s = 0 начинаются при 5 МПа: B_g, μ_g и кривая
        насыщения берутся с края. Обе категории — с первого шага (1 ч = 0.04167 сут).
        """
        _, _, messages = _run(_table_config(p_wf=2e6), caplog)
        assert len(messages) == 2
        assert all(m.startswith("Состояние при t = 0.04167 сут вне таблиц: ") for m in messages)
        assert {_category(m) for m in messages} == {
            "GAS_PVT pressure below table", "OIL_PVT saturated locus below table"}

    def test_initial_category_not_repeated(self, caplog):
        """p0 = 32 МПа выше газовой таблицы и ветвей (до 30 МПа): записи только начальные.

        Вдали от забоя давление остаётся выше таблицы весь расчёт (предусловие ниже),
        но категории, выведенные при t = 0, адаптер не повторяет.
        """
        simulator, history, messages = _run(_table_config(p0=32e6), caplog)
        model = simulator._hydro._model
        assert any(w.startswith("GAS_PVT pressure above table")
                   for w in pvt_range_warnings(model, _proto(history.states[-1])))
        assert len(messages) == 2
        assert all(m.startswith("Начальное состояние вне таблиц: ") for m in messages)
        assert {_category(m) for m in messages} == {
            "GAS_PVT pressure above table", "OIL_PVT branch pressure above supplied range"}

    def test_free_gas_above_table_reported(self, caplog):
        """Пример 04a, первые 3 ч: газ выше p_b = 15 МПа, который не может раствориться, — с 2 ч.

        Изобара p_b за 0.75 ч уходит до r ≈ 1.8 м и возвращается (README 04a); в
        ячейках между давление снова выше 15 МПа, а таблица кончается ветвью
        R_s = 30 = R_s0. Плюс две категории первого шага (p у забоя 4.23 МПа < 5 МПа).
        """
        config = load_config(EXAMPLE_04A)
        config.time.history = config.time.history[:36]   # 36 интервалов по 300 с
        _, _, messages = _run(config, caplog)
        assert len(messages) == 3
        above = [m for m in messages if _category(m) == ABOVE]
        assert len(above) == 1
        assert above[0].startswith(f"Состояние при t = 0.08333 сут вне таблиц: {ABOVE}: free gas")


class TestStandingRelperm:
    """Путь Стендинга (DEBT-071): проверяется только таблица ОФП — PVT по формулам, краёв нет."""

    def test_relperm_above_table_reported_alone(self, tmp_path, caplog):
        """S_g = 0.85 выше таблицы примера 05 (до 0.8): одна запись, PVT-категорий нет.

        Давление 500 бар и R_s = 300 — далеко за псевдотаблицей адаптера Стендинга
        (rs_values, pb — до p0 = 200 бар), но PVT не проверяется: свойства по
        формулам. Вызванная, PVT-проверка упала бы на газовой таблице gp, которой у
        HydroPVTtoBlackOilAdapter нет (предусловие).
        """
        simulator, _ = SimulatorFactory.from_config(_standing_config(tmp_path))
        adapter = simulator._hydro
        state = BlackOilState.undersaturated(3, 500.0, 300.0)
        state.gas_active[0] = True
        state.sg[0] = 0.85
        with pytest.raises(AttributeError):
            pvt_range_warnings(adapter._model, state)
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            adapter.warn_table_range(state, 3600.0)
        messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert messages == ["Состояние при t = 0.04167 сут вне таблиц: RELPERM Sg above table: "
                            "max Sg=0.85, table max=0.8. Endpoint value used; no extrapolation."]

    def test_relperm_above_table_before_failure(self, tmp_path, caplog):
        """Таблица до S_g = 0.01 (k_ro = 0.98 на краю): запись с 56 с, затем отказ первого часа.

        Выше края k_ro и k_rg постоянны: нефть подвижна при любой S_o и уходит, газ
        остаётся — у забоя S_g = 0.917 на принятом подшаге 3600/64 = 56.25 с. Затем
        подшаг не сходится и при dt/512 (DEBT-073: отказ — свойство таблицы, текст
        отказа её не называет). Запись «вне таблиц» — единственное указание на таблицу.
        """
        config = _standing_config(tmp_path, ["0.0,1.0,0.0", "0.01,0.98,0.001"], hours=1)
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            simulator, state0 = SimulatorFactory.from_config(config)
            with pytest.raises(RuntimeError, match="не сошёлся"):
                simulator.run(state0)
        messages = [r.getMessage() for r in caplog.records
                    if r.levelno >= logging.WARNING and "вне таблиц" in r.getMessage()]
        assert len(messages) == 1
        assert messages[0].startswith(
            f"Состояние при t = 0.000651 сут вне таблиц: {RELPERM_ABOVE}: max Sg=0.917")

    def test_initial_below_table_not_repeated(self, tmp_path, caplog):
        """Таблица ОФП с S_g = 0.05: S_g = 0 ниже таблицы — одна запись, при t = 0.

        SGOF требует начала таблицы с S_g = 0, фабрика это не проверяет. Вдали
        от забоя S_g = 0 весь расчёт (предусловие), но категория, выведенная для
        начального состояния, по ходу расчёта не повторяется.
        """
        rows = ["0.05,0.9,0.005", "0.1,0.8,0.01", "0.2,0.6,0.05",
                "0.4,0.3,0.2", "0.6,0.1,0.5", "0.8,0.0,0.8"]
        _, history, messages = _run(_standing_config(tmp_path, rows), caplog)
        assert history.states[-1].Sg.min() == 0.0
        assert messages == ["Начальное состояние вне таблиц: RELPERM Sg below table: min Sg=0, "
                            "table min=0.05. Endpoint value used; no extrapolation."]

    def test_checked_after_every_accepted_step(self, tmp_path, monkeypatch):
        """ОФП проверяется в начале и после каждого принятого шага, PVT — ни разу.

        Пример 05 считает каждый час одним шагом, без дробления (72 из 72, проба
        DEBT-071 scan.out.txt): за 6 ч — 1 + 6 вызовов. Шпионы подменяют функции
        модуля прототипа: адаптер импортирует их при каждом вызове и видит подмену.
        """
        import radial_blackoil.diagnostics as diagnostics
        calls = {"pvt": 0, "relperm": 0}
        relperm_orig = diagnostics.relperm_range_warnings
        pvt_orig = diagnostics.pvt_range_warnings

        def relperm_spy(model, state):
            calls["relperm"] += 1
            return relperm_orig(model, state)

        def pvt_spy(model, state, free_gas_sg=None):
            calls["pvt"] += 1
            return pvt_orig(model, state, free_gas_sg=free_gas_sg)

        monkeypatch.setattr(diagnostics, "relperm_range_warnings", relperm_spy)
        monkeypatch.setattr(diagnostics, "pvt_range_warnings", pvt_spy)
        simulator, state0 = SimulatorFactory.from_config(_standing_config(tmp_path))
        simulator.run(state0)
        assert calls == {"pvt": 0, "relperm": 7}

    def test_standing_corey_silent(self, caplog):
        """Стендинг + Кори (configs/baseline, 96 ч): Кори — таблица на S_g ∈ [0, 1], записей нет."""
        _, _, messages = _run(load_config(BASELINE), caplog)
        assert messages == []
