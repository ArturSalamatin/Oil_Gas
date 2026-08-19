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
    beta: float = 2.0


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

    lower = r_w + r_w * 1e-3
    Q_quad, _ = quad(Q_quad_integrand, lower, r_b)

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
    beta = state.beta

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
    beta = state.beta
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


# ─── A_{2,β}: −Sg_w·∫r·η^β·ln(η)·dr (eq:A2beta) ─────────────────


def gas_A2beta(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A_{2,β} при β̇ во 2-м уравнении. Ур. (eq:A2beta) moments_method.tex."""
    r_b = state.r_b
    Sg_w = state.Sg_w
    r_w = s_profile.r_w
    beta = state.beta

    def integrand(r):
        eta = s_profile.eta(r, r_b)
        if eta <= 0.0:
            return 0.0
        return r * eta**beta * np.log(eta)

    I, _ = quad(integrand, r_w, r_b)
    return -Sg_w * I


# ─── A₄₁: Sg·β/(rb·Lb)·∫r·η^{2β}·dr − ∫r·η^β·So·(cr+co)·∂p/∂rb dr (eq:A41)


def gas_A41(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₄₁ при ṙ_b в 4-м уравнении. Ур. (eq:A41) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    r_w = p_profile.r_w
    cr = rock["c_r"]
    beta = state.beta
    L_b = np.log(r_b / r_w)

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0,
                                    dT_w, Sg_w)
    So1 = 1.0 - Sg1
    co_sat_1 = fluid.co_sat(p1, T1)

    def integrand_eta(r):
        eta = s_profile.eta(r, r_b)
        return r * eta ** (2.0 * beta)

    I_eta, _ = quad(integrand_eta, r_w, r_b)

    def integrand_pressure(r):
        eta = s_profile.eta(r, r_b)
        dp = dp_drb_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
        return r * eta**beta * So1 * (cr + co_sat_1) * dp

    I_pressure, _ = quad(integrand_pressure, r_w, r_b)

    return Sg_w * beta / (r_b * L_b) * I_eta - I_pressure


# ─── A₄₂: ∫r·η^β·(1−η^β)·dr (eq:A42) ───────────────────────────


def gas_A42(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₄₂ при Ṡg,w в 4-м уравнении. Ур. (eq:A42) moments_method.tex."""
    r_b = state.r_b
    r_w = s_profile.r_w
    beta = state.beta

    def integrand(r):
        eta = s_profile.eta(r, r_b)
        return r * eta**beta * (1.0 - eta**beta)

    I, _ = quad(integrand, r_w, r_b)
    return I


# ─── A₄₃: −Sg_w·∫r·η^{2β}·ln(η)·dr (eq:A43) ───────────────────


def gas_A43(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₄₃ при β̇ в 4-м уравнении. Ур. (eq:A43) moments_method.tex."""
    r_b = state.r_b
    Sg_w = state.Sg_w
    r_w = s_profile.r_w
    beta = state.beta

    def integrand(r):
        eta = s_profile.eta(r, r_b)
        if eta <= 0.0:
            return 0.0
        return r * eta ** (2.0 * beta) * np.log(eta)

    I, _ = quad(integrand, r_w, r_b)
    return -Sg_w * I


# ─── A₄₄: −∫r·η^β·So·βo_sat·Ψ(ζ)·dr (eq:A44) ─────────────────


def gas_A44(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₄₄ при ΔṪ_w в 4-м уравнении. Ур. (eq:A44) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    r_w = p_profile.r_w
    beta = state.beta

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0,
                                    dT_w, Sg_w)
    So1 = 1.0 - Sg1
    beta_o_sat_1 = fluid.beta_o_sat(p1, T1)

    def integrand(r):
        eta = s_profile.eta(r, r_b)
        zeta = t_profile.zeta(r)
        return r * eta**beta * So1 * beta_o_sat_1 * t_profile.Psi(zeta)

    I, _ = quad(integrand, r_w, r_b)
    return -I


# ─── F₄: −(Bo/φ)·r·(λo/Bo)·p'|_{rb} + F₄^(V) + I_pwf^(4) (eq:F4)


def gas_F4(fluid, rock, p_profile, t_profile, s_profile, state):
    """Правая часть F₄ четвёртого уравнения. Ур. (eq:F4) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    r_w = p_profile.r_w
    phi = rock["phi"]
    k = rock["k"]
    beta = state.beta
    L_b = np.log(r_b / r_w)

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    gam = p_profile.gamma(r_b, pbs)

    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0,
                                    dT_w, Sg_w)
    Bo_frozen = fluid.Bo(p1, T1)

    T_b = t_profile(r_b, dT_w)
    mob_o_Bo_b = fluid.mobility_o_over_Bo(pbs, T_b, 0.0, k)
    dp_dr_b = p_profile.dp_dr(r_b, r_b, pbs, gam)
    flux_rb = r_b * mob_o_Bo_b * dp_dr_b

    boundary = -(Bo_frozen / phi) * flux_rb

    mob_o_Bo_frozen = fluid.mobility_o_over_Bo(p1, T1, Sg1, k)

    def integrand_vol(r):
        eta = s_profile.eta(r, r_b)
        if eta <= 0.0:
            return 0.0
        dp_dr = p_profile.dp_dr(r, r_b, pbs, gam)
        return eta ** (beta - 1.0) * mob_o_Bo_frozen * dp_dr

    I_vol, _ = quad(integrand_vol, r_w, r_b)
    F4_vol = (Bo_frozen / phi) * (beta / L_b) * I_vol

    I_pwf = 0.0
    if state.dp_wf_dt != 0.0:
        So1 = 1.0 - Sg1
        co_sat_1 = fluid.co_sat(p1, T1)
        cr = rock["c_r"]

        def integrand_pwf(r):
            eta = s_profile.eta(r, r_b)
            dp = dp_dpwf_numerical(p_profile, r, r_b, fluid, t_profile,
                                   dT_w)
            return r * eta**beta * So1 * (cr + co_sat_1) * dp

        i, _ = quad(integrand_pwf, r_w, r_b)
        I_pwf = i * state.dp_wf_dt

    return boundary + F4_vol + I_pwf


# ─── A₃₁: −∫r·Q̄_ad*·∂p/∂r_b dr (eq:A31) ─────────────────────────


def energy_A31(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₃₁ при ṙ_b в уравнении энергии. Ур. (eq:A31) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    phi = rock["phi"]
    cr = rock["c_r"]
    rho_cp_s = rock["rho_cp_s"]

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)

    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, state.Sg_w)
    Qad1 = fluid.Qad_star_coeff(p1, T1, Sg1, phi, rho_cp_s, cr)

    p2, T2, Sg2 = frozen_pvt_zone2(pbs, p_profile.p_0, t_profile.T_0)
    Qad2 = fluid.Qad_star_coeff(p2, T2, Sg2, phi, rho_cp_s, cr)

    def integrand_zone1(r):
        dp = dp_drb_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
        return r * Qad1 * dp

    def integrand_zone2(r):
        dp = dp_drb_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
        return r * Qad2 * dp

    r_w = p_profile.r_w
    R_ext = p_profile.R_ext

    I1, _ = quad(integrand_zone1, r_w, r_b)
    I2, _ = quad(integrand_zone2, r_b, R_ext)
    return -(I1 + I2)


# ─── A₃₃: −∫r·(ρcp)_eff*·Ψ(ζ) dr (eq:A33) ──────────────────────


def energy_A33(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₃₃ при Δ̇T_w в уравнении энергии. Ур. (eq:A33) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    phi = rock["phi"]
    rho_cp_s = rock["rho_cp_s"]

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)

    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, state.Sg_w)
    rhocp1 = fluid.rhocp_eff_star(p1, T1, Sg1, phi, rho_cp_s)

    p2, T2, Sg2 = frozen_pvt_zone2(pbs, p_profile.p_0, t_profile.T_0)
    rhocp2 = fluid.rhocp_eff_star(p2, T2, Sg2, phi, rho_cp_s)

    def integrand_zone1(r):
        zeta = t_profile.zeta(r)
        return r * rhocp1 * t_profile.Psi(zeta)

    def integrand_zone2(r):
        zeta = t_profile.zeta(r)
        return r * rhocp2 * t_profile.Psi(zeta)

    r_w = p_profile.r_w
    R_ext = p_profile.R_ext

    I1, _ = quad(integrand_zone1, r_w, r_b)
    I2, _ = quad(integrand_zone2, r_b, R_ext)
    return -(I1 + I2)


# ─── F₃: теплопроводность + конвекция + JT + ṗ_wf (eq:F3) ───────


def energy_F3(fluid, rock, p_profile, t_profile, s_profile, state):
    """Правая часть F₃ уравнения энергии. Ур. (eq:F3) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    phi = rock["phi"]
    cr = rock["c_r"]
    k = rock["k"]
    lambda_eff = rock["lambda_eff"]
    rho_cp_s = rock["rho_cp_s"]

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    gam = p_profile.gamma(r_b, pbs)

    r_w = p_profile.r_w
    R_ext = p_profile.R_ext

    # --- теплопроводность: R_ext · λ_eff · T'(R_ext) ---
    flux_cond = R_ext * lambda_eff * t_profile.dT_dr(R_ext, dT_w)

    # --- замороженные PVT ---
    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, Sg_w)
    p2, T2, Sg2 = frozen_pvt_zone2(pbs, p_profile.p_0, t_profile.T_0)

    Cconv1 = fluid.C_conv_star(p1, T1, Sg1, k)
    Cconv2 = fluid.C_conv_star(p2, T2, Sg2, k)

    QJT1 = fluid.QJT_star_coeff(p1, T1, Sg1, k)
    QJT2 = fluid.QJT_star_coeff(p2, T2, Sg2, k)

    # --- конвективный: +∫r · C̄_conv* · (dp/dr)(dT/dr) dr ---
    def conv_integrand_z1(r):
        dp_dr = p_profile.dp_dr(r, r_b, pbs, gam)
        dT_dr = t_profile.dT_dr(r, dT_w)
        return r * Cconv1 * dp_dr * dT_dr

    def conv_integrand_z2(r):
        dp_dr = p_profile.dp_dr(r, r_b, pbs, gam)
        dT_dr = t_profile.dT_dr(r, dT_w)
        return r * Cconv2 * dp_dr * dT_dr

    I_conv1, _ = quad(conv_integrand_z1, r_w, r_b)
    I_conv2, _ = quad(conv_integrand_z2, r_b, R_ext)
    conv_total = I_conv1 + I_conv2

    # --- JT: +∫r · Q̄_JT* · (dp/dr)² dr ---
    def jt_integrand_z1(r):
        dp_dr = p_profile.dp_dr(r, r_b, pbs, gam)
        return r * QJT1 * dp_dr ** 2

    def jt_integrand_z2(r):
        dp_dr = p_profile.dp_dr(r, r_b, pbs, gam)
        return r * QJT2 * dp_dr ** 2

    lower = r_w + r_w * 1e-3
    I_jt1, _ = quad(jt_integrand_z1, lower, r_b)
    I_jt2, _ = quad(jt_integrand_z2, r_b, R_ext)
    jt_total = I_jt1 + I_jt2

    # --- I_pwf^(3): +∫r · Q̄_ad* · (dp/dp_wf) dr · ṗ_wf ---
    I_pwf = 0.0
    if state.dp_wf_dt != 0.0:
        Qad1 = fluid.Qad_star_coeff(p1, T1, Sg1, phi, rho_cp_s, cr)
        Qad2 = fluid.Qad_star_coeff(p2, T2, Sg2, phi, rho_cp_s, cr)

        def pwf_z1(r):
            dp = dp_dpwf_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
            return r * Qad1 * dp

        def pwf_z2(r):
            dp = dp_dpwf_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
            return r * Qad2 * dp

        i1, _ = quad(pwf_z1, r_w, r_b)
        i2, _ = quad(pwf_z2, r_b, R_ext)
        I_pwf = (i1 + i2) * state.dp_wf_dt

    return flux_cond + conv_total + jt_total + I_pwf


def assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state,
                        beta_fixed=True):
    """Сборка A·ẋ=F. Ур. (eq:ode_system), (eq:ode_system_4x4) moments_method.tex."""
    if beta_fixed:
        A = np.zeros((3, 3))

        A[0, 0] = oil_A11(fluid, rock, p_profile, t_profile, state)
        A[0, 2] = oil_A13(fluid, rock, p_profile, t_profile, state)

        A[1, 0] = gas_A21(fluid, rock, p_profile, t_profile, s_profile, state)
        A[1, 1] = gas_A22(fluid, rock, p_profile, t_profile, s_profile, state)
        A[1, 2] = gas_A23(fluid, rock, p_profile, t_profile, s_profile, state)

        A[2, 0] = energy_A31(fluid, rock, p_profile, t_profile, s_profile, state)
        A[2, 2] = energy_A33(fluid, rock, p_profile, t_profile, s_profile, state)

        F = np.array([
            oil_F1(fluid, rock, p_profile, t_profile, s_profile, state),
            gas_F2(fluid, rock, p_profile, t_profile, s_profile, state),
            energy_F3(fluid, rock, p_profile, t_profile, s_profile, state),
        ])
    else:
        A = np.zeros((4, 4))

        A[0, 0] = oil_A11(fluid, rock, p_profile, t_profile, state)
        A[0, 3] = oil_A13(fluid, rock, p_profile, t_profile, state)

        A[1, 0] = gas_A21(fluid, rock, p_profile, t_profile, s_profile, state)
        A[1, 1] = gas_A22(fluid, rock, p_profile, t_profile, s_profile, state)
        A[1, 2] = gas_A2beta(fluid, rock, p_profile, t_profile, s_profile, state)
        A[1, 3] = gas_A23(fluid, rock, p_profile, t_profile, s_profile, state)

        A[2, 0] = energy_A31(fluid, rock, p_profile, t_profile, s_profile, state)
        A[2, 3] = energy_A33(fluid, rock, p_profile, t_profile, s_profile, state)

        A[3, 0] = gas_A41(fluid, rock, p_profile, t_profile, s_profile, state)
        A[3, 1] = gas_A42(fluid, rock, p_profile, t_profile, s_profile, state)
        A[3, 2] = gas_A43(fluid, rock, p_profile, t_profile, s_profile, state)
        A[3, 3] = gas_A44(fluid, rock, p_profile, t_profile, s_profile, state)

        F = np.array([
            oil_F1(fluid, rock, p_profile, t_profile, s_profile, state),
            gas_F2(fluid, rock, p_profile, t_profile, s_profile, state),
            energy_F3(fluid, rock, p_profile, t_profile, s_profile, state),
            gas_F4(fluid, rock, p_profile, t_profile, s_profile, state),
        ])

    return A, F
