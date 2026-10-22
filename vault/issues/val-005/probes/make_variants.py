"""Проба VAL-005: варианты черновика с намеренной ошибкой конвертации — ловит ли их сверка с прототипом.

Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\val-005\\probes\\make_variants.py
"""
import json
import shutil
from pathlib import Path

P = Path(__file__).parent
base = json.loads((P / "draft_18" / "config.json").read_text(encoding="utf-8"))

variants = {
    "cr0": lambda c: c["rock"].__setitem__("compressibility", 0.0),           # потерянная сжимаемость породы
    "k101": lambda c: c["rock"].__setitem__("permeability", c["rock"]["permeability"] * 1.01),  # k на 1 %
    "skin01": lambda c: c["numerics"].__setitem__("skin", 0.1),                # скин 0.1 вместо 0
    "dt86400": lambda c: c["time"].__setitem__("dt_integration", 86400.0),     # суточный шаг
    "dt600": lambda c: c["time"].__setitem__("dt_integration", 600.0),         # шаг 10 мин
}
for name, change in variants.items():
    d = P / f"draft_18_{name}"
    d.mkdir(exist_ok=True)
    for f in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
        shutil.copy(P / "draft_18" / f, d / f)
    cfg = json.loads(json.dumps(base))
    change(cfg)
    (d / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(d)
