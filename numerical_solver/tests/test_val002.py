"""VAL-002: Верификация TridiagEnergySolver на аналитических эталонах.

4 кейса:
  A. Конвекция + теплопроводность (μ_JT=0, L=0) → стационар T = T_ext
  B. Чистый JT (λ ≈ 0) → T(r) = T_ext + μ_JT·(p(r) − p_ext)
  C. Конвекция + JT + теплопроводность (Pe ~ 1) → mesh refinement, порядок ≥ 2
  D. Нестационарная теплопроводность (Q=0) → принцип максимума, энергобаланс

Все кейсы: однофазная нефть (Sg=0), L=0, постоянные свойства.
Эталон: аналитические решения или свойства решения.
"""

import numpy as np
import pytest

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.state import (
    SimulationState, HydroResult, BoundaryConditions,
)
from gpn_multiphase_solver.bc import PressureControl
from gpn_multiphase_solver.fluxes import compute_fluxes
from gpn_multiphase_solver.io.config import RockConfig
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver


# ── Общие параметры (из VAL-001) ────────────────────────────

R_WELL = 0.1
R_EXT = 50.0
H = 10.0
K_PERM = 1e-13
PHI = 0.2

P_EXT = 20e6
P_WF = 15e6
T_EXT = 350.0
RS0 = 50.0

RHO_O_STD = 850.0
RHO_G_STD = 0.85
CP_OIL = 2000.0
CP_GAS = 1000.0


# ── Хелперы (шаг 1 + шаг 6) ────────────────────────────────

def _make_pvt(mu_JT_oil=0.0, mu_JT_gas=0.0, L_degas=0.0):
    return StandingFullPVT(
        rho_o_std=RHO_O_STD, rho_g_std=RHO_G_STD,
        T0=T_EXT, Rs0=RS0, co_undersaturated=0.0,
        c_p_oil=CP_OIL, c_p_gas=CP_GAS,
        mu_JT_oil_val=mu_JT_oil, mu_JT_gas_val=mu_JT_gas,
        L_degas_val=L_degas)


def _rock(lambda_solid=1.5, lambda_oil=0.14, lambda_gas=0.04):
    return RockConfig(
        porosity=PHI, permeability=K_PERM,
        rho_cp_solid=1.25e6, lambda_solid=lambda_solid,
        lambda_oil=lambda_oil, lambda_gas=lambda_gas)


def _zero_hydro(state, N):
    """HydroResult с нулевыми потоками."""
    Z = np.zeros(N + 1)
    return HydroResult(
        state=state, G_o=Z, G_g=Z, G_free_gas=Z,
        Q_o=Z, Q_g=Z, u_o=Z, u_g=Z, m_o=Z, m_g=Z, Gm_o=Z, Gm_g=Z,
        p_wf=state.p[0])   # потока нет: давление на забое = p[0]


def _log_pressure_profile(grid, p_wf, p_ext):
    """Стационарный логарифмический профиль p(r) (Дюпюи)."""
    r = grid.r_centers
    return p_wf + (p_ext - p_wf) * np.log(r / grid.r_well) / np.log(grid.R_ext / grid.r_well)


def _stationary_hydro_result(grid, pvt, relperm, p_wf, p_ext, T0, Rs0):
    """HydroResult со стационарными потоками из формулы Дюпюи.

    Вычисляет p(r) логарифмический, потоки через compute_fluxes.
    """
    N = grid.N
    p = _log_pressure_profile(grid, p_wf, p_ext)
    state = SimulationState(
        p=p, Sg=np.zeros(N), Rs=np.full(N, Rs0),
        T=np.full(N, T0), regime=np.full(N, 2, dtype=int), t=0.0)
    bc = BoundaryConditions(
        well=PressureControl(p_wf), p_ext=p_ext,
        T_ext=T0, Rs_ext=Rs0, Sg_ext=0.0)
    return compute_fluxes(state, grid, pvt, relperm, bc)


def _run_energy_steps(solver, hydro, state_prev, dt, T_ext, n_steps,
                      rtol_converge=None, Rs_ext=None):
    """Прогнать energy solver n_steps шагов, обновляя только T.

    Если rtol_converge задан — остановиться при |T^{n+1} − T^n|/|ΔT| < rtol.
    Возвращает (T_final [N], T_history list[ndarray]).

    Rs_ext — состав притока с контура (DEBT-009). По умолчанию берётся из
    самого состояния: во всех кейсах VAL-002 контур насыщен и Rs однороден.
    """
    T = state_prev.T.copy()
    history = [T.copy()]
    delta_T_scale = max(np.ptp(T), abs(T[0] - T_ext), 1.0)

    if Rs_ext is None:
        Rs_ext = float(state_prev.Rs[-1])
    # Энергетический решатель использует из bc только T_ext и Rs_ext;
    # p_ext и well в его расчёт не входят (работает на замороженных полях)
    bc = BoundaryConditions(
        well=PressureControl(P_WF), p_ext=P_EXT,
        T_ext=T_ext, Rs_ext=Rs_ext, Sg_ext=0.0)

    for _ in range(n_steps):
        # Обновить T в state_prev
        updated = SimulationState(
            p=state_prev.p, Sg=state_prev.Sg, Rs=state_prev.Rs,
            T=T, regime=state_prev.regime, t=state_prev.t)
        T_new = solver.solve(hydro, updated, dt, bc)

        if rtol_converge is not None:
            resid = np.max(np.abs(T_new - T)) / delta_T_scale
            if resid < rtol_converge:
                T = T_new
                history.append(T.copy())
                break

        T = T_new
        history.append(T.copy())

    return T, history


def check_energy_balance(solver, hydro, state_prev, dt, T_ext, T_new):
    """Проверка невязки СЛАУ: max|a·T_{j-1} + b·T_j + c·T_{j+1} − d_j| / max|d_j|.

    ⚠️ Это САМО-невязка, а не независимая проверка правильности схемы:
    a, b, c, d собираются теми же методами решателя, что и в solve.
    Проверяется, что прогонка решила ту систему, которую собрали. При
    согласованной ошибке в коэффициентах невязка останется нулевой.
    Независимую сверку с постановкой даёт tests/test_energy_matrix_examples.py
    (DEBT-016), где эталон строится по problem_statement.tex.
    """
    N = solver._grid.N
    p = hydro.state.p
    Sg = hydro.state.Sg
    Rs = hydro.state.Rs
    So = 1.0 - Sg

    # ГУ контура: нужны для свойств выше по потоку при притоке
    # (_ext_properties, eq:bc_props_ext, DEBT-017). Собираются здесь
    # из тех же констант, что и в фикстурах теста — объект bc до
    # вызывающих не доходит, передаётся только T_ext.
    bc = BoundaryConditions(
        well=PressureControl(P_WF), p_ext=P_EXT,
        T_ext=T_ext, Rs_ext=RS0, Sg_ext=0.0)
    ext = solver._ext_properties(bc)

    props = solver.compute_cell_properties(p, Sg, Rs, So, state_prev.T)
    Phi_plus, Phi_minus, Phi_o, Phi_g = solver.compute_convective_coefficients(
        hydro.Q_o, hydro.Q_g, props['rho_o'], props['rho_g'],
        props['c_p_o'], props['c_p_g'], N, ext)
    Q_T = solver.compute_conductive_transmissibility(props['lambda_eff'], N)
    # p_wf — давление на забойной грани: в адвективной форме JT-вклад
    # этой грани равен μ_JT·Φ⁻·(p[0] − p_wf) и без p_wf не считается
    # (BUG-012). Берётся из HydroResult — тот же источник, что у решателя
    # (FEAT-020).
    p_wf = hydro.p_wf
    J_jt = solver.compute_jt(
        hydro.Q_o, hydro.Q_g, Phi_o, Phi_g,
        props['mu_JT_o'], props['mu_JT_g'], p, N, ext, p_wf)
    Q_ad = solver.compute_adiabatic(
        So, Sg, props['rho_o'], props['rho_g'],
        props['c_p_o'], props['c_p_g'],
        props['mu_JT_o'], props['mu_JT_g'], p, state_prev.p, dt)
    p_old = state_prev.p
    Rs_old = state_prev.Rs
    # Rs_ext = Rs[-1]: контур насыщен, состав притока совпадает с последней
    # ячейкой, поэтому обе ветви контурной грани дают одно значение (DEBT-009)
    Q_deg = solver.compute_degassing(
        So, Sg, Rs, Rs_old, props['Bo'], hydro.G_o, props['L'], dt, N,
        float(Rs[-1]))

    a, b, c, d = solver.assemble_tridiag(
        N, dt, state_prev.T, T_ext,
        props['rho_cp_eff'], Q_T,
        Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)

    # Невязка: a·T_{j-1} + b·T_j + c·T_{j+1} − d_j
    residual = b * T_new - d
    residual[1:] += a[1:] * T_new[:-1]
    residual[:-1] += c[:-1] * T_new[1:]

    return np.max(np.abs(residual)) / np.max(np.abs(d))


# ═══════════════════════════════════════════════════════════
# Шаг 1: тест хелпера стационарных потоков
# ═══════════════════════════════════════════════════════════

class TestStationaryFluxes:
    """Проверка хелпера _stationary_hydro_result."""

    def test_Q_o_times_r_approx_const(self):
        """Q_o · r ~ const на внутренних гранях (стационарный приток).

        Не точно const: Bo(p) и μ_o(p) зависят от давления (Standing),
        mob_o(p) слегка меняется по радиусу. Проверяем порядок величины.
        """
        N = 50
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        pvt = _make_pvt()
        relperm = CoreyRP(S_or=0.0, S_gc=0.0, n_o=2.0, n_g=2.0)
        hydro = _stationary_hydro_result(grid, pvt, relperm, P_WF, P_EXT, T_EXT, RS0)

        Q_inner = hydro.Q_o[1:N]
        r_inner = grid.r_faces[1:N]
        Qr = Q_inner * r_inner
        # При постоянных PVT было бы точно const.
        # Standing: Bo и μ_o слабо зависят от p → Qr меняется, но не более чем в 2 раза
        assert np.all(Qr < 0), "Q_o < 0 (к скважине)"
        ratio = np.max(np.abs(Qr)) / np.min(np.abs(Qr))
        assert ratio < 500, f"Q_o·r разброс слишком велик: ratio={ratio:.1f}"

    def test_Q_o_negative(self):
        """Q_o < 0 на всех гранях (поток к скважине)."""
        N = 20
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        pvt = _make_pvt()
        relperm = CoreyRP(S_or=0.0, S_gc=0.0, n_o=2.0, n_g=2.0)
        hydro = _stationary_hydro_result(grid, pvt, relperm, P_WF, P_EXT, T_EXT, RS0)
        assert np.all(hydro.Q_o <= 0)


# ═══════════════════════════════════════════════════════════
# Кейс D: нестационарная теплопроводность (Q=0)
# ═══════════════════════════════════════════════════════════

class TestCaseD_PureConduction:
    """D. Нестационарная теплопроводность (Q=0).

    Скважина закрыта, IC: T₀=330 К, ГУ: T(R_ext)=350 К.
    Проверка свойств решения (без точной аналитики).
    """

    @pytest.fixture
    def setup(self):
        N = 50
        T0 = 330.0
        dt = 3600.0
        n_steps = 200

        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        pvt = _make_pvt(mu_JT_oil=0.0, L_degas=0.0)
        rock = _rock()
        solver = TridiagEnergySolver(grid, pvt, rock)

        # IC: uniform p (нет потоков), T = T₀
        state = SimulationState(
            p=np.full(N, P_EXT), Sg=np.zeros(N),
            Rs=np.full(N, RS0), T=np.full(N, T0),
            regime=np.full(N, 2, dtype=int), t=0.0)
        hydro = _zero_hydro(state, N)

        T_final, history = _run_energy_steps(
            solver, hydro, state, dt, T_EXT, n_steps)

        return dict(solver=solver, hydro=hydro, state=state,
                    T_final=T_final, history=history,
                    T0=T0, dt=dt, N=N)

    def test_maximum_principle(self, setup):
        """T ∈ [T₀, T_ext] на каждом шаге."""
        for T in setup['history']:
            assert np.all(T >= setup['T0'] - 1e-10)
            assert np.all(T <= T_EXT + 1e-10)

    def test_monotone_warming(self, setup):
        """T(r, t+dt) ≥ T(r, t) при T₀ < T_ext (до машинной точности)."""
        for i in range(1, len(setup['history'])):
            diff = setup['history'][i] - setup['history'][i - 1]
            assert np.all(diff >= -1e-10)

    def test_progress_toward_T_ext(self, setup):
        """Ячейки у контура прогрелись (T[-1] > T₀). Забой прогревается крайне медленно (τ ~ 83 года)."""
        assert setup['T_final'][-1] > setup['T0'] + 0.01

    def test_energy_balance(self, setup):
        """Невязка СЛАУ < 1e-12 на последнем шаге."""
        s = setup
        # Проверяем баланс на последнем шаге
        state_prev = SimulationState(
            p=s['state'].p, Sg=s['state'].Sg, Rs=s['state'].Rs,
            T=s['history'][-2], regime=s['state'].regime, t=0.0)
        resid = check_energy_balance(
            s['solver'], s['hydro'], state_prev, s['dt'], T_EXT, s['T_final'])
        assert resid < 1e-12

    def test_conductive_transmissibility_single_ln(self, setup):
        """Q_T при однородном λ: проверка на двойной ln (BUG-002).

        Стационарный кондуктивный поток через кольцевой слой:
        Q_analyt = 2πhλ·ΔT / ln(R_ext/r_w)
        Если код даёт Q_T = 2πhλ/ln² — ошибка будет заметна.
        """
        s = setup
        grid = s['solver']._grid
        N = grid.N
        # Однородный λ_eff при Sg=0
        rock = _rock()
        lambda_eff_val = (1 - PHI) * rock.lambda_solid + PHI * rock.lambda_oil
        lambda_eff = np.full(N, lambda_eff_val)

        Q_T = s['solver'].compute_conductive_transmissibility(lambda_eff, N)

        # Аналитический Q для потока от центра j к центру j+1:
        # Q = 2πhλ / ln(r_{j+1}/r_j) · ΔT   (один ln)
        # До BUG-002 код вычислял geom · lambda_face = (2πh/ln) · (λ/ln) = 2πhλ/ln²;
        # сейчас — последовательные сопротивления 2πh/(w_L/λ + w_R/λ) = 2πhλ/ln.
        # Сравним: Q_T[1] / (2πhλ/ln(r_c[1]/r_c[0])); грань 1 — между
        # центрами ячеек 0 и 1 (Q_T по номеру грани, DEBT-020)
        r_c = grid.r_centers
        Q_analyt_0 = 2 * np.pi * H * lambda_eff_val / np.log(r_c[1] / r_c[0])
        ratio = Q_T[1] / Q_analyt_0

        # После исправления BUG-002: один ln → ratio ≈ 1
        np.testing.assert_allclose(ratio, 1.0, rtol=0.05,
            err_msg=f"Q_T / Q_analyt = {ratio:.4f}, ожидалось ≈ 1.0")


# ═══════════════════════════════════════════════════════════
# Кейс B: чистый JT (стационар, λ ≈ 0)
# ═══════════════════════════════════════════════════════════

class TestCaseB_PureJT:
    """B. Чистый JT (стационар, λ ≈ 0).

    Аналитический эталон: T(r) = T_ext + μ_JT · (p(r) − p_ext).
    При μ_JT = −3e-7 К/Па, Δp = 5 МПа: ΔT_w = +1.5 К (нагрев).
    """

    MU_JT = -3e-7  # К/Па
    DT_LARGE = 1e7  # с — большой шаг для быстрого стационара
    N_STEPS = 200
    N_CELLS = 50

    @pytest.fixture
    def result(self):
        grid = LogRadialGrid(R_WELL, R_EXT, H, self.N_CELLS, K_PERM)
        pvt = _make_pvt(mu_JT_oil=self.MU_JT)
        relperm = CoreyRP(S_or=0.0, S_gc=0.0, n_o=2.0, n_g=2.0)
        rock = _rock(lambda_solid=0.001, lambda_oil=0.001, lambda_gas=0.001)
        solver = TridiagEnergySolver(grid, pvt, rock)

        # Стационарные потоки
        hydro = _stationary_hydro_result(grid, pvt, relperm, P_WF, P_EXT, T_EXT, RS0)

        # IC: T = T_ext (uniform)
        state = SimulationState(
            p=hydro.state.p, Sg=hydro.state.Sg, Rs=hydro.state.Rs,
            T=np.full(self.N_CELLS, T_EXT), regime=hydro.state.regime, t=0.0)

        T_final, history = _run_energy_steps(
            solver, hydro, state, self.DT_LARGE, T_EXT, self.N_STEPS,
            rtol_converge=1e-6)

        # Аналитика
        p_profile = _log_pressure_profile(grid, P_WF, P_EXT)
        T_exact = T_EXT + self.MU_JT * (p_profile - P_EXT)

        return dict(T_final=T_final, T_exact=T_exact, grid=grid,
                    solver=solver, hydro=hydro, state=state, history=history)

    def test_T_profile_matches_analytical(self, result):
        """max|T_num − T_exact| / |ΔT_w| < 1%."""
        delta_Tw = abs(self.MU_JT * (P_WF - P_EXT))  # 1.5 К
        err = np.max(np.abs(result['T_final'] - result['T_exact']))
        assert err / delta_Tw < 0.01, f"err={err:.6f} К, ΔT_w={delta_Tw:.2f} К"

    def test_wellbore_temperature(self, result):
        """T(r_w) ≈ T_ext + μ_JT·(p_wf − p_ext)."""
        T_w_exact = T_EXT + self.MU_JT * (P_WF - P_EXT)
        np.testing.assert_allclose(result['T_final'][0], T_w_exact, rtol=0.01)

    def test_T_monotone_with_radius(self, result):
        """T(r) монотонна. При μ_JT < 0: T убывает от r_w к R_ext."""
        dT = np.diff(result['T_final'])
        # μ_JT < 0, dp/dr > 0 → dT/dr = μ_JT·dp/dr < 0 → T убывает
        assert np.all(dT <= 1e-10)

    def test_energy_balance(self, result):
        """Невязка СЛАУ < 1e-12."""
        r = result
        state_prev = SimulationState(
            p=r['state'].p, Sg=r['state'].Sg, Rs=r['state'].Rs,
            T=r['history'][-2], regime=r['state'].regime, t=0.0)
        resid = check_energy_balance(
            r['solver'], r['hydro'], state_prev, self.DT_LARGE, T_EXT, r['T_final'])
        assert resid < 1e-12


# ═══════════════════════════════════════════════════════════
# Кейс C: mesh refinement (конвекция + JT + теплопроводность)
# ═══════════════════════════════════════════════════════════

class TestCaseC_MeshConvergence:
    """C. Конвекция + JT + теплопроводность (Pe ~ 1): сходимость по сетке.

    Две независимые проверки:
      - монотонное убывание ошибки с N — против эталона на мелкой сетке;
      - порядок сходимости ≥ 1 — методом Рунге, БЕЗ эталона.

    Схема против потока на логарифмической сетке даёт первый порядок,
    не второй.
    """

    MU_JT = -3e-7
    DT_LARGE = 1e7
    N_STEPS = 300  # больше, чтобы грубые сетки тоже сходились
    N_LIST = [10, 20, 50, 100]
    N_REF = 400

    # Тройка сеток для метода Рунге: отношение строго 2, иначе формула
    # p = log2(Δ1/Δ2) неприменима. На логарифмической сетке шаг по ln(r)
    # равен ln(R_ext/r_well)/N, поэтому удвоение N — ровно половинный h.
    N_RUNGE = (50, 100, 200)

    def _run_to_stationary(self, N):
        """Прогнать energy solver до стационара с заданным N."""
        grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
        pvt = _make_pvt(mu_JT_oil=self.MU_JT)
        relperm = CoreyRP(S_or=0.0, S_gc=0.0, n_o=2.0, n_g=2.0)
        rock = _rock()  # типичные λ: Pe ~ 1
        solver = TridiagEnergySolver(grid, pvt, rock)

        hydro = _stationary_hydro_result(grid, pvt, relperm, P_WF, P_EXT, T_EXT, RS0)
        state = SimulationState(
            p=hydro.state.p, Sg=hydro.state.Sg, Rs=hydro.state.Rs,
            T=np.full(N, T_EXT), regime=hydro.state.regime, t=0.0)

        T_final, _ = _run_energy_steps(
            solver, hydro, state, self.DT_LARGE, T_EXT, self.N_STEPS,
            rtol_converge=1e-8)

        return grid.r_centers, T_final

    @pytest.fixture(scope="class")
    def solutions(self):
        """Решения на всех сетках: N_LIST + эталон + тройка для Рунге.

        Списки пересекаются (50, 100 есть в обоих), поэтому объединяем
        через set — иначе те же сетки считались бы дважды.
        """
        results = {}
        for N in sorted(set(self.N_LIST) | {self.N_REF} | set(self.N_RUNGE)):
            r, T = self._run_to_stationary(N)
            results[N] = (r, T)
        return results

    def test_error_decreases(self, solutions):
        """Ошибка монотонно убывает с N.

        Здесь эталон на N_REF уместен, в отличие от замера порядка
        (см. test_convergence_order_ge_1): паразитный вклад погрешности
        эталона одинаков для всех N и потому не нарушает монотонности —
        искажается величина ошибки, но не знак её изменения.
        """
        r_ref, T_ref = solutions[self.N_REF]
        errors = []
        for N in self.N_LIST:
            r_N, T_N = solutions[N]
            T_ref_interp = np.interp(r_N, r_ref, T_ref)
            err = np.sqrt(np.mean((T_N - T_ref_interp) ** 2))
            errors.append(err)
        for i in range(1, len(errors)):
            assert errors[i] < errors[i - 1], (
                f"Ошибка не убывает: N={self.N_LIST[i-1]}→{self.N_LIST[i]}, "
                f"err={errors[i-1]:.2e}→{errors[i]:.2e}")

    def test_convergence_order_ge_1(self, solutions):
        """Порядок сходимости ≥ 1 методом Рунге. Схема против потока даёт ~1, не 2.

        Метод. Разложение ошибки T_h = T* + C·h^p + O(h^{p+1}) для трёх
        сеток h, h/2, h/4 даёт для отношения последовательных приращений:
            (T_h − T_{h/2}) / (T_{h/2} − T_{h/4}) = 2^p,
        поскольку T*, C и множитель (1 − 2^{−p}) сокращаются. Отсюда
            p = log2( |T_h − T_{h/2}| / |T_{h/2} − T_{h/4}| ).
        Точное решение знать НЕ требуется — это ключевое свойство.

        Почему не против эталона (прежняя редакция теста). Ошибка
        относительно решения на N_REF содержит паразитный вклад —
        погрешность самого эталона:
            ‖T_N − T_ref‖ ≈ ‖T_N − T*‖ − ‖T_ref − T*‖.
        Пока второе слагаемое мало, наклон измеряется верно. После
        DEBT-017 ошибка схемы упала в 27 раз (RMS 4.8e-3 → 1.7e-4) и стала
        сопоставима с погрешностью эталона: при N = 100 ошибка 6.7e-3
        против 9.4e-4 у N_REF = 400 — всего в 7 раз больше. Наклон
        исказился, тест давал 0.85 при фактическом первом порядке.
        Замер по Рунге на том же коде даёт 1.081 / 1.043 / 1.022 / 1.011
        на тройках 25-100 / 50-200 / 100-400 / 200-800: монотонный выход
        на p = 1 сверху, как и положено схеме первого порядка.

        Сравнивается T на забое (ячейка 0): после DEBT-017 там
        сосредоточено 100 % остаточной ошибки — зона максимального
        градиента dp/dr на логарифмической сетке. Норму по всей сетке
        методом Рунге взять нельзя: при удвоении N узлы грубой сетки не
        попадают в узлы мелкой, а интерполяция вернула бы свою ошибку.

        Что этот тест ловит, а что нет (проверено инъекциями ошибок).
        Ловит появление в решении члена меньшего порядка: добавка
        B·sqrt(h) к T даёт измеренный p = 0.497 при B = 3 (аналитически
        для T_h = T* + A·h + B·sqrt(h) порядок падает как 0.965 / 0.786 /
        0.559 при B = 0.03 / 0.3 / 3 и A = 1). НЕ ловит ошибку в значении
        коэффициента: линейное расстояние вместо логарифмического в Q_T
        меняет решение, но оставляет p = 1.04 — схема по-прежнему первого
        порядка, просто сходится к неверному пределу. Это не пробел:
        такие ошибки — предмет tests/test_energy_matrix_examples.py
        (DEBT-016), и ту же инъекцию он поймал.

        Отдельно: прогон идёт ДО стационара, поэтому cap = V·(ρcp)/dt
        выпадает из уравнения (T^{n+1} = T^n) и возмущения в нём на
        результат не влияют — проверять через cap здесь бессмысленно.
        """
        N1, N2, N3 = self.N_RUNGE
        T_a, T_b, T_c = (solutions[N][1][0] for N in self.N_RUNGE)

        d1 = abs(T_a - T_b)   # приращение h → h/2
        d2 = abs(T_b - T_c)   # приращение h/2 → h/4

        # Вырождение: если приращения на уровне машинной точности, сетки
        # уже неразличимы и порядок не определён — это не успех теста
        assert d2 > 1e-12, (
            f"приращение N={N2}→{N3} вырождено ({d2:.2e}): "
            f"измерять порядок нечем")

        order = np.log(d1 / d2) / np.log(2.0)
        assert order >= 1.0, (
            f"Порядок сходимости по Рунге {order:.3f} < 1.0 "
            f"(T[0]: {T_a:.8f}, {T_b:.8f}, {T_c:.8f} при "
            f"N = {N1}, {N2}, {N3})")

    def test_T_bounded(self, solutions):
        """T в пределах [T_ext + μ_JT·Δp, T_ext] при стационаре (или наоборот)."""
        T_w_jt = T_EXT + self.MU_JT * (P_WF - P_EXT)  # при μ_JT < 0: > T_ext
        T_lo = min(T_EXT, T_w_jt) - 0.1
        T_hi = max(T_EXT, T_w_jt) + 0.1
        for N in self.N_LIST:
            _, T_N = solutions[N]
            assert np.all(T_N >= T_lo), f"N={N}: min(T)={T_N.min():.4f} < {T_lo:.4f}"
            assert np.all(T_N <= T_hi), f"N={N}: max(T)={T_N.max():.4f} > {T_hi:.4f}"


# ═══════════════════════════════════════════════════════════
# Кейс A: конвекция + теплопроводность (без JT)
# ═══════════════════════════════════════════════════════════

class TestCaseA_ConvectionConduction:
    """A. Конвекция + теплопроводность (μ_JT=0, L=0).

    Стационар: T → T_ext (тривиальный, без источников).
    Проверка: направление сходимости, принцип максимума.
    """

    N_CELLS = 50
    DT_LARGE = 1e7
    N_STEPS = 200
    T0 = 330.0

    @pytest.fixture
    def result(self):
        grid = LogRadialGrid(R_WELL, R_EXT, H, self.N_CELLS, K_PERM)
        pvt = _make_pvt(mu_JT_oil=0.0)
        relperm = CoreyRP(S_or=0.0, S_gc=0.0, n_o=2.0, n_g=2.0)
        rock = _rock()
        solver = TridiagEnergySolver(grid, pvt, rock)

        hydro = _stationary_hydro_result(grid, pvt, relperm, P_WF, P_EXT, T_EXT, RS0)
        state = SimulationState(
            p=hydro.state.p, Sg=hydro.state.Sg, Rs=hydro.state.Rs,
            T=np.full(self.N_CELLS, self.T0), regime=hydro.state.regime, t=0.0)

        T_final, history = _run_energy_steps(
            solver, hydro, state, self.DT_LARGE, T_EXT, self.N_STEPS)

        return dict(T_final=T_final, history=history,
                    solver=solver, hydro=hydro, state=state)

    def test_converges_toward_T_ext(self, result):
        """После прогона max|T − T_ext| уменьшилось."""
        err_init = np.max(np.abs(result['history'][0] - T_EXT))
        err_final = np.max(np.abs(result['T_final'] - T_EXT))
        assert err_final < err_init

    def test_maximum_principle(self, result):
        """T ∈ [T₀, T_ext] на каждом шаге."""
        for T in result['history']:
            assert np.all(T >= self.T0 - 1e-10)
            assert np.all(T <= T_EXT + 1e-10)

    def test_last_cell_near_T_ext(self, result):
        """T[N-1] ≈ T_ext (ячейка у контура получает T_ext)."""
        assert result['T_final'][-1] > 0.5 * (self.T0 + T_EXT)

    def test_energy_balance(self, result):
        """Невязка энергобаланса < 1e-10."""
        r = result
        state_prev = SimulationState(
            p=r['state'].p, Sg=r['state'].Sg, Rs=r['state'].Rs,
            T=r['history'][-2], regime=r['state'].regime, t=0.0)
        resid = check_energy_balance(
            r['solver'], r['hydro'], state_prev, self.DT_LARGE, T_EXT, r['T_final'])
        assert resid < 1e-10
