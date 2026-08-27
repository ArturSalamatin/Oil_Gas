# Prototype 1.0.3 — final release notes

Prototype 1.0.3 is released on top of the exact numerical core build that passed the final T00-T11 production regression: `1.0.3-prebeta-final-regression-20260825a`.

Validated numerical/physics changes already included before final release:
- SCHEDULE rows are exact integration/report/control boundaries;
- producer-only protection against reverse injection;
- numerical Jacobian robustness at the maximum-Rs PVTO kink;
- sparse production linear solver;
- component material-balance output and QC;
- run passport (`run_summary`) with build/input hash/settings/warnings/QC;
- no PVT/relperm linear extrapolation: endpoint clamp + warning;
- automatic `OUTPUT\<input name>\` when `--output` is omitted;
- restored/expanded 80-test unit/physics/contract suite;
- frozen production regression inputs/golden outputs and external IMEX validation evidence;
- engineer-facing `INPUT_TEMPLATE.xlsx` based on the T07 BHP/degas scenario.

Final external validation result: `PASS WITH DOCUMENTED NOTES`.

Windows clean-room handoff test of the beta package: `PASS`.

## Final-release-only changes after validation

These changes are deliberately limited to output/presentation and package organization; the numerical core was not changed:
- added `results.xlsx` with sheets `rates`, `profiles`, `material_balance`;
- added automatic PNG plots for oil rate, gas rate, GOR, BHP, pressure profiles, Sg profiles and Rs profiles;
- profile PNGs include all SCHEDULE report times and logarithmic radius;
- internal `Nabor_0b.xlsx` / `Nabor_1b.xlsx` test data moved from root `data/` to `tests/fixtures/`;
- documentation updated for final 1.0.3 packaging.

Negative/invalid Excel acceptance tests are intentionally deferred by project decision.
