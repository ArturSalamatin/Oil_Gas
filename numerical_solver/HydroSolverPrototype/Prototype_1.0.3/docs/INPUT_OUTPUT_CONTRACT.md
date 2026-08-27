# Input/output contract — Prototype 1.0.3

## Normal PowerShell run

`python .\run_prototype.py .\INPUT\My_Model.xlsx`

If `--output` is omitted, output is created under the Prototype root as:
`OUTPUT\My_Model\`.

Explicit output remains supported:
`python .\run_prototype.py .\INPUT\My_Model.xlsx --output D:\Results\Case01`

## Required successful-run files

- `profiles.csv`
- `rates.csv`
- `step_log.csv`
- `material_balance.csv`
- `run_summary.json`
- `run_summary.txt`
- `summary.json` (backward-compatible alias)

## PVT / relperm range policy

No linear extrapolation. Endpoint values / endpoint branches are used (clamp).
Accepted-state range exceedance is reported as a WARNING in `run_summary`.
Repeated/material warnings mean the engineering input table should be extended.
