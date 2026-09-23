"""Величина устранённого дефекта формы в JT-члене (BUG-012).

ЧТО БЫЛО. Постановка eq:main_QJT_muJT задаёт JT-источник ПОТОЧЕЧНО, через
градиент давления:

    Q_JT = Σ_α ρ_α c_p,α μ_JT,α u_α ∂p/∂r     [Вт/м³]

Прежняя дискретизация собирала его как РАЗНОСТЬ ПОТОКОВ через грани:

    J_j = J_{j+1/2} − J_{j−1/2},  J_f = Σ_α μ_JT,α <Φ_α p>_f

то есть аппроксимировала div(μ_JT·Φ·p). Разность двух операторов —
лишний член μ_JT·p_j·D_j, где D_j = Φ_{j+1/2} − Φ_{j−1/2}.

ЧТО СТАЛО. После правки ядро считает eq:QJT_disc в адвективной форме:
вклад грани содержит ПЕРЕПАД давления, а не само p.

ЧТО МЕРИТ СКРИПТ. Обе версии на одних входах решателя:

  jt_adv — то, что считает ядро сейчас (compute_jt);
  jt_div — прежняя дивергентная версия, воспроизведённая здесь.

Разность — величина устранённого дефекта. Скрипт остаётся в репозитории
как инструмент замера: он показывает, какой вклад давал паразитный член,
и позволяет повторить оценку при изменении конфигов.

ЗАМЕРЕНО ДО ПРАВКИ (2026-09-22): расхождение форм составляло 1.86 (пр. 08)
и 1.88 (пр. 10) от величины самого JT-члена — то есть дефект был не
поправкой, а ошибкой ведущего порядка.
"""

import sys
from pathlib import Path

import numpy as np

EXAMPLES_DIR = Path(__file__).parent
sys.path.insert(0, str(EXAMPLES_DIR))

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

        props = solver.compute_cell_properties(p, Sg, Rs, 1.0 - Sg, T_old)
        ext = solver._ext_properties(bc)
        Q_o, Q_g = hydro_result.Q_o, hydro_result.Q_g
        _, _, Phi_o, Phi_g = solver.compute_convective_coefficients(
            Q_o, Q_g, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'], N, ext)

        p_wf = bc.well.boundary_pressure(hydro_result.state, grid,
                                         solver._pvt, None)

        # ── Адвективная версия: то, что считает ядро ──
        jt_adv = solver.compute_jt(
            Q_o, Q_g, Phi_o, Phi_g,
            props['mu_JT_o'], props['mu_JT_g'], p, N, ext, p_wf)

        # ── Дивергентная версия: как было до BUG-012 ──
        # J_face[f] = Σ_α μ_JT,α^up · <Φ_α·p>_f, затем разность по ячейкам.
        mu_o, mu_g = props['mu_JT_o'], props['mu_JT_g']
        J_face = np.zeros(N + 1)
        f = np.arange(1, N)
        up_o = np.where(Q_o[f] >= 0, f - 1, f)
        up_g = np.where(Q_g[f] >= 0, f - 1, f)
        J_face[f] = (mu_o[up_o] * (np.maximum(Phi_o[f], 0.0) * p[f - 1]
                                   + np.minimum(Phi_o[f], 0.0) * p[f])
                     + mu_g[up_g] * (np.maximum(Phi_g[f], 0.0) * p[f - 1]
                                     + np.minimum(Phi_g[f], 0.0) * p[f]))
        J_face[0] = mu_o[0] * Phi_o[0] * p[0] + mu_g[0] * Phi_g[0] * p[0]
        mu_o_N = mu_o[-1] if Q_o[N] >= 0 else ext['mu_JT_o']
        p_o_N = p[-1] if Q_o[N] >= 0 else ext['p']
        mu_g_N = mu_g[-1] if Q_g[N] >= 0 else ext['mu_JT_g']
        p_g_N = p[-1] if Q_g[N] >= 0 else ext['p']
        J_face[N] = mu_o_N * Phi_o[N] * p_o_N + mu_g_N * Phi_g[N] * p_g_N
        jt_div = J_face[1:] - J_face[:-1]

        records.append(dict(
            t=state_prev.t,
            adv_max=float(np.max(np.abs(jt_adv))),
            div_max=float(np.max(np.abs(jt_div))),
            diff_max=float(np.max(np.abs(jt_adv - jt_div))),
        ))

    solver.matrix_probe = probe
    simulator.run(initial)
    solver.matrix_probe = None
    return records


if __name__ == "__main__":
    examples = sys.argv[1:] or ["08_degassing_jt", "10_deep_degassing",
                                "11_degassing_at_boundary"]
    print("Величина устранённого дефекта формы в JT-члене (BUG-012)")
    print("=" * 78)
    print(f"{'пример':>26} {'|J_адв|':>13} {'|J_див|':>13} "
          f"{'|разн|':>13} {'разн/адв':>10}")
    print("-" * 78)
    for ex in examples:
        rec = measure(ex)
        adv = max(r['adv_max'] for r in rec)
        div = max(r['div_max'] for r in rec)
        dif = max(r['diff_max'] for r in rec)
        ratio = dif / adv if adv > 0 else float('nan')
        print(f"{ex:>26} {adv:13.4e} {div:13.4e} {dif:13.4e} {ratio:10.4f}")
    print("\n  J_адв — то, что ядро считает сейчас (адвективная форма)")
    print("  J_див — прежняя дивергентная версия")
    print("  Отношение показывает, какой вклад давал паразитный член")
    print("  μ_JT·p_j·D_j относительно самого JT-источника.")
