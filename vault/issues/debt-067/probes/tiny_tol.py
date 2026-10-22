"""DEBT-067, проба планирования: почему порог 1e-30 недостижим и с полом |J|·ulp(z).

Ступень 4 на останове rs300 (168.75 с) при пороге 1e-30 и полу (вариант a) отказывает по
лимиту 40 итераций (unit_numbers.out.txt, п. 4). В последней точке — строки, где
|F_r| > (|J|·ulp(z))_r: какие (ячейка, компонент), во сколько раз, и сравнение с
округлением накопления eps*M_r/dt (M_r — запас строки на новом слое; разность запасов
в невязке, eq:newton_abs_tol), которого |J|·ulp(z) не содержит.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-067\\probes\\tiny_tol.py
Выход — tiny_tol.out.txt рядом со скриптом.
"""
import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import variants  # noqa: E402,F401  (пути SOLVER и прототипа)

from gpn_multiphase_solver.factory import SimulatorFactory               # noqa: E402
from gpn_multiphase_solver.io.config import load_config                  # noqa: E402
from radial_blackoil.state import BlackOilState                          # noqa: E402
from tests.test_prototype_cell_tolerance import ATM_BAR, BAR, DT_STAGE4, RS300  # noqa: E402

OUT = open(HERE / "tiny_tol.out.txt", "w", encoding="utf-8")
EPS = float(np.finfo(float).eps)


def out(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


cfg = load_config(RS300)
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
s = sim.run(init).states[-1]
model = sim._hydro._model
model.set_oil_rate_control(0.0, ATM_BAR)
ps = BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(),
                   sg=s.Sg.copy(), gas_active=(s.regime == 1))
model.cell_tol = 1e-30
new, rep = model._newton_switching(ps, DT_STAGE4)
out(f"Ступень 4, {DT_STAGE4} с, порог 1e-30 (без пола): converged={rep.converged}, "
    f"exit={rep.exit_reason}, мера {rep.cell_measure:.3e}, предел {rep.cell_floor:.3e}")

n = model.grid.n
mask = new.gas_active.copy()
z = model.pack(new, mask)
J, f = model.finite_difference_jacobian(z, ps, DT_STAGE4, mask)
noise = abs(J) @ np.spacing(np.abs(z))
w = model._cell_weights(ps, DT_STAGE4)
ww = np.concatenate([w, w])
# Запасы нового слоя (м³ст): строки нефти и газа (газ / s_g, как в residual)
oi, gi = model.component_inventories(new)
M = np.concatenate([np.abs(oi), np.abs(gi) / model.gas_residual_scale])
store = EPS * M / DT_STAGE4
ratio = np.abs(f) / noise
bad = ratio > 1.0
out(f"строк {2 * n}, с |F| > (|J|·ulp)_r: {int(bad.sum())} "
    f"(нефть {int(bad[:n].sum())}, газ {int(bad[n:].sum())}); max отношение {ratio.max():.2f}")
order = np.argsort(-ratio)[:12]
out("  строка   |F|, м³ст/с   (|J|ulp)_r    eps*M/dt     |F|/(|J|ulp)  |F|/(eps*M/dt)  мера строки  предел строки")
for r in order:
    tag = f"{'o' if r < n else 'g'}{r % n}"
    out(f"  {tag:<7}  {abs(f[r]):.3e}     {noise[r]:.3e}    {store[r]:.3e}    {ratio[r]:8.2f}      "
        f"{abs(f[r]) / store[r]:8.3f}       {abs(f[r]) * ww[r]:.2e}     {noise[r] * ww[r]:.2e}")
both = noise + store
out(f"с полом (|J|ulp)_r + eps*M_r/dt: строк выше {int((np.abs(f) > both).sum())}, "
    f"max |F|/пол {float(np.max(np.abs(f) / both)):.2f}")
out(f"мера строк выше пола |J|ulp: max {float(np.max((np.abs(f) * ww)[bad])):.2e}; "
    f"eps*M/dt в единицах меры: max {float(np.max(store * ww)):.2e}")
