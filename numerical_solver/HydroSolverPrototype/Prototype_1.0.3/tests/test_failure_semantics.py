import unittest
from tests.helpers import model_and_state
from radial_blackoil.schedule import Schedule,ScheduleRow
from radial_blackoil.simulation import simulate_schedule,SimulationFailure

class FailureSemanticsTests(unittest.TestCase):
    def test_failure_object_keeps_partial_history(self):
        _,m,s=model_and_state(n=5,p0=200,bhp=100)
        # Force an impossible dt minimum relationship after first nonlinear rejection by monkeypatching advance.
        class R: converged=False; iterations=15; active_set_iterations=1; phase_switches=0; residual_inf=1.0
        old=m.advance; m.advance=lambda state,dt:(state.copy(),R())
        sch=Schedule([ScheduleRow(0,'BHP',100),ScheduleRow(.01,'BHP',100)],.01)
        with self.assertRaises(SimulationFailure) as cm: simulate_schedule(m,s,sch,60,40,60)
        self.assertEqual(cm.exception.history.accepted_steps,0); self.assertGreater(cm.exception.history.rejected_steps,0); self.assertEqual(cm.exception.time_s,0)
        m.advance=old

if __name__=='__main__': unittest.main()
