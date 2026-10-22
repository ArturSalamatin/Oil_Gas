r"""Аудит DEBT-057: все правки шагов 1–3 плана на копии numerical_solver/ — сторожа меток и скриптов примеров.

Запуск из numerical_solver/ (копия — vault/issues/debt-057/probes/audit_tree/, удаляется следующим
запуском, не коммитится):
    .venv\Scripts\python ..\vault\issues\debt-057\probes\audit_tree.py
Копия: пакет, tests/*.py, examples/ без output, pyproject.toml, doc/problem_statement.tex.
Правки — пары tex_apply.PAIRS и apply_code.CODE/TESTS, новый файл тестов — черновик.
pytest из корня копии: пакет копии первым в sys.path.
"""
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()
HERE = Path(__file__).parent
TREE = HERE / "audit_tree"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    tex, code = _load("tex_apply"), _load("apply_code")
    if TREE.exists():
        shutil.rmtree(TREE)
    ign = shutil.ignore_patterns("__pycache__", "output", "*.png", "*.emf", "*.npz")
    shutil.copytree(SOLVER / "gpn_multiphase_solver", TREE / "gpn_multiphase_solver", ignore=ign)
    shutil.copytree(SOLVER / "tests", TREE / "tests", ignore=ign)
    shutil.copytree(SOLVER / "examples", TREE / "examples", ignore=ign)
    shutil.copytree(SOLVER / "configs", TREE / "configs", ignore=ign)
    (TREE / "doc").mkdir()
    shutil.copy(SOLVER / "doc" / "problem_statement.tex", TREE / "doc" / "problem_statement.tex")
    shutil.copy(SOLVER / "pyproject.toml", TREE / "pyproject.toml")
    # Шаг 1 — .tex
    code.apply(TREE / "doc" / "problem_statement.tex",
               [(o, n, k) for o, n, k in tex.PAIRS])
    # Шаг 2 — новый файл тестов
    t = (HERE / "test_energy_porosity_draft.py").read_text(encoding="utf-8")
    (TREE / "tests" / "test_energy_porosity.py").write_text(t, encoding="utf-8")
    # Шаг 3 — код, эталон, скрипт примеров
    for rel, pairs in {**code.CODE, **code.TESTS}.items():
        code.apply(TREE / rel, pairs)
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
           "tests/test_eq_references.py", "tests/test_example_scripts.py",
           "tests/test_energy_porosity.py", "tests/test_config.py"]
    r = subprocess.run(cmd, cwd=TREE, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = r.stdout.strip().splitlines()
    print("\n".join([l for l in out if l.startswith(("FAILED", "ERROR", "E "))][:40]))
    print(out[-1] if out else r.stderr[-2000:])
    r = subprocess.run([sys.executable, "-c",
                        "import gpn_multiphase_solver as g; print(g.__file__)"],
                       cwd=TREE, capture_output=True, text=True)
    print("пакет:", r.stdout.strip())


if __name__ == "__main__":
    main()
