"""Дефект формы в члене дегазации — сравнение двух форм (BUG-012).

ВОПРОС. Все три пространственных члена уравнения энергии имеют в
постановке ОДНУ структуру: скорость, скалярно умноженная на градиент
скаляра.

    конвекция   rho c_p u · grad T          (eq:main_energy_final)
    JT          rho c_p mu_JT u · grad p     (eq:QJT_muJT)
    дегазация   (u_o/Bo) · grad Rs           (eq:main_mdot, :415-422)

И все три в коде собраны как РАЗНОСТЬ ПОТОКОВ через грани, то есть в
дивергентной форме. Для mdot это eq:mdot_disc (:1313-1318):

    V_j mdot_j = -rho_g_ст [ V_j phi (1-Sg)/Bo (Rs^{n+1}-Rs^n)/dt
                             + (R_{j+1/2} - R_{j-1/2}) ],
    R_{j+1/2} = <G^o · Rs>_{j+1/2}

то есть div(G^o·Rs) вместо (u_o/Bo)·grad Rs — тот же дефект формы.

ЧТО МЕРИТЬ, А ЧТО НЕТ. Проверять замкнутость баланса нефти
(накопление^o + div G^o ≈ 0) БЕСПОЛЕЗНО: она лишь означает, что
div(G^o)_j = −накопление^o_j, то есть лишний член Rs_j·div(G^o)_j равен
−Rs_j·накопление^o_j, а не нулю. Мерить надо прямое расхождение двух
полных версий mdot.

ДВЕ ВЕРСИИ на одних и тех же входах решателя:

  mdot_div — то, что считает решатель (compute_degassing);
  mdot_adv — та же временная часть, но пространственная собрана
             адвективно, ТОЧНО ТАК ЖЕ, как конвекция энергии
             (eq:tridiag_a/b/c, оператор против потока):

                 (1/V_j)[ G^o⁺_{j-1/2} (Rs_j − Rs_{j-1})
                        + G^o⁻_{j+1/2} (Rs_{j+1} − Rs_j) ]

             G⁺ = max(G,0), G⁻ = min(G,0). Забой: левая грань вклада не
             даёт (слева ячейки нет). Контур: справа Rs_ext.

⚠️ ЗНАКИ. При выводе легко перевернуть разность: при потоке к скважине
(G^o < 0) выше по потоку ПРАВАЯ ячейка, и разность берётся (Rs_{j+1} −
Rs_j), а не наоборот. Признак ошибки знака — отношение |разн|/|div| ≈ 2
при почти равных по модулю E_div и E_adv: это подпись «величины
противоположны по знаку», а не физический дефект. Проверено на опыте.

Обе версии умножаются на −L и приводятся к вкладу V·Q_deg [Вт] — в той
размерности, в которой член входит в правую часть уравнения энергии.

ЗАМЕРЕННЫЙ РЕЗУЛЬТАТ (2026-09-22): расхождение 0.91–1.04 от самого члена
на переходном режиме. В примерах 09 и 10 затухает к стационару (там
dRs/dt → 0, обе формы сходятся), в примере 11 (разгазирование у контура)
СОХРАНЯЕТСЯ на стационаре — 5.3 %. Вывод: править надо, вместе с
конвекцией и JT, единой схемой.
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
    V = grid.volumes
    phi = solver._rock.porosity
    rho_g_std = solver._pvt.rho_g_std

    records = []

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        st = hydro_result.state
        Sg = st.Sg
        Rs = st.Rs
        So = 1.0 - Sg
        G_o = hydro_result.G_o

        props = solver.compute_cell_properties(st.p, Sg, Rs, So, T_old)
        Bo = props['Bo']
        L = props['L']

        # ── Версия решателя (дивергентная) ──
        Q_deg_div = solver.compute_degassing(
            So, Sg, Rs, state_prev.Rs, Bo, G_o, L, dt, N, bc.Rs_ext)

        # ── Адвективная версия ──
        # Временная часть — та же (eq:mdot_disc, первое слагаемое).
        mdot_time = -rho_g_std * phi * So / Bo * (Rs - state_prev.Rs) / dt

        # Пространственная часть против потока. Конвенция знаков проекта:
        # G^o >= 0 — от скважины (выше по потоку левая ячейка), G^o < 0 —
        # к скважине (выше по потоку правая). Тот же критерий, что в
        # compute_convective_coefficients и compute_degassing.
        Gp = np.maximum(G_o, 0.0)
        Gm = np.minimum(G_o, 0.0)
        # Rs соседей: слева от ячейки 0 ячейки нет (забой), справа от
        # ячейки N-1 — контур с составом Rs_ext (eq:bc_Sg_ext).
        Rs_left = np.r_[Rs[0], Rs[:-1]]
        Rs_right = np.r_[Rs[1:], bc.Rs_ext]

        # Грань j — левая для ячейки j, грань j+1 — правая.
        adv = Gp[0:N] * (Rs - Rs_left) + Gm[1:N + 1] * (Rs_right - Rs)
        # Забой: левая грань (f=0) вклада не даёт — слева нет ячейки,
        # градиент через забой не определён. Остаётся только правая грань.
        adv[0] = Gm[1] * (Rs_right[0] - Rs[0])

        mdot_adv = mdot_time + (-rho_g_std * adv / V)
        Q_deg_adv = -L * mdot_adv

        E_div = V * Q_deg_div
        E_adv = V * Q_deg_adv

        records.append(dict(
            t=state_prev.t,
            div_max=float(np.max(np.abs(E_div))),
            adv_max=float(np.max(np.abs(E_adv))),
            diff_max=float(np.max(np.abs(E_div - E_adv))),
            sum_div=float(np.sum(E_div)),
            sum_adv=float(np.sum(E_adv)),
            # dRs/dt: при нулевом значении обе формы сходятся
            dRs_max=float(np.max(np.abs((Rs - state_prev.Rs) / dt))),
            L_max=float(np.max(np.abs(L))) if np.ndim(L) else float(abs(L)),
        ))

    solver.matrix_probe = probe
    simulator.run(initial)
    solver.matrix_probe = None
    return records


def report(example, rec):
    print(f"\n{'=' * 84}\n{example}   шагов: {len(rec)}\n{'=' * 84}")
    if rec and rec[0]['L_max'] == 0.0:
        print("  L = 0 в этом конфиге — Q_deg тождественно ноль,")
        print("  дефект формы mdot на уравнение энергии не влияет.\n")
    print(f"{'t, ч':>8} {'|E_div|, Вт':>13} {'|E_adv|, Вт':>13} "
          f"{'|разн|, Вт':>13} {'разн/div':>9} {'max dRs/dt':>12}")
    print('-' * 84)
    for r in rec[:4] + ([rec[-1]] if len(rec) > 4 else []):
        ratio = r['diff_max'] / r['div_max'] if r['div_max'] > 0 else np.nan
        print(f"{r['t'] / 3600:8.2f} {r['div_max']:13.4e} {r['adv_max']:13.4e} "
              f"{r['diff_max']:13.4e} {ratio:9.4f} {r['dRs_max']:12.4e}")
    fin = [r['diff_max'] / r['div_max'] for r in rec if r['div_max'] > 0]
    if fin:
        last = rec[-1]
        print(f"\n  max |разн| / |E_div| за прогон: {max(fin):.4f}")
        print(f"  на последнем шаге:              "
              f"{last['diff_max'] / last['div_max'] if last['div_max'] > 0 else float('nan'):.4f}")
        print(f"  суммы на последнем шаге: div = {last['sum_div']:.4e} Вт, "
              f"adv = {last['sum_adv']:.4e} Вт")


if __name__ == "__main__":
    examples = sys.argv[1:] or ["09_degassing_latent_heat", "10_deep_degassing",
                                "11_degassing_at_boundary"]
    for ex in examples:
        report(ex, measure(ex))
