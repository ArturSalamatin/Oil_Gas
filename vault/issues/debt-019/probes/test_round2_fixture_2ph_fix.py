"""Аудит DEBT-019, раунд 2: проверка фикса шага 3а (bc_2ph с p_wf = 6 МПа).

Воспроизводит фикстуры state_2ph / grid_2ph / pvt / relperm из
tests/test_fluxes.py, но с p_wf = 6 МПа < p[0] = 8 МПа, и прогоняет те же
проверки, что TestTwoPhaseAllFields и TestTwoPhaseConcreteValues, при
включённой имитации запрета (dp_w > 0 → ValueError).

Запуск из каталога numerical_solver:
    $env:PYTHONPATH = "..\\vault\\issues\\debt-019\\probes"
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\debt-019\\probes\\test_round2_fixture_2ph_fix.py -q -p round2_guard_plugin
"""

import sys
from pathlib import Path

import numpy as np
import pytest

_SOLVER_ROOT = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(_SOLVER_ROOT / "tests"))
sys.path.insert(0, str(_SOLVER_ROOT))

import test_fluxes as tf                                            # noqa: E402
from gpn_multiphase_solver import fluxes as fl                      # noqa: E402
from gpn_multiphase_solver.bc import PressureControl                # noqa: E402
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions  # noqa: E402

P_WF_2PH = 6e6


def _setup():
    pvt = tf.StandingFullPVT(rho_o_std=tf.RHO_O_STD, rho_g_std=tf.RHO_G_STD,
                             T0=tf.T0, Rs0=tf.RS0, co_undersaturated=0.0)
    rp = tf.CoreyRP(S_or=tf.S_OR, S_gc=tf.S_GC, n_o=2.0, n_g=2.0,
                    kro_max=1.0, krg_max=0.8)
    grid = tf.LogRadialGrid(r_well=tf.R_WELL, R_ext=tf.R_EXT, h=tf.H,
                            N=tf.N_2PH, k=tf.K_PERM)
    p = np.array([8e6, 10e6, 13e6, 16e6, 19e6])
    Rs = pvt.Rs_eq(p)
    Rs[4] = tf.RS0
    state = SimulationState(p=p, Sg=np.array([0.3, 0.2, 0.1, 0.05, 0.0]), Rs=Rs,
                            T=np.full(tf.N_2PH, tf.T0),
                            regime=np.array([1, 1, 1, 1, 2], dtype=int), t=0.0)
    bc = BoundaryConditions(well=PressureControl(P_WF_2PH), p_ext=tf.P_EXT,
                            T_ext=tf.T0, Rs_ext=tf.RS0, Sg_ext=0.0)
    return pvt, rp, grid, state, bc


def test_all_fields_match_reference_with_guard():
    pvt, rp, grid, state, bc = _setup()
    # fl.compute_fluxes — подменён плагином, если он загружен
    res = fl.compute_fluxes(state, grid, pvt, rp, bc)
    assert res.G_o[0] < 0.0          # поток через забой к скважине
    for f in range(tf.N_2PH + 1):
        ref = tf._compute_reference_face(pvt, rp, grid, state, bc, f)
        for field in tf.TestTwoPhaseAllFields.FIELDS:
            assert getattr(res, field)[f] == pytest.approx(
                ref[field], rel=1e-12, abs=1e-30), (field, f)


def test_face_1_values_unchanged():
    # Значения TestTwoPhaseConcreteValues (грань 1) от p_wf не зависят
    pvt, rp, grid, state, bc = _setup()
    res = fl.compute_fluxes(state, grid, pvt, rp, bc)
    assert res.G_o[1] == pytest.approx(-0.006019771615013, rel=1e-8)
    assert res.G_g[1] == pytest.approx(-2.118667745913, rel=1e-8)
    assert res.m_g[1] == pytest.approx(-1.526494503140, rel=1e-8)


def test_guard_loaded():
    # Убедиться, что проба действительно идёт с имитацией запрета
    assert fl.compute_fluxes.__name__ == "_guarded_compute_fluxes"
