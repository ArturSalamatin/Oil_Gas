"""Обёртка solve_ivp для метода моментов — §5–6 moments_method.tex."""

import numpy as np
from scipy.integrate import solve_ivp
from scipy.special import erfinv

from .ode_system import make_rhs


def _initial_conditions(fluid, rock, p_profile, t_profile, p_wf, t_eps):
    """Начальные условия ODE. Ур. (eq:ic_regularized) moments_method.tex. DEBT-001: вынести в initial.py."""
    p_0 = p_profile.p_0
    p_b = fluid.p_b
    T_0 = t_profile.T_0

    alpha_star = erfinv((p_b - p_wf) / (p_0 - p_wf))

    Cp0 = fluid.Cp(p_0, T_0, 0.0, rock["phi"], rock["c_r"])
    Lambda0 = fluid.Lambda(p_0, T_0, 0.0, rock["k"])
    chi_0 = Lambda0 / Cp0

    r_b0 = p_profile.r_w + 2.0 * alpha_star * np.sqrt(chi_0 * t_eps)

    Rs_pb = fluid.Rs(p_b, T_0)
    Rs_pwf = fluid.Rs(p_wf, T_0)
    Bg_pwf = fluid.Bg(p_wf, T_0)
    Bo_pwf = fluid.Bo(p_wf, T_0)
    Sgw_eq = (Rs_pb - Rs_pwf) * Bg_pwf / Bo_pwf

    return np.array([r_b0, Sgw_eq, 0.0])


def _event_rb_reached(r_e):
    """Event: r_b достиг r_e."""
    def event(t, y):
        return r_e - y[0]
    event.terminal = True
    event.direction = -1
    return event


def solve_moments(fluid, rock, p_profile, t_profile, s_profile,
                  p_wf, r_e, t_end, t_eps=1e-5, dp_wf_dt=0.0,
                  **ivp_kwargs):
    """Интегрирование ODE метода моментов. §5–6 moments_method.tex."""
    y0 = _initial_conditions(fluid, rock, p_profile, t_profile, p_wf, t_eps)
    rhs = make_rhs(fluid, rock, p_profile, t_profile, s_profile,
                   p_wf, dp_wf_dt)
    event = _event_rb_reached(r_e)

    defaults = dict(method='Radau', rtol=1e-6, atol=1e-9,
                    dense_output=True, first_step=1e-8)
    defaults.update(ivp_kwargs)

    return solve_ivp(rhs, (t_eps, t_end), y0, events=[event], **defaults)


def reconstruct_profiles(r_b, Sg_w, dT_w, p_profile, t_profile,
                         s_profile, fluid, r_grid):
    """Восстановление p(r), Sg(r), T(r) из параметров решения. §4 moments_method.tex."""
    pb_star = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    gamma = p_profile.gamma(r_b, pb_star)

    p_arr = np.array([p_profile(r, r_b, pb_star, gamma) for r in r_grid])
    Sg_arr = np.array([s_profile(r, r_b, Sg_w) for r in r_grid])
    T_arr = np.array([t_profile(r, dT_w) for r in r_grid])

    return p_arr, Sg_arr, T_arr
