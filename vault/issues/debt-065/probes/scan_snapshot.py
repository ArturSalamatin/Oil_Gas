"""Проба DEBT-065: строки про фронт и R_s в снимке вывода примеров DEBT-011.

Снимок snap_before.json (проба DEBT-011 snapshot_examples.py) хранит печать
main.py всех примеров. Здесь — только строки, где упоминается фронт, изобара
или проверка R_s: по ним видно, у каких примеров печатается r_b и в каком
виде (число / nan).

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-065\\probes\\scan_snapshot.py <снимок.json>
"""

import json
import re
import sys
from pathlib import Path

snap = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["examples"]
pat = re.compile(r"фронт|изобар|r_b|Rs|R_s|pb|p_b", re.IGNORECASE)
for name, e in snap.items():
    lines = [s for s in e["stdout"].splitlines() if pat.search(s)]
    print(f"== {name} (код {e['returncode']})")
    for s in lines:
        print(f"   {s}")
