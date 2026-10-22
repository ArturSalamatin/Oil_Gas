"""Проба при планировании DEBT-059: выполнимы ли два дистрибутива — на копиях, без правки исходников.

Проверяет предположения плана до реализации:
  1. setuptools берёт версию 1.0.3+gpn.1 из radial_blackoil.__version__
     статически, не импортируя пакет (в изолированной сборке numpy нет);
  2. в колесо radial-blackoil попадает только пакет radial_blackoil
     (tests/ прототипа с __init__.py — нет);
  3. pip без PyPI (--no-index) находит radial-blackoil==1.0.3+gpn.1
     среди локальных колёс как зависимость gpn-multiphase-solver;
  4. в чистом окружении (python -I) ядро считает пример побитово так же,
     как сейчас из репозитория;
  5. установка с правкой исходников (pip install -e) обоих пакетов.

Всё — в numerical_solver/build/debt059_feasibility/ (build/ игнорируется git).
Запуск из корня репозитория интерпретатором общего venv:

    numerical_solver\\.venv\\Scripts\\python -X utf8 vault\\issues\\debt-059\\probes\\packaging_feasibility.py
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path.cwd()
SOLVER = ROOT / "numerical_solver"
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из корня репозитория; сейчас {ROOT}")
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
PY = Path(sys.executable)
WORK = SOLVER / "build" / "debt059_feasibility"
PROBES = Path(__file__).resolve().parent
VERSION = "1.0.3+gpn.1"

PROTO_PYPROJECT = f"""\
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "radial-blackoil"
dynamic = ["version"]
requires-python = ">=3.10"
dependencies = [
    "numpy>=1.24",
    "scipy>=1.10",
    "matplotlib>=3.7",
    "XlsxWriter>=3.2",
]

[tool.setuptools.dynamic]
version = {{attr = "radial_blackoil.__version__"}}

[tool.setuptools.packages.find]
where = ["."]
include = ["radial_blackoil*"]
"""


def run(cmd, **kw) -> subprocess.CompletedProcess:
    """Запуск команды; вывод — в результат, ошибка — остановка с текстом."""
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    if p.returncode != 0:
        print(f"ОШИБКА rc={p.returncode}: {' '.join(map(str, cmd))}")
        print(p.stdout[-3000:])
        print(p.stderr[-3000:])
        sys.exit(1)
    return p


def main() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    # ── Копия прототипа с pyproject.toml и версией 1.0.3+gpn.1 ──
    proto = WORK / "proto"
    shutil.copytree(PROTO / "radial_blackoil", proto / "radial_blackoil",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(PROTO / "tests", proto / "tests",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (proto / "pyproject.toml").write_text(PROTO_PYPROJECT, encoding="utf-8")
    init = proto / "radial_blackoil" / "__init__.py"
    src = init.read_text(encoding="utf-8")
    assert src.startswith("__version__='1.0.3'"), src[:40]
    init.write_text(src.replace("__version__='1.0.3'", f"__version__='{VERSION}'", 1),
                    encoding="utf-8")

    # ── Копия пакета GPN с зависимостью от прототипа ──
    gpn = WORK / "gpn"
    shutil.copytree(SOLVER / "gpn_multiphase_solver", gpn / "gpn_multiphase_solver",
                    ignore=shutil.ignore_patterns("__pycache__"))
    text = (SOLVER / "pyproject.toml").read_text(encoding="utf-8")
    anchor = '    "matplotlib>=3.7",\n]'
    assert anchor in text
    text = text.replace(anchor, f'    "matplotlib>=3.7",\n    "radial-blackoil=={VERSION}",\n]', 1)
    (gpn / "pyproject.toml").write_text(text, encoding="utf-8")

    # ── 1–2. Колёса ──
    wheels = WORK / "wheels"
    run([PY, "-m", "pip", "wheel", "--no-deps", "-q", "-w", wheels, proto, gpn])
    for whl in sorted(wheels.glob("*.whl")):
        with zipfile.ZipFile(whl) as z:
            names = z.namelist()
            tops = sorted({n.split("/")[0] for n in names})
            meta = next(n for n in names if n.endswith(".dist-info/METADATA"))
            lines = z.read(meta).decode("utf-8").splitlines()
        print(f"{whl.name}: верхние каталоги {tops}")
        for ln in lines:
            if ln.startswith(("Version:", "Requires-Dist:")):
                print(f"  {ln}")

    # ── Зависимости — локально, в версиях общего venv (отпечаток сравним) ──
    freeze = run([PY, "-m", "pip", "freeze", "--exclude-editable"]).stdout
    constraints = WORK / "constraints.txt"
    constraints.write_text(freeze, encoding="utf-8")
    run([PY, "-m", "pip", "download", "-q", "-d", wheels, "-c", constraints,
         "numpy", "scipy", "matplotlib", "XlsxWriter", "setuptools>=68"])

    # ── 3–4. Чистое окружение, колёса, без PyPI ──
    venv_a = WORK / "venv_wheels"
    run([PY, "-m", "venv", venv_a])
    py_a = venv_a / "Scripts" / "python.exe"
    run([py_a, "-m", "pip", "install", "-q", "--no-index", "--find-links", wheels,
         "gpn-multiphase-solver"])
    print("venv_wheels: pip check —", run([py_a, "-m", "pip", "check"]).stdout.strip())
    fp_a = run([py_a, "-I", "-X", "utf8", PROBES / "history_fingerprint.py",
                "--examples", SOLVER / "examples", "--only", "03_standing_corey"],
               cwd=WORK)
    print("venv_wheels, импорты:\n" + fp_a.stderr.strip())

    # Текущее состояние: общий venv, прототип через PYTHONPATH (как вставка в sys.path)
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = f"{SOLVER};{PROTO}"
    fp_0 = run([PY, "-X", "utf8", PROBES / "history_fingerprint.py",
                "--examples", SOLVER / "examples", "--only", "03_standing_corey"],
               cwd=WORK, env=env)
    print("текущее, импорты:\n" + fp_0.stderr.strip())
    same = fp_a.stdout == fp_0.stdout
    print(f"отпечаток 03: {'СОВПАЛ' if same else 'РАЗНЫЙ'}")
    print(fp_a.stdout.strip())
    if not same:
        print(fp_0.stdout.strip())

    # ── 5. Установка с правкой исходников, тоже без PyPI ──
    venv_b = WORK / "venv_editable"
    run([PY, "-m", "venv", venv_b])
    py_b = venv_b / "Scripts" / "python.exe"
    run([py_b, "-m", "pip", "install", "-q", "--no-index", "--find-links", wheels,
         "-e", proto, "-e", gpn])
    print("venv_editable: pip check —", run([py_b, "-m", "pip", "check"]).stdout.strip())
    p = run([py_b, "-I", "-c",
             "import radial_blackoil as r, gpn_multiphase_solver as g;"
             "from importlib.metadata import version;"
             "print(r.__file__); print(g.__file__); print(version('radial-blackoil'))"],
            cwd=WORK)
    print("venv_editable, импорты:\n" + p.stdout.strip())


if __name__ == "__main__":
    main()
