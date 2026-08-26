import unittest, numpy as np
from tests.helpers import model_and_state

class SgcPhaseMobilityTests(unittest.TestCase):
    def test_gas_phase_existence_independent_of_mobility(self):
        _,m,s=model_and_state(n=6,p0=160); s.gas_active[0]=True; s.sg[0]=0.01; s.rs_sm3_sm3[0]=m.pvt.rs_sat(160); self.assertTrue(s.gas_active[0]); self.assertEqual(float(m.relperm.krg(s.sg[0])),0.0)
    def test_krg_zero_below_sgc(self):
        _,m,_=model_and_state(); self.assertEqual(float(m.relperm.krg(0.04)),0.0)
    def test_krg_positive_above_sgc(self):
        _,m,_=model_and_state(); self.assertGreater(float(m.relperm.krg(0.15)),0.0)
    def test_active_immobile_state_has_zero_free_gas_well_flux_if_sg_below_sgc(self):
        _,m,s=model_and_state(n=6,p0=160,bhp=100); s.gas_active[0]=True; s.sg[0]=0.01; s.rs_sm3_sm3[0]=m.pvt.rs_sat(160); f=m.face_component_fluxes_sm3s(s); self.assertAlmostEqual(float(f['free_gas_well']),0.0,16)

if __name__=='__main__': unittest.main()
