"""Проба FEAT-040, п. 3: перевод книги примера 22 (шаблон) равен переводу свежего шаблона под тем же именем.

Основа теста test_book_is_template: книга примера 23 – тоже шаблон без изменений.
Запуск из numerical_solver: .venv\\Scripts\\python ..\\vault\\issues\\feat-040\\probes\\p3_book_vs_template.py
Свежий шаблон пишется в probes\\out\\ и удаляется в конце.
"""

import shutil
from pathlib import Path

from gpn_multiphase_solver.io.workbook_convert import workbook_to_config
from gpn_multiphase_solver.io.workbook_template import write_template
from gpn_multiphase_solver.io.xlsx_reader import read_workbook

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
book = SOLVER / "examples" / "22_workbook_input" / "22_workbook_input.xlsx"

out = HERE / "out"
out.mkdir(exist_ok=True)
fresh = out / book.name
fresh.unlink(missing_ok=True)
write_template(fresh)
own, new = workbook_to_config(read_workbook(book)), workbook_to_config(read_workbook(fresh))
print("перевод совпадает:", own == new)
print("заголовок:", own[0]["output"]["title"], "| таблицы:", sorted(own[1]))
# Тот же шаблон под другим именем: отличие только в заголовке
other = out / "другое_имя.xlsx"
other.unlink(missing_ok=True)
write_template(other)
cfg = workbook_to_config(read_workbook(other))
print("под другим именем совпадает:", cfg == own,
      "| без заголовка:", {**cfg[0], "output": {}} == {**own[0], "output": {}})
shutil.rmtree(out)
