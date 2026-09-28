"""Аудит FEAT-021: откуда GOR > R_s^0 в примере 12 — баланс компонентов.

Утверждение плана (§2.3): газовый фактор выше R_s^0, потому что расширяющаяся
воронка срабатывает запас газа в пласте. Проверка: за интервал [t1, t2]

    добыча = приток через контур + убыль запаса,
    Q_g = I_g + (M_g(t1) - M_g(t2)),   Q_o = I_o + (M_o(t1) - M_o(t2)),

где M_o = Σ V φ S_o / B_o, M_g = Σ V φ (S_o R_s / B_o + S_g / B_g), м³ст;
потоки G на гранях — м³ст/с, знак «+» от скважины (приток через контур G_N < 0).
Первый час пропускается: он раздроблен на 128 подшагов, а в истории сохранён
поток только последнего.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-021\\probes\\gor_component_balance.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

# Конфиг примера 12 = заготовка 11 с R_ext = 200 м и p0 = 15.5 МПа, 15 сут.
# История здесь ПОЧАСОВАЯ (360 × 3600 с), а не суточная, как в примере: при
# dt_integration = 3600 с подшаги те же, счёт побитово тот же, но сумма
# «поток на конце интервала × dt» точна только при записи на каждом подшаге.
import copy  # noqa: E402

cfg = load_config(SOLVER / "examples" / "11_degassing_at_boundary" / "config.json")
cfg.geometry.R_ext = 200.0
cfg.initial_conditions.p0 = 15.5e6
cfg.time.history = [copy.deepcopy(cfg.time.history[0]) for _ in range(360)]
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
h = sim.run(init)
pvt, V, phi = sim._energy._pvt, sim._grid.volumes, cfg.rock.porosity
Rs0 = cfg.initial_conditions.Rs0


def stock(st):
    So = 1.0 - st.Sg
    Bo, Bg = pvt.Bo(st.p, st.Rs), pvt.Bg(st.p)
    return (float(np.sum(V * phi * So / Bo)),
            float(np.sum(V * phi * (So * st.Rs / Bo + st.Sg / Bg))))


t = np.array(h.times)
n1, n2 = 1, len(t) - 1
Mo1, Mg1 = stock(h.states[n1])
Mo2, Mg2 = stock(h.states[n2])
Qo = Qg = Io = Ig = 0.0
for n in range(n1 + 1, n2 + 1):
    dt = t[n] - t[n - 1]
    hr = h.hydro_results[n]
    Qo += -hr.G_o[0] * dt          # добыча: G_0 < 0 (к скважине)
    Qg += -hr.G_g[0] * dt
    Io += -hr.G_o[-1] * dt         # приток через контур: G_N < 0
    Ig += -hr.G_g[-1] * dt

print(f"интервал {t[n1]/3600:.0f}–{t[n2]/3600:.0f} ч")
print(f"нефть: добыча {Qo:.2f}, приток {Io:.2f}, убыль запаса {Mo1-Mo2:.2f}, "
      f"невязка {(Qo - Io - (Mo1-Mo2))/Qo:.2e}")
print(f"газ:   добыча {Qg:.2f}, приток {Ig:.2f} (= R_s0·I_o = {Rs0*Io:.2f}), "
      f"убыль запаса {Mg1-Mg2:.2f}, невязка {(Qg - Ig - (Mg1-Mg2))/Qg:.2e}")
print(f"GOR накопленный = {Qg/Qo:.2f}; вклад притока {Ig/Qo:.2f}, вклад убыли запаса газа "
      f"{(Mg1-Mg2)/Qo:.2f}; доля нефти из убыли запаса {(Mo1-Mo2)/Qo:.3f}")
