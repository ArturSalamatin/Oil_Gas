"""Пробы плана FEAT-037: --version при обязательной подкоманде, разбор номера, сборка колеса.

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-037/probes/plan_checks.py [--apply-plan] [КАТАЛОГ_РЕШАТЕЛЯ]

КАТАЛОГ_РЕШАТЕЛЯ — numerical_solver основного каталога или worktree (по
умолчанию — основной). В каталог build/feat037_probe/ решателя (игнорируется
git) копируются pyproject.toml и пакет; --apply-plan вносит в копию правки
шага 1 плана (литерал __version__, dynamic). Колесо собирается pip wheel
--no-deps с изоляцией сборки (setuptools в venv нет — нужен доступ к PyPI
или кеш pip). Печать: строка «ОК»/«ОШИБКА» на каждую проверку.
"""

import argparse
import io
import re
import shutil
import subprocess
import sys
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
args = sys.argv[1:]
apply_plan = "--apply-plan" in args
args = [a for a in args if a != "--apply-plan"]
SOLVER = Path(args[0]).resolve() if args else ROOT / "numerical_solver"
PLAN_VERSION = "1.0.0.dev0"
failed = 0


def check(ok: bool, text: str) -> None:
    global failed
    failed += not ok
    print(("ОК      " if ok else "ОШИБКА  ") + text)


print(f"Решатель: {SOLVER}; правки плана в копии: {apply_plan}")

# ── 1. argparse: --version при add_subparsers(required=True) ──
# Как в cli._parser: обязательная подкоманда. action="version" печатает в
# stdout и выходит с кодом 0 до проверки обязательных аргументов.
p = argparse.ArgumentParser(prog="python -m gpn_multiphase_solver")
p.add_argument("--version", action="version", version=f"gpn-multiphase-solver {PLAN_VERSION}")
sub = p.add_subparsers(dest="command", required=True, metavar="команда")
sub.add_parser("run")
buf = io.StringIO()
try:
    with redirect_stdout(buf):
        p.parse_args(["--version"])
    code = None
except SystemExit as e:
    code = e.code
check(code == 0, f"--version: код выхода {code!r}")
check(buf.getvalue() == f"gpn-multiphase-solver {PLAN_VERSION}\n",
      f"--version: stdout {buf.getvalue()!r}")
try:
    p.parse_args([])
    code = None
except SystemExit as e:
    code = e.code
check(code == 2, f"без подкоманды по-прежнему код {code!r}")

# ── 2. packaging (зависимость pytest): каноническая форма и предвыпуск ──
from packaging.version import Version  # noqa: E402
v = Version(PLAN_VERSION)
check(str(v) == PLAN_VERSION, f"канонический вид {PLAN_VERSION} → {v}")
check(v.is_prerelease and v.is_devrelease, f"{PLAN_VERSION}: предвыпуск и dev")
check(not Version("1.0.0").is_prerelease, "1.0.0 — выпуск")
check(not Version("1.0.1.post1").is_prerelease, "1.0.1.post1 — выпуск")
# Проверка теста шага 1: каноническая форма PEP 440 И ровно три компоненты
# MAJOR.MINOR.PATCH. Каноничность одна не ловит «1.0»: по PEP 440 это
# каноническая запись (первая версия пробы ожидала обратного — ошибка пробы).
def rule_ok(text: str) -> bool:
    try:
        ver = Version(text)
    except Exception:
        return False
    return str(ver) == text and len(ver.release) == 3


check(str(Version("1.0")) == "1.0", "'1.0' по PEP 440 — каноническая форма")
for good in (PLAN_VERSION, "1.0.0", "1.2.3rc1", "2.0.0.post1"):
    check(rule_ok(good), f"{good!r} — проходит правило")
for bad in ("1.0", "1", "1.0.0.0", "v1.0.0", "1.0.0-dev0", "1.0.0dev", "01.0.0"):
    check(not rule_ok(bad), f"{bad!r} — отклоняется правилом")

# ── 3. Колесо копии пакета: номер из литерала ──
work = SOLVER / "build" / "feat037_probe"
if work.exists():
    shutil.rmtree(work)
src = work / "src"
shutil.copytree(SOLVER / "gpn_multiphase_solver", src / "gpn_multiphase_solver",
                ignore=shutil.ignore_patterns("__pycache__"))
shutil.copy2(SOLVER / "pyproject.toml", src / "pyproject.toml")
init_py = src / "gpn_multiphase_solver" / "__init__.py"
pyproject = src / "pyproject.toml"
if apply_plan:
    init_py.write_text(init_py.read_text(encoding="utf-8")
                       + f'\n__version__ = "{PLAN_VERSION}"\n', encoding="utf-8")
    text = pyproject.read_text(encoding="utf-8")
    text = text.replace('version = "0.1.0"\n', 'dynamic = ["version"]\n', 1)
    text = text.replace(
        "[tool.setuptools.packages.find]",
        '[tool.setuptools.dynamic]\nversion = {attr = "gpn_multiphase_solver.__version__"}\n\n'
        "[tool.setuptools.packages.find]", 1)
    pyproject.write_text(text, encoding="utf-8")
literal = re.search(r'^__version__ = "([^"]+)"', init_py.read_text(encoding="utf-8"), re.M)
literal = literal.group(1) if literal else None
print(f"Литерал в копии: {literal}")

wheels = work / "wheels"
r = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-q",
                    "-w", str(wheels), str(src)], capture_output=True, text=True)
check(r.returncode == 0, f"pip wheel: код {r.returncode}" + (f"\n{r.stderr[-1500:]}" if r.returncode else ""))
whl = sorted(wheels.glob("*.whl")) if wheels.exists() else []
if whl:
    print(f"Колесо: {whl[0].name}")
    with zipfile.ZipFile(whl[0]) as z:
        meta = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
        # METADATA — с переводами строк CRLF: без strip в номер попадает \r
        version = re.search(r"^Version: (.+)$", z.read(meta).decode("utf-8"), re.M).group(1).strip()
    print(f"METADATA Version: {version}")
    if literal is not None:
        check(version == literal, f"номер колеса {version} = литерал {literal}")
        check(f"-{literal}-" in whl[0].name, "номер в имени колеса")
    else:
        check(version == "0.1.0", f"без правок плана — статический номер 0.1.0: {version}")

print(f"\nИтог: {'все проверки пройдены' if not failed else f'ошибок {failed}'}")
sys.exit(1 if failed else 0)
