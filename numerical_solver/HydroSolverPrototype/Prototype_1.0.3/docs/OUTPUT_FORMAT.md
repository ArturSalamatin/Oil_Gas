# OUTPUT format — Prototype 1.0.3

A successful run creates a folder with the input filename as its default name.

## CSV outputs

### `profiles.csv`
Reservoir profiles at every SCHEDULE report time:
- time, day
- cell
- radius, m
- pressure, bar(a)
- gas saturation Sg
- solution gas ratio Rs, Sm3/Sm3

### `rates.csv`
Well response at report times:
- oil rate, Sm3/day
- gas rate, Sm3/day
- GOR, Sm3/Sm3
- BHP, bar(a)
- active control mode
- constraint-active flag

### `step_log.csv`
Internal accepted/rejected timestep/Newton information.

### `material_balance.csv`
Oil- and gas-component inventories, well production, outer-boundary net flux and component-balance errors at report times. Gas current inventory is separated into dissolved and free gas.

## Excel output

### `results.xlsx`
One engineer-friendly workbook with three sheets:
- `rates` — same engineering quantities as `rates.csv`;
- `profiles` — same engineering quantities as `profiles.csv`;
- `material_balance` — same balance quantities as `material_balance.csv`.

The CSV files remain the machine-readable reference outputs; `results.xlsx` is an additional convenient presentation/export format.

## Automatic PNG plots

Rate/well plots:
- `oil_rate.png`
- `gas_rate.png`
- `GOR.png`
- `BHP.png`

Profile plots:
- `pressure_profiles.png`
- `Sg_profiles.png`
- `Rs_profiles.png`

All profile PNG files contain every report time defined by SCHEDULE. Radius is plotted on a logarithmic X axis.

## Run passport

### `run_summary.json` / `run_summary.txt`
Run passport and QC:
- Prototype version and exact validated-core build ID;
- input-format version;
- input file/path and SHA256;
- grid/timestep/Jacobian/linear-solver settings;
- wall time and accepted/rejected steps;
- requested/written report times;
- PVT/relperm warnings;
- report/state/control QC;
- material-balance QC;
- failure information when available.

`summary.json` is retained as a backward-compatible alias of `run_summary.json`.
