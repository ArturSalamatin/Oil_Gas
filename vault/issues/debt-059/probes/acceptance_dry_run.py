"""Проверка самой пробы приёмки при планировании DEBT-059: макет будущего дерева + clean_env_acceptance.py.

Макет — копия numerical_solver с тем, что сделает реализация в части установки:
pyproject.toml прототипа, версия 1.0.3+gpn.1, зависимость GPN от radial-blackoil.
Вставки путей в sys.path в макете не убираются — для пробы приёмки они
безразличны (она запускает python -I в постороннем каталоге).

Всё — в numerical_solver/build/debt059_mock/ (build/ игнорируется git).
Запуск из корня репозитория интерпретатором общего venv:

    numerical_solver\\.venv\\Scripts\\python -X utf8 vault\\issues\\debt-059\\probes\\acceptance_dry_run.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
SOLVER = ROOT / "numerical_solver"
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из корня репозитория; сейчас {ROOT}")
PROBES = Path(__file__).resolve().parent
MOCK = SOLVER / "build" / "debt059_mock" / "numerical_solver"
SKIP = shutil.ignore_patterns("__pycache__", "output", "*.egg-info")

sys.path.insert(0, str(PROBES))
from packaging_feasibility import PROTO_PYPROJECT, VERSION  # noqa: E402


def main() -> None:
    if MOCK.parent.exists():
        shutil.rmtree(MOCK.parent)
    proto_src = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
    proto = MOCK / "HydroSolverPrototype" / "Prototype_1.0.3"
    for name in ("radial_blackoil", "tests"):
        shutil.copytree(proto_src / name, proto / name, ignore=SKIP)
    (proto / "pyproject.toml").write_text(PROTO_PYPROJECT, encoding="utf-8")
    init = proto / "radial_blackoil" / "__init__.py"
    init.write_text(init.read_text(encoding="utf-8").replace(
        "__version__='1.0.3'", f"__version__='{VERSION}'", 1), encoding="utf-8")

    for name in ("gpn_multiphase_solver", "examples"):
        shutil.copytree(SOLVER / name, MOCK / name, ignore=SKIP)
    text = (SOLVER / "pyproject.toml").read_text(encoding="utf-8")
    text = text.replace('    "matplotlib>=3.7",\n]',
                        f'    "matplotlib>=3.7",\n    "radial-blackoil=={VERSION}",\n]', 1)
    (MOCK / "pyproject.toml").write_text(text, encoding="utf-8")

    p = subprocess.run([sys.executable, "-X", "utf8", str(PROBES / "clean_env_acceptance.py"),
                        "--baseline", str(PROBES / "fingerprint_plan_c0ec060.out.txt")],
                       cwd=MOCK, capture_output=True, text=True, encoding="utf-8")
    print(p.stdout)
    print(p.stderr[-2000:])
    sys.exit(p.returncode)


if __name__ == "__main__":
    main()
