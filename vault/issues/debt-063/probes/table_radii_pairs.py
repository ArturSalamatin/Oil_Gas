"""DEBT-063, аудит: пары «было → станет» для радиусов в столбцах таблиц README.

Берёт строки readme_radii.out.txt с пометкой «столбец таблицы, м», для
каждой строки README строит подстроку «| <соседняя ячейка> | <число> |»
(слева — для уникальности) и замену. Печатает пары и проверяет, что
«было» встречается в файле ровно один раз. Пары переносятся в таблицу 4.1
плана и в table41_check.py.

Запуск из numerical_solver/:  python ..\\vault\\issues\\debt-063\\probes\\table_radii_pairs.py
"""
import re
from pathlib import Path

SOLVER = Path.cwd()
OUT = Path(__file__).resolve().parent / "readme_radii.out.txt"
pat = re.compile(r"^(examples\\[^:]+):(\d+): «([\d.]+)» \(столбец таблицы, м\) — центр \d+ "
                 r"\[[^\]]+\] → ([\d.]+)")
seen = set()
for line in OUT.read_text(encoding="utf-8").splitlines():
    m = pat.match(line)
    if not m:
        continue
    rel, n, old, new = m.group(1), int(m.group(2)), m.group(3), m.group(4)
    if (rel, n) in seen:
        continue
    seen.add((rel, n))
    path = SOLVER / rel.replace("\\", "/")
    text = path.read_text(encoding="utf-8")
    row = text.splitlines()[n - 1]
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    i = cells.index(old)
    was = f"| {cells[i - 1]} | {old} |"
    becomes = f"| {cells[i - 1]} | {new} |"
    # Уникальность: при повторе — вся строка таблицы
    if text.count(was) != 1:
        was, becomes = row, row.replace(f"| {old} |", f"| {new} |")
    print(f'("{rel.replace(chr(92), "/").removeprefix("examples/")}", {n}, "{was}", "{becomes}", '
          f'{text.count(was)}),')
