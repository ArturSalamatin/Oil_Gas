"""Проба FEAT-034, шаг 3: что разбор видит в книге, сохранённой Excel пользователем.

Запуск из корня worktree задачи (разбор — из пакета дерева, где запущено); venv —
в основном каталоге, в worktree своего нет:
    D:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\numerical_solver\\.venv\\Scripts\\python.exe ^
        vault/issues/feat-034/probes/excel_book.py <книга.xlsx> [...]
Печать: лист, адрес, тип, значение, признак даты, формула; пометка fullCalcOnLoad.
Вывод сохранить в excel_book.out.txt рядом.
"""

import sys
from pathlib import Path

SOLVER = Path.cwd() / "numerical_solver"
sys.path.insert(0, str(SOLVER))

from gpn_multiphase_solver.io import xlsx_reader as xr  # noqa: E402

print("разбор:", xr.__file__)
for arg in sys.argv[1:]:
    try:
        book = xr.read_workbook(arg)
    except (xr.WorkbookError, OSError) as exc:
        print(f"{arg}: {type(exc).__name__}: {exc}")
        continue
    print(f"{arg}: листов {len(book.sheets)}, recalc_on_open = {book.recalc_on_open}")
    for sheet in book.sheets.values():
        for (_, _), c in sorted(sheet.cells.items()):
            print(f"  {c.ref:12} {c.kind:7} {c.value!r:28} date={c.is_date!s:5} "
                  f"formula={c.formula!r}")
