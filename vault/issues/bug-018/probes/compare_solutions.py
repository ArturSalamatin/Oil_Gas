"""BUG-018: сверка решений, сохранённых cap_initial_sg.py (save=имя).

Первое имя — эталон; для остальных печатает max|разности| по всем записям
и ячейкам: p (Па), S_g, R_s, T (К), q_o, q_g (отн.).

Запуск: python compare_solutions.py ref other1 other2 ...
"""

import sys
from pathlib import Path

import numpy as np

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ref_name, *others = sys.argv[1:]
ref = np.load(HERE / f"{ref_name}.npz")
for nm in others:
    x = np.load(HERE / f"{nm}.npz")
    dq = lambda k: np.max(np.abs(x[k][1:] - ref[k][1:]) / np.abs(ref[k][1:]))  # noqa: E731
    print(f"{nm} против {ref_name}: max|Δp| = {np.max(np.abs(x['p'] - ref['p'])):.3e} Па, "
          f"max|ΔS_g| = {np.max(np.abs(x['Sg'] - ref['Sg'])):.3e}, "
          f"max|ΔR_s| = {np.max(np.abs(x['Rs'] - ref['Rs'])):.3e}, "
          f"max|ΔT| = {np.max(np.abs(x['T'] - ref['T'])):.3e} К, "
          f"отн. Δq_o = {dq('q_o'):.3e}, отн. Δq_g = {dq('q_g'):.3e}")
