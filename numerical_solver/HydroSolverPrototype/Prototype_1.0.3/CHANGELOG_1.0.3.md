# Prototype 1.0.3 — changes

## Schedule/output update
- `SCHEDULE` is now the single source of both well-control events and output/report times.
- Every SCHEDULE row is an exact timestep boundary and mandatory output point.
- Repeating the same BHP/RATE target only adds a report time and does not change physics.
- New control at a schedule boundary is applied starting with the next timestep.
- `t=0` is exported because it is the first schedule row.

## Regression protection
- Black-oil conservation equations: unchanged.
- Active-set phase switching: unchanged.
- PVT/relperm physics: unchanged.
- Grouped/reference finite-difference Jacobians: unchanged.
- Sparse/dense linear backend behavior: unchanged.
- Adaptive timestep growth/cut rules: unchanged.

## Validation
- 10/10 schedule/input/rate-control tests PASS.
- T00 and T01 step sequences are exactly identical to the preceding validated 1.0.3 runs.
- Common-time T00/T01 state and rate differences are at floating-point roundoff level.


## Validation bugfix: producer-only reverse-flow protection
- BHP producer now shuts in when target BHP exceeds first-cell pressure instead of injecting.
- OIL_RATE control with active minimum-BHP constraint follows the same producer-only rule.
- This fix was triggered by T08 reverse-dissolution validation.

## T05 numerical-robustness fix
- Production convergence test with N=100 and DTMAX=3 min exposed a Newton failure at day 28.0769 as a gas-active cell crossed the maximum-Rs bubble-point kink (Pb=180 bar).
- Root cause: the positive finite-difference pressure perturbation straddled the piecewise-linear Rs_sat(P) kink/clamp and contaminated the numerical Jacobian.
- Fix: gas-active pressure derivatives now use a one-sided finite-difference perturbation that remains on the same saturated-PVTO segment. Physics, residual equations, tolerances, timestep controller, and well controls are unchanged.
- The same rule is applied to grouped and reference finite-difference Jacobians.

## Final 1.0.3 release — output/presentation layer
- Numerical core remains the exact build validated in the final T00-T11 production regression.
- Added `results.xlsx` to every standard OUTPUT with sheets `rates`, `profiles`, and `material_balance`.
- Added automatic PNG files: `oil_rate.png`, `gas_rate.png`, `GOR.png`, `BHP.png`, `pressure_profiles.png`, `Sg_profiles.png`, `Rs_profiles.png`.
- Profile PNGs include all SCHEDULE report times and use logarithmic radius on the X axis.
- Existing CSV/JSON/TXT outputs are retained unchanged.
- Internal `Nabor_0b.xlsx` and `Nabor_1b.xlsx` test fixtures moved from root `data/` to `tests/fixtures/`; user-facing package no longer contains an ambiguous `data/` directory.
- Added pinned runtime dependencies for final output generation: XlsxWriter 3.2.9 and Matplotlib 3.10.8.
- Short technical output smoke check confirmed that pre-existing `profiles.csv`, `rates.csv`, `material_balance.csv`, and `step_log.csv` are byte-for-byte identical to the validated beta output for the same short input.
