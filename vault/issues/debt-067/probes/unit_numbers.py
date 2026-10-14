"""DEBT-067, проба планирования: числа тестов плана — эмуляция варианта a (Patch из variants.py).

1. BUG-018 при N = 350, шаг 86400 с: _advance_phases и advance с полом — сходятся? мера,
   предел, итерации, где сработал пол.
2. Те же сутки при dt/2: предел вдвое меньше (6.42e-8 -> 3.21e-8) — пол ещё принимает?
3. Nabor_1b при N = 12 и 50 (тесты BUG-022): пол ничего не меняет (предел ниже порога).
4. Недостижимый порог 1e-30 с полом: ступень 4 (останов rs300, 168.75 с) и сутки BUG-018 —
   сходятся ли (округление накопления ~eps*M/dt пол |J|·ulp(z) не учитывает).
5. Первый Ньютон суток BUG-018 (_newton_fixed_active_set из начального состояния) с полом:
   итерации, мера, предел — числа теста приёма по полу.
6. Nabor_1b N = 12, Ньютон без условия (2 итерации, мера 2.33e-8): предел в этой точке —
   почему пол её не принимает.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-067\\probes\\unit_numbers.py
Выход — unit_numbers.out.txt рядом со скриптом.
"""
import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import variants  # noqa: E402  (Patch; пути SOLVER и прототипа)

from gpn_multiphase_solver.factory import SimulatorFactory               # noqa: E402
from gpn_multiphase_solver.io.config import load_config                  # noqa: E402
from radial_blackoil.state import BlackOilState                          # noqa: E402
from tests.test_prototype_cell_tolerance import (                        # noqa: E402
    ATM_BAR, BAR, CELL_TOL, DT, DT_STAGE4, RS300, _build, _measure, _newton)
from tests.test_prototype_failure_diagnostics import _bug018_model       # noqa: E402

OUT = open(HERE / "unit_numbers.out.txt", "w", encoding="utf-8")


def out(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


def floor_of(model, z, s_old, dt, mask):
    """Предел eq:newton_cell_floor в точке z — якобиан в z (как _cell_floor)."""
    J, _ = model.finite_difference_jacobian(z, s_old, dt, mask)
    return model._cell_floor(J, z, model._cell_weights(s_old, dt))


def rep_line(rep):
    return (f"converged={rep.converged}, iterations={rep.iterations}, active_set={rep.active_set_iterations}, "
            f"exit={rep.exit_reason!r}, residual={rep.residual_inf:.3e} (tol {rep.residual_tol}), "
            f"measure={rep.cell_measure!r}, cell_floor={rep.cell_floor!r}, fallback={rep.fallback}, "
            f"globalized={rep.globalized}, phase_switching={rep.phase_switching}")


out(f"SOLVER = {SOLVER}, KAPPA = {variants.KAPPA}")

# ── 1, 2. Сутки BUG-018 при N = 350 ──
for label, frac in (("сутки", 1.0), ("полсуток", 0.5)):
    model, ps, dt = _bug018_model()
    dt = dt * frac
    p = variants.Patch(model, "a")
    new, rep = model._advance_phases(ps, dt)
    out(f"\n1. BUG-018 N = 350, {label} ({dt:g} с), _advance_phases: {rep_line(rep)}")
    out(f"   приёмов по полу {len(p.events)}: " + "; ".join(
        f"мера {e[2]:.4e}, предел {e[3]:.4e}, kappa {e[5]:.3f}, строки {e[7]}" for e in p.events))
    if rep.converged:
        z = model.pack(new, new.gas_active)
        out(f"   мера решения {_measure(model, ps, new, dt):.4e}, предел в решении "
            f"{floor_of(model, z, ps, dt, new.gas_active):.4e}; S_g(r_w) = {new.sg[0]:.6f}, "
            f"p(r_w) = {new.pressure_bar[0]:.6f} бар")
    model, ps, dt = _bug018_model()
    dt = dt * frac
    p = variants.Patch(model, "a")
    new, rep = model.advance(ps, dt)
    out(f"   advance: {rep_line(rep)}; приёмов по полу {len(p.events)}")

# ── 3. Nabor_1b, тесты BUG-022 ──
for n in (12, 50):
    model, state = _build(n, cell_tol=CELL_TOL)
    p = variants.Patch(model, "a")
    z, rep = _newton(model, state)
    out(f"\n3. Nabor_1b N = {n}: {rep_line(rep)}; мера "
        f"{_measure(model, state, model.unpack(z, state.gas_active), DT):.3e}; "
        f"приёмов по полу {len(p.events)}, пол не помог {p.rejects}")
    model, state = _build(n, cell_tol=CELL_TOL)
    p = variants.Patch(model, "a")
    new, rep = model.advance(state, DT)
    out(f"   advance: {rep_line(rep)}; мера {_measure(model, state, new, DT):.3e}; "
        f"приёмов по полу {len(p.events)}")

# ── 4. Порог 1e-30 с полом ──
cfg = load_config(RS300)
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
s = sim.run(init).states[-1]
model = sim._hydro._model
model.set_oil_rate_control(0.0, ATM_BAR)
ps = BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(),
                   sg=s.Sg.copy(), gas_active=(s.regime == 1))
p = variants.Patch(model, "a")
model.cell_tol = 1e-30
new, rep = model._newton_switching(ps, DT_STAGE4)
out(f"\n4. Ступень 4, останов rs300, {DT_STAGE4} с, порог 1e-30: {rep_line(rep)}; "
    f"приёмов по полу {len(p.events)}, пол не помог {p.rejects}")
model.cell_tol = CELL_TOL
new, rep = model._newton_switching(ps, DT_STAGE4)
out(f"   порог 1e-8: {rep_line(rep)}")

model, ps, dt = _bug018_model()
p = variants.Patch(model, "a")
model.cell_tol = 1e-30
new, rep = model._advance_phases(ps, dt)
out(f"\n4. BUG-018 N = 350, сутки, порог 1e-30: {rep_line(rep)}; приёмов по полу {len(p.events)}, "
    f"пол не помог {p.rejects}")

# ── 5. Первый Ньютон суток BUG-018 ──
for variant in ("base", "a"):
    model, ps, dt = _bug018_model()
    p = variants.Patch(model, variant)
    z, rep = model._newton_fixed_active_set(model.pack(ps, ps.gas_active), ps, dt, ps.gas_active)
    out(f"\n5. BUG-018 первый Ньютон суток, {variant}: {rep_line(rep)}")
    for e in p.events:
        out(f"   приём по полу: мера {e[2]!r}, предел(J) {e[3]!r}, предел(Jz) {e[4]!r}, kappa {e[5]:.4f}, строки {e[7]}")
    out(f"   предел в возвращённой точке (якобиан в ней): "
        f"{floor_of(model, z, ps, dt, ps.gas_active)!r}")

# ── 6. Nabor_1b N = 12: недорешённая точка BUG-022 ──
base, state = _build(12)
z2, r2 = _newton(base, state)
model, state = _build(12, cell_tol=CELL_TOL)
w = model._cell_weights(state, DT)
J, f = model.finite_difference_jacobian(z2, state, DT, state.gas_active)
noise = abs(J) @ np.spacing(np.abs(z2))
ww = np.concatenate([w, w])
bad = np.abs(f) * ww > CELL_TOL
out(f"\n6. Nabor_1b N = 12 после {r2.iterations} итераций без условия: мера "
    f"{float(np.max(np.abs(f) * ww)):.3e}, предел {model._cell_floor(J, z2, w):.3e}; строк выше порога "
    f"{int(bad.sum())}, max |F_r|/(|J|ulp)_r по ним {float(np.max(np.abs(f)[bad] / noise[bad])):.3e}")
