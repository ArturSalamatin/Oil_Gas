"""Вид сообщений перевода для README §3.6 (FEAT-036): книга с N = 20.5 и книга с Rs0 = 70.

Код перевода — основной каталог (FEAT-035 влит). Книги пишутся рядом со
скриптом и удаляются. Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-036/probes/message_probe.py
Вывод: message_probe.out.txt.
"""

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "numerical_solver"))

import xlsxwriter  # noqa: E402

from gpn_multiphase_solver.io import workbook_format as wf  # noqa: E402
from gpn_multiphase_solver.io import workbook_template as wt  # noqa: E402
from gpn_multiphase_solver.io.workbook_convert import workbook_to_config  # noqa: E402
from gpn_multiphase_solver.io.xlsx_reader import WorkbookError, read_workbook  # noqa: E402

# _small_book и SMALL_SCHEDULE — из тестов плана, без импорта модуля тестов
# (он берёт имена pipeline, которых в основном каталоге ещё нет)
_src = (HERE / "plan_code" / "test_workbook_run.py").read_text(encoding="utf-8")
_ns = {"xlsxwriter": xlsxwriter, "wf": wf, "wt": wt, "Path": Path}
for node in ast.parse(_src).body:
    if (isinstance(node, ast.FunctionDef) and node.name == "_small_book") or (
            isinstance(node, ast.Assign) and node.targets[0].id == "SMALL_SCHEDULE"):
        exec(compile(ast.Module([node], []), "test_workbook_run.py", "exec"), _ns)
small_book = _ns["_small_book"]

out = []
for name, values in (("n_fraction.xlsx", {"grid.N": 20.5}),
                     ("rs0_70.xlsx", {"initial_conditions.Rs0": 70.0})):
    path = small_book(HERE / name, **values)
    try:
        workbook_to_config(read_workbook(path))
        out.append(f"{name}: перевод прошёл")
    except WorkbookError as exc:
        out.append(f"{name}: {exc}")
    path.unlink()
text = "\n".join(out)
(HERE / "message_probe.out.txt").write_text(text + "\n", encoding="utf-8")
print(text)
