# Prototype 1.0.3 — unit-test audit before final production regression

## Evidence used

The archived Prototype 1 unit-test manifest (`UNIT_TESTS.md`, 2026-08-23) documents these legacy groups:
`test_physics`, `test_grouped_jacobian`, `test_sgc_phase_mobility`, `test_strong_degassing_recovery`,
`test_producer_control_semantics`, `test_oil_rate_control`, `test_case_config_and_dtmax`,
`test_model_invariants`, `test_results_io`.
The Prototype 1.0.2 regression summary records 48/48 unit tests PASS.

The exact 48 individual historical source functions are not present in the recovered 1.0.3 archive. Therefore this audit does not claim a one-to-one recovery by historical function name. It restores every documented behavior group and keeps all 16 tests that were present in the post-T05 1.0.3 package.

## Mapping

| Legacy behavior | 1.0.3 hardening coverage | Decision |
|---|---|---|
| No free gas above Pb | `test_physics.py` | restored |
| Gas appears below Pb | `test_physics.py` | restored |
| Component balance | `test_physics.py`, `test_material_balance.py` | expanded |
| Grouped/reference Jacobian equality | `test_grouped_jacobian.py` | restored |
| Sparse/dense one-step equality | `test_grouped_jacobian.py` | added/retained sparse validation |
| Phase existence independent of gas mobility | `test_sgc_phase_mobility.py` | restored |
| Strong degassing active-set recovery | `test_strong_degassing_recovery.py` | restored |
| Producer cannot reverse to injection | `test_producer_only.py` | retained from 1.0.3 |
| Rate control / BHP floor | `test_rate_control.py` | retained |
| DTMAX honored | `test_case_config.py` | restored |
| Input restricted to `data/` | replaced by `input_can_be_outside_data_directory` | intentionally retired: current product contract allows arbitrary XLSX path |
| Workbook parameters build geometry/model | `test_case_config.py`, `test_input_contract.py` | restored |
| Radial volume / hydraulic resistance invariants | `test_model_invariants.py` | restored |
| One-phase radial analytical rate | `test_model_invariants.py` | added explicit analytical check |
| Rock PV law | `test_model_invariants.py` | restored |
| PVT saturated nodes / endpoint behavior | `test_model_invariants.py`, `test_pvt_clamp.py` | expanded |
| Relperm bounds/endpoints | `test_model_invariants.py`, `test_sgc_phase_mobility.py` | restored |
| Repressurization / redissolution | `test_physics.py` | restored |
| Result XLSX writer | replaced by CSV + `run_summary` output-contract tests | intentionally retired: current output contract is CSV/JSON/TXT, not result XLSX |
| Exact SCHEDULE/report semantics | `test_schedule_reporting.py`, `test_input_contract.py` | retained from 1.0.3 |
| PVTO-kink FD Jacobian robustness | `test_pvt_kink_jacobian.py` | retained from T05 fix |
| PVT no-extrapolation + warnings | `test_pvt_clamp.py` | new |
| Runtime sanity checks | `test_diagnostics.py` | new |
| Material-balance history/output | `test_material_balance.py`, `test_output_contract.py` | new |
| Clean failure with partial history/output | `test_failure_semantics.py`, `test_runner_failure.py` | new |
| PowerShell/CLI path/output/reproducibility behavior | `test_cli_workflow.py` | new |

## Result

Current fast suite: **79 tests**. All PASS before T00–T11 final regression.

This suite is intentionally separate from the production regression cases T00–T11.
