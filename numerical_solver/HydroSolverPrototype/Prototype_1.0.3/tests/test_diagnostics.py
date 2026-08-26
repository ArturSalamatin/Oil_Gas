import unittest, numpy as np
from tests.helpers import model_and_state
from radial_blackoil.diagnostics import state_sanity

class DiagnosticsTests(unittest.TestCase):
    def test_normal_state_passes(self): _,_,s=model_and_state(); self.assertEqual(state_sanity(s),[])
    def test_negative_pressure_detected(self): _,_,s=model_and_state(); s.pressure_bar[0]=-1; self.assertTrue(any('pressure' in x for x in state_sanity(s)))
    def test_bad_sg_detected(self): _,_,s=model_and_state(); s.sg[0]=1.1; self.assertTrue(any('Sg' in x for x in state_sanity(s)))
    def test_negative_rs_detected(self): _,_,s=model_and_state(); s.rs_sm3_sm3[0]=-1; self.assertTrue(any('Rs' in x for x in state_sanity(s)))
    def test_nan_detected(self): _,_,s=model_and_state(); s.pressure_bar[0]=np.nan; self.assertTrue(any('NaN' in x for x in state_sanity(s)))

if __name__=='__main__': unittest.main()
