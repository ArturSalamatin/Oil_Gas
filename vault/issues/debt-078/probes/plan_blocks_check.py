"""DEBT-078: блоки «До/После» пробы plan_apply.py есть в тексте плана дословно.

    python vault\\issues\\debt-078\\probes\\plan_blocks_check.py
"""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PLAN = ROOT / "vault" / "plans" / "debt-078 co-undersaturated-table-check.md"

spec = importlib.util.spec_from_file_location("plan_apply", HERE / "plan_apply.py")
pa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pa)

plan = PLAN.read_text(encoding="utf-8").replace("\r\n", "\n")
ok = True
for i, (path, old, new) in enumerate(pa.EDITS + [pa.README_EDIT], start=1):
    for kind, block in (("До", old), ("После", new)):
        # в плане блок стоит внутри ```…``` — с переводом строки до и после
        found = ("\n" + block.rstrip("\n") + "\n```") in plan
        ok &= found
        print(f"{'OK ' if found else 'НЕТ'} {i:2d} {kind:5s} {path}")
print("все блоки найдены" if ok else "ЕСТЬ РАСХОЖДЕНИЯ")
