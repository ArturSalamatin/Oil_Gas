"""DEBT-023: числа для плана — примеры 03–09 при λ = 0 (конфиг) и λ = 1.5 / 0.14 / 0.04.

Замеряется:
  A. по каждому примеру, обе λ: T(r_w) на финале и по суткам; max|ΔT| между
     вариантами по области и по всем записям; гидродинамика побитово (p, S_g,
     R_s, q_o, q_g); отставание от однофазной асимптотики (как report_asymptotics);
     баланс энергии (все члены, невязка); T_{N-1} − T_ext по записям.
     У 04a — T(r_w) на 5 мин, 1, 6, 12, 24, 72 ч (таблица «Переходный процесс»).
  B. суперпозиция 04/07/08/09 при обеих λ (test_thermal_superposition) и знаки
     вкладов (test_thermal_effects_sign).
  C. укороченный сценарий тестов баланса (как _run_balance в
     tests/test_energy_balance_examples.py: N = 25, 6 ч) — 03, 04, 04 при p_wf = 16 МПа.
  D. серия Δt = 3600 / 900 / 360 с (energy_balance_convergence.run_convergence)
     для 03, 04, 05 при λ ≠ 0.
  E. сетка: 03 при N = 25, 50, 100, 150, 200; 04 при N = 25, 50, 100, 150
     (max_retries 14, как 04/grid_convergence.py) — T(r_w), обе λ.
  F. рычаг 1 README 04: T(r_w) при табличной ОФП и трёх вариантах Кори, обе λ.
  G. test_dt_convergence на 07 при обеих λ: ошибки по DT_LIST и оба условия теста.

Запуск — из каталога numerical_solver (основного или worktree), через Bash:
    .venv/Scripts/python ../vault/issues/debt-023/probes/plan_numbers.py > ../vault/issues/debt-023/probes/plan_numbers.out.txt 2>&1
"""

import copy
import sys
import time
from pathlib import Path

import numpy as np

# Код берётся из текущего каталога: проба запускается из numerical_solver
# основного каталога или worktree, и первая строка вывода называет, чей код.
SOLVER = Path.cwd()
EXAMPLES = SOLVER / "examples"
for p in (SOLVER, EXAMPLES):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver.factory as _factory  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from energy_balance import compute_balance  # noqa: E402
from energy_balance_convergence import run_convergence  # noqa: E402
import temperature_asymptotics as ta  # noqa: E402

DAY = 86400.0
LAM_PHYS = (1.5, 0.14, 0.04)
# Оба варианта заданы явно: проба даёт одни и те же числа и до правки
# конфигов (λ = 0 в файлах), и после (λ = LAM_PHYS) — её можно запускать на
# любом шаге реализации. Что стоит в файле, печатает строка «λ в конфиге».
VARIANTS = (("λ=0", (0.0, 0.0, 0.0)), ("λ=phys", LAM_PHYS))
NAMES = ["03_standing_corey", "04_table_table", "04a_high_gas_saturation",
         "05_standing_table_rp", "06_table_corey_rp",
         "07_degassing_adiabatic_only", "08_degassing_jt",
         "09_degassing_latent_heat"]
SG_EPS = ta.SG_EPS


def load(name, lam):
    """Конфиг примера с заменой теплопроводностей; lam — (λ_s, λ_o, λ_g)."""
    cfg = load_config(EXAMPLES / name / "config.json")
    cfg.output.log_level = "ERROR"
    cfg.rock.lambda_solid, cfg.rock.lambda_oil, cfg.rock.lambda_gas = lam
    return cfg


def lam_in_file(name):
    """(λ_s, λ_o, λ_g), как они записаны в config.json примера."""
    r = load_config(EXAMPLES / name / "config.json").rock
    return r.lambda_solid, r.lambda_oil, r.lambda_gas


def run_cfg(cfg):
    sim, init = SimulatorFactory.from_config(cfg)
    t0 = time.perf_counter()
    h = sim.run(init)
    return sim, h, time.perf_counter() - t0


def rec_index(h, t):
    """Номер записи с моментом t (с) или None."""
    times = np.asarray(h.times)
    k = np.flatnonzero(np.isclose(times, t, rtol=0.0, atol=1e-6))
    return int(k[0]) if k.size else None


def part_a():
    print("\n=== A. Примеры 03–09: λ = 0 против λ = 1.5 / 0.14 / 0.04 ===")
    out = {}
    for name in NAMES:
        res = {}
        for tag, lam in VARIANTS:
            cfg = load(name, lam)
            sim, h, el = run_cfg(cfg)
            res[tag] = (cfg, sim, h, el)
        print(f"\n--- {name} ---")
        cfg0, sim0, h0, el0 = res["λ=0"]
        cfg1, sim1, h1, el1 = res["λ=phys"]
        T0 = cfg0.initial_conditions.T0
        print(f"λ в конфиге: {' / '.join(str(v) for v in lam_in_file(name))}; "
              f"N = {cfg0.grid.N}; записей {len(h0.states)}; "
              f"sim.run {el0:.1f} / {el1:.1f} с")

        # Гидродинамика: побитовое равенство по всем записям
        same = len(h0.states) == len(h1.states)
        for s0, s1 in zip(h0.states, h1.states):
            same &= (np.array_equal(s0.p, s1.p) and np.array_equal(s0.Sg, s1.Sg)
                     and np.array_equal(s0.Rs, s1.Rs))
        for w0, w1 in zip(h0.well_data, h1.well_data):
            same &= (w0.q_o_std == w1.q_o_std and w0.q_g_std == w1.q_g_std)
        print(f"гидродинамика (p, S_g, R_s, q_o, q_g) побитово равна: {same}")

        # Температура
        for tag, (cfg, sim, h, _) in res.items():
            Tw = [s.T[0] for s in h.states]
            days = []
            for d in (1, 2, 3):
                k = rec_index(h, d * DAY)
                days.append(f"{Tw[k]:.5f}" if k is not None else "—")
            print(f"[{tag}] T(r_w) финал {Tw[-1]:.6f} К (ΔT {Tw[-1] - T0:+.6f}); "
                  f"по суткам 1/2/3: {' / '.join(days)}")
        dT_all = np.array([s1.T - s0.T for s0, s1 in zip(h0.states, h1.states)])
        n_m, j_m = np.unravel_index(np.argmax(np.abs(dT_all)), dT_all.shape)
        r = sim0._grid.r_centers
        print(f"T(λ=phys) − T(λ=0): на забое финал {dT_all[-1, 0]:+.5f} К; "
              f"max|·| по области на финале {np.abs(dT_all[-1]).max():.5f} К "
              f"(r = {r[int(np.argmax(np.abs(dT_all[-1])))]:.3f} м); "
              f"по всем записям {np.abs(dT_all).max():.5f} К "
              f"(t = {h0.times[n_m] / 3600:.2f} ч, r = {r[j_m]:.3f} м)")

        if name == "04a_high_gas_saturation":
            for tag, (cfg, sim, h, _) in res.items():
                row = []
                for t in (300.0, 3600.0, 6 * 3600.0, 12 * 3600.0, DAY, 3 * DAY):
                    k = rec_index(h, t)
                    row.append(f"{h.states[k].T[0]:.5f}" if k is not None else "—")
                print(f"[{tag}] 04a T(r_w) на 5 мин / 1 / 6 / 12 / 24 / 72 ч: "
                      f"{' | '.join(row)}")

        # Однофазная асимптотика — как report_asymptotics
        for tag, (cfg, sim, h, _) in res.items():
            st = h.states[-1]
            mask1 = st.Sg <= SG_EPS
            T_as = ta.single_phase_asymptote(cfg, h)
            err = float(np.max(np.abs(st.T[mask1] - T_as[mask1]))) if mask1.any() else float("nan")
            print(f"[{tag}] асимптотика: max|T − T_as| = {err:.4f} К на "
                  f"{int(mask1.sum())} ячейках из {len(st.Sg)}")

        # Баланс энергии
        for tag, (cfg, sim, h, _) in res.items():
            bal = compute_balance(h, sim._grid, cfg)
            terms = " ".join(f"{k}={bal[k][-1]:+.6e}" for k in
                             ("delta_E", "cum_adiab", "cum_conv", "cum_jt",
                              "cum_deg", "cum_cond"))
            print(f"[{tag}] баланс: {terms}; residual {bal['residual'][-1]:+.4e} Дж; "
                  f"rel {bal['rel_residual'][-1]:.4e}; max rel по записям "
                  f"{bal['rel_residual'][1:].max():.2e}")
        for tag, (cfg, sim, h, _) in res.items():
            d = np.array([s.T[-1] - cfg.initial_conditions.T0 for s in h.states])
            print(f"[{tag}] T_(N-1) − T_ext по записям: min {d.min():+.2e} / "
                  f"max {d.max():+.2e} / конец {d[-1]:+.2e} К")
        out[name] = {tag: (v[0], v[2]) for tag, v in res.items()}
    return out


def part_b(out):
    print("\n=== B. Суперпозиция 04/07/08/09 и знаки вкладов ===")
    for tag, _ in VARIANTS:
        Tw = {n: out[n][tag][1].states[-1].T[0] for n in
              ("04_table_table", "07_degassing_adiabatic_only",
               "08_degassing_jt", "09_degassing_latent_heat")}
        T04, T07 = Tw["04_table_table"], Tw["07_degassing_adiabatic_only"]
        T08, T09 = Tw["08_degassing_jt"], Tw["09_degassing_latent_heat"]
        jt, lat, both = T08 - T07, T09 - T07, T04 - T07
        print(f"[{tag}] T04 {T04:.6f}, T07 {T07:.6f}, T08 {T08:.6f}, T09 {T09:.6f}; "
              f"JT {jt:+.5f}, L {lat:+.5f}, сумма {jt + lat:+.5f}, T04−T07 {both:+.5f}; "
              f"невязка {jt + lat - both:+.2e} К; T08 > T07: {T08 > T07}; T09 < T07: {T09 < T07}")
    for tag, _ in VARIANTS:
        T = {n: out[n][tag][1].states[-1].T[0] for n in NAMES}
        print(f"[{tag}] |T04 − T06| = {abs(T['04_table_table'] - T['06_table_corey_rp']):.3f} К; "
              f"|T05 − T04| = {abs(T['05_standing_table_rp'] - T['04_table_table']):.3f} К; "
              f"нагрев 04a {T['04a_high_gas_saturation'] - 350.0:+.3f}, "
              f"04 {T['04_table_table'] - 350.0:+.3f} К")


def part_c():
    print("\n=== C. Укороченный сценарий тестов баланса (N = 25, 6 ч) ===")
    for name, p_wf in (("03_standing_corey", None), ("04_table_table", None),
                       ("04_table_table", 16e6)):
        for tag, lam in VARIANTS:
            cfg = load(name, lam)
            cfg.grid.N = 25
            cfg.time.history = cfg.time.history[:1]
            cfg.time.history[0].dt = 21600.0
            if p_wf is not None:
                cfg.time.history[0].p_wf = p_wf
            sim, h, _ = run_cfg(cfg)
            assert abs(h.times[-1] - 21600.0) < 1e-6
            bal = compute_balance(h, sim._grid, cfg)
            print(f"{name} p_wf={p_wf} [{tag}]: rel_residual {bal['rel_residual'][-1]:.2e}; "
                  f"cum_cond {bal['cum_cond'][-1]:+.3e} Дж")


def part_d():
    print("\n=== D. Серия Δt = 3600 / 900 / 360 с при λ ≠ 0 ===")
    for name in ("03_standing_corey", "04_table_table", "05_standing_table_rp"):
        t0 = time.perf_counter()
        rows = run_convergence(load(name, LAM_PHYS))
        vals = " / ".join(f"{r['final_rel']:.2e}" for r in rows)
        mx = " / ".join(f"{r['max_rel']:.2e}" for r in rows)
        print(f"{name}: финальная {vals}; максимальная {mx} "
              f"({time.perf_counter() - t0:.0f} с)")


def part_e():
    print("\n=== E. Сходимость T(r_w) по сетке ===")
    for name, grids, retries in (("03_standing_corey", (25, 50, 100, 150, 200), None),
                                 ("04_table_table", (25, 50, 100, 150), 14)):
        for tag, lam in VARIANTS:
            vals = []
            for N in grids:
                cfg = load(name, lam)
                cfg.grid.N = N
                if retries is not None:
                    cfg.numerics.max_retries = retries
                _, h, _ = run_cfg(cfg)
                vals.append(h.states[-1].T[0])
            inc = np.abs(np.diff(vals))
            print(f"{name} [{tag}] N = {grids}: T(r_w) = "
                  f"{', '.join(f'{v:.6f}' for v in vals)}; приращения "
                  f"{', '.join(f'{v:.5f}' for v in inc)} К")


def part_f():
    print("\n=== F. README 04, рычаг 1: T(r_w) при разных ОФП ===")
    coreys = [("Кори n_g=2, krg_max=0.8", dict(S_gc=0.05, n_g=2.0, krg_max=0.8)),
              ("Кори n_g=3, krg_max=0.3", dict(S_gc=0.05, n_g=3.0, krg_max=0.3)),
              ("Кори n_g=4, krg_max=0.1, S_gc=0.1", dict(S_gc=0.1, n_g=4.0, krg_max=0.1))]
    for tag, lam in VARIANTS:
        rows = []
        cfg = load("04_table_table", lam)
        _, h, _ = run_cfg(cfg)
        rows.append(("табличная", h.states[-1]))
        for label, kw in coreys:
            cfg = load("04_table_table", lam)
            rp = cfg.relperm
            rp.model, rp.file = "corey", None
            rp.S_or, rp.n_o, rp.kro_max = 0.2, 2.0, 1.0
            for k, v in kw.items():
                setattr(rp, k, v)
            _, h, _ = run_cfg(cfg)
            rows.append((label, h.states[-1]))
        print(f"[{tag}] " + "; ".join(f"{lab}: S_g^max {st.Sg.max():.4f}, T(r_w) {st.T[0]:.4f}"
                                       for lab, st in rows))


def part_g():
    print("\n=== G. test_dt_convergence на 07 ===")
    DT_REF = 50.0
    DT_LIST = [1800.0, 1200.0, 900.0, 720.0, 600.0, 450.0, 400.0, 360.0]
    for tag, lam in VARIANTS:
        def first_interval(dt):
            cfg = copy.deepcopy(load("07_degassing_adiabatic_only", lam))
            cfg.time.dt_integration = float(dt)
            cfg.time.history = cfg.time.history[:1]
            _, h, _ = run_cfg(cfg)
            return np.asarray(h.states[-1].T, float)
        T_ref = first_interval(DT_REF)
        err = {dt: float(np.max(np.abs(first_interval(dt) - T_ref))) for dt in DT_LIST}
        ordered = sorted(err, reverse=True)
        mono = max(err[f] / err[c] for c, f in zip(ordered, ordered[1:]))
        trend = max(e / (err[max(err)] * dt / max(err)) for dt, e in err.items())
        print(f"[{tag}] ошибки: " + ", ".join(f"{dt:g}: {e:.3e}" for dt, e in err.items()))
        print(f"[{tag}] max отношение соседних (порог 1.5): {mono:.3f}; "
              f"max отношение к тренду O(dt) (порог 2.0): {trend:.3f}")


def main():
    print(f"Код: {Path(_factory.__file__).resolve()}")
    t0 = time.perf_counter()
    out = part_a()
    part_b(out)
    part_c()
    part_g()
    part_f()
    part_e()
    part_d()
    print(f"\nВсего {time.perf_counter() - t0:.0f} с")


if __name__ == "__main__":
    main()
