"""DEBT-033: побитовое сравнение историй примеров до и после векторизации якобиана.

Запуск — из каталога numerical_solver, код которого считается (основного или worktree);
P = d:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\vault\\issues\\debt-033\\probes\\history_snapshot.py:
    .venv\\Scripts\\python P save base   [пример ...]
    .venv\\Scripts\\python P save new    [пример ...]
    .venv\\Scripts\\python P compare base new

save — считает примеры через SimulatorFactory.from_config + Simulator.run (без записи файлов
примеров) и сохраняет p, Sg, Rs, T, regime, t, G_o, G_g каждой записи истории в
history_<метка>/<пример>.npz рядом со скриптом. compare — np.array_equal по всем массивам.
Без списка примеров — все каталоги examples/*/ с config.json (~4 мин).
Повторный прогон того же кода даёт побитово те же истории (проверено 2026-10-03 на 04, 15).
"""
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
# Код — из каталога запуска: vault/issues/ в .gitignore, в worktree проб нет, их запускают
# по пути основного каталога, а считать надо код worktree
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))

FIELDS = ("p", "Sg", "Rs", "T", "regime")


def all_examples():
    return sorted(d.name for d in (SOLVER_ROOT / "examples").iterdir()
                  if (d / "config.json").is_file())


def save(tag, examples):
    if not (SOLVER_ROOT / "gpn_multiphase_solver").is_dir():
        raise SystemExit("запускать из каталога numerical_solver (основного или worktree)")
    import gpn_multiphase_solver
    import radial_blackoil
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config
    print("код:", Path(radial_blackoil.__file__).parent, "|", Path(gpn_multiphase_solver.__file__).parent)
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
        # Потоки на гранях: первая запись — начальное состояние, у неё гидро-шага может не быть
        arrays["G_o"] = np.array([r.G_o for r in h.hydro_results[1:]])
        arrays["G_g"] = np.array([r.G_g for r in h.hydro_results[1:]])
        np.savez(out / f"{ex}.npz", **arrays)
        print(f"{ex}: {h.n_saved} записей, {wall:.1f} с")


def compare(tag_a, tag_b):
    da, db = HERE / f"history_{tag_a}", HERE / f"history_{tag_b}"
    bad = 0
    for fa in sorted(da.glob("*.npz")):
        fb = db / fa.name
        if not fb.is_file():
            print(f"{fa.stem}: нет в {tag_b}")
            bad += 1
            continue
        a, b = np.load(fa), np.load(fb)
        diff = [k for k in a.files if a[k].shape != b[k].shape or not np.array_equal(a[k], b[k])]
        if diff:
            bad += 1
            worst = {k: float(np.max(np.abs(a[k] - b[k]))) for k in diff if a[k].shape == b[k].shape}
            print(f"{fa.stem}: РАЗЛИЧИЕ в {diff}; max|Δ| {worst}")
        else:
            print(f"{fa.stem}: побитово")
    print(f"итого: различий {bad}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "save":
        save(sys.argv[2], sys.argv[3:] or all_examples())
    elif cmd == "compare":
        compare(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit("использование: save <метка> [пример ...] | compare <метка_a> <метка_b>")
