"""DEBT-067, проба планирования: пол округления в условии сходимости по ячейке — варианты.

Условие BUG-022 (eq:newton_cell_tol): строка r (нефть или газ ячейки i) проходит при
|F_r|*dt/V_p,i <= cell_tol. Пол: строка проходит и при |F_r| <= KAPPA*(|J| ulp(z))_r —
невязка строки не выше её предела округления (eq:newton_cell_floor, DEBT-055).
Строгое условие проверяется первым, теми же операциями: где оно выполнено, всё побитово.

Варианты (эмуляция без правки прототипа — обёртки на экземпляре модели фабрики):
  base — как сейчас;
  a    — пол в каждой проверке; якобиан — последний построенный в этом Ньютоне. У ступеней
         1–3 проверка после обновления — с якобианом предыдущего приближения, до первой
         итерации якобиана нет (строгое условие); у ступени 4 якобиан — в той же точке;
  a1   — пол в каждой проверке; якобиан — в проверяемой точке. У ступеней 1–3 его построила
         бы следующая итерация (в реализации не лишний), здесь строится отдельно;
  v    — у ступеней 1–3 пол только на выходе отказа ('line_search', 'max_iter') при
         выполненном абсолютном критерии, якобиан — в возвращённой точке; ступень 4 — как a;
  impl… (любое имя с этим началом) — код как есть, без эмуляции: проверка реализации
         DEBT-067 (истории должны побитово совпасть с эмуляцией a). Приём по полу виден
         как сошедшаяся проверка с мерой выше порога.

Сценарии — как у DEBT-055 (histories.py) плюс примеры 19–21 (N = 350, шаг 1 сут) и пример 17
при пороге 1e-10; «extra» — остальные 17 примеров.

Запуск из numerical_solver/ (KAPPA — переменная окружения, по умолчанию 1):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-067\\probes\\variants.py run base [сценарии | extra]
    .venv\\Scripts\\python ..\\vault\\issues\\debt-067\\probes\\variants.py compare a a1 v
    .venv\\Scripts\\python ..\\vault\\issues\\debt-067\\probes\\variants.py same a impl
Из worktree — тот же скрипт основного каталога (полный путь): код берётся из каталога
запуска, истории пишутся рядом со скриптом, к историям планирования.
Выход — hist_<сценарий>_<вариант>.npz (в git не идут), variants_<вариант>.out.txt,
variants_compare.out.txt, variants_same_<A>_<B>.out.txt.
"""
import copy
import os
import sys
import time
from pathlib import Path

import numpy as np

# Код — из каталога запуска (основной или worktree), а не из установки в общий venv
SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
HERE = Path(__file__).resolve().parent

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver import factory as _factory                  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory              # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError      # noqa: E402
from gpn_multiphase_solver.io.config import load_config                 # noqa: E402
import radial_blackoil                                                   # noqa: E402

KAPPA = float(os.environ.get("KAPPA", "1.0"))
DAY = 86400.0


def _bug018():
    cfg = load_config(SOLVER / "tests" / "data" / "bug018_rs500" / "config.json")
    cfg.grid.N = 350
    return cfg


def _example(name):
    return lambda: load_config(SOLVER / "examples" / name / "config.json")


def _ex17_tol(tol):
    # Пример 17 с пользовательским порогом ниже умолчания: предел у забоя выше порога на
    # шагах останова 3600 с (DEBT-055: при 1e-10 отклонённых шагов 214 против 47)
    def make():
        cfg = load_config(SOLVER / "examples" / "17_shut_in_strong_cooling" / "config.json")
        cfg.numerics.newton_cell_tol = tol
        return cfg
    return make


def _daily_shutin():
    # TestDailyShutin (tests/test_prototype_phase_switching.py): 10 сут добычи + 3 сут q_oil = 0
    cfg = load_config(SOLVER / "tests" / "data" / "bug020_rs300" / "config.json")
    hist = list(cfg.time.history)
    for _ in range(3):
        x = copy.deepcopy(hist[0])
        x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    return cfg


# сценарий: (конфиг, начало останова в сутках или None)
SCENARIOS = {
    "bug018_n350": (_bug018, None),
    "ex14": (_example("14_high_gor_cooling"), None),
    "ex16": (_example("16_well_shut_in"), 15.0),
    "ex17": (_example("17_shut_in_strong_cooling"), 15.0),
    "ex19": (_example("19_rs150_cooling"), None),
    "ex20": (_example("20_rs300_cooling"), None),
    "ex21": (_example("21_rs100_cooling"), None),
    "daily_shutin": (_daily_shutin, 10.0),
    "ex17_tol1e-10": (_ex17_tol(1e-10), 15.0),
}
# Остальные примеры (ключ — имя папки): запускаются только по имени, в полный прогон не входят
EXTRA = {d.parent.name: (_example(d.parent.name), None)
         for d in sorted((SOLVER / "examples").glob("*/config.json"))
         if not any(d.parent.name.startswith(k[2:] + "_") for k in SCENARIOS if k[2:4].isdigit())}


class Patch:
    """Обёртки модели: якобиан и точка последней проверки, пол в _cells_converged."""

    def __init__(self, model, variant):
        self.m, self.variant = model, variant
        self.J = None          # последний якобиан текущего Ньютона
        self.args = None       # (z, state_old, dt, gas_active) последней невязки или якобиана
        self.stage = ""
        self.n_jac = 0         # якобианы решателя (без диагностических)
        self.n_jac_extra = 0   # якобианы, построенные вариантом a1/v сверх решателя
        self.events = []       # приёмы по полу
        self.rejects = 0       # строгое не выполнено, пол не помог
        res, fd = model.residual, model.finite_difference_jacobian
        fas, sw, cc = model._newton_fixed_active_set, model._newton_switching, model._cells_converged
        self.fd = fd

        def residual(z, state_old, dt_s, gas_active):
            self.args = (z, state_old, dt_s, gas_active)
            return res(z, state_old, dt_s, gas_active)

        def jac(z, state_old, dt_s, gas_active, *a, **kw):
            self.n_jac += 1
            J, f0 = fd(z, state_old, dt_s, gas_active, *a, **kw)
            # невязки внутри fd (сдвинутые z) затёрли args — точка якобиана
            self.J, self.args = J, (np.asarray(z, float), state_old, dt_s, gas_active)
            return J, f0

        def newton_fas(z0, state_old, dt_s, gas_active, *a, **kw):
            self.J, self.stage = None, "1-3"
            z, rep = fas(z0, state_old, dt_s, gas_active, *a, **kw)
            if (variant == "v" and not rep.converged and rep.exit_reason in ("line_search", "max_iter")
                    and rep.residual_inf <= rep.residual_tol and rep.cell_measure > model.cell_tol):
                J, f = fd(z, state_old, dt_s, gas_active)
                self.n_jac_extra += 1
                w = model._cell_weights(state_old, dt_s)
                if self.floor_ok(f, w, J, z, state_old, dt_s, gas_active, "1-3 выход"):
                    rep.converged, rep.exit_reason = True, "converged"
            return z, rep

        def newton_sw(state_old, dt_s, *a, **kw):
            self.J, self.stage = None, "4"
            return sw(state_old, dt_s, *a, **kw)

        def cells(f, w, *rest):
            if variant.startswith("impl"):
                # код DEBT-067: (f, w, J, z) передаёт сам; приём по полу — сошлось при мере > порога
                ok = cc(f, w, *rest)
                if ok and w is not None and model._cell_measure(f, w) > model.cell_tol:
                    self.events.append((self.stage, float(self.args[2]), model._cell_measure(f, w),
                                        np.nan, np.nan, np.nan, np.nan, ""))
                return ok
            if cc(f, w):
                return True
            if variant == "base" or w is None or (variant == "v" and self.stage == "1-3"):
                return False
            z, state_old, dt_s, gas_active = self.args
            if self.stage == "4" or variant in ("a", "v"):
                J = self.J
                if J is None:
                    self.rejects += 1
                    return False
            else:
                J, _ = fd(z, state_old, dt_s, gas_active)
                self.n_jac_extra += 1
            return self.floor_ok(f, w, J, z, state_old, dt_s, gas_active, self.stage)

        model.residual = residual
        model.finite_difference_jacobian = jac
        model._newton_fixed_active_set = newton_fas
        model._newton_switching = newton_sw
        model._cells_converged = cells

    def floor_ok(self, f, w, J, z, state_old, dt_s, gas_active, where):
        """Пол поячеечно: строки, где строгое условие не выполнено, — |F_r| <= KAPPA*(|J| ulp(z))_r."""
        ww = np.concatenate([w, w])
        bad = np.abs(f) * ww > self.m.cell_tol
        noise = abs(J) @ np.spacing(np.abs(z))
        ok = bool(np.all(np.abs(f)[bad] <= KAPPA * noise[bad]))
        if not ok:
            self.rejects += 1
            return False
        # Диагностика приёма: нужное kappa с этим якобианом и с якобианом в точке z
        # (невязки внутри fd затирают args — вернуть)
        saved = self.args
        Jz, _ = self.fd(z, state_old, dt_s, gas_active)
        self.args = saved
        noise_z = abs(Jz) @ np.spacing(np.abs(z))
        n = self.m.grid.n
        meas = float(np.max(np.abs(f) * ww))
        flo = float(np.max(noise * ww))
        flo_z = float(np.max(noise_z * ww))
        k_used = float(np.max(np.abs(f)[bad] / noise[bad]))
        k_z = float(np.max(np.abs(f)[bad] / noise_z[bad]))
        # строки, где действует пол: ячейка и компонент
        rows = [f"{'o' if r < n else 'g'}{r % n}" for r in np.flatnonzero(bad)]
        self.events.append((where, float(dt_s), meas, flo, flo_z, k_used, k_z, ",".join(rows[:6])))
        return True


def run(name, variant, out):
    make, t_shut = SCENARIOS[name] if name in SCENARIOS else EXTRA[name]
    cfg = make()
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    patch = Patch(model, variant)
    calls, msgs = [], []
    orig = sim._hydro.solve

    def solve(state, dt, bc):
        try:
            r = orig(state, dt, bc)
        except HydroConvergenceError as exc:
            calls.append((state.t, dt, 0.0))
            msgs.append(str(exc))
            raise
        calls.append((state.t, dt, 1.0))
        return r

    sim._hydro.solve = solve
    t0 = time.perf_counter()
    try:
        h = sim.run(init)
        res = "прошёл"
    except RuntimeError as e:
        out(f"  {name}: ОТКАЗ РАСЧЁТА {str(e)[:200]}")
        return
    wall = time.perf_counter() - t0
    data = {f: np.array([getattr(s, f) for s in h.states]) for f in ("p", "Sg", "Rs", "T", "regime")}
    data["t"] = np.array([s.t for s in h.states])
    data["calls"] = np.array(calls, float).reshape(-1, 3)
    data["msgs"] = np.array(msgs, dtype=str)
    data["n_jac"] = np.array([patch.n_jac, patch.n_jac_extra])
    data["events"] = np.array([e[1:7] for e in patch.events], float).reshape(-1, 6)
    np.savez(HERE / f"hist_{name}_{variant}.npz", **data)
    drs = ""
    if t_shut is not None:
        rs0 = data["Rs"][:, 0][data["t"] >= t_shut * DAY - 1e-6]
        drs = f", min ΔR_s(r_w) на останове {np.min(np.diff(rs0)):+.3e}"
    out(f"  {name}: {res}, {wall:.1f} с, записей {len(h.states)}, вызовов гидро {len(calls)}, "
        f"отказов {len(msgs)}, якобианов {patch.n_jac} (+{patch.n_jac_extra} варианта), "
        f"приёмов по полу {len(patch.events)}, пол не помог {patch.rejects}{drs}")
    if patch.events:
        out("    где        dt, с      мера       предел(J)  предел(Jz)  kappa(J) kappa(Jz) строки")
        for where, dt, meas, flo, flo_z, k, kz, rows in patch.events[:30]:
            out(f"    {where:<10} {dt:<10.4g} {meas:.3e}  {flo:.3e}  {flo_z:.3e}   {k:.2f}     {kz:.2f}     {rows}")
        if len(patch.events) > 30:
            out(f"    … ещё {len(patch.events) - 30}")
        k = np.array([e[5] for e in patch.events])
        r = np.array([e[3] / e[4] for e in patch.events])
        out(f"    kappa(J): max {k.max():.2f}; предел(J)/предел(Jz): min {r.min():.3f}, max {r.max():.3f}")


def compare(variants, out):
    for name in list(SCENARIOS) + list(EXTRA):
        f0 = HERE / f"hist_{name}_base.npz"
        if not f0.exists():
            continue
        a = np.load(f0)
        out(f"\n{name}: base — вызовов {len(a['calls'])}, отказов {len(a['msgs'])}, "
            f"якобианов {int(a['n_jac'][0])}")
        for v in variants:
            fv = HERE / f"hist_{name}_{v}.npz"
            if not fv.exists():
                continue
            b = np.load(fv)
            same = all(np.array_equal(a[f], b[f]) for f in ("p", "Sg", "Rs", "T", "regime", "t"))
            line = (f"  {v:<3}: вызовов {len(b['calls'])}, отказов {len(b['msgs'])}, якобианов "
                    f"{int(b['n_jac'][0])}+{int(b['n_jac'][1])}, приёмов по полу {len(b['events'])}; ")
            if same:
                line += "история побитово"
            elif a["t"].shape == b["t"].shape and np.array_equal(a["t"], b["t"]):
                d = {f: float(np.max(np.abs(a[f] - b[f]))) for f in ("p", "Sg", "Rs", "T")}
                line += (f"max|Δ|: p {d['p'] / 1e5:.2e} бар, S_g {d['Sg']:.2e}, R_s {d['Rs']:.2e}, "
                         f"T {d['T']:.2e} К; режим {'тот же' if np.array_equal(a['regime'], b['regime']) else 'ДРУГОЙ'}")
            else:
                line += "моменты записей разные"
            out(line)


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["run"]:
        variant = sys.argv[2]
        # «extra» — все примеры, которых нет в SCENARIOS
        names = list(EXTRA) if sys.argv[3:] == ["extra"] else (sys.argv[3:] or list(SCENARIOS))
        # выбранные сценарии — в отдельный файл, полный прогон не затирается
        tail = "_" + "_".join(sys.argv[3:]) if sys.argv[3:] else ""
        fh = open(HERE / f"variants_{variant}{tail}.out.txt", "w", encoding="utf-8")

        def out(*a):
            line = " ".join(str(x) for x in a)
            print(line, flush=True)
            fh.write(line + "\n")
            fh.flush()

        out(f"SOLVER = {SOLVER}")
        out(f"Код: {_factory.__file__}")
        out(f"Прототип: {radial_blackoil.__file__}")
        out(f"Вариант {variant}, KAPPA = {KAPPA}")
        for name in names:
            run(name, variant, out)
    elif cmd == ["same"]:
        # побитовая сверка двух прогонов по всем сценариям, где есть оба
        va, vb = sys.argv[2], sys.argv[3]
        fh = open(HERE / f"variants_same_{va}_{vb}.out.txt", "w", encoding="utf-8")
        ok = True
        for name in list(SCENARIOS) + list(EXTRA):
            fa, fb = HERE / f"hist_{name}_{va}.npz", HERE / f"hist_{name}_{vb}.npz"
            if not (fa.exists() and fb.exists()):
                continue
            a, b = np.load(fa), np.load(fb)
            same = {f: np.array_equal(a[f], b[f]) for f in ("p", "Sg", "Rs", "T", "regime", "t", "calls")}
            ok &= all(same.values())
            line = (f"{name}: {'побитово' if all(same.values()) else 'РАЗЛИЧИЕ ' + str(same)}; "
                    f"вызовов {len(a['calls'])} / {len(b['calls'])}, приёмов по полу "
                    f"{len(a['events'])} / {len(b['events'])}")
            print(line)
            fh.write(line + "\n")
        print("ИТОГ:", "OK" if ok else "РАСХОЖДЕНИЕ")
        fh.write(f"ИТОГ: {'OK' if ok else 'РАСХОЖДЕНИЕ'}\n")
    elif cmd == ["compare"]:
        fh = open(HERE / "variants_compare.out.txt", "w", encoding="utf-8")

        def out(*a):
            line = " ".join(str(x) for x in a)
            print(line, flush=True)
            fh.write(line + "\n")

        out(f"KAPPA = {KAPPA}")
        compare(sys.argv[2:] or ["a", "a1", "v"], out)
    else:
        sys.exit(__doc__)
