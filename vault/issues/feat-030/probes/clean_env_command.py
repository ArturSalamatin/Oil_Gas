"""Приёмка FEAT-030: команда расчёта работает в чистом окружении из колёс, из постороннего каталога, и даёт тот же вывод.

Что проверяет (каждое — строка «ОК»/«ОШИБКА» в выводе, итог — последней строкой):
  1. колесо gpn-multiphase-solver содержит подпакет report/ (9 модулей),
     io/figures.py, cli.py, __main__.py; точка входа gpn-solver =
     gpn_multiphase_solver.cli:main;
  2. окружение «колёса» (pip install --no-index): из постороннего каталога
     python -I -m gpn_multiphase_solver run cases\\06_table_corey_rp\\config.json →
     код 0; хеши всех файлов output равны снимку «после» (snap_after.json,
     пример 06 там запущен обёрткой команды), печать — тоже, кроме строки
     времени;
  3. там же gpn-solver.exe run cases\\07_degassing_adiabatic_only\\config.json →
     код 0, хеши файлов равны снимку;
  4. конфиг с output.n_profiles = 1 → код 2, имя поля в stderr;
  5. --output = папка конфига → код 2, конфиг и CSV на месте;
  6. без GPN_EXAMPLES_EMF (как у заказчика) и с INKSCAPE на несуществующий
     путь → код 0, одно предупреждение «Inkscape не найден», в emf/ — SVG без EMF.
Проверки 2–5 — с GPN_EXAMPLES_EMF=0, как снимок.

Сравнивать со снимком можно только примеры, чей main.py — обёртка команды:
у 01–05 и 18 main.py делает ещё собственную часть примера (у 03 —
наложение T и печать tpa.report), команда — только штатный набор.

Всё — в <solver>/build/feat030_acceptance/ (build/ игнорируется git). Общий
venv проба не меняет. Зависимости (numpy, scipy, ...) скачиваются в каталог
колёс в версиях общего venv (pip freeze → constraints) — иначе PNG могли бы
разойтись из-за другой версии matplotlib. Нужен доступ к PyPI для pip
download (или кэш pip) и для изолированной сборки (setuptools).

Запуск интерпретатором общего venv, из проверяемого каталога numerical_solver:

    cd <W>\\numerical_solver
    <КОРЕНЬ>\\numerical_solver\\.venv\\Scripts\\python -X utf8 <W>\\vault\\issues\\feat-030\\probes\\clean_env_command.py ^
        --snapshot <W>\\vault\\issues\\feat-030\\probes\\out\\snap_after.json
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PY = Path(sys.executable)
CASES = ("06_table_corey_rp", "07_degassing_adiabatic_only")
TIME_LINE = re.compile(r"^Время расчёта:")
REPORT_MODULES = {"__init__", "pipeline", "relperm", "pvt", "rs", "closed_form",
                  "energy_balance", "mass_balance", "temperature"}

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    """Строка результата; неудача — в общий список."""
    print(f"{'ОК    ' if ok else 'ОШИБКА'} {what}", flush=True)
    if not ok:
        failures.append(what)


def run(cmd, **kw) -> subprocess.CompletedProcess:
    """Запуск команды подготовки; ненулевой код — остановка пробы с выводом команды."""
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    if p.returncode != 0:
        print(f"ОШИБКА rc={p.returncode}: {' '.join(map(str, cmd))}")
        print(p.stdout[-3000:])
        print(p.stderr[-3000:])
        sys.exit(1)
    return p


def command(cmd, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    """Проверяемый запуск команды расчёта; код возврата оценивает вызывающий."""
    return subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _files(output: Path) -> dict:
    """Хеши файлов каталога вывода — в том же виде, что в снимке."""
    return {f.relative_to(output).as_posix(): _sha(f)
            for f in sorted(output.rglob("*")) if f.is_file()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True, type=Path,
                    help="снимок «после» (snapshot_examples.py snap)")
    args = ap.parse_args()
    snap = json.loads(args.snapshot.read_text(encoding="utf-8"))["examples"]

    solver = Path.cwd()
    if not (solver / "gpn_multiphase_solver").is_dir():
        sys.exit(f"Запускать из каталога numerical_solver; сейчас {solver}")
    proto = solver / "HydroSolverPrototype" / "Prototype_1.0.3"
    work = solver / "build" / "feat030_acceptance"
    print(f"Проверяемое дерево: {solver}")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    # ── 1. Колёса из дерева ──
    wheels = work / "wheels"
    run([PY, "-m", "pip", "wheel", "--no-deps", "-q", "-w", wheels, proto, solver])
    gpn_whl = next(wheels.glob("gpn_multiphase_solver-*.whl"))
    with zipfile.ZipFile(gpn_whl) as z:
        names = z.namelist()
        ep = next((n for n in names if n.endswith(".dist-info/entry_points.txt")), None)
        entry = z.read(ep).decode("utf-8") if ep else ""
    report = {Path(n).stem for n in names
              if n.startswith("gpn_multiphase_solver/report/") and n.endswith(".py")}
    check(report == REPORT_MODULES, f"колесо: report/ — {sorted(report)}")
    need = {"gpn_multiphase_solver/io/figures.py", "gpn_multiphase_solver/cli.py",
            "gpn_multiphase_solver/__main__.py"}
    check(need <= set(names), "колесо: io/figures.py, cli.py, __main__.py")
    check("gpn-solver = gpn_multiphase_solver.cli:main" in entry,
          f"колесо: точка входа gpn-solver ({entry.strip()!r})")

    # Зависимости — в каталог колёс, в версиях общего venv
    constraints = work / "constraints.txt"
    constraints.write_text(run([PY, "-m", "pip", "freeze", "--exclude-editable"]).stdout,
                           encoding="utf-8")
    run([PY, "-m", "pip", "download", "-q", "-d", wheels, "-c", constraints,
         "numpy", "scipy", "matplotlib", "XlsxWriter", "setuptools>=68"])

    # ── 2. Окружение «колёса», без PyPI; команда из постороннего каталога ──
    run([PY, "-m", "venv", work / "venv_wheels"])
    py_w = work / "venv_wheels" / "Scripts" / "python.exe"
    exe_w = work / "venv_wheels" / "Scripts" / "gpn-solver.exe"
    run([py_w, "-m", "pip", "install", "-q", "--no-index", "--find-links", wheels,
         "gpn-multiphase-solver"])
    cases = work / "cases"
    for name in CASES:
        shutil.copytree(solver / "examples" / name, cases / name,
                        ignore=shutil.ignore_patterns("output", "*.py", "README.md",
                                                      "__pycache__"))
    env = dict(os.environ, PYTHONIOENCODING="utf-8", GPN_EXAMPLES_EMF="0")

    name = CASES[0]
    p = command([py_w, "-I", "-m", "gpn_multiphase_solver", "run",
                 Path("cases") / name / "config.json"], cwd=work, env=env)
    check(p.returncode == 0, f"python -m: {name} — код {p.returncode}")
    got = _files(cases / name / "output")
    check(got == snap[name]["files"],
          f"python -m: {name} — {len(got)} файлов побайтно равны снимку")
    # Печать: путь копии → путь в снимке; строку времени не сравниваем
    norm = p.stdout.replace(str(cases.resolve()), "<TREE>" + os.sep + "examples")
    a = [s for s in norm.splitlines() if not TIME_LINE.search(s)]
    b = [s for s in snap[name]["stdout"].splitlines() if not TIME_LINE.search(s)]
    check(a == b, f"python -m: {name} — печать равна снимку ({len(a)} строк)")

    # ── 3. gpn-solver.exe ──
    name = CASES[1]
    p = command([exe_w, "run", Path("cases") / name / "config.json"], cwd=work, env=env)
    check(p.returncode == 0, f"gpn-solver.exe: {name} — код {p.returncode}")
    got = _files(cases / name / "output")
    check(got == snap[name]["files"],
          f"gpn-solver.exe: {name} — {len(got)} файлов побайтно равны снимку")

    # ── 4. Ошибка в конфиге → код 2 ──
    bad = cases / "bad"
    bad.mkdir()
    raw = json.loads((cases / CASES[1] / "config.json").read_text(encoding="utf-8"))
    raw["output"]["n_profiles"] = 1
    (bad / "config.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    p = command([py_w, "-I", "-m", "gpn_multiphase_solver", "run", bad / "config.json"],
                cwd=work, env=env)
    check(p.returncode == 2 and "output.n_profiles" in p.stderr,
          f"ошибка конфига: код {p.returncode}, «output.n_profiles» в stderr")

    # ── 5. Каталог вывода = папка конфига → код 2 до расчёта ──
    case = cases / CASES[0]
    p = command([py_w, "-I", "-m", "gpn_multiphase_solver", "run", case / "config.json",
                 "--output", case], cwd=work, env=env)
    check(p.returncode == 2 and (case / "config.json").is_file()
          and (case / "oil_pvt.csv").is_file(),
          f"--output = папка конфига: код {p.returncode}, конфиг и CSV на месте")

    # ── 6. Без Inkscape, EMF включён (как у заказчика) ──
    env_emf = {k: v for k, v in env.items() if k != "GPN_EXAMPLES_EMF"}
    env_emf["INKSCAPE"] = str(work / "нет" / "inkscape.com")
    out = work / "emf_check"
    p = command([py_w, "-I", "-m", "gpn_multiphase_solver", "run",
                 cases / CASES[1] / "config.json", "--output", out], cwd=work, env=env_emf)
    svg = sorted((out / "emf").glob("*.svg")) if (out / "emf").is_dir() else []
    emf = sorted((out / "emf").glob("*.emf")) if (out / "emf").is_dir() else []
    check(p.returncode == 0 and p.stdout.count("Inkscape не найден") == 1
          and len(svg) > 0 and not emf,
          f"без Inkscape: код {p.returncode}, предупреждений "
          f"{p.stdout.count('Inkscape не найден')}, SVG {len(svg)}, EMF {len(emf)}")

    print("ПРИЁМКА: ПРОЙДЕНА" if not failures else f"ПРИЁМКА: НЕ ПРОЙДЕНА — {len(failures)}")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    os.environ.pop("PYTHONPATH", None)   # подпроцессы не должны видеть PYTHONPATH вызывающего
    main()
