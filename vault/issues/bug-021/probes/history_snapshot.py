"""BUG-021: побитовое сравнение историй примеров GPN до и после исправления Ньютона.

Копия скрипта DEBT-033 (vault/issues/debt-033/probes/history_snapshot.py): сохраняет p, Sg, Rs, T,
regime, t, G_o, G_g каждой записи и время счёта. Флаг --variant N подменяет
_newton_fixed_active_set вариантом N из planned_code.py (1 или 2) — для проверки при
планировании; при реализации не нужен (код уже исправлен).

Запуск — из каталога numerical_solver, код которого считается (основного или worktree):
    .venv\\Scripts\\python <P>\\history_snapshot.py save base [пример ...]
    .venv\\Scripts\\python <P>\\history_snapshot.py --variant 2 save v2 [пример ...]
    .venv\\Scripts\\python <P>\\history_snapshot.py compare base v2
Без списка примеров — все каталоги examples/*/ с config.json.
"""
import logging
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))
logging.disable(logging.INFO)

FIELDS = ("p", "Sg", "Rs", "T", "regime")


def all_examples():
    return sorted(d.name for d in (SOLVER_ROOT / "examples").iterdir() if (d / "config.json").is_file())


def save(tag, examples):
    import gpn_multiphase_solver
    import radial_blackoil
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config
    print("код:", Path(radial_blackoil.__file__).parent, "|", Path(gpn_multiphase_solver.__file__).parent, flush=True)
    out = HERE / f"history_{tag}"
    out.mkdir(exist_ok=True)
    for ex in examples:
        cfg = load_config(SOLVER_ROOT / "examples" / ex / "config.json")
        sim, s0 = SimulatorFactory.from_config(cfg)
        t = time.perf_counter()
        h = sim.run(s0)
        wall = time.perf_counter() - t
        arrays = {f: np.array([getattr(s, f) for s in h.states]) for f in FIELDS}
        arrays["t"] = np.array(h.times, float)
        for k in ("G_o", "G_g"):
            arrays[k] = np.array([getattr(r, k) for r in h.hydro_results[1:]])
        arrays["wall"] = np.array(wall)
        np.savez(out / f"{ex}.npz", **arrays)
        print(f"{ex}: {h.n_saved} записей, {wall:.1f} с", flush=True)


def compare(tag_a, tag_b):
    da, db = HERE / f"history_{tag_a}", HERE / f"history_{tag_b}"
    bad = 0; wa = wb = 0.0
    for fa in sorted(da.glob("*.npz")):
        fb = db / fa.name
        if not fb.is_file():
            print(f"{fa.stem}: нет в {tag_b}"); bad += 1
            continue
        a, b = np.load(fa), np.load(fb)
        wa += float(a["wall"]); wb += float(b["wall"])
        keys = [k for k in a.files if k != "wall"]
        diff = [k for k in keys if a[k].shape != b[k].shape or not np.array_equal(a[k], b[k])]
        tw = f"время {float(a['wall']):.1f} → {float(b['wall']):.1f} с"
        if diff:
            bad += 1
            worst = {k: float(np.max(np.abs(a[k] - b[k]))) for k in diff if a[k].shape == b[k].shape}
            print(f"{fa.stem}: РАЗЛИЧИЕ в {diff}; max|Δ| {worst}; {tw}")
        else:
            print(f"{fa.stem}: побитово; {tw}")
    print(f"итого: различий {bad}; время {wa:.1f} → {wb:.1f} с")


if __name__ == "__main__":
    if "--variant" in sys.argv:
        i = sys.argv.index("--variant"); v = int(sys.argv[i + 1]); del sys.argv[i:i + 2]
        sys.path.insert(0, str(HERE))
        import planned_code
        planned_code.apply(v)
        print(f"код подменён: вариант {v}", flush=True)
    cmd = sys.argv[1]
    if cmd == "save":
        save(sys.argv[2], sys.argv[3:] or all_examples())
    elif cmd == "compare":
        compare(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit("использование: [--variant N] save <метка> [пример ...] | compare <метка_a> <метка_b>")
