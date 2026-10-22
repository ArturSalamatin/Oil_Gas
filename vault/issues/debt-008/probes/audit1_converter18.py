"""Аудит 1 DEBT-008: конвертер примера 18 без start_day даёт ровно файл после strip_removed_keys.

Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\debt-008\\probes\\audit1_converter18.py
Конвертер не правится: его вывод в каталог пробы, затем ключ убирается из
словаря и файл пересобирается тем же json.dumps(indent=2, ensure_ascii=False).
"""
import importlib.util
import json
import sys
from dataclasses import fields
from pathlib import Path

SOLVER = Path.cwd()
PROBES = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBES))
import strip_removed_keys as srk  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "pi18", SOLVER / "examples" / "18_prototype_input" / "prototype_input.py")
pi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pi)

out = PROBES / "audit1_converter18_out"
pi.convert(pi.BOOK, out)
cfg = json.loads((out / "config.json").read_text(encoding="utf-8"))
del cfg["time"]["start_day"]
regenerated = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
stripped = srk.strip((SOLVER / "examples" / "18_prototype_input" / "config.json")
                     .read_text(encoding="utf-8"))
print("конвертер без start_day == файл после strip:",
      regenerated.splitlines() == stripped.splitlines())
for f in out.iterdir():
    f.unlink()
out.rmdir()

from gpn_multiphase_solver.io.config import (  # noqa: E402
    GeometryConfig, RockConfig, PVTConfig, RelPermConfig, ThermalConfig,
    InitialConfig, TimeConfig, NumericsConfig)
n = sum(1 for c in (GeometryConfig, RockConfig, PVTConfig, RelPermConfig, ThermalConfig,
                    InitialConfig, TimeConfig, NumericsConfig)
        for f in fields(c) if f.type == "float")
print("float-полей (_FLOAT_FIELDS):", n)
