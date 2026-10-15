"""DEBT-058 (/issue): сколько отказов гидродинамики на останове и каких — замер на текущем коде.

Код решателя не меняется: проба оборачивает на экземпляре Simulator метод _advance (начало
шага dt) и solve гидродинамики (одна попытка подшага). Попытка относится к одному виду:
  first  — первая попытка шага dt (подшаг dt или dt/2**depth после смены управления, FEAT-032);
  growth — попытка после удачи с удвоенным подшагом (рост G1a, DEBT-015) — предмет DEBT-058;
  same   — попытка после удачи с тем же подшагом (рост запрещён выравниванием);
  split  — повтор после отказа с подшагом вдвое меньше.
Участок: «останов» — управление по дебиту нефти с q_oil = 0, иначе «добыча».

Режимы (запуск из numerical_solver/, P — путь к скрипту):
    .venv\\Scripts\\python P e2e <пример 19|20|21> <n_prod> <n_shut> <dt_integration>
        n_prod суток добычи при p_wf примера, затем n_shut суток останова (q_oil = 0,
        min_bhp = 1 атм) — сценарий B проб DEBT-048 (vault/issues/debt-048/probes/stage_memory.py)
    .venv\\Scripts\\python P example <имя примера>
        пример как есть (16_well_shut_in, 17_shut_in_strong_cooling)
Вывод — в stdout и в файл рядом со скриптом (<режим>_<параметры>.out.txt, UTF-8).
"""

import copy
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
# Код решателя и прототипа — из каталога запуска (основной или worktree)
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
import radial_blackoil  # noqa: E402
from gpn_multiphase_solver.bc import RateControl  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.hydro.base import HydroConvergenceError  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

HERE = Path(__file__).resolve().parent
DAY = 86400.0
BASES = {"19": "19_rs150_cooling", "20": "20_rs300_cooling", "21": "21_rs100_cooling"}
KINDS = ("first", "growth", "same", "split")


class Tee:
    """Печать в stdout и в файл UTF-8."""

    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def __call__(self, s=""):
        print(s)
        self.f.write(s + "\n")
        self.f.flush()


def period(bc):
    """Останов — управление по дебиту нефти с нулевым дебитом."""
    shut = isinstance(bc.well, RateControl) and bc.well.q_oil == 0.0
    return "останов" if shut else "добыча"


def instrument(sim):
    """Обёртки _advance и solve на экземпляре; возвращает журнал попыток."""
    log = []                       # (участок, вид, h, сошлось, время, номер шага dt)
    ctx = {"new": False, "prev": None, "step": -1}
    orig_adv, orig_solve = sim._advance, sim._hydro.solve

    def adv(state, dt, bc, balance, mass, depth=0):
        ctx["new"], ctx["prev"] = True, None
        ctx["step"] += 1
        return orig_adv(state, dt, bc, balance, mass, depth)

    def solve(state, h, bc):
        if ctx["new"]:
            kind = "first"
        elif not ctx["prev"][1]:
            kind = "split"
        elif h > ctx["prev"][0]:
            kind = "growth"
        else:
            kind = "same"
        ctx["new"] = False
        t0 = time.perf_counter()
        ok = False
        try:
            res = orig_solve(state, h, bc)
            ok = True
            return res
        except HydroConvergenceError:
            raise
        finally:
            log.append((period(bc), kind, h, ok, time.perf_counter() - t0, ctx["step"]))
            ctx["prev"] = (h, ok)

    sim._advance = adv
    sim._hydro.solve = solve
    return log


def report(out, log, per):
    rows = [r for r in log if r[0] == per]
    if not rows:
        return
    n, nf = len(rows), sum(not r[3] for r in rows)
    t_all, t_fail = sum(r[4] for r in rows), sum(r[4] for r in rows if not r[3])
    steps = {r[5] for r in rows}
    split_steps = {r[5] for r in rows if not r[3]}
    out(f"  [{per}] попыток solve {n}, отказов {nf} ({100 * nf / n:.0f} %); "
        f"время solve {t_all:.1f} с, из них на отказы {t_fail:.1f} с ({100 * t_fail / max(t_all, 1e-12):.0f} %); "
        f"шагов dt {len(steps)}, из них с дроблением {len(split_steps)}")
    by = defaultdict(lambda: [0, 0, 0.0])
    for r in rows:
        b = by[r[1]]
        b[0] += 1
        b[1] += (not r[3])
        b[2] += r[4] if not r[3] else 0.0
    out("    вид    | попыток | отказов | время отказов, с")
    for k in KINDS:
        if k in by:
            out(f"    {k:<6} | {by[k][0]:7d} | {by[k][1]:7d} | {by[k][2]:8.1f}")
    acc = Counter(f"{r[2]:.4g}" for r in rows if r[3])
    out(f"    принятые подшаги, с: {dict(sorted(acc.items(), key=lambda kv: -float(kv[0])))}")
    fails = Counter((r[1], f"{r[2]:.4g}") for r in rows if not r[3])
    out(f"    отказы (вид, подшаг с): {dict(sorted(fails.items(), key=lambda kv: (kv[0][0], -float(kv[0][1]))))}")


def run(cfg, title, out):
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    log = instrument(sim)
    out(f"код: {Path(gpn_multiphase_solver.__file__).parent}, {Path(radial_blackoil.__file__).parent}")
    out(f"=== {title}; dt_integration = {cfg.time.dt_integration:.0f} с, "
        f"max_retries = {cfg.numerics.max_retries}, "
        f"dt_after_control_change = {cfg.time.dt_after_control_change} ===")
    t0 = time.perf_counter()
    try:
        sim.run(init)
        status = "✓"
    except RuntimeError as e:
        status = f"✗ {str(e)[:300]}"
    out(f"итог: {status}; счёт {time.perf_counter() - t0:.0f} с")
    for per in ("добыча", "останов"):
        report(out, log, per)


def run_e2e(args):
    base, n_prod, n_shut, dt_int = args
    n_prod, n_shut, dt_int = int(n_prod), int(n_shut), float(dt_int)
    out = Tee(HERE / f"e2e_{base}B_{n_prod}_{n_shut}_{dt_int:.0f}.out.txt")
    cfg = load_config(SOLVER / "examples" / BASES[base] / "config.json")
    iv = cfg.time.history[0]
    hist = []
    for _ in range(n_prod):
        x = copy.deepcopy(iv); x.dt = DAY; hist.append(x)
    for _ in range(n_shut):
        x = copy.deepcopy(iv); x.dt = DAY
        x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    cfg.time.dt_integration = dt_int
    run(cfg, f"{BASES[base]}: {n_prod} сут добычи + {n_shut} сут останова (B)", out)


def run_example(args):
    name = args[0]
    out = Tee(HERE / f"example_{name}.out.txt")
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    run(cfg, name, out)


if __name__ == "__main__":
    {"e2e": run_e2e, "example": run_example}[sys.argv[1]](sys.argv[2:])
