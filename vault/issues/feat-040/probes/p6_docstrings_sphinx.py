"""Проба аудита FEAT-040, п. 6: докстринги шага 1 плана проходят D1–D7 и сборку Sphinx -W – без правки пакета.

Докстринги берутся из плана (блоки ```python шага 1 со строковым литералом), подставляются
в функции в памяти; проверка – docstring_problems из tests/test_docs.py; сборка – копия
doc/source с дополненным api.rst в probes\\out\\ (autodoc видит функции из sys.modules).
Запуск из numerical_solver: .venv\\Scripts\\python ..\\vault\\issues\\feat-040\\probes\\p6_docstrings_sphinx.py
Каталог probes\\out\\ удалить после разбора.
"""

import ast
import importlib
import importlib.util
import re
import shutil
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOLVER = ROOT / "numerical_solver"
PLAN = ROOT / "vault" / "plans" / "feat-040 workbook-example-without-install.md"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]

# Порядок функций – порядок блоков с докстрингами в шаге 1 плана
TARGETS = ["report.relperm.plot_relperm", "report.pvt.plot_pvt", "report.pvt.report_pvt",
           "report.energy_balance.plot_energy_balance", "report.mass_balance.plot_mass_balance",
           "report.rs.make_overlay_rs", "report.rs.report_rs"]

text = PLAN.read_text(encoding="utf-8")
step1 = text[text.index("### Шаг 1:"):text.index("### Шаг 2:")]
docs = []
for block in re.findall(r"```python\n(.*?)```", step1, re.S):
    tree = ast.parse(textwrap.dedent(block))
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        docs.append(tree.body[0].value.value)
assert len(docs) == len(TARGETS), len(docs)

funcs = {}
for name, doc in zip(TARGETS, docs):
    mod, attr = name.rsplit(".", 1)
    func = getattr(importlib.import_module(f"gpn_multiphase_solver.{mod}"), attr)
    func.__doc__ = doc
    funcs[f"gpn_multiphase_solver.{name}"] = func

spec = importlib.util.spec_from_file_location("test_docs_probe", SOLVER / "tests" / "test_docs.py")
td = importlib.util.module_from_spec(spec)
spec.loader.exec_module(td)
for full, func in funcs.items():
    td.API[full] = ("function", func, None, None)
    print(f"{full.split('.')[-1]:22s} D1–D7:", td.docstring_problems(full) or "ok")

# ── Sphinx -W на копии doc/source с дополненным api.rst ──
out = HERE / "out"
shutil.rmtree(out, ignore_errors=True)
src = out / "doc" / "source"
shutil.copytree(SOLVER / "doc" / "source", src)
shutil.copy(SOLVER / "README.md", out / "README.md")
api = (src / "api.rst").read_text(encoding="utf-8")
block = textwrap.dedent(re.search(r"```rst\n(.*?)```", step1, re.S).group(1))
api = api.replace("Балансы\n-------", block.rstrip() + "\n\nБалансы\n-------", 1)
assert "make_overlay_rs" in api
(src / "api.rst").write_text(api, encoding="utf-8")
from sphinx.cmd.build import build_main  # noqa: E402
code = build_main(["-W", "-b", "html", "-q", "-d", str(out / "doctrees"), str(src), str(out / "html")])
print("sphinx -W:", code)
html = (out / "html" / "api.html").read_text(encoding="utf-8")
print("нет в api.html:", [n for n in funcs if f'id="{n}"' not in html])
