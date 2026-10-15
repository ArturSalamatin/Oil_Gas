"""DEBT-071: тесты GPN шага 2 плана на коде плана, подставленном в памяти (standing_relperm_scan.install).

Класс TestStandingRelperm — дословно из плана (шаг 2, п. 6); помощники _run, _standing_config —
как в tests/test_table_range_warnings.py после шага 2. Запуск из numerical_solver/:
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\debt-071\\probes\\plan_tests_emulate.py -q -p no:cacheprovider
"""
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import standing_relperm_scan  # noqa: E402

standing_relperm_scan.install()

from radial_blackoil.diagnostics import pvt_range_warnings  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

ROOT = Path.cwd()
BASELINE = ROOT / "configs" / "baseline.json"


def _run(config, caplog):
    """Фабрика и расчёт; (simulator, history, тексты записей журнала уровня WARNING)."""
    with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
        simulator, state0 = SimulatorFactory.from_config(config)
        history = simulator.run(state0)
    messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    return simulator, history, messages


# ── Дословно из плана, шаг 2, п. 6 ──
EXAMPLE_05 = ROOT / "examples" / "05_standing_table_rp" / "config.json"
RELPERM_ABOVE = "RELPERM Sg above table"


def _standing_config(tmp_path, rows=None, hours=6):
    """Пример 05 (Стендинг + таблица ОФП до S_g = 0.8): первые hours интервалов по 1 ч; rows — своя таблица ОФП."""
    config = load_config(EXAMPLE_05)
    config.time.history = config.time.history[:hours]
    if rows is not None:
        csv = tmp_path / "relperm.csv"
        csv.write_text("Sg,kro,krg\n" + "\n".join(rows) + "\n", encoding="utf-8")
        config.relperm.file = str(csv)
    return config


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
        """Таблица с S_g = 0.05 (SGOF требует начала с 0): S_g = 0 ниже таблицы — одна запись при t = 0.

        Вдали от забоя S_g = 0 весь расчёт (предусловие), но категория, выведенная
        для начального состояния, по ходу расчёта не повторяется.
        """
        rows = ["0.05,0.9,0.005", "0.1,0.8,0.01", "0.2,0.6,0.05",
                "0.4,0.3,0.2", "0.6,0.1,0.5", "0.8,0.0,0.8"]
        _, history, messages = _run(_standing_config(tmp_path, rows), caplog)
        assert history.states[-1].Sg.min() == 0.0
        assert messages == ["Начальное состояние вне таблиц: RELPERM Sg below table: min Sg=0, "
                            "table min=0.05. Endpoint value used; no extrapolation."]

    def test_checked_after_every_accepted_step(self, tmp_path, monkeypatch):
        """Проверка ОФП — на начальном состоянии и после каждого принятого шага; PVT-проверка — ни разу.

        Пример 05 считает каждый час одним шагом, без дробления (72 из 72, проба
        DEBT-071 scan.out.txt): за 6 ч — 1 + 6 вызовов.
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
        """Стендинг + Кори (configs/baseline, 96 ч): Кори протабулирована на S_g ∈ [0, 1] — записей нет."""
        _, _, messages = _run(load_config(BASELINE), caplog)
        assert messages == []
