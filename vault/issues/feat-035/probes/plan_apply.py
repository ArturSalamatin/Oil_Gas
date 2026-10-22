"""Проверка плана FEAT-035: код плана на копии HEAD numerical_solver (рабочий код не трогается).

Копия — git archive HEAD numerical_solver в probes/plan_tree/ (только файлы из
git: черновика руководителя нет, как в worktree). В неё — код plan_code/:
io/workbook_convert.py, cli.py, tests/test_workbook_convert.py; блок
plan_code/test_cli_convert.py дописывается в конец tests/test_cli.py. Python —
venv основного каталога, запуск из каталога копии: pytest берёт пакет и
прототип копии (pythonpath pyproject.toml), подпроцессы test_cli — через PYTHONPATH.

Что делается:
  1. новые тесты, test_cli.py, сторожа (метки, зависимости пакета, публичный интерфейс);
  2. число тестов и весь быстрый уровень;
  3. порчи кода плана — каждую должен поймать хотя бы один тест;
  4. сценарий книги генератора: convert → run (код 0, предупреждений нет, время).

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-035/probes/plan_apply.py
Вывод: plan_apply.out.txt. Каталог plan_tree/ в конце удаляется.
"""

import os
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
MODULE = SOLVER / "gpn_multiphase_solver" / "io" / "workbook_convert.py"
CLI = SOLVER / "gpn_multiphase_solver" / "cli.py"
NEW_TESTS = ["tests/test_workbook_convert.py", "tests/test_cli.py"]
GUARDS = ["tests/test_eq_references.py", "tests/test_public_api.py",
          "tests/test_packaging.py::TestDistributions::"
          "test_declared_dependencies_cover_imports[gpn-multiphase-solver]"]


def build() -> str:
    if TREE.exists():
        shutil.rmtree(TREE)
    TREE.mkdir()
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    tar = TREE / "head.tar"
    subprocess.run(["git", "archive", "--format=tar", "-o", str(tar), "HEAD", "numerical_solver"],
                   cwd=ROOT, check=True)
    subprocess.run(["tar", "-xf", str(tar), "-C", str(TREE)], check=True)
    tar.unlink()
    shutil.copy2(CODE / "workbook_convert.py", MODULE)
    shutil.copy2(CODE / "cli.py", CLI)
    shutil.copy2(CODE / "test_workbook_convert.py", SOLVER / "tests" / "test_workbook_convert.py")
    test_cli = SOLVER / "tests" / "test_cli.py"
    test_cli.write_text(test_cli.read_text(encoding="utf-8")
                        + (CODE / "test_cli_convert.py").read_text(encoding="utf-8"),
                        encoding="utf-8")
    return head


def run(args, **kw):
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               PYTHONPATH=os.pathsep.join([str(SOLVER),
                                           str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]))
    return subprocess.run([sys.executable, *args], env=env, capture_output=True, cwd=SOLVER,
                          text=True, encoding="utf-8", errors="replace", **kw)


def tail(r, n=8) -> str:
    lines = [ln for ln in r.stdout.strip().splitlines() if not ln.startswith(".")]
    return "\n  ".join(lines[-n:]) + (f"\n  stderr: {r.stderr[-800:]}" if r.returncode else "")


# Порча кода плана → тесты обязаны упасть. (файл, название, [(было, стало), …])
MUTATIONS = [
    (MODULE, "пробелы по краям не срезаются (решение 20)",
     [("    return cell.value.strip() if cell.kind == STRING else None\n",
       "    return cell.value if cell.kind == STRING else None\n")]),
    (MODULE, "округление разностей, как пример 18 (решение 19)",
     [("            m = round(t * MS_PER_DAY)          # round(float) — int\n",
       "            m = t * MS_PER_DAY\n"),
      ('    return [{"dt": (ms[k + 1] - ms[k]) / 1000, **controls[k]} for k in range(len(controls))]\n',
       '    return [{"dt": round((ms[k + 1] - ms[k]) / 1000, 3), **controls[k]}'
       ' for k in range(len(controls))]\n')]),
    (MODULE, "целые поля не в int",
     [("        out[p.key] = int(v) if limit.integer else wf.UNIT_TO_SI[p.unit](v)\n",
       "        out[p.key] = wf.UNIT_TO_SI[p.unit](v)\n")]),
    (MODULE, "читаются все ячейки режима, не только своего (решение 16)",
     [("        for target in used:\n",
       '        for target in ("p_wf", "q_oil", "min_bhp"):\n')]),
    (MODULE, "пустая строка таблицы — ошибка (решение 23)",
     [("    return sorted({r for r, c in sheet.cells if r > 1 and c <= ncols})\n",
       "    return list(range(2, max((r for r, c in sheet.cells if c <= ncols), default=1) + 1))\n")]),
    (MODULE, "постоянные слова не проверяются",
     [("            if _text(cell) != p.demo:\n", "            if False:\n")]),
    (MODULE, "крайние строки RELPERM не проверяются",
     [('        if name == "RELPERM" and len(errors) == n_before:\n', "        if False:\n")]),
    (MODULE, "крайние строки RELPERM — и после ошибки ячейки",
     [('        if name == "RELPERM" and len(errors) == n_before:\n',
       '        if name == "RELPERM":\n')]),
    (MODULE, "дата принимается числом",
     [("        if cell.is_date:\n", "        if False:\n")]),
    (MODULE, "формула без значения — как пустая ячейка",
     [("    if cell.formula_without_value:\n", "    if False:\n")]),
    (MODULE, "только первая ошибка (решение 22)",
     [("        self.errors = list(errors)\n", "        self.errors = list(errors)[:1]\n")]),
    (MODULE, "единица не сверяется",
     [("        if _text(unit) != p.unit:\n", "        if False:\n")]),
    (MODULE, "заголовки не сверяются",
     [("        if _text(cell) != h:\n", "        if False:\n")]),
    (MODULE, "пористость без пересчёта к p0",
     [("    return float(phi_ref * np.exp(c_r * (p0 - p_ref)))\n",
       "    return float(phi_ref)\n")]),
    (MODULE, "φ0 > 1 не проверяется (умолчание 35, аудит 1)",
     [("    if phi0 is not None and phi0 > 1.0:\n", "    if False:\n")]),
    (MODULE, "общая формула — пустой текст в сообщении (аудит 1)",
     [('            what = f"формула ={cell.formula}" if cell.formula else "общая формула"\n',
       '            what = f"формула ={cell.formula}"\n')]),
    (MODULE, "первая строка SCHEDULE не проверяется",
     [("            if k == 0 and t != 0.0:\n", "            if False:\n")]),
    (MODULE, "сравнение r_e > r_w при ошибке r_w",
     [("                limit = replace(limit, above_key=None)\n", "                pass\n")]),
    (MODULE, "непустой каталог не проверяется (решение 10)",
     [("    if out_dir.exists() and (not out_dir.is_dir() or any(out_dir.iterdir())):\n",
       "    if False:\n")]),
    (CLI, "командная строка не ловит WorkbookError",
     [("    except WorkbookError as exc:\n", "    except KeyError as exc:\n")]),
]


def mutations() -> list[str]:
    lines = []
    for path, title, pairs in MUTATIONS:
        clean = path.read_text(encoding="utf-8")
        text = clean
        for old, new in pairs:
            assert text.count(old) == 1, f"порча «{title}»: якорь найден {text.count(old)} раз"
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
        r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no",
                 "tests/test_workbook_convert.py", "tests/test_cli.py", "-k", "convert"])
        path.write_text(clean, encoding="utf-8")
        lines.append(f"  {title}: {r.stdout.strip().splitlines()[-1]}")
    return lines


def scenario() -> list[str]:
    """Книга генератора: convert → run, код 0, предупреждения, время."""
    case = TREE / "case"
    out = []
    r = run(["-m", "gpn_multiphase_solver", "convert", "configs/INPUT_TEMPLATE_v1.xlsx",
             str(case)])
    out.append(f"convert: код {r.returncode}\n  " + "\n  ".join(
        (r.stdout + r.stderr).strip().splitlines()))
    t0 = time.perf_counter()
    r = run(["-m", "gpn_multiphase_solver", "run", str(case / "config.json")])
    dt = time.perf_counter() - t0
    text = r.stdout + r.stderr
    warnings = [ln for ln in text.splitlines() if "WARNING" in ln or "Предупреждение" in ln]
    out.append(f"run: код {r.returncode}, {dt:.1f} с, строк предупреждений {len(warnings)}")
    out.extend(f"  {w}" for w in warnings[:10])
    out.append("  " + "\n  ".join(text.strip().splitlines()[:6]))
    files = sorted(p.name for p in (case / "output").iterdir()) if (case / "output").exists() else []
    out.append(f"  файлов вывода: {len(files)} {files}")
    return out


def main():
    if sys.argv[1:] == ["tests"]:
        # Разбор отказов: только новые тесты и test_cli, полный отчёт; дерево остаётся
        head = build()
        r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", "--tb=short",
                 *NEW_TESTS])
        print(f"HEAD {head}\n{r.stdout[-6000:]}\n{r.stderr[-1500:]}")
        return
    head = build()
    out = [f"HEAD {head}"]
    r = run(["-c", "import gpn_multiphase_solver.io.workbook_convert as m; print(m.__file__)"])
    out.append(f"модуль: {r.stdout.strip()} {r.stderr[-300:]}")
    r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", "--durations=5",
             *NEW_TESTS, *GUARDS])
    out.append("новые тесты, test_cli, сторожа:\n  " + tail(r, 14))
    r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only",
             "tests/test_workbook_convert.py"])
    out.append("собрано в test_workbook_convert.py: " + r.stdout.strip().splitlines()[-1])
    r = run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only", "tests/test_cli.py",
             "-k", "convert"])
    out.append("собрано convert в test_cli.py: " + r.stdout.strip().splitlines()[-1])
    r = run(["-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider", "--collect-only"])
    out.append("всего тестов: " + r.stdout.strip().splitlines()[-1])
    t0 = time.perf_counter()
    r = run(["-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider", "-m", "not slow", "-rs"])
    out.append(f"быстрый уровень ({time.perf_counter() - t0:.0f} с):\n  " + tail(r, 8))
    out.append("порча кода плана (ждём failed в каждой строке):")
    out.extend(mutations())
    out.extend(scenario())
    shutil.rmtree(TREE)
    text = "\n".join(out)
    (HERE / "plan_apply.out.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
