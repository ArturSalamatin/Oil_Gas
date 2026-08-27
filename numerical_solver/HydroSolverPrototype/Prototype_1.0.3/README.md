# Prototype 1.0.3

Final 1D radial isothermal oil-gas black-oil research simulator with Excel input.

**Version:** `1.0.3`  
**Numerical core validated build:** `1.0.3-prebeta-final-regression-20260825a`  
**Input format:** `1.0.3`  
**External validation:** final production regression T00-T11 completed against fully implicit CMG IMEX references; overall result `PASS WITH DOCUMENTED NOTES`.

The final 1.0.3 release keeps the validated numerical core unchanged. Relative to the validated beta package, only the output/presentation layer and package layout were changed: `results.xlsx`, automatic PNG plots, and migration of internal test fixtures from the root `data/` folder into `tests/fixtures/`.

## Normal PowerShell workflow

1. Copy `INPUT_TEMPLATE.xlsx` to `INPUT\\My_Model.xlsx`.
2. Edit the copy in Excel.
3. From the Prototype root run:

```powershell
python .\run_prototype.py .\INPUT\My_Model.xlsx
```

If `--output` is omitted, results are written automatically to:

```text
OUTPUT\My_Model\
```

Explicit output path is also supported:

```powershell
python .\run_prototype.py .\INPUT\My_Model.xlsx --output "D:\Results\My_Model"
```

## Successful OUTPUT

Tabular files:
- `profiles.csv`
- `rates.csv`
- `material_balance.csv`
- `step_log.csv`
- `results.xlsx` with sheets `rates`, `profiles`, `material_balance`
- `run_summary.json`
- `run_summary.txt`
- `summary.json` (backward-compatible alias)

Automatic PNG plots:
- `oil_rate.png`
- `gas_rate.png`
- `GOR.png`
- `BHP.png`
- `pressure_profiles.png`
- `Sg_profiles.png`
- `Rs_profiles.png`

Profile plots contain **all report times from SCHEDULE** and use logarithmic radius on the X axis.

`run_summary` includes version/build/input SHA256, numerical settings, accepted/rejected timesteps, report-time QC, physical/control QC, material-balance QC and PVT/relperm warnings.

## PVT / relperm range policy

No linear extrapolation is performed. When an accepted state is outside a supplied tabular range, the nearest endpoint/endpoint branch is used (`clamp`) and a `WARNING` is written to `run_summary`. Repeated warnings mean the engineering input table should be extended.

## Tests and validation

Fast internal suite:

```powershell
python -m unittest discover -s tests -v
```

The validated core had **80/80 PASS** before and after the final production regression. The Windows clean-room test of the beta package also passed. Negative/invalid Excel acceptance tests remain intentionally deferred.

Frozen software regression:

```powershell
python .\regression\run_regression.py
```

This reruns the frozen production Excel cases and compares the numerical CSV outputs with the exact golden outputs of the validated core build. The final output-only additions do not alter those golden numerical results.

## Documentation

Start with:
- `docs\QUICK_START.md`
- `docs\INPUT_FORMAT.md`
- `docs\OUTPUT_FORMAT.md`
- `docs\TESTING.md`
- `docs\VALIDATION_STATUS.md`
- `docs\RELEASE_NOTES_1.0.3.md`
