# Final 1.0.3 Windows output check

The beta clean-room handoff test already passed. For the final 1.0.3 release, repeat the same `CleanRoom_T07.xlsx` calculation to verify the output-only additions on Windows.

## Run

```powershell
python .\run_prototype.py .\INPUT\CleanRoom_T07.xlsx
```

If `--output` is omitted, expected folder:

```text
OUTPUT\CleanRoom_T07\
```

## Required PASS checks

1. `run_summary.txt` contains `STATUS: SUCCESS`.
2. Existing outputs remain present:
   - `profiles.csv`
   - `rates.csv`
   - `material_balance.csv`
   - `step_log.csv`
   - `run_summary.json`
   - `run_summary.txt`
3. New Excel output exists:
   - `results.xlsx`
   - sheets: `rates`, `profiles`, `material_balance`
4. New PNG outputs exist:
   - `oil_rate.png`
   - `gas_rate.png`
   - `GOR.png`
   - `BHP.png`
   - `pressure_profiles.png`
   - `Sg_profiles.png`
   - `Rs_profiles.png`
5. Profile plots show all SCHEDULE report times.
6. `results.xlsx` contains the same engineering results as the corresponding CSV files.
7. No Python source editing is required.

Negative/invalid Excel tests remain intentionally deferred.
