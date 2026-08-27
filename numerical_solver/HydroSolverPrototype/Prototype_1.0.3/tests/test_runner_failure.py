import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from radial_blackoil.runner import run_workbook
from radial_blackoil.simulation import SimulationFailure,RunHistory
from tests.helpers import ROOT

class RunnerFailureTests(unittest.TestCase):
    def test_runner_writes_failed_summary_and_partial_outputs(self):
        h=RunHistory(report_states=[],report_rates=[],step_log=[(0,60,False,15,1,0,1.0)],accepted_steps=0,rejected_steps=1,material_balance=[],warnings=[],sanity_issues=[])
        e=SimulationFailure('DTMIN reached at t=0 day',h,0,60,None)
        with tempfile.TemporaryDirectory() as d, patch('radial_blackoil.runner.simulate_schedule',side_effect=e):
            out=Path(d)/'failed'
            with self.assertRaises(SimulationFailure): run_workbook(ROOT/'tests/fixtures/short_run.xlsx',out)
            js=json.loads((out/'run_summary.json').read_text())
            self.assertEqual(js['status'],'FAILED'); self.assertEqual(js['rejected_steps'],1); self.assertIn('failure',js); self.assertTrue((out/'step_log.csv').exists())

if __name__=='__main__': unittest.main()
