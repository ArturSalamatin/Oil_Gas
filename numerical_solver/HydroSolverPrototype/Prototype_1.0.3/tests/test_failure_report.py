import unittest
from tests.helpers import ROOT, model_and_state

# DEBT-030 (GPN project): first step of regression case T04 (Nabor_1b with other
# relperm tables, N = 100, p0 = 200 bar, BHP = 100 bar, dt = 60 s).  All three
# stages of advance() fail; the BHP 'shut' branch "converges" in 0 iterations with
# ||F|| = 0 on the unchanged initial state and is dropped as inconsistent.  Before
# DEBT-030 its report went to step_log.csv; now the Newton fields of the failure
# report are the original algorithm's.  The Nabor_1b fixture itself converges on
# this step.  An absolute case path: ROOT/'tests'/'fixtures'/<absolute> == <absolute>.
T04=ROOT/'regression'/'inputs'/'T04.xlsx'

class FailureReportTests(unittest.TestCase):
    def test_total_failure_reports_original_newton(self):
        _,ref,s=model_and_state(n=100,bhp=100.0,p0=200.0,case=T04)
        _,orig=ref._advance_phases(s,60.0)
        self.assertFalse(orig.converged,'precondition: the original algorithm fails on this step')
        _,m,_=model_and_state(n=100,bhp=100.0,p0=200.0,case=T04)
        _,rep=m.advance(s,60.0)
        self.assertFalse(rep.converged); self.assertTrue(rep.fallback and rep.globalized)
        self.assertGreater(rep.iterations,0)
        self.assertEqual((rep.iterations,rep.residual_inf,rep.active_set_iterations,rep.phase_switches),
                         (orig.iterations,orig.residual_inf,orig.active_set_iterations,orig.phase_switches))

if __name__=='__main__': unittest.main()
