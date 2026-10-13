"""Проверка R_s: diagnostics/rs.py (проверка) и examples/rs_analytics.py (печать, наложение); DEBT-026.

Проверка обязана быть верной при любой истории давления:
  ячейка со свободным газом (Sg > SG_GAS): Rs = Rs_eq(p);
  ячейка без газа:                         Rs <= Rs_eq(p) + rs_switch_tol —
                                           недонасыщенность допустима.
Прежняя формула Rs = min(Rs_eq(p), Rs0) во всех ячейках верна только при
монотонно падающем давлении и на примерах 12, 13b печатала «не совпадают».

Состояния синтетические, PVT — настоящий, примеров 04 (таблица, Rs0 = 30,
pb = 15 МПа, Rs_eq = 30 при p >= 15 МПа) и 03 (Стендинг, Rs0 = 50).
Расчёта нет — быстрый уровень.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gpn_multiphase_solver.factory import create_pvt  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.state import SimulationState  # noqa: E402

# Модуль примеров, не пакета: путь только до examples/ (как в
# test_energy_balance_examples.py).
_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

import rs_analytics  # noqa: E402
# Проверка R_s — в пакете (DEBT-011); печать и наложение — examples/rs_analytics.py
from gpn_multiphase_solver.diagnostics import rs as rs_core  # noqa: E402

MPA = 1e6
R = np.geomspace(0.1, 100.0, 6)        # центры ячеек, м (только для рисунка)


def _case(name):
    """(config, pvt) примера без расчёта."""
    cfg = load_config(_EXAMPLES / name / "config.json")
    return cfg, create_pvt(cfg)


def _history(p_mpa, Rs, regime, Sg=None):
    """История из одного состояния: rs_analytics читает только states[-1].

    Sg по умолчанию — 0.1 в ячейках regime == 1 и 0 в остальных, как у
    решателя без артефактов; явный Sg — для ячеек «флаг без газа».
    """
    p = np.asarray(p_mpa, float) * MPA
    regime = np.asarray(regime, int)
    if Sg is None:
        Sg = np.where(regime == 1, 0.1, 0.0)
    st = SimulationState(p=p, Sg=np.asarray(Sg, float), Rs=np.asarray(Rs, float),
                         T=np.full(p.size, 350.0), regime=regime, t=0.0)
    return SimpleNamespace(states=[st])


def _report(cfg, hist, pvt, capsys):
    """report_rs без засорения вывода теста."""
    rep = rs_analytics.report_rs(cfg, hist, pvt)
    capsys.readouterr()
    return rep


def _draw(cfg, pvt, hist):
    """Наложение на пустые оси; возвращает (кружки, подписи линий)."""
    fig, ax = plt.subplots()
    grid = SimpleNamespace(r_centers=R[:hist.states[-1].p.size])
    sim = SimpleNamespace(pvt=pvt)
    rs_analytics._draw_rs(ax, hist, grid, sim, cfg)
    marks = [ln for ln in ax.get_lines() if ln.get_marker() == "o"]
    labels = [ln.get_label() for ln in ax.get_lines()]
    plt.close(fig)
    return marks, labels


# ── Падающее давление: прежняя и новая проверки согласны ──

def test_monotone_pressure_passes(capsys):
    """Фронт на 15 МПа: левее газ (Rs = Rs_eq), правее исходная нефть (Rs0).

    Ожидание: ошибка в ячейках с газом ровно 0 (одна функция от одного p),
    нарушений нет, нефти без газа ниже pb нет.
    """
    cfg, pvt = _case("04_table_table")
    p = [8, 10, 12, 14, 16, 18]
    regime = [1, 1, 1, 1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[4:] = 30.0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["max_abs"] == 0.0
    assert rep["n_two_phase"] == 4
    assert rep["n_supersaturated"] == 0
    assert rep["n_single_below_pb"] == 0


# ── Восстановление давления: случай DEBT-026 ──

def test_repressurization_undersaturated_is_not_violation(capsys):
    """Нефть без газа ниже pb с Rs < Rs_eq(p) — допустимое состояние.

    Картина 13b на конце 30 сут: газ только у забоя, дальше до изобары
    недонасыщенная нефть. Прежняя формула min(Rs_eq, Rs0) дала бы здесь
    ошибку 2 — это и проверяется первой строкой, чтобы тест не стал
    тавтологией. Новая: нарушений нет, три ячейки ниже pb учтены.
    """
    cfg, pvt = _case("04_table_table")
    p = [10.75, 11, 12, 13, 16, 18]
    regime = [1, 2, 2, 2, 2, 2]
    p_pa = np.array(p, float) * MPA
    Rs = pvt.Rs_eq(p_pa)
    Rs[1:4] -= 2.0                         # недонасыщенность 2 м³ст/м³ст
    Rs[4:] = 30.0
    hist = _history(p, Rs, regime)
    old = np.abs(rs_core.rs_expected(cfg, pvt, p_pa) - Rs).max()
    assert old == pytest.approx(2.0)       # прежняя проверка «не совпадают»
    rep = _report(cfg, hist, pvt, capsys)
    assert rep["max_abs"] == 0.0
    assert rep["n_supersaturated"] == 0
    assert rep["n_single_below_pb"] == 3


# ── Что проверка обязана ловить ──

def test_supersaturated_single_phase_is_violation(capsys):
    """Ячейка без газа с Rs > Rs_eq(p) — газ растворился сверх равновесия."""
    cfg, pvt = _case("04_table_table")
    p = [10, 12, 16]
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1] += 0.5
    Rs[2] = 30.0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["n_supersaturated"] == 1
    assert rep["max_excess"] == pytest.approx(0.5)


def test_two_phase_mismatch_is_reported(capsys):
    """Ячейка с газом и Rs != Rs_eq(p): задержка выделения или чужой PVT."""
    cfg, pvt = _case("04_table_table")
    p = [10, 12, 16]
    regime = [1, 1, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1] -= 1e-3
    Rs[2] = 30.0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["max_abs"] == pytest.approx(1e-3)
    assert rep["max_rel"] == pytest.approx(1e-3 / 30.0)


def test_tolerance_on_flat_branch(capsys):
    """На табличном PVT при p >= pb Rs_eq = Rs0: шум 1e-12 — не нарушение.

    Нефть без газа с Rs = Rs0 лежит ровно на границе Rs <= Rs_eq(p); без
    допуска шум Ньютона ~1e-13 давал бы ложные «пересыщения».
    """
    cfg, pvt = _case("04_table_table")
    p = [10, 16, 18]
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1:] += 1e-12
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["n_supersaturated"] == 0


def test_supersaturation_within_solver_tolerance_is_accepted(capsys):
    """Пересыщение до rs_switch_tol — состояние, принятое решателем; сверх — нарушение.

    Прототип включает газ в ячейке только при Rs > Rs_eq(p) + rs_switch_tol
    (blackoil.py, _advance_phases): ячейка с меньшим пересыщением остаётся
    однофазной законно. Допуск проверки — numerics.rs_switch_tol конфига, тот
    же, что фабрика передаёт прототипу (DEBT-008); равенство умолчания конфига
    умолчанию прототипа — test_config.py::test_defaults_match_prototype.
    """
    cfg, pvt = _case("04_table_table")
    tol = cfg.numerics.rs_switch_tol
    p = [10, 12, 13]
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1] += 0.5 * tol     # в пределах допуска решателя
    Rs[2] += 2.0 * tol     # сверх допуска: решатель включил бы газ
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["n_supersaturated"] == 1


def test_supersaturation_tolerance_from_config(capsys):
    """Допуск пересыщения — numerics.rs_switch_tol конфига, а не константа модуля (DEBT-008).

    С допуском решателя 1e-4 однофазная ячейка с пересыщением 2e-5 —
    законное состояние; с константой 1e-5 проверка печатала бы нарушение.
    """
    cfg, pvt = _case("04_table_table")
    p = [10, 12, 13]
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[2] += 2e-5                          # сверх умолчания 1e-5
    assert _report(cfg, _history(p, Rs, regime), pvt, capsys)["n_supersaturated"] == 1
    cfg.numerics.rs_switch_tol = 1e-4      # решатель с таким допуском газ не включил бы
    assert _report(cfg, _history(p, Rs, regime), pvt, capsys)["n_supersaturated"] == 0


def test_rs_above_rs0_is_observation_not_violation(capsys):
    """Стендинг, p выше pb(Rs0): Rs0 < Rs < Rs_eq(p) — допустимо.

    Газ, скопившийся у забоя, при росте давления растворяется сверх Rs0.
    Условие Rs <= min(Rs_eq, Rs0) сочло бы это нарушением (вариант 1,
    отклонён); здесь — только счётчик наблюдения.
    """
    cfg, pvt = _case("03_standing_corey")
    Rs0 = cfg.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    p = np.array([0.5, 1.5, 1.5]) * pb / MPA
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(p * MPA)
    assert Rs[1] > Rs0 + 1.0               # предпосылка: у Стендинга есть запас
    Rs[1] = Rs0 + 1.0
    Rs[2] = Rs0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["n_supersaturated"] == 0
    assert rep["n_above_rs0"] == 1


def test_no_two_phase_cells(capsys):
    """Газа нет нигде: мера для ячеек с газом — ноль, Rs_eq на пустом массиве не зовётся."""
    cfg, pvt = _case("04_table_table")
    rep = _report(cfg, _history([16, 18], [30.0, 30.0], [2, 2]), pvt, capsys)
    assert rep["max_abs"] == 0.0
    assert rep["n_two_phase"] == 0


def test_noise_cell_with_solver_flag_is_single_phase(capsys):
    """Ячейка regime == 1 с Sg ~ 1e-14 за изобарой — без газа (замер 04, 04a).

    На таблице без ветвей выше Rs0 растворившийся газ оставляет флаг решателя
    двухфазным при Sg ~ 1e-14 и Rs = Rs_eq(p) = Rs0 (у 04 — ячейка на 2.70 м,
    +40 кПа над pb). Газа нет: в счёт ячеек с газом она не идёт, кружка нет,
    подпись остаётся «фронт». По флагу regime пример с падающим давлением
    получил бы подпись «изобара».
    """
    cfg, pvt = _case("04_table_table")
    p = [8, 10, 12, 14, 16, 18]
    regime = np.array([1, 1, 1, 1, 1, 2])           # ячейка 4 — флаг без газа
    Sg = np.array([0.1, 0.1, 0.1, 0.1, 1e-14, 0.0])
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)        # в ячейке 4 = Rs0 = 30
    Rs[5] = 30.0
    hist = _history(p, Rs, regime, Sg)
    rep = _report(cfg, hist, pvt, capsys)
    assert rep["n_two_phase"] == 4
    assert rep["n_supersaturated"] == 0
    marks, labels = _draw(cfg, pvt, hist)
    np.testing.assert_array_equal(marks[0].get_xdata(), R[:4])
    assert any(lb.startswith("фронт") for lb in labels)


# ── Рисунок rs_profiles.png ──

def test_overlay_marks_only_two_phase_and_front_label():
    """Падающее давление: кружки только в ячейках с газом, линия — «фронт»."""
    cfg, pvt = _case("04_table_table")
    p = [8, 10, 12, 14, 16, 18]
    regime = np.array([1, 1, 1, 1, 2, 2])
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[4:] = 30.0
    marks, labels = _draw(cfg, pvt, _history(p, Rs, regime))
    assert len(marks) == 1
    np.testing.assert_array_equal(marks[0].get_xdata(), R[regime == 1])
    assert any(lb.startswith("фронт") for lb in labels)


def test_overlay_isobar_label_after_repressurization():
    """Восстановление давления: газ у забоя, ниже pb нефть без газа — «изобара».

    Изобара p = pb стоит между 13 и 16 МПа, а граница газа — у первой ячейки:
    называть линию фронтом разгазирования нельзя.
    """
    cfg, pvt = _case("04_table_table")
    p = [10.75, 11, 12, 13, 16, 18]
    regime = np.array([1, 2, 2, 2, 2, 2])
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1:4] -= 2.0
    Rs[4:] = 30.0
    marks, labels = _draw(cfg, pvt, _history(p, Rs, regime))
    np.testing.assert_array_equal(marks[0].get_xdata(), R[regime == 1])
    assert any(lb.startswith("изобара") for lb in labels)
    assert not any(lb.startswith("фронт") for lb in labels)


def test_overlay_without_gas_has_no_marks():
    """Газа нет: кружков нет (пустая линия дала бы пункт легенды без точек)."""
    cfg, pvt = _case("04_table_table")
    marks, _labels = _draw(cfg, pvt, _history([16, 18], [30.0, 30.0], [2, 2]))
    assert marks == []
