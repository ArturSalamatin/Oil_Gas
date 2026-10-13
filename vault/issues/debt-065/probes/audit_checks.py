"""Аудит плана DEBT-065: тесты шагов 2–3 на пакете ветки DEBT-011.

Код плана (isobar_radius, новые front_radius и r_b_interp, новый r_b
замкнутого решения) задан здесь копией — рабочий код не меняется. Проверяется,
что тесты плана исполнимы на API после DEBT-011: SimulationState, dupuit_check
на синтетической истории, create_pvt, Simulator.grid/pvt/relperm.

Запуск (пакет — из worktree DEBT-011, прототип — установленный):
    $env:PYTHONPATH = "<корень>\\.worktrees\\debt-011\\numerical_solver"
    numerical_solver\\.venv\\Scripts\\python -m pytest vault\\issues\\debt-065\\probes\\audit_checks.py -q -p no:cacheprovider
"""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import gpn_multiphase_solver
from gpn_multiphase_solver.diagnostics import rs as rs_core
from gpn_multiphase_solver.diagnostics import two_phase
from gpn_multiphase_solver.diagnostics.closed_form import solve_closed
from gpn_multiphase_solver.factory import SimulatorFactory, create_pvt
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.state import SimulationState

PKG = Path(gpn_multiphase_solver.__file__).resolve().parents[1]
EXAMPLES = PKG / "examples"
MPA = 1e6
PB = 15.0 * MPA
R = np.geomspace(0.1, 45.0, 6)


def test_package_is_from_debt011_worktree():
    """Страж: пакет взят из worktree DEBT-011, а не из основного каталога."""
    assert ".worktrees" in str(PKG), PKG
    assert hasattr(rs_core, "front_radius") and not hasattr(rs_core, "isobar_radius")


def isobar_radius(r, p, pb, R_ext, p_ext):
    """Копия кода шага 1 плана."""
    r_n = np.append(np.asarray(r, float), float(R_ext))
    p_n = np.append(np.asarray(p, float), float(p_ext))
    above = np.flatnonzero(p_n >= pb)
    if above.size == 0:
        return np.nan
    j = int(above[0])
    if j == 0:
        return np.nan
    if j == r_n.size - 1 and not r_n[-2] < r_n[-1]:
        raise ValueError("узел контура")
    w = (pb - p_n[j - 1]) / (p_n[j] - p_n[j - 1])
    return float(np.exp(np.log(r_n[j - 1]) + w * (np.log(r_n[j]) - np.log(r_n[j - 1]))))


def front_radius_plan(config, history, grid, pvt):
    """Копия «После» шага 2.1 плана."""
    _below, pb = rs_core.degassed_cells(config, history, pvt)
    return isobar_radius(grid.r_centers, history.states[-1].p, pb,
                         config.geometry.R_ext, config.initial_conditions.p0)


def _case04():
    cfg = load_config(EXAMPLES / "04_table_table" / "config.json")
    return cfg, create_pvt(cfg)


def _history(p_mpa):
    p = np.asarray(p_mpa, float) * MPA
    gas = p < PB
    st = SimulationState(p=p, Sg=np.where(gas, 0.1, 0.0), Rs=np.full(p.size, 30.0),
                         T=np.full(p.size, 350.0), regime=np.where(gas, 1, 2), t=0.0)
    hr = SimpleNamespace(G_o=np.full(p.size + 1, -1e-5))
    return SimpleNamespace(states=[st], hydro_results=[hr])


@pytest.mark.parametrize("p_mpa", [
    [10, 12, 14, 16, 18, 19.5],
    [10, 11, 12, 13, 14, 14.5],
    [15.5, 16, 17, 18, 19, 19.5],
])
def test_numeric_profile_functions_agree(p_mpa):
    """Тест шага 2: синтетическая история проходит degassing_front (dupuit_check) без ошибок."""
    cfg, pvt = _case04()
    pb = float(pvt.pb(np.array([cfg.initial_conditions.Rs0]))[0])
    assert pb == PB                       # утверждение плана: pb примера 04 — ровно 15 МПа
    hist = _history(p_mpa)
    grid = SimpleNamespace(r_centers=R)
    expected = isobar_radius(R, np.asarray(p_mpa, float) * MPA, pb,
                             cfg.geometry.R_ext, cfg.initial_conditions.p0)
    fr = two_phase.degassing_front(hist, grid, cfg, pvt)   # прежний код: проверяем, что не падает
    r_b_plan = isobar_radius(R, hist.states[-1].p, fr["pb"], cfg.geometry.R_ext,
                             cfg.initial_conditions.p0)      # «После» шага 2.3
    np.testing.assert_equal(front_radius_plan(cfg, hist, grid, pvt), expected)
    np.testing.assert_equal(r_b_plan, expected)
    # Внутри сетки прежние функции дают то же число (побитово)
    if p_mpa[0] < 15 < p_mpa[-1]:
        assert rs_core.front_radius(cfg, hist, grid, pvt) == expected
        assert fr["r_b_interp"] == expected


def test_closed_form_example11():
    """Тест шага 3: API Simulator.grid/pvt/relperm и значение с узлом контура."""
    cfg = load_config(EXAMPLES / "11_degassing_at_boundary" / "config.json")
    sim, _ = SimulatorFactory.from_config(cfg)
    assert sim.relperm is not None
    r = sim.grid.r_centers
    cl = solve_closed(cfg, sim.pvt, sim.relperm, r)
    assert np.all(cl["p"] < cl["pb"])
    r_b = isobar_radius(r, cl["p"], cl["pb"], cfg.geometry.R_ext, cfg.initial_conditions.p0)
    assert r[-1] < r_b < cfg.geometry.R_ext
    assert r_b == pytest.approx(47.7338, rel=1e-4)
    assert cl["r_b"] == pytest.approx(46.9873, abs=5e-5)   # прежнее значение — центр ячейки
