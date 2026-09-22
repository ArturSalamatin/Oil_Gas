"""Замер дефекта формы в JT-члене (BUG-012, расширение на J_jt).

Постановка (eq:QJT_muJT, problem_statement.tex:2270-2276) даёт ПОТОЧЕЧНЫЙ
JT-член с градиентом давления:

    Q_JT = Σ_α ρ_α c_p,α μ_JT,α u_α ∂p/∂r     [Вт/м³]

Умножая на объём ячейки и переходя к расходам Q_α = u_α·A:

    V_j·Q_JT,j = Σ_α μ_JT,α Φ_α,j · (∂p/∂r)_j · (V_j/A_j)
               ≈ Σ_α μ_JT,α Φ_α  · Δp     — разность давлений по ячейке

Дискретизация (eq:QJT_disc, :1278-1280) вместо этого берёт РАЗНОСТЬ ПОТОКОВ:

    J_j = J_{j+1/2} − J_{j−1/2},   J_{j+1/2} = Σ_α μ_JT,α <Φ_α p>_{j+1/2}

то есть дискретизирует div(μ_JT Φ p), а не μ_JT Φ ∂p/∂r. Разность форм —
тот же дефект, что у конвективного члена (BUG-012), с лишним слагаемым
вида μ_JT·p_j·D_j.

Скрипт считает две версии JT-члена на одних и тех же входах решателя:
  jt_div  — то, что считает решатель (compute_jt, дивергентная форма);
  jt_adv  — адвективный аналог: Σ_α μ_JT,α^up Φ_α^up · (p_up − p_down)
            через те же грани и те же ячейки выше по потоку.

Адвективная версия строится из тех же Φ_α, что вернул решатель, — не своей
копией формулы (иначе это повторило бы BUG-004).
"""

import sys
from pathlib import Path

import numpy as np

EXAMPLES_DIR = Path(__file__).parent
sys.path.insert(0, str(EXAMPLES_DIR))

# radial_blackoil (прототип) подключается через sys.path, как в conftest.py
_PROTO_ROOT = EXAMPLES_DIR.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROTO_ROOT))

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config


def measure(example: str):
    cfg = load_config(EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)

    solver = simulator._energy
    grid = solver._grid
    N = grid.N

    records = []

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        p = hydro_result.state.p
        Sg = hydro_result.state.Sg
        Rs = hydro_result.state.Rs
        So = 1.0 - Sg

        props = solver.compute_cell_properties(p, Sg, Rs, So, T_old)
        ext = solver._ext_properties(bc)
        Phi_plus, Phi_minus, Phi_o, Phi_g = \
            solver.compute_convective_coefficients(
                hydro_result.Q_o, hydro_result.Q_g,
                props['rho_o'], props['rho_g'],
                props['c_p_o'], props['c_p_g'], N, ext)

        # Дивергентная версия — та, что реально уходит в правую часть d[j].
        jt_div = solver.compute_jt(
            hydro_result.Q_o, hydro_result.Q_g, Phi_o, Phi_g,
            props['mu_JT_o'], props['mu_JT_g'], p, N, ext)

        # ── Адвективный аналог ──
        # Для грани f (между ячейками f-1 и f) поток фазы α несёт
        # μ_JT и Φ из ячейки выше по потоку, а множителем идёт РАЗНОСТЬ
        # давлений на этой грани, а не само p. Собираем вклад грани и
        # разносим по ячейкам так же, как схема разносит поток: вклад
        # грани f принадлежит ячейке выше по потоку — именно она
        # испытывает перепад.
        mu_o = props['mu_JT_o']
        mu_g = props['mu_JT_g']

        # Давление "за гранью": для внутренней грани f это p[f] справа
        # и p[f-1] слева; для забоя — p_wf; для контура — p_ext.
        p_wf = bc.well.value if hasattr(bc.well, 'value') else p[0]
        jt_adv = np.zeros(N)

        for f in range(N + 1):
            # Ячейки по обе стороны грани f
            left = f - 1          # -1 означает "скважина"
            right = f             # N означает "контур"

            # Давление по обе стороны
            pL = p_wf if left < 0 else p[left]
            pR = ext['p'] if right >= N else p[right]

            for Phi, mu in ((Phi_o, mu_o), (Phi_g, mu_g)):
                Pf = Phi[f]
                if Pf == 0.0:
                    continue
                if Pf > 0:
                    # Поток наружу: выше по потоку — левая ячейка
                    if left < 0:
                        continue          # втекание из скважины — не штатно
                    cell, mu_up = left, mu[left]
                else:
                    # Поток к скважине: выше по потоку — правая ячейка
                    if right >= N:
                        mu_up = ext['mu_JT_o'] if mu is mu_o else ext['mu_JT_g']
                        cell = N - 1      # вклад достаётся крайней ячейке
                    else:
                        cell, mu_up = right, mu[right]
                # Перепад давления на грани в направлении потока
                jt_adv[cell] += mu_up * Pf * (pL - pR)

        records.append(dict(
            t=state_prev.t,
            div_max=float(np.max(np.abs(jt_div))),
            adv_max=float(np.max(np.abs(jt_adv))),
            diff_max=float(np.max(np.abs(jt_div - jt_adv))),
        ))

    solver.matrix_probe = probe
    simulator.run(initial)
    solver.matrix_probe = None
    return records


if __name__ == "__main__":
    examples = sys.argv[1:] or ["08_degassing_jt", "10_deep_degassing",
                                "11_degassing_at_boundary"]
    for ex in examples:
        rec = measure(ex)
        print(f"\n{'=' * 70}\n{ex}   шагов: {len(rec)}\n{'=' * 70}")
        print(f"{'t, ч':>8} {'|J_div|':>12} {'|J_adv|':>12} {'|разн|':>12} "
              f"{'разн/div':>10}")
        print('-' * 70)
        for r in rec[:5] + ([rec[-1]] if len(rec) > 5 else []):
            ratio = r['diff_max'] / r['div_max'] if r['div_max'] > 0 else np.inf
            print(f"{r['t'] / 3600:8.2f} {r['div_max']:12.4e} "
                  f"{r['adv_max']:12.4e} {r['diff_max']:12.4e} {ratio:10.3f}")
        mx = max((r['diff_max'] / r['div_max']) for r in rec if r['div_max'] > 0)
        print(f"\n  max |разн| / |J_div| за прогон: {mx:.4f}")
