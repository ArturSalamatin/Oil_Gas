"""Аналитические соотношения двухфазного стационара — пример 03.

Все три проверки опираются на одно наблюдение: гидродинамика выходит на
стационар за 1-2 часа модельного времени, а в стационаре компонентные
потоки G^o и G^g постоянны по r (дивергенция = 0, накопление = 0).

A. ГАЗОВЫЙ ФАКТОР.  На контуре газ входит только растворённым, при
   Rs_ext = Rs0. Раз G^g и G^o постоянны по r, то на ЛЮБОЙ грани, включая
   забой:

       GOR = q_g,ст / q_o,ст = Rs0.

   Разгазирование в ПЗП само по себе НЕ повышает газовый фактор скважины:
   весь свободный газ на забое — это газ, вышедший из проходящей нефти.
   Следствие для свободного газа на грани r:

       G^своб.газ(r) = |G^o| · [Rs0 - Rs(p(r))].

B. НАСЫЩЕННОСТЬ.  Распишем GOR = Rs0 через подвижности на грани
   (eq. 8-9 problem_statement.tex):

       G^g / G^o = Rs + (k_rg/(mu_g·Bg)) / (k_ro/(mu_o·Bo)) = Rs0,

   откуда ЛОКАЛЬНОЕ алгебраическое уравнение на S_g при известном p:

       k_rg(S_g) / k_ro(S_g) = [Rs0 - Rs(p)] · mu_g·Bg / (mu_o·Bo).

   Насыщенность в стационаре не требует решения PDE — она определяется
   давлением поточечно. Отсюда же понятно, почему пример 05 (табличная
   ОФП) даёт тот же дебит при вшестеро меньшей S_g: подстраивается
   насыщенность, а отношение подвижностей фиксировано правой частью.

C. ФРОНТ РАЗГАЗИРОВАНИЯ.  Газ есть ровно там, где p < pb. Радиус фронта
   получается экстраполяцией ОДНОФАЗНОГО профиля Дюпюи внутрь, от контура:

       r_b = R_e · exp[ (pb - p_0) / (dp/d ln r) ].

   Внимание: экстраполировать от ЗАБОЯ этой же формулой нельзя. В
   двухфазной зоне k_ro < 1, подвижность нефти падает и наклон растёт
   (в базовом конфиге с 1.913e6 до 2.174e6 Па, то есть на 14 %), так что
   p_wf + slope·ln(r/r_w) завысит r_b примерно вдвое. Однофазный наклон
   применим только там, где он и постоянен — вне зоны разгазирования.

D. ДЮПЮИ В ОДНОФАЗНОЙ ЗОНЕ.  При co_undersaturated = 0 нефть несжимаема,
   а вне зоны разгазирования Rs = Rs0 = const, значит Bo и mu_o постоянны
   и уравнение линейно — ровно как в примере 02. Наклон профиля
   предсказывается независимо, из потока:

       dp/d ln r = |G^o| · mu_o · Bo / (2 pi k h).

Запуск автономно:
    cd numerical_solver
    .venv\\Scripts\\python examples\\03_standing_corey\\two_phase_analytics.py
"""

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

# Порог, ниже которого ячейка считается однофазной.
# Sg в однофазной зоне равен нулю машинно (газ там не выделялся вовсе),
# так что порог отделяет "нет газа" от "есть газ", а не сглаживает шум.
SG_EPS = 1e-12


def _build_relperm(config):
    """Собрать модель ОФП из конфига — нужна для обращения k_rg/k_ro.

    Пример 03 — комбинация A (Corey). Табличная ОФП разбирается в примере 05,
    там же и её вариант этой проверки, поэтому здесь не поддерживаем молча,
    а падаем с внятным сообщением.
    """
    from gpn_multiphase_solver.pvt.relperm import CoreyRP

    rp = config.relperm
    if rp.model != "corey":
        raise ValueError(
            f"two_phase_analytics рассчитан на ОФП Кори, получено "
            f"relperm.model = {rp.model!r}")
    return CoreyRP(S_or=rp.S_or, S_gc=rp.S_gc, n_o=rp.n_o, n_g=rp.n_g,
                   kro_max=rp.kro_max, krg_max=rp.krg_max)


def compute_gor(history):
    """A. Газовый фактор на забое и на контуре в финальном состоянии.

    Возвращает (GOR_well, GOR_ext). В стационаре оба равны Rs0.
    """
    hr = history.hydro_results[-1]
    return hr.G_g[0] / hr.G_o[0], hr.G_g[-1] / hr.G_o[-1]


def compute_free_gas_prediction(history, config):
    """A. Свободный газ на гранях: |G^o|·(Rs0 - Rs_up) против расчёта.

    Возвращает (predicted, actual) — оба [N+1], м³ст/с по модулю.
    Upstream грани f при потоке к скважине — ячейка f (правая).
    """
    hr = history.hydro_results[-1]
    Rs = history.states[-1].Rs
    Rs0 = config.initial_conditions.Rs0
    N = len(Rs)

    # Rs в ячейке выше по потоку: для всех граней, кроме контурной, это
    # правая ячейка (поток направлен к скважине, G^o < 0).
    Rs_up = np.empty(N + 1)
    Rs_up[:N] = Rs
    Rs_up[N] = Rs[-1]

    predicted = np.abs(hr.G_o) * (Rs0 - Rs_up)
    return predicted, np.abs(hr.G_free_gas)


def predict_saturation(history, config, pvt):
    """B. S_g из локального условия GOR = Rs0, поячеечно.

    Для каждой двухфазной ячейки решает
        k_rg(S)/k_ro(S) = [Rs0 - Rs(p)] · mu_g·Bg / (mu_o·Bo)
    методом Брента. Возвращает (indices, Sg_num, Sg_pred).

    В ячейках у самого фронта k_rg → 0 и уравнение плохо обусловлено:
    производная d(k_rg/k_ro)/dS там почти нулевая, поэтому ошибка
    предсказания растёт именно к фронту, а не к забою.
    """
    relperm = _build_relperm(config)
    st = history.states[-1]
    p, Sg, Rs = st.p, st.Sg, st.Rs
    Rs0 = config.initial_conditions.Rs0

    # Верхняя граница поиска: за S_g = 1 - S_or нефть неподвижна (k_ro = 0)
    # и отношение k_rg/k_ro обращается в бесконечность.
    S_hi = 1.0 - config.relperm.S_or - 1e-6

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

        # Требуемое отношение ОФП, чтобы суммарный газовый поток дал Rs0
        ratio = (Rs0 - Rs_eq) * mu_g * Bg / (mu_o * Bo)

        def residual(S):
            S_arr = np.array([S])
            return relperm.krg(S_arr)[0] / relperm.kro(S_arr)[0] - ratio

        try:
            Sg_pred[i] = brentq(residual, 1e-14, S_hi, xtol=1e-12)
        except ValueError:
            # Корня в интервале нет — оставляем NaN, вызывающий код
            # отфильтрует. Бывает у фронта, где ratio ниже машинного нуля.
            pass

    return idx, Sg[idx], Sg_pred


def dupuit_check(history, grid, config, pvt):
    """D. Проверка Дюпюи в однофазной зоне.

    Возвращает dict: slope_fit, slope_theory, max_dev, n_cells,
    а также mask однофазных ячеек.
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

    # Независимое предсказание наклона из потока (закон Дарси в форме eq. 8).
    # В однофазной зоне Bo и mu_o постоянны, поэтому берём их в любой ячейке.
    Bo = pvt.Bo(p1, Rs[mask])
    mu_o = pvt.mu_o(p1, Rs[mask])
    k = config.rock.permeability
    h = config.geometry.h
    slope_theory = float(abs(hr.G_o[-1]) * mu_o.mean() * Bo.mean()
                         / (2.0 * np.pi * k * h))

    return dict(slope_fit=slope_fit, slope_theory=slope_theory,
                max_dev=max_dev, n_cells=int(mask.sum()), mask=mask)


def degassing_front(history, grid, config, pvt):
    """C. Радиус фронта разгазирования: p(r_b) = pb.

    Возвращает dict: r_b_interp (интерполяция численного профиля),
    r_b_formula (экстраполяция однофазного Дюпюи от контура),
    pb, cells_below_pb, cells_with_gas.

    Обе оценки должны совпадать: разгазирование включается ровно там,
    где давление падает ниже pb, никакой задержки в схеме нет.
    """
    st = history.states[-1]
    p, Sg = st.p, st.Sg
    r = grid.r_centers
    Rs0 = config.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])

    # Интерполяция r(p = pb) по численному профилю: ищем пару соседних
    # ячеек, между которыми давление пересекает pb, и линейно интерполируем
    # ln r по p (профиль логарифмичен, поэтому интерполяция именно по ln r).
    # np.interp здесь не годится: он требует возрастающий массив узлов, а
    # p и ln r монотонны в противоположные стороны, и молча даёт мусор.
    r_b_interp = np.nan
    j = int(np.searchsorted(p, pb))          # p возрастает с ростом r
    if 0 < j < len(p):
        w = (pb - p[j - 1]) / (p[j] - p[j - 1])
        r_b_interp = float(np.exp(np.log(r[j - 1])
                                  + w * (np.log(r[j]) - np.log(r[j - 1]))))

    # Экстраполяция однофазного профиля ВНУТРЬ, от опорной точки в
    # однофазной зоне: p(r) = p_ref + slope·ln(r/r_ref) ⇒
    #   r_b = r_ref·exp[(pb - p_ref)/slope].
    # Опора — самая дальняя ячейка (там ГУ Дирихле, p ≈ p_0). От забоя
    # экстраполировать нельзя: в двухфазной зоне наклон другой (см. docstring).
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


# Overlay здесь больше нет. Аналитика p и Sg (замкнутое решение) и Rs
# (равновесие) вынесена в общие модули examples/closed_form.py и
# examples/rs_analytics.py: эти выводы не зависят ни от вида PVT, ни от
# вида ОФП, поэтому одинаковы для всех сценариев с газом и ставятся
# самим example_runner. Здесь остаются проверки, которых в общей части
# нет: постоянство GOR по граням, наклон Дюпюи из потока, совпадение
# двух независимых оценок фронта.


def report(history, grid, config, pvt) -> dict:
    """Все четыре проверки с печатью в консоль. Возвращает сводку."""
    Rs0 = config.initial_conditions.Rs0

    print("── Аналитика двухфазного стационара ──")

    # A. Газовый фактор
    gor_w, gor_e = compute_gor(history)
    print(f"  A. GOR(забой)  = {gor_w:.8f}   |GOR - Rs0| = {abs(gor_w - Rs0):.2e}")
    print(f"     GOR(контур) = {gor_e:.8f}   Rs0 = {Rs0:.1f} м³ст/м³ст")

    pred, act = compute_free_gas_prediction(history, config)
    # Сравниваем только там, где газ есть: в однофазной зоне обе величины
    # равны нулю и относительная ошибка не определена.
    nz = act > 1e-12
    rel_gas = float(np.max(np.abs(pred[nz] - act[nz]) / act[nz])) if nz.any() else 0.0
    print(f"     своб. газ = |G^o|·(Rs0-Rs): max отн. откл. = {rel_gas:.2e}")

    # B. Насыщенность
    idx, Sg_num, Sg_pred = predict_saturation(history, config, pvt)
    ok = ~np.isnan(Sg_pred)
    dSg = float(np.max(np.abs(Sg_pred[ok] - Sg_num[ok]))) if ok.any() else np.nan
    print(f"  B. S_g из GOR=Rs0: {ok.sum()} ячеек, max|ΔS_g| = {dSg:.2e}")

    # C. Фронт
    fr = degassing_front(history, grid, config, pvt)
    same = np.array_equal(fr["cells_below_pb"], fr["cells_with_gas"])
    d_rb = abs(fr["r_b_formula"] - fr["r_b_interp"]) / fr["r_b_interp"]
    print(f"  C. фронт: r_b = {fr['r_b_interp']:.5f} м (интерп. профиля), "
          f"{fr['r_b_formula']:.5f} м (формула), расхожд. {d_rb*100:.2f} %")
    print(f"     pb = {fr['pb']/1e6:.4f} МПа; "
          f"ячейки p<pb и ячейки Sg>0 совпадают: {same}")

    # D. Дюпюи
    dup = dupuit_check(history, grid, config, pvt)
    rel_slope = abs(dup["slope_fit"] - dup["slope_theory"]) / dup["slope_theory"]
    print(f"  D. Дюпюи: {dup['n_cells']} однофазных ячеек, "
          f"max|p - Дюпюи| = {dup['max_dev']:.2e} Па")
    print(f"     наклон: {dup['slope_fit']:.5e} Па (профиль) vs "
          f"{dup['slope_theory']:.5e} Па (из G^o), отн. разн. {rel_slope:.2e}")

    return dict(gor_well=gor_w, gor_ext=gor_e, rel_free_gas=rel_gas,
                dSg_max=dSg, front=fr, dupuit=dup,
                sat_idx=idx, sat_num=Sg_num, sat_pred=Sg_pred)


# ── Автономный запуск ──
if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent
    SOLVER_ROOT = HERE.parents[1]
    sys.path.insert(0, str(SOLVER_ROOT))
    sys.path.insert(0, str(SOLVER_ROOT / "examples"))
    sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

    from gpn_multiphase_solver.io.config import load_config
    from gpn_multiphase_solver.factory import SimulatorFactory

    config = load_config(HERE / "config.json")
    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)

    report(history, sim._grid, config, sim._energy._pvt)
