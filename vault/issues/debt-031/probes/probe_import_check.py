"""Проба аудита DEBT-031: тест импорта из плана и проверка глобальных имён run_series.

Запуск (из numerical_solver/ основного каталога или worktree):
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\debt-031\\probes\\probe_import_check.py -q -p no:cacheprovider

Проверяет:
  1. тело теста плана (шаг 2) зелёное на текущем коде;
  2. файл «После» шага 3 (берётся из плана) загружается, и у run_series
     все глобальные имена определены;
  3. проверка через dis ловит потерянный `from copy import deepcopy`
     (имя нужно только при вызове — сам импорт модуля его не ловит);
  4. отсутствие run_series ловится.
"""

import builtins
import dis
import re
import runpy
import sys
from pathlib import Path

# Код берётся из текущего каталога: запуск из worktree проверяет worktree.
SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), f"запускать из numerical_solver/: {SOLVER}"
EXAMPLES_DIR = SOLVER / "examples"
PLAN = Path(__file__).resolve().parents[3] / "plans" / "debt-031 convergence-dead-code.md"
print(f"Код: {EXAMPLES_DIR}")

SCRIPTS = ("convergence.py",
           "energy_balance_convergence.py",
           "04a_high_gas_saturation/grid_convergence.py")


def _missing_globals(fn):
    """Глобальные имена тела fn, не определённые ни в модуле, ни во встроенных."""
    return sorted(
        ins.argval for ins in dis.get_instructions(fn)
        if ins.opname == "LOAD_GLOBAL"
        and ins.argval not in fn.__globals__
        and not hasattr(builtins, ins.argval))


def _after_code() -> str:
    """Блок «После — весь файл» шага 3 из плана."""
    text = PLAN.read_text(encoding="utf-8")
    m = re.search(r"После — \*\*весь файл\*\*:\n```python\n(.*?)\n```", text, re.S)
    assert m, "в плане не найден блок «После — весь файл»"
    return m.group(1) + "\n"


def _exec_as_convergence(source: str) -> dict:
    """Выполнить исходник как examples/convergence.py (тот же __file__)."""
    ns = {"__name__": "__import_check__",
          "__file__": str(EXAMPLES_DIR / "convergence.py")}
    exec(compile(source, str(EXAMPLES_DIR / "convergence.py"), "exec"), ns)
    return ns


def test_plan_test_body_on_current_code(monkeypatch):
    """Тело теста плана (с проверкой dis) зелёное на текущем коде."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    for script in SCRIPTS:
        namespace = runpy.run_path(str(EXAMPLES_DIR / script),
                                   run_name="__import_check__")
        run_series = namespace.get("run_series")
        assert callable(run_series), script
        print(script, "LOAD_GLOBAL:",
              sorted({i.argval for i in dis.get_instructions(run_series)
                      if i.opname == "LOAD_GLOBAL"}))
        assert _missing_globals(run_series) == [], script


def test_after_file_loads_and_resolves():
    """Файл «После» шага 3 выполняется, run_series без неопределённых имён."""
    src = _after_code()
    ns = _exec_as_convergence(src)
    assert callable(ns["run_series"])
    assert _missing_globals(ns["run_series"]) == []
    for name in ("np", "plt", "matplotlib", "save_figure", "export_emf",
                 "fit_order", "pairwise_orders", "plot_convergence",
                 "report_series"):
        assert name not in ns, name
    print("строк в файле «После»:", src.count("\n"))


def test_dis_check_catches_lost_deepcopy():
    """Без `from copy import deepcopy` импорт проходит, а dis — ловит."""
    src = _after_code().replace("from copy import deepcopy\n", "")
    ns = _exec_as_convergence(src)
    assert callable(ns["run_series"])          # импорт этого не видит
    assert _missing_globals(ns["run_series"]) == ["deepcopy"]


def test_missing_run_series_caught():
    """Переименованная run_series — в пространстве имён её нет."""
    src = _after_code().replace("def run_series(", "def run_series_x(")
    ns = _exec_as_convergence(src)
    assert not callable(ns.get("run_series"))
