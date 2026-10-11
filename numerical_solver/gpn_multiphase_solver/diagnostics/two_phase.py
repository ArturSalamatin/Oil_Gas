"""Аналитика двухфазного стационара (DEBT-011: из examples/two_phase_analytics.py).

Все выкладки опираются на стационарность компонентных потоков и НЕ
используют вид k_r(S_g) вообще, поэтому проверка применима к любой
комбинации PVT × ОФП. Единственное место, где вид ОФП входит, — пункт B:
там уравнение обращается численно, тем же объектом ОФП, которым считалась
задача (`Simulator.relperm`).

ЧТО ПОКАЗЫВАЕТ СРАВНЕНИЕ ПРИМЕРОВ 03 И 05. Постановка у них одна (те же
PVT Стендинга, Rs0 = 50, p_wf = 8 МПа < pb = 9.43 МПа), отличается ровно
ОФП: аналитические формулы Кори против relperm.csv. Насыщенность при этом
падает с 0.0804 до 0.0140, то есть в 5.7 раза, а дебит, фронт и
температура совпадают в четырёх значащих цифрах:

    S_g подстраивается под ОФП, отношение подвижностей — нет.

Причина — поведение k_rg при малых S_g:

    Кори:    k_rg = 0.8·(S_g - 0.05)^2 / (1 - 0.25)^2 — порог S_gc и
             квадратичное вырождение, k_rg(0.014) = 0 (газ неподвижен!);
    таблица: k_rg ≈ 0.1·S_g на первом отрезке — линейный рост без порога,
             k_rg(0.014) = 1.4e-3.

Табличная ОФП делает газ подвижным сразу, поэтому для переноса того же
количества газа хватает вшестеро меньшей насыщенности. Отсюда и разная
точность пункта B: max|ΔS_g| = 1.93e-03 у Кори против 1.06e-12 у таблицы —
у Кори порог подвижности делает уравнение (B) плохо обусловленным у
фронта (d(k_rg/k_ro)/dS там почти нулевая), у таблицы такой зоны нет.
Это свойство ОФП, а не дефект проверки.

──────────────────────────────────────────────────────────────────
Проверки, не зависящие от вида ОФП
(G^o = const, G^g = const по r) и не используют вид k_r(S_g) вообще:

A. ГАЗОВЫЙ ФАКТОР.  На контуре газ входит только растворённым (S_g = 0,
   Rs_ext = Rs0), а G^g и G^o не зависят от r, значит на любой грани

       GOR = q_g,ст / q_o,ст = Rs0 = 50.

   Следствие для потока свободного газа:  G^своб = |G^o|·[Rs0 - Rs(p)].

C. ФРОНТ РАЗГАЗИРОВАНИЯ.  Газ есть ровно там, где p < pb; радиус фронта
   получается экстраполяцией однофазного профиля Дюпюи от контура внутрь.

D. ДЮПЮИ В ОДНОФАЗНОЙ ЗОНЕ.  Вне зоны разгазирования Rs = Rs0, k_ro = 1,
   и наклон предсказывается из потока: dp/d ln r = |G^o| mu_o Bo/(2 pi k h).

──────────────────────────────────────────────────────────────────
B. НАСЫЩЕННОСТЬ — единственный пункт, где входит вид ОФП

Локальное условие GOR = Rs0, расписанное через подвижности (eq:flux_oil,
eq:flux_gas problem_statement.tex), даёт алгебраическое уравнение на S_g:

    k_rg(S_g)/k_ro(S_g) = [Rs0 - Rs(p)] · mu_g·Bg / (mu_o·Bo).        (B)

Правая часть определяется только PVT и давлением. Левая — обращаемая
функция ОФП; её передаёт вызывающий — тот объект, которым считалась задача
(`Simulator.relperm`), поэтому уравнение обращает ровно ту зависимость, что
стояла в расчёте, а не её повторную реализацию.

──────────────────────────────────────────────────────────────────
E. ЗАМКНУТОЕ РЕШЕНИЕ — из расчёта не берётся НИЧЕГО

Подставив S_g(p) из (B) в уравнение для нефтяного компонента, получаем

    dp/d ln r = q_o/(2 pi k h) · mu_o(p) Bo(p) / k_ro(S_g(p)),          (2)

где правая часть — функция ТОЛЬКО p. Разделение переменных даёт дебит
без единой итерации:

    q_o = 2 pi k h/ln(R_e/r_w) · int_{p_wf}^{p_e} k_ro(S_g(p))/(mu_o Bo) dp. (3)

Это радиальный аналог функции Маскета (Мускат, «Течение однородных жидкостей
в пористых средах», гл. о двухфазном стационарном притоке). Профиль p(r)
затем восстанавливается интегрированием (2) от контура внутрь.

Ни дебит, ни S_g, ни давление из расчёта не используются. Реализация —
diagnostics/closed_form.py.

ПРИМЕНИМОСТЬ. Проверка требует двухфазного стационара: Rs0 > 0 и
p_wf < pb, иначе газа нет и обращать (B) не на чем. Для однофазных
сценариев (Rs0 = 0) проверка не имеет смысла — report это сообщает, а не
падает.
"""

import numpy as np
from scipy.optimize import brentq

from .closed_form import kr_max_Sg

# Порог, ниже которого ячейка считается однофазной. В однофазной зоне
# Sg равен нулю машинно (газ там не выделялся), так что порог отделяет
# "нет газа" от "есть газ", а не сглаживает шум.
SG_EPS = 1e-12


# ── A. Газовый фактор ────────────────────────────────────────────

def compute_gor(history):
    """A. Газовый фактор на забое и на контуре в финальном состоянии.

    Возвращает (GOR_well, GOR_ext). В стационаре оба равны Rs0.
    """
    hr = history.hydro_results[-1]
    return hr.G_g[0] / hr.G_o[0], hr.G_g[-1] / hr.G_o[-1]


def compute_free_gas_prediction(history, config):
    """A. Свободный газ на гранях: |G^o|·(Rs0 - Rs_up) против расчёта.

    Возвращает (predicted, actual) — оба [N+1], м³ст/с по модулю.
    Грань f при потоке к скважине берёт Rs из правой ячейки (выше по потоку).
    """
    hr = history.hydro_results[-1]
    Rs = history.states[-1].Rs
    Rs0 = config.initial_conditions.Rs0
    N = len(Rs)

    Rs_up = np.empty(N + 1)
    Rs_up[:N] = Rs
    # Контур: при притоке (G_o < 0) выше по потоку лежит контур с составом
    # Rs0, поэтому predicted = |G_o|·(Rs0 - Rs0) = 0 — через контур свободный
    # газ не поступает (Sg_ext = 0, k_rg = 0). Безусловный Rs[-1] давал бы
    # ложную невязку при разгазировании у контура — DEBT-009.
    Rs_up[N] = Rs[-1] if hr.G_o[N] >= 0 else Rs0

    predicted = np.abs(hr.G_o) * (Rs0 - Rs_up)
    return predicted, np.abs(hr.G_free_gas)


# ── B. Насыщенность из локального замыкания ──────────────────────

def predict_saturation(history, config, pvt, relperm):
    """B. S_g из локального условия GOR = Rs0, поячеечно.

    Для каждой двухфазной ячейки решает уравнение (B) методом Брента,
    подставляя ЧИСЛЕННОЕ давление. Это проверка самого замыкания,
    отделённая от точности профиля p(r).

    Возвращает (indices, Sg_num, Sg_pred).
    """
    st = history.states[-1]
    p, Sg, Rs = st.p, st.Sg, st.Rs
    Rs0 = config.initial_conditions.Rs0
    S_hi = kr_max_Sg(relperm)

    idx = np.where(Sg > SG_EPS)[0]
    Sg_pred = np.full(len(idx), np.nan)

    for i, j in enumerate(idx):
        pj = np.array([p[j]])
        Rs_j = np.array([Rs[j]])
        Rs_eq = pvt.Rs_eq(pj)[0]
        mu_o = pvt.mu_o(pj, Rs_j)[0]
        mu_g = pvt.mu_g(pj)[0]
        Bo = pvt.Bo(pj, Rs_j)[0]
        Bg = pvt.Bg(pj)[0]

        # Требуемое отношение ОФП, чтобы суммарный газовый поток дал Rs0.
        ratio = (Rs0 - Rs_eq) * mu_g * Bg / (mu_o * Bo)

        def residual(S):
            S_arr = np.array([S])
            return relperm.krg(S_arr)[0] / relperm.kro(S_arr)[0] - ratio

        try:
            Sg_pred[i] = brentq(residual, 1e-14, S_hi, xtol=1e-14)
        except ValueError:
            # Корня в брекете нет — оставляем NaN, вызывающий код отфильтрует.
            pass

    return idx, Sg[idx], Sg_pred


# ── C, D. Фронт и Дюпюи ──────────────────────────────────────────

def dupuit_check(history, grid, config, pvt):
    """D. Проверка Дюпюи в однофазной зоне.

    Возвращает dict: slope_fit, slope_theory, max_dev, n_cells, mask.
    """
    st = history.states[-1]
    hr = history.hydro_results[-1]
    p, Sg, Rs = st.p, st.Sg, st.Rs
    r = grid.r_centers

    mask = Sg <= SG_EPS
    if mask.sum() < 3:
        return dict(slope_fit=np.nan, slope_theory=np.nan, max_dev=np.nan,
                    n_cells=int(mask.sum()), mask=mask)

    r1, p1 = r[mask], p[mask]
    slope_fit = float(np.polyfit(np.log(r1), p1, 1)[0])

    # Профиль Дюпюи, привязанный к самой дальней ячейке (там ГУ Дирихле)
    p_dup = p1[-1] + slope_fit * np.log(r1 / r1[-1])
    max_dev = float(np.max(np.abs(p1 - p_dup)))

    # Независимое предсказание наклона из потока (закон Дарси, eq:flux_oil).
    # В однофазной зоне Bo и mu_o постоянны, k_ro = 1.
    Bo = pvt.Bo(p1, Rs[mask])
    mu_o = pvt.mu_o(p1, Rs[mask])
    slope_theory = float(abs(hr.G_o[-1]) * mu_o.mean() * Bo.mean()
                         / (2.0 * np.pi * config.rock.permeability
                            * config.geometry.h))

    return dict(slope_fit=slope_fit, slope_theory=slope_theory,
                max_dev=max_dev, n_cells=int(mask.sum()), mask=mask)


def degassing_front(history, grid, config, pvt):
    """C. Радиус фронта разгазирования: p(r_b) = pb.

    Возвращает dict: r_b_interp (интерполяция численного профиля),
    r_b_formula (экстраполяция однофазного Дюпюи от контура), pb,
    cells_below_pb, cells_with_gas.
    """
    st = history.states[-1]
    p, Sg = st.p, st.Sg
    r = grid.r_centers
    Rs0 = config.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])

    # Интерполяция r(p = pb): ищем пару соседних ячеек, между которыми
    # давление пересекает pb, и интерполируем линейно по ln r (профиль
    # логарифмичен). np.interp здесь не годится: он требует возрастающие
    # узлы, а p и ln r монотонны в противоположные стороны.
    r_b_interp = np.nan
    j = int(np.searchsorted(p, pb))          # p возрастает с ростом r
    if 0 < j < len(p):
        w = (pb - p[j - 1]) / (p[j] - p[j - 1])
        r_b_interp = float(np.exp(np.log(r[j - 1])
                                  + w * (np.log(r[j]) - np.log(r[j - 1]))))

    # Экстраполяция однофазного профиля внутрь от опоры в однофазной зоне:
    #   p(r) = p_ref + slope·ln(r/r_ref)  ⇒  r_b = r_ref·exp[(pb - p_ref)/slope].
    # Опора — самая дальняя ячейка. От забоя экстраполировать нельзя:
    # в двухфазной зоне k_ro < 1 и наклон другой.
    dup = dupuit_check(history, grid, config, pvt)
    slope = dup["slope_fit"]
    if slope and dup["n_cells"] >= 3:
        r_ref, p_ref = r[dup["mask"]][-1], p[dup["mask"]][-1]
        r_b_formula = float(r_ref * np.exp((pb - p_ref) / slope))
    else:
        r_b_formula = np.nan

    return dict(
        r_b_interp=r_b_interp, r_b_formula=r_b_formula, pb=pb,
        cells_below_pb=np.where(p < pb)[0],
        cells_with_gas=np.where(Sg > SG_EPS)[0],
    )
