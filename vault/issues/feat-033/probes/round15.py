"""Решение 63 плана FEAT-033: демо-таблицы генератора — с 15 значащими цифрами.

Переписывает литералы float в блоках DEMO_* файла plan_code/workbook_template.py
на repr(float(f"{x:.15G}")): число с ≤ 16 значащими цифрами XlsxWriter
({:.16G}) записывает без изменения, а 15 — точность набранного числа в Excel.
Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-033/probes/round15.py
"""

import re
from pathlib import Path

PATH = Path(__file__).resolve().parent / "plan_code" / "workbook_template.py"
FLOAT = re.compile(r"(?<![\w.])-?\d+\.\d+(?:[eE][-+]?\d+)?")


def main():
    lines = PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    inside, changed = False, 0
    for i, line in enumerate(lines):
        if line.startswith("DEMO_") and line.rstrip().endswith("("):
            inside = True
        elif inside and line.startswith(")"):
            inside = False
        elif inside:
            def sub(m):
                nonlocal changed
                new = repr(float(f"{float(m.group()):.15G}"))
                changed += new != m.group()
                return new
            lines[i] = FLOAT.sub(sub, line)
    PATH.write_text("".join(lines), encoding="utf-8")
    print(f"изменено литералов: {changed}")


if __name__ == "__main__":
    main()
