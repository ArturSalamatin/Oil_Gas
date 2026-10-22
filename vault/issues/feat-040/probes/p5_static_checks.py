"""Проба FEAT-040, п. 5: логика быстрых тестов плана на черновике main_draft.py – штатный набор run_case и вставки путей.

Запуск из корня репозитория: numerical_solver\\.venv\\Scripts\\python vault\\issues\\feat-040\\probes\\p5_static_checks.py
Черновик лежит не в examples\\, поэтому папки вставок отсчитываются от numerical_solver\\ явно.
"""

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
sys.path.insert(0, str(SOLVER))
import gpn_multiphase_solver.report.pipeline as pipeline  # noqa: E402

main = ast.parse((HERE / "main_draft.py").read_text(encoding="utf-8"))

# ── test_main_repeats_standard_set ──
steady_only = {"make_overlay_pressure", "make_overlay_saturation",
               "report_closed", "report_asymptotics"}
standard = set()
for node in ast.parse(Path(pipeline.__file__).read_text(encoding="utf-8")).body:
    if isinstance(node, ast.ImportFrom) and (
            node.level == 1 or (node.level == 2 and node.module in ("io.output", "io.figures"))):
        standard |= {a.asname or a.name for a in node.names}
called = {n.func.id for n in ast.walk(main)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
print("штатный набор:", sorted(standard))
print("стационарная аналитика в наборе:", steady_only <= standard)
print("не вызваны в main:", sorted(standard - steady_only - called))
print("run_case / main вызваны:", "run_case" in called, "main" in called)

# ── test_main_inserts_tree_folders ──
inserts = [n for n in ast.walk(main) if isinstance(n, ast.Call)
           and ast.unparse(n.func) == "sys.path.insert"]
found = set()
for call in inserts:
    parts = sorted((c for c in ast.walk(call.args[1])
                    if isinstance(c, ast.Constant) and isinstance(c.value, str)),
                   key=lambda c: (c.lineno, c.col_offset))
    folder = SOLVER.joinpath(*(c.value for c in parts))
    print("вставка:", ast.unparse(call.args[1]), "→", folder.relative_to(SOLVER.parent))
    found |= {name for name in ("gpn_multiphase_solver", "radial_blackoil")
              if (folder / name / "__init__.py").is_file()}
print("вставок:", len(inserts), "| пакеты найдены:", sorted(found))
