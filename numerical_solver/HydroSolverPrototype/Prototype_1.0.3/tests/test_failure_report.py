import unittest
from tests.helpers import ROOT, model_and_state

# DEBT-030 (GPN project): first step of regression case T04 (Nabor_1b with other
# relperm tables, N = 100, p0 = 200 bar, BHP = 100 bar, dt = 60 s).  All three
# stages of advance() fail; the BHP 'shut' branch "converges" in 0 iterations with
# ||F|| = 0 on the unchanged initial state and is dropped as inconsistent.  Before
# DEBT-030 its report went to step_log.csv; now the Newton fields of the failure
# report are the original algorithm's.  The Nabor_1b fixture itself converges on
# this step.  An absolute case path: ROOT/'tests'/'fixtures'/<absolute> == <absolute>.
# DEBT-069: the report also lists every attempt of the fallback stages (attempts).
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

    def test_total_failure_lists_attempts(self):
        # DEBT-069: the report lists every attempt in order.  T04 (BHP 100 bar, p_ext = 200 bar,
        # the old p0 = 200 > 100: 'open' first): stage 1; stages 2 and 3 -- 'open' fails by the
        # iteration limit, 'shut' "converges" in 0 iterations on the unchanged state and is
        # dropped as inconsistent ('branch').  Measured (GPN vault/issues/debt-069/probes/
        # t04_attempts.out.txt): stage 1 and stage 2 'open' 15 iterations, 2 passes, 21 switches.
        _,m,s=model_and_state(n=100,bhp=100.0,p0=200.0,case=T04)
        _,rep=m.advance(s,60.0)
        self.assertFalse(rep.converged)
        self.assertEqual([(a.stage,a.branch) for a in rep.attempts],
                         [(1,''),(2,'open'),(2,'shut'),(3,'open'),(3,'shut')])
        self.assertEqual([a.report.exit_reason for a in rep.attempts],
                         ['max_iter','max_iter','branch','max_iter','branch'])
        self.assertEqual([a.report.iterations for a in rep.attempts],[15,15,0,15,0])
        self.assertFalse(any(a.report.converged for a in rep.attempts))
        # the first attempt is the original algorithm whose Newton fields the report carries (DEBT-030)
        first=rep.attempts[0].report
        self.assertEqual((first.iterations,first.residual_inf,first.active_set_iterations,first.phase_switches),
                         (rep.iterations,rep.residual_inf,rep.active_set_iterations,rep.phase_switches))
        # copies: no attempts of their own
        self.assertTrue(all(a.report.attempts==() for a in rep.attempts))

    def test_accepted_original_has_no_attempts(self):
        # DEBT-069: where the original algorithm solves the step the report has no attempts
        # (the Nabor_1b fixture converges on this step: 12 iterations, no fallback)
        _,m,s=model_and_state(n=100,bhp=100.0,p0=200.0)
        _,rep=m.advance(s,60.0)
        self.assertTrue(rep.converged); self.assertFalse(rep.fallback)
        self.assertEqual(rep.attempts,())

if __name__=='__main__': unittest.main()
