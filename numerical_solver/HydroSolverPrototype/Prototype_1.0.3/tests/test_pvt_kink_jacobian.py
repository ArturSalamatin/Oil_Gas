import unittest
from pathlib import Path
from radial_blackoil.input_reader import load_input
from radial_blackoil.grid import RadialGrid
from radial_blackoil.rock import CompressibleRock
from radial_blackoil.blackoil import RadialBlackOilModel

ROOT=Path(__file__).resolve().parents[1]

class PVTKinkJacobianTests(unittest.TestCase):
    def _model(self):
        inp=load_input(ROOT/'tests'/'fixtures'/'Nabor_1b.xlsx'); p=inp.params
        g=RadialGrid(float(p['Well radius rw']),float(p['Outer radius re']),float(p['Formation thickness h']),int(p['Grid cells N']),float(p['Absolute permeability']))
        r=CompressibleRock(float(p['Reference porosity']),float(p['Reference pressure']),float(p['Rock compressibility cr']))
        return RadialBlackOilModel(g,r,inp.pvt,inp.relperm,100.0,float(p['Outer-boundary pressure']),float(p['Initial dissolved gas Rs']),skin=float(p['Well skin']),jacobian_mode='grouped',linear_solver='sparse')

    def test_active_pressure_fd_does_not_cross_max_pb_from_below(self):
        m=self._model(); pb=m.pvt.bubble_point_max_rs_bar
        p=pb-7.0e-5
        h=m._pressure_fd_step(p,True)
        self.assertLess(h,0.0)
        self.assertLess(p+h,pb)

    def test_active_pressure_fd_does_not_cross_max_pb_from_above(self):
        m=self._model(); pb=m.pvt.bubble_point_max_rs_bar
        p=pb+7.0e-5
        h=m._pressure_fd_step(p,True)
        self.assertGreater(h,0.0)
        self.assertGreater(p+h,pb)

    def test_inactive_pressure_fd_keeps_default_positive_step(self):
        m=self._model(); pb=m.pvt.bubble_point_max_rs_bar
        self.assertGreater(m._pressure_fd_step(pb-7.0e-5,False),0.0)

if __name__=='__main__': unittest.main()
