"""DEBT-027, проба при /issue: у каких табличных примеров R_s0 = последняя ветвь PVTO (кандидаты на ложное 'saturated locus above table').

Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\debt-027\\probes\\rs0_last_branch.py
"""
import csv
import json
from pathlib import Path

SOLVER = Path.cwd()
for cfg in sorted((SOLVER / "examples").glob("*/config.json")):
    c = json.loads(cfg.read_text(encoding="utf-8"))
    if c["pvt"].get("model") != "table":
        continue
    with open(cfg.parent / c["pvt"]["oil_pvt_file"], encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rs_last = max(float(r["Rs_sm3_sm3"]) for r in rows)
    gas = [float(r["pressure_Pa"]) for r in csv.DictReader(open(cfg.parent / c["pvt"]["gas_pvt_file"], encoding="utf-8"))]
    pwf = [h.get("p_wf", h.get("min_bhp")) for h in c["time"]["history"]]
    pwf = [p for p in pwf if p is not None]
    print(f"{cfg.parent.name:32s} Rs0 = {c['initial_conditions']['Rs0']:6g}, последняя ветвь {rs_last:6g}, "
          f"газ. таблица от {min(gas) / 1e6:g} МПа, min p_wf = {min(pwf) / 1e6 if pwf else float('nan'):g} МПа")
