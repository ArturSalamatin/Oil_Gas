"""BUG-024: примеры с вариантом обновления R_s в ступени 4 (stage4_variants.py) — отпечатки, ступени, истории.

Режимы (из numerical_solver; дерево кода — каталог, откуда запущено, его путь печатается):
  run <вариант|code> [имя ...]   — примеры (по умолчанию все): отпечаток истории, время, какая ступень
                                   решала шаги (0 — отказ), якобианов ступени 4; история — в
                                   hist_<имя>_<вариант>.npz рядом со скриптом (в git не идут);
  compare <вариант A> <вариант B> [имя ...] — наибольшие отличия p, T, S_g, R_s, q_o историй
                                   (вариант с суффиксом — как в именах файлов, например code_branch).
BUG024_TAG — суффикс имён вывода и историй (прогон ветки: BUG024_TAG=_branch).
Профиль ступеней и отпечаток — как в vault/issues/debt-048/probes/stage_memory.py (копия: та проба
в git не входит). Вывод — в stdout и в examples_<режим>_<...>.out.txt рядом со скриптом.
    .venv\\Scripts\\python ..\\vault\\issues\\bug-024\\probes\\examples_variant.py run satrel
"""

import hashlib
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = Path.cwd().resolve()
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3", HERE):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import stage4_variants              # noqa: E402

BAR = 1e5
# суффикс файлов вывода и историй — чтобы прогон ветки не перезаписал замер базы
TAG = __import__("os").environ.get("BUG024_TAG", "")


class Tee:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def __call__(self, *a):
        line = " ".join(str(x) for x in a)
        print(line, flush=True)
        self.f.write(line + "\n")
        self.f.flush()


def fingerprint(history):
    """sha256 истории: p, T, S_g, R_s всех записей, времена и q_o (как stage_memory.fingerprint)."""
    h = hashlib.sha256()
    for s in history.states:
        for a in (s.p, s.T, s.Sg, s.Rs):
            h.update(np.ascontiguousarray(a, dtype=float).tobytes())
    h.update(np.asarray(history.times, float).tobytes())
    h.update(np.asarray([w.q_o_std for w in history.well_data], float).tobytes())
    return h.hexdigest()[:16]


def save_history(history, path):
    np.savez(path,
             p=np.array([s.p for s in history.states]), T=np.array([s.T for s in history.states]),
             Sg=np.array([s.Sg for s in history.states]), Rs=np.array([s.Rs for s in history.states]),
             t=np.asarray(history.times, float),
             q_o=np.array([w.q_o_std for w in history.well_data], float))


def run(args):
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config
    import gpn_multiphase_solver
    import radial_blackoil
    variant = args[0]
    names = args[1:] or sorted(p.parent.name for p in (SOLVER / "examples").glob("*/config.json"))
    tag = names[0] if len(names) == 1 else "all"
    out = Tee(HERE / f"examples_run_{tag}_{variant}{TAG}.out.txt")
    out(f"    код: {Path(gpn_multiphase_solver.__file__).parent}, {Path(radial_blackoil.__file__).parent}")
    for name in names:
        cfg = load_config(SOLVER / "examples" / name / "config.json")
        cfg.output.log_level = "ERROR"
        sim, init = SimulatorFactory.from_config(cfg)
        model = sim._hydro._model
        if variant != "code":
            stage4_variants.install(model, variant)
        jac4 = [0]
        base_jac = model.finite_difference_jacobian

        def jac(*a, _b=base_jac, _m=model, **kw):
            if _m._phase_switching:
                jac4[0] += 1
            return _b(*a, **kw)

        model.finite_difference_jacobian = jac
        # ступень, решившая шаг advance (0 — отказ), по флагам отчёта
        steps = []
        base_adv = model.advance

        def advance(state_old, dt_s, *a, _b=base_adv, **kw):
            new, rep = _b(state_old, dt_s, *a, **kw)
            st = 0
            if rep.converged:
                st = 4 if rep.phase_switching else 3 if rep.globalized else 2 if rep.fallback else 1
            steps.append(st)
            return new, rep

        model.advance = advance
        t0 = time.perf_counter()
        try:
            hist = sim.run(init)
            fp = fingerprint(hist)
            save_history(hist, HERE / f"hist_{name}_{variant}{TAG}.npz")
        except RuntimeError as e:
            fp = f"✗ {str(e)[:100]}"
        wall = time.perf_counter() - t0
        by = Counter(steps)
        out(f"{name:<28} {wall:6.1f} с  отпечаток {fp}  ступени {dict(sorted(by.items()))}  "
            f"якобианов ступени 4 {jac4[0]}")


def compare(args):
    va, vb = args[0], args[1]
    names = args[2:] or sorted(p.name[5:-len(va) - 5] for p in HERE.glob(f"hist_*_{va}.npz"))
    out = Tee(HERE / f"examples_compare_{va}_{vb}.out.txt")
    for name in names:
        fa, fb = HERE / f"hist_{name}_{va}.npz", HERE / f"hist_{name}_{vb}.npz"
        if not (fa.exists() and fb.exists()):
            out(f"{name}: нет истории")
            continue
        a, b = np.load(fa), np.load(fb)
        if a["p"].shape != b["p"].shape:
            out(f"{name}: разные размеры историй")
            continue
        parts = []
        for key, unit, scale in (("p", "бар", BAR), ("T", "К", 1.0), ("Sg", "", 1.0), ("Rs", "", 1.0)):
            d = np.abs(a[key] - b[key]) / scale
            n, j = np.unravel_index(int(np.argmax(d)), d.shape)
            parts.append(f"{key} {d.max():.2e}{unit} (зап.{n}, яч.{j})")
        dq = np.max(np.abs(a["q_o"] - b["q_o"]))
        same = all(np.array_equal(a[k], b[k]) for k in ("p", "T", "Sg", "Rs", "t", "q_o"))
        out(f"{name:<28} {'побитово' if same else '; '.join(parts) + f'; q_o {dq:.2e}'}; "
            f"T(r_w) конец {a['T'][-1, 0]:.5f} / {b['T'][-1, 0]:.5f} К; "
            f"p(r_w) конец {a['p'][-1, 0] / BAR:.4f} / {b['p'][-1, 0] / BAR:.4f} бар")


if __name__ == "__main__":
    {"run": run, "compare": compare}[sys.argv[1]](sys.argv[2:])
