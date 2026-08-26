# Prototype 1.0.3 — result of tasks 1–15

Status: pre-beta hardening completed; final T00–T11 production regression NOT started.

- Unit-test audit performed from recovered 1.0.2 documentation and current 1.0.3 source. Historical 1.0.2 summary confirms 48/48; exact 48 source functions were not recoverable, but every documented legacy behavior group was restored/replaced and current T05/T08 fixes retained.
- Current fast suite: 79/79 PASS.
- Oil/gas component material balance added at report times and written to `material_balance.csv`; summary contains max relative errors and QC status.
- Run summary added: version/build/input-format IDs, SHA256 of input, model/numerical settings, runtime, steps, reports, warnings, material-balance and sanity QC.
- PVT/relperm out-of-range policy implemented: no linear extrapolation, endpoint clamp, WARNING in run summary. PVTO Rs interpolation was explicitly changed from extrapolating beyond Rs range to endpoint clamp.
- Cheap runtime sanity/control checks added.
- T07-based `INPUT_TEMPLATE.xlsx` created with 10/20/30/40/50/60 s boundaries after BHP steps at days 5 and 15; COMMENTS includes the range policy and workflow.
- Automatic output rule implemented: omitted `--output` => `OUTPUT/<input stem>/` under Prototype root.
- Reproducibility/CLI checks added: explicit output, automatic output, path with spaces, repeated deterministic run, existing output directory.
- Clean calculation-failure path tested: FAILED summary and partial standard output are written before the CLI exits with an error code.
- Windows/clean-room items that cannot be certified here are listed in `docs/NOT_TESTED_HERE.md`.
- Negative Excel tests remain intentionally deferred until 1.0.3 beta.
- Regression input copies have been prepared with COMMENTS policy text, but T00–T11 have not been executed.
- `INPUT_TEMPLATE.xlsx` smoke run completed: SUCCESS, 781 accepted / 0 rejected, all 23 requested report times written, material balance QC PASS. One intentional range warning occurred because a gas-active accepted state briefly reached 182.14 bar above the max saturated-locus Pb=180 bar; endpoint Rs was used with no extrapolation.
- A short in-range case was compared pre-hardening vs hardening build: maximum deltas were approximately 4.1e-10 bar in pressure, 2.5e-13 in Sg, 5.0e-11 in Rs and 1.1e-9 Sm3/day in gas rate (floating-point level).
