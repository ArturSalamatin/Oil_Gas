"""BUG-022: величины тестов примера 17 (tests/test_examples.py, TestShutInStrongCooling) на историях вариантов.

Копия vault/issues/debt-048/probes/check17.py, дополненная утверждениями о газе и кольце.
Истории — hist_17_shut_in_strong_cooling_<вариант>.npz, их пишет cell_tol.py examples.
Проверяются утверждения, которые читают p, T, S_g, R_s (энергобаланс, дебит и графики — нет):
  :2678 T(r_w) записи 15 = 365.0166 ± 2e-3 К        :2682 S_g(r_w) записи 15 = 0.4490 ± 1e-3
  :2683 ячеек с газом на записи 15 — 165              :2712 p(r_w) не убывает с записи 15
  :2713 p(r_w) записи 16 = 24.5554 МПа ± 1e-4 отн.    :2716 первая запись выше p_b — 27 ± 1
  :2740 число ячеек с газом не растёт с записи 15     :2743 ячеек с газом на конце — 51
  :2749 R_s(r_w) последней = 79.51 ± 0.01             :2767-2769 T(r_w) записей 16, 39, 53 ± 2e-3 К
  :2766 T(r_w) строго растёт с записи 15              :2785 max(T - T0) на конце = 0.2216 ± 2e-3 К
Дополнительно (не тест): наименьшее изменение R_s(r_w) по записям 16..53 и число убываний.
Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\check17.py 0 pv1e-8
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
T0 = 380.0          # начальная температура примера 17, К

lines = []
for v in sys.argv[1:]:
    h = np.load(HERE / f"hist_17_shut_in_strong_cooling_{v}.npz")
    pw, T, Rs, Sg = h["p"][:, 0], h["T"][:, 0], h["Rs"][:, 0], h["Sg"]
    dp = np.diff(pw[END:])
    above = [n for n in range(END, len(pw)) if pw[n] > PB]
    ngas = np.count_nonzero(Sg > 0.0, axis=1)
    drs = np.diff(Rs[16:])
    checks = [
        ("T15", T[END], abs(T[END] - 365.0166) <= 2e-3),
        ("Sg15", Sg[END, 0], abs(Sg[END, 0] - 0.4490) <= 1e-3),
        ("газ15", ngas[END], ngas[END] == 165),
        ("min Δp Па", dp.min(), bool(np.all(dp >= 0.0))),
        ("p16 МПа", pw[END + 1] / 1e6, abs(pw[END + 1] / 24.5554e6 - 1) <= 1e-4),
        ("выше p_b с", above[0], abs(above[0] - 27) <= 1),
        ("газ не растёт", int(np.diff(ngas[END:]).max()), bool(np.all(np.diff(ngas[END:]) <= 0))),
        ("газ кон.", ngas[-1], ngas[-1] == 51),
        ("Rs(r_w) кон.", Rs[-1], abs(Rs[-1] - 79.51) <= 0.01),
        ("min ΔT К", np.diff(T[END:]).min(), bool(np.all(np.diff(T[END:]) > 0.0))),
        ("T16", T[END + 1], abs(T[END + 1] - 368.7791) <= 2e-3),
        ("T39", T[39], abs(T[39] - 373.6456) <= 2e-3),
        ("T кон.", T[-1], abs(T[-1] - 377.3093) <= 2e-3),
        ("max ΔT кольца", (h["T"][-1] - T0).max(), abs((h["T"][-1] - T0).max() - 0.2216) <= 2e-3),
    ]
    lines.append(f"{v:>8}: " + "; ".join(f"{n} = {x:.6g} {'✓' if ok else '✗'}" for n, x, ok in checks)
                 + f" | min dR_s(r_w) 16..53 = {drs.min():+.2e}, убываний {int(np.sum(drs < 0))}")

text = "\n".join(lines)
print(text)
(HERE / "check17.out.txt").write_text(text + "\n", encoding="utf-8")
