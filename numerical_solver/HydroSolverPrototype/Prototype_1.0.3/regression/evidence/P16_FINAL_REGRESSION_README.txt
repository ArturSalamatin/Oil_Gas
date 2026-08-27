Prototype 1.0.3 — Point 16: Final Production Regression T00–T11

Build: 1.0.3-prebeta-final-regression-20260825a
Overall: PASS WITH DOCUMENTED NOTES
Unit tests before: 80/80 PASS
Unit tests after: 80/80 PASS

All benchmark calculations were rerun through: production Excel -> production parser -> run_prototype.py -> standard OUTPUT.
No direct Python model calls were used for acceptance runs.

Cases:
  T00: PASS
  T01: PASS WITH NOTE
  T02: PASS
  T03: PASS
  T04: PASS WITH NOTE
  T05: PASS
  T06: PASS
  T07: PASS WITH TRANSIENT NOTE
  T08c: PASS WITH REOPENING / GAS-FRONT NOTE
  T09: PASS
  T10: PASS WITH TRANSIENT NOTE
  T11: PASS

QC:
  max oil material-balance error = 1.35444e-07% initial inventory
  max gas material-balance error = 2.35445e-07% initial inventory
  tolerance = 0.0001%
  all material balance PASS = True
  all state/control PASS = True
  all report times PASS = True

Notes:
  T07/T10: one-minute post-control-step transient differences remain documented and are excluded from stable acceptance.
  T08c: reverse dissolution remains inside extended PVTO; day-6 reopening and localized late Sg-front differences remain documented notes.
  PVT range warnings are intentional: no extrapolation is performed; endpoint clamp is used and warning is recorded.

Point 17 (assembling Prototype 1.0.3 beta) and point 18 (clean-room reminder/test) were NOT performed in this package.