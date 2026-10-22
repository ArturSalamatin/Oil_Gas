"""Раунд 2 аудита BUG-012: что происходит с забойной гранью в mdot.

ВОПРОС РЕАЛИЗУЕМОСТИ. Текущий compute_degassing (tridiag.py:376-377)
учитывает забойную грань явно:

    R_conv[0] = G_o[0] * Rs[0]

и она входит в разность (R_conv[1:] - R_conv[:-1]), то есть даёт вклад
в ячейку 0. Блок шага 8а плана забойную грань ИСКЛЮЧАЕТ (adv[0] содержит
только правую грань).

Это не просто смена формы — это изменение того, учитывается ли вынос
газосодержания через забой. Скрипт замеряет разницу, чтобы реализация
не приняла её за побочный эффект.

ФИЗИЧЕСКИЙ СМЫСЛ. В дивергентной форме R_conv[0] = G^o_0·Rs_0 — поток
газосодержания, покидающий область через забой. В адвективной форме
член имеет вид (u_o/Bo)·dRs/dr, и через забойную грань градиент Rs не
определён (слева ячейки нет) — ровно та же трактовка, что для
температуры в assemble_tridiag при ГУ Неймана.

Вопрос, на который отвечает замер: насколько велик вклад забойной грани
и не теряется ли с ним что-то физически существенное.

РЕЗУЛЬТАТ (замерено 2026-09-22, раунд 2 аудита): |mdot_div[0]| и
|mdot_adv[0]| совпадают с точностью ~0.04 % на примерах 09, 10, 11.
Исключение забойной грани в ячейке 0 практически не меняет результат:
в дивергентной форме вклады забойной и правой граней почти уничтожают
друг друга. Расхождение форм (0.91-1.04) берётся из ВНУТРЕННИХ ячеек.
Это снимает опасение, что правка на забое что-то ломает.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python ..\\vault\\issues\\bug-012\\probes\\probe_well_face_degassing.py
"""

import sys
from pathlib import Path

import numpy as np

EXAMPLES = Path(__file__).resolve().parents[4] / "numerical_solver" / "examples"
sys.path.insert(0, str(EXAMPLES.parent))
sys.path.insert(0, str(EXAMPLES))
_PROTO = EXAMPLES.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO) not in sys.path:
    sys.path.insert(0, str(_PROTO))

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config


def measure(example: str):
    cfg = load_config(EXAMPLES / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)

    solver = simulator._energy
    grid = solver._grid
    N = grid.N
    V = grid.volumes
    rho_g_std = solver._pvt.rho_g_std

    rec = []

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        st = hydro_result.state
        Rs = st.Rs
        G_o = hydro_result.G_o
        Rs_ext = bc.Rs_ext

        # Вклад ЗАБОЙНОЙ грани в дивергентной форме: он входит в
        # разность R_conv[1] - R_conv[0] для ячейки 0 со знаком минус.
        R_conv_0 = G_o[0] * Rs[0]
        contrib_div_well = -rho_g_std * (-R_conv_0) / V[0]   # [кг/(м³·с)]

        # Полный mdot_conv ячейки 0 в дивергентной форме
        f = np.arange(1, N)
        R_conv = np.zeros(N + 1)
        R_conv[f] = (np.maximum(G_o[f], 0.0) * Rs[f - 1]
                     + np.minimum(G_o[f], 0.0) * Rs[f])
        R_conv[0] = R_conv_0
        R_conv[N] = (G_o[N] * Rs[N - 1] if G_o[N] >= 0
                     else G_o[N] * Rs_ext)
        mdot_div = -rho_g_std * (R_conv[1:] - R_conv[:-1]) / V

        # Адвективная версия (блок шага 8а)
        Gp = np.maximum(G_o, 0.0)
        Gm = np.minimum(G_o, 0.0)
        Rs_left = np.r_[Rs[0], Rs[:-1]]
        Rs_right = np.r_[Rs[1:], Rs_ext]
        adv = Gp[0:N] * (Rs - Rs_left) + Gm[1:N + 1] * (Rs_right - Rs)
        mdot_adv = -rho_g_std * adv / V

        rec.append(dict(
            t=state_prev.t,
            well_contrib=float(abs(contrib_div_well)),
            mdot_div_0=float(abs(mdot_div[0])),
            mdot_adv_0=float(abs(mdot_adv[0])),
            mdot_div_max=float(np.max(np.abs(mdot_div))),
            Rs_0=float(Rs[0]),
            Rs_1=float(Rs[1]) if N > 1 else float(Rs[0]),
            G_o_0=float(G_o[0]),
        ))

    solver.matrix_probe = probe
    simulator.run(initial)
    solver.matrix_probe = None
    return rec


if __name__ == "__main__":
    print("Вклад забойной грани в член дегазации")
    print("=" * 88)
    print(f"{'пример':>26} {'|вклад забоя|':>14} {'|mdot_div[0]|':>14} "
          f"{'|mdot_adv[0]|':>14} {'доля забоя':>11}")
    print("-" * 88)
    for ex in sys.argv[1:] or ["09_degassing_latent_heat", "10_deep_degassing",
                               "11_degassing_at_boundary"]:
        r = measure(ex)
        w = max(x['well_contrib'] for x in r)
        dv = max(x['mdot_div_0'] for x in r)
        ad = max(x['mdot_adv_0'] for x in r)
        share = w / dv if dv > 0 else float('nan')
        print(f"{ex:>26} {w:14.4e} {dv:14.4e} {ad:14.4e} {share:11.3f}")
    print("\n  Вклад забоя = |ρ_g,ст · G^o_0 · Rs_0 / V_0| — отдельное")
    print("  слагаемое дивергентной формы, которое адвективная исключает.")
    print()
    print("  ⚠️ КАК ЧИТАТЬ «долю забоя». Она > 1, потому что сравнивает")
    print("  ОДНО слагаемое с РАЗНОСТЬЮ двух: в дивергентной форме вклады")
    print("  забойной и правой граней почти уничтожают друг друга. Сама по")
    print("  себе эта колонка не говорит о величине эффекта.")
    print()
    print("  ЧТО ВАЖНО: |mdot_div[0]| и |mdot_adv[0]| совпадают с точностью")
    print("  ~0.04 %. То есть исключение забойной грани в ячейке 0 почти")
    print("  НЕ меняет результат — обе формы дают там одно и то же.")
    print("  Расхождение форм (0.91-1.04, см. measure_mdot_form.py) берётся")
    print("  из ВНУТРЕННИХ ячеек, а не из забойной грани.")
