"""BUG-027: кондуктивная проводимость грани — запись документа против кода.

Три формы Q^T_{j+1/2} [Вт/К] на сетках примеров:
  старая  — problem_statement.tex до BUG-027 (eq:heat_cond_disc + среднее
            под ним без нормировки весов): 2πh/ln · (w_L/λ_L + w_R/λ_R)^{-1};
  новая   — после BUG-027 (веса нормированы, eq:face_interp):
            2πh/ln · ln·(w_L/λ_L + w_R/λ_R)^{-1};
  код     — TridiagEnergySolver.compute_conductive_transmissibility:
            2πh/(w_L/λ_L + w_R/λ_R) — последовательные сопротивления, точное
            стационарное решение для кусочно-постоянной λ в двух слоях кольца.
Здесь ln = ln(r_{j+1}/r_j) между центрами, w_L + w_R = ln.

Ожидание: старая/код = 1/ln(r_{j+1}/r_j) (поток документа завышен);
новая/код = 1 до округления; среднее новой формы при однородном λ равно λ.

Запуск из каталога numerical_solver/ (основного или worktree):
    .venv\\Scripts\\python <путь к пробе>
"""
import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного или worktree), cwd = {SOLVER}")
sys.path.insert(0, str(SOLVER))

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver  # noqa: E402
from gpn_multiphase_solver.grid.log_radial import LogRadialGrid  # noqa: E402

print(f"Код: {gpn_multiphase_solver.__file__}")

# (подпись, r_w, R_ext, h, N): сетка примера 14 и сетка test_grid.py
GRIDS = [
    ("пример 14", 0.1, 200.0, 10.0, 350),
    ("test_grid", 0.1, 500.0, 10.0, 50),
]

for name, r_w, R_ext, h, N in GRIDS:
    grid = LogRadialGrid(r_w, R_ext, h, N, 1e-13)
    w_L = grid.log_weights_left       # ln(r_{j+1/2}/r_j)      [N-1]
    w_R = grid.log_weights_right      # ln(r_{j+1}/r_{j+1/2})  [N-1]
    ln_c = np.log(grid.r_centers[1:] / grid.r_centers[:-1])
    print(f"\n{name}: N = {N}, R_ext = {R_ext} м, "
          f"ln(r_(j+1)/r_j) = {ln_c.min():.6g}…{ln_c.max():.6g}, "
          f"max|w_L + w_R − ln| = {np.abs(w_L + w_R - ln_c).max():.1e}")

    # Однородная λ и ступенька λ (контраст 4: порода с разной насыщенностью)
    cases = {
        "однородная λ = 1.228": np.full(N, 1.228),
        "ступенька 1.228 | 0.3": np.where(np.arange(N) < N // 2, 1.228, 0.3),
    }
    for label, lam in cases.items():
        lam_L, lam_R = lam[:-1], lam[1:]
        R_sum = w_L / lam_L + w_R / lam_R
        # compute_conductive_transmissibility читает только сетку
        Q_code, _ = TridiagEnergySolver(grid, None, None) \
            .compute_conductive_transmissibility(lam, N)
        Q_old = 2.0 * np.pi * h / ln_c * (1.0 / R_sum)
        lam_new = ln_c / R_sum                         # среднее по eq:face_interp
        Q_new = 2.0 * np.pi * h / ln_c * lam_new
        print(f"  {label}:")
        print(f"    старая/код  = {(Q_old / Q_code).min():.6g}…"
              f"{(Q_old / Q_code).max():.6g}   (1/ln = {(1 / ln_c).max():.6g})")
        print(f"    |новая/код − 1| ≤ {np.abs(Q_new / Q_code - 1).max():.1e}")
        # Выход среднего за [min λ, max λ], относительный. Не ноль даже у верной
        # формы: ln_c считается из центров, w_L + w_R — из граней, расхождение
        # ~1e-16 абсолютное, при ln = 0.02 это ~1e-14 относительное. Отсюда
        # допуск 1e-12 в тестах, а не 1e-15.
        excess_new = np.maximum(np.minimum(lam_L, lam_R) - lam_new,
                                lam_new - np.maximum(lam_L, lam_R)) / lam_new
        excess_old = (1.0 / R_sum) / np.maximum(lam_L, lam_R) - 1.0
        print(f"    выход среднего за [λ_min, λ_max]: новая ≤ {excess_new.max():.1e}"
              f" (допуск 1e-12: {bool(excess_new.max() <= 1e-12)}); "
              f"старая — больше λ_max на {excess_old.min():.3g}…{excess_old.max():.3g}")
