"""Приёмочная проверка копии решателя в свежем окружении (FEAT-031).

Повторяется на машине команды разработки после получения архива: распакуйте
архив в новый каталог и запустите любым Python 3.10 или новее (Windows):

    py -3 tools\\acceptance.py

Проверки — каждая строкой «ОК» или «ОШИБКА», итог — последней строкой:
  1. в копии нет .venv — приёмка идёт на свежей копии;
  2. setup.bat создаёт .venv и ставит оба пакета (нужен доступ к PyPI);
  3. номера установленных пакетов — те, что в исходном коде копии;
  4. полный прогон тестов (около 12 мин): ни одного отказа, пропуски — только
     с известными причинами; числа расчётов примеров тесты сверяют с README
     с допусками, поэтому отдельного эталона нет;
  5. HTML-документация собирается без предупреждений;
  6. расчёт по книге Excel из постороннего каталога: шаблон → расчёт →
     файлы результатов; versions.txt — версии этого окружения;
  7. расчёт по файлу конфигурации из постороннего каталога (копия примера 06).

Посторонний каталог — <копия>-acceptance рядом с копией; создаётся заново.
Код возврата: 0 — приёмка пройдена, 1 — нет. Только стандартная библиотека.
"""

import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]                  # корень копии (numerical_solver)
WORK = ROOT.parent / f"{ROOT.name}-acceptance"
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
SOLVER_EXE = ROOT / ".venv" / "Scripts" / "gpn-solver.exe"
EXAMPLE = "06_table_corey_rp"

# Допустимые причины пропуска тестов в копии — подстроки сообщений pytest.skip
# (сверку с исходниками тестов делает tests/test_acceptance_script.py)
ALLOWED_SKIPS = (
    "нет vault/knowledge/",            # test_eq_references.py: заметок vault в копии нет
    "черновик руководителя вне git",   # test_xlsx_reader.py: книги руководителя в копии нет
    "нет problem_statement.aux",       # test_docs.py: .aux в копию не входит
    "could not import 'tomllib'",      # Python 3.10: test_cli.py, test_packaging.py
)
# Файлы результатов расчёта (README §3.5); у книги ещё input/config.json
REQUIRED_OUTPUT = (
    "well_history.csv", "profiles.csv", "versions.txt",
    "pressure_profiles.png", "temperature_profiles.png", "saturation_profiles.png",
    "rs_profiles.png", "well_rates.png", "wellbore_dynamics.png",
    "relperm.png", "pvt.png", "energy_balance.png", "mass_balance.png",
)
VERSION_RE = re.compile(r"""^__version__\s*=\s*(['"])([^'"]+)\1""", re.M)
PIN_RE = re.compile(r'"radial-blackoil==([^"]+)"')

failures: list[str] = []


# ── Чистые функции (проверяются тестами) ─────────────────────

def parse_skips(stdout: str) -> list[tuple[int, str]]:
    """Строки «SKIPPED [n] файл:строка: причина» итога pytest -rs → (n, причина)."""
    return [(int(m.group(1)), m.group(2).strip())
            for m in re.finditer(r"^SKIPPED \[(\d+)\] [^:\n]+:\d+: (.+)$", stdout, re.M)]


def disallowed_skips(skips: list[tuple[int, str]], allowed=ALLOWED_SKIPS) -> list[str]:
    """Причины пропуска, которых нет среди допустимых."""
    return [reason for _, reason in skips if not any(a in reason for a in allowed)]


def missing_outputs(directory: Path, required) -> list[str]:
    """Файлы из required, которых нет в directory (пути — относительно неё)."""
    return [name for name in required if not (Path(directory) / name).is_file()]


def read_versions(path: Path) -> dict[str, str]:
    """versions.txt каталога результатов: по строке «имя номер» → {имя: номер}."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        name, _, ver = line.strip().partition(" ")
        if name:
            out[name] = ver.strip()
    return out


def source_versions(root: Path = ROOT) -> tuple[str, str]:
    """Номер решателя (литерал __version__) и требуемый номер radial-blackoil из pyproject.toml."""
    init = (root / "gpn_multiphase_solver" / "__init__.py").read_text(encoding="utf-8")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    return VERSION_RE.search(init).group(2), PIN_RE.search(pyproject).group(1)


# ── Запуск ───────────────────────────────────────────────────

def check(ok: bool, what: str) -> bool:
    """Строка результата; неудача — в общий список."""
    print(f"{'ОК    ' if ok else 'ОШИБКА'} {what}", flush=True)
    if not ok:
        failures.append(what)
    return ok


def run(cmd, cwd: Path, timeout: float = 3600) -> subprocess.CompletedProcess:
    """Команда с выводом в строку; окружение — без активированного venv вызывающего."""
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def tail(p: subprocess.CompletedProcess, n: int = 2000) -> str:
    """Хвост вывода команды для сообщения об ошибке."""
    return (p.stdout[-n:] + "\n" + p.stderr[-n:]).strip()


def main() -> int:
    print(f"Приёмка копии: {ROOT}\nПосторонний каталог: {WORK}", flush=True)
    if sys.platform != "win32":
        print("Приёмка — только Windows (setup.bat)")
        return 1
    t_all = time.perf_counter()

    # ── 1. Свежая копия ──
    if not check(not (ROOT / ".venv").exists(),
                 "в копии нет .venv (приёмка — на свежей копии: распакуйте архив заново)"):
        return 1
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    # ── 2. setup.bat — из постороннего каталога: скрипт находит свой сам ──
    t0 = time.perf_counter()
    p = run(["cmd", "/c", ROOT / "setup.bat"], cwd=WORK, timeout=1800)
    if not check(p.returncode == 0 and VENV_PY.is_file(),
                 f"setup.bat: код {p.returncode} ({time.perf_counter() - t0:.0f} с)"):
        print(tail(p))
        return 1

    # ── 3. Версии ──
    gpn_ver, proto_ver = source_versions()
    p = run([VENV_PY, "-m", "gpn_multiphase_solver", "--version"], cwd=WORK)
    check(p.stdout.strip() == f"gpn-multiphase-solver {gpn_ver}",
          f"gpn-solver --version: {p.stdout.strip()!r}, в коде {gpn_ver}")
    p = run([VENV_PY, "-c", "import radial_blackoil; print(radial_blackoil.__version__)"], cwd=WORK)
    check(p.stdout.strip() == proto_ver,
          f"radial-blackoil: {p.stdout.strip()!r}, требуется {proto_ver}")
    p = run([VENV_PY, "-c", "import platform, numpy, scipy; "
             "print(platform.python_version(), numpy.__version__, scipy.__version__)"], cwd=WORK)
    py_ver, np_ver, sp_ver = (p.stdout.split() + ["?", "?", "?"])[:3]
    print(f"       окружение: Python {py_ver}, numpy {np_ver}, scipy {sp_ver}")

    # ── 4. Полный прогон тестов ──
    t0 = time.perf_counter()
    p = run([VENV_PY, "-m", "pytest", "tests", "-q", "-rs", "-p", "no:cacheprovider"],
            cwd=ROOT, timeout=7200)
    summary = next((s for s in reversed(p.stdout.splitlines()) if " in " in s and "passed" in s), "")
    skips = parse_skips(p.stdout)
    bad = disallowed_skips(skips)
    check(p.returncode == 0, f"тесты: {summary.strip('= ')} ({time.perf_counter() - t0:.0f} с)")
    for n, reason in skips:
        print(f"       пропущено {n}: {reason}")
    check(not bad, f"пропуски только с известными причинами{'' if not bad else ': ' + '; '.join(bad)}")
    if p.returncode != 0:
        print(tail(p, 4000))

    # ── 5. Документация ──
    p = run([VENV_PY, "-m", "sphinx", "-W", "-b", "html", "-q", "-d", WORK / "doctrees",
             ROOT / "doc" / "source", WORK / "html"], cwd=ROOT, timeout=600)
    check(p.returncode == 0 and (WORK / "html" / "index.html").is_file(),
          f"документация без предупреждений: код {p.returncode}")
    if p.returncode != 0:
        print(tail(p))

    expected = {"gpn-multiphase-solver": gpn_ver, "radial-blackoil": proto_ver,
                "Python": py_ver, "numpy": np_ver, "scipy": sp_ver}

    # ── 6. Книга из постороннего каталога ──
    book = WORK / "book"
    book.mkdir()
    p = run([SOLVER_EXE, "template", "case.xlsx"], cwd=book)
    check(p.returncode == 0 and (book / "case.xlsx").is_file(), f"шаблон книги: код {p.returncode}")
    p = run([SOLVER_EXE, "run", "case.xlsx"], cwd=book, timeout=1800)
    lost = missing_outputs(book / "output", REQUIRED_OUTPUT + ("input/config.json",))
    check(p.returncode == 0 and not lost,
          f"расчёт по книге: код {p.returncode}, нет файлов: {lost or '—'}")
    if p.returncode != 0:
        print(tail(p))
    if (book / "output" / "versions.txt").is_file():
        got = read_versions(book / "output" / "versions.txt")
        check(got == expected, f"versions.txt: {got}")

    # ── 7. Файл конфигурации из постороннего каталога ──
    case = WORK / "case06"
    case.mkdir()
    for f in [ROOT / "examples" / EXAMPLE / "config.json",
              *sorted((ROOT / "examples" / EXAMPLE).glob("*.csv"))]:
        shutil.copy(f, case / f.name)
    p = run([VENV_PY, "-I", "-m", "gpn_multiphase_solver", "run", Path("case06") / "config.json"],
            cwd=WORK, timeout=1800)
    lost = missing_outputs(case / "output", REQUIRED_OUTPUT)
    check(p.returncode == 0 and not lost,
          f"расчёт по конфигурации ({EXAMPLE}): код {p.returncode}, нет файлов: {lost or '—'}")
    if p.returncode != 0:
        print(tail(p))

    print(f"Время приёмки: {time.perf_counter() - t_all:.0f} с ({platform.platform()})")
    print("ПРИЁМКА: ПРОЙДЕНА" if not failures else f"ПРИЁМКА: НЕ ПРОЙДЕНА — {len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        # Консоль Windows (cp1251) не кодирует часть знаков вывода pytest и решателя
        stream.reconfigure(errors="replace")
    sys.exit(main())
