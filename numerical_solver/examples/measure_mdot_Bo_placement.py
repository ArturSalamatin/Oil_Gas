"""Где брать B_o в члене дегазации: снос по потоку или текущая ячейка.

ВОПРОС. В eq:main_mdot множитель 1/B_o стоит в ОБЕИХ частях:

    mdot = -rho_g_ст [ phi (1-Sg)/Bo · dRs/dt  +  (u_o/Bo) · dRs/dr ]

Но в дискретизации они попадают в разные места:

  временной член       — B_o,j из ТЕКУЩЕЙ ячейки (явно в формуле);
  пространственный     — B_o сидит внутри G^o (fluxes.py:86,
                         mob_o = kro/(mu_o·Bo)), взятого из ячейки
                         ВЫШЕ ПО ПОТОКУ.

Два варианта дискретизации:

  (А) как сейчас: B_o снесён по потоку в пространственной части,
      из текущей ячейки — во временной;

  (Б) общий множитель 1/B_o,j вынесен за скобку, то есть и в
      пространственной части B_o берётся из текущей ячейки. Тогда
      поток нужно брать в ПЛАСТОВЫХ условиях: Q_o = G^o · B_o,up.

Скрипт считает обе версии на одних данных решателя и сравнивает.

ЧТО ОЖИДАТЬ. Разница возникает только там, где B_o различается между
соседними ячейками, то есть на градиенте давления. Величина B_o в
районе p_b меняется быстро, поэтому у фронта разгазирования эффект
должен быть заметнее, чем вдали от него.

ЗАЧЕМ. Оба варианта аппроксимируют одно и то же дифференциальное
выражение и различаются на O(dr) — но выбор влияет на то, обращается
ли mdot в нуль тождественно при Rs = const, и на согласованность с
балансом газового компонента.
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
    pvt = solver._pvt
    N = grid.N
    V = grid.volumes
    phi = solver._rock.porosity
    rho_g_std = pvt.rho_g_std

    rec = []

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        st = hydro_result.state
        Sg = st.Sg
        Rs = st.Rs
        So = 1.0 - Sg
        G_o = hydro_result.G_o
        Rs_ext = bc.Rs_ext

        props = solver.compute_cell_properties(st.p, Sg, Rs, So, T_old)
        Bo = props['Bo']

        # Общая временная часть (B_o из текущей ячейки — в обоих вариантах)
        mdot_time = -rho_g_std * phi * So / Bo * (Rs - state_prev.Rs) / dt

        Rs_left = np.r_[Rs[0], Rs[:-1]]
        Rs_right = np.r_[Rs[1:], Rs_ext]

        # ── Вариант А: B_o снесён по потоку (внутри G^o) ──
        Gp = np.maximum(G_o, 0.0)
        Gm = np.minimum(G_o, 0.0)
        adv_A = Gp[0:N] * (Rs - Rs_left) + Gm[1:N + 1] * (Rs_right - Rs)
        mdot_A = mdot_time + (-rho_g_std * adv_A / V)

        # ── Вариант Б: B_o из текущей ячейки ──
        # Поток в пластовых условиях: Q_o = G^o · B_o,up. Затем делим
        # на B_o,j текущей ячейки. Итог: G^o · (B_o,up / B_o,j).
        # Ячейка выше по потоку для грани f: f-1 при G>=0, f при G<0.
        Bo_up = np.empty(N + 1)
        for f in range(N + 1):
            if f == 0:
                Bo_up[f] = Bo[0]                 # забой: upstream = ячейка 0
            elif f == N:
                Bo_up[f] = Bo[N - 1] if G_o[N] >= 0 else Bo[N - 1]
            else:
                Bo_up[f] = Bo[f - 1] if G_o[f] >= 0 else Bo[f]
        # G^o · B_o,up — расход нефти в пластовых условиях [м³пл/с]
        Qo_face = G_o * Bo_up
        Qp = np.maximum(Qo_face, 0.0)
        Qm = np.minimum(Qo_face, 0.0)
        adv_B = Qp[0:N] * (Rs - Rs_left) + Qm[1:N + 1] * (Rs_right - Rs)
        mdot_B = mdot_time + (-rho_g_std * adv_B / (V * Bo))

        # Вклад в уравнение энергии [Вт]
        L = props['L']
        E_A = V * (-L * mdot_A)
        E_B = V * (-L * mdot_B)

        # Насколько B_o различается между соседями
        Bo_jump = np.max(np.abs(np.diff(Bo))) / np.mean(Bo)

        rec.append(dict(
            t=state_prev.t,
            A_max=float(np.max(np.abs(E_A))),
            B_max=float(np.max(np.abs(E_B))),
            diff_max=float(np.max(np.abs(E_A - E_B))),
            Bo_jump=float(Bo_jump),
            Bo_min=float(np.min(Bo)), Bo_max=float(np.max(Bo)),
        ))

    solver.matrix_probe = probe
    simulator.run(initial)
    solver.matrix_probe = None
    return rec


if __name__ == "__main__":
    print("B_o в члене дегазации: снос по потоку (А) против текущей ячейки (Б)")
    print("=" * 92)
    print(f"{'пример':>26} {'max|E_A|':>12} {'max|E_B|':>12} {'max|разн|':>12} "
          f"{'разн/A':>9} {'размах Bo':>11}")
    print("-" * 92)
    for ex in sys.argv[1:] or ["09_degassing_latent_heat", "10_deep_degassing",
                               "11_degassing_at_boundary"]:
        r = measure(ex)
        A = max(x['A_max'] for x in r)
        B = max(x['B_max'] for x in r)
        D = max(x['diff_max'] for x in r)
        jump = max(x['Bo_jump'] for x in r)
        print(f"{ex:>26} {A:12.4e} {B:12.4e} {D:12.4e} "
              f"{D / A if A > 0 else float('nan'):9.4f} {jump:11.3e}")
    print("\n  размах Bo — max|B_o,j+1 - B_o,j| / среднее B_o: мера того,")
    print("  насколько вообще различаются соседние ячейки по B_o.")
    print("  Если разница вариантов того же порядка, что размах, — выбор")
    print("  влияет на решение; если на порядки меньше — вопрос вкуса.")
