"""Аудит плана DEBT-059: шаги 1–3 на копии numerical_solver — блоки «До/После» берутся из текста плана.

Проверяет то, что мысленный прогон не ловит:
  - каждый блок «До:» находится в файле ровно столько раз, сколько план
    обещает (иначе Edit при реализации не найдёт old_string);
  - после правок test_packaging.py — 8 passed; с -o pythonpath= — ровно один
    отказ (прототип даёт именно pythonpath, не что-то ещё);
  - быстрый уровень всего набора тестов зелёный на копии;
  - примеры 03 и 18 с PYTHONPATH на копию считаются; без PYTHONPATH пример 03
    падает с ModuleNotFoundError: radial_blackoil (прототип в общем venv не стоит).

Копия — numerical_solver/build/debt059_audit/numerical_solver (build/ игнорируется
git). Общий venv не меняется. Запуск из корня репозитория:

    numerical_solver\\.venv\\Scripts\\python -X utf8 vault\\issues\\debt-059\\probes\\audit_plan_dry_run.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
SOLVER = ROOT / "numerical_solver"
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из корня репозитория; сейчас {ROOT}")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_blocks import blocks  # noqa: E402

MOCK = SOLVER / "build" / "debt059_audit" / "numerical_solver"
PROTO_REL = Path("HydroSolverPrototype") / "Prototype_1.0.3"
SKIP = shutil.ignore_patterns(".venv", "build", "deliverables", "__pycache__", "output",
                              "OUTPUT", "figures", "*.egg-info", ".pytest_cache", "results")
PY = sys.executable
problems: list[str] = []


def replace(rel: str, old: str, new: str, count: int = 1) -> None:
    """Edit как при реализации: old должен встретиться ровно count раз."""
    path = MOCK / rel
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != count:
        problems.append(f"{rel}: блок «До» найден {n} раз, ожидалось {count}: {old[:70]!r}")
        return
    path.write_text(text.replace(old, new), encoding="utf-8")


def run(cmd, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], cwd=MOCK, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)


def main() -> None:
    if MOCK.parent.exists():
        shutil.rmtree(MOCK.parent)
    shutil.copytree(SOLVER, MOCK, ignore=SKIP)
    b = blocks()
    code = [x["code"] for x in b]
    proto = str(PROTO_REL).replace("\\", "/")

    # ── Шаг 1 ──
    (MOCK / PROTO_REL / "pyproject.toml").write_text(code[6], encoding="utf-8")
    replace(f"{proto}/radial_blackoil/__init__.py", code[7], code[8])

    # ── Шаг 2 ──
    replace("pyproject.toml", code[10], code[11])
    replace("pyproject.toml", code[12], code[13])
    replace("tests/conftest.py", code[14], code[15])
    (MOCK / "tests" / "test_packaging.py").write_text(code[16], encoding="utf-8")
    replace("tests/test_energy_balance_examples.py", code[17], code[18])
    replace("tests/test_examples.py", "(путь — conftest)", "(путь — pythonpath в pyproject.toml)")
    replace("tests/baseline_vectorization_check.py",
            "Запуск через pytest, потому что conftest настраивает путь к внешнему\n"
            "прототипу radial_blackoil (нужен табличному PVT примеров 07-11).",
            "Запуск через pytest, потому что pytest подключает прототип radial_blackoil\n"
            "(pythonpath в pyproject.toml, DEBT-059; нужен табличному PVT примеров 07-11).")

    # ── Шаг 3 ──
    runner = (MOCK / "examples" / "example_runner.py").read_text(encoding="utf-8")
    start = runner.index("# ── Подключение прототипа radial_blackoil")
    end = runner.index("    sys.path.insert(0, str(_PROTO_ROOT))\n") + len(
        "    sys.path.insert(0, str(_PROTO_ROOT))\n\n")
    (MOCK / "examples" / "example_runner.py").write_text(
        runner[:start] + code[19] + runner[end:], encoding="utf-8")
    for m in ("convergence", "energy_balance", "energy_balance_convergence", "mass_balance",
              "two_phase_analytics"):
        replace(f"examples/{m}.py", code[20], code[21])
    replace("examples/temperature_asymptotics.py", code[22], code[23])
    replace("examples/verify_balance_vs_solver.py", code[24], code[25])
    line = 'sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))\n'
    for s in ("check_energy_balance_all.py", "01_single_phase_no_jt/spatial_convergence.py",
              "02_single_phase_jt/check_slopes.py", "05_standing_table_rp/closed_form_convergence.py"):
        replace(f"examples/{s}", line, "")
    replace("examples/18_prototype_input/prototype_input.py", code[26], code[27])
    replace("examples/18_prototype_input/prototype_input.py", "import sys\n", "")
    for s in ("04_table_table", "04a_high_gas_saturation"):
        replace(f"examples/{s}/grid_convergence.py", code[28], code[29])
    with open(MOCK / "tests" / "test_packaging.py", "a", encoding="utf-8") as f:
        f.write("\n\n" + code[30])

    print("Правки по блокам плана:", "все блоки «До» найдены" if not problems else "ПРОБЛЕМЫ")
    for p in problems:
        print("  " + p)

    # ── Проверки ──
    p = run([PY, "-m", "pytest", "tests/test_packaging.py", "-q", "-p", "no:cacheprovider"])
    print("test_packaging.py:", p.stdout.strip().splitlines()[-1])
    p = run([PY, "-m", "pytest", "tests/test_packaging.py", "-q", "-p", "no:cacheprovider",
             "-o", "pythonpath="])
    print("test_packaging.py с -o pythonpath=:", p.stdout.strip().splitlines()[-1])
    for ln in p.stdout.splitlines():
        if ln.startswith("FAILED"):
            print("  " + ln[:160])
    p = run([PY, "-m", "pytest", "tests/", "--collect-only", "-q", "-p", "no:cacheprovider"])
    print("число тестов:", p.stdout.strip().splitlines()[-1])
    p = run([PY, "-m", "pytest", "tests/", "-m", "not slow", "-q", "-p", "no:cacheprovider"])
    print("быстрый уровень:", p.stdout.strip().splitlines()[-1])
    for ln in p.stdout.splitlines():
        if ln.startswith(("FAILED", "ERROR")):
            print("  " + ln[:200])

    env = dict(os.environ)
    env["PYTHONPATH"] = f"{MOCK};{MOCK / PROTO_REL}"
    env["PYTHONIOENCODING"] = "utf-8"
    env["GPN_EXAMPLES_EMF"] = "0"
    p = run([PY, "-c", "import gpn_multiphase_solver as g, radial_blackoil as r;"
                       "print(g.__file__); print(r.__file__)"], env=env)
    print("пути импортов с PYTHONPATH:", p.stdout.strip().replace("\n", " ; "))
    for ex in ("03_standing_corey", "18_prototype_input"):
        p = run([PY, f"examples/{ex}/main.py"], env=env)
        tail = (p.stdout.strip().splitlines() or [""])[-1]
        print(f"пример {ex} с PYTHONPATH: rc={p.returncode}; {tail[:120]}")
        if p.returncode:
            print(p.stderr[-1500:])
    env.pop("PYTHONPATH")
    p = run([PY, "examples/03_standing_corey/main.py"], env=env)
    err = (p.stderr.strip().splitlines() or [""])[-1]
    print(f"пример 03 без PYTHONPATH: rc={p.returncode}; {err[:120]}")


if __name__ == "__main__":
    main()
