"""DEBT-020, план: тесты шагов 1 и 2 — дословно из плана, до правки кода.

Шаг 1 (test_wellbore_face_phi_plus_not_in_matrix, test_two_cells_rows_by_formulas)
обязан проходить на нынешнем коде. Шаг 2 (test_face_indexed_array) — на
кандидатной compute_conductive_transmissibility из plan_vector_assembly.py.

Запуск (из numerical_solver):
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\debt-020\\probes\\plan_step_tests.py -q -p no:cacheprovider
"""

import sys
from pathlib import Path

import numpy as np
import pytest

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir()
sys.path[:0] = [str(SOLVER), str(SOLVER / "tests"),
                str(Path(__file__).resolve().parent)]

from test_energy import (  # noqa: E402
    LogRadialGrid, TridiagEnergySolver, _make_pvt, _rock,
    R_WELL, R_EXT, H, K_PERM, P0, RS0, T0, T_EXT, DT)
import plan_vector_assembly as pva  # noqa: E402


class TestStep1OnCurrentCode:

    def test_wellbore_face_phi_plus_not_in_matrix(self):
        for N_cells in (1, 2, 5):
            grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
            solver = TridiagEnergySolver(grid, _make_pvt(), _rock())
            props = solver.compute_cell_properties(
                np.full(N_cells, P0), np.zeros(N_cells),
                np.full(N_cells, RS0), np.ones(N_cells),
                np.full(N_cells, T0))
            Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(
                props['lambda_eff'], N_cells)
            Phi_minus = np.linspace(-500.0, -100.0, N_cells + 1)
            z = np.zeros(N_cells)

            def assemble(phi_plus_0):
                Phi_plus = np.zeros(N_cells + 1)
                Phi_plus[0] = phi_plus_0
                return solver.assemble_tridiag(
                    N_cells, DT, np.full(N_cells, T0), T_EXT,
                    props['rho_cp_eff'], Q_T_int, Q_T_ext,
                    Phi_plus, Phi_minus, z, z, z)

            for name, x, y in zip("abcd", assemble(0.0), assemble(500.0)):
                assert np.array_equal(x, y), (
                    f"N = {N_cells}, {name}: Φ⁺ забойной грани вошёл в "
                    f"сборку (ГУ забоя, ssec:bc_disc)")

    def test_two_cells_rows_by_formulas(self):
        N_cells = 2
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        solver = TridiagEnergySolver(grid, _make_pvt(), _rock())
        props = solver.compute_cell_properties(
            np.full(N_cells, P0), np.zeros(N_cells),
            np.full(N_cells, RS0), np.ones(N_cells), np.full(N_cells, T0))
        Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(
            props['lambda_eff'], N_cells)
        Q1, Q2 = Q_T_int[0], Q_T_ext

        Phi_plus = np.array([0.0, 120.0, 70.0])
        Phi_minus = np.array([-300.0, -500.0, -40.0])
        T_old = np.array([T0 - 3.0, T0 + 1.0])
        J_jt = np.array([7.0, -2.0])
        Q_ad = np.array([0.5, -0.1])
        Q_deg = np.array([-0.3, 0.2])

        a, b, c, d = solver.assemble_tridiag(
            N_cells, DT, T_old, T_EXT, props['rho_cp_eff'],
            Q_T_int, Q_T_ext, Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)

        V = grid.volumes
        cap = V * props['rho_cp_eff'] / DT
        assert a[0] == 0.0
        assert c[0] == pytest.approx(-Q1 + Phi_minus[1], rel=1e-12)
        assert b[0] == pytest.approx(cap[0] + Q1 - Phi_minus[1], rel=1e-12)
        assert d[0] == pytest.approx(
            cap[0] * T_old[0] + J_jt[0] + V[0] * (Q_ad[0] + Q_deg[0]),
            rel=1e-12)
        assert a[1] == pytest.approx(-Q1 - Phi_plus[1], rel=1e-12)
        assert c[1] == 0.0
        assert b[1] == pytest.approx(
            cap[1] + Q1 + Q2 + Phi_plus[1] - Phi_minus[2], rel=1e-12)
        assert d[1] == pytest.approx(
            cap[1] * T_old[1] + (Q2 - Phi_minus[2]) * T_EXT
            + J_jt[1] + V[1] * (Q_ad[1] + Q_deg[1]), rel=1e-12)


class TestStep2OnCandidate:

    def test_face_indexed_array(self):
        for N_cells in (1, 5):
            grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
            solver = TridiagEnergySolver(grid, _make_pvt(), _rock())
            lam = np.linspace(0.8, 1.6, N_cells)

            Q_T = pva.new_conductive(solver, lam, N_cells)

            assert Q_T.shape == (N_cells + 1,)
            assert Q_T[0] == 0.0, "забойная грань: ГУ Неймана, Q_T[0] = 0"
            geom_ext = 2.0 * np.pi * grid.h / np.log(
                grid.R_ext / grid.r_centers[-1])
            assert Q_T[N_cells] == pytest.approx(geom_ext * lam[-1], rel=1e-12)
            assert np.all(Q_T[1:N_cells] > 0.0)

    def test_negative_control_phi_plus_0(self):
        """Тест шага 1 ловит сборку, прибавляющую Φ⁺[0] к b[0]."""
        def bad_assemble(self, N, dt, T_old, T_ext, rho_cp_eff, Q_T,
                         Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg):
            a, b, c, d = pva.new_assemble(self, N, dt, T_old, T_ext,
                                          rho_cp_eff, Q_T, Phi_plus,
                                          Phi_minus, J_jt, Q_ad, Q_deg)
            b[0] += Phi_plus[0]
            return a, b, c, d

        grid = LogRadialGrid(R_WELL, R_EXT, H, 5, K_PERM)
        solver = TridiagEnergySolver(grid, _make_pvt(), _rock())
        lam = np.full(5, 1.2)
        Q_T = pva.new_conductive(solver, lam, 5)
        Phi_minus = np.linspace(-500.0, -100.0, 6)
        z = np.zeros(5)
        rc = np.full(5, 2e6)
        outs = []
        for p0 in (0.0, 500.0):
            Phi_plus = np.zeros(6)
            Phi_plus[0] = p0
            outs.append(bad_assemble(solver, 5, DT, np.full(5, T0), T_EXT,
                                     rc, Q_T, Phi_plus, Phi_minus, z, z, z))
        assert not np.array_equal(outs[0][1], outs[1][1])
