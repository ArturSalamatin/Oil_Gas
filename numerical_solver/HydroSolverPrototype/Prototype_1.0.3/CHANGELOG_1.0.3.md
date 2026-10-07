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

## Local changes — GPN project (DEBT-036): faster residual on tabular PVT
- Problem: on a tabular PVTO one residual cost 3.5 ms at N = 350 against 0.9 ms with the Standing adapter: `_oil_prop` interpolated with a Python loop over Rs segments (a mask and two `np.interp` per segment, 14 segments in a 19-branch table), `component_inventories()` evaluated and dropped mu_o, mu_g, the inventories of the old state were recomputed on every residual of a step, and the faces evaluated Bo and mu_o in separate passes.
- `BlackOilPVT`: `_oil_props()` evaluates all cells at once from tables built in `__init__` (`_build_interp_tables()`: branch rows with np.interp's own slopes, a map from the union of all branch knots to the row of each branch, segment differences); `bo()`, `mu_o()` keep their signature and values; new `bo_mu_o()` returns both from one segment and row search. `_branch_prop_delta()` removed. A table with a single Rs branch is rejected (`ValueError`): it used to give NaN Bo, mu_o everywhere.
- `RadialBlackOilModel`: `component_inventories()` takes `pvt.bo`, `pvt.bg` only; `physical_residual()` takes the old-state inventories from `_old_inventories()`, a one-entry cache keyed by the bytes of p, Rs, Sg; `_phase_mobilities_surface()` calls `pvt.bo_mu_o` where the PVT has it.
- Bitwise: Bo and mu_o equal the former loop on all project tables (4.1 million points incl. knots, one ulp off them, NaN, +inf); residuals, Newton steps (the same Jacobian counts), the 20 GPN examples and the quick regression (11/11 PASS) are unchanged. The only difference: +inf pressure raises a RuntimeWarning (0*inf in a discarded `np.where` branch); the prototype never evaluates PVT there.
- Effect (GPN examples, run time before -> after): N = 350 tabular PVT (19 branches) 43.8 -> 14.4 s, residuals inside the Jacobian 33.5 -> 8.3 s; N = 350 Standing PVT 6.3 -> 5.0 s; N = 50 tabular 1.3 -> 0.9 s, N = 150 Standing 0.72 -> 0.62 s. One residual at N = 350: 3.49 -> 0.74 ms (19-branch table), 0.88 -> 0.57 ms (Standing). Prototype tests 92 passed (9 new: inventories without viscosities, the old-state cache, bitwise PVTO against the former loop, shapes, the single-branch check, `bo_mu_o`, the face mobilities); full regression 17/17 PASS (with T05, on `f79c753`).
- Physics, residual equations, tolerances and Newton/active-set logic are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/59; plan: `vault/plans/debt-036 table-pvt-residual-speedup.md` of the GPN project.

## Local changes — GPN project (DEBT-030): report of a rejected step
- Problem: when all three stages of `advance()` failed, the report of the last `_advance_phases()` call was returned. Under BHP control that is usually the 'shut' branch: on an unchanged state it "converges" in 0 iterations with ||F||_inf = 0 and is dropped as inconsistent, so `step_log.csv`, the `failure` block of `run_summary.json` and the GPN adapter's debug message showed every rejected step as "0 iterations, residual 0".
- `advance()`: if the third stage fails too, the Newton fields of the report (`iterations`, `residual_inf`, `active_set_iterations`, `phase_switches`) are the original algorithm's, as before BUG-014; the branch fields (`well_branch`, `well_switches`, `fallback`, `globalized`) stay the last attempt's. Accepted steps and the step sequence are unchanged: full regression 17/17 PASS.
- `newton_iterations` in `step_log.csv` keeps its meaning (accepted rows: sum over the phase active-set loop; rejected rows: the failed Newton solve), now documented in `docs/OUTPUT_FORMAT.md`.
- `regression/golden/*/step_log.csv` refreshed for the six DEBT-029 jobs (T03, T04, T05S_N100_DT5m, T05T_N100_DT10m, T05T_N100_DT3m, T05T_N100_DT60m): the 7 rejected rows "0, 1, 0, 0.0" replaced by the original algorithm's reports (T03 60 s / 30 s: 15, 2, 21, 5.61e-5 / 15, 2, 18, 6.89e-5; T04 and the four T05 jobs on N = 100, 60 s: 15, 2, 21, 2.35e-7), taken from the full regression run that passed 17/17; all other rows and the other four files of these jobs are unchanged. `step_log.csv` is not compared by `run_regression.py`. In T05S_N200_DT5m (authors' golden, not refreshed) the rejected rows again match the golden in all integer columns; `residual_inf` differs at round-off in every row of this job, as before.
- Tests: `tests/test_failure_report.py` (first step of T04). Physics, residual equations, tolerances and Newton/active-set logic are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/62; plan: `vault/plans/debt-030 rejected-step-report.md` of the GPN project.

## Local changes — GPN project (BUG-021): Newton convergence tested on every new iterate
- Problem: `_newton_fixed_active_set()` tested ||F||_inf against the tolerance only at the top of an iteration, before the update. After the update of iteration `max_iter` (15) the loop ended; the residual of the new iterate was computed but not compared, so a solve that converged on its last allowed update was reported as failed and the step was rejected and halved (T05S_N200_DT5m: dt = 3.75 s, 15 iterations, ||F||_inf = 4.2e-16).
- Convergence is now tested right after each accepted line-search point, on the residual the line search has already evaluated, the last update included; a start that already meets the tolerance returns before the loop with 0 iterations. That residual is bitwise the `f0` the Jacobian call returns at the same point, so wherever the solve converged before, iterates, iteration counts and residuals are bitwise unchanged, and the Jacobian that was built only to detect convergence is no longer built (one per converged solve: 30-48 % of the Jacobians of the regression jobs).
- Regression: 16 of 17 jobs reproduce the golden outputs bitwise. T05S_N200_DT5m now accepts its 3.75 s step (19 iterations) instead of rejecting it: accepted/rejected steps 8689/5 -> 8675/4; against the former golden, max |dp| is 0.23 bar at 1 min, 1.4e-4 bar at 1 day and 2.6e-6 bar at 30 days. There is no IMEX reference for T05; the spatial convergence metric `spatial_100_200` (p_max 0.060 bar) moves by at most 0.2 %. All five golden files of T05S_N200_DT5m are refrozen from the run on the fixed code, so the statements in `README.md`, `docs/TESTING.md` and `regression/README.md` that `golden/` is the output of the externally validated build now hold for 10 of the 17 jobs (11 after DEBT-029).
- Effect on the GPN examples: 19 of 21 bitwise; 14 differs at round-off (its second step is accepted by the original algorithm, no longer by the third stage); 13b no longer splits the first hour of day 2 into 2 x 1800 s (max |dp| 392 Pa at 1.5 days, about 1 Pa at 30 days). Run time without other load: the 21 GPN examples 128.4 -> 98.4 s, the quick regression 174.7 -> 129.4 s.
- Tests: `tests/test_newton_last_iteration.py` (4 new: convergence on the last allowed update, the limit not relaxed, no Jacobian only for the convergence test, a converged start). Physics, residual equations, tolerances and active-set logic are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/64; plan: `vault/plans/bug-021 newton-final-iterate-check.md` of the GPN project.

## Local changes — GPN project (BUG-020): fourth stage of advance (off by default)
- Problem: shut-in (q_oil = 0, or BHP raised to the outer pressure) after production with a developed gas zone (Sg near the well 0.4, GPN examples 19-21) did not converge at any step split. (1) First step: once the well is shut, the well cell is upstream of no face, and its gas storage per unit Sg, 1/Bg - Rs/Bo, is small at low pressure (7.4 at 51 bar against 38.9 at 200 bar); the first Newton direction asks |dSg| ~ 0.7*dt[s] there. The original bound Sg >= -0.05 rejects every trial, the BUG-014 fallback overshoots to Sg = -23...-1137, the BUG-016 third stage scales the whole update by 0.2/|dSg| and the pressure stalls. (2) Later steps: in the stagnant undersaturated zone near the shut well the upstream cell of 1-11 faces flips every Newton iteration; the Newton needs ~26 iterations against the limit 15.
- `advance()`: a fourth stage, only when the three existing stages fail and only with the new constructor argument `phase_switching_stage=True` (default `False`). It is the BUG-014 fallback (`_fallback`: well branches, consistency check) with `_advance_phases` routed to the new `_newton_switching()`: the phase active set is switched after every Newton iteration (`_switch_phases()`: a two-phase cell with Sg < 0 becomes undersaturated with the Rs that keeps its gas/oil ratio; an undersaturated cell with Rs > Rs_sat becomes two-phase with the closed-flash Sg and the BUG-018 cap); updates are limited per cell (|dp| <= 0.3 p, |dSg| <= 0.2, as dpMaxRel, dsMax of OPM Flow); no line search; faces whose flow direction flipped twice keep their upstream cell (`_upwind_frozen`, read by `face_component_fluxes_sm3s`) until convergence, then a polish without holding returns the original upwind scheme; at most 40 iterations, the residual after the last update is checked; a root with two-phase Sg > 0.98 is rejected.
- With the default `phase_switching_stage=False` the prototype runs exactly the former code: regression 17/17 PASS bitwise, golden outputs unchanged. With the stage on (the GPN factory), steps the first three stages solve stay bitwise.
- `BlackOilNewtonReport`: new field `phase_switching` (the fourth stage ran), default `False`.
- Physics, residual equations, tolerances and well semantics are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/63; plan: `vault/plans/bug-020 shutin-phase-switching-newton.md` of the GPN project.
