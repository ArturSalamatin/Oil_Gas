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

## Local changes — GPN project (BUG-014)
- Problem: a long step after BHP is raised above the first-cell pressure did not converge at any step split. Two mechanisms: (1) the producer-only well branch (open/shut) was chosen from the current Newton iterate — the first iterate is below BHP, the well is shut, and on that branch the step has no consistent solution; (2) free gas dissolving in the near-well zone drove trial points below `Sg = -0.05`, and the line search rejected them all; the phase active set switches cells only after convergence.
- `advance()` first runs the original algorithm (now `_advance_phases()`, unchanged). If it converges, the result is bitwise the same as before.
- Only on failure, a fallback: `_sg_lower_bound = None` (no lower bound on Sg of two-phase cells — method of negative saturations; Sg < 0 is a smooth extension of the cell equations and the phase active set switches such cells after convergence). BHP control additionally fixes the well branch for the whole solve (`_well_branch`): start from the old state (`p0 <= BHP` → shut), accept only a consistent result (open → `p0 >= BHP`, shut → `p0 <= BHP`), otherwise try the other branch once. OIL_RATE control: a plain retry without the Sg bound.
- Outside `advance()` both attributes keep their defaults (`None`, `-0.05`), also after an exception (`try/finally`); `well_rates()` and `face_component_fluxes_sm3s()` choose the branch from `p0` as before.
- `BlackOilNewtonReport`: new fields `well_branch` (BHP control, branch of the accepted step), `well_switches`, `fallback` — with defaults, positional construction unchanged.
- Physics, residual equations, tolerances and well semantics (producer only, no injection) are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/42; plan: `vault/plans/bug-014 well-shutin-active-set.md` of the GPN project.

## Local changes — GPN project (BUG-016)
- Problem: with a high initial Rs (Rs0 = 150) and a sharp BHP drop, the first step did not converge on grids N >= 100 at any step split. The phase active set activates tens of cells at once with a closed-flash Sg guess (0.55-0.71 against 0.22 in the solution); the Newton direction then does not decrease ||F||_inf for any alpha, and the line search (12 halvings) stalls. The BUG-014 fallback fails the same way.
- `advance()`: a third stage, only when the original algorithm and the BUG-014 fallback both fail — the fallback (moved verbatim into `_fallback()`) is run again with `_line_search_l2 = True` (a Newton step is accepted on a decrease of ||F||_2; the convergence test stays on ||F||_inf) and `_sg_step_max = 0.2` (the whole update is scaled so that |dSg| of two-phase cells <= 0.2, as ds_max in OPM Flow). Wherever the first two stages converge, results are bitwise the same as before.
- Outside `advance()` both attributes keep their defaults (`False`, `None`), also after an exception (`try/finally`).
- `BlackOilNewtonReport`: new field `globalized` (the third stage ran), default `False`.
- Effect on the GPN examples: 13 of 17 bitwise; 04a, 11, 12, 13b no longer split their first step (99.8 -> 40 s, 6.6 -> 3.6 s, 27.6 -> 15 s, 69.6 -> 56.8 s); first-step splitting of 04a on N = 150...500 drops from 512...16384 to 1...8 substeps.
- Physics, residual equations, tolerances and well semantics are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/44; plan: `vault/plans/bug-016 newton-line-search-norm.md` of the GPN project.
