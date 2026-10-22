"""DEBT-071, аудит 1: строки кода длиннее 100 символов в блоках ```python плана (без f-строк прототипа).

Запуск из корня проекта: numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-071\\probes\\audit1_long_lines.py
"""
from pathlib import Path

PLAN = Path("vault/plans/debt-071 standing-relperm-range-check.md")
inb, ind, out = False, 0, []
for i, line in enumerate(PLAN.read_text(encoding="utf-8").splitlines(), 1):
    s = line.strip()
    if s.startswith("```"):
        if not inb:
            inb, ind = s == "```python", len(line) - len(line.lstrip())
        else:
            inb = False
        continue
    if inb:
        code = line[ind:]
        if len(code) > 100 and "w.append" not in code:
            out.append((i, len(code), code.strip()[:80]))
for i, n, c in out:
    print(f"план:{i} длина {n}: {c}")
print(f"итог: {len(out)}")
