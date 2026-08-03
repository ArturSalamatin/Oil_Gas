"""Правая часть ODE метода моментов — §5 moments_method.tex."""

import numpy as np

from .coefficients import OdeState, assemble_ode_system


def make_rhs(fluid, rock, p_profile, t_profile, s_profile, p_wf, dp_wf_dt=0.0,
             beta_fixed=True):
    """Фабрика rhs(t, y) для solve_ivp. Ур. (eq:ode_system), (eq:ode_system_4x4) moments_method.tex."""

    def rhs(t, y):
        if beta_fixed:
            r_b, Sg_w, dT_w = y
            beta = s_profile.beta
        else:
            r_b, Sg_w, beta, dT_w = y

        state = OdeState(
            r_b=r_b, Sg_w=Sg_w, dT_w=dT_w,
            p_wf=p_wf, dp_wf_dt=dp_wf_dt, beta=beta,
        )
        A, F = assemble_ode_system(
            fluid, rock, p_profile, t_profile, s_profile, state,
            beta_fixed=beta_fixed,
        )
        dy = np.linalg.solve(A, F)

        if not beta_fixed and Sg_w < 1e-6:
            dy[2] = 0.0

        return dy

    return rhs
