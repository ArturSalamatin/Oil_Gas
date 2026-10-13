"""BUG-025, аудит 2: эмуляция шага 3 плана (blackoil.py) — только при BUG025_EMULATE=1.

Модуль radial_blackoil.blackoil получает _EPS, ROUNDOFF_KAPPA и метод _absolute_tol буквально
как в блоке «После» шага 3; оба Ньютона получают atol_sm3s = _absolute_tol(...). В них
tol = atol_sm3s + rtol*scale, а в шаге 3 — tol = _absolute_tol(...) + rtol*scale: та же арифметика.
"""
import os

import numpy as np

if os.environ.get("BUG025_EMULATE") == "1":
    from radial_blackoil import blackoil as bo

    bo._EPS = float(np.finfo(float).eps)
    bo.ROUNDOFF_KAPPA = 4.0

    def _absolute_tol(self, state_old, dt_s, atol_sm3s):
        oi0, gi0 = self._old_inventories(state_old)
        m = max(float(np.max(np.abs(oi0))), float(np.max(np.abs(gi0))) / self.gas_residual_scale)
        return max(atol_sm3s, bo.ROUNDOFF_KAPPA * bo._EPS * m / float(dt_s))

    _fixed = bo.RadialBlackOilModel._newton_fixed_active_set
    _switching = bo.RadialBlackOilModel._newton_switching

    def _newton_fixed_active_set(self, z0, state_old, dt_s, gas_active, max_iter=15, rtol=1e-8, atol_sm3s=1e-11):
        return _fixed(self, z0, state_old, dt_s, gas_active, max_iter=max_iter, rtol=rtol,
                      atol_sm3s=self._absolute_tol(state_old, dt_s, atol_sm3s))

    def _newton_switching(self, state_old, dt_s, max_iter=40, rtol=1e-8, atol_sm3s=1e-11, **kw):
        return _switching(self, state_old, dt_s, max_iter=max_iter, rtol=rtol,
                          atol_sm3s=self._absolute_tol(state_old, dt_s, atol_sm3s), **kw)

    bo.RadialBlackOilModel._absolute_tol = _absolute_tol
    bo.RadialBlackOilModel._newton_fixed_active_set = _newton_fixed_active_set
    bo.RadialBlackOilModel._newton_switching = _newton_switching
    print("BUG025_EMULATE: шаг 3 подставлен", flush=True)
