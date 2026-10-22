"""BUG-022: критерий сходимости Ньютона по ячейке, отнесённый к её поровому объёму — замер.

Код решателя не меняется: проба подменяет на классе RadialBlackOilModel два Ньютона
прототипа (_newton_fixed_active_set — ступени 1-3, _newton_switching — ступень 4)
копиями из blackoil.py (база 7b34a33), в которых к абсолютному критерию
    ||f||_inf <= atol + rtol*max(||f_0||_inf, 1e-9)
добавлено условие по ячейке (форма «И», вариант 3 issue #82):
    max_i |f_c,i| * dt / V_i <= eps,   c = нефть, газ;
f — та же невязка residual(): м³ст/с, газовые строки уже поделены на gas_residual_scale;
V_i — нормировка ячейки, берётся на state_old (постоянна внутри шага):
    pv  — поровый объём pore_volume_m3(bulk_volumes_m3, p_old), м³ (как CNV в OPM Flow);
    oil — запас нефти ячейки oi_old, м³ст.
В недонасыщенной ячейке ошибка R_s за шаг (R_s входит только в накопление газа):
    delta R_s <= eps * B_o * (gas_residual_scale + R_s)    (pv),
    delta R_s <= eps * (gas_residual_scale + R_s)          (oil).

Варианты: 0 — код базы без подмены; copy — подмена с eps = inf (проверка, что копии
побитово равны оригиналу); pv<eps>, oil<eps> — например pv1e-8.

Переменные окружения (опыт к найденному полу округления):
  BUG022_KAPPA — пол нормировки: V_i -> max(V_i, kappa * eps_маш * max_j V_j / eps), чтобы
                 порог ячейки не опускался ниже шума округления крупнейшей ячейки (функция
                 качества линейного поиска — ||f||_inf по всем ячейкам — на этом шуме стоит);
  BUG022_REXT  — R_ext примера, м (опыт на большой области дренирования);
  BUG022_TAG   — суффикс имён выходных файлов.

Режимы:
  examples <вариант> [имя ...]   примеры (по умолчанию все): отпечаток истории, время,
                                 сборок якобиана, шагов advance и отказов, ступени;
                                 пример 17 — ещё ряд R_s(r_w) на останове
  compare <имя> <вариант A> <вариант B>   наибольшие отличия историй (hist_*.npz)
  fptable                        сводка examples_all_*.out.txt: «=» — побитово как 0

Вывод — в stdout и в файл рядом со скриптом (UTF-8). Истории hist_*.npz в git не идут.
Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\cell_tol.py examples copy
    .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\cell_tol.py examples pv1e-8 17_shut_in_strong_cooling
"""

import hashlib
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
# BUG022_SOLVER — numerical_solver проверяемого дерева; по умолчанию — основной каталог
SOLVER = Path(os.environ.get("BUG022_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
for _p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(_p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from radial_blackoil import blackoil as bo_mod  # noqa: E402
from radial_blackoil.blackoil import BlackOilNewtonReport  # noqa: E402

BAR = 1e5
SHUT17 = "17_shut_in_strong_cooling"
CELL = {"eps": None, "norm": "pv", "soft": False, "refine": False}   # заполняется install()
KAPPA = os.environ.get("BUG022_KAPPA")
REXT = os.environ.get("BUG022_REXT")
TAG = os.environ.get("BUG022_TAG", "")
EPS_MACH = np.finfo(float).eps
# Отказы Ньютона при выполненном абсолютном критерии (недобрало только условие ячейки):
# stall — линейный поиск ступеней 1-3 не уменьшил ||f||; maxit — исчерпан лимит итераций
# (ступени 1-3 — 15, ступень 4 — 40). base — те же отказы при невыполненном абсолютном.
FAILS = Counter()


class Tee:
    """Печать в stdout и в файл вывода."""

    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def __call__(self, *a):
        line = " ".join(str(x) for x in a)
        print(line, flush=True)
        self.f.write(line + "\n")
        self.f.flush()


def _cell_weights(self, state_old, dt_s):
    """dt / V_i по ячейкам; V_i — нормировка CELL['norm'] на state_old."""
    if CELL["norm"] == "pv":
        v = self.rock.pore_volume_m3(self.grid.bulk_volumes_m3, state_old.pressure_bar)
    else:
        v = self._old_inventories(state_old)[0]
    v = np.asarray(v, float)
    if KAPPA and CELL["eps"] != np.inf:
        v = np.maximum(v, float(KAPPA) * EPS_MACH * v.max() / CELL["eps"])
    return float(dt_s) / v


def _cell_metric(self, f, w):
    """Мера по ячейкам: max |f| * dt / V по обеим строкам (eps = inf — 0, условие всегда выполнено)."""
    if CELL["eps"] == np.inf:
        return 0.0
    # pytest_cell_tol.py: условие только у моделей фабрики GPN (как флаг cell_tol плана)
    if CELL.get("require_mark") and not getattr(self, "_probe_cell", False):
        return 0.0
    n = self.grid.n
    return max(float(np.max(np.abs(f[:n]) * w)), float(np.max(np.abs(f[n:]) * w)))


def _cell_ok(self, f, w):
    """Условие по ячейке: мера <= eps."""
    return _cell_metric(self, f, w) <= CELL["eps"]


def _soft_stop(c, c_abs):
    """«Мягкий» вариант: после абсолютного критерия мера не убыла — остановиться (сошлось)."""
    # у w и q прогресс доводки обеспечивает линейный поиск по своей мере — правило только для s
    return CELL["soft"] and not CELL["refine"] and c_abs is not None and c >= c_abs


# ── Копии Ньютонов blackoil.py (база 7b34a33) с условием по ячейке ──
# Отличия от оригинала помечены «BUG-022 probe»; остальное — текст оригинала.

def newton_fixed_active_set(self, z0, state_old, dt_s, gas_active, max_iter=15, rtol=1e-8, atol_sm3s=1e-11):
    z = np.asarray(z0, float).copy(); f = self.residual(z, state_old, dt_s, gas_active); nrm = np.linalg.norm(f, np.inf)
    scale = max(nrm, 1e-9); tol = atol_sm3s + rtol * scale
    w = _cell_weights(self, state_old, dt_s)  # BUG-022 probe
    merit = (lambda v: np.linalg.norm(v)) if self._line_search_l2 else (lambda v: np.linalg.norm(v, np.inf))
    c = _cell_metric(self, f, w)  # BUG-022 probe
    if nrm <= tol and c <= CELL["eps"]: return z, BlackOilNewtonReport(True, 0, float(nrm))  # BUG-022 probe
    c_abs = c if nrm <= tol else None  # BUG-022 probe: мера последнего приближения с выполненным абсолютным
    for it in range(1, max_iter + 1):
        J, f = self.finite_difference_jacobian(z, state_old, dt_s, gas_active)
        try: dz = self._linear_solve(J, -f)
        except Exception: return z, BlackOilNewtonReport(False, it, float(nrm))
        if self._sg_step_max is not None:
            dsg = np.abs(dz[self.grid.n:][gas_active])
            if dsg.size and dsg.max() > self._sg_step_max: dz = dz * (self._sg_step_max / dsg.max())
        # BUG-022 probe, вариант w: после абсолютного критерия (доводка) линейный поиск
        # идёт по мере ячеек — функция качества ||f|| забойную ячейку не видит
        # q — то же по взвешенной L2: направление Ньютона — направление спуска для ||D f||_2
        # при любой диагональной D, для L_inf-норм это не так
        if CELL["refine"] and c_abs is not None:
            m = (lambda v: _cell_metric(self, v, w)) if CELL["refine"] == "w" else \
                (lambda v: float(np.linalg.norm(np.abs(v).reshape(2, -1) * w)))
        else:
            m = merit
        mf = m(f); alpha = 1.0; accepted = False
        for _ in range(12):
            trial = z + alpha * dz
            if self._trial_is_reasonable(trial, gas_active):
                ft = self.residual(trial, state_old, dt_s, gas_active)
                if m(ft) < mf: z = trial; f = ft; accepted = True; break
            alpha *= 0.5
        if not accepted:
            FAILS["stall" if nrm <= tol else "stall base"] += 1  # BUG-022 probe
            # мягкий вариант: линейный поиск встал после абсолютного критерия — сошлось
            return z, BlackOilNewtonReport(CELL["soft"] and nrm <= tol, it, float(nrm))
        nrm = np.linalg.norm(f, np.inf)
        c = _cell_metric(self, f, w)  # BUG-022 probe
        if nrm <= tol and (c <= CELL["eps"] or _soft_stop(c, c_abs)):
            if c > CELL["eps"]: FAILS["soft stop"] += 1
            return z, BlackOilNewtonReport(True, it, float(nrm))
        c_abs = c if nrm <= tol else None
    FAILS["maxit" if nrm <= tol else "maxit base"] += 1  # BUG-022 probe
    return z, BlackOilNewtonReport(CELL["soft"] and nrm <= tol, max_iter, float(nrm))


def newton_switching(self, state_old, dt_s, max_iter=40, rtol=1e-8, atol_sm3s=1e-11, dp_rel=0.3, ds_max=0.2, flips_to_freeze=2):
    state_old = state_old.copy(); n = self.grid.n; nf = max(n - 1, 0)
    mask = state_old.gas_active.copy(); z = self.pack(state_old, mask)
    scale = max(np.linalg.norm(self.residual(z, state_old, dt_s, mask), np.inf), 1e-9); tol = atol_sm3s + rtol * scale
    w = _cell_weights(self, state_old, dt_s)  # BUG-022 probe
    switched = total = 0; flips = np.zeros(nf, int); prev = None; polish = False
    c_abs = None  # BUG-022 probe
    self._upwind_frozen = np.zeros(nf, bool); self._upwind_left = np.zeros(nf, bool)
    try:
        for it in range(1, max_iter + 2):
            p = z[:n]; left = (p[:-1] - p[1:]) >= 0
            if not polish:
                if prev is not None: flips += (left != prev) & ~self._upwind_frozen
                fr = (~self._upwind_frozen) & (flips >= flips_to_freeze)
                self._upwind_left = np.where(fr, left, self._upwind_left); self._upwind_frozen = self._upwind_frozen | fr
            prev = left
            J, f = self.finite_difference_jacobian(z, state_old, dt_s, mask); nrm = np.linalg.norm(f, np.inf)
            c = _cell_metric(self, f, w)  # BUG-022 probe
            if nrm <= tol and switched == 0:
                fz = self._upwind_frozen
                if fz is None or np.array_equal(self._upwind_left[fz], left[fz]):
                    # BUG-022 probe: условие ячейки; мягкий вариант — ещё мера не убыла или лимит
                    if c <= CELL["eps"] or _soft_stop(c, c_abs) or (CELL["soft"] and it > max_iter):
                        if c > CELL["eps"]: FAILS["soft stop4"] += 1
                        new = self.unpack(z, mask); new.sg[mask & (new.sg < 0)] = 0.0
                        ok = not np.any(new.sg[mask] > 0.98)
                        return new, BlackOilNewtonReport(ok, it - 1, float(nrm), 1, total)
                    if it > max_iter: FAILS["maxit4"] += 1
                    c_abs = c
                else:
                    self._upwind_frozen = None; polish = True; continue
            else:
                c_abs = None
            if it > max_iter: break
            try: dz = self._linear_solve(J, -f)
            except Exception: break
            x = z[n:]; lim = dp_rel * np.maximum(p, 1.0)
            pn = np.maximum(p + np.clip(dz[:n], -lim, lim), 1.0 + 1e-6)
            xn = np.where(mask, x + np.clip(dz[n:], -ds_max, ds_max), np.maximum(x + dz[n:], 0.0))
            if not (np.all(np.isfinite(pn)) and np.all(np.isfinite(xn))): break
            xn, mask, switched = self._switch_phases(pn, xn, mask); total += switched
            z = np.concatenate([pn, xn])
        f = self.residual(z, state_old, dt_s, mask)
        return self.unpack(z, mask), BlackOilNewtonReport(False, max_iter, float(np.linalg.norm(f, np.inf)), 1, total)
    finally:
        self._upwind_frozen = None; self._upwind_left = None


def install(variant):
    """Подмена Ньютонов на классе; вариант 0 — без подмены."""
    if variant == "0":
        return
    # s — мягкий: после абсолютного критерия остановка, если мера не убыла, линейный поиск
    # встал или кончились итерации; w — мягкий + доводка с линейным поиском по мере ячеек
    CELL["soft"] = CELL["refine"] = False
    if variant == "copy":
        CELL["eps"] = np.inf
    else:
        m = re.fullmatch(r"([swq]?)(pv|oil)([0-9.eE+-]+)", variant)
        if not m:
            raise SystemExit(f"неизвестный вариант {variant!r}")
        CELL["soft"] = m.group(1) in ("s", "w", "q")
        CELL["refine"] = m.group(1) if m.group(1) in ("w", "q") else False
        CELL["norm"], CELL["eps"] = m.group(2), float(m.group(3))
    cls = bo_mod.RadialBlackOilModel
    cls._newton_fixed_active_set = newton_fixed_active_set
    cls._newton_switching = newton_switching


class Counters:
    """Сборки якобиана, шаги advance (отказы, ступень принятого) одной модели."""

    def __init__(self, model):
        self.jac = 0
        self.steps = 0
        self.fail = 0
        self.stage = Counter()
        jac0, adv0 = model.finite_difference_jacobian, model.advance

        def jac(*a, **k):
            self.jac += 1
            return jac0(*a, **k)

        def advance(state_old, dt_s, *a, **k):
            new, rep = adv0(state_old, dt_s, *a, **k)
            self.steps += 1
            if not rep.converged:
                self.fail += 1
            else:
                self.stage[4 if rep.phase_switching else 3 if rep.globalized else 2 if rep.fallback else 1] += 1
            return new, rep

        model.finite_difference_jacobian = jac
        model.advance = advance


def fingerprint(history):
    h = hashlib.sha1()
    for s in history.states:
        for a in (s.p, s.T, s.Sg, s.Rs):
            h.update(np.ascontiguousarray(a, float).tobytes())
    return h.hexdigest()[:12]


def save_history(history, path):
    np.savez(path,
             p=np.array([s.p for s in history.states]), T=np.array([s.T for s in history.states]),
             Sg=np.array([s.Sg for s in history.states]), Rs=np.array([s.Rs for s in history.states]),
             t=np.asarray(history.times, float),
             q_o=np.array([w.q_o_std for w in history.well_data], float))


def report_balances(out, history, grid, cfg):
    """Невязки балансов, как в README: энергия — на конец (energy_balance), масса — max по записям."""
    if str(SOLVER / "examples") not in sys.path:
        sys.path.insert(0, str(SOLVER / "examples"))
    from energy_balance import compute_balance
    from mass_balance import compute_mass_balance
    e = compute_balance(history, grid, cfg)
    m = compute_mass_balance(history)
    mo = float(np.max(m["rel_residual_o"])) if m is not None else float("nan")
    mg = float(np.max(m["rel_residual_g"])) if m is not None else float("nan")
    out(f"    балансы: энергия на конце {float(e['rel_residual'][-1]):.2e}; "
        f"масса max — нефть {mo:.2e}, газ {mg:.2e}")


def report_rs_well(out, history):
    """Пример 17: R_s(r_w) на останове (записи 16..конец) — монотонность."""
    rs = np.array([s.Rs[0] for s in history.states])
    t = np.asarray(history.times, float) / 86400.0
    d = np.diff(rs[16:])
    out(f"    R_s(r_w): запись 16 {rs[16]:.5f}, 39 {rs[39]:.5f}, 43 {rs[43]:.5f}, конец {rs[-1]:.5f} "
        f"(t = {t[-1]:.2f} сут); min dR_s по записям 16..{len(rs) - 1} = {d.min():+.2e}, "
        f"убываний {int(np.sum(d < 0))}")
    out("    сутки 20-30: " + " ".join(f"{v:.5f}" for v in rs[43:54]))


def run_examples(args):
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config
    variant = args[0]
    install(variant)
    names = args[1:] or sorted(p.parent.name for p in (SOLVER / "examples").glob("*/config.json"))
    tag = names[0] if len(names) == 1 else "all"
    out = Tee(HERE / f"examples_{tag}_{variant}{TAG}.out.txt")
    import gpn_multiphase_solver.factory as _factory
    out(f"код: {SOLVER}; вариант {variant}; eps = {CELL['eps']}, нормировка {CELL['norm']}; "
        f"kappa = {KAPPA or '—'}; R_ext = {REXT or 'примера'}")
    # фактически загруженные модули: в worktree пакет мог прийти из основного каталога
    out(f"модули: {Path(_factory.__file__).parent}; {Path(bo_mod.__file__).parent}")
    for name in names:
        cfg = load_config(SOLVER / "examples" / name / "config.json")
        cfg.output.log_level = "ERROR"
        if REXT:
            cfg.geometry.R_ext = float(REXT)
        sim, init = SimulatorFactory.from_config(cfg)
        cnt = Counters(sim._hydro._model)
        FAILS.clear()
        t0 = time.perf_counter()
        try:
            hist = sim.run(init)
            fp = fingerprint(hist)
            save_history(hist, HERE / f"hist_{name}_{variant}{TAG}.npz")
        except RuntimeError as e:
            hist, fp = None, f"✗ {str(e)[:80]}"
        wall = time.perf_counter() - t0
        out(f"{name:<28} {wall:6.1f} с  отпечаток {fp}  якобианов {cnt.jac}  шагов {cnt.steps}  "
            f"отказов {cnt.fail}  ступени {dict(sorted(cnt.stage.items()))}  "
            f"отказы Ньютона {dict(sorted(FAILS.items()))}")
        if hist is not None:
            report_balances(out, hist, sim._grid, cfg)
        if name == SHUT17 and hist is not None:
            report_rs_well(out, hist)


def run_compare(args):
    name, va, vb = args
    a = np.load(HERE / f"hist_{name}_{va}.npz")
    b = np.load(HERE / f"hist_{name}_{vb}.npz")
    out = Tee(HERE / f"compare_{name}_{va}_{vb}.out.txt")
    out(f"=== {name}: {va} против {vb}; записей {len(a['t'])} / {len(b['t'])} ===")
    if a["p"].shape != b["p"].shape:
        out("  разные размеры историй — сравнение невозможно")
        return
    for key, unit, scale in (("p", "бар", BAR), ("T", "К", 1.0), ("Sg", "", 1.0), ("Rs", "м³/м³", 1.0)):
        d = np.abs(a[key] - b[key]) / scale
        n, j = np.unravel_index(int(np.argmax(d)), d.shape)
        out(f"  {key}: max|Δ| = {d.max():.3e} {unit} (запись {n}, ячейка {j}); "
            f"у забоя {d[:, 0].max():.3e}; на последней записи {d[-1].max():.3e}; "
            f"побитово записей {int(np.sum(np.all(d == 0, axis=1)))} из {d.shape[0]}")
    dq = np.abs(a["q_o"] - b["q_o"])
    out(f"  q_o: max|Δ| = {dq.max():.3e} м³ст/с")


def run_fptable(_args):
    pat = re.compile(r"^(\S+)\s+([\d.]+) с\s+отпечаток (\S+)\s+якобианов (\d+)\s+шагов (\d+)\s+отказов (\d+)")
    runs = {}
    for f in sorted(HERE.glob("examples_all_*.out.txt")):
        v = f.stem[len("examples_all_"):-len(".out")]
        runs[v] = {m.group(1): m.groups()[1:] for m in map(pat.match, f.read_text(encoding="utf-8").splitlines()) if m}
    if "0" not in runs:
        raise SystemExit("нет examples_all_0.out.txt")
    out = Tee(HERE / "fptable.out.txt")
    vs = ["0"] + sorted(v for v in runs if v != "0")
    out("пример".ljust(28) + "".join(v.rjust(26) for v in vs))
    for name, base in runs["0"].items():
        cells = []
        for v in vs:
            r = runs[v].get(name)
            if r is None:
                cells.append("—".rjust(26))
                continue
            wall, fp, jac, steps, fail = r
            mark = "=" if fp == base[1] else ("✗" if fp.startswith("✗") else "≠")
            cells.append(f"{mark} {wall:>6}с J{jac:>6} отк{fail:>4}".rjust(26))
        out(name.ljust(28) + "".join(cells))


if __name__ == "__main__":
    mode, rest = sys.argv[1], sys.argv[2:]
    {"examples": run_examples, "compare": run_compare, "fptable": run_fptable}[mode](rest)
