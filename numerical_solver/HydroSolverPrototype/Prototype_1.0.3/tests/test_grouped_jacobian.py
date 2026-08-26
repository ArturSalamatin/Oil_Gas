import unittest, numpy as np
from tests.helpers import model_and_state

class GroupedJacobianTests(unittest.TestCase):
    def test_grouped_equals_reference_oil_only(self):
        _,m,s=model_and_state(n=7); z=m.pack(s); Jg,f=m.finite_difference_jacobian_grouped(z,s,60,s.gas_active); Jr,_=m.finite_difference_jacobian_reference(z,s,60,s.gas_active); self.assertLess(np.max(abs(Jg-Jr)),1e-8)
    def test_grouped_equals_reference_mixed_active(self):
        _,m,s=model_and_state(n=7,p0=160); mask=np.zeros(7,bool); mask[:3]=True; s.gas_active=mask; s.sg[:3]=0.02; s.rs_sm3_sm3[:3]=m.pvt.rs_sat(s.pressure_bar[:3]); z=m.pack(s); Jg,_=m.finite_difference_jacobian_grouped(z,s,60,mask); Jr,_=m.finite_difference_jacobian_reference(z,s,60,mask); self.assertLess(np.max(abs(Jg-Jr)),2e-7)
    def test_one_step_grouped_reference_same(self):
        _,mg,s=model_and_state(n=8,jacobian='grouped'); _,mr,_=model_and_state(n=8,jacobian='reference'); a,rg=mg.advance(s,60); b,rr=mr.advance(s,60); self.assertTrue(rg.converged and rr.converged); self.assertLess(np.max(abs(a.pressure_bar-b.pressure_bar)),1e-7); self.assertLess(np.max(abs(a.rs_sm3_sm3-b.rs_sm3_sm3)),1e-7)
    def test_sparse_dense_same_step(self):
        _,ms,s=model_and_state(n=8,linear='sparse'); _,md,_=model_and_state(n=8,linear='dense'); a,ra=ms.advance(s,60); b,rb=md.advance(s,60); self.assertTrue(ra.converged and rb.converged); self.assertLess(np.max(abs(a.pressure_bar-b.pressure_bar)),1e-8)

if __name__=='__main__': unittest.main()
