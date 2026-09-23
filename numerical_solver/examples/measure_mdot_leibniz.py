"""Какой вариант B_o воспроизводит дискретное правило Лейбница (BUG-012).

ОТКУДА БЕРЁТСЯ mdot. Выражение eq:main_mdot получается вычитанием
R_s·(баланс нефти) из баланса газового компонента:

    d/dt[phi·Rs(1-Sg)/Bo] - Rs·d/dt[phi·(1-Sg)/Bo] = phi·(1-Sg)/Bo · dRs/dt
    div[Rs·u_o/Bo]        - Rs·div[u_o/Bo]         = (u_o/Bo)·grad Rs

Обе строки — правило Лейбница, и в обеих величины u_o/Bo и (1-Sg)/Bo
входят КАК ЕДИНОЕ ЦЕЛОЕ. Проинтегрированная по грани величина u_o/Bo —
это в точности G^o, поток нефтяного КОМПОНЕНТА (eq:flux_oil), в котором
Bo уже взят из ячейки выше по потоку (fluxes.py:86).

ЧТО ПРОВЕРЯЕТСЯ. Дискретный аналог второй строки:

    div_дискр[G^o·Rs]_j - Rs_j · div_дискр[G^o]_j  =?=  R_j

где R_j — адвективный член eq:mdot_conv_face. Тождество должно
выполняться ТОЧНО (до машинного нуля), если Bo в адвективном члене
берётся так же, как в G^o, то есть СНЕСЁННЫМ ПО ПОТОКУ (вариант А).

Вариант Б (Bo из текущей ячейки, поток в пластовых условиях
Q_o = G^o·Bo_up, затем деление на Bo_j) тождеству не удовлетворяет:
он вносит множитель Bo_up/Bo_j, который в правиле Лейбница не возникает.

ВЫВОД, который проверяет скрипт: вариант А согласован с балансами масс
по построению, вариант Б — нет, хотя численно они близки (разница
0.02-0.5 %, см. measure_mdot_Bo_placement.py).
"""

import sys
from pathlib import Path

import numpy as np

EXAMPLES_DIR = Path(__file__).parent
sys.path.insert(0, str(EXAMPLES_DIR))

_PROTO = EXAMPLES_DIR.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO) not in sys.path:
    sys.path.insert(0, str(_PROTO))

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config


def measure(example: str):
    cfg = load_config(EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)

    solver = simulator._energy
    grid = solver._grid
    N = grid.N
    rec = []

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        st = hydro_result.state
        Rs = st.Rs
        G_o = hydro_result.G_o
        Rs_ext = bc.Rs_ext
        Bo = solver.compute_cell_properties(
            st.p, st.Sg, Rs, 1.0 - st.Sg, T_old)['Bo']

        # ── Левая часть тождества ──
        # div[G^o·Rs]: поток произведения через грани, upstream по знаку G^o
        f = np.arange(1, N)
        GR = np.zeros(N + 1)
        GR[f] = (np.maximum(G_o[f], 0.0) * Rs[f - 1]
                 + np.minimum(G_o[f], 0.0) * Rs[f])
        GR[0] = G_o[0] * Rs[0]
        GR[N] = G_o[N] * Rs[N - 1] if G_o[N] >= 0 else G_o[N] * Rs_ext
        div_GR = GR[1:] - GR[:-1]

        # Rs_j · div[G^o]
        div_G = G_o[1:] - G_o[:-1]
        lhs = div_GR - Rs * div_G

        # ── Вариант А: Bo снесён по потоку (внутри G^o) ──
        Gp = np.maximum(G_o, 0.0)
        Gm = np.minimum(G_o, 0.0)
        Rs_left = np.r_[Rs[0], Rs[:-1]]
        Rs_right = np.r_[Rs[1:], Rs_ext]
        R_A = Gp[0:N] * (Rs - Rs_left) + Gm[1:N + 1] * (Rs_right - Rs)

        # ── Вариант Б: Bo из текущей ячейки ──
        Bo_up = np.empty(N + 1)
        Bo_up[0] = Bo[0]
        Bo_up[N] = Bo[N - 1]
        for k in range(1, N):
            Bo_up[k] = Bo[k - 1] if G_o[k] >= 0 else Bo[k]
        Qo = G_o * Bo_up                       # пластовые условия
        Qp = np.maximum(Qo, 0.0)
        Qm = np.minimum(Qo, 0.0)
        R_B = (Qp[0:N] * (Rs - Rs_left) + Qm[1:N + 1] * (Rs_right - Rs)) / Bo

        scale = max(float(np.max(np.abs(lhs))), 1e-300)
        rec.append(dict(
            t=state_prev.t,
            err_A=float(np.max(np.abs(lhs - R_A))) / scale,
            err_B=float(np.max(np.abs(lhs - R_B))) / scale,
            scale=scale,
        ))

    solver.matrix_probe = probe
    simulator.run(initial)
    solver.matrix_probe = None
    return rec


if __name__ == "__main__":
    print("Проверка дискретного правила Лейбница:")
    print("  div[G^o·Rs]_j - Rs_j·div[G^o]_j  =?=  R_j")
    print("=" * 78)
    print(f"{'пример':>26} {'отн. ошибка А':>16} {'отн. ошибка Б':>16}")
    print("-" * 78)
    for ex in sys.argv[1:] or ["09_degassing_latent_heat", "10_deep_degassing",
                               "11_degassing_at_boundary"]:
        r = measure(ex)
        eA = max(x['err_A'] for x in r)
        eB = max(x['err_B'] for x in r)
        print(f"{ex:>26} {eA:16.3e} {eB:16.3e}")
    print("\n  А — Bo снесён по потоку (внутри G^o), как в fluxes.py")
    print("  Б — Bo из текущей ячейки (поток в пластовых условиях)")
    print()
    print("  Машинный ноль у А означает: адвективный член ТОЧНО равен")
    print("  разности, которую даёт правило Лейбница на дискретном уровне,")
    print("  то есть согласован с балансами масс по построению.")
