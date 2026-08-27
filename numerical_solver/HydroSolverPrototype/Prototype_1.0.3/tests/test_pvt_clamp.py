import unittest, numpy as np
from tests.helpers import model_and_state
from radial_blackoil.diagnostics import pvt_range_warnings

class PVTClampTests(unittest.TestCase):
    def test_oil_rs_above_max_uses_endpoint_branch_not_extrapolation(self):
        inp,_,_=model_and_state(); p=inp.pvt; v1=float(p.bo(250,p.rs_values[-1])); v2=float(p.bo(250,p.rs_values[-1]+100)); self.assertAlmostEqual(v1,v2,14)
    def test_oil_rs_below_min_uses_endpoint_branch(self):
        inp,_,_=model_and_state(); p=inp.pvt; v1=float(p.mu_o(100,p.rs_values[0])); v2=float(p.mu_o(100,p.rs_values[0]-100)); self.assertAlmostEqual(v1,v2,14)
    def test_oil_high_pressure_clamps_branch(self):
        inp,_,_=model_and_state(); p=inp.pvt; rs=40.; self.assertAlmostEqual(float(p.bo(10000,rs)),float(p.bo(300,rs)),14)
    def test_warning_on_gas_pvt_high_pressure(self):
        _,m,s=model_and_state(p0=350); w=pvt_range_warnings(m,s); self.assertTrue(any('GAS_PVT pressure above' in x for x in w))
    def test_warning_on_oil_branch_high_pressure(self):
        _,m,s=model_and_state(p0=350); w=pvt_range_warnings(m,s); self.assertTrue(any('OIL_PVT branch pressure' in x for x in w))
    def test_no_warning_normal_initial_state(self):
        _,m,s=model_and_state(p0=200); w=pvt_range_warnings(m,s); self.assertFalse(any('GAS_PVT pressure above' in x for x in w))
    def test_no_rs_warning_for_machine_roundoff_at_endpoint(self):
        _,m,s=model_and_state(p0=200); s.rs_sm3_sm3[0]=m.pvt.rs_values[-1]+1e-11; w=pvt_range_warnings(m,s); self.assertFalse(any('OIL_PVT Rs above table' in x for x in w))

if __name__=='__main__': unittest.main()
