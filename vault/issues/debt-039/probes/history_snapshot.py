"""DEBT-039 (по пробе DEBT-036): побитовое сравнение историй примеров до и после реализации.

Запуск — из каталога numerical_solver, код которого считается (основного или worktree);
P = d:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\vault\\issues\\debt-039\\probes\\history_snapshot.py:
    .venv\\Scripts\\python P save base   [пример ...]     # до шага 2 плана
    .venv\\Scripts\\python P save new    [пример ...]     # после шага 5
    .venv\\Scripts\\python P compare base new

save — считает примеры через SimulatorFactory.from_config + Simulator.run и сохраняет
p, Sg, Rs, T, regime, t, G_o, G_g, G_free_gas каждой записи, данные скважины и члены
баланса энергии в history_<метка>/<пример>.npz рядом со скриптом. compare —
np.array_equal по всем массивам, которые есть в обоих снимках (баланс массы есть
только в new — он не сравнивается, а печатается: max отн. невязки по записям).
Без списка примеров — все каталоги examples/*/ с config.json (~4 мин).
"""
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(SOLVER_ROOT))

FIELDS = ("p", "Sg", "Rs", "T", "regime")
FLUXES = ("G_o", "G_g", "G_free_gas")
WELL = ("q_o_std", "q_g_std", "m_o_well", "m_g_well", "p_wf", "T_wf")
ENERGY = ("delta_E", "cum_adiab", "cum_conv", "cum_jt", "cum_deg", "cum_cond")
MASS = ("M_o", "M_g", "cum_o_well", "cum_o_ext", "cum_g_well", "cum_g_ext")


def all_examples():
    return sorted(d.name for d in (SOLVER_ROOT / "examples").iterdir()
                  if (d / "config.json").is_file())


def save(tag, examples):
    if not (SOLVER_ROOT / "gpn_multiphase_solver").is_dir():
        raise SystemExit("запускать из каталога numerical_solver (основного или worktree)")
    import gpn_multiphase_solver
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config
    print("код:", Path(gpn_multiphase_solver.__file__).parent)
    out = HERE / f"history_{tag}"
    out.mkdir(exist_ok=True)
    for ex in examples:
        cfg = load_config(SOLVER_ROOT / "examples" / ex / "config.json")
        cfg.output.log_level = "WARNING"
        sim, s0 = SimulatorFactory.from_config(cfg)
        t = time.perf_counter()
        h = sim.run(s0)
        wall = time.perf_counter() - t
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
        print(f"{ex}: {h.n_saved} записей, {wall:.1f} с", flush=True)


def _rel_mass(b, a):
    """max по записям |dM + cum_ext - cum_well| / (|dM| + |cum_well| + |cum_ext|)."""
    dM = b[f"mass_M_{a}"] - b[f"mass_M_{a}"][0]
    w, e = b[f"mass_cum_{a}_well"], b[f"mass_cum_{a}_ext"]
    s = np.abs(dM) + np.abs(w) + np.abs(e)
    return float(np.max(np.abs(dM + e - w) / np.where(s > 0, s, 1.0)))


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
        common = [k for k in a.files if k in b.files]
        diff = [k for k in common if a[k].shape != b[k].shape or not np.array_equal(a[k], b[k])]
        mass = (f"; баланс массы: нефть {_rel_mass(b, 'o'):.2e}, газ {_rel_mass(b, 'g'):.2e}"
                if "mass_M_o" in b.files else "")
        if diff:
            bad += 1
            print(f"{fa.stem}: РАЗЛИЧИЕ в {diff}{mass}")
        else:
            print(f"{fa.stem}: побитово ({len(common)} массивов){mass}")
    print(f"итого: различий {bad}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "save":
        save(sys.argv[2], sys.argv[3:] or all_examples())
    elif cmd == "compare":
        compare(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit("использование: save <метка> [пример ...] | compare <метка_a> <метка_b>")
