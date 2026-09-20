"""DEBT-016: поэлементная сверка матрицы температурной задачи с постановкой.

Что проверяется. Для КАЖДОГО вызова `TridiagEnergySolver.solve` на конфигах
всех примеров коэффициенты трёх диагоналей `a`, `b`, `c` и правая часть `d`,
реально ушедшие в `solve_banded_system`, сравниваются с эталоном, собранным
здесь независимо по формулам `doc/problem_statement.tex`.

Граница теста. Гидродинамика НЕ проверяется: поля `Q_o`, `Q_g`, `G_o`, `p`,
`Sg`, `Rs` берутся из `hydro_result` как точно известные. Всё, что вычисляет
сама температурная задача, эталон считает сам: выбор ячейки выше по потоку,
разложение Φ±, λ_eff, (ρcp)_eff, проводимости граней, J_JT, Q_ad, Q_deg, cap.
Из ядра берутся только PVT-корреляции и геометрия сетки — иначе тест выродился
бы в копию `pvt/` и `grid/`.

Эталон следует форме ДОКУМЕНТА, а не форме кода. В двух местах они записаны
по-разному при тождественных значениях (см. `_ref_adiabatic` и `_ref_conductive`).
Копировать форму кода нельзя: тогда тест зафиксировал бы реализацию вместо
постановки и перестал бы ловить расхождение между ними. По той же причине
контурные свойства считает `_ref_ext_properties`, а не метод ядра
`TridiagEnergySolver._ext_properties`.

Почему нельзя требовать побитового равенства. Эталон и ядро суммируют одни и
те же величины в разном порядке, набегает несколько ULP. Замерено: худшее
относительное расхождение 2.4e-15 при пороге 1e-13 — запас ~40×. Границы
(a[0], c[N-1]) при этом проверяются строгим равенством нулю: там нет
арифметики, только структура схемы.

Нулевые члены — это верный результат, а не пробел. На текущих конфигах
Φ⁺ ≡ 0 (потоки всегда к скважине) и λ_eff = 0 везде, кроме 10 и 11. Эталон
по формуле даёт там же ноль, значения совпадают. Появится конфиг с оттоком
от скважины или с теплопроводностью — тот же тест отработает на нём верно
без единой правки: он вычисляет формулу, а не перебирает случаи.

Эталон подхода: InjectorGPN, tests/heat_compressible_fluid_field_RFP_control_test.cpp.
"""

import math
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# Те же 12 сценариев, что в tests/test_examples.py::ALL_EXAMPLES.
# Список дублируется намеренно: тест не должен молча менять охват
# вслед за правками соседнего модуля.
ALL_EXAMPLES = [
    "01_single_phase_no_jt",
    "02_single_phase_jt",
    "03_standing_corey",
    "04_table_table",
    "04a_high_gas_saturation",
    "05_standing_table_rp",
    "06_table_corey_rp",
    "07_degassing_adiabatic_only",
    "08_degassing_jt",
    "09_degassing_latent_heat",
    "10_deep_degassing",
    "11_degassing_at_boundary",
]

# Порог сверки. Ниже 1e-13 начинается шум разного порядка суммирования
# (замерено 2.4e-15), выше — пропускаются реальные дефекты: самая слабая
# инъекция ошибки в обратном ходе даёт 7.9e-09.
RTOL = 1e-13


# ═══════════════════════════════════════════════════════════
# Эталонная сборка: формулы problem_statement.tex
# ═══════════════════════════════════════════════════════════

def _ref_cell_properties(pvt, rock, p, Sg, Rs, T_old):
    """Эффективные свойства в ячейках. eq:main_rhocpeff, eq:lambda_eff.

    (ρcp)_eff = (1-φ)·(ρcp)_s + φ·Σ_α S_α·ρ_α·c_pα   [Дж/(м³·К)]
    λ_eff     = (1-φ)·λ_s     + φ·Σ_α S_α·λ_α        [Вт/(м·К)]

    So берётся как 1 - Sg, как в ядре: тождество So + Sg = 1 обязано
    выполняться точно.
    """
    So = 1.0 - Sg
    phi = rock.porosity

    # PVT берём из ядра — воспроизводить корреляции здесь бессмысленно,
    # тест проверяет сборку матрицы, а не PVT-модель.
    props = dict(
        Bo=pvt.Bo(p, Rs),
        rho_o=pvt.rho_o(p, Rs),
        rho_g=pvt.rho_g(p),
        c_p_o=pvt.c_p_oil(p, T_old),
        c_p_g=pvt.c_p_gas(p, T_old),
        mu_JT_o=pvt.mu_JT_oil(p, T_old),
        mu_JT_g=pvt.mu_JT_gas(p, T_old),
        L=pvt.L_degas(p, T_old),
        So=So,
    )
    props['rho_cp_eff'] = ((1.0 - phi) * rock.rho_cp_solid
                           + phi * (So * props['rho_o'] * props['c_p_o']
                                    + Sg * props['rho_g'] * props['c_p_g']))
    props['lambda_eff'] = ((1.0 - phi) * rock.lambda_solid
                           + phi * (So * rock.lambda_oil
                                    + Sg * rock.lambda_gas))
    return props


def _upstream(flux_at_face, face):
    """Ячейка выше по потоку для внутренней грани. eq:upstream_operator.

    Конвенция знаков (vault/knowledge/decisions/конвенции-знаков.md):
    положительное направление — от скважины, в сторону роста r.
    Значит flux >= 0 — течение слева направо, берём левую ячейку face-1;
    flux < 0 — течение к скважине, берём правую ячейку face.

    Ноль отнесён к левой ветке (>=), как и в ядре: при нулевом потоке
    конвективный вклад всё равно нулевой, выбор ячейки ни на что не влияет.
    """
    return face - 1 if flux_at_face >= 0 else face


def _ref_convective(Q_o, Q_g, rho_o, rho_g, c_p_o, c_p_g, N, ext):
    """Конвективные коэффициенты на гранях. eq:energy_conv_face.

    Φ_α = ρ_α·c_pα·Q_α  [Вт/К], свойства из ячейки выше по потоку.
    Направление определяется РАЗДЕЛЬНО по каждой фазе — фазы могут
    течь в разные стороны (прямо оговорено в eq:energy_conv_face).

    Φ⁺ = Σ_α max(Φ_α, 0) >= 0, Φ⁻ = Σ_α min(Φ_α, 0) <= 0.
    На текущих конфигах Q_α < 0 всюду, поэтому Φ⁺ ≡ 0 — это верно,
    а не пропуск: вклад ветки «от скважины» здесь физически отсутствует.

    Возвращает Φ_o, Φ_g, Φ⁺, Φ⁻ — все [N+1].
    """
    Phi_o = np.zeros(N + 1)
    Phi_g = np.zeros(N + 1)

    # ── Внутренние грани ──
    for f in range(1, N):
        up_o = _upstream(Q_o[f], f)
        Phi_o[f] = rho_o[up_o] * c_p_o[up_o] * Q_o[f]

        up_g = _upstream(Q_g[f], f)
        Phi_g[f] = rho_g[up_g] * c_p_g[up_g] * Q_g[f]

    # ── Забой (f=0) ──
    # Флюид уходит в скважину, выше по потоку — ячейка 0
    # (ssec:bc_disc, подпараграф «Температура»).
    Phi_o[0] = rho_o[0] * c_p_o[0] * Q_o[0]
    Phi_g[0] = rho_g[0] * c_p_g[0] * Q_g[0]

    # ── Контур (f=N) ── eq:bc_props_ext (74)
    # По знаку расхода, раздельно по фазам: отток наружу — свойства
    # из ячейки N-1, приток — при условиях контура (p_0, T_0, Rs^0).
    # Газовая ветвь при Sg|ext = 0 умножается на Q_g = 0, поэтому
    # значение ρ_g, c_p_g на результат не влияет; формула всё равно
    # выписана полностью — она верна и при Sg_ext > 0.
    Phi_o[N] = ((rho_o[N - 1] * c_p_o[N - 1] if Q_o[N] >= 0
                 else ext['rho_o'] * ext['c_p_o']) * Q_o[N])
    Phi_g[N] = ((rho_g[N - 1] * c_p_g[N - 1] if Q_g[N] >= 0
                 else ext['rho_g'] * ext['c_p_g']) * Q_g[N])

    return (Phi_o, Phi_g,
            np.maximum(Phi_o, 0.0) + np.maximum(Phi_g, 0.0),
            np.minimum(Phi_o, 0.0) + np.minimum(Phi_g, 0.0))


def _ref_conductive(grid, lambda_eff, N):
    """Кондуктивная проводимость граней. eq:heat_cond_disc.

    ФОРМА ДОКУМЕНТА:
        Q_T = 2πh · λ^{j+1/2} / ln(r_{j+1}/r_j),
        λ^{j+1/2} = (w_L/λ_L + w_R/λ_R)^{-1} · (w_L + w_R)   [гармоническое
        среднее с логарифмическими весами]

    Ядро считает это иначе — как последовательные кольцевые сопротивления
    Q_T = 2πh / (w_L/λ_L + w_R/λ_R). Формы алгебраически тождественны, так
    как w_L + w_R = ln(r_{j+1}/r_j); расхождение 3.4e-16 (несколько ULP).
    Здесь намеренно записана форма документа: именно ошибка в этом месте
    (двойной ln) была содержанием BUG-002.

    При λ = 0 сопротивление бесконечно, проводимость — ноль. Считаем через
    errstate: промежуточные inf/nan ожидаемы, 2πh/inf = 0 — верный ответ.

    Контур: соседней ячейки нет, λ берётся из ячейки N-1 (ssec:bc_disc).

    Возвращает Q_T_internal [N-1] (>= 0) и Q_T_ext (скаляр, >= 0).
    """
    if N > 1:
        w_L = grid.log_weights_left      # ln(r_face / r_center_left)
        w_R = grid.log_weights_right     # ln(r_center_right / r_face)
        r_c = grid.r_centers
        ln_ratio = np.log(r_c[1:] / r_c[:-1])

        with np.errstate(divide='ignore', invalid='ignore'):
            lam_face = (w_L + w_R) / (w_L / lambda_eff[:-1]
                                      + w_R / lambda_eff[1:])
            Q_T_internal = 2.0 * np.pi * grid.h * lam_face / ln_ratio
        # λ = 0 даёт 0/0 → nan; физический ответ — нулевая проводимость.
        Q_T_internal = np.nan_to_num(Q_T_internal, nan=0.0)
    else:
        Q_T_internal = np.empty(0)

    Q_T_ext = (2.0 * np.pi * grid.h
               / np.log(grid.R_ext / grid.r_centers[-1]) * lambda_eff[-1])

    return Q_T_internal, Q_T_ext


def _ref_ext_properties(pvt, bc):
    """Свойства фаз при условиях контура. eq:bc_props_ext (74).

    Считается ЗДЕСЬ, а не вызовом TridiagEnergySolver._ext_properties:
    эталон обязан быть независимым от ядра, иначе он зафиксирует
    реализацию вместо постановки (шапка модуля). Из ядра берутся только
    PVT-корреляции — воспроизводить их тут бессмысленно.

    Sg на контуре не участвует: тепловые PVT-величины от насыщенности
    не зависят (FullPVT, pvt/base.py:60-107); отсутствие газовой фазы
    выражается через Q_g = 0 при k_rg|ext = 0 (eq:bc_flux_ext).
    """
    p_a = np.array([bc.p_ext])
    T_a = np.array([bc.T_ext])
    Rs_a = np.array([bc.Rs_ext])
    return dict(
        p=bc.p_ext,
        rho_o=pvt.rho_o(p_a, Rs_a)[0],
        rho_g=pvt.rho_g(p_a)[0],
        c_p_o=pvt.c_p_oil(p_a, T_a)[0],
        c_p_g=pvt.c_p_gas(p_a, T_a)[0],
        mu_JT_o=pvt.mu_JT_oil(p_a, T_a)[0],
        mu_JT_g=pvt.mu_JT_gas(p_a, T_a)[0])


def _ref_jt(Phi_o, Phi_g, mu_JT_o, mu_JT_g, Q_o, Q_g, p, N, ext):
    """Вклад Джоуля—Томсона. eq:QJT_face, eq:QJT_disc.

    J_{f} = Σ_α μ_JT,α^up · <Φ_α·p>_f,  где <·> — оператор против потока
            <Φ·p>_f = Φ⁺·p_{f-1} + Φ⁻·p_f          (eq:upstream_operator)
    J_j   = J_{j+1/2} - J_{j-1/2}                    [Вт]

    Коэффициент μ_JT берётся из ячейки выше по потоку СВОЕЙ фазы.

    На граничных гранях значения за границей заменяются граничными
    условиями (ssec:bc_disc, «Источниковые члены на граничных гранях»):
    на забое выше по потоку — ячейка 0.

    На контуре — по знаку расхода, eq:bc_props_ext (74):
        Q_α >= 0 (отток наружу)  → μ_JT и p из ячейки N-1;
        Q_α <  0 (приток)        → μ_JT при (p_0, T_0), p = p_ext.
    Раздельно по фазам, как и всюду в операторе против потока.

    Возвращает J_jt [N].
    """
    J_face = np.zeros(N + 1)

    # ── Внутренние грани ──
    for f in range(1, N):
        up_o = _upstream(Q_o[f], f)
        J_o = mu_JT_o[up_o] * (max(Phi_o[f], 0.0) * p[f - 1]
                               + min(Phi_o[f], 0.0) * p[f])

        up_g = _upstream(Q_g[f], f)
        J_g = mu_JT_g[up_g] * (max(Phi_g[f], 0.0) * p[f - 1]
                               + min(Phi_g[f], 0.0) * p[f])

        J_face[f] = J_o + J_g

    # ── Забой ──
    # Поток направлен к скважине, upstream — ячейка 0, поэтому
    # <Φ·p> вырождается в Φ·p[0] независимо от знака Φ.
    J_face[0] = (mu_JT_o[0] * Phi_o[0] * p[0]
                 + mu_JT_g[0] * Phi_g[0] * p[0])

    # ── Контур ── eq:bc_props_ext (74)
    # При притоке за границей находится контур, поэтому μ_JT и p
    # берутся при его условиях. Признак — знак Q_α, раздельно по фазам.
    mu_o_N = mu_JT_o[-1] if Q_o[N] >= 0 else ext['mu_JT_o']
    p_o_N = p[-1] if Q_o[N] >= 0 else ext['p']
    mu_g_N = mu_JT_g[-1] if Q_g[N] >= 0 else ext['mu_JT_g']
    p_g_N = p[-1] if Q_g[N] >= 0 else ext['p']

    J_face[N] = mu_o_N * Phi_o[N] * p_o_N + mu_g_N * Phi_g[N] * p_g_N

    return J_face[1:] - J_face[:-1]


def _ref_adiabatic(rock, So, Sg, rho_o, rho_g, c_p_o, c_p_g,
                   mu_JT_o, mu_JT_g, p, p_old, dt):
    """Адиабатический эффект. eq:Qad_disc (при c_r = 0).

    ФОРМА ДОКУМЕНТА — единица ВНЕ суммы:
        Q_ad = φ·[1 + Σ_α S_α·ρ_α·c_pα·μ_JT,α]·(p^{n+1} - p^n)/Δt   [Вт/м³]

    Ядро пишет единицу ВНУТРИ суммы: φ·Σ_α S_α·(1 + ρ_α·c_pα·μ_JT,α)·dp/dt.
    Формы тождественны ровно потому, что S_o + S_g = 1; проверено численно:
    при выполнении инварианта расхождение 3.8e-16, при нарушении — 1.5e-07.
    Поэтому So здесь обязан приходить как 1 - Sg, а не из другого источника.
    """
    dp_dt = (p - p_old) / dt
    return rock.porosity * (1.0
                            + So * rho_o * c_p_o * mu_JT_o
                            + Sg * rho_g * c_p_g * mu_JT_g) * dp_dt


def _ref_degassing(grid, pvt, rock, So, Sg, Rs, Rs_old, Bo, G_o, L,
                   dt, N, Rs_ext):
    """Теплота дегазации. eq:Qdeg_disc, eq:mdot_disc, eq:mdot_conv_face.

    Q_deg = -L·ṁ   [Вт/м³],  ṁ — массовый темп выделения свободного газа.

    V_j·ṁ_j = -ρ_g^ст·[ V_j·φ·(1-S_g)/B_o·(R_s^{n+1} - R_s^n)/Δt
                        + (R_{j+1/2} - R_{j-1/2}) ],
    где R_f = <G^o·R_s>_f — конвективный поток газосодержания через грань,
    G^o — поток нефтяного КОМПОНЕНТА [м³ст/с] (не расход фазы Q_o [м³пл/с]).

    Контурная грань: при притоке (G_o < 0) состав задан граничным условием
    R_s|_ext = R_s^0 (eq:bc_Sg_ext). Брать Rs[N-1] нельзя — при p_{N-1} < p_b
    это состав дегазированной нефти вместо состава притока (DEBT-009).
    """
    phi = rock.porosity
    V = grid.volumes
    rho_g_std = pvt.rho_g_std

    # Временная часть: изменение растворённого газа в ячейке
    mdot_time = -rho_g_std * phi * So / Bo * (Rs - Rs_old) / dt

    # Конвективная часть: перенос R_s потоком нефтяного компонента
    R_conv = np.zeros(N + 1)
    for f in range(1, N):
        # Оператор против потока по знаку G_o (eq:upstream_operator)
        R_conv[f] = (max(G_o[f], 0.0) * Rs[f - 1]
                     + min(G_o[f], 0.0) * Rs[f])

    # Забой: поток к скважине, upstream — ячейка 0
    R_conv[0] = G_o[0] * Rs[0]

    # Контур: при оттоке наружу upstream — ячейка N-1,
    # при притоке — состав задан ГУ (DEBT-009)
    R_conv[N] = G_o[N] * (Rs[N - 1] if G_o[N] >= 0 else Rs_ext)

    mdot = mdot_time + (-rho_g_std * (R_conv[1:] - R_conv[:-1]) / V)
    return -L * mdot


def _ref_assemble(grid, N, dt, T_old, T_ext, rho_cp_eff,
                  Q_T_internal, Q_T_ext, Phi_plus, Phi_minus,
                  J_jt, Q_ad, Q_deg):
    """Коэффициенты СЛАУ. eq:tridiag_a, eq:tridiag_b, eq:tridiag_c, eq:tridiag_d.

    a_j = -Q_T_{j-1/2} - Φ⁺_{j-1/2}
    c_j = -Q_T_{j+1/2} + Φ⁻_{j+1/2}
    b_j = V_j·(ρcp)_eff/Δt + Q_T_{j-1/2} + Q_T_{j+1/2} + Φ⁺_{j+1/2} - Φ⁻_{j-1/2}
    d_j = V_j·(ρcp)_eff/Δt·T_j^n + J_j + V_j·(Q_ad + Q_deg)

    Ожидаемые знаки: a <= 0, c <= 0, b > 0 — диагональное преобладание.

    Граничные условия (ssec:bc_disc, подпараграф «Температура»):
      - забой, j=0: ∂T/∂r = 0 → кондуктивный поток через левую грань
        обнуляется, Q_λ,1/2 = 0, связи с ячейкой слева нет → a[0] = 0.
        Конвективный поток через забой остаётся: Φ⁺[0] входит в b.
      - контур, j=N-1: T|_Rext = T_ext (Дирихле). Известная температура
        уходит в правую часть: кондуктивный вклад Q_T_ext·T_ext и
        конвективный (-Φ⁻[N])·T_ext. Связи справа нет → c[N-1] = 0.
    """
    V = grid.volumes

    a = np.zeros(N)
    b = np.zeros(N)
    c = np.zeros(N)
    d = np.zeros(N)

    # Накопительный член [Вт/К]. Δt — ФАКТИЧЕСКИЙ шаг, с которым
    # собрана матрица (при A-retry это dt_sub, а не шаг расписания).
    cap = V * rho_cp_eff / dt

    # ── Внутренние ячейки j = 1..N-2 ──
    for j in range(1, N - 1):
        Q_T_L = Q_T_internal[j - 1]
        Q_T_R = Q_T_internal[j]

        a[j] = -Q_T_L - Phi_plus[j]
        c[j] = -Q_T_R + Phi_minus[j + 1]
        b[j] = cap[j] + Q_T_L + Q_T_R + Phi_plus[j + 1] - Phi_minus[j]
        d[j] = cap[j] * T_old[j] + J_jt[j] + V[j] * (Q_ad[j] + Q_deg[j])

    # ── Забой j=0: Нейман ──
    Q_T_R0 = Q_T_internal[0] if N > 1 else 0.0

    a[0] = 0.0
    c[0] = (-Q_T_R0 + Phi_minus[1]) if N > 1 else 0.0
    b[0] = cap[0] + Q_T_R0 + Phi_plus[1] - Phi_minus[0] + Phi_plus[0]
    d[0] = cap[0] * T_old[0] + J_jt[0] + V[0] * (Q_ad[0] + Q_deg[0])

    # ── Контур j=N-1: Дирихле ──
    Q_T_LN = Q_T_internal[-1] if N > 1 else 0.0

    a[N - 1] = (-Q_T_LN - Phi_plus[N - 1]) if N > 1 else 0.0
    c[N - 1] = 0.0
    b[N - 1] = cap[N - 1] + Q_T_LN + Q_T_ext + Phi_plus[N] - Phi_minus[N - 1]
    d[N - 1] = (cap[N - 1] * T_old[N - 1]
                + Q_T_ext * T_ext               # кондуктивный вклад ГУ
                + (-Phi_minus[N]) * T_ext       # конвективный вклад ГУ
                + J_jt[N - 1]
                + V[N - 1] * (Q_ad[N - 1] + Q_deg[N - 1]))

    return a, b, c, d


def build_reference(grid, pvt, rock, hydro_result, state_prev, dt, bc):
    """Собрать эталонные a, b, c, d для одного вызова solve.

    dt — фактический шаг вызова, НЕ шаг расписания: при A-retry Simulator
    дробит интервал и вызывает solve с dt_sub = dt/n_sub (BUG-010), а
    cap = V·(ρcp)/dt зависит именно от dt_sub.
    """
    N = grid.N
    st = hydro_result.state

    props = _ref_cell_properties(pvt, rock, st.p, st.Sg, st.Rs, state_prev.T)

    # Свойства контура — выше по потоку при притоке, eq:bc_props_ext (74)
    ext = _ref_ext_properties(pvt, bc)

    Phi_o, Phi_g, Phi_plus, Phi_minus = _ref_convective(
        hydro_result.Q_o, hydro_result.Q_g,
        props['rho_o'], props['rho_g'],
        props['c_p_o'], props['c_p_g'], N, ext)

    Q_T_internal, Q_T_ext = _ref_conductive(grid, props['lambda_eff'], N)

    J_jt = _ref_jt(Phi_o, Phi_g, props['mu_JT_o'], props['mu_JT_g'],
                   hydro_result.Q_o, hydro_result.Q_g, st.p, N, ext)

    Q_ad = _ref_adiabatic(rock, props['So'], st.Sg,
                          props['rho_o'], props['rho_g'],
                          props['c_p_o'], props['c_p_g'],
                          props['mu_JT_o'], props['mu_JT_g'],
                          st.p, state_prev.p, dt)

    Q_deg = _ref_degassing(grid, pvt, rock, props['So'], st.Sg,
                           st.Rs, state_prev.Rs, props['Bo'],
                           hydro_result.G_o, props['L'], dt, N, bc.Rs_ext)

    return _ref_assemble(grid, N, dt, state_prev.T, bc.T_ext,
                         props['rho_cp_eff'], Q_T_internal, Q_T_ext,
                         Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)


# ═══════════════════════════════════════════════════════════
# A. Сверка матрицы с эталоном на конфигах примеров
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("example", ALL_EXAMPLES)
def test_matrix_matches_reference(example):
    """Коэффициенты СЛАУ совпадают с эталоном на каждом вызове solve.

    Условия: штатный конфиг примера без урезания сетки и расписания.
    Ожидание: a, b, c, d совпадают с эталоном при rtol=1e-13; границы
    a[0] и c[N-1] равны нулю точно.

    Сверка идёт НА ЛЕТУ, внутри пробы: накапливать нельзя — у 04a 1375
    вызовов при N=150, список из четырёх векторов на вызов дал бы сотни
    мегабайт.
    """
    cfg = load_config(EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)

    n_calls = [0]

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        ref_a, ref_b, ref_c, ref_d = build_reference(
            simulator._grid, simulator._pvt, cfg.rock,
            hydro_result, state_prev, dt, bc)

        where = f"{example}: вызов {n_calls[0]}, dt={dt:g} с"
        np.testing.assert_allclose(a, ref_a, rtol=RTOL, atol=0.0,
                                   err_msg=f"{where}, поддиагональ a")
        np.testing.assert_allclose(b, ref_b, rtol=RTOL, atol=0.0,
                                   err_msg=f"{where}, главная диагональ b")
        np.testing.assert_allclose(c, ref_c, rtol=RTOL, atol=0.0,
                                   err_msg=f"{where}, наддиагональ c")
        np.testing.assert_allclose(d, ref_d, rtol=RTOL, atol=0.0,
                                   err_msg=f"{where}, правая часть d")

        # Границы — структура схемы, а не арифметика: строгое равенство.
        # a[0] = 0: на забое Нейман, кондуктивный поток через левую грань
        # обнулён, связи с ячейкой слева нет.
        assert a[0] == 0.0, f"{where}: a[0] обязан быть нулём (Нейман на забое)"
        # c[N-1] = 0: на контуре Дирихле, T_ext известна и ушла в d.
        assert c[-1] == 0.0, f"{where}: c[N-1] обязан быть нулём (Дирихле на контуре)"

        n_calls[0] += 1

    simulator._energy.matrix_probe = probe
    simulator.run(initial)

    assert n_calls[0] > 0, f"{example}: проба ни разу не вызвана"


# ═══════════════════════════════════════════════════════════
# B. Дробление шага энергии при A-retry
# ═══════════════════════════════════════════════════════════

class _CountingEnergySolver:
    """Обёртка над энергетическим решателем: считает вызовы и их dt.

    Не подменяет физику — делегирует настоящему TridiagEnergySolver.
    Та же конструкция, что в tests/test_simulator.py, но там она работает
    на двойнике гидродинамики, а здесь — на живых конфигах.
    """

    def __init__(self, inner):
        self._inner = inner
        self.dt_calls: list[float] = []

    def solve(self, hydro_result, state_prev, dt, bc, collect=None):
        self.dt_calls.append(dt)
        return self._inner.solve(hydro_result, state_prev, dt, bc, collect)


# Примеры, где A-retry реально срабатывает (замерено):
#   10_deep_degassing        — один шаг 3600 с раздроблен на 2 × 1800 с
#   11_degassing_at_boundary — один шаг 3600 с раздроблен на 16 × 225 с
# На остальных конфигах дробления нет и проверять нечего.
SUBDIVIDING_EXAMPLES = ["10_deep_degassing", "11_degassing_at_boundary"]


@pytest.mark.parametrize("example", SUBDIVIDING_EXAMPLES)
def test_energy_substeps_preserve_total_time(example):
    """Сумма фактических dt по вызовам solve равна модельному времени.

    Физика: расщепление «гидро → энергия» имеет порядок O(dt) и применимо
    лишь там, где устойчивы обе половины. Если гидро признало шаг слишком
    крупным и раздробило его, энергия обязана пройти те же подшаги
    (BUG-010). Инвариант, который это фиксирует, — сохранение времени:
    сколько бы подшагов ни получилось, их сумма равна интервалу.

    Почему не сверяем с hydro_result.n_substeps: внутри solve оно всегда
    равно 1. Пробный шаг с n_substeps > 1 отбрасывается в Simulator._advance,
    а в рекурсивные вызовы приходит уже несдроблённый результат.
    """
    cfg = load_config(EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)

    counter = _CountingEnergySolver(simulator._energy)
    simulator._energy = counter
    simulator.run(initial)

    total_scheduled = sum(iv.dt for iv in cfg.time.history)
    total_actual = sum(counter.dt_calls)

    assert math.isclose(total_actual, total_scheduled, rel_tol=1e-12), (
        f"{example}: сумма dt по {len(counter.dt_calls)} вызовам = "
        f"{total_actual:g} с, расписание = {total_scheduled:g} с")

    # Дробление действительно произошло: вызовов больше, чем шагов
    # интегрирования, и среди них есть шаги короче штатного.
    dt_min = min(counter.dt_calls)
    dt_max = max(counter.dt_calls)
    assert dt_min < dt_max, (
        f"{example}: ожидалось дробление A-retry, но все вызовы прошли "
        f"с одинаковым dt={dt_max:g} с — конфиг или гидродинамика изменились")
