"""DEBT-015: равномерное A-retry адаптера против локального дробления в Simulator.

Локальное дробление (подмена Simulator._advance): адаптер делает одну попытку
(max_retries = 0, отказ — RuntimeError). Отказавший подшаг h делится пополам
и повторяется из того же состояния; принятый подшаг сразу идёт в энергию и в
балансы — отката нет, повторного прохода нет. Предел — h_min = dt / 2**max_retries
(та же глубина, что у A-retry). Политика роста после принятого подшага:
  G0 — h не растёт до конца шага dt (последовательность как у равномерного,
       пока он сходится на первой глубине);
  G1 — h = min(2h, остаток);
  G1a — G1 с выравниванием (код плана): подшаг — dt/2**k, удвоение только если
        пройденная часть кратна удвоенному подшагу.
base — штатный код (равномерное A-retry + повторный проход BUG-010).

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P examples <base|G0|G1|G1a>[:имя] [пример ...]  # история → history_<метка>/
    .venv\\Scripts\\python P compare <метка_a> <метка_b>
    .venv\\Scripts\\python P depth                                   # глубина дробления G1a в точках README 03/04/05
    .venv\\Scripts\\python P case <конфиг теста> <политика> <ступень4 0|1>
    .venv\\Scripts\\python P shutin <19|20|21> <A|B> <dt_int> <base|G0|G1> [max_retries] [предел_с]
shutin — 10 сут добычи + 3 сут останова (A: p_wf = p_ext; B: q_oil = 0), как
vault/issues/bug-020/probes/e2e_shutin.py.
"""

import copy
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.simulator import Simulator  # noqa: E402
from gpn_multiphase_solver.state import SimulationState  # noqa: E402

DAY = 86400.0
FIELDS = ("p", "Sg", "Rs", "T", "regime")
FLUXES = ("G_o", "G_g", "G_free_gas")
WELL = ("q_o_std", "q_g_std", "m_o_well", "m_g_well", "p_wf", "T_wf")
ENERGY = ("delta_E", "cum_adiab", "cum_conv", "cum_jt", "cum_deg", "cum_cond")
MASS = ("M_o", "M_g", "cum_o_well", "cum_o_ext", "cum_g_well", "cum_g_ext")

# ── Счётчики: сбрасываются перед каждым расчётом ──
ST = {}


def reset():
    ST.clear()
    ST.update(adv_ok=0, adv_fail=0, t_adv=0.0, h_ok=Counter(), depth=Counter(),
              t_reached=0.0)


def wrap_model(model, wall=None, t0=None):
    """Счёт вызовов advance прототипа (принятых и отказавших) и их времени."""
    orig = model.advance

    def adv(state_old, dt_s, *a, **kw):
        if wall is not None and time.perf_counter() - t0 > wall:
            raise TimeoutError("предел времени счёта")
        t1 = time.perf_counter()
        new, rep = orig(state_old, dt_s, *a, **kw)
        ST["t_adv"] += time.perf_counter() - t1
        if rep.converged:
            ST["adv_ok"] += 1
        else:
            ST["adv_fail"] += 1
        return new, rep

    model.advance = adv


def make_aligned(max_retries):
    """G1a — код плана DEBT-015: подшаг в единицах dt/2**max_retries, рост ×2 только с выравниванием."""

    def _advance(self, state, dt, bc, balance, mass, allow_subdivision=True):
        n_units = 2 ** max_retries          # dt в единицах наименьшего подшага
        done = 0                            # пройдено единиц
        size = n_units                      # текущий подшаг, единиц (степень двойки)
        depth = 0
        hydro_result = None
        while done < n_units:
            h = dt / (n_units // size)      # деление на степень двойки — точно
            try:
                hydro_result = self._hydro.solve(state, h, bc)
            except RuntimeError:
                if size == 1:
                    raise RuntimeError(
                        f"локальное дробление: не сошёлся при h = {h:.3e} с, "
                        f"t = {state.t / DAY:.4f} сут")
                size //= 2
                depth += 1
                continue
            if mass is not None:
                mass.add_step(hydro_result)
            T_new = self._energy.solve(hydro_result, state, h, bc, collect=balance)
            state = SimulationState(
                p=hydro_result.state.p, Sg=hydro_result.state.Sg,
                Rs=hydro_result.state.Rs, T=T_new,
                regime=hydro_result.state.regime, t=hydro_result.state.t)
            ST["h_ok"][round(h, 4)] += 1
            ST["t_reached"] = state.t
            done += size
            # Рост ×2, если граница кратна удвоенному подшагу: подшаги остаются dt/2**k
            if done < n_units and done % (2 * size) == 0:
                size *= 2
        ST["depth"][depth] += 1
        return state, hydro_result

    return _advance


def make_local(policy, max_retries):
    """Simulator._advance с локальным дроблением; policy — G0 или G1 (G1a — make_aligned)."""
    if policy == "G1a":
        return make_aligned(max_retries)

    def _advance(self, state, dt, bc, balance, mass, allow_subdivision=True):
        h_min = dt / 2 ** max_retries
        h = dt
        t_left = dt
        depth = 0
        hydro_result = None
        while t_left > 0.0:
            h = min(h, t_left)
            try:
                hydro_result = self._hydro.solve(state, h, bc)
            except RuntimeError:
                if h / 2 < h_min * (1 - 1e-12):
                    raise RuntimeError(
                        f"локальное дробление: не сошёлся при h = {h:.3e} с "
                        f"(h_min = {h_min:.3e}), t = {state.t / DAY:.4f} сут")
                h /= 2
                depth += 1
                continue
            # Принятый подшаг: энергия и балансы сразу — откатывать нечего
            if mass is not None:
                mass.add_step(hydro_result)
            T_new = self._energy.solve(hydro_result, state, h, bc, collect=balance)
            state = SimulationState(
                p=hydro_result.state.p, Sg=hydro_result.state.Sg,
                Rs=hydro_result.state.Rs, T=T_new,
                regime=hydro_result.state.regime, t=hydro_result.state.t)
            ST["h_ok"][round(h, 4)] += 1
            ST["t_reached"] = state.t
            t_left -= h
            if policy == "G1":
                h = 2 * h
        ST["depth"][depth] += 1
        return state, hydro_result

    return _advance


def build(cfg, policy, wall=None):
    cfg.output.log_level = "ERROR"
    max_retries = cfg.numerics.max_retries
    sim, s0 = SimulatorFactory.from_config(cfg)
    t0 = time.perf_counter()
    wrap_model(sim._hydro._model, wall, t0)
    if policy == "base":
        Simulator._advance = ORIG_ADVANCE
    else:
        sim._hydro._max_retries = 0          # одна попытка, отказ — RuntimeError
        Simulator._advance = make_local(policy, max_retries)
    return sim, s0, t0


ORIG_ADVANCE = Simulator._advance


def summary(status, el):
    h = ", ".join(f"{k:g}×{v}" for k, v in sorted(ST["h_ok"].items()))
    return (f"{status}; счёт {el:.1f} с, в advance {ST['t_adv']:.1f} с; advance принято "
            f"{ST['adv_ok']}, отказов {ST['adv_fail']}" + (f"; подшаги: {h}" if h else ""))


def run_examples(tag, names):
    # Метка «политика:имя» — снимок под другим именем (base:impl — штатный код
    # проверяемого дерева после правки); каталог history_<политика>_<имя>
    policy = tag.split(":")[0]
    out = HERE / f"history_{tag.replace(':', '_')}"
    out.mkdir(exist_ok=True)
    import gpn_multiphase_solver
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    for ex in names:
        reset()
        cfg = load_config(SOLVER_ROOT / "examples" / ex / "config.json")
        sim, s0, t0 = build(cfg, policy)
        h = sim.run(s0)
        el = time.perf_counter() - t0
        arrays = {f: np.array([getattr(s, f) for s in h.states]) for f in FIELDS}
        arrays["t"] = np.array(h.times, float)
        for f in FLUXES:
            arrays[f] = np.array([getattr(r, f) for r in h.hydro_results[1:]])
        for f in WELL:
            arrays["well_" + f] = np.array([getattr(w, f) for w in h.well_data], float)
        for f in ENERGY:
            arrays["energy_" + f] = np.array([b[f] for b in h.balance], float)
        mb = getattr(h, "mass_balance", None)
        if mb and mb[0] is not None:
            for f in MASS:
                arrays["mass_" + f] = np.array([b[f] for b in mb], float)
        np.savez(out / f"{ex}.npz", **arrays)
        dep = {k: v for k, v in ST["depth"].items() if k > 0}
        print(f"{ex:28s} {summary('✓', el)}" + (f"; глубина>0: {dep}" if dep else ""),
              flush=True)


def compare(a_tag, b_tag):
    da = HERE / f"history_{a_tag.replace(':', '_')}"
    db = HERE / f"history_{b_tag.replace(':', '_')}"
    bad = 0
    for fa in sorted(da.glob("*.npz")):
        fb = db / fa.name
        if not fb.is_file():
            continue
        a, b = np.load(fa), np.load(fb)
        common = [k for k in a.files if k in b.files]
        diff = [k for k in common if a[k].shape != b[k].shape or not np.array_equal(a[k], b[k])]
        if diff:
            bad += 1
            dd = {k: float(np.max(np.abs(a[k] - b[k]))) for k in diff if a[k].shape == b[k].shape}
            print(f"{fa.stem}: РАЗЛИЧИЕ " + ", ".join(f"{k} {v:.2e}" for k, v in dd.items()))
        else:
            print(f"{fa.stem}: побитово ({len(common)} массивов)")
    print(f"итого: различий {bad}")


BASES = {"19": "19_rs150_cooling", "20": "20_rs300_cooling", "21": "21_rs100_cooling"}


def run_shutin(key, mode, dt_int, policy, max_retries=None, wall=None):
    reset()
    cfg = load_config(SOLVER_ROOT / "examples" / BASES[key] / "config.json")
    iv = cfg.time.history[0]
    p_ext = cfg.initial_conditions.p0
    hist = []
    for i in range(13):
        x = copy.deepcopy(iv)
        x.dt = DAY
        if i >= 10:
            if mode == "A":
                x.control, x.p_wf = "pressure", p_ext
            else:
                x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    cfg.time.dt_integration = dt_int
    if max_retries is not None:
        cfg.numerics.max_retries = max_retries
    sim, s0, t0 = build(cfg, policy, wall)
    try:
        sim.run(s0)
        status = "✓"
    except (RuntimeError, TimeoutError) as e:
        status = f"✗ {str(e)[:140]}"
    el = time.perf_counter() - t0
    reached = f"; достигнуто {ST['t_reached'] / DAY:.3f} сут" if policy != "base" else ""
    print(f"{BASES[key]} {mode} dt_int={dt_int:.0f} {policy} max_retries="
          f"{cfg.numerics.max_retries}: {summary(status, el)}{reached}", flush=True)


def run_case(path, policy, stage4):
    """Конфиг теста (tests/data/...) целиком; stage4 = 0 — без четвёртой ступени advance."""
    reset()
    cfg = load_config(SOLVER_ROOT / path)
    sim, s0, t0 = build(cfg, policy)
    sim._hydro._model.phase_switching_stage = bool(stage4)
    try:
        h = sim.run(s0)
        st = h.states[-1]
        status = (f"✓ p(r_w) = {st.p[0] / 1e5:.4f} бар, 2ф = "
                  f"{int(np.count_nonzero(st.regime == 1))}, T(r_w) = {st.T[0]:.4f} К")
    except RuntimeError as e:
        status = f"✗ {str(e)[:120]}"
    print(f"{path} {policy} ступень4={stage4}: {summary(status, time.perf_counter() - t0)}",
          flush=True)


def run_depth(points):
    """Наибольшая глубина дробления G1a за прогон — минимально достаточный max_retries (таблицы README, DEBT-041)."""
    for name, pwf, N in points:
        reset()
        cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
        if N is not None:
            cfg.grid.N = N
        if pwf is not None:
            # Депрессия — всем интервалам истории, как в DEBT-041 (max_retries_probe.py)
            for iv in cfg.time.history:
                iv.p_wf = pwf * 1e6
        sim, s0, t0 = build(cfg, "G1a")
        sim.run(s0)
        k = max(ST["depth"])
        print(f"{name} p_wf={pwf} N={N}: k = {k}; отказов {ST['adv_fail']}; "
              f"{time.perf_counter() - t0:.1f} с", flush=True)


README_POINTS = (
    [("03_standing_corey", p, 150) for p in (8.0, 7.5, 7.0, 6.0, 5.0, 4.0, 2.0, 0.5)]
    + [("03_standing_corey", 8.0, N) for N in (50, 75, 100, 140, 200)]
    + [("04_table_table", p, None) for p in (14, 12, 10, 8, 6, 4, 3, 2, 1, 0.5)]
    + [("04_table_table", 8.0, N) for N in (100, 150, 200)]
    + [("05_standing_table_rp", p, None) for p in (8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0)])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "depth":
        run_depth(README_POINTS)
        sys.exit(0)
    if cmd == "case":
        run_case(sys.argv[2], sys.argv[3], int(sys.argv[4]))
        sys.exit(0)
    if cmd == "examples":
        names = sys.argv[3:] or sorted(d.name for d in (SOLVER_ROOT / "examples").iterdir()
                                       if (d / "config.json").is_file())
        run_examples(sys.argv[2], names)
    elif cmd == "compare":
        compare(sys.argv[2], sys.argv[3])
    elif cmd == "shutin":
        a = sys.argv[2:]
        run_shutin(a[0], a[1], float(a[2]), a[3],
                   int(a[4]) if len(a) > 4 and a[4] != "-" else None,
                   float(a[5]) if len(a) > 5 else None)
    else:
        raise SystemExit(__doc__)
