# Testing and validation layers

Prototype 1.0.3 has three deliberately separate test layers.

## 1. `tests/` — fast unit/physics/numerics suite

Run:

```powershell
python -m unittest discover -s tests -v
```

Validated result: `80/80 PASS` before and after final production regression.

This layer covers physics invariants, analytical radial checks, PVT/relperm behavior, sparse/dense and grouped/reference numerics, phase switching, schedule semantics, producer-only behavior, rate/BHP controls, material balance, diagnostics, failure handling and CLI/output contracts.

## 2. `regression/run_regression.py` — frozen software regression

Run all frozen Excel cases including T05:

```powershell
python .\regression\run_regression.py
```

Quick run without expensive T05:

```powershell
python .\regression\run_regression.py --quick
```

Single case:

```powershell
python .\regression\run_regression.py --case T00
```

This test intentionally uses the full production path `XLSX -> run_prototype.py -> OUTPUT`, then compares deterministic solver files against the golden outputs frozen from the externally validated build.

## 3. External IMEX validation evidence

The final scientific validation against fully implicit CMG IMEX is already completed and frozen in:

- `regression/evidence/Prototype_1.0.3_FINAL_PRODUCTION_REGRESSION_T00_T11.xlsx`
- `regression/evidence/FINAL_REGRESSION_METRICS_20260825a.json`
- `regression/reference_imex_xlsx/`
- `regression/reference_imex_normalized/`
- `regression/figures/`

The overall external-validation result is `PASS WITH DOCUMENTED NOTES`.
