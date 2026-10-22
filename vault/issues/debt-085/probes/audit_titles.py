"""Аудит 1 DEBT-085: подписи всех рисунков run_case по малой книге – перехват save_figure, как в фикстуре case плана.

Запуск из каталога копии numerical_solver (или worktree), чтобы пакет брался из него:
    <python> <путь>\\audit_titles.py
"""

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

os.environ["GPN_EXAMPLES_EMF"] = "0"
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / "tests"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

import gpn_multiphase_solver  # noqa: E402
import gpn_multiphase_solver.report.energy_balance as energy_balance  # noqa: E402
import gpn_multiphase_solver.report.mass_balance as mass_balance  # noqa: E402
import gpn_multiphase_solver.report.pipeline as pipeline  # noqa: E402
import gpn_multiphase_solver.report.pvt as report_pvt  # noqa: E402
import gpn_multiphase_solver.report.relperm as report_relperm  # noqa: E402
from gpn_multiphase_solver.io.figures import save_figure  # noqa: E402
from test_workbook_run import _small_book  # noqa: E402

print("Пакет:", gpn_multiphase_solver.__file__)
figures = {}


def keep(fig, path, dpi):
    figures[Path(path).name] = fig
    return save_figure(fig, path, dpi)


for module in (pipeline, report_relperm, report_pvt, energy_balance, mass_balance):
    setattr(module, "save_figure", keep)

with tempfile.TemporaryDirectory() as tmp:
    book = _small_book(Path(tmp) / "малая книга.xlsx")
    with contextlib.redirect_stdout(io.StringIO()):
        pipeline.run_case(book)

for name, fig in figures.items():
    sup = fig._suptitle.get_text() if fig._suptitle is not None else None
    head = sup if sup is not None else fig.axes[0].get_title()
    print(f"{name:26} {'suptitle' if sup is not None else 'axes[0] '} {head!r}")
print("Всего рисунков:", len(figures))
