"""Проверка плана FEAT-036: код плана на копии базы numerical_solver (рабочий код не трогается).

База — numerical_scheme/implementation, если FEAT-037 туда влита, иначе ветка
feat/feat-037/solver-version-changelog (план FEAT-036 стоит поверх FEAT-037).
Копия — git archive <база> numerical_solver в probes/plan_tree/. В неё:
  - правки plan_code/edits.py (каждое «было» — ровно одно вхождение);
  - plan_code/test_workbook_run.py — новый файл тестов;
  - блоки plan_code/test_cli_block.py, test_examples_block.py — в конец файлов;
  - пример 22: main.py, README.md (черновик), книга — командой template копии;
  - configs/INPUT_TEMPLATE_v1.xlsx пересоздаётся командой template копии.
Python — venv основного каталога, запуск из каталога копии: pytest берёт пакет
и прототип копии (pythonpath pyproject.toml), подпроцессы — через PYTHONPATH.

Что делается:
  1. новые и затронутые тесты, сторожа;
  2. число тестов и весь быстрый уровень;
  3. порчи кода плана — каждую должен поймать хотя бы один тест;
  4. пример 22: main.py (код, время, печать — example22.out.txt);
  5. tests/test_examples.py целиком (медленные — все 24 примера).

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-036/probes/plan_apply.py
Вывод: plan_apply.out.txt. Каталог plan_tree/ в конце удаляется.
"""

import os
import runpy
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TREE = HERE / "plan_tree"
SOLVER = TREE / "numerical_solver"
CODE = HERE / "plan_code"
EX22 = SOLVER / "examples" / "22_workbook_input"
BOOK22 = "examples/22_workbook_input/22_workbook_input.xlsx"
GENERATOR = "configs/INPUT_TEMPLATE_v1.xlsx"
FEAT037 = "feat/feat-037/solver-version-changelog"
BASE_BRANCH = "numerical_scheme/implementation"
NEW_TESTS = ["tests/test_workbook_run.py", "tests/test_cli.py", "tests/test_workbook_template.py"]
NEAR = ["tests/test_workbook_convert.py", "tests/test_xlsx_reader.py", "tests/test_workbook_format.py"]
GUARDS = ["tests/test_eq_references.py", "tests/test_public_api.py", "tests/test_example_scripts.py",
          "tests/test_packaging.py"]


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
                          text=True).stdout.strip()


def base() -> str:
    merged = subprocess.run(["git", "merge-base", "--is-ancestor", FEAT037, BASE_BRANCH],
                            cwd=ROOT).returncode == 0
    return BASE_BRANCH if merged else FEAT037


def run(args, **kw):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", GPN_EXAMPLES_EMF="0",
               PYTHONPATH=os.pathsep.join([str(SOLVER),
                                           str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]))
    return subprocess.run([sys.executable, *args], env=env, capture_output=True, cwd=SOLVER,
                          text=True, encoding="utf-8", errors="replace", **kw)


def build() -> str:
    ref = base()
    if TREE.exists():
        shutil.rmtree(TREE)
    TREE.mkdir()
    tar = TREE / "base.tar"
    subprocess.run(["git", "archive", "--format=tar", "-o", str(tar), ref, "numerical_solver"],
                   cwd=ROOT, check=True)
    subprocess.run(["tar", "-xf", str(tar), "-C", str(TREE)], check=True)
    tar.unlink()
    edits = runpy.run_path(str(CODE / "edits.py"))["EDITS"]
    for rel, pairs in edits.items():
        path = SOLVER / rel
        text = path.read_text(encoding="utf-8")
        for old, new in pairs:
            n = text.count(old)
            assert n == 1, f"{rel}: «было» найдено {n} раз:\n{old[:200]}"
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8", newline="\n")
    shutil.copy2(CODE / "test_workbook_run.py", SOLVER / "tests" / "test_workbook_run.py")
    for block, target in (("test_cli_block.py", "tests/test_cli.py"),
                          ("test_examples_block.py", "tests/test_examples.py")):
        path = SOLVER / target
        path.write_text(path.read_text(encoding="utf-8")
                        + (CODE / block).read_text(encoding="utf-8"), encoding="utf-8",
                        newline="\n")
    EX22.mkdir()
    for name in ("main.py", "README.md"):
        shutil.copy2(CODE / "example_22" / name, EX22 / name)
    (SOLVER / GENERATOR).unlink()
    return f"{ref} = {git('rev-parse', '--short', ref)}"


def tail(r, n=8) -> str:
    lines = [ln for ln in r.stdout.strip().splitlines() if not ln.startswith(".")]
    return "\n  ".join(lines[-n:]) + (f"\n  stderr: {r.stderr[-800:]}" if r.returncode else "")


def books() -> list[str]:
    """Книга примера 22 и книга генератора — командой template копии (строка «Run» на месте)."""
    out = []
    r = run(["-c", "import gpn_multiphase_solver.io.workbook_template as m; print(m.__file__)"])
    out.append(f"генератор: {r.stdout.strip()} {r.stderr[-300:]}")
    for path in (BOOK22, GENERATOR):
        r = run(["-m", "gpn_multiphase_solver", "template", path])
        out.append(f"template {path}: код {r.returncode}, {(SOLVER / path).stat().st_size} байт "
                   f"{r.stderr[-300:]}")
    return out


PIPELINE = SOLVER / "gpn_multiphase_solver" / "report" / "pipeline.py"
CLI = SOLVER / "gpn_multiphase_solver" / "cli.py"
TEMPLATE = SOLVER / "gpn_multiphase_solver" / "io" / "workbook_template.py"

# Порча кода плана → тесты обязаны упасть. (файл, название, [(было, стало), …])
MUTATIONS = [
    (PIPELINE, "книга внутри каталога вывода не отвергается",
     [("    if book == out or out in book.parents:\n", "    if False:\n")]),
    (PIPELINE, "очистка до чтения книги (книга с ошибкой стирает вывод)",
     [("        config, tables = workbook_to_config(read_workbook(workbook))\n",
       "        shutil.rmtree(output_dir, ignore_errors=True)\n"
       "        config, tables = workbook_to_config(read_workbook(workbook))\n")]),
    (PIPELINE, "нет очистки до записи перевода",
     [("        try:\n            shutil.rmtree(output_dir)\n        except OSError as exc:\n",
       "        try:\n            pass\n        except OSError as exc:\n")]),
    (PIPELINE, "очистка после расчёта и у книги (input/ стирается)",
     [("    if workbook is None and output_dir.is_dir():\n", "    if output_dir.is_dir():\n")]),
    (PIPELINE, "защита входных файлов и у книги",
     [("    if workbook is None:\n        # Перевод книги лежит",
       "    if True:\n        # Перевод книги лежит")]),
    (PIPELINE, "печать «Конфиг:» вместо «Книга:»",
     [('    print(f"Книга: {workbook}" if workbook is not None else f"Конфиг: {config_path}")\n',
       '    print(f"Конфиг: {config_path}")\n')]),
    (PIPELINE, "ошибка фабрики — с путём перевода, а не книги",
     [("        # же категория: расчёт не начат\n"
       '        raise CaseConfigError(f"{source}: {exc}") from exc\n',
       "        # же категория: расчёт не начат\n"
       '        raise CaseConfigError(f"{config_path}: {exc}") from exc\n')]),
    (PIPELINE, "расширение с учётом регистра",
     [("config_path.suffix.lower() in EXCEL_SUFFIXES", "config_path.suffix in EXCEL_SUFFIXES")]),
    (PIPELINE, "явный n_profiles не проверяется до перевода",
     [("    if n_profiles is not None and (isinstance(n_profiles, bool)\n",
       "    if False and (isinstance(n_profiles, bool)\n")]),
    (PIPELINE, "нет книги — сообщение ОС вместо «книга не найдена»",
     [("    except FileNotFoundError as exc:\n"
       '        raise CaseConfigError(f"{workbook}: книга не найдена") from exc\n', "")]),
    (PIPELINE, "очистка у конфига отключена (аудит 1)",
     [("    if workbook is None and output_dir.is_dir():\n", "    if False:\n")]),
    (PIPELINE, "отказ очистки (файл открыт) не ловится (аудит 1)",
     [("        except OSError as exc:\n            # Windows: файл каталога открыт",
       "        except KeyError as exc:\n            # Windows: файл каталога открыт")]),
    (CLI, "командная строка: «Ошибка конфига» и для книги",
     [('        what = "книги" if config.suffix.lower() in EXCEL_SUFFIXES else "конфига"\n',
       '        what = "конфига"\n')]),
    (TEMPLATE, "нет строки «Run» на листе COMMENTS",
     [('    ("Run",\n', '    ("Rum",\n')]),
]


def mutations() -> list[str]:
    lines = []
    for path, title, pairs in MUTATIONS:
        clean = path.read_text(encoding="utf-8")
        text = clean
        for old, new in pairs:
            assert text.count(old) == 1, f"порча «{title}»: якорь найден {text.count(old)} раз"
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8", newline="\n")
        r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no",
                 "tests/test_workbook_run.py", "tests/test_workbook_template.py::test_comments_sheet",
                 "tests/test_cli.py", "-k", "workbook or book or comments"])
        path.write_text(clean, encoding="utf-8", newline="\n")
        lines.append(f"  {title}: {r.stdout.strip().splitlines()[-1]}")
    return lines


def example22() -> list[str]:
    t0 = time.perf_counter()
    r = run([str(EX22 / "main.py")])
    dt = time.perf_counter() - t0
    (HERE / "example22.out.txt").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr,
                                            encoding="utf-8")
    out_dir = EX22 / "output"
    files = sorted(p.name for p in out_dir.iterdir()) if out_dir.exists() else []
    inp = sorted(p.name for p in (out_dir / "input").iterdir()) if (out_dir / "input").exists() else []
    return [f"пример 22 main.py: код {r.returncode}, {dt:.1f} с; вывод: {files}; input/: {inp}"]


def main():
    mode = sys.argv[1:]
    head = build()
    out = [f"база {head}"]
    out.extend(books())
    if mode == ["tests"]:
        # Разбор отказов: новые тесты, полный отчёт; дерево остаётся
        r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", "--tb=short", *NEW_TESTS])
        print("\n".join(out) + f"\n{r.stdout[-8000:]}\n{r.stderr[-1500:]}")
        return
    if mode == ["extra"]:
        # Пример 22: прогон и числа README; сверка матрицы энергии и сводная
        # проверка баланса для 22; дерево остаётся
        out.extend(example22())
        r = run([str(HERE / "example22_numbers.py"), str(EX22 / "output")])
        out.append("числа README 22:\n" + r.stdout + r.stderr[-800:])
        t0 = time.perf_counter()
        r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short",
                 "tests/test_energy_matrix_examples.py", "-k", "coverage or 22_workbook_input"])
        out.append(f"сверка матрицы 22 и охват ({time.perf_counter() - t0:.0f} с):\n  " + tail(r, 6))
        code = ("import sys; sys.path.insert(0, 'examples'); import check_energy_balance_all as m; "
                "e = m.find_examples(); print(len(e), e[-1]); print(m.check_one('22_workbook_input'))")
        r = run(["-c", code])
        out.append("check_energy_balance_all: " + r.stdout.strip() + r.stderr[-800:])
        (HERE / "plan_apply_extra.out.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
        print("\n".join(out))
        return
    if mode == ["examples"]:
        # Разбор отказов tests/test_examples.py: до первого отказа, полная трассировка; дерево остаётся
        r = run(["-m", "pytest", "tests/test_examples.py", "-q", "-p", "no:cacheprovider", "-x",
                 "-rfE", "--tb=long", "-W", "ignore::DeprecationWarning"])
        lines = r.stdout.splitlines()
        start = next((i for i, ln in enumerate(lines) if "FAILURES" in ln or "ERRORS" in ln),
                     max(len(lines) - 80, 0))
        text = "\n".join(out) + "\n" + "\n".join(lines[start:])[-15000:]
        (HERE / "plan_apply_examples.out.txt").write_text(text + "\n", encoding="utf-8")
        print(text)
        return
    if mode == ["fast"]:
        # Разбор отказов быстрого уровня: только отказы, короткая трассировка; дерево остаётся
        r = run(["-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider", "-m", "not slow",
                 "-rf", "--tb=short", "-W", "ignore::DeprecationWarning"])
        lines = r.stdout.splitlines()
        start = next((i for i, ln in enumerate(lines) if "FAILURES" in ln), max(len(lines) - 60, 0))
        print("\n".join(out) + "\n" + "\n".join(lines[start:])[-12000:])
        return
    r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", "--durations=8",
             *NEW_TESTS, *NEAR, *GUARDS])
    out.append("новые и затронутые тесты, сторожа:\n  " + tail(r, 16))
    r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only",
             "tests/test_workbook_run.py"])
    out.append("собрано в test_workbook_run.py: " + r.stdout.strip().splitlines()[-1])
    r = run(["-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider", "--collect-only"])
    out.append("всего тестов: " + r.stdout.strip().splitlines()[-1])
    t0 = time.perf_counter()
    r = run(["-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider", "-m", "not slow", "-rs"])
    out.append(f"быстрый уровень ({time.perf_counter() - t0:.0f} с):\n  " + tail(r, 8))
    out.append("порча кода плана (ждём failed в каждой строке):")
    out.extend(mutations())
    out.extend(example22())
    t0 = time.perf_counter()
    r = run(["-m", "pytest", "tests/test_examples.py", "-q", "-p", "no:cacheprovider", "-rf",
             "--tb=short", "--durations=5"])
    out.append(f"test_examples.py целиком ({time.perf_counter() - t0:.0f} с):\n  " + tail(r, 30))
    shutil.rmtree(TREE)
    text = "\n".join(out)
    (HERE / "plan_apply.out.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
