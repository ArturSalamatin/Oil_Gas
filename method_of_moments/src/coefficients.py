"""Коэффициенты ODE метода моментов — §5 moments_method.tex."""

import dataclasses

import numpy as np
from scipy.integrate import quad


@dataclasses.dataclass
class OdeState:
    """Текущее состояние ODE-системы метода моментов."""

    r_b: float
    Sg_w: float
    dT_w: float
    p_wf: float
    dp_wf_dt: float = 0.0


# ─── Замораживание PVT (§5.4) ──────────────────────────────────────


def frozen_pvt_zone1(p_wf, pb_star, T_0, dT_w, Sg_w):
    """Средние PVT-параметры зоны разгазирования. §5.4 moments_method.tex."""
    p_bar = 0.5 * (p_wf + pb_star)
    T_bar = T_0 - dT_w
    Sg_bar = 0.5 * Sg_w
    return p_bar, T_bar, Sg_bar


def frozen_pvt_zone2(pb_star, p_0, T_0):
    """Средние PVT-параметры однофазной зоны. §5.4 moments_method.tex."""
    p_bar = 0.5 * (pb_star + p_0)
    T_bar = T_0
    Sg_bar = 0.0
    return p_bar, T_bar, Sg_bar


# ─── Производная dp/dr_b (числ. конечная разность) ─────────────────


def _pressure_at(p_profile, r, r_b, fluid, temp_profile, dT_w):
    """p(r) при заданном r_b — с пересчётом pb_star и gamma."""
    pbs = p_profile.pb_star(r_b, dT_w, fluid, temp_profile)
    gam = p_profile.gamma(r_b, pbs)
    return p_profile(r, r_b, pbs, gam)


def dp_drb_numerical(p_profile, r, r_b, fluid, temp_profile, dT_w,
                     dr_b_rel=1e-5):
    """∂p/∂r_b центральной конечной разностью. §5.4.1 moments_method.tex."""
    dr = r_b * dr_b_rel
    p_plus = _pressure_at(p_profile, r, r_b + dr, fluid, temp_profile, dT_w)
    p_minus = _pressure_at(p_profile, r, r_b - dr, fluid, temp_profile, dT_w)
    return (p_plus - p_minus) / (2.0 * dr)


def dp_dpwf_numerical(p_profile, r, r_b, fluid, temp_profile, dT_w,
                      dp_wf_rel=1e-5):
    """∂p/∂p_wf центральной конечной разностью."""
    dp = p_profile.p_wf * dp_wf_rel
    p_wf_orig = p_profile.p_wf

    p_profile.p_wf = p_wf_orig + dp
    p_plus = _pressure_at(p_profile, r, r_b, fluid, temp_profile, dT_w)

    p_profile.p_wf = p_wf_orig - dp
    p_minus = _pressure_at(p_profile, r, r_b, fluid, temp_profile, dT_w)

    p_profile.p_wf = p_wf_orig
    return (p_plus - p_minus) / (2.0 * dp)


# ─── A₁₁: ∫r·Cp·∂p/∂r_b dr (eq:A11) ──────────────────────────────


def oil_A11(fluid, rock, p_profile, t_profile, state):
    """Коэффициент A₁₁ при ṙ_b в уравнении массы нефти. Ур. (eq:A11) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    phi = rock["phi"]
    cr = rock["c_r"]
    k = rock["k"]

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)

    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, state.Sg_w)
    Cp1 = fluid.Cp(p1, T1, Sg1, phi, cr)

    p2, T2, Sg2 = frozen_pvt_zone2(pbs, p_profile.p_0, t_profile.T_0)
    Cp2 = fluid.Cp(p2, T2, Sg2, phi, cr)

    def integrand_zone1(r):
        dp = dp_drb_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
        return r * Cp1 * dp

    def integrand_zone2(r):
        dp = dp_drb_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
        return r * Cp2 * dp

    r_w = p_profile.r_w
    R_ext = p_profile.R_ext

    I1, _ = quad(integrand_zone1, r_w, r_b)
    I2, _ = quad(integrand_zone2, r_b, R_ext)
    return I1 + I2


# ─── A₁₃: −∫r·CT·Ψ(ζ) dr (eq:A13) ────────────────────────────────


def oil_A13(fluid, rock, p_profile, t_profile, state):
    """Коэффициент A₁₃ при Δ̇T_w в уравнении массы нефти. Ур. (eq:A13) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    phi = rock["phi"]

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)

    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, state.Sg_w)
    CT1 = fluid.CT(p1, T1, Sg1, phi)

    p2, T2, Sg2 = frozen_pvt_zone2(pbs, p_profile.p_0, t_profile.T_0)
    CT2 = fluid.CT(p2, T2, Sg2, phi)

    def integrand_zone1(r):
        zeta = t_profile.zeta(r)
        return r * CT1 * t_profile.Psi(zeta)

    def integrand_zone2(r):
        zeta = t_profile.zeta(r)
        return r * CT2 * t_profile.Psi(zeta)

    r_w = p_profile.r_w
    R_ext = p_profile.R_ext

    I1, _ = quad(integrand_zone1, r_w, r_b)
    I2, _ = quad(integrand_zone2, r_b, R_ext)
    return -(I1 + I2)


# ─── F₁: граничные потоки + Q_quad − I_pwf (eq:F1) ────────────────


def oil_F1(fluid, rock, p_profile, t_profile, s_profile, state):
    """Правая часть F₁ уравнения массы нефти. Ур. (eq:F1) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    phi = rock["phi"]
    cr = rock["c_r"]
    k = rock["k"]

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    gam = p_profile.gamma(r_b, pbs)

    # --- граничные потоки [rΛ dp/dr] ---
    R_ext = p_profile.R_ext
    r_w = p_profile.r_w

    Lambda_ext = fluid.Lambda(p_profile.p_0, t_profile.T_0, 0.0, k)
    dp_dr_ext = p_profile.dp_dr(R_ext, r_b, pbs, gam)
    flux_ext = R_ext * Lambda_ext * dp_dr_ext

    T_w = t_profile(r_w, dT_w)
    Lambda_w = fluid.Lambda(p_profile.p_wf, T_w, Sg_w, k)
    if gam >= 1.0:
        dp_dr_w = p_profile.dp_dr(r_w, r_b, pbs, gam)
        flux_w = r_w * Lambda_w * dp_dr_w
    else:
        eps_r = r_w * 1e-3
        dp_dr_w = p_profile.dp_dr(r_w + eps_r, r_b, pbs, gam)
        flux_w = (r_w + eps_r) * Lambda_w * dp_dr_w

    boundary_flux = flux_ext - flux_w

    # --- Q_quad: ∫rw..rb r·(λo/Bo)·(dRs/dp·dp/dr + dRs/dT·dT/dr)·dp/dr dr ---
    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, Sg_w)
    mob_o_Bo_1 = fluid.mobility_o_over_Bo(p1, T1, Sg1, k)
    dRs_dp_1 = fluid.dRs_dp(p1, T1)
    dRs_dT_1 = fluid.dRs_dT(p1, T1)

    def Q_quad_integrand(r):
        dp_dr_val = p_profile.dp_dr(r, r_b, pbs, gam)
        dT_dr_val = t_profile.dT_dr(r, dT_w)
        return r * mob_o_Bo_1 * (dRs_dp_1 * dp_dr_val + dRs_dT_1 * dT_dr_val) * dp_dr_val

    if gam > 0.5:
        Q_quad, _ = quad(Q_quad_integrand, r_w, r_b)
    else:
        Q_quad, _ = quad(Q_quad_integrand, r_w, r_b, points=[r_w + r_w * 1e-6])

    # --- I_pwf: ∫r·Cp·(dp/dp_wf)·dp_wf/dt dr ---
    I_pwf = 0.0
    if state.dp_wf_dt != 0.0:
        p2, T2, Sg2 = frozen_pvt_zone2(pbs, p_profile.p_0, t_profile.T_0)
        Cp1 = fluid.Cp(p1, T1, Sg1, phi, cr)
        Cp2 = fluid.Cp(p2, T2, Sg2, phi, cr)

        def I_pwf_integrand_z1(r):
            dp = dp_dpwf_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
            return r * Cp1 * dp

        def I_pwf_integrand_z2(r):
            dp = dp_dpwf_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
            return r * Cp2 * dp

        i1, _ = quad(I_pwf_integrand_z1, r_w, r_b)
        i2, _ = quad(I_pwf_integrand_z2, r_b, R_ext)
        I_pwf = (i1 + i2) * state.dp_wf_dt

    return boundary_flux + Q_quad - I_pwf


# ─── A₂₂: ∫r·(1−η^β) dr (eq:A22) ─────────────────────────────────


def gas_A22(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₂₂ при Ṡg,w в уравнении массы газа. Ур. (eq:A22) moments_method.tex."""
    r_b = state.r_b
    r_w = s_profile.r_w
    beta = s_profile.beta

    def integrand(r):
        eta = s_profile.eta(r, r_b)
        return r * (1.0 - eta ** beta)

    I, _ = quad(integrand, r_w, r_b)
    return I


# ─── A₂₁: Sg·β/(rb·Lb)·∫r·η^β dr − ∫r·So·(cr+co_sat)·∂p/∂rb dr ─


def gas_A21(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₂₁ при ṙ_b в уравнении массы газа. Ур. (eq:A21) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    r_w = p_profile.r_w
    cr = rock["c_r"]
    beta = s_profile.beta
    L_b = np.log(r_b / r_w)

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0,
                                    dT_w, Sg_w)
    So1 = 1.0 - Sg1
    co_sat_1 = fluid.co_sat(p1, T1)

    def integrand_eta(r):
        eta = s_profile.eta(r, r_b)
        return r * eta ** beta

    I_eta, _ = quad(integrand_eta, r_w, r_b)

    def integrand_pressure(r):
        dp = dp_drb_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
        return r * So1 * (cr + co_sat_1) * dp

    I_pressure, _ = quad(integrand_pressure, r_w, r_b)

    return Sg_w * beta / (r_b * L_b) * I_eta - I_pressure


# ─── A₂₃: −∫r·So·β_o_sat·Ψ dr (eq:A23) ──────────────────────────


def gas_A23(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₂₃ при Δ̇T_w в уравнении массы газа. Ур. (eq:A23) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    r_w = p_profile.r_w

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0,
                                    dT_w, Sg_w)
    So1 = 1.0 - Sg1
    beta_o_sat_1 = fluid.beta_o_sat(p1, T1)

    def integrand(r):
        zeta = t_profile.zeta(r)
        return r * So1 * beta_o_sat_1 * t_profile.Psi(zeta)

    I, _ = quad(integrand, r_w, r_b)
    return -I


# ─── F₂: −(Bo/φ)·[r·λo/Bo·dp/dr] + I_pwf^(2) (eq:F2) ───────────


def gas_F2(fluid, rock, p_profile, t_profile, s_profile, state):
    """Правая часть F₂ уравнения массы газа. Ур. (eq:F2) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    r_w = p_profile.r_w
    phi = rock["phi"]
    cr = rock["c_r"]
    k = rock["k"]

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    gam = p_profile.gamma(r_b, pbs)

    T_b = t_profile(r_b, dT_w)
    mob_o_Bo_b = fluid.mobility_o_over_Bo(pbs, T_b, 0.0, k)
    dp_dr_b = p_profile.dp_dr(r_b, r_b, pbs, gam)
    flux_rb = r_b * mob_o_Bo_b * dp_dr_b

    T_w = t_profile(r_w, dT_w)
    mob_o_Bo_w = fluid.mobility_o_over_Bo(p_profile.p_wf, T_w, Sg_w, k)
    if gam >= 1.0:
        dp_dr_w = p_profile.dp_dr(r_w, r_b, pbs, gam)
        flux_rw = r_w * mob_o_Bo_w * dp_dr_w
    else:
        eps_r = r_w * 1e-3
        dp_dr_w = p_profile.dp_dr(r_w + eps_r, r_b, pbs, gam)
        flux_rw = (r_w + eps_r) * mob_o_Bo_w * dp_dr_w

    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0,
                                    dT_w, Sg_w)
    Bo_frozen = fluid.Bo(p1, T1)

    boundary = -(Bo_frozen / phi) * (flux_rb - flux_rw)

    I_pwf = 0.0
    if state.dp_wf_dt != 0.0:
        So1 = 1.0 - Sg1
        co_sat_1 = fluid.co_sat(p1, T1)

        def integrand_pwf(r):
            dp = dp_dpwf_numerical(p_profile, r, r_b, fluid, t_profile,
                                   dT_w)
            return r * So1 * (cr + co_sat_1) * dp

        i, _ = quad(integrand_pwf, r_w, r_b)
        I_pwf = i * state.dp_wf_dt

    return boundary + I_pwf
