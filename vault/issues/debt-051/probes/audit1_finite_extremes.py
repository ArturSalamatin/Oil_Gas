r"""DEBT-051, аудит 1: закрывает ли проверка конечности молча неверные расчёты, или их дают и конечные абсурдные значения.

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-051\probes\audit1_finite_extremes.py
Те же случаи, что разделы B, C пробы red_state.py, но с большими конечными
значениями вместо inf. Проверка конечности DEBT-051 их пропустит — вопрос, что
делает расчёт. Код берётся из текущего каталога (red_state.SOLVER = Path.cwd()).
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import red_state  # noqa: E402

CASES = {
    "эталон (без подмены)": ("pressure", None),
    "numerics.skin = 1e6": ("pressure", ("numerics", "skin", 1e6)),
    "numerics.skin = 1e300": ("pressure", ("numerics", "skin", 1e300)),
    "numerics.skin = -1e300": ("pressure", ("numerics", "skin", -1e300)),
    "history.p_wf = 1e12": ("pressure", ("history", "p_wf", 1e12)),
    "эталон rate_hi (без подмены)": ("rate_hi", None),
    "history.min_bhp = 1e300, rate_hi": ("rate_hi", ("history", "min_bhp", 1e300)),
    "history.q_oil = 1e300, rate_hi": ("rate_hi", ("history", "q_oil", 1e300)),
}

if __name__ == "__main__":
    red_state.WORK = Path(__file__).resolve().parent / "audit1_tmp"
    if red_state.WORK.exists():
        shutil.rmtree(red_state.WORK)
    red_state.WORK.mkdir()
    try:
        red_state.run_cases("X", "Аудит 1: большие конечные значения", CASES)
    finally:
        shutil.rmtree(red_state.WORK)
