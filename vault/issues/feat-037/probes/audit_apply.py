"""Аудит плана FEAT-037: правки шагов 1–5 на копии дерева из git, затем тесты и сценарий.

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-037/probes/audit_apply.py [REF] [--fast]

REF — коммит или ветка (по умолчанию HEAD): дерево numerical_solver/ берётся
git archive (только файлы под git), распаковывается в
numerical_solver/build/feat037_audit/<REF>/ (игнорируется git). Правки — те же
строки, что в блоках «После» плана; каждый якорь «До» обязан найтись ровно
один раз. Текст CHANGELOG.md извлекается из файла плана. --fast — ещё и
быстрый уровень тестов на копии. Рабочее дерево и git не меняются.
"""

import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import textwrap
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PY = ROOT / "numerical_solver" / ".venv" / "Scripts" / "python.exe"
PLAN = ROOT / "vault" / "plans" / "feat-037 solver-version-changelog.md"
argv = [a for a in sys.argv[1:] if not a.startswith("--")]
REF = argv[0] if argv else "HEAD"
FAST = "--fast" in sys.argv
failed = 0


def check(ok: bool, text: str) -> None:
    global failed
    failed += not ok
    print(("ОК      " if ok else "ОШИБКА  ") + text)


# ── Копия дерева ──
slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", REF)
work = ROOT / "numerical_solver" / "build" / "feat037_audit" / slug
if work.exists():
    shutil.rmtree(work)
work.mkdir(parents=True)
sha = subprocess.run(["git", "rev-parse", "--short", REF], cwd=ROOT, capture_output=True,
                     text=True, check=True).stdout.strip()
tar = subprocess.run(["git", "archive", "--format=tar", REF, "numerical_solver"], cwd=ROOT,
                     capture_output=True, check=True).stdout
with tarfile.open(fileobj=io.BytesIO(tar)) as t:
    t.extractall(work, filter="data")
S = work / "numerical_solver"
print(f"Копия {REF} ({sha}): {S}")


def edit(rel: str, old: str, new: str) -> None:
    """Замена old → new ровно в одном месте файла копии (якорь «До» плана)."""
    p = S / rel
    text = p.read_text(encoding="utf-8")
    n = text.count(old)
    check(n == 1, f"{rel}: якорь найден {n} раз — {old.strip().splitlines()[0][:70]!r}")
    if n == 1:
        p.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


# ── Шаг 1: __init__.py, pyproject.toml, test_packaging.py ──
edit("gpn_multiphase_solver/__init__.py",
     '"""gpn_multiphase_solver — FVM solver for two-phase Black Oil with energy equation."""\n',
     '"""gpn_multiphase_solver — FVM solver for two-phase Black Oil with energy equation."""\n'
     "\n"
     "# Номер версии пакета (FEAT-037) — единственный источник: pyproject.toml\n"
     "# берёт его через [tool.setuptools.dynamic]. Только литерал, без вычислений\n"
     "# и импортов: setuptools читает его разбором исходника, не импортируя\n"
     "# пакет. Форма — PEP 440, три числа MAJOR.MINOR.PATCH; между выпусками —\n"
     "# суффикс .devN. Правило номеров — CHANGELOG.md.\n"
     '__version__ = "1.0.0.dev0"\n')
edit("pyproject.toml",
     'version = "0.1.0"\n',
     "# Номер — литерал gpn_multiphase_solver.__version__ ([tool.setuptools.dynamic]\n"
     "# ниже, FEAT-037); правило номеров — CHANGELOG.md\n"
     'dynamic = ["version"]\n')
edit("pyproject.toml",
     "[tool.setuptools.packages.find]\n",
     "[tool.setuptools.dynamic]\n"
     "# Единственный источник номера — литерал в gpn_multiphase_solver/__init__.py,\n"
     "# как у прототипа (DEBT-059). setuptools читает его разбором исходника, без\n"
     "# импорта пакета: в изолированной сборке numpy нет.\n"
     'version = {attr = "gpn_multiphase_solver.__version__"}\n'
     "\n"
     "[tool.setuptools.packages.find]\n")
edit("tests/test_packaging.py",
     '"""Установка пакетов: зависимости, версия прототипа, ',
     '"""Установка пакетов: зависимости, версии решателя (FEAT-037) и прототипа, ')
edit("tests/test_packaging.py",
     "import pytest\n",
     "import pytest\n"
     "# packaging — зависимость pytest (packaging>=22), не пакета решателя\n"
     "from packaging.version import Version\n")
edit("tests/test_packaging.py",
     'PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"  # дистрибутив radial-blackoil\n',
     'PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"  # дистрибутив radial-blackoil\n'
     'SOLVER_INIT = SOLVER / "gpn_multiphase_solver" / "__init__.py"  # литерал __version__ решателя\n')
STEP1_TESTS = '''
    def test_solver_version_is_dynamic_from_literal(self):
        """Версия дистрибутива решателя — из gpn_multiphase_solver.__version__: один источник номера (FEAT-037)."""
        proj = _pyproject(SOLVER / "pyproject.toml")
        assert proj["project"]["dynamic"] == ["version"]
        # Статический номер рядом с dynamic — второй источник (setuptools
        # отвергает сборку), его возврат при правке pyproject.toml ловится здесь
        assert "version" not in proj["project"]
        assert proj["tool"]["setuptools"]["dynamic"]["version"] == {
            "attr": "gpn_multiphase_solver.__version__"}

    def test_solver_version_literal_follows_rule(self):
        """__version__ решателя — литерал, каноническая форма PEP 440, ровно три числа MAJOR.MINOR.PATCH."""
        # _static_version отвергает вычисляемое значение (не ast.Constant)
        text = _static_version(SOLVER_INIT)
        version = Version(text)            # InvalidVersion — не PEP 440
        assert str(version) == text, f"не каноническая форма PEP 440: {text!r} → {version}"
        # '1.0' по PEP 440 канонична (проба plan_checks.py) — число частей отдельно
        assert len(version.release) == 3, f"не MAJOR.MINOR.PATCH: {text!r}"
'''
STEP2_TEST = '''
    def test_changelog_has_section_for_version(self):
        """Журнал согласован с номером: до выпуска — раздел «Не выпущено», выпуск — раздел своего номера (FEAT-037)."""
        # is_prerelease истинно для .devN, aN, bN, rcN. Ловит выпуск без
        # раздела журнала. Суффикс .dev, забытый после выпуска, не ловит:
        # номер ставит выпуск (FEAT-031), журнал за него не отвечает
        version = Version(_static_version(SOLVER_INIT))
        lines = (SOLVER / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
        if version.is_prerelease:
            assert "## Не выпущено" in lines, "номер до выпуска, а раздела «Не выпущено» нет"
        else:
            head = re.compile(rf"## {re.escape(str(version))}( |$)")
            assert any(head.match(s) for s in lines), f"нет раздела «## {version} — <дата>»"
'''
anchor = ('            "attr": "radial_blackoil.__version__"}\n')
edit("tests/test_packaging.py", anchor, anchor + STEP1_TESTS + STEP2_TEST)

# ── Шаг 2: CHANGELOG.md — текст из файла плана ──
plan = PLAN.read_text(encoding="utf-8")
m = re.search(r"текст целиком:\n    ```markdown\n(.*?)\n    ```\n", plan, re.S)
check(m is not None, "текст CHANGELOG.md найден в плане")
changelog = textwrap.dedent(m.group(1)) + "\n" if m else ""
(S / "CHANGELOG.md").write_text(changelog, encoding="utf-8", newline="\n")

# ── Шаг 3: cli.py ──
edit("gpn_multiphase_solver/cli.py",
     '"""\n\nfrom __future__ import annotations\n',
     "\nНомер версии: gpn-solver --version (FEAT-037) — номер решателя; решатель\n"
     "и прототип не импортируются.\n"
     '"""\n\nfrom __future__ import annotations\n')
edit("gpn_multiphase_solver/cli.py",
     "from pathlib import Path\n",
     "from pathlib import Path\n\nfrom . import __version__\n")
edit("gpn_multiphase_solver/cli.py",
     '"(gpn_multiphase_solver).")\n',
     '"(gpn_multiphase_solver).")\n'
     "    # Номер решателя (FEAT-037). Строка — имя дистрибутива, а не %(prog)s:\n"
     "    # prog зависит от способа запуска (gpn-solver.exe, python -m …), а\n"
     "    # строка совпадает с первой строкой versions.txt. argparse печатает её в\n"
     "    # stdout и выходит с кодом 0 до проверки обязательной подкоманды.\n"
     "    # Прототип не импортируется — как и для --help.\n"
     '    p.add_argument("--version", action="version",\n'
     '                   version=f"gpn-multiphase-solver {__version__}")\n')
edit("tests/test_cli.py",
     "import gpn_multiphase_solver.report.pipeline as pipeline\n",
     "import gpn_multiphase_solver\nimport gpn_multiphase_solver.report.pipeline as pipeline\n")
# Пункт «Проверяется»: в конец списка — перед пустой строкой и абзацем о PYTHONPATH
edit("tests/test_cli.py",
     " прототип не импортируются.\n\nПодпроцессы получают PYTHONPATH",
     " прототип не импортируются;\n"
     "  - номер версии (FEAT-037): --version без импорта решателя и прототипа;\n"
     "    строка «Версии: …» в печати и versions.txt в каталоге вывода.\n"
     "\nПодпроцессы получают PYTHONPATH")
STEP3_TESTS = '''

# ── Номер версии (FEAT-037) ──────────────────────────────────

def test_version_flag(capsys):
    """--version: «gpn-multiphase-solver <номер>» в stdout, код 0 — подкоманда не нужна."""
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0
    assert capsys.readouterr().out == f"gpn-multiphase-solver {gpn_multiphase_solver.__version__}\\n"


def test_version_does_not_import_solver(tmp_path):
    """--version, как и template, не импортирует решатель, scipy и прототип: номер — литерал пакета."""
    code = ("import sys\\nfrom gpn_multiphase_solver import cli\\n"
            "try:\\n    cli.main(['--version'])\\nexcept SystemExit as e:\\n    rc = e.code\\n"
            "print(rc, 'scipy' in sys.modules, 'radial_blackoil' in sys.modules)")
    r = _run(["-c", code], cwd=tmp_path)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split()[-3:] == ["0", "False", "False"]
'''
STEP4_TEST = '''

def test_versions_sources():
    """Пары versions.txt: решатель и прототип — литералы модулей этого дерева, затем Python, numpy, scipy.

    Ловит подмену источника метаданными pip: в основном каталоге они
    отстают от литерала до переустановки (0.1.0 на 2026-10-18).
    """
    import platform

    import numpy as np
    import radial_blackoil
    import scipy
    assert pipeline._versions() == [
        ("gpn-multiphase-solver", gpn_multiphase_solver.__version__),
        ("radial-blackoil", radial_blackoil.__version__),
        ("Python", platform.python_version()),
        ("numpy", np.__version__),
        ("scipy", scipy.__version__)]
'''
p = S / "tests" / "test_cli.py"
p.write_text(p.read_text(encoding="utf-8").rstrip("\n") + "\n" + STEP3_TESTS + STEP4_TEST,
             encoding="utf-8", newline="\n")

# ── Шаг 4: pipeline.py, test_cli.py, test_examples.py ──
edit("gpn_multiphase_solver/report/pipeline.py", "import shutil\n", "import platform\nimport shutil\n")
edit("gpn_multiphase_solver/report/pipeline.py",
     "from ..factory import SimulatorFactory\n",
     "from .. import __version__\nfrom ..factory import SimulatorFactory\n")
edit("gpn_multiphase_solver/report/pipeline.py",
     '    print(f"=== {title} ===")\n    print(f"Конфиг: {config_path}")\n',
     "    # Версии — после проверки конфига: при его ошибке stdout по-прежнему\n"
     "    # пуст (test_run_case_config_errors). Тот же список пишется в\n"
     "    # versions.txt после расчёта (FEAT-037)\n"
     "    versions = _versions()\n"
     '    print(f"=== {title} ===")\n    print(f"Конфиг: {config_path}")\n'
     '    print("Версии: " + ", ".join(f"{name} {ver}" for name, ver in versions))\n')
edit("gpn_multiphase_solver/report/pipeline.py",
     "    output_dir.mkdir(parents=True, exist_ok=True)\n",
     "    output_dir.mkdir(parents=True, exist_ok=True)\n"
     "\n"
     "    # ── Версии (FEAT-037) ──\n"
     "    # Какой версией получены результаты: решатель и прототип, а также Python,\n"
     "    # numpy и scipy — от них зависят последние разряды чисел\n"
     '    (output_dir / "versions.txt").write_text(\n'
     '        "".join(f"{name} {ver}\\n" for name, ver in versions), encoding="utf-8")\n')
edit("gpn_multiphase_solver/report/pipeline.py",
     "конфиг и его CSV внутри него — отказ до расчёта.\n",
     "конфиг и его CSV внутри него — отказ до расчёта.\n"
     "    В нём же versions.txt — версии решателя, прототипа, Python, numpy и\n"
     "    scipy (FEAT-037).\n")
edit("gpn_multiphase_solver/report/pipeline.py",
     "def _print_summary(",
     "def _versions() -> list[tuple[str, str]]:\n"
     '    """Версии решателя, прототипа, Python, numpy, scipy — пары (имя, номер) для versions.txt и печати. FEAT-037."""\n'
     "    # Импорт здесь, как во всём пакете: прототип импортируется при сборке\n"
     "    # задачи, а не при импорте модулей. Номер прототипа — из модуля,\n"
     "    # который считает задачу, а не из метаданных pip: у редактируемой\n"
     "    # установки они записаны при pip install -e и отстают от кода, в\n"
     "    # worktree — принадлежат основному каталогу. build_info.VERSION\n"
     "    # ('1.0.3') — номер для регрессии прототипа, не номер дистрибутива.\n"
     "    import radial_blackoil\n"
     "    import scipy\n"
     '    return [("gpn-multiphase-solver", __version__),\n'
     '            ("radial-blackoil", radial_blackoil.__version__),\n'
     '            ("Python", platform.python_version()),\n'
     '            ("numpy", np.__version__),\n'
     '            ("scipy", scipy.__version__)]\n'
     "\n\n"
     "def _print_summary(")
edit("tests/test_cli.py",
     '    "relperm.png", "pvt.png", "energy_balance.png", "mass_balance.png",\n])\n',
     '    "relperm.png", "pvt.png", "energy_balance.png", "mass_balance.png",\n'
     "    # FEAT-037: версии, которыми получены результаты\n"
     '    "versions.txt",\n])\n')
edit("tests/test_cli.py",
     '    """Команда из постороннего каталога: код 0, 12 файлов штатного набора, заголовок из конфига.',
     '    """Команда из постороннего каталога: код 0, 13 файлов штатного набора, строка версий и versions.txt, заголовок из конфига.')
edit("tests/test_cli.py",
     '    assert lines[1] == f"Конфиг: {cfg.resolve()}"\n',
     '    assert lines[1] == f"Конфиг: {cfg.resolve()}"\n'
     "    # FEAT-037: строка версий третьей и versions.txt — тот же список. Подпроцесс\n"
     "    # — тот же интерпретатор и PYTHONPATH на это дерево: пары совпадают\n"
     '    expected = [f"{name} {ver}" for name, ver in pipeline._versions()]\n'
     '    assert lines[2] == "Версии: " + ", ".join(expected)\n'
     '    assert (out / "versions.txt").read_text(encoding="utf-8").splitlines() == expected\n')
edit("tests/test_examples.py",
     '        "pvt.png",\n    ]\n    for fname in expected:\n',
     '        "pvt.png",\n'
     "        # FEAT-037: версии, которыми получены результаты\n"
     '        "versions.txt",\n'
     "    ]\n    for fname in expected:\n")

# ── Шаг 5: README ──
edit("README.md",
     "| [doc/](doc/) | постановка задачи (LaTeX) |\n",
     "| [doc/](doc/) | постановка задачи (LaTeX) |\n"
     "| [CHANGELOG.md](CHANGELOG.md) | журнал изменений между выпусками, правило номеров версий |\n")
edit("README.md",
     "Проверка установки:\n\n```powershell\n.venv\\Scripts\\python -m gpn_multiphase_solver run --help\n```\n",
     "Проверка установки:\n\n```powershell\n.venv\\Scripts\\python -m gpn_multiphase_solver run --help\n```\n"
     "\nНомер установленной версии решателя печатает\n"
     "`.venv\\Scripts\\python -m gpn_multiphase_solver --version`; изменения между\n"
     "версиями и правило номеров — в [CHANGELOG.md](CHANGELOG.md).\n")
edit("README.md",
     "| балансы энергии и массы компонентов — контроль разностной схемы |\n",
     "| балансы энергии и массы компонентов — контроль разностной схемы |\n"
     "| `versions.txt` | версии решателя, прототипа, Python, numpy и scipy, которыми получены результаты: по строке «имя номер» |\n")
edit("README.md",
     "В консоль выводятся сводка (давление и температура у забоя и дебиты на конец\n"
     "расчёта), невязки балансов энергии и массы, проверка равновесия $R_s$ и\n"
     "сводка PVT. Дебиты при добыче положительны. Время на всех графиках — в сутках.\n",
     "В консоль выводятся: перед расчётом — путь к файлу конфигурации и версии\n"
     "(те же, что в `versions.txt`); после расчёта — сводка (давление и\n"
     "температура у забоя и дебиты на конец расчёта), невязки балансов энергии и\n"
     "массы, проверка равновесия $R_s$ и сводка PVT. Дебиты при добыче\n"
     "положительны. Время на всех графиках — в сутках.\n")
edit("README.md",
     "Полезные модули:\n",
     "Номер версии пакета — строка `gpn_multiphase_solver.__version__` (форма\n"
     "PEP 440; правило номеров — [CHANGELOG.md](CHANGELOG.md)).\n\nПолезные модули:\n")
edit("README.md",
     "- [doc/problem_statement.tex](doc/problem_statement.tex) — постановка задачи и дискретные уравнения;\n",
     "- [doc/problem_statement.tex](doc/problem_statement.tex) — постановка задачи и дискретные уравнения;\n"
     "- [CHANGELOG.md](CHANGELOG.md) — изменения решателя между выпусками и правило номеров версий;\n")
edit("examples/README.md",
     "приток через контур (нефть, газ) + относительная невязка |\n",
     "приток через контур (нефть, газ) + относительная невязка |\n"
     "| `versions.txt` | версии решателя, прототипа, Python, numpy и scipy, которыми получены результаты |\n")

if failed:
    print(f"\nПравки не применились: {failed}. Тесты не запускаются.")
    sys.exit(1)

# ── Тесты на копии ──
env = dict(os.environ, PYTHONIOENCODING="utf-8")
env.pop("PYTHONPATH", None)


def pytest(*args):
    r = subprocess.run([str(PY), "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
                       cwd=S, env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.returncode, r.stdout


code, out = pytest("tests/", "--collect-only")
print("Собрано:", out.strip().splitlines()[-1])
code, out = pytest("tests/test_packaging.py", "tests/test_cli.py")
print("\n".join(out.strip().splitlines()[-3:]))
check(code == 0, "test_packaging.py + test_cli.py на копии")
code, out = pytest("tests/test_examples.py", "-k", "test_pipeline_writes_output or run_case")
print("\n".join(out.strip().splitlines()[-2:]))
check(code == 0, "test_examples.py: test_pipeline_writes_output и run_case")

# ── Сценарий: команда из постороннего каталога, --version ──
env_cmd = dict(env, PYTHONPATH=os.pathsep.join([str(S), str(S / "HydroSolverPrototype" / "Prototype_1.0.3")]),
               GPN_EXAMPLES_EMF="0")
case = work / "case"
r = subprocess.run([str(PY), "-m", "gpn_multiphase_solver", "--version"], cwd=work, env=env_cmd,
                   capture_output=True, text=True, encoding="utf-8")
print(f"--version: код {r.returncode}, stdout {r.stdout!r}")
check(r.returncode == 0 and r.stdout == "gpn-multiphase-solver 1.0.0.dev0\n", "--version из отдельного процесса")
r = subprocess.run([str(PY), "-m", "gpn_multiphase_solver", "--help"], cwd=work, env=env_cmd,
                   capture_output=True, text=True, encoding="utf-8")
check("--version" in r.stdout, "--version в общей справке")

import json  # noqa: E402
raw = json.loads((S / "examples" / "03_standing_corey" / "config.json").read_text(encoding="utf-8"))
raw["grid"]["N"] = 20
h0 = raw["time"]["history"][0]
raw["time"]["history"] = [dict(h0, duration=86400.0, dt_out=43200.0)]
raw["output"] = {"log_level": "INFO", "title": "проба FEAT-037"}
case.mkdir()
(case / "config.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
r = subprocess.run([str(PY), "-m", "gpn_multiphase_solver", "run", "case/config.json"], cwd=work,
                   env=env_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
check(r.returncode == 0, f"run: код {r.returncode}")
print("Первые строки печати:")
print("\n".join("    " + s for s in r.stdout.splitlines()[:3]))
vt = case / "output" / "versions.txt"
crlf = b"\r\n" in vt.read_bytes()     # write_text на Windows переводит \n в \r\n
print(f"versions.txt ({vt.stat().st_size} байт, CRLF: {crlf}):")
print("\n".join("    " + s for s in vt.read_text(encoding="utf-8").splitlines()))
check(len(vt.read_text(encoding="utf-8").splitlines()) == 5, "versions.txt — 5 строк")

# ── Регулярное выражение раздела выпуска (ветка теста после выпуска) ──
lines = ["# Журнал", "## Правило номеров", "## 1.0.0 — 2026-11-02", "## 1.0.10 — 2027-01-01"]
for v, want in (("1.0.0", True), ("1.0.1", False), ("1.0.10", True), ("1.0.1.post1", False)):
    head = re.compile(rf"## {re.escape(v)}( |$)")
    check(any(head.match(s) for s in lines) == want, f"раздел выпуска {v}: найден = {want}")

# ── pip выбирает 1.0.0.dev0, если других версий нет (README §1, установка без PyPI) ──
wheels = work / "wheels"
r = subprocess.run([str(PY), "-m", "pip", "wheel", "--no-deps", "-q", "-w", str(wheels), str(S)],
                   capture_output=True, text=True)
check(r.returncode == 0, "pip wheel копии" + (f": {r.stderr[-800:]}" if r.returncode else ""))
dl = work / "dl"
r = subprocess.run([str(PY), "-m", "pip", "download", "--no-index", "--find-links", str(wheels),
                    "--no-deps", "-d", str(dl), "gpn-multiphase-solver"], capture_output=True, text=True)
got = sorted(p.name for p in dl.glob("*.whl")) if dl.exists() else []
print(f"pip download --no-index gpn-multiphase-solver: код {r.returncode}, {got}")
check(r.returncode == 0 and got and "1.0.0.dev0" in got[0],
      "pip без --pre берёт единственную версию разработки")

# ── Быстрый уровень на копии ──
if FAST:
    code, out = pytest("tests/", "-m", "not slow")
    print("Быстрый уровень:", out.strip().splitlines()[-1])
    check(code == 0, "быстрый уровень на копии")

print(f"\nИтог: {'все проверки пройдены' if not failed else f'ошибок {failed}'}")
sys.exit(1 if failed else 0)
