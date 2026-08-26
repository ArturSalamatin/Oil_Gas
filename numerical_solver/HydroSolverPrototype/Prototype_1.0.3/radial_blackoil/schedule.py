from dataclasses import dataclass
import math
from .units import DAY_TO_S

@dataclass(frozen=True)
class ScheduleRow:
    time_day: float
    mode: str
    bhp_bar: float|None = None
    oil_rate_sm3_day: float|None = None
    min_bhp_bar: float|None = None

class Schedule:
    """Well schedule and report-time contract.

    Every SCHEDULE row is simultaneously:
    - an exact integration boundary,
    - a report/output time,
    - the control definition that becomes active *after* that boundary.

    Thus the state saved at a control-change row is the state reached under the
    preceding control. The row's new control applies to the next timestep.
    """
    def __init__(self, rows, total_time_day):
        self.rows=list(rows); self.total_time_day=float(total_time_day)
        if not self.rows: raise ValueError('SCHEDULE must contain at least one data row')
        if abs(self.rows[0].time_day)>1e-12: raise ValueError('first SCHEDULE row must have Time=0')
        for a,b in zip(self.rows,self.rows[1:]):
            if not b.time_day>a.time_day: raise ValueError('SCHEDULE times must be strictly increasing')
        if self.rows[-1].time_day > self.total_time_day+1e-12: raise ValueError('SCHEDULE time exceeds Simulation time')
    @property
    def report_days(self): return [r.time_day for r in self.rows]
    @property
    def boundaries_s(self): return [r.time_day*DAY_TO_S for r in self.rows[1:]] + ([self.total_time_day*DAY_TO_S] if self.rows[-1].time_day < self.total_time_day-1e-12 else [])
    def control_for_interval_starting_at(self,t_s):
        t=t_s/DAY_TO_S
        idx=0
        for i,r in enumerate(self.rows):
            if r.time_day <= t+1e-12: idx=i
            else: break
        return self.rows[idx]
    def next_boundary_s(self,t_s):
        for b in self.boundaries_s:
            if b > t_s+1e-9: return b
        return self.total_time_day*DAY_TO_S
