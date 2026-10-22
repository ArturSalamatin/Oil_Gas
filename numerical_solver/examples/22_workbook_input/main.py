"""Сценарий 22: расчёт по книге ввода Excel 22_workbook_input.xlsx — без файла конфигурации."""

import sys
from pathlib import Path

from gpn_multiphase_solver.cli import main

if __name__ == "__main__":
    # То же, что python -m gpn_multiphase_solver run <папка примера>\22_workbook_input.xlsx:
    # книга переводится в output\input\ (config.json и CSV таблиц), расчёт идёт
    # по переводу; заголовок рисунков — имя книги (FEAT-036)
    sys.exit(main(["run", str(Path(__file__).parent / "22_workbook_input.xlsx")]))
