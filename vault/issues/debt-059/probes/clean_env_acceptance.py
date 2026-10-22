"""Приёмка DEBT-059: оба дистрибутива ставятся в чистое окружение без PyPI и считают побитово как прежде.

Что проверяет (каждое — строка «ОК»/«ОШИБКА» в выводе, итог — последней строкой):
  1. колёса radial-blackoil и gpn-multiphase-solver собираются из дерева
     (pip wheel); в колесе прототипа — только пакет radial_blackoil;
     версия 1.0.3+gpn.1, у GPN — зависимость radial-blackoil==1.0.3+gpn.1;
  2. окружение «колёса»: pip install --no-index --find-links — без PyPI,
     pip check чистый; python -I импортирует оба пакета из site-packages
     этого окружения; версия дистрибутива = radial_blackoil.__version__;
  3. там же — расчёт примеров 03, 04, 05 из постороннего каталога: отпечаток
     истории (history_fingerprint.py) побитово равен базовому варианту;
  4. там же — вход через Excel: run_workbook на tests/fixtures/short_run.xlsx
     прототипа (нужны XlsxWriter и matplotlib из зависимостей прототипа);
  5. окружение «правка исходников»: pip install -e обоих пакетов без PyPI,
     pip check чистый, python -I импортирует их из проверяемого дерева.

Всё — в <solver>/build/debt059_acceptance/ (build/ игнорируется git; в worktree
удаляется вместе с ним). Общий venv проба НЕ меняет: в нём ничего не ставится.
Зависимости (numpy, scipy, ...) скачиваются в каталог колёс в версиях общего venv
(pip freeze → constraints) — иначе отпечаток мог бы разойтись из-за другой numpy.
Нужен доступ к PyPI для pip download (или кэш pip) и для изолированной сборки
(setuptools).

Запуск интерпретатором общего venv, из проверяемого каталога numerical_solver:

    cd <W>\\numerical_solver
    <КОРЕНЬ>\\numerical_solver\\.venv\\Scripts\\python -X utf8 <W>\\vault\\issues\\debt-059\\probes\\clean_env_acceptance.py ^
        --baseline <W>\\vault\\issues\\debt-059\\probes\\fingerprint_before.out.txt
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PY = Path(sys.executable)
PROBES = Path(__file__).resolve().parent
VERSION = "1.0.3+gpn.1"
EXAMPLES = ("03_standing_corey", "04_table_table", "05_standing_table_rp")

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    """Строка результата; неудача — в общий список."""
    print(f"{'ОК    ' if ok else 'ОШИБКА'} {what}")
    if not ok:
        failures.append(what)


def run(cmd, **kw) -> subprocess.CompletedProcess:
    """Запуск команды; ненулевой код — остановка пробы с выводом команды."""
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    if p.returncode != 0:
        print(f"ОШИБКА rc={p.returncode}: {' '.join(map(str, cmd))}")
        print(p.stdout[-3000:])
        print(p.stderr[-3000:])
        sys.exit(1)
    return p


def make_venv(path: Path) -> Path:
    """Новое окружение от базового интерпретатора общего venv; путь к его python."""
    run([PY, "-m", "venv", path])
    return path / "Scripts" / "python.exe"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True, type=Path,
                    help="вывод history_fingerprint.py на базовом варианте")
    args = ap.parse_args()

    solver = Path.cwd()
    if not (solver / "gpn_multiphase_solver").is_dir():
        sys.exit(f"Запускать из каталога numerical_solver; сейчас {solver}")
    proto = solver / "HydroSolverPrototype" / "Prototype_1.0.3"
    work = solver / "build" / "debt059_acceptance"
    print(f"Проверяемое дерево: {solver}")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    # ── 1. Колёса из дерева ──
    wheels = work / "wheels"
    run([PY, "-m", "pip", "wheel", "--no-deps", "-q", "-w", wheels, proto, solver])
    proto_whl = next(wheels.glob("radial_blackoil-*.whl"))
    gpn_whl = next(wheels.glob("gpn_multiphase_solver-*.whl"))
    with zipfile.ZipFile(proto_whl) as z:
        tops = sorted({n.split("/")[0] for n in z.namelist()})
    check(tops == ["radial_blackoil", f"radial_blackoil-{VERSION}.dist-info"],
          f"колесо прототипа содержит только пакет: {tops}")
    with zipfile.ZipFile(gpn_whl) as z:
        meta = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
        requires = [ln for ln in z.read(meta).decode("utf-8").splitlines()
                    if ln.startswith("Requires-Dist:")]
    check(f"Requires-Dist: radial-blackoil=={VERSION}" in requires,
          f"GPN объявляет radial-blackoil=={VERSION}")

    # Зависимости — в каталог колёс, в версиях общего venv
    constraints = work / "constraints.txt"
    constraints.write_text(run([PY, "-m", "pip", "freeze", "--exclude-editable"]).stdout,
                           encoding="utf-8")
    run([PY, "-m", "pip", "download", "-q", "-d", wheels, "-c", constraints,
         "numpy", "scipy", "matplotlib", "XlsxWriter", "setuptools>=68"])

    # ── 2. Окружение «колёса», без PyPI ──
    py_w = make_venv(work / "venv_wheels")
    run([py_w, "-m", "pip", "install", "-q", "--no-index", "--find-links", wheels,
         "gpn-multiphase-solver"])
    p = subprocess.run([str(py_w), "-m", "pip", "check"], capture_output=True, text=True)
    check(p.returncode == 0, f"venv_wheels: pip check — {p.stdout.strip()}")
    site = (work / "venv_wheels" / "Lib" / "site-packages").resolve()
    p = run([py_w, "-I", "-c",
             "import radial_blackoil as r, gpn_multiphase_solver as g;"
             "from importlib.metadata import version;"
             "print(r.__file__); print(g.__file__);"
             "print(r.__version__); print(version('radial-blackoil'))"], cwd=work)
    r_file, g_file, r_ver, d_ver = p.stdout.split("\n")[:4]
    check(Path(r_file).resolve().is_relative_to(site)
          and Path(g_file).resolve().is_relative_to(site),
          f"venv_wheels: пакеты из site-packages окружения ({r_file}; {g_file})")
    check(r_ver == d_ver == VERSION,
          f"venv_wheels: версия {r_ver} (модуль) = {d_ver} (дистрибутив) = {VERSION}")

    # ── 3. Расчёт из постороннего каталога, побитово ──
    fp_file = work / "fingerprint_clean_env.out.txt"
    run([py_w, "-I", "-X", "utf8", PROBES / "history_fingerprint.py",
         "--examples", solver / "examples", "--only", *EXAMPLES, "--out", fp_file], cwd=work)
    # Построчно и через utf-8-sig: базовый файл мог быть записан с BOM и CRLF
    got = fp_file.read_text(encoding="utf-8-sig").splitlines()
    base = args.baseline.read_text(encoding="utf-8-sig").splitlines()
    check(got == base and len(got) == 2 * len(EXAMPLES),
          "venv_wheels: отпечаток примеров 03, 04, 05 побитово равен базовому")
    if got != base:
        print("\n".join(got))

    # ── 4. Вход через Excel ──
    out = work / "short_run"
    p = run([py_w, "-I", "-c",
             "import sys; from radial_blackoil.runner import run_workbook;"
             "s = run_workbook(sys.argv[1], sys.argv[2]); print(s['status'])",
             proto / "tests" / "fixtures" / "short_run.xlsx", out], cwd=work)
    check(p.stdout.strip() == "SUCCESS" and (out / "results.xlsx").exists()
          and (out / "pressure_profiles.png").exists(),
          f"venv_wheels: run_workbook — {p.stdout.strip()}, results.xlsx и PNG на месте")

    # ── 5. Окружение «правка исходников», без PyPI ──
    py_e = make_venv(work / "venv_editable")
    run([py_e, "-m", "pip", "install", "-q", "--no-index", "--find-links", wheels,
         "-e", proto, "-e", solver])
    p = subprocess.run([str(py_e), "-m", "pip", "check"], capture_output=True, text=True)
    check(p.returncode == 0, f"venv_editable: pip check — {p.stdout.strip()}")
    p = run([py_e, "-I", "-c",
             "import radial_blackoil as r, gpn_multiphase_solver as g;"
             "print(r.__file__); print(g.__file__)"], cwd=work)
    r_file, g_file = p.stdout.split("\n")[:2]
    check(Path(r_file).resolve().is_relative_to(proto.resolve())
          and Path(g_file).resolve().is_relative_to(solver.resolve()),
          f"venv_editable: пакеты из проверяемого дерева ({r_file}; {g_file})")

    print("ПРИЁМКА: ПРОЙДЕНА" if not failures else f"ПРИЁМКА: НЕ ПРОЙДЕНА — {len(failures)}")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    os.environ.pop("PYTHONPATH", None)   # подпроцессы не должны видеть PYTHONPATH вызывающего
    main()
