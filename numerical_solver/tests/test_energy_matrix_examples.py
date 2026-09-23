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
на ВНУТРЕННИХ гранях или с теплопроводностью — тот же тест отработает на
нём верно без единой правки: он вычисляет формулу, а не перебирает случаи.

Единственное исключение — ЗАБОЙНАЯ грань: там закачка (Q > 0) запрещена
assert-ом, а не обрабатывается ветвью. Это не ограничение теста, а
требование постановки: при втекании через забой температура входящего
потока не задана ни одним граничным условием (на забое стоит условие
Неймана), и режим объявлен неопределённым (ssec:bc_disc). Конфиг с
нагнетанием потребует сначала расширить постановку, а не тест.

Эталон подхода: InjectorGPN, tests/heat_compressible_fluid_field_RFP_control_test.cpp.
"""

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
# Охват: список против содержимого examples/
# ═══════════════════════════════════════════════════════════

def test_coverage_matches_disk():
    """ALL_EXAMPLES не отстал от examples/.

    Список выше дублирует test_examples.py намеренно, 
    но расхождение с папками в репозитории —
    всегда ошибка. Без этой проверки новый пример добавляется в
    test_examples.py, срабатывает test_no_extra_example_folders,
    а здесь новый пример не учитывается: сценарий молча не проверяется на структуру
    матрицы.

    Отбор по d.name[0].isdigit() — тот же, что в test_examples.py:
    служебные папки (output, __pycache__) и общие модули отсеиваются,
    примеры именуются с ведущего номера.
    """
    on_disk = sorted(
        d.name for d in EXAMPLES_DIR.iterdir()
        if d.is_dir() and d.name[0].isdigit()
    )
    assert on_disk == sorted(ALL_EXAMPLES), (
        "список ALL_EXAMPLES разошёлся с examples/: "
        f"на диске {on_disk}, в списке {sorted(ALL_EXAMPLES)}")


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
    Это заготовка на будущее, если учитывается капиллярное давление
    и тензор проницаемости.

    Φ⁺ = Σ_α max(Φ_α, 0) >= 0, Φ⁻ = Σ_α min(Φ_α, 0) <= 0.
    На текущих конфигах Q_α < 0 всюду, поэтому Φ⁺ ≡ 0 — это верно,
    а не пропуск: вклад ветки «от скважины» здесь физически отсутствует.

    Возвращает Φ_o, Φ_g, Φ⁺, Φ⁻ — все [N+1].
    """
    Phi_o = np.zeros(N + 1)
    Phi_g = np.zeros(N + 1)

    # определяем, с какого направления потоком приносится энергия,
    # вызов функции _upstream, и вычисляем поток энергии Φ_o, Φ_g 
    # через грань

    # ── Внутренние грани ──
    for f in range(1, N):
        up_o = _upstream(Q_o[f], f)
        Phi_o[f] = rho_o[up_o] * c_p_o[up_o] * Q_o[f]

        up_g = _upstream(Q_g[f], f)
        Phi_g[f] = rho_g[up_g] * c_p_g[up_g] * Q_g[f]

    # ── Забой (f=0) ──
    # Флюид уходит в скважину, выше по потоку — ячейка 0
    # (ssec:bc_disc, подпараграф «Температура»).
    #
    # Закачка через забой не допускается: расходы обязаны быть
    # НЕПОЛОЖИТЕЛЬНЫМИ. Конвенция знаков проекта — положительное
    # направление от скважины, поэтому Q < 0 это добыча (штатный режим),
    # а Q > 0 — нагнетание в пласт.
    #
    # Почему это запрет, а не выбор ветви. При втекании выше по потоку
    # оказывается скважина, но температура закачиваемого флюида не задана
    # ни одним граничным условием: на забое стоит условие Неймана
    # ∂T/∂r = 0, а не Дирихле. Постановка (ssec:bc_disc) прямо называет
    # такой режим неопределённым и требует запрещать его проверкой в
    # реализации. Формула ниже взяла бы T из ячейки 0 — то есть внесла бы
    # в область энергию с температурой, которой там нет.
    #
    # Ноль допустим: при p_wf = p[0] потока нет и вклад нулевой.
    # Та же строгость, что в DEBT-019 (отказ при dp_w > 0, не >=).
    assert Q_o[0] <= 0.0, (
        f"закачка нефти через забой: Q_o[0] = {Q_o[0]:.6e} м³пл/с > 0. "
        "Режим не определён постановкой — температура втекающего потока "
        "не задана (ssec:bc_disc)")
    assert Q_g[0] <= 0.0, (
        f"закачка газа через забой: Q_g[0] = {Q_g[0]:.6e} м³пл/с > 0. "
        "Режим не определён постановкой — температура втекающего потока "
        "не задана (ssec:bc_disc)")

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


def _ref_jt(Phi_o, Phi_g, mu_JT_o, mu_JT_g, Q_o, Q_g, p, N, ext, p_wf):
    """Вклад Джоуля—Томсона. eq:QJT_disc (АДВЕКТИВНАЯ форма, BUG-012).

    J_j = Σ_α [ μ_JT,α^{j-1/2}·Φ⁺_{α,j-1/2}·(p_j - p_{j-1})
              + μ_JT,α^{j+1/2}·Φ⁻_{α,j+1/2}·(p_{j+1} - p_j) ]   [Вт]

    Каждое слагаемое содержит ПЕРЕПАД давления на грани, а не само p:
    источник eq:main_QJT_muJT записан поточечно, через градиент давления,
    и дискретизация обязана воспроизводить именно эту форму. Прежняя
    запись J_j = J_{j+1/2} - J_{j-1/2} с J_f = Σ_α μ_JT·<Φ_α·p>_f
    дискретизировала div(μ_JT·Φ·p) и давала лишний член μ_JT·p_j·D_j,
    где D_j = Φ_{j+1/2} - Φ_{j-1/2} (BUG-012).

    Контрольное свойство: при однородном p член обращается в нуль
    тождественно — каждое слагаемое содержит разность давлений.

    Коэффициент μ_JT берётся из ячейки выше по потоку СВОЕЙ фазы.

    Граничные грани (ssec:bc_disc, «Источниковые члены на граничных
    гранях»). В отличие от температуры и состава, давление за обеими
    границами ЗАДАНО, поэтому обе граничные грани дают ненулевой вклад:
      - забой: p за гранью = p_wf, выше по потоку — ячейка 0;
      - контур: по знаку расхода (eq:bc_props_ext, 74):
            Q_α >= 0 (отток)  → μ_JT из ячейки N-1, p за гранью = p_ext;
            Q_α <  0 (приток) → μ_JT при условиях контура, p = p_ext.

    О полушаге на забое: перепад (p_0 - p_wf) набирается на половине
    пути (от центра ячейки 0 до грани), тогда как на внутренних гранях —
    между центрами. Поправки не требуется: длина пути уже учтена в Φ
    через проводимость грани (trans_well на ln(r_0/r_well) против
    trans_internal на ln(r_{j+1}/r_j)). См. постановку, «О полушаге».

    Возвращает J_jt [N].
    """
    J = np.zeros(N)

    for j in range(N):
        # ── Левая грань j-1/2 (индекс j): работает при Φ⁺ > 0 ──
        # Давление за гранью: p[j-1] для внутренней, p_wf для забоя.
        p_left = p_wf if j == 0 else p[j - 1]
        up_o_l = _upstream(Q_o[j], j) if j > 0 else 0
        up_g_l = _upstream(Q_g[j], j) if j > 0 else 0
        J[j] += (mu_JT_o[up_o_l] * max(Phi_o[j], 0.0) * (p[j] - p_left)
                 + mu_JT_g[up_g_l] * max(Phi_g[j], 0.0) * (p[j] - p_left))

        # ── Правая грань j+1/2 (индекс j+1): работает при Φ⁻ < 0 ──
        f = j + 1
        if f < N:
            p_right = p[f]
            mu_o_r = mu_JT_o[_upstream(Q_o[f], f)]
            mu_g_r = mu_JT_g[_upstream(Q_g[f], f)]
        else:
            # Контур: давление за гранью — контурное; μ_JT по знаку расхода
            p_right = ext['p']
            mu_o_r = mu_JT_o[-1] if Q_o[N] >= 0 else ext['mu_JT_o']
            mu_g_r = mu_JT_g[-1] if Q_g[N] >= 0 else ext['mu_JT_g']
        J[j] += (mu_o_r * min(Phi_o[f], 0.0) * (p_right - p[j])
                 + mu_g_r * min(Phi_g[f], 0.0) * (p_right - p[j]))

    return J


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

    V_j·ṁ_j = -ρ_g^ст·[ V_j·φ·(1-S_g)/B_o·(R_s^{n+1} - R_s^n)/Δt + R_j ],

    где пространственная часть — АДВЕКТИВНАЯ (eq:mdot_conv_face, BUG-012):

        R_j = G^{o,+}_{j-1/2}·(R_{s,j} - R_{s,j-1})
            + G^{o,-}_{j+1/2}·(R_{s,j+1} - R_{s,j}),

    G^o — поток нефтяного КОМПОНЕНТА [м³ст/с] (не расход фазы Q_o
    [м³пл/с]). Каждое слагаемое содержит РАЗНОСТЬ R_s на грани: источник
    (u_o/B_o)·∂R_s/∂r записан поточечно, через градиент состава. Прежняя
    запись (R_{j+1/2} - R_{j-1/2}) с R_f = <G^o·R_s>_f дискретизировала
    div(G^o·R_s) и давала лишний член R_{s,j}·(G^o_{j+1/2} - G^o_{j-1/2}).

    Контрольное свойство: при однородном R_s член обращается в нуль
    тождественно — это дискретный аналог утверждения постановки о том,
    что в однофазной зоне (R_s = R_s^0 = const) ṁ = 0 автоматически.

    Где берётся B_o. Во временном члене — из текущей ячейки, в
    пространственном множитель 1/B_o уже сидит внутри G^o и взят из
    ячейки выше по потоку. Асимметрия намеренная: временной член — это
    ЗАПАС нефти в ячейке, пространственный — ПОТОК через грань. Форма
    воспроизводит дискретное правило Лейбница
        (<G^o·R_s>_{j+1/2} - <G^o·R_s>_{j-1/2})
        - R_{s,j}·(G^o_{j+1/2} - G^o_{j-1/2}) = R_j
    точно (относительная невязка ~1e-15); вариант с общим множителем
    1/B_{o,j} даёт ~5e-3. См. постановку, «Где берётся B_o».

    Граничные грани:
      - забой: состав за гранью не задан (ни ячейки, ни ГУ по R_s),
        поэтому вклад забойной грани равен нулю. Приём R_s,left = R_s[0]
        (ячейка сама себе левый сосед) даёт это автоматически при любом
        знаке потока;
      - контур: роль R_{s,N} играет состав притока R_s^0 (eq:bc_Sg_ext).
        Брать Rs[N-1] нельзя — при p_{N-1} < p_b это состав
        дегазированной нефти вместо состава притока (DEBT-009).
    """
    phi = rock.porosity
    V = grid.volumes
    rho_g_std = pvt.rho_g_std

    # Временная часть: изменение растворённого газа в ячейке
    mdot_time = -rho_g_std * phi * So / Bo * (Rs - Rs_old) / dt

    # Конвективная часть: перенос R_s потоком нефтяного компонента,
    # адвективная форма — разности R_s на гранях (eq:mdot_conv_face)
    Gp = np.maximum(G_o, 0.0)
    Gm = np.minimum(G_o, 0.0)
    # Соседи по R_s. Слева от ячейки 0 она сама себе сосед — разность
    # нулевая, забойная грань вклада не даёт. Справа от N-1 — состав
    # притока из ГУ (DEBT-009).
    Rs_left = np.concatenate(([Rs[0]], Rs[:-1]))
    Rs_right = np.concatenate((Rs[1:], [Rs_ext]))

    R_adv = Gp[0:N] * (Rs - Rs_left) + Gm[1:N + 1] * (Rs_right - Rs)

    mdot = mdot_time + (-rho_g_std * R_adv / V)
    return -L * mdot


def _ref_assemble(grid, N, dt, T_old, T_ext, rho_cp_eff,
                  Q_T_internal, Q_T_ext, Phi_plus, Phi_minus,
                  J_jt, Q_ad, Q_deg):
    """Коэффициенты СЛАУ. eq:tridiag_a, eq:tridiag_b, eq:tridiag_c, eq:tridiag_d.

    a_j = -Q_T_{j-1/2} - Φ⁺_{j-1/2}
    c_j = -Q_T_{j+1/2} + Φ⁻_{j+1/2}
    b_j = V_j·(ρcp)_eff/Δt + Q_T_{j-1/2} + Q_T_{j+1/2} + Φ⁺_{j-1/2} - Φ⁻_{j+1/2}
    d_j = V_j·(ρcp)_eff/Δt·T_j^n + J_j + V_j·(Q_ad + Q_deg)

    АДВЕКТИВНАЯ форма (BUG-012). В b_j участвуют ТЕ ЖЕ грани, что в a_j и
    c_j: Φ⁺ с левой грани j-1/2, Φ⁻ с правой j+1/2. Это прямое следствие
    eq:energy_conv_face, где вклад каждой грани содержит разность
    температур. В дивергентной записи в b_j стояли бы противоположные
    грани (Φ⁺_{j+1/2} - Φ⁻_{j-1/2}), и разность двух версий b_j равнялась
    бы ровно D_j = Φ_{j+1/2} - Φ_{j-1/2} — паразитному члену.

    Диагональное преобладание (eq:diag_dominance): для ВНУТРЕННИХ ячеек
    выполняется равенство b_j - |a_j| - |c_j| = V_j·(ρcp)_eff/Δt > 0 —
    кондуктивные и конвективные вклады сокращаются полностью. Оно
    безусловно: не зависит ни от Δt, ни от величины потоков. В граничных
    ячейках связь с одной стороны отсутствует, и запас там больше.

    Ожидаемые знаки: a <= 0, c <= 0, b > 0.

    Граничные условия (ssec:bc_disc, подпараграф «Температура»):
      - забой, j=0: ∂T/∂r = 0. Кондуктивный поток через левую грань
        обнуляется (Q_λ,1/2 = 0), связи слева нет → a[0] = 0.
        Конвективного вклада забойная грань НЕ даёт вовсе: слева ячейки
        нет, а условие Неймана означает отсутствие перепада T через эту
        грань. В адвективной форме каждое слагаемое пропорционально
        разности T соседей, поэтому член грани 1/2 тождественно нулевой.
      - контур, j=N-1: T|_Rext = T_ext (Дирихле). Известная температура
        уходит в правую часть: кондуктивный вклад Q_T_ext·T_ext и
        конвективный (-Φ⁻[N])·T_ext. Связи справа нет → c[N-1] = 0.
      - N = 1 (вырожденный случай): единственная ячейка, обе грани
        граничные. Левая вклада не даёт, правая (контур) даёт его ОДИН
        раз. Раздельные блоки ниже дублировали бы или теряли его, поэтому
        случай выделен явной ветвью.
    """
    V = grid.volumes

    a = np.zeros(N)
    b = np.zeros(N)
    c = np.zeros(N)
    d = np.zeros(N)

    # Накопительный член [Вт/К]. Δt — ФАКТИЧЕСКИЙ шаг, с которым
    # собрана матрица (при A-retry это dt_sub, а не шаг расписания).
    cap = V * rho_cp_eff / dt

    # ── Вырожденный случай N = 1 ──
    # b_0 = cap + Q_T_ext - Φ⁻_1;  d_0 += (Q_T_ext - Φ⁻_1)·T_ext
    if N == 1:
        b[0] = cap[0] + Q_T_ext - Phi_minus[1]
        d[0] = (cap[0] * T_old[0]
                + Q_T_ext * T_ext
                + (-Phi_minus[1]) * T_ext
                + J_jt[0] + V[0] * (Q_ad[0] + Q_deg[0]))
        return a, b, c, d

    # ── Внутренние ячейки j = 1..N-2 ──
    for j in range(1, N - 1):
        Q_T_L = Q_T_internal[j - 1]
        Q_T_R = Q_T_internal[j]

        a[j] = -Q_T_L - Phi_plus[j]
        c[j] = -Q_T_R + Phi_minus[j + 1]
        b[j] = cap[j] + Q_T_L + Q_T_R + Phi_plus[j] - Phi_minus[j + 1]
        d[j] = cap[j] * T_old[j] + J_jt[j] + V[j] * (Q_ad[j] + Q_deg[j])

    # ── Забой j=0: Нейман ──
    # Забойная грань (индекс 0) конвективного вклада не даёт — из b
    # уходят ОБА слагаемых, что стояли в дивергентной версии
    # (+Φ⁺[0] и -Φ⁻[0]). Остаётся только правая грань 1.
    Q_T_R0 = Q_T_internal[0]

    a[0] = 0.0
    c[0] = -Q_T_R0 + Phi_minus[1]
    b[0] = cap[0] + Q_T_R0 - Phi_minus[1]
    d[0] = cap[0] * T_old[0] + J_jt[0] + V[0] * (Q_ad[0] + Q_deg[0])

    # ── Контур j=N-1: Дирихле ──
    Q_T_LN = Q_T_internal[-1]

    a[N - 1] = -Q_T_LN - Phi_plus[N - 1]
    c[N - 1] = 0.0
    b[N - 1] = cap[N - 1] + Q_T_LN + Q_T_ext + Phi_plus[N - 1] - Phi_minus[N]
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

    # Забойное давление задано НА ГРАНИ и входит в JT-вклад забойной
    # грани как значение "за гранью" (eq:QJT_disc, ssec:bc_disc).
    # Для температуры и состава такого значения нет — там вклад нулевой.
    p_wf = bc.well.boundary_pressure(st, grid, pvt, None)

    J_jt = _ref_jt(Phi_o, Phi_g, props['mu_JT_o'], props['mu_JT_g'],
                   hydro_result.Q_o, hydro_result.Q_g, st.p, N, ext, p_wf)

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

    assert np.isclose(total_actual, total_scheduled, rtol=1e-12, atol=0.0), (
        f"{example}: сумма dt по {len(counter.dt_calls)} вызовам = "
        f"{total_actual:g} с, расписание = {total_scheduled:g} с")

    # Дробление действительно произошло: вызовов больше, чем шагов
    # интегрирования, и среди них есть шаги короче штатного.
    dt_min = min(counter.dt_calls)
    dt_max = max(counter.dt_calls)
    assert dt_min < dt_max, (
        f"{example}: ожидалось дробление A-retry, но все вызовы прошли "
        f"с одинаковым dt={dt_max:g} с — конфиг или гидродинамика изменились")
