"""DEBT-055, проба планирования: пол округления меры условия ячейки — прямой замер.

Мера условия ячейки (BUG-022): m = max_c max_i |F_c,i| * dt / V_p,i, F = residual() (м³ст/с,
газ поделён на gas_residual_scale), V_p — поровый объём state_old.

Гипотезы о пределе, ниже которого m не опускается:
  V — оценка реестра: eps_маш * V_max / V_min ~ eps_маш * (R_ext/r_w)^2, от dt не зависит;
  Q — квантование состояния: давление ячейки представимо лишь с шагом ulp(p), и невязка
      ячейки не меньше ~ sum_j |dF_i/dz_j| * ulp(z_j); вес dt/V_p,i -> предел растёт как dt,
      как T_грани/V_p,1 ~ N^2/ln^2(R_ext/r_w) и лишь логарифмически зависит от R_ext.

Что считается для сошедшегося шага z* (advance при пороге конфига):
  m*     — мера в z*;
  m_newt — наименьшая мера за 8 итераций чистого Ньютона из z* (без линейного поиска):
           достижимый предел итерации;
  m_lat  — разброс меры при случайном сдвиге каждой компоненты z* на -1/0/+1 ulp
           (20 выборок): шум решётки представимых чисел, без якобиана;
  m_J    — оценка Q по якобиану: max_i (|J| @ ulp(z*))_i * dt / V_p,i;
  est_V  — оценка V.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-055\\probes\\floor_probe.py
"""
import copy
import sys
import time
from pathlib import Path

import numpy as np

# Код — из каталога запуска (основной или worktree), не из установки в общий venv
SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
HERE = Path(__file__).resolve().parent

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config      # noqa: E402
from radial_blackoil.state import BlackOilState               # noqa: E402
import radial_blackoil                                        # noqa: E402

EPS = np.finfo(float).eps
BAR = 1e5
OUT = open(HERE / "floor_probe.out.txt", "w", encoding="utf-8")


def out(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.write(line + "\n")
    OUT.flush()


out(f"SOLVER = {SOLVER}")
out(f"radial_blackoil: {Path(radial_blackoil.__file__).parent}")


def measure_rows(model, f, w):
    """Мера по строкам: (нефть, газ) — массивы |F|*dt/V_p по ячейкам."""
    n = model.grid.n
    return np.abs(f[:n]) * w, np.abs(f[n:]) * w


def measure(model, f, w):
    a, b = measure_rows(model, f, w)
    return max(float(a.max()), float(b.max()))


def argmax_cell(model, f, w):
    a, b = measure_rows(model, f, w)
    return ("o", int(np.argmax(a))) if a.max() >= b.max() else ("g", int(np.argmax(b)))


def floors(model, state_old, new, dt):
    """m*, m_newt, m_lat, m_J и ячейки, где они достигаются."""
    mask = new.gas_active.copy()
    z = model.pack(new, mask)
    w = dt / model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, state_old.pressure_bar)
    f = model.residual(z, state_old, dt, mask)
    m_star = measure(model, f, w)
    cell_star = argmax_cell(model, f, w)
    # Оценка Q по якобиану
    J, _ = model.finite_difference_jacobian(z, state_old, dt, mask)
    ulp = np.spacing(np.abs(z))
    noise = abs(J) @ ulp
    m_J = measure(model, noise, w)
    cell_J = argmax_cell(model, noise, w)
    # Шум решётки: сдвиг компонент на -1/0/+1 ulp
    rng = np.random.default_rng(0)
    m_lat = 0.0
    for _ in range(20):
        zp = z + rng.integers(-1, 2, z.size) * ulp
        m_lat = max(m_lat, measure(model, model.residual(zp, state_old, dt, mask) - f, w))
    # Чистый Ньютон из z*
    m_newt = m_star
    zz = z.copy()
    for _ in range(8):
        Jk, fk = model.finite_difference_jacobian(zz, state_old, dt, mask)
        try:
            zz = zz + model._linear_solve(Jk, -fk)
        except Exception:
            break
        fk = model.residual(zz, state_old, dt, mask)
        m_newt = min(m_newt, measure(model, fk, w))
    return m_star, cell_star, m_newt, m_lat, m_J, cell_J


def prepare(rext, N, days):
    """Пример 17 с R_ext, N; добыча days сут — состояние с газовой зоной у забоя."""
    cfg = load_config(SOLVER / "examples" / "17_shut_in_strong_cooling" / "config.json")
    cfg.output.log_level = "ERROR"
    cfg.geometry.R_ext = float(rext)
    cfg.grid.N = int(N)
    h0 = copy.deepcopy(cfg.time.history[0])
    h0.duration = days * 86400.0
    cfg.time.history = [h0]
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    s = hist.states[-1]
    model = sim._hydro._model
    st = BlackOilState(pressure_bar=s.p / BAR, rs_sm3_sm3=s.Rs.copy(), sg=s.Sg.copy(),
                       gas_active=(s.regime == 1))
    pv = model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, st.pressure_bar)
    return model, st, float(pv.max() / pv.min()), cfg


def scenario(rext, N, dts, days=2.0):
    t0 = time.perf_counter()
    model, st, vratio, cfg = prepare(rext, N, days)
    out(f"\n=== R_ext = {rext} м, N = {N}, состояние после {days} сут добычи; "
        f"V_max/V_min = {vratio:.3e}, est_V = {EPS * vratio:.2e}; "
        f"газовых ячеек {int(st.gas_active.sum())}, p(r_w) = {st.pressure_bar[0]:.2f} бар "
        f"(подготовка {time.perf_counter() - t0:.0f} с) ===")
    for control in ("добыча", "останов"):
        if control == "добыча":
            model.set_bhp_control(cfg.time.history[0].p_wf / BAR)
        else:
            model.set_oil_rate_control(0.0, 101325.0 / BAR)
        out(f"  {control}:")
        out("    dt, с      сошлось  m*        m_newt    m_lat     m_J       ячейка m_J  ячейка m*")
        for dt in dts:
            new, rep = model.advance(st, dt)
            if not rep.converged:
                out(f"    {dt:<10g} нет      мера {rep.cell_measure}")
                continue
            m_star, c_star, m_newt, m_lat, m_J, c_J = floors(model, st, new, dt)
            out(f"    {dt:<10g} да       {m_star:.2e}  {m_newt:.2e}  {m_lat:.2e}  {m_J:.2e}  "
                f"{c_J[0]}{c_J[1]:<10d} {c_star[0]}{c_star[1]}")


DTS = [225.0, 900.0, 3600.0, 14400.0, 86400.0]
# Зависимость от dt и от сетки: N при R_ext = 200; R_ext при N = 200
scenario(200, 200, DTS)
scenario(200, 100, [3600.0])
scenario(200, 400, [3600.0])
scenario(1000, 200, [3600.0])
scenario(2000, 200, [3600.0])
