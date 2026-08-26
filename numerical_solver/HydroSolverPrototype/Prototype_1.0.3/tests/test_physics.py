import unittest, numpy as np
from tests.helpers import model_and_state

class PhysicsTests(unittest.TestCase):
    def test_no_free_gas_above_bubble_point(self):
        _,m,s=model_and_state(p0=200,bhp=195); s1,r=m.advance(s,60); self.assertTrue(r.converged); self.assertFalse(np.any(s1.gas_active)); self.assertTrue(np.allclose(s1.sg,0))
    def test_gas_appears_after_pressure_drop(self):
        _,m,s=model_and_state(n=8,p0=200,bhp=100); cur=s
        for _ in range(12): cur,r=m.advance(cur,300); self.assertTrue(r.converged)
        self.assertTrue(np.any(cur.gas_active)); self.assertGreater(np.max(cur.sg),0)
    def test_one_step_component_balance(self):
        _,m,s=model_and_state(n=8,p0=200,bhp=150); s1,r=m.advance(s,60); self.assertTrue(r.converged)
        bo,bg=m.step_global_balance(s,s1,60); oi,gi=m.component_inventories(s)
        self.assertLess(abs(bo),max(1e-8,1e-8*np.sum(oi))); self.assertLess(abs(bg),max(1e-8,1e-8*np.sum(gi)))
    def test_repressurization_dissolves_free_gas(self):
        _,m,s=model_and_state(n=8,p0=160,bhp=100); cur=s
        for _ in range(6): cur,r=m.advance(cur,300); self.assertTrue(r.converged)
        self.assertGreater(np.max(cur.sg),0); sg0=np.sum(cur.sg); rs0=np.mean(cur.rs_sm3_sm3)
        m.set_bhp_control(175)
        for _ in range(20): cur,r=m.advance(cur,300); self.assertTrue(r.converged)
        self.assertLess(np.sum(cur.sg),sg0); self.assertGreater(np.mean(cur.rs_sm3_sm3),rs0)
    def test_oil_and_gas_inventories_positive(self):
        _,m,s=model_and_state(); oi,gi=m.component_inventories(s); self.assertTrue(np.all(oi>0)); self.assertTrue(np.all(gi>0))

if __name__=='__main__': unittest.main()
