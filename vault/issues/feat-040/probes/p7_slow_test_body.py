"""Проба аудита FEAT-040, п. 7: тело test_runs_without_installed_packages из плана и проверки test_example_scripts – на main_draft.py.

Папки примера ещё нет: копия дерева собирается из пакетов numerical_solver и папки с
main_draft.py (как main.py) и книгой write_template. Окружение подпроцесса – как в тесте:
os.environ (с GPN_EXAMPLES_EMF=0, как задаёт tests/conftest.py) + PYTHONPATH из sysconfig.
Запуск из корня репозитория: numerical_solver\\.venv\\Scripts\\python vault\\issues\\feat-040\\probes\\p7_slow_test_body.py
Каталог probes\\out\\ удалить после разбора.
"""

import ast
import importlib.util
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
NAME = "23_source_tree_run"
os.environ["GPN_EXAMPLES_EMF"] = "0"                 # как tests/conftest.py
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
from gpn_multiphase_solver.io.workbook_template import write_template  # noqa: E402

OUTPUT = {"input", "versions.txt", "well_history.csv", "profiles.csv",
          "pressure_profiles.png", "temperature_profiles.png",
          "saturation_profiles.png", "rs_profiles.png", "well_rates.png",
          "wellbore_dynamics.png", "relperm.png", "pvt.png",
          "energy_balance.png", "mass_balance.png"}

out = HERE / "out"
shutil.rmtree(out, ignore_errors=True)
example_src = out / "example"
example_src.mkdir(parents=True)
shutil.copy(HERE / "main_draft.py", example_src / "main.py")
write_template(example_src / f"{NAME}.xlsx")

# ── Тело теста (план, шаг 3), EXAMPLES_DIR / NAME → example_src ──
tmp_path = out / "tmp"
tmp_path.mkdir()
tree = tmp_path / "solver"
skip = shutil.ignore_patterns("__pycache__", "output")
shutil.copytree(SOLVER / "gpn_multiphase_solver", tree / "gpn_multiphase_solver", ignore=skip)
proto = Path("HydroSolverPrototype", "Prototype_1.0.3", "radial_blackoil")
shutil.copytree(SOLVER / proto, tree / proto, ignore=skip)
shutil.copytree(example_src, tree / "examples" / NAME, ignore=skip)

site = dict.fromkeys(sysconfig.get_paths()[k] for k in ("purelib", "platlib"))
print("PYTHONPATH:", list(site))
env = dict(os.environ, PYTHONPATH=os.pathsep.join(site), PYTHONIOENCODING="utf-8")


def run(*args):
    return subprocess.run([sys.executable, "-S", *args], cwd=tmp_path, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


check = run("-c", "import importlib.util as u; "
                  "print([m for m in ('gpn_multiphase_solver', 'radial_blackoil') "
                  "if u.find_spec(m)])")
print("контроль:", check.returncode, check.stdout.strip())
assert check.returncode == 0 and check.stdout.strip() == "[]", check.stdout + check.stderr

r = run(str(tree / "examples" / NAME / "main.py"))
assert r.returncode == 0, r.stderr[-2000:]
lines = r.stdout.splitlines()
for line, head in zip(lines[:2], ("Решатель:", "Прототип:")):
    assert line.startswith(head), lines[:2]
    path = Path(line.split(maxsplit=2)[2]).resolve()
    assert path.is_relative_to(tree.resolve()), f"{head} не из копии: {path}"
out_dir = tree / "examples" / NAME / "output"
names = {p.name for p in out_dir.iterdir()}
print("output: лишние", sorted(names - OUTPUT), "| нет", sorted(OUTPUT - names))
assert names == OUTPUT
assert (out_dir / "input" / "config.json").is_file()
rows = [[float(x) for x in s.split()] for s in lines
        if len(s.split()) == 4 and s.split()[0].replace(".", "", 1).isdigit()]
print("строк таблицы:", len(rows))
assert len(rows) == 23
by_time = {round(t * 1440): (p, T, q) for t, p, T, q in rows}
import pytest  # noqa: E402
p, T, q = by_time[1]
assert (p, T, q) == (150.0, pytest.approx(349.748, abs=2e-3), pytest.approx(8.212, abs=2e-3))
p, T, q = by_time[30 * 1440]
assert (p, T, q) == (100.0, pytest.approx(350.105, abs=2e-3), pytest.approx(3.077, abs=2e-3))
print("тело медленного теста: все утверждения выполнены")

# ── tests/test_example_scripts.py на main.py примера ──
spec = importlib.util.spec_from_file_location("tes_probe", SOLVER / "tests" / "test_example_scripts.py")
tes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tes)
main_py = example_src / "main.py"
print("имена (а–д):", tes._script_problems(main_py) or "ok")
print("приватные атрибуты:", tes._private_access(ast.parse(main_py.read_text(encoding="utf-8"))) or "ok")
