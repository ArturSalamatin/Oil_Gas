"""Проба DEBT-057: отпечаток истории T примера 18 штатным кодом пакета — сверка реализации с вариантом B пробы.

Запуск из numerical_solver/ дерева, которое проверяется (в worktree — с PYTHONPATH на него):
    <python> <путь>\\t_fingerprint.py [метка]
Печать: путь пакета, T(r_w) − T0 на записях 1, 11, 20, 22, отпечаток sha256 (16 знаков)
массива T всех записей. phi_energy.py печатает отпечатки base и B тем же способом.
"""
import hashlib
import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
import gpn_multiphase_solver as gms  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

tag = sys.argv[1] if len(sys.argv) > 1 else ""
print("SOLVER =", SOLVER)
print("пакет  =", Path(gms.__file__).parent)
cfg = load_config(SOLVER / "examples" / "18_prototype_input" / "config.json")
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
hist = sim.run(init)
T = np.array([s.T for s in hist.states])
dT = T[:, 0] - cfg.initial_conditions.T0
print(f"[{tag}] T(r_w) − T0: запись 1 {dT[1]:+.5f}, 11 {dT[11]:+.5f}, 20 {dT[20]:+.5f}, 22 {dT[22]:+.5f} К")
print(f"[{tag}] отпечаток T: {hashlib.sha256(np.ascontiguousarray(T).tobytes()).hexdigest()[:16]}")
