"""Перепись докстрингов пакета gpn_multiphase_solver и прототипа (FEAT-031, вопрос документации).

Сколько публичных модулей, классов, функций; у скольких докстринга нет, однострочный,
многострочный; есть ли разделы Parameters/Returns (стиль numpydoc) или Args (Google);
язык (кириллица). Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-031/probes/docstring_census.py
"""

import ast
import re
from collections import Counter
from pathlib import Path

ROOT = Path.cwd() / "numerical_solver"
PACKAGES = {
    "gpn_multiphase_solver": ROOT / "gpn_multiphase_solver",
    "radial_blackoil": ROOT / "HydroSolverPrototype" / "Prototype_1.0.3" / "radial_blackoil",
}
CYR = re.compile("[а-яА-ЯёЁ]")
NUMPY_SECTIONS = re.compile(r"^\s*(Parameters|Returns|Raises|Yields)\s*\n\s*-{3,}", re.M)
GOOGLE_SECTIONS = re.compile(r"^\s*(Args|Returns|Raises):\s*$", re.M)
EQ_LABEL = re.compile(r"eq:[\w-]+")


def kind_of(doc):
    if doc is None:
        return "нет"
    lines = [ln for ln in doc.strip().splitlines() if ln.strip()]
    return "одна строка" if len(lines) <= 1 else "многострочный"


def census(pkg_dir):
    stats = {"module": Counter(), "class": Counter(), "function": Counter(), "method": Counter()}
    extra = Counter()
    for path in sorted(pkg_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        nodes = [("module", tree, path.stem)]
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                nodes.append(("class", node, node.name))
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        nodes.append(("method", sub, sub.name))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nodes.append(("function", node, node.name))
        for kind, node, name in nodes:
            # Публичное: модуль не с «_» (кроме __init__/__main__), имя без «_», кроме __init__ класса
            if kind == "module":
                public = not name.startswith("_") or name in ("__init__", "__main__")
            elif kind == "method":
                public = not name.startswith("_") or name == "__init__"
            else:
                public = not name.startswith("_")
            if not public:
                continue
            doc = ast.get_docstring(node)
            stats[kind][kind_of(doc)] += 1
            if doc:
                extra["с кириллицей"] += bool(CYR.search(doc))
                extra["без кириллицы"] += not CYR.search(doc)
                extra["разделы numpydoc"] += bool(NUMPY_SECTIONS.search(doc))
                extra["разделы Google"] += bool(GOOGLE_SECTIONS.search(doc))
                extra["с меткой eq:"] += bool(EQ_LABEL.search(doc))
    return stats, extra


for pkg, pkg_dir in PACKAGES.items():
    stats, extra = census(pkg_dir)
    print(f"=== {pkg} ({pkg_dir.relative_to(Path.cwd())}) — только публичные имена")
    for kind, c in stats.items():
        total = sum(c.values())
        print(f"  {kind:9s} всего {total:4d}: " + ", ".join(f"{k} {c[k]}" for k in ("нет", "одна строка", "многострочный")))
    print("  докстринги: " + ", ".join(f"{k} {v}" for k, v in extra.items()))
