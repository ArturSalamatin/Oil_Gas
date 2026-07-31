"""Правая часть ODE метода моментов — §5 moments_method.tex."""

import numpy as np

from .coefficients import OdeState, assemble_ode_system


def make_rhs(fluid, rock, p_profile, t_profile, s_profile, p_wf, dp_wf_dt=0.0):
    """Фабрика rhs(t, y) для solve_ivp. Ур. (eq:ode_system) moments_method.tex."""

    def rhs(t, y):
        r_b, Sg_w, dT_w = y
        state = OdeState(
            r_b=r_b, Sg_w=Sg_w, dT_w=dT_w,
            p_wf=p_wf, dp_wf_dt=dp_wf_dt,
        )
        A, F = assemble_ode_system(
            fluid, rock, p_profile, t_profile, s_profile, state,
        )
        return np.linalg.solve(A, F)

    return rhs
