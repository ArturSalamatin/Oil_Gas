import unittest, math, numpy as np
from radial_blackoil.grid import RadialGrid
from radial_blackoil.rock import CompressibleRock
from radial_blackoil.units import MD_TO_M2
from tests.helpers import model_and_state

class ModelInvariantTests(unittest.TestCase):
    def test_radial_cell_volumes_reproduce_annulus(self):
        g=RadialGrid(.1,100,10,100,1); exact=math.pi*10*(100**2-.1**2); self.assertAlmostEqual(np.sum(g.bulk_volumes_m3),exact,8)
    def test_radial_resistance_reproduces_log(self):
        g=RadialGrid(.1,100,10,100,1); kh=1*MD_TO_M2*10
        resist=1/g.well_transmissibility_m3(0)+np.sum(1/g.internal_transmissibility_m3)+1/g.outer_transmissibility_m3
        exact=math.log(100/.1)/(2*math.pi*kh); self.assertAlmostEqual(resist/exact,1,12)
    def test_discrete_single_phase_rate_matches_radial_analytic(self):
        g=RadialGrid(.1,100,10,100,1); mu=2e-3; bo=1.1; dp=50*1e5
        Ttot=1/(1/g.well_transmissibility_m3()+np.sum(1/g.internal_transmissibility_m3)+1/g.outer_transmissibility_m3)
        qdisc=Ttot*dp/(mu*bo); qanal=2*math.pi*(1*MD_TO_M2)*10*dp/(mu*bo*math.log(100/.1)); self.assertAlmostEqual(qdisc/qanal,1,12)
    def test_rock_pv_reference(self):
        r=CompressibleRock(.2,200,4.5e-5); self.assertAlmostEqual(float(r.porosity(200)),.2,14)
    def test_rock_pv_increases_with_pressure(self):
        r=CompressibleRock(.2,200,4.5e-5); self.assertGreater(float(r.porosity(250)),float(r.porosity(150)))
    def test_pvt_saturated_nodes(self):
        inp,_,_=model_and_state(); p=inp.pvt
        for pb,rs in zip(p.pb,p.rs_values): self.assertAlmostEqual(float(p.rs_sat(pb)),float(rs),12)
    def test_relperm_bounds_at_nodes(self):
        inp,_,_=model_and_state(); r=inp.relperm; self.assertTrue(np.all(r.kro_tab>=0)); self.assertTrue(np.all(r.krg_tab>=0)); self.assertTrue(np.all((r.sg>=0)&(r.sg<=1)))
    def test_lower_bhp_increases_production(self):
        _,m,s=model_and_state(bhp=150); q1=m.well_rates(s)['oil_sm3_s']; m.set_bhp_control(100); q2=m.well_rates(s)['oil_sm3_s']; self.assertGreater(q2,q1)
    def test_rs_sat_clamps_at_table_max(self):
        inp,_,_=model_and_state(); self.assertAlmostEqual(float(inp.pvt.rs_sat(10000)),float(inp.pvt.rs_values[-1]),12)
    def test_rs_sat_clamps_at_table_min(self):
        inp,_,_=model_and_state(); self.assertAlmostEqual(float(inp.pvt.rs_sat(-100)),float(inp.pvt.rs_values[0]),12)
    def test_gas_pvt_clamps_both_ends(self):
        inp,_,_=model_and_state(); p=inp.pvt; self.assertAlmostEqual(float(p.bg(-10)),p.gbg[0],14); self.assertAlmostEqual(float(p.bg(10000)),p.gbg[-1],14)
    def test_relperm_clamps_both_ends(self):
        inp,_,_=model_and_state(); r=inp.relperm; self.assertAlmostEqual(float(r.krg(-1)),r.krg_tab[0],14); self.assertAlmostEqual(float(r.krg(2)),r.krg_tab[-1],14)

if __name__=='__main__': unittest.main()
