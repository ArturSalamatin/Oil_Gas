import unittest, numpy as np
from types import SimpleNamespace
from tests.helpers import model_and_state
from radial_blackoil.diagnostics import pvt_range_warnings, relperm_range_warnings, warning_category, unique_warnings

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
    # DEBT-027 (GPN project): cell 0 gas-active 1 bar above the last Pb (Nabor_1b: 180 bar);
    # Sg = 0 is a saturation-front cell (nothing clamped), Sg = 0.02 is free gas that cannot dissolve.
    def _cell_above_locus(self,sg):
        _,m,s=model_and_state(p0=200); s.gas_active[0]=True; s.pressure_bar[0]=m.pvt.pb[-1]+1.0; s.sg[0]=sg; return m,s
    def test_locus_above_default_reports_any_gas_active_cell(self):
        m,s=self._cell_above_locus(0.0); w=pvt_range_warnings(m,s); self.assertTrue(any(x.startswith('OIL_PVT saturated locus above table: gas-active max P=') for x in w))
    def test_locus_above_free_gas_test_skips_front_cell(self):
        m,s=self._cell_above_locus(0.0); w=pvt_range_warnings(m,s,free_gas_sg=1e-6); self.assertFalse(any(x.startswith('OIL_PVT saturated locus above') for x in w))
    def test_locus_above_free_gas_test_reports_free_gas(self):
        m,s=self._cell_above_locus(0.02); w=pvt_range_warnings(m,s,free_gas_sg=1e-6); self.assertTrue(any(x.startswith('OIL_PVT saturated locus above table: free gas Sg up to 0.02 at P up to 181 bar') for x in w))
    def test_warning_category_ignores_numbers(self):
        a='OIL_PVT branch pressure above supplied range by up to 1 bar. Endpoint branch property used; no extrapolation.'; b=a.replace('up to 1 bar','up to 2 bar')
        self.assertEqual(warning_category(a),'OIL_PVT branch pressure above supplied range'); self.assertEqual(warning_category(b),warning_category(a)); self.assertEqual(unique_warnings([a,b]),[a])
    # DEBT-071 (GPN project): the relperm part of the range check is callable alone -- the GPN
    # adapter on the Standing correlation path has a relperm table but no PVT tables (no gp).
    def test_relperm_warnings_close_pvt_range_warnings(self):
        _,m,s=model_and_state(p0=350); s.sg[0]=0.9; w=pvt_range_warnings(m,s); r=relperm_range_warnings(m,s)
        self.assertEqual(r,['RELPERM Sg above table: max Sg=0.9, table max=0.85. Endpoint value used; no extrapolation.'])
        self.assertEqual(w[-1:],r); self.assertTrue(any(x.startswith('GAS_PVT pressure above') for x in w))
    def test_relperm_warnings_need_no_pvt(self):
        _,m,s=model_and_state(); s.sg[0]=-0.01; stub=SimpleNamespace(relperm=m.relperm)
        self.assertEqual([warning_category(x) for x in relperm_range_warnings(stub,s)],['RELPERM Sg below table'])
        with self.assertRaises(AttributeError): pvt_range_warnings(stub,s)

if __name__=='__main__': unittest.main()
