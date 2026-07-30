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
