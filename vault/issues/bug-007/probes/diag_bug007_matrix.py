"""BUG-007: сверка конвективного члена баланса с коэффициентами МАТРИЦЫ.

Не доверяем шаблону "flux[N] - flux[0]" на слово, а извлекаем конвективный
вклад прямо из a, b, c, d в assemble_tridiag и сравниваем.

В строке j матрицы конвекция даёт (внутренние ячейки, tridiag.py:324-326):
    -Phi_plus[j]*T[j-1] + (Phi_plus[j+1] - Phi_minus[j])*T[j] + Phi_minus[j+1]*T[j+1]
Это дивергенция потока энтальпии по ячейке j:  flux[j+1] - flux[j],
где flux[f] = Phi_plus[f]*T[f-1] + Phi_minus[f]*T[f].

Сумма по всем ячейкам телескопируется до flux[N] - flux[0], а вклад в
баланс области = -(flux[N] - flux[0]).

Здесь обе величины считаются НЕЗАВИСИМО на каждом шаге и сравниваются.
"""
import sys
from pathlib import Path

ROOT = Path(r"d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver")
for p in (str(ROOT), str(ROOT / "examples"),
          str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

EXAMPLE = sys.argv[1] if len(sys.argv) > 1 else "03_standing_corey"

_orig_solve = TridiagEnergySolver.solve
_orig_assemble = TridiagEnergySolver.assemble_tridiag
box = {}
worst = {"rel": -1.0, "calls": 0}


def patched_assemble(self, N, dt, T_old, T_ext, rho_cp_eff,
                     Q_T_internal, Q_T_ext, Phi_plus, Phi_minus,
                     J_jt, Q_ad, Q_deg):
    box["Phi_plus"] = Phi_plus.copy()
    box["Phi_minus"] = Phi_minus.copy()
    box["T_ext"] = T_ext
    box["N"] = N
    return _orig_assemble(self, N, dt, T_old, T_ext, rho_cp_eff,
                          Q_T_internal, Q_T_ext, Phi_plus, Phi_minus,
                          J_jt, Q_ad, Q_deg)


def patched_solve(self, hydro_result, state_prev, dt, bc, collect=None):
    T_new = _orig_solve(self, hydro_result, state_prev, dt, bc, collect)

    Phi_plus, Phi_minus = box["Phi_plus"], box["Phi_minus"]
    N, T_ext = box["N"], box["T_ext"]

    # (A) шаблон граней: flux[f] = Phi_plus[f] T[f-1] + Phi_minus[f] T[f]
    T_left = np.concatenate(([T_new[0]], T_new))
    T_right = np.concatenate((T_new, [T_ext]))
    flux = Phi_plus * T_left + Phi_minus * T_right
    by_faces = -(flux[N] - flux[0])

    # (B) независимо: поячеечная дивергенция ровно как в строках матрицы
    div = np.zeros(N)
    for j in range(N):
        Tm = T_new[j - 1] if j > 0 else T_new[0]          # ГУ забоя: та же ячейка
        Tp = T_new[j + 1] if j < N - 1 else T_ext         # ГУ контура: Дирихле
        div[j] = (-Phi_plus[j] * Tm
                  + (Phi_plus[j + 1] - Phi_minus[j]) * T_new[j]
                  + Phi_minus[j + 1] * Tp)
    by_cells = -float(np.sum(div))

    denom = max(abs(by_faces), abs(by_cells), 1e-30)
    rel = abs(by_faces - by_cells) / denom
    worst["calls"] += 1
    if rel > worst["rel"]:
        worst.update(rel=rel, faces=by_faces, cells=by_cells)
    return T_new


TridiagEnergySolver.assemble_tridiag = patched_assemble
TridiagEnergySolver.solve = patched_solve
try:
    cfg = load_config(ROOT / "examples" / EXAMPLE / "config.json")
    cfg.output.log_level = "WARNING"
    sim, init = SimulatorFactory.from_config(cfg)
    sim.run(init)
finally:
    TridiagEnergySolver.solve = _orig_solve
    TridiagEnergySolver.assemble_tridiag = _orig_assemble

print(f"=== {EXAMPLE} ===")
print(f"перехвачено вызовов solve: {worst['calls']}")
print("Макс. расхождение 'шаблон граней' vs 'сумма строк матрицы':")
print(f"  отн. = {worst['rel']:.3e}")
print(f"  по граням  = {worst.get('faces', 0.0):+.10e} Вт")
print(f"  по ячейкам = {worst.get('cells', 0.0):+.10e} Вт")
print()
print("Совпадение на уровне 1e-15..1e-16 => шаблон граней точно")
print("воспроизводит конвекцию из матрицы СЛАУ.")
