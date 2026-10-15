"""Управление скважиной по дебиту нефти (FEAT-020).

Проверяет:
  A. RateControl — данные управления и их проверка при создании.
  B. Фабрика: конфиг с control = "rate" → RateControl → расчёт.
  C. Согласованность двух управлений: прогон по дебиту, которому подали
     дебиты прогона по давлению, повторяет его траекторию.
  D. Равенство управлений по значению (FEAT-032).

Физика (problem_statement.tex, eq:bc_rate_well, eq:bc_rate_pwf): при заданном
дебите нефти q_o,ст забойное давление выражается из уравнения притока,
p_wf = p[0] − q_o,ст / (T_{-1/2}·λ_o[0]), с нижней границей min_bhp. Дебит
положителен при добыче (q = −G_o[0], конвенция: > 0 — от скважины).
"""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.bc import PressureControl, RateControl, WellControl
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import HistoryInterval, load_config


DAY = 86400.0
ATM = 101325.0

# Конфиг примера 12 (R_ext = 200 м, p0 = 15.5 МПа, p_b = 15 МПа, N = 50,
# табличные PVT и ОФП) — заготовка сценариев управления по дебиту.
EX12 = Path(__file__).parent.parent / "examples" / "12_large_drainage_radius"


# ═══════════════════════════════════════════════════════════
# A. RateControl
# ═══════════════════════════════════════════════════════════

class TestRateControlClass:
    def test_stores_si_values(self):
        """Дебит в м³ст/с и min_bhp в Па хранятся как заданы (СИ, без пересчёта)."""
        rc = RateControl(2.0 / DAY, ATM)
        assert rc.q_oil == 2.0 / DAY
        assert rc.min_bhp == ATM

    def test_zero_rate_allowed(self):
        """q_oil = 0 допустим: скважина стоит, p_wf = p[0]."""
        assert RateControl(0.0, ATM).q_oil == 0.0

    def test_negative_rate_rejected(self):
        """q_oil < 0 — нагнетание; прототип его не поддерживает (blackoil.py)."""
        with pytest.raises(ValueError, match="q_oil"):
            RateControl(-1e-3, ATM)

    @pytest.mark.parametrize("min_bhp", [0.0, -1.0])
    def test_nonpositive_min_bhp_rejected(self, min_bhp):
        """min_bhp ≤ 0 — без нижней границы p_wf при λ_o → 0 уходит в −∞."""
        with pytest.raises(ValueError, match="min_bhp"):
            RateControl(1e-3, min_bhp)

    def test_is_well_control(self):
        assert isinstance(RateControl(1e-3, ATM), WellControl)

    def test_has_no_boundary_pressure(self):
        """Управление — только данные: способа вычислить p_wf в обход
        HydroResult у него нет (решение 8 плана FEAT-020)."""
        assert not hasattr(PressureControl(1e7), "boundary_pressure")
        assert not hasattr(RateControl(1e-3, ATM), "boundary_pressure")


class TestControlValueEquality:
    """FEAT-032: управления сравниваются по значению — смену управления ищет TimeSchedule."""

    def test_pressure_equal_by_value(self):
        """Два объекта с одним p_wf равны и хешируются одинаково; другой p_wf — не равен."""
        # Фабрика создаёт новый объект на каждый интервал: без равенства по
        # значению сменой управления был бы каждый интервал истории
        a, b = PressureControl(1.0e7), PressureControl(1.0e7)
        assert a is not b and a == b and hash(a) == hash(b)
        assert a != PressureControl(1.1e7)

    def test_rate_equal_by_value(self):
        """RateControl равны при равных q_oil и min_bhp; отличие любого — не равны."""
        a = RateControl(1e-3, 1e6)
        assert a == RateControl(1e-3, 1e6) and hash(a) == hash(RateControl(1e-3, 1e6))
        assert a != RateControl(2e-3, 1e6)
        assert a != RateControl(1e-3, 2e6)   # min_bhp — часть управления

    def test_different_types_not_equal(self):
        """Давление и дебит не равны ни в одну сторону (NotImplemented → тождество)."""
        p, r = PressureControl(1e6), RateControl(0.0, 1e6)
        assert p != r and r != p

    def test_boundary_conditions_compare_controls_by_value(self):
        """BoundaryConditions (dataclass) равны, если равны управления и условия на контуре."""
        from gpn_multiphase_solver.state import BoundaryConditions
        bc = lambda w: BoundaryConditions(well=w, p_ext=15.5e6, T_ext=350.0, Rs_ext=30.0)
        assert bc(PressureControl(6e6)) == bc(PressureControl(6e6))
        assert bc(PressureControl(6e6)) != bc(RateControl(0.0, ATM))


# ═══════════════════════════════════════════════════════════
# B. Фабрика: конфиг → RateControl → расчёт
# ═══════════════════════════════════════════════════════════

class TestFactoryRate:
    def test_factory_builds_rate_control(self):
        """Интервал control = "rate" превращается в RateControl и считается.

        Условия: конфиг примера 12, один интервал 3600 с, дебит 50 м³ст/сут,
        min_bhp = 1 атм. Ожидание: в расписании RateControl; дебит записи =
        заданному (прототип выдерживает его точно — уравнение притока
        решается относительно p_wf); p_wf ниже p0 = 15.5 МПа (добыча).
        Ловит: TypeError на p_wf = None при создании прототипа, отказ фабрики
        на control = "rate", ошибку единиц.
        """
        cfg = load_config(EX12 / "config.json")
        cfg.time.history = [HistoryInterval(dt=3600.0, control="rate",
                                            q_oil=50.0 / DAY, min_bhp=ATM)]
        cfg.output.log_level = "WARNING"
        simulator, initial = SimulatorFactory.from_config(cfg)
        assert isinstance(simulator._schedule.intervals[0].bc.well, RateControl)

        history = simulator.run(initial)
        w = history.well_data[1]
        assert w.q_o_std == pytest.approx(50.0 / DAY, rel=1e-12)
        assert ATM < w.p_wf < 15.5e6


# ═══════════════════════════════════════════════════════════
# C. Согласованность двух управлений
# ═══════════════════════════════════════════════════════════

class _CountingEnergy:
    """Обёртка энергии: запоминает dt каждого принятого подшага, физику не трогает.

    По образцу _CountingEnergySolver (test_simulator.py). Нужна, чтобы
    убедиться, что Simulator не раздробил шаги (локальное дробление,
    DEBT-015): при разном дроблении двух прогонов их совпадение не обязано
    выполняться.
    """

    def __init__(self, inner):
        self._inner = inner
        self.dt_calls: list[float] = []

    def solve(self, hydro_result, state_prev, dt, bc, collect=None):
        self.dt_calls.append(dt)
        return self._inner.solve(hydro_result, state_prev, dt, bc, collect)


def _config_via_json(tmp_path, name, history):
    """Конфиг примера 12 с заданной историей: JSON в tmp_path → load_config.

    Через файл, а не правкой объекта: так проверяется и чтение управления
    из конфига. Значения q_oil json пишет repr-точно. CSV таблиц PVT и ОФП
    копируются рядом — пути в конфиге относительные.
    """
    for f in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
        shutil.copyfile(EX12 / f, tmp_path / f)
    raw = json.loads((EX12 / "config.json").read_text(encoding="utf-8"))
    raw["time"]["history"] = history
    raw["time"]["dt_integration"] = 3600.0     # один подшаг на интервал
    raw["output"]["log_level"] = "WARNING"
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    return load_config(path)


def _run(cfg):
    simulator, initial = SimulatorFactory.from_config(cfg)
    counter = _CountingEnergy(simulator._energy)
    simulator._energy = counter
    return simulator.run(initial), counter


# p_wf прогона по давлению (24 интервала по 3600 с) и номера интервалов,
# которые прогон Б ведёт по дебиту. 14.4 МПа — первая ступень 13a: шаг не
# дробится; ячейка 0 переходит в двухфазный режим в первые часы.
_CASES = {
    "constant": ([14.4e6] * 24, range(24)),
    "step": ([14.4e6] * 12 + [13.8e6] * 12, range(24)),
    # 1-12 по дебиту, 13-24 по давлению: смена режима модели между интервалами
    "mixed": ([14.4e6] * 12 + [13.8e6] * 12, range(12)),
}


class TestControlConsistency:
    @pytest.mark.parametrize("case", list(_CASES))
    def test_rate_run_reproduces_pressure_run(self, tmp_path, case):
        """Прогон по дебиту с дебитами прогона по давлению повторяет его траекторию.

        Физика: схема неявная, поэтому состояние n+1 прогона А (по давлению)
        тождественно удовлетворяет невязке прогона Б, где тот же поток нефти
        через забой задан дебитом (eq:bc_rate_pwf), а p_wf выражается из
        уравнения притока. Решение шага единственно — траектории совпадают
        с точностью до допуска Ньютона, включая температуру: она зависит от
        управления только через поля гидродинамики.

        Замер (аудит FEAT-020): max|Δp| ≤ 3.6e-3 Па, |ΔS_g| ≤ 8.8e-11,
        |ΔR_s| ≤ 1.1e-8, |ΔT| ≤ 1.4e-9 К, |Δp_wf| ≤ 3.6e-3 Па. Пороги — с
        запасом ~300×. regime не сравнивается: ячейка на фазовой границе
        (S_g ≈ 0) может разойтись в режиме при |ΔS_g| < 1e-10.

        Не проверяет, какой p_wf получает энергия: при добыче он в неё не
        входит (Φ⁺ = 0, BUG-015) — это TestWellPressureSource (test_energy.py).
        """
        p_steps, rate_intervals = _CASES[case]
        rate_intervals = set(rate_intervals)

        hist_a = [{"dt": 3600.0, "control": "pressure", "p_wf": pw} for pw in p_steps]
        h_a, cnt_a = _run(_config_via_json(tmp_path, "pressure", hist_a))

        hist_b = [
            {"dt": 3600.0, "control": "rate",
             "q_oil": float(h_a.well_data[k + 1].q_o_std), "min_bhp": ATM}
            if k in rate_intervals else dict(hist_a[k])
            for k in range(len(p_steps))
        ]
        h_b, cnt_b = _run(_config_via_json(tmp_path, "rate", hist_b))

        # Без дробления: 24 подшага энергии в каждом прогоне
        assert len(cnt_a.dt_calls) == len(p_steps)
        assert len(cnt_b.dt_calls) == len(p_steps)

        for k, iv in enumerate(hist_b):
            w = h_b.well_data[k + 1]
            # ограничение min_bhp не сработало — иначе совпадения нет
            assert w.p_wf > ATM
            if iv["control"] == "rate":
                assert w.q_o_std == pytest.approx(iv["q_oil"], rel=1e-12)

        def max_diff(field):
            return max(float(np.max(np.abs(getattr(a, field) - getattr(b, field))))
                       for a, b in zip(h_a.states, h_b.states))

        assert max_diff("p") < 1.0          # Па
        assert max_diff("Sg") < 1e-8
        assert max_diff("Rs") < 1e-6        # м³ст/м³ст
        assert max_diff("T") < 1e-6         # К
        d_pwf = max(abs(a.p_wf - b.p_wf)
                    for a, b in zip(h_a.well_data[1:], h_b.well_data[1:]))
        assert d_pwf < 1.0                  # Па
