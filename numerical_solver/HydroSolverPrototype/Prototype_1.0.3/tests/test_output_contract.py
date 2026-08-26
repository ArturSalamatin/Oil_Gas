import unittest,tempfile,json,csv
from pathlib import Path
from radial_blackoil.runner import run_workbook
from tests.helpers import ROOT

class OutputContractTests(unittest.TestCase):
    def test_run_writes_required_files_and_summary(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'run'; s=run_workbook(ROOT/'tests'/'fixtures'/'short_run.xlsx',out)
            self.assertEqual(s['status'],'SUCCESS')
            for fn in ['profiles.csv','rates.csv','step_log.csv','material_balance.csv','run_summary.json','run_summary.txt','summary.json','results.xlsx','oil_rate.png','gas_rate.png','GOR.png','BHP.png','pressure_profiles.png','Sg_profiles.png','Rs_profiles.png']:
                self.assertTrue((out/fn).exists(),fn)
            js=json.loads((out/'run_summary.json').read_text())
            self.assertEqual(js['prototype_version'],'1.0.3'); self.assertIn('input_sha256',js); self.assertTrue(js['qc']['report_times_pass'])
    def test_material_balance_csv_has_component_columns(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'run'; run_workbook(ROOT/'tests'/'fixtures'/'short_run.xlsx',out)
            with open(out/'material_balance.csv',newline='',encoding='utf-8') as f: hdr=next(csv.reader(f))
            for x in ['oil_balance_error_pct_initial','gas_current_dissolved_sm3','gas_current_free_sm3','gas_balance_error_pct_initial']: self.assertIn(x,hdr)
    def test_run_summary_records_range_warning_without_extrapolation(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'run'; s=run_workbook(ROOT/'tests'/'fixtures'/'range_warning_run.xlsx',out)
            self.assertGreater(s['warning_count'],0)
            self.assertTrue(any('no extrapolation' in x.lower() for x in s['warnings']))
            self.assertEqual(len([x for x in s['warnings'] if x.startswith('OIL_PVT branch pressure')]),1)
    def test_summary_contains_build_and_qc(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'run'; s=run_workbook(ROOT/'tests'/'fixtures'/'short_run.xlsx',out)
            self.assertIn('build_id',s); self.assertIn('qc',s); self.assertIn('warnings',s)
    def test_build_file_exists(self): self.assertTrue((ROOT/'BUILD.txt').exists())
    def test_version_file_exists(self): self.assertTrue((ROOT/'VERSION.txt').exists())

if __name__=='__main__': unittest.main()
