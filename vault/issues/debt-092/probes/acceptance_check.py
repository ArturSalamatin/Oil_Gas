"""Проверка инструкций на копии опубликованной поставки с наложенными правками."""

from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
import sysconfig

here = Path(__file__).resolve().parent
worktree = here.parents[3]
copy = here / "acceptance" / "gpn-multiphase-solver-1.0.7"
source = worktree / "numerical_solver"
for relative in ("README.md", "pyproject.toml", "examples/06_table_corey_rp/README.md",
                 "examples/23_source_tree_run/README.md"):
    shutil.copy2(source / relative, copy / relative)
    print("overlay", relative, hashlib.sha256((copy / relative).read_bytes()).hexdigest(), flush=True)

# Ключ -S отключает editable-установки; зависимости доступны по одному пути.
env = os.environ.copy()
env["PYTHONPATH"] = sysconfig.get_paths()["purelib"]
env.pop("GPN_EXAMPLES_EMF", None)
env["INKSCAPE"] = str(here / "no-such-inkscape.exe")
env["PYTHONUTF8"] = "1"


def run(name, args, *, cwd, environment):
    """Сохранить вывод и требовать успешного завершения команды."""
    result = subprocess.run([sys.executable, "-S", *args], cwd=cwd, env=environment,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    (here / f"{name}.log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    print(name, "exit", result.returncode, flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
    return result.stdout + result.stderr


report = run("example23", [str(copy / "examples/23_source_tree_run/main.py")],
             cwd=here, environment=env)
assert str(copy) in report and "inkscape" in report.lower(), "Пути импорта или предупреждение Inkscape"
out = copy / "examples/23_source_tree_run/output"
assert sorted(p.name for p in (out / "input").iterdir()) == [
    "config.json", "gas_pvt.csv", "oil_pvt.csv", "relperm.csv"]
assert (copy / "examples/23_source_tree_run/23_source_tree_run.xlsx").is_file()
assert list((out / "emf").glob("*.svg")) and not list((out / "emf").glob("*.emf"))

case = here / "my_case"
if case.exists():
    raise SystemExit("my_case уже существует – использовать новый каталог пробы")
shutil.copytree(copy / "examples/06_table_corey_rp", case,
                ignore=shutil.ignore_patterns("output", "__pycache__"))
env["PYTHONPATH"] = os.pathsep.join((str(copy), str(copy / "HydroSolverPrototype/Prototype_1.0.3"),
                                    sysconfig.get_paths()["purelib"]))
env["GPN_EXAMPLES_EMF"] = "0"
run("example06_cli", ["-m", "gpn_multiphase_solver", "run", str(case / "config.json")],
    cwd=here, environment=env)
assert (case / "output/profiles.csv").is_file()
print("PASS: book input, imports, SVG without Inkscape, copied case and CLI", flush=True)
