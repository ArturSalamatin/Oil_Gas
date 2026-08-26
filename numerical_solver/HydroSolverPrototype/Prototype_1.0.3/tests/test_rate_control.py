import unittest
from pathlib import Path
from radial_blackoil.input_reader import load_input
from radial_blackoil.grid import RadialGrid
from radial_blackoil.rock import CompressibleRock
from radial_blackoil.state import BlackOilState
from radial_blackoil.blackoil import RadialBlackOilModel

ROOT=Path(__file__).resolve().parents[1]
class RateControlTests(unittest.TestCase):
    def _model(self):
        inp=load_input(ROOT/'tests'/'fixtures'/'Nabor_1b.xlsx'); p=inp.params
        g=RadialGrid(float(p['Well radius rw']),float(p['Outer radius re']),float(p['Formation thickness h']),int(p['Grid cells N']),float(p['Absolute permeability']))
        r=CompressibleRock(float(p['Reference porosity']),float(p['Reference pressure']),float(p['Rock compressibility cr']))
        m=RadialBlackOilModel(g,r,inp.pvt,inp.relperm,150,float(p['Outer-boundary pressure']),float(p['Initial dissolved gas Rs']),skin=float(p['Well skin']),linear_solver='sparse')
        s=BlackOilState.undersaturated(g.n,float(p['Initial pressure']),float(p['Initial dissolved gas Rs']))
        return m,s
    def test_rate_control_algebraic_well_equation(self):
        m,s=self._model(); m.set_oil_rate_control(2.0,100.0)
        r=m.well_rates(s)
        self.assertAlmostEqual(r['oil_sm3_s']*86400.0,2.0,12)
        self.assertGreater(r['bhp_bar'],100.0)
        self.assertFalse(r['constraint_active'])
    def test_rate_floor_switches_to_bhp(self):
        m,s=self._model(); m.set_oil_rate_control(1000.0,100.0)
        r=m.well_rates(s)
        self.assertAlmostEqual(r['bhp_bar'],100.0,12)
        self.assertTrue(r['constraint_active'])
        self.assertLess(r['oil_sm3_s']*86400.0,1000.0)
    def test_rate_control_one_implicit_step(self):
        m,s=self._model(); m.set_oil_rate_control(2.0,100.0)
        s1,rep=m.advance(s,60.0); r=m.well_rates(s1)
        self.assertTrue(rep.converged)
        self.assertAlmostEqual(r['oil_sm3_s']*86400.0,2.0,10)
        self.assertGreater(r['bhp_bar'],100.0)

if __name__=='__main__': unittest.main()
