"""FEAT-029: профили T, S_g, p, R_s по радиусу из npz пробы shutin_scenario.py.

Печать на выбранных записях: значения в характерных радиусах, радиус зоны
охлаждения (где T0 - T > 10 % перепада у забоя), внешний край газовой зоны.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-029\\probes\\profiles_dump.py shutin_20_15p15s.npz 380 15 16 27 39 40 43 53
"""

import sys
from pathlib import Path

import numpy as np

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
d = np.load(HERE / sys.argv[1])
T0 = float(sys.argv[2])
recs = [int(x) for x in sys.argv[3:]]
r = d["r"]
radii = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 199.0]
idx = [int(np.argmin(np.abs(r - x))) for x in radii]
print("радиусы центров:", " ".join(f"{r[i]:.2f}" for i in idx))
for n in recs:
    t = d["t"][n] / 86400.0
    T, Sg, p, Rs = d["T"][n], d["Sg"][n], d["p"][n], d["Rs"][n]
    dT = T - T0
    cold = np.nonzero(dT < 0.1 * dT[0])[0] if dT[0] < 0 else []
    r_cold = r[cold[-1]] if len(cold) else 0.0
    gas = np.nonzero(Sg > 0)[0]
    gz = f"{r[gas[0]]:.2f}…{r[gas[-1]]:.1f} м ({len(gas)})" if len(gas) else "нет"
    print(f"--- запись {n}, t = {t:.3f} сут; зона охлаждения (ΔT < 0.1 ΔT_w) до r = {r_cold:.2f} м; "
          f"газ: {gz}; min T = {T.min():.3f} при r = {r[np.argmin(T)]:.2f}")
    print("  ΔT, К : " + " ".join(f"{dT[i]:>8.3f}" for i in idx))
    print("  S_g   : " + " ".join(f"{Sg[i]:>8.4f}" for i in idx))
    print("  p, МПа: " + " ".join(f"{p[i]/1e6:>8.3f}" for i in idx))
    print("  R_s   : " + " ".join(f"{Rs[i]:>8.2f}" for i in idx))
