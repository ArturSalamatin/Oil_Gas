"""Проверка разбора AST из будущего tests/test_packaging.py (DEBT-059) на текущем дереве, при планировании.

Функции — те же, что в плане (шаги 2 и 3). Ожидание на базе c0ec060:
  - сторож вставок находит ровно 14 вставок пути к прототипу (таблица плана);
  - сторонние импорты: gpn_multiphase_solver — matplotlib, numpy, radial_blackoil,
    scipy; radial_blackoil — matplotlib, numpy, scipy, xlsxwriter;
  - __version__ прототипа читается статически: '1.0.3'.

Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python -X utf8 vault\\issues\\debt-059\\probes\\plan_tests_check.py
"""

import ast
import sys
from pathlib import Path

SOLVER = Path.cwd() / "numerical_solver"
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"


def _imported_top_modules(package_dir: Path) -> set[str]:
    names = set()
    for path in package_dir.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names.add(node.module.split(".")[0])
    return names


def _static_version(init_py: Path) -> str:
    for node in ast.parse(init_py.read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "__version__"):
            return node.value.value
    raise AssertionError("нет __version__")


def _is_path_insert(call: ast.Call) -> bool:
    f = call.func
    if not isinstance(f, ast.Attribute):
        return False
    if f.attr == "syspath_prepend":
        return True
    return (f.attr in ("insert", "append") and isinstance(f.value, ast.Attribute)
            and f.value.attr == "path" and isinstance(f.value.value, ast.Name)
            and f.value.value.id == "sys")


def _path_insertions(tree: ast.AST) -> list[str]:
    loop_iter: dict[int, str] = {}
    for loop in ast.walk(tree):
        if isinstance(loop, ast.For):
            for node in ast.walk(loop):
                loop_iter[id(node)] = loop_iter.get(id(node), "") + " | " + ast.unparse(loop.iter)
    return [ast.unparse(n) + loop_iter.get(id(n), "")
            for n in ast.walk(tree) if isinstance(n, ast.Call) and _is_path_insert(n)]


def main() -> None:
    for pkg in (SOLVER / "gpn_multiphase_solver", PROTO / "radial_blackoil"):
        third = sorted(_imported_top_modules(pkg) - set(sys.stdlib_module_names) - {pkg.name})
        print(f"{pkg.name}: сторонние импорты {third}")
    print(f"__version__ прототипа: {_static_version(PROTO / 'radial_blackoil' / '__init__.py')!r}")

    found, hits = 0, []
    for base in ("gpn_multiphase_solver", "examples", "tests"):
        for path in sorted((SOLVER / base).rglob("*.py")):
            for text in _path_insertions(ast.parse(path.read_text(encoding="utf-8"))):
                found += 1
                if "proto" in text.lower():
                    hits.append(f"{path.relative_to(SOLVER)}: {text}")
    print(f"вставок в sys.path всего: {found}; с путём к прототипу: {len(hits)}")
    for h in hits:
        print(f"  {h}")


if __name__ == "__main__":
    main()
