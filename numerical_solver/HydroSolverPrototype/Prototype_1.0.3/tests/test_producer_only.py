import unittest
from pathlib import Path
from radial_blackoil.input_reader import load_input
from radial_blackoil.grid import RadialGrid
from radial_blackoil.rock import CompressibleRock
from radial_blackoil.state import BlackOilState
from radial_blackoil.blackoil import RadialBlackOilModel

ROOT=Path(__file__).resolve().parents[1]

class ProducerOnlyTests(unittest.TestCase):
    def _model(self,p0=120.0):
        inp=load_input(ROOT/'tests'/'fixtures'/'Nabor_1b.xlsx'); p=inp.params
        g=RadialGrid(float(p['Well radius rw']),float(p['Outer radius re']),float(p['Formation thickness h']),int(p['Grid cells N']),float(p['Absolute permeability']))
        rock=CompressibleRock(float(p['Reference porosity']),float(p['Reference pressure']),float(p['Rock compressibility cr']))
        m=RadialBlackOilModel(g,rock,inp.pvt,inp.relperm,175.0,float(p['Outer-boundary pressure']),float(p['Initial dissolved gas Rs']),skin=float(p['Well skin']),linear_solver='sparse')
        s=BlackOilState.undersaturated(g.n,p0,float(p['Initial dissolved gas Rs']))
        return m,s

    def test_bhp_producer_shuts_in_instead_of_reverse_flow(self):
        m,s=self._model(120.0); m.set_bhp_control(175.0)
        r=m.well_rates(s)
        self.assertEqual(r['oil_sm3_s'],0.0)
        self.assertEqual(r['total_gas_sm3_s'],0.0)
        self.assertAlmostEqual(r['bhp_bar'],120.0,12)

    def test_bhp_producer_reopens_when_pressure_above_target(self):
        m,s=self._model(180.0); m.set_bhp_control(175.0)
        r=m.well_rates(s)
        self.assertGreater(r['oil_sm3_s'],0.0)
        self.assertGreater(r['total_gas_sm3_s'],0.0)
        self.assertAlmostEqual(r['bhp_bar'],175.0,12)

    def test_rate_floor_shuts_in_instead_of_reverse_flow(self):
        m,s=self._model(120.0); m.set_oil_rate_control(1000.0,175.0)
        r=m.well_rates(s)
        self.assertEqual(r['oil_sm3_s'],0.0)
        self.assertEqual(r['total_gas_sm3_s'],0.0)
        self.assertAlmostEqual(r['bhp_bar'],120.0,12)
        self.assertTrue(r['constraint_active'])

if __name__=='__main__': unittest.main()
