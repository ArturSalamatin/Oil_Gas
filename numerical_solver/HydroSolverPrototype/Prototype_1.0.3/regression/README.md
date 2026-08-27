# Regression package

This folder separates two concepts:

1. **Frozen software regression**: `run_regression.py` reruns the production XLSX inputs through `run_prototype.py` and compares the deterministic solver outputs against `golden/`, which was frozen from the exact build that passed final external validation.
2. **External scientific validation**: `evidence/`, `reference_imex_xlsx/`, `reference_imex_normalized/` and `figures/` document the completed comparison against fully implicit CMG IMEX.

Full regression, including six T05 convergence calculations:

```powershell
python .\regression\run_regression.py
```

Quick regression without T05:

```powershell
python .\regression\run_regression.py --quick
```

Single case:

```powershell
python .\regression\run_regression.py --case T00
```

The full T05 block is intentionally expensive and is not intended as a normal user workflow.
