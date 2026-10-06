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

## Local changes — GPN project (DEBT-029): regression golden outputs refrozen
- `regression/golden/` refrozen for T03, T04, T05S_N100_DT5m, T05T_N100_DT10m, T05T_N100_DT3m, T05T_N100_DT60m (all five files of each), taken from `run_regression.py` on GPN commit `00af963` (BUG-014, BUG-016, BUG-018 included). The other 11 jobs still reproduce the original golden bitwise and are unchanged.
- Cause: in these cases the original algorithm fails on the first steps (the old golden rejected 60, 30, 15 s ...); the BUG-014/016 fallback stages of `advance()` now solve them (T03: 15 s, T04: 30 s), so the step sequence differs from the first step on. Differences to the old golden decay from 0.83 / 1.7 bar (T03 / T04) at 1 min to about 1e-3 bar at 1 day and 1e-5 bar at 30 days; QC passes everywhere. The PVT range warning text changes as well (maximum gas-active pressure).
- External IMEX validation, metrics of `regression/evidence/FINAL_REGRESSION_METRICS_20260825a.json` recomputed for T03 / T04: stable acceptance at 1-30 days unchanged (T03 `max_abs_dp_bar` 0.18407 -> 0.18394, all T04 metrics within 1 %). At 1 min, outside acceptance, the agreement is worse; a time-refinement study of the first minute shows that the dt -> 0 limit of the prototype deviates from IMEX at 1 min more than either golden, so the old 1-min agreement was error cancellation, not accuracy. T05 convergence metrics: upper-bound shift about 6 %, not recomputed.
- Hence the statements in `README.md`, `docs/TESTING.md` and `regression/README.md` that `golden/` is the output of the externally validated build hold for 11 of the 17 jobs. `regression/evidence/` is unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Record: DEBT-029 in `vault/roadmap/` of the GPN project.

## Local changes — GPN project (DEBT-033): vectorized grouped Jacobian
- Problem: the grouped finite-difference Jacobian took 72-81 % of the run time of the GPN examples; at N = 350 half of the run time was bookkeeping around its six residual evaluations: a Python loop over cells per colour (`_pressure_fd_step` per cell, `np.arange`, row writes into a dense 2N x 2N matrix) and `csc_matrix(J)` scanning all 4N^2 entries in `_linear_solve()`.
- `_fd_steps()`: perturbation steps of all 2N unknowns at once, elementwise the same arithmetic as `_pressure_fd_step()` and the Rs/Sg step rule.
- `finite_difference_jacobian_grouped()`: entries written by array slicing per colour, the matrix assembled directly as CSC (`coo_matrix(...).tocsc()`, `eliminate_zeros()`); it returns a `scipy.sparse.csc_matrix` instead of a dense array. Same steps, the same residual evaluations in the same order, the same entries `df/h`: bitwise the former matrix and the same CSC arrays as `csc_matrix(dense)`, so SuperLU gets the same input. `reference` mode still returns a dense array.
- `_linear_solve()` accepts sparse or dense J (`linear_solver='dense'` uses `J.toarray()`).
- Effect (GPN examples, run time before -> after, same Newton iterations): N = 350 Standing PVT 14.6 -> 6.0 s (x2.45), N = 350 tabular PVT 59.6 -> 40.0 s (x1.49), N = 150 1.08 -> 0.69 s, N = 50 1.28 -> 1.18 s; Jacobian bookkeeping at N = 350: 8.9 -> 0.56 s. Prototype tests 83 passed (3 new: steps vs `_pressure_fd_step`, CSC bitwise vs `reference`, whole steps bitwise grouped vs reference); full regression 17/17 PASS; the 20 GPN examples reproduce their histories bitwise.
- Physics, residual equations, tolerances and Newton/active-set logic are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/52; plan: `vault/plans/debt-033 vectorize-grouped-jacobian.md` of the GPN project.

## Local changes — GPN project (DEBT-030): report of a rejected step
- Problem: when all three stages of `advance()` failed, the report of the last `_advance_phases()` call was returned. Under BHP control that is usually the 'shut' branch: on an unchanged state it "converges" in 0 iterations with ||F||_inf = 0 and is dropped as inconsistent, so `step_log.csv`, the `failure` block of `run_summary.json` and the GPN adapter's debug message showed every rejected step as "0 iterations, residual 0".
- `advance()`: if the third stage fails too, the Newton fields of the report (`iterations`, `residual_inf`, `active_set_iterations`, `phase_switches`) are the original algorithm's, as before BUG-014; the branch fields (`well_branch`, `well_switches`, `fallback`, `globalized`) stay the last attempt's. Accepted steps and the step sequence are unchanged: full regression 17/17 PASS.
- `newton_iterations` in `step_log.csv` keeps its meaning (accepted rows: sum over the phase active-set loop; rejected rows: the failed Newton solve), now documented in `docs/OUTPUT_FORMAT.md`.
- `regression/golden/*/step_log.csv` refreshed for the six DEBT-029 jobs (T03, T04, T05S_N100_DT5m, T05T_N100_DT10m, T05T_N100_DT3m, T05T_N100_DT60m): the 7 rejected rows "0, 1, 0, 0.0" replaced by the original algorithm's reports (T03 60 s / 30 s: 15, 2, 21, 5.61e-5 / 15, 2, 18, 6.89e-5; T04 and the four T05 jobs on N = 100, 60 s: 15, 2, 21, 2.35e-7), taken from the full regression run that passed 17/17; all other rows and the other four files of these jobs are unchanged. `step_log.csv` is not compared by `run_regression.py`. In T05S_N200_DT5m (authors' golden, not refreshed) the rejected rows again match the golden in all integer columns; `residual_inf` differs at round-off in every row of this job, as before.
- Tests: `tests/test_failure_report.py` (first step of T04). Physics, residual equations, tolerances and Newton/active-set logic are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/62; plan: `vault/plans/debt-030 rejected-step-report.md` of the GPN project.
