"""DEBT-020, /implement: матрица и поле T до и после правки — побитово.

  capture <метка> — снять снимок кода, из которого запущена проба:
      examples: на каждом вызове solve хеш sha256 байтов a, b, c, d (через
                matrix_probe — ровно то, что уходит в прогонку) и все
                записанные поля T истории;
      synth:    a, b, c, d для синтетических входов N = 1, 2, 3, 10 с
                T_ext != 0 и Phi_plus[0] > 0 (ветви, которых нет на рабочем
                пути), λ = 0 в каждом десятом случае.
      Снимок — bits_<метка>.npz рядом со скриптом (*.npz в .gitignore:
      снимки не попадают в коммит).
  compare <a> <b> — сравнить два снимка ПО БАЙТАМ (tobytes различает и знак
      нуля). Печатает первый расходящийся вызов. Код выхода 0 — совпадение.

Сигнатуры до и после правки разные: compute_conductive_transmissibility
возвращала пару (Q_T_internal, Q_T_ext), после — массив Q_T [N+1]. Синтетика
определяет форму по возвращённому значению и подаёт в assemble_tridiag то,
что тот принимает. Входы синтетики одинаковы (фиксированное зерно).

Код берётся из текущего каталога (numerical_solver основного каталога или
worktree) — первая строка вывода называет путь.

Запуск (из <каталог>\\numerical_solver; в worktree интерпретатор основного
каталога по абсолютному пути):
    <python> ..\\vault\\issues\\debt-020\\probes\\bits_capture.py capture base
    <python> ..\\vault\\issues\\debt-020\\probes\\bits_capture.py capture step1
    <python> ..\\vault\\issues\\debt-020\\probes\\bits_capture.py compare base step1
"""

import hashlib
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

# 07 — λ = 0 (Q_T ≡ 0); 10, 11 — λ > 0, дегазация, газ у контура;
# 14 — высокий газовый фактор, охлаждение; 16 — останов (Φ ≈ 0, дробление).
EXAMPLES = [
    "07_degassing_adiabatic_only",
    "10_deep_degassing",
    "11_degassing_at_boundary",
    "14_high_gor_cooling",
    "16_well_shut_in",
]


def _setup_path():
    solver = Path.cwd()
    assert (solver / "gpn_multiphase_solver").is_dir(), \
        f"запускать из numerical_solver, а не из {solver}"
    for p in (solver, solver / "HydroSolverPrototype" / "Prototype_1.0.3"):
        sys.path.insert(0, str(p))
    from gpn_multiphase_solver import factory
    print(f"Код: {factory.__file__}")
    return solver


def _digest(*arrays):
    h = hashlib.sha256()
    for x in arrays:
        h.update(np.ascontiguousarray(x, dtype=float).tobytes())
    return h.hexdigest()


def _synth():
    """Хеши a, b, c, d на синтетических входах — независимо от формы Q_T."""
    from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
    from gpn_multiphase_solver.grid.log_radial import LogRadialGrid

    rng = np.random.default_rng(20261011)
    out = []
    for N in (1, 2, 3, 10):
        grid = LogRadialGrid(0.1, 200.0, 10.0, N, 1e-13)
        solver = TridiagEnergySolver(grid, None, None)
        for trial in range(200):
            lam = rng.uniform(0.2, 3.0, N)
            if trial % 10 == 0:
                lam[:] = 0.0
            Q = solver.compute_conductive_transmissibility(lam, N)
            # До правки — пара, после — массив [N+1]: в сборку уходит как есть
            Q_args = tuple(Q) if isinstance(Q, tuple) else (Q,)
            Phi = rng.normal(0.0, 300.0, N + 1)
            Phi_plus = np.maximum(Phi, 0.0)
            Phi_minus = np.minimum(Phi, 0.0)
            Phi_plus[0] = abs(rng.normal(0.0, 300.0))   # втекание через забой
            dt = rng.uniform(1.0, 86400.0)
            T_old = rng.uniform(300.0, 360.0, N)
            T_ext = rng.uniform(300.0, 360.0)
            rho_cp = rng.uniform(1e6, 3e6, N)
            J, Qad, Qdeg = (rng.normal(0.0, 50.0, N), rng.normal(0.0, 1.0, N),
                            rng.normal(0.0, 1.0, N))
            a, b, c, d = solver.assemble_tridiag(
                N, dt, T_old, T_ext, rho_cp, *Q_args,
                Phi_plus, Phi_minus, J, Qad, Qdeg)
            out.append(_digest(a, b, c, d))
    return out


def capture(tag):
    solver = _setup_path()
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config

    synth = _synth()
    out = {"synth.digests": np.array(synth)}
    print(f"  synth: {len(synth)} случаев")
    for name in EXAMPLES:
        t0 = time.perf_counter()
        cfg = load_config(solver / "examples" / name / "config.json")
        cfg.output.log_level = "ERROR"
        sim, init = SimulatorFactory.from_config(cfg)
        digests = []

        def probe(a, b, c, d, **_):
            digests.append(_digest(a, b, c, d))

        sim._energy.matrix_probe = probe
        hist = sim.run(init)
        out[f"{name}.digests"] = np.array(digests)
        out[f"{name}.T"] = np.array([s.T for s in hist.states])
        print(f"  {name}: вызовов solve {len(digests)}, записей T "
              f"{len(hist.states)}, {time.perf_counter() - t0:.1f} с")

    np.savez(HERE / f"bits_{tag}.npz", **out)
    print(f"сохранено: bits_{tag}.npz")


def compare(a, b):
    A = np.load(HERE / f"bits_{a}.npz")
    B = np.load(HERE / f"bits_{b}.npz")
    ok = True
    for key in ["synth"] + EXAMPLES:
        da, db = list(A[f"{key}.digests"]), list(B[f"{key}.digests"])
        bad = next((i for i, (x, y) in enumerate(zip(da, db)) if x != y), None)
        same = len(da) == len(db) and bad is None
        line = f"  {key}: вызовов {len(da)} / {len(db)}, матрица " + (
            "побитово" if same else f"РАСХОДИТСЯ (первый вызов {bad})")
        if key != "synth":
            TA, TB = A[f"{key}.T"], B[f"{key}.T"]
            t_same = TA.shape == TB.shape and TA.tobytes() == TB.tobytes()
            line += ", T " + ("побитово" if t_same else "РАСХОДИТСЯ")
            same &= t_same
        ok &= same
        print(line)
    print("ИТОГ:", "OK" if ok else "ПРОВАЛ")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if sys.argv[1] == "capture":
        capture(sys.argv[2])
    else:
        compare(sys.argv[2], sys.argv[3])
