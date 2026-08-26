import unittest, tempfile, shutil
from pathlib import Path
from radial_blackoil.input_reader import load_input
from radial_blackoil.units import DAY_TO_S
from tests.helpers import ROOT, model_and_state
from radial_blackoil.schedule import Schedule, ScheduleRow
from radial_blackoil.simulation import simulate_schedule

class CaseConfigTests(unittest.TestCase):
    def test_nabor1_dtmax_60min(self): self.assertEqual(float(load_input(ROOT/'tests'/'fixtures'/'Nabor_1b.xlsx').params['DTMAX'])*60,3600)
    def test_input_can_be_outside_data_directory(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'copy.xlsx'; shutil.copy(ROOT/'tests'/'fixtures'/'Nabor_1b.xlsx',p); self.assertEqual(load_input(p).path,p)
    def test_geometry_is_built_from_input(self):
        inp,m,_=model_and_state(n=17); self.assertEqual(m.grid.n,17); self.assertAlmostEqual(m.grid.rw_m,float(inp.params['Well radius rw']))
    def test_schedule_report_days_from_excel(self):
        inp=load_input(ROOT/'tests'/'fixtures'/'Nabor_1b.xlsx'); self.assertEqual(len(inp.schedule.report_days),8); self.assertAlmostEqual(inp.schedule.report_days[-1],30,12)
    def test_dtmax_is_honored_by_driver(self):
        _,m,s=model_and_state(n=5,p0=200,bhp=190); sch=Schedule([ScheduleRow(0,'BHP',190),ScheduleRow(.01,'BHP',190)],.01); h=simulate_schedule(m,s,sch,60,1e-5,120); self.assertTrue(all(row[1]<=120+1e-12 for row in h.step_log if row[2]))

if __name__=='__main__': unittest.main()
