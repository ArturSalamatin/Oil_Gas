import unittest
from radial_blackoil.pvt import BlackOilPVT
from radial_blackoil.relperm import TabulatedRelPerm

class ValidationExtraTests(unittest.TestCase):
    def test_gas_pvt_needs_increasing_pressure(self):
        oil=[(1,10,1.1,2),(1,20,1.09,2.1),(2,20,1.2,1.8),(2,30,1.19,1.9)]
        with self.assertRaises(ValueError): BlackOilPVT(oil,[(20,.1,.01),(10,.2,.02)])
    def test_relperm_needs_increasing_sg(self):
        with self.assertRaises(ValueError): TabulatedRelPerm([0,.2,.1],[1,.5,.4],[0,.1,.2])
    def test_relperm_nonnegative(self):
        with self.assertRaises(ValueError): TabulatedRelPerm([0,1],[1,-1],[0,1])

if __name__=='__main__': unittest.main()
