# Quick start — Prototype 1.0.3

## 1. Prepare Python

Validated numerical environment: Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0. The final output layer additionally uses XlsxWriter 3.2.9 and Matplotlib 3.10.8.

Recommended clean installation from the Prototype directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 2. Create a working input

Do not edit the master template directly. Copy:

```text
INPUT_TEMPLATE.xlsx -> INPUT\My_Model.xlsx
```

Edit the copy in Microsoft Excel.

## 3. Run

```powershell
python .\run_prototype.py .\INPUT\My_Model.xlsx
```

Default result folder:

```text
OUTPUT\My_Model\
```

## 4. Check the calculation

Open `OUTPUT\My_Model\run_summary.txt` first. Required successful status:

```text
STATUS: SUCCESS
```

Then check:
- report/state/material QC are `True`;
- material-balance errors are below the reported tolerance;
- `WARNINGS` are understood;
- especially check PVT/relperm range warnings before using the result quantitatively.

For engineering review use `results.xlsx` and the automatically generated PNG plots. CSV files remain available for machine processing.
