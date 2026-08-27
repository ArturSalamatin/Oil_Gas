import unittest,subprocess,tempfile,shutil,json,sys,os
from pathlib import Path
from tests.helpers import ROOT

class CliWorkflowTests(unittest.TestCase):
    def test_explicit_output_path(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'custom output'
            r=subprocess.run([sys.executable,str(ROOT/'run_prototype.py'),str(ROOT/'tests/fixtures/short_run.xlsx'),'--output',str(out)],cwd=Path(d),capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr); self.assertTrue((out/'run_summary.json').exists())
    def test_automatic_output_is_relative_to_prototype_root(self):
        auto=ROOT/'OUTPUT'/'short_run'; shutil.rmtree(auto,ignore_errors=True)
        with tempfile.TemporaryDirectory() as d:
            r=subprocess.run([sys.executable,str(ROOT/'run_prototype.py'),str(ROOT/'tests/fixtures/short_run.xlsx')],cwd=Path(d),capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr); self.assertTrue((auto/'run_summary.json').exists()); shutil.rmtree(auto,ignore_errors=True)
    def test_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='prototype path with spaces ') as d:
            inp=Path(d)/'my model with spaces.xlsx'; shutil.copy(ROOT/'tests/fixtures/short_run.xlsx',inp); out=Path(d)/'results with spaces'
            r=subprocess.run([sys.executable,str(ROOT/'run_prototype.py'),str(inp),'--output',str(out)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr); self.assertTrue((out/'rates.csv').exists())
    def test_repeated_run_is_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a'; b=Path(d)/'b'; run=[sys.executable,str(ROOT/'run_prototype.py'),str(ROOT/'tests/fixtures/short_run.xlsx')]
            self.assertEqual(subprocess.run(run+['--output',str(a)],capture_output=True).returncode,0)
            self.assertEqual(subprocess.run(run+['--output',str(b)],capture_output=True).returncode,0)
            for fn in ['profiles.csv','rates.csv','material_balance.csv']:
                self.assertEqual((a/fn).read_bytes(),(b/fn).read_bytes())
    def test_existing_output_directory_can_be_reused(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'same'; out.mkdir(); (out/'old.txt').write_text('old')
            r=subprocess.run([sys.executable,str(ROOT/'run_prototype.py'),str(ROOT/'tests/fixtures/short_run.xlsx'),'--output',str(out)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr); self.assertTrue((out/'run_summary.json').exists())

if __name__=='__main__': unittest.main()
