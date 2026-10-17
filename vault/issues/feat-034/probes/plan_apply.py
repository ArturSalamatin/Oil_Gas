"""Проверка плана FEAT-034: код плана на копии дерева numerical_solver (рабочий код не трогается).

Копия — probes/plan_tree/: пакет gpn_multiphase_solver, tests/*.py, pyproject.toml,
постановка (сторож меток), configs/*.xlsx. Модуль и тесты — из probes/plan_code/
(шаги 1–2 плана). Прототип — из основного дерева (PYTHONPATH). Тесты: новые,
сторож меток, тест зависимостей пакета. Черновик руководителя копируется, если он
есть: без него тест черновика пропускается — проверяется и это.

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-034/probes/plan_apply.py
Вывод: plan_apply.out.txt. Каталог plan_tree/ в конце удаляется.
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
DRAFT = "INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx"


def build(with_draft: bool) -> None:
    if TREE.exists():
        shutil.rmtree(TREE)
    shutil.copytree(SOLVER / "gpn_multiphase_solver", TREE / "gpn_multiphase_solver",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (TREE / "tests").mkdir()
    for f in (SOLVER / "tests").glob("*.py"):
        shutil.copy2(f, TREE / "tests" / f.name)
    shutil.copy2(SOLVER / "pyproject.toml", TREE / "pyproject.toml")
    (TREE / "doc").mkdir()
    shutil.copy2(SOLVER / "doc" / "problem_statement.tex", TREE / "doc" / "problem_statement.tex")
    (TREE / "configs").mkdir()
    shutil.copy2(SOLVER / "configs" / "INPUT_TEMPLATE_v1.xlsx", TREE / "configs")
    if with_draft and (SOLVER / "configs" / DRAFT).exists():
        shutil.copy2(SOLVER / "configs" / DRAFT, TREE / "configs")
    # Корпус тестов — книги прототипа: копии с теми же относительными путями
    # (тест ищет их от своего каталога); код прототипа — из основного дерева
    for book in PROTO.rglob("*.xlsx"):
        rel = book.relative_to(PROTO)
        if rel.parts[0] == "OUTPUT":
            continue
        (TREE / "HydroSolverPrototype" / "Prototype_1.0.3" / rel).parent.mkdir(
            parents=True, exist_ok=True)
        shutil.copy2(book, TREE / "HydroSolverPrototype" / "Prototype_1.0.3" / rel)
    # Шаги 1–2: модуль и тесты
    shutil.copy2(CODE / "xlsx_reader.py", TREE / "gpn_multiphase_solver" / "io" / "xlsx_reader.py")
    shutil.copy2(CODE / "test_xlsx_reader.py", TREE / "tests" / "test_xlsx_reader.py")


def run(args, **kw):
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               PYTHONPATH=os.pathsep.join([str(TREE), str(PROTO)]))
    return subprocess.run([sys.executable, *args], env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", **kw)


# Порча модуля → тест, который обязан упасть: тесты ловят то, что обещают
MUTATIONS = [
    ("fullCalcOnLoad не учитывается", "    if formula is not None and recalc:\n",
     "    if False:\n"),
    ("экранированные буквы — дата", r'''_FORMAT_LITERALS = re.compile(r'"[^"]*"|\\.|''',
     r'''_FORMAT_LITERALS = re.compile(r'"[^"]*"|'''),
    ("фонетика <rPh> читается", '        elif child.tag == f"{_M}r":\n',
     '        elif child.tag in (f"{_M}r", f"{_M}rPh"):\n'),
    ("numFmt из <dxf>", '    numfmts = root.find(f"{_M}numFmts")\n',
     '    numfmts = list(root.iter(f"{_M}numFmt"))\n'),
    ("_xHHHH_ не раскодируется",
     "    return _ESCAPED_CHAR.sub(lambda m: chr(int(m.group(1), 16)), s)\n",
     "    return s\n"),
    ("<v></v> — число", "    if not text.strip():\n", "    if False:\n"),
    ("логическое — число 1.0",
     '        return Cell(sheet, row, col, BOOL, text in ("1", "true"), formula=formula)\n',
     '        return Cell(sheet, row, col, NUMBER, float(text), formula=formula)\n'),
    ("Strict не распознаётся", "    if root.tag == _STRICT_WORKBOOK:\n", "    if False:\n"),
    ("цель «xl/…» от корня не читается",
     "    return target if part not in names and target in names else part\n",
     "    return part\n"),
    ("стилизованные пустые хранятся",
     "            if cell.kind != EMPTY or cell.formula is not None:\n",
     "            if True:\n"),
    ("стиль ячейки — голый int() (аудит 2)",
     '    style = _int(path, c.get("s", "0"), f"ячейка {sheet}!{column_letters(col)}{row}: стиль")\n',
     '    style = int(c.get("s", "0"))\n'),
]


def mutations() -> list[str]:
    """Каждая порча модуля в копии дерева → число упавших тестов (ждём > 0)."""
    module = TREE / "gpn_multiphase_solver" / "io" / "xlsx_reader.py"
    clean = module.read_text(encoding="utf-8")
    lines = []
    for title, old, new in MUTATIONS:
        assert clean.count(old) == 1, f"порча «{title}»: якорь найден {clean.count(old)} раз"
        module.write_text(clean.replace(old, new), encoding="utf-8")
        r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_xlsx_reader.py"],
                cwd=TREE)
        lines.append(f"  {title}: {r.stdout.strip().splitlines()[-1]}")
    module.write_text(clean, encoding="utf-8")
    return lines


def main():
    out = []
    for with_draft in (True, False):
        build(with_draft)
        r = run(["-c", "import gpn_multiphase_solver.io.xlsx_reader as m; print(m.__file__)"],
                cwd=TREE)
        out.append(f"== черновик {'есть' if with_draft else 'нет'}; модуль: {r.stdout.strip()}"
                   f" {r.stderr[-300:]}")
        r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs",
                 "tests/test_xlsx_reader.py", "tests/test_eq_references.py", DEPS_TEST],
                cwd=TREE)
        out.append("pytest:\n" + r.stdout[-5000:] + r.stderr[-1500:])
        if with_draft:
            r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only",
                     "tests/test_xlsx_reader.py"], cwd=TREE)
            out.append("собрано новых: " + r.stdout.strip().splitlines()[-1])
            r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "--durations=3",
                     "tests/test_xlsx_reader.py"], cwd=TREE)
            out.append("время:\n" + "\n".join(r.stdout.strip().splitlines()[-6:]))
            out.append("порча модуля (ждём failed в каждой строке):")
            out.extend(mutations())
    shutil.rmtree(TREE)
    text = "\n".join(out)
    (HERE / "plan_apply.out.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
