"""Аудит плана FEAT-033: код плана на копии дерева numerical_solver (рабочий код не трогается).

Копия — probes/plan_tree/: пакет gpn_multiphase_solver, tests/*.py,
pyproject.toml. Правки шагов 2 и 5 применяются по якорям текущего кода
(якорь не найден — отказ: значит, план разошёлся с кодом); модули и тесты
шагов 3–5 — из probes/plan_code/. Книга генератора — командой, как в шаге 6.
Тесты — новые и тесты шаблона из test_cli.py, test_packaging (зависимости).

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-033/probes/plan_apply.py
Вывод: plan_apply.out.txt. Каталог plan_tree/ после аудита удаляется.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOLVER = ROOT / "numerical_solver"
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
TREE = HERE / "plan_tree"
CODE = HERE / "plan_code"
DEPS_TEST = ("tests/test_packaging.py::TestDistributions::"
             "test_declared_dependencies_cover_imports[gpn-multiphase-solver]")


def edit(path: Path, anchor: str, new: str) -> None:
    """Заменить якорь (ровно одно вхождение) на new."""
    text = path.read_text(encoding="utf-8")
    assert text.count(anchor) == 1, f"{path.name}: якорь найден {text.count(anchor)} раз:\n{anchor}"
    path.write_text(text.replace(anchor, new), encoding="utf-8")


def build() -> None:
    if TREE.exists():
        shutil.rmtree(TREE)
    shutil.copytree(SOLVER / "gpn_multiphase_solver", TREE / "gpn_multiphase_solver",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (TREE / "tests").mkdir()
    for f in (SOLVER / "tests").glob("*.py"):
        shutil.copy2(f, TREE / "tests" / f.name)
    shutil.copy2(SOLVER / "pyproject.toml", TREE / "pyproject.toml")
    (TREE / "configs").mkdir()
    (TREE / "doc").mkdir()                       # сторож меток читает постановку
    shutil.copy2(SOLVER / "doc" / "problem_statement.tex", TREE / "doc" / "problem_statement.tex")

    # ── Шаг 2 ──
    edit(TREE / "pyproject.toml", '    "matplotlib>=3.7",\n',
         '    "matplotlib>=3.7",\n'
         '    # Шаблон книги ввода Excel (gpn-solver template, FEAT-033). Граница — как\n'
         '    # у прототипа (его pyproject.toml): в общем окружении одна версия.\n'
         '    "XlsxWriter>=3.2",\n')
    edit(TREE / "gpn_multiphase_solver" / "units.py", "MIN_TO_S = 60.0\n",
         "MIN_TO_S = 60.0\nHOUR_TO_S = 3600.0\n")

    # ── Шаги 3, 4 ──
    for name in ("workbook_format.py", "workbook_template.py"):
        shutil.copy2(CODE / name, TREE / "gpn_multiphase_solver" / "io" / name)
    for name in ("_xlsx.py", "test_workbook_format.py", "test_workbook_template.py"):
        shutil.copy2(CODE / name, TREE / "tests" / name)

    # ── Шаг 5 ──
    cli = TREE / "gpn_multiphase_solver" / "cli.py"
    edit(cli, '                          "— output.n_profiles конфига)")\n    return p\n',
         '                          "— output.n_profiles конфига)")\n'
         '    tpl = sub.add_parser(\n'
         '        "template", help="шаблон книги ввода Excel с демонстрационными значениями",\n'
         '        description="Шаблон книги ввода Excel (.xlsx, формат версии 1) с "\n'
         '                    "демонстрационными значениями. Существующий файл не "\n'
         '                    "перезаписывается.",\n'
         '        epilog="Коды возврата: 0 — шаблон записан; 2 — ошибка аргументов, файл "\n'
         '               "уже существует или не записывается.")\n'
         '    tpl.add_argument("workbook", type=Path, help="путь новой книги .xlsx")\n'
         '    return p\n')
    edit(cli, "    args = _parser(prog).parse_args(argv)   # ошибка аргументов — SystemExit(2)\n",
         "    args = _parser(prog).parse_args(argv)   # ошибка аргументов — SystemExit(2)\n"
         '    if args.command == "template":\n'
         "        return _template(args.workbook.resolve())\n")
    edit(cli, "def main(argv: list[str] | None = None, prog: str | None = None) -> int:\n",
         'def _template(path: Path) -> int:\n'
         '    """Подкоманда template: шаблон книги в новый файл → код возврата (FEAT-033)."""\n'
         '    # Импорт здесь: шаблону не нужны решатель, scipy и прототип (импорт\n'
         '    # конвейера run — ниже, в main)\n'
         '    from .io.workbook_template import write_template\n'
         '    try:\n'
         '        write_template(path)\n'
         '    except FileExistsError:\n'
         '        print(f"Ошибка: файл {path} уже существует — шаблон не записан, файл не "\n'
         '              f"изменён. Удалите его или укажите другое имя.", file=sys.stderr)\n'
         '        return 2\n'
         '    except ValueError as exc:\n'
         '        print(f"Ошибка: {exc}", file=sys.stderr)\n'
         '        return 2\n'
         '    except OSError as exc:\n'
         '        print(f"Ошибка: не удалось записать {path}: {exc.strerror or exc}", '
         'file=sys.stderr)\n'
         '        return 2\n'
         '    print(f"Шаблон книги записан: {path}")\n'
         '    return 0\n\n\n'
         "def main(argv: list[str] | None = None, prog: str | None = None) -> int:\n")
    with open(TREE / "tests" / "test_cli.py", "a", encoding="utf-8") as f:
        f.write((CODE / "test_cli_template_append.py").read_text(encoding="utf-8"))


def run(args, **kw):
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               PYTHONPATH=os.pathsep.join([str(TREE), str(PROTO)]))
    return subprocess.run([sys.executable, *args], env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", **kw)


def main():
    build()
    out = []
    # ── Шаг 6: книга генератора командой; пакет — из копии ──
    r = run(["-c", "import gpn_multiphase_solver.io.workbook_template as t; print(t.__file__)"],
            cwd=TREE)
    out.append(f"модуль генератора: {r.stdout.strip()} {r.stderr[-500:]}")
    r = run(["-m", "gpn_multiphase_solver", "template", r"configs\INPUT_TEMPLATE_v1.xlsx"],
            cwd=TREE)
    out.append(f"template: код {r.returncode}; {r.stdout.strip()} {r.stderr[-800:]}")
    book = TREE / "configs" / "INPUT_TEMPLATE_v1.xlsx"
    out.append(f"размер книги: {book.stat().st_size if book.exists() else None} байт")
    r = run(["-m", "gpn_multiphase_solver", "template", r"configs\INPUT_TEMPLATE_v1.xlsx"],
            cwd=TREE)
    out.append(f"повтор template: код {r.returncode}; {r.stderr.strip()}")
    # ── Тесты ──
    r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider",
             "tests/test_workbook_format.py", "tests/test_workbook_template.py",
             "tests/test_cli.py", "-k", "not test_cli or template",
             DEPS_TEST, "tests/test_eq_references.py"], cwd=TREE)
    out.append("pytest:\n" + r.stdout[-6000:] + r.stderr[-2000:])
    # К3: без строки XlsxWriter в pyproject тест зависимостей падает
    edit(TREE / "pyproject.toml", '    "XlsxWriter>=3.2",\n', "")
    r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", DEPS_TEST], cwd=TREE)
    out.append("без XlsxWriter в pyproject: " + r.stdout.strip().splitlines()[-1])
    r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only",
             "tests/test_workbook_format.py", "tests/test_workbook_template.py"], cwd=TREE)
    out.append("собрано новых: " + r.stdout.strip().splitlines()[-1])
    text = "\n".join(out)
    (HERE / "plan_apply.out.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
