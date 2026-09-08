"""Аналитика двухфазного стационара — пример 05 (Standing PVT + табличная ОФП).

Постановка та же, что в примере 03: те же PVT Стендинга, тот же режим
(Rs0 = 50, p_wf = 8 МПа < pb = 9.43 МПа). Отличается ровно один модуль —
ОФП берутся из relperm.csv вместо аналитических формул Кори. Поэтому здесь
проверяется не «другая физика», а СПРАВЕДЛИВОСТЬ ТЕХ ЖЕ СООТНОШЕНИЙ при
замене замыкающей зависимости k_r(S_g).

──────────────────────────────────────────────────────────────────
Что переносится из 03 дословно

Все выкладки опираются на стационарность компонентных потоков
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
Что меняется: пункт B (насыщенность)

Локальное условие GOR = Rs0, расписанное через подвижности (eq. 8-9
problem_statement.tex), даёт алгебраическое уравнение на S_g:

    k_rg(S_g)/k_ro(S_g) = [Rs0 - Rs(p)] · mu_g·Bg / (mu_o·Bo).        (B)

ПРАВАЯ ЧАСТЬ ЗДЕСЬ ТА ЖЕ, ЧТО В ПРИМЕРЕ 03 — она определяется только PVT
и давлением, а PVT в 03 и 05 одинаковы. Меняется ЛЕВАЯ часть: обращается
другая функция. Отсюда главный физический вывод примера:

    S_g подстраивается под ОФП, отношение подвижностей — нет.

Численно: при том же p(r) насыщенность падает с 0.0804 (Кори) до 0.0140
(таблица), то есть в 5.7 раза, а дебит, фронт и температура совпадают
с 03 в четырёх значащих цифрах. Причина — поведение k_rg при малых S_g:

    Кори:    k_rg = 0.8·(S_g - 0.05)^2 / (1 - 0.25)^2   — порог S_gc и
             квадратичное вырождение, k_rg(0.014) = 0 (газ неподвижен!);
    таблица: k_rg ≈ 0.1·S_g на первом отрезке — линейный рост без порога,
             k_rg(0.014) = 1.4e-3.

Табличная ОФП делает газ подвижным сразу, поэтому для переноса того же
количества газа хватает вшестеро меньшей насыщенности.

──────────────────────────────────────────────────────────────────
Отличие от 03 в технике: замкнутость решения

В 03 функции ниже брали p(r) из расчёта и проверяли только соотношение (B).
Здесь дополнительно реализовано ПОЛНОСТЬЮ ЗАМКНУТОЕ решение (solve_closed):
подставив S_g(p) из (B) в уравнение для нефтяного компонента, получаем

    dp/d ln r = q_o/(2 pi k h) · mu_o(p) Bo(p) / k_ro(S_g(p)),          (2)

где правая часть — функция ТОЛЬКО p. Разделение переменных даёт дебит
без единой итерации:

    q_o = 2 pi k h/ln(R_e/r_w) · int_{p_wf}^{p_e} k_ro(S_g(p))/(mu_o Bo) dp. (3)

Это радиальный аналог функции Маскета (Мускат, «Течение однородных жидкостей
в пористых средах», гл. о двухфазном стационарном притоке). Профиль p(r)
затем восстанавливается интегрированием (2) от контура внутрь.

То есть в этом примере из расчёта не берётся НИЧЕГО: ни дебит, ни S_g,
ни давление. Тот же приём, что в примере 04 (pressure_gor_closure.py),
но с PVT по корреляциям вместо таблиц.

Запуск автономно:
    cd numerical_solver
    .venv\\Scripts\\python examples\\05_standing_table_rp\\two_phase_analytics.py
"""

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

# Замкнутое решение живёт в общем модуле examples/closed_form.py (см.
# комментарий ниже, где оно реэкспортируется). Путь к examples/ добавляем
# здесь, до импорта: при запуске через main.py он уже в sys.path, а при
# автономном запуске этого файла — ещё нет.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Порог, ниже которого ячейка считается однофазной. В однофазной зоне
# Sg равен нулю машинно (газ там не выделялся), так что порог отделяет
# "нет газа" от "есть газ", а не сглаживает шум.
SG_EPS = 1e-12


def _build_relperm(config):
    """Табличная ОФП примера 05 — тот же объект, что использует решатель.

    Пример 05 — комбинация C (табличная ОФП). Вариант с Кори разобран
    в примере 03, поэтому здесь падаем с внятным сообщением, а не
    поддерживаем молча.
    """
    if config.relperm.model != "table":
        raise ValueError(
            f"two_phase_analytics примера 05 рассчитан на табличную ОФП, "
            f"получено relperm.model = {config.relperm.model!r}")

    # Тот же конструктор, которым ОФП создаёт фабрика при сборке решателя:
    # аналитика обращает ровно ту интерполяцию таблицы, что стояла в расчёте,
    # а не её повторную реализацию по CSV.
    from gpn_multiphase_solver.factory import _create_relperm

    return _create_relperm(config)


def _kr_max_Sg(relperm, Sg_hi=0.999):
    """Верхняя граница поиска корня: S_g, при которой нефть ещё подвижна.

    Выше этой точки k_ro = 0 и отношение k_rg/k_ro обращается в
    бесконечность — брать её как правый конец брекета нельзя.
    """
    S = np.linspace(0.0, Sg_hi, 2000)
    kro = relperm.kro(S)
    dead = np.where(kro <= 0.0)[0]
    return float(S[dead[0]]) * 0.999 if dead.size else Sg_hi


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
    Rs_up[N] = Rs[-1]

    predicted = np.abs(hr.G_o) * (Rs0 - Rs_up)
    return predicted, np.abs(hr.G_free_gas)


# ── B. Насыщенность из локального замыкания ──────────────────────

def predict_saturation(history, config, pvt, relperm=None):
    """B. S_g из локального условия GOR = Rs0, поячеечно.

    Для каждой двухфазной ячейки решает уравнение (B) методом Брента,
    подставляя ЧИСЛЕННОЕ давление. Это проверка самого замыкания,
    отделённая от точности профиля p(r).

    Возвращает (indices, Sg_num, Sg_pred).
    """
    if relperm is None:
        relperm = _build_relperm(config)
    st = history.states[-1]
    p, Sg, Rs = st.p, st.Sg, st.Rs
    Rs0 = config.initial_conditions.Rs0
    S_hi = _kr_max_Sg(relperm)

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
        # Правая часть совпадает с примером 03 — PVT там те же.
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


# ── Замкнутое решение: дебит и профиль без данных расчёта ────────
#
# Реализация вынесена в общий модуль examples/closed_form.py: вывод
# опирается только на стационарность потоков и условие GOR = Rs0, поэтому
# не зависит ни от источника PVT, ни от вида ОФП и применим ко всем
# примерам 03-10. Здесь оставлен реэкспорт, чтобы прежние вызовы
# tpa.solve_closed(...) в main.py и closed_form_convergence.py работали.
#
# Одно отличие от прежней локальной версии: фронт r_b теперь определяется
# условием p(r_b) = pb, а не обнулением аналитической S_g. Для табличной
# ОФП этого примера оба критерия дают одно и то же (0.1986 м), но для
# Кори с порогом S_gc второй занижает r_b на 13 % — см. docstring
# closed_form.py.

from closed_form import Closure, solve_closed, _CACHE  # noqa: E402,F401


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

    # Независимое предсказание наклона из потока (закон Дарси, eq. 8).
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


# ── Сводный отчёт ────────────────────────────────────────────────

def report(history, grid, config, pvt) -> dict:
    """Все проверки с печатью в консоль. Возвращает сводку."""
    Rs0 = config.initial_conditions.Rs0
    relperm = _build_relperm(config)

    print("── Аналитика двухфазного стационара (табличная ОФП) ──")

    # A. Газовый фактор
    gor_w, gor_e = compute_gor(history)
    print(f"  A. GOR(забой)  = {gor_w:.8f}   |GOR - Rs0| = {abs(gor_w - Rs0):.2e}")
    print(f"     GOR(контур) = {gor_e:.8f}   Rs0 = {Rs0:.1f} м³ст/м³ст")

    pred, act = compute_free_gas_prediction(history, config)
    # Сравниваем только там, где газ есть: в однофазной зоне обе величины
    # нулевые и относительная ошибка не определена.
    nz = act > 1e-12
    rel_gas = float(np.max(np.abs(pred[nz] - act[nz]) / act[nz])) if nz.any() else 0.0
    print(f"     своб. газ = |G^o|·(Rs0-Rs): max отн. откл. = {rel_gas:.2e}")

    # B. Насыщенность при численном давлении — проверка самого замыкания
    idx, Sg_num, Sg_pred = predict_saturation(history, config, pvt, relperm)
    ok = ~np.isnan(Sg_pred)
    dSg = float(np.max(np.abs(Sg_pred[ok] - Sg_num[ok]))) if ok.any() else np.nan
    rel = (np.abs(Sg_pred[ok] - Sg_num[ok]) / Sg_num[ok]).max() * 100 if ok.any() else np.nan
    print(f"  B. S_g из GOR=Rs0 при численном p: {ok.sum()} ячеек, "
          f"max|ΔS_g| = {dSg:.2e} ({rel:.3f} %)")

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

    # E. Замкнутое решение — ничего из расчёта не используется
    r = grid.r_centers
    cl = solve_closed(config, pvt, relperm, r)
    p_num = history.states[-1].p
    q_num = abs(history.hydro_results[-1].G_o[0])
    dp_max = float(np.abs(cl["p"] - p_num).max())
    dep = config.initial_conditions.p0 - config.time.history[0].p_wf
    print("  E. Замкнутое решение (дебит квадратурой, профиль ОДУ):")
    print(f"     q_o = {cl['q_o']:.6e} м³ст/с (аналитика) vs "
          f"{q_num:.6e} (расчёт), расхожд. {abs(cl['q_o']-q_num)/q_num*100:.3f} %")
    print(f"     max|p_ана - p_чис| = {dp_max/1e3:.2f} кПа "
          f"({dp_max/dep*100:.3f} % депрессии)")
    print(f"     S_g макс = {cl['Sg'].max():.5f} (аналитика) vs "
          f"{history.states[-1].Sg.max():.5f} (расчёт)")

    return dict(gor_well=gor_w, gor_ext=gor_e, rel_free_gas=rel_gas,
                dSg_max=dSg, front=fr, dupuit=dup, closed=cl,
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
