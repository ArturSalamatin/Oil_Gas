"""Раунд 2 аудита BUG-012: исполним ли блок кода шага 8а как написан.

Фокус раунда — реализуемость. Проверяется НЕ физика (это раунд 1), а то,
что приведённый в плане блок:
  1. исполняется без исключений на реальных данных решателя;
  2. даёт массив нужной формы [N] и размерности;
  3. корректно обрабатывает N = 1 и N = 2 (в плане — три ветки `if N > 1`);
  4. обращается в ноль при Rs = const (утверждение п. 5 шага 8а);
  5. не теряет DEBT-009: на контурной грани при притоке берётся Rs_ext.

Блок скопирован из плана ДОСЛОВНО, чтобы поймать опечатки в нём самом,
а не в моей переформулировке.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python ..\\vault\\issues\\bug-012\\probes\\probe_degassing_advective.py
"""

import sys
from pathlib import Path

import numpy as np

_SOLVER = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(_SOLVER))

from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.io.config import RockConfig
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver

R_WELL, R_EXT, H, K_PERM, PHI = 0.1, 50.0, 10.0, 1e-13, 0.2
P0, T0, RS0 = 20e6, 350.0, 50.0
RHO_O_STD, RHO_G_STD, DT = 850.0, 0.85, 3600.0


def _solver(N):
    grid = LogRadialGrid(R_WELL, R_EXT, H, N, K_PERM)
    pvt = StandingFullPVT(
        rho_o_std=RHO_O_STD, rho_g_std=RHO_G_STD, T0=T0, Rs0=RS0,
        co_undersaturated=0.0, c_p_oil=2000.0, c_p_gas=1000.0,
        mu_JT_oil_val=0.0, mu_JT_gas_val=0.0, L_degas_val=1e5)
    rock = RockConfig(porosity=PHI, permeability=K_PERM, rho_cp_solid=1.25e6,
                      lambda_solid=1.5, lambda_oil=0.14, lambda_gas=0.04)
    return TridiagEnergySolver(grid, pvt, rock)


def plan_block(solver, N, Rs, G_o, Rs_ext):
    """Блок из шага 8а плана, ДОСЛОВНО. Возвращает mdot_conv [N]."""
    V = solver._grid.volumes
    rho_g_std = solver._pvt.rho_g_std

    # ── начало блока плана ──
    Gp = np.maximum(G_o, 0.0)
    Gm = np.minimum(G_o, 0.0)
    Rs_left = np.r_[Rs[0], Rs[:-1]]
    Rs_right = np.r_[Rs[1:], Rs_ext]
    adv = Gp[0:N] * (Rs - Rs_left) + Gm[1:N + 1] * (Rs_right - Rs)
    adv[0] = Gm[1] * (Rs_right[0] - Rs[0])
    mdot_conv = -rho_g_std * adv / V
    # ── конец блока плана ──
    return mdot_conv


def case(label, N, Rs, G_o, Rs_ext):
    solver = _solver(N)
    print(f"\n--- {label}  (N={N}) ---")
    try:
        res = plan_block(solver, N, Rs, G_o, Rs_ext)
    except Exception as e:
        print(f"  ❌ ИСКЛЮЧЕНИЕ: {type(e).__name__}: {e}")
        return None
    print(f"  форма: {res.shape}  (ожидается ({N},))  "
          f"{'OK' if res.shape == (N,) else '❌ НЕВЕРНО'}")
    print(f"  max|mdot_conv| = {np.max(np.abs(res)):.6e}")
    print(f"  конечные значения: {np.all(np.isfinite(res))}")
    return res


if __name__ == "__main__":
    print("=" * 70)
    print("Раунд 2: исполнимость блока шага 8а")
    print("=" * 70)

    # 1. Типовой случай: N=10, поток к скважине, Rs растёт к контуру
    N = 10
    Rs = np.linspace(20.0, 50.0, N)
    G_o = np.full(N + 1, -5.0e-3)          # всюду к скважине
    case("типовой, поток к скважине", N, Rs, G_o, RS0)

    # 2. Rs = const — член ОБЯЗАН быть нулём (п. 5 шага 8а)
    Rs_c = np.full(N, RS0)
    r = case("Rs = const (ожидается ноль)", N, Rs_c, G_o, RS0)
    if r is not None:
        ok = np.max(np.abs(r)) < 1e-30
        print(f"  ноль? {'OK' if ok else '❌ НЕ НОЛЬ — утверждение п.5 неверно'}")

    # 3. Отток наружу (G_o > 0) — ветка Gp, в конфигах не встречается
    case("отток наружу (G_o > 0)", N, Rs, np.full(N + 1, 5.0e-3), RS0)

    # 4. Две ячейки
    case("две ячейки", 2, np.array([20.0, 40.0]),
         np.full(3, -5.0e-3), RS0)

    # 5. ОДНА ячейка — критический случай
    case("одна ячейка", 1, np.array([30.0]), np.full(2, -5.0e-3), RS0)

    # 6. DEBT-009: меняем только Rs_ext — результат ДОЛЖЕН измениться
    print("\n--- DEBT-009: влияет ли Rs_ext на результат ---")
    s = _solver(N)
    a = plan_block(s, N, Rs, G_o, RS0)
    b = plan_block(s, N, Rs, G_o, RS0 * 2)
    d = np.max(np.abs(a - b))
    print(f"  max|разн| при Rs_ext ×2 = {d:.6e}")
    print(f"  {'OK — состав ГУ учитывается' if d > 0 else '❌ Rs_ext игнорируется — DEBT-009 потерян'}")
    print(f"  затронутые ячейки: {np.nonzero(np.abs(a - b) > 0)[0]}")
