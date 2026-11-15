"""Изолированная проверка расчётной поставки без запуска выпуска."""

import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "dist" / "debt-091-probe"
OUT.mkdir(parents=True, exist_ok=False)
archive = subprocess.run(["git", "archive", "HEAD", "numerical_solver"], cwd=ROOT,
                         check=True, capture_output=True).stdout
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    tar.extractall(OUT, filter="data")
tree = OUT / "numerical_solver"
shutil.copyfile(ROOT / "numerical_solver" / "README.md", tree / "README.md")
spec = importlib.util.spec_from_file_location("release_probe", ROOT / "tools" / "release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
examples = OUT / "examples.zip"
release.zip_examples(tree / "examples", examples)
docs, _ = release.build_docs(tree, OUT, "1.0.8.dev0")
wheels = release.build_wheels(tree, OUT / "wheels", "1.0.8.dev0", "1.0.3+gpn.2")
target = OUT / "gpn-multiphase-solver-wheels-1.0.8.dev0.zip"
release.zip_calculation_delivery(examples, docs, wheels, tree / "README.md", target)
unpacked = OUT / "unpacked"
with zipfile.ZipFile(target) as z:
    names = z.namelist()
    assert "docs/index.html" in names
    assert not any(n.startswith(("examples/18_prototype_input/", "examples/23_source_tree_run/")) for n in names)
    assert not any(n.endswith(".zip") for n in names)
    z.extractall(unpacked)
assert (unpacked / "README.md").read_bytes() == (tree / "README.md").read_bytes()
assert (unpacked / "examples/06_table_corey_rp/config.json").is_file()
assert (unpacked / "examples/22_workbook_input/22_workbook_input.xlsx").is_file()
env = OUT / "venv"
subprocess.run([sys.executable, "-m", "venv", str(env)], check=True)
python = env / "Scripts" / "python.exe"
clean_env = dict(os.environ)
clean_env.pop("PYTHONPATH", None)
subprocess.run([str(python), "-m", "pip", "install", *map(str, sorted((unpacked / "wheels").glob("*.whl")))],
               cwd=OUT, env=clean_env, check=True)
subprocess.run([str(python), "-m", "gpn_multiphase_solver", "--version"], cwd=OUT, env=clean_env, check=True)
subprocess.run([str(python), "-c", "import gpn_multiphase_solver as g, radial_blackoil as r; print(g.__file__); print(r.__file__)"],
               cwd=OUT, env=clean_env, check=True)
subprocess.run([str(python), "-m", "gpn_multiphase_solver", "run",
                str(unpacked / "examples/06_table_corey_rp/config.json")], cwd=OUT, env=clean_env, check=True)
print(f"Проверена поставка: {target}, файлов в ZIP: {len(names)}")
