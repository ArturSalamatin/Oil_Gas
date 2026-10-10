"""Аналитика двухфазного стационара — общая проверка для двухфазных примеров.

Все выкладки опираются на стационарность компонентных потоков и НЕ
используют вид k_r(S_g) вообще, поэтому проверка применима к любой
комбинации PVT × ОФП. Единственное место, где вид ОФП входит, — пункт B:
там уравнение обращается численно, тем же объектом ОФП, которым считалась
задача (`_create_relperm` из фабрики).

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
функция ОФП; она берётся у фабрики, поэтому уравнение обращает ровно ту
зависимость, что стояла в расчёте, а не её повторную реализацию.

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

Ни дебит, ни S_g, ни давление из расчёта не используются. Реализация — в
общем модуле examples/closed_form.py, здесь реэкспорт.

ПРИМЕНИМОСТЬ. Проверка требует двухфазного стационара: Rs0 > 0 и
p_wf < pb, иначе газа нет и обращать (B) не на чем. Для однофазных
сценариев (Rs0 = 0) проверка не имеет смысла — report это сообщает, а не
падает.

Запуск для конкретного примера:
    cd numerical_solver
    .venv\\Scripts\\python examples\\two_phase_analytics.py 03
"""

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

_EXAMPLES = Path(__file__).resolve().parent
_ROOT = _EXAMPLES.parent
for _p in (str(_ROOT), str(_EXAMPLES),
           str(_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Порог, ниже которого ячейка считается однофазной. В однофазной зоне
# Sg равен нулю машинно (газ там не выделялся), так что порог отделяет
# "нет газа" от "есть газ", а не сглаживает шум.
SG_EPS = 1e-12


def _build_relperm(config):
    """ОФП задачи — тот же объект, что использует решатель.

    Тот же конструктор, которым ОФП создаёт фабрика при сборке решателя:
    аналитика обращает ровно ту зависимость k_r(S_g), что стояла в расчёте,
    а не её повторную реализацию по формулам или CSV. Фабрика собирает и
    Кори, и таблицу, поэтому проверка работает при любой модели ОФП.
    """
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
    # Контур: при притоке (G_o < 0) выше по потоку лежит контур с составом
    # Rs0, поэтому predicted = |G_o|·(Rs0 - Rs0) = 0 — через контур свободный
    # газ не поступает (Sg_ext = 0, k_rg = 0). Безусловный Rs[-1] давал бы
    # ложную невязку при разгазировании у контура — DEBT-009.
    Rs_up[N] = Rs[-1] if hr.G_o[N] >= 0 else Rs0

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
# сценариям с газом. Здесь — реэкспорт для вызовов tpa.solve_closed(...).
# Фронт r_b определяется условием p(r_b) = pb, а не обнулением
# аналитической S_g — см. docstring closed_form.py.

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


# ── Сводный отчёт ────────────────────────────────────────────────

def report(history, grid, config, pvt) -> dict:
    """Все проверки с печатью в консоль. Возвращает сводку."""
    Rs0 = config.initial_conditions.Rs0

    print(f"── Аналитика двухфазного стационара "
          f"(ОФП: {config.relperm.model}) ──")

    # Однофазный сценарий: газа нет, обращать (B) не на чем, GOR не
    # определён (G_g = 0). Сообщаем, а не падаем — так же поступает
    # rs_analytics при Rs0 = 0.
    if Rs0 <= 0.0:
        print(f"  не проверяется: Rs0 = {Rs0} — растворённого газа нет, "
              f"сценарий однофазный")
        return dict(applicable=False)

    relperm = _build_relperm(config)

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
    # Та же депрессия, по которой solve_closed строит решение (FEAT-022);
    # p_wf берётся из решения — при управлении по дебиту оно вычислено (FEAT-020)
    dep = config.initial_conditions.p0 - cl["p_wf"]
    print("  E. Замкнутое решение (дебит квадратурой, профиль ОДУ):")
    print(f"     q_o = {cl['q_o']:.6e} м³ст/с (аналитика) vs "
          f"{q_num:.6e} (расчёт), расхожд. {abs(cl['q_o']-q_num)/q_num*100:.3f} %")
    print(f"     max|p_ана - p_чис| = {dp_max/1e3:.2f} кПа "
          f"({dp_max/dep*100:.3f} % депрессии)")
    print(f"     S_g макс = {cl['Sg'].max():.5f} (аналитика) vs "
          f"{history.states[-1].Sg.max():.5f} (расчёт)")

    return dict(applicable=True,
                gor_well=gor_w, gor_ext=gor_e, rel_free_gas=rel_gas,
                dSg_max=dSg, front=fr, dupuit=dup, closed=cl,
                sat_idx=idx, sat_num=Sg_num, sat_pred=Sg_pred)


def _resolve_example(name_or_prefix: str) -> Path:
    """examples/<имя>/ по полному имени или числовому префиксу ('03').

    Пользователю не нужно печатать '03_standing_corey' целиком.
    Ошибка при отсутствии или неоднозначности префикса.
    """
    exact = _EXAMPLES / name_or_prefix
    if exact.is_dir():
        return exact
    matches = sorted(d for d in _EXAMPLES.iterdir()
                     if d.is_dir() and d.name.startswith(name_or_prefix))
    if not matches:
        raise SystemExit(f"нет примера '{name_or_prefix}'")
    if len(matches) > 1:
        raise SystemExit(f"неоднозначно: {[m.name for m in matches]}")
    return matches[0]


# ── Автономный запуск ──
if __name__ == "__main__":
    from gpn_multiphase_solver.io.config import load_config
    from gpn_multiphase_solver.factory import SimulatorFactory

    if len(sys.argv) < 2:
        raise SystemExit(
            "укажите пример: python examples\\two_phase_analytics.py 03")

    folder = _resolve_example(sys.argv[1])
    config = load_config(folder / "config.json")
    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)

    report(history, sim._grid, config, sim._energy._pvt)
