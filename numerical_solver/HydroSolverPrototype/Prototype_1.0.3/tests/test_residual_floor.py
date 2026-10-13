import unittest, numpy as np
from tests.helpers import model_and_state
from radial_blackoil import blackoil

# BUG-025: the absolute Newton tolerance is not below the round-off floor of the storage
# term, max(atol, ROUNDOFF_KAPPA*eps*M_max/dt), M_max -- the largest cell inventory of
# state_old (oil rows, gas rows / gas_residual_scale).  Without it a GPN shut-in step
# shorter than ~0.05 s stalled at |F|*dt = 5-7e-13 m3st and no stage of advance converged.
# The defect itself needs a developed transient (GPN tests); on Nabor_1b from a uniform state
# far cells do not change in a short step and carry no round-off.  These tests check the formula.
EPS=float(np.finfo(float).eps); ATOL=1e-11

def _m_max(m,s):
    oi,gi=m._old_inventories(s)
    return max(float(np.max(np.abs(oi))),float(np.max(np.abs(gi)))/m.gas_residual_scale)

class ResidualFloorTests(unittest.TestCase):
    def test_long_step_returns_atol(self):
        # dt = 1 h: the floor 4*eps*3.8e4/3600 = 9e-15 is below atol, so the tolerance is atol
        # itself and every solve is bitwise the former one
        _,m,s=model_and_state(n=12)
        self.assertEqual(m._absolute_tol(s,3600.0,ATOL),ATOL)
    def test_short_step_floor(self):
        # dt = 1 ms: the floor 3.4e-8 m3st/s is above atol
        _,m,s=model_and_state(n=12); dt=1e-3
        tol=m._absolute_tol(s,dt,ATOL)
        self.assertEqual(tol,blackoil.ROUNDOFF_KAPPA*EPS*_m_max(m,s)/dt); self.assertGreater(tol,100*ATOL)
    def test_gas_rows_scaled(self):
        # Undersaturated state: gas inventory = Rs*oil inventory; with gas_residual_scale = 1 the
        # gas rows set M_max, with the default scale (Rs_ext) both rows give the same value
        _,m,s=model_and_state(n=12); dt=1e-3
        oil=float(np.max(m._old_inventories(s)[0]))
        m.gas_residual_scale=1.0
        tol=m._absolute_tol(s,dt,ATOL)
        self.assertEqual(tol,blackoil.ROUNDOFF_KAPPA*EPS*_m_max(m,s)/dt)
        self.assertGreater(tol,blackoil.ROUNDOFF_KAPPA*EPS*oil/dt)
    def test_newton_reports_floored_tolerance(self):
        # _newton_fixed_active_set reports tol = _absolute_tol + rtol*max(||F0||, 1e-9)
        _,m,s=model_and_state(n=12); dt=1e-3; z0=m.pack(s)
        f0=m.residual(z0,s,dt,s.gas_active)
        _,rep=m._newton_fixed_active_set(z0,s,dt,s.gas_active)
        self.assertEqual(rep.residual_tol,m._absolute_tol(s,dt,ATOL)+1e-8*max(np.linalg.norm(f0,np.inf),1e-9))

if __name__=='__main__': unittest.main()
