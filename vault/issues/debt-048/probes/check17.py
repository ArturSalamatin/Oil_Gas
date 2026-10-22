"""DEBT-048: величины тестов примера 17 (tests/test_examples.py, TestShutInStrongCooling) на историях вариантов.

Истории — hist_17_shut_in_strong_cooling_<вариант>.npz, их пишет stage_memory.py examples.
Проверяются утверждения, которые читают p, T, S_g, R_s (энергобаланс и графики — нет):
  :2678 T(r_w) записи 15 = 365.0166 ± 2e-3 К        :2713 p(r_w) записи 16 = 24.5554 МПа ± 1e-4 отн.
  :2712 p(r_w) не убывает с записи 15                 :2716 первая запись выше p_b — 27 ± 1
  :2752 R_s(r_w) последней = 79.537 ± 1e-3 (после BUG-022; до него 79.51 ± 0.01)
  :2769 R_s(r_w) с записи 16 не убывает больше чем на 1e-4 (BUG-022)
  :2788-2790 T(r_w) записей 16, 39, 53 ± 2e-3 К (после BUG-024: 368.7791, 373.6369, 377.3078)
Номера строк — на d7528d4 (BUG-024 влит); тесты сверять по тексту, константы ниже — по ним.
Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-048\\probes\\check17.py 0 m2rs m2s
"""

import sys
from pathlib import Path

import numpy as np

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
END = 15            # запись конца добычи
PB = 30.2921e6      # p_b при R_s0 = 300, Па (docstring test_pressure_builds_up_past_pb)

lines = []
for v in sys.argv[1:]:
    h = np.load(HERE / f"hist_17_shut_in_strong_cooling_{v}.npz")
    pw, T, Rs = h["p"][:, 0], h["T"][:, 0], h["Rs"][:, 0]
    dp = np.diff(pw[END:])
    above = [n for n in range(END, len(pw)) if pw[n] > PB]
    checks = [
        ("T15", T[END], abs(T[END] - 365.0166) <= 2e-3),
        ("p16 МПа", pw[END + 1] / 1e6, abs(pw[END + 1] / 24.5554e6 - 1) <= 1e-4),
        ("min Δp Па", dp.min(), bool(np.all(dp >= 0.0))),
        ("выше p_b с", above[0], abs(above[0] - 27) <= 1),
        ("Rs(r_w) кон.", Rs[-1], abs(Rs[-1] - 79.537) <= 1e-3),
        ("min ΔRs(r_w)", np.diff(Rs[END + 1:]).min(), np.diff(Rs[END + 1:]).min() >= -1e-4),
        ("T16", T[END + 1], abs(T[END + 1] - 368.7791) <= 2e-3),
        ("T39", T[39], abs(T[39] - 373.6369) <= 2e-3),
        ("T кон.", T[-1], abs(T[-1] - 377.3078) <= 2e-3),
    ]
    lines.append(f"{v:>5}: " + "; ".join(f"{k} = {x:.6g} {'✓' if ok else '✗'}" for k, x, ok in checks))
out = "\n".join(lines)
print(out)
(HERE / "check17.out.txt").write_text(out + "\n", encoding="utf-8")
