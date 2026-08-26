import unittest
from radial_blackoil.schedule import Schedule, ScheduleRow
from radial_blackoil.units import DAY_TO_S

class FakeReport:
    converged=True; iterations=2; active_set_iterations=1; phase_switches=0; residual_inf=0.0
class FakeState:
    def __init__(self,x=0): self.x=x
    def copy(self): return FakeState(self.x)
class FakeModel:
    def __init__(self): self.p_bhp_bar=0.0; self.used=[]
    def set_bhp_control(self,bhp): self.p_bhp_bar=float(bhp)
    def set_oil_rate_control(self,q,min_bhp=None): raise NotImplementedError
    def advance(self,state,dt):
        self.used.append((self.p_bhp_bar,dt))
        return FakeState(state.x+1), FakeReport()
    def well_rates(self,state):
        return {'oil_sm3_s':1.0,'total_gas_sm3_s':2.0,'gor_sm3_sm3':2.0,'bhp_bar':self.p_bhp_bar}

class ScheduleReportingTests(unittest.TestCase):
    def test_every_row_is_report_time(self):
        rows=[ScheduleRow(0,'BHP',100),ScheduleRow(1/1440,'BHP',100),ScheduleRow(1,'BHP',100),ScheduleRow(2,'BHP',100)]
        s=Schedule(rows,2)
        self.assertEqual(s.report_days,[0,1/1440,1,2])
        self.assertAlmostEqual(s.next_boundary_s(0),60.0,places=10)
        self.assertAlmostEqual(s.next_boundary_s(60.0),DAY_TO_S,places=10)

    def test_repeated_control_is_not_a_control_change(self):
        rows=[ScheduleRow(0,'BHP',100),ScheduleRow(1,'BHP',100),ScheduleRow(2,'BHP',100)]
        s=Schedule(rows,2)
        self.assertEqual([s.control_for_interval_starting_at(t*DAY_TO_S).bhp_bar for t in (0,0.5,1,1.5,2)],[100]*5)

    def test_new_control_applies_after_boundary(self):
        # Import here to keep schedule-only parsing tests independent.
        from radial_blackoil.simulation import simulate_schedule
        rows=[ScheduleRow(0,'BHP',150),ScheduleRow(1,'BHP',120),ScheduleRow(2,'BHP',100)]
        s=Schedule(rows,2); m=FakeModel()
        h=simulate_schedule(m,FakeState(),s,DAY_TO_S,1.0,DAY_TO_S)
        self.assertEqual([x[0] for x in m.used],[150,120])
        # Report at day 1 is associated with the control that produced that state.
        self.assertEqual(h.report_rates[1][2],150)
        self.assertEqual([x[0] for x in h.report_states],[0.0,1.0,2.0])

    def test_non_increasing_times_fail(self):
        with self.assertRaises(ValueError):
            Schedule([ScheduleRow(0,'BHP',100),ScheduleRow(1,'BHP',100),ScheduleRow(1,'BHP',100)],2)

if __name__=='__main__': unittest.main()
