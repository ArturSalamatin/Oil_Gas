import unittest
from pathlib import Path
from radial_blackoil.input_reader import load_input

ROOT=Path(__file__).resolve().parents[1]
EXPECTED=[0.0,1/1440,1.0,2.0,4.0,6.0,14.0,30.0]

class InputContractTests(unittest.TestCase):
    def test_t00_schedule_drives_reports(self):
        inp=load_input(ROOT/'tests'/'fixtures'/'Nabor_0b.xlsx')
        self.assertEqual(len(inp.schedule.rows),8)
        for a,b in zip(inp.schedule.report_days,EXPECTED): self.assertAlmostEqual(a,b,14)
        self.assertTrue(all(r.mode=='BHP' and r.bhp_bar==100 for r in inp.schedule.rows))
    def test_t01_schedule_drives_reports(self):
        inp=load_input(ROOT/'tests'/'fixtures'/'Nabor_1b.xlsx')
        for a,b in zip(inp.schedule.report_days,EXPECTED): self.assertAlmostEqual(a,b,14)
        self.assertAlmostEqual(inp.pvt.bubble_point_max_rs_bar,180.0,12)
    def test_eclipse_pvto_first_rows_define_saturated_locus(self):
        inp=load_input(ROOT/'tests'/'fixtures'/'Nabor_0b.xlsx')
        self.assertEqual(list(inp.pvt.rs_values),[5,10,20,30,40,50])
        self.assertAlmostEqual(inp.pvt.rs_sat(inp.pvt.pb[-1]),50.0,12)
        # At gas-active saturated state, branch-clamped PVTO equals first-row locus.
        p=100.0; rs=float(inp.pvt.rs_sat(p))
        self.assertGreater(rs,30.0); self.assertLess(rs,40.0)
        self.assertTrue(inp.pvt.bo(p,rs)>1.0)

if __name__=='__main__': unittest.main()
