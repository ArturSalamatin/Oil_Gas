import unittest, numpy as np
from tests.helpers import model_and_state

class StrongDegassingRecoveryTests(unittest.TestCase):
    def test_phase_appearance_converges(self):
        _,m,s=model_and_state(n=8,p0=185,bhp=100); cur=s; switches=0
        for _ in range(8): cur,r=m.advance(cur,300); self.assertTrue(r.converged); switches+=r.phase_switches
        self.assertGreater(switches,0); self.assertTrue(np.any(cur.gas_active))
    def test_active_set_state_is_finite(self):
        _,m,s=model_and_state(n=8,p0=185,bhp=100); cur=s
        for _ in range(8): cur,r=m.advance(cur,300); self.assertTrue(r.converged)
        self.assertTrue(np.all(np.isfinite(cur.pressure_bar))); self.assertTrue(np.all(np.isfinite(cur.sg)))

if __name__=='__main__': unittest.main()
