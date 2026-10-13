"""Временная обёртка FEAT-030: run_example → gpn_multiphase_solver.report.pipeline.run_case.

Живёт до шага 7 плана FEAT-030 (vault/plans/feat-030 run-command-from-config.md):
main.py примеров ещё зовут run_example, и полный снимок их вывода
проверяет, что run_case даёт тот же вывод. На шаге 7 файл удаляется.
"""

import sys

# Как прежде при импорте example_runner — консоль UTF-8 и matplotlib без
# окна; теперь это делает команда (cli.configure_batch_run, шаг 6).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import matplotlib  # noqa: E402
matplotlib.use("Agg")

from gpn_multiphase_solver.report.pipeline import run_case  # noqa: E402


def run_example(config_path, output_dir, title, overlays=None,
                n_profiles=None, steady_state=True) -> tuple:
    """Прежняя сигнатура и умолчание steady_state=True; возврат (elapsed, history, grid, config)."""
    # steady_state=True по умолчанию — как было: main.py 01–12, 04a, 13a, 15
    # флаг не передают и ждут стационарную аналитику
    r = run_case(config_path, output_dir, title=title, overlays=overlays,
                 n_profiles=n_profiles, steady_state=steady_state)
    return r.elapsed, r.history, r.grid, r.config
