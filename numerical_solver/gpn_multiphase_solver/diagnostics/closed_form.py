"""Замкнутое решение стационарной двухфазной задачи (DEBT-011: из examples/closed_form.py).

Из расчёта не берётся НИЧЕГО: ни дебит, ни давление, ни насыщенность.
Всё выводится из двух условий стационарности, поэтому модуль применим
к любому сценарию с растворённым газом — независимо от того, заданы PVT
корреляциями или таблицами, а ОФП формулами Кори или таблицей.

──────────────────────────────────────────────────────────────────
Вывод

В стационаре компонентные потоки не зависят от r:

    G^o(r) = const,      G^g(r) = const,

а на контуре питания свободного газа нет (Sg = 0), значит весь газ входит
растворённым, и газовый фактор равен исходному газосодержанию:

    GOR = q_g / q_o = Rs0.

Подставляя выражения для потоков (eq:flux_oil, eq:flux_gas problem_statement.tex),

    G^o = T · kro/(mu_o Bo) · dp,
    G^g = T · [Rs·kro/(mu_o Bo) + krg/(mu_g Bg)] · dp,

видим, что множитель T·dp сокращается, и остаётся АЛГЕБРАИЧЕСКОЕ
уравнение на Sg при известном p:

    Rs(p) + krg(Sg)/kro(Sg) · (mu_o Bo)/(mu_g Bg) = Rs0.            (1)

Правая часть не содержит ОФП: требуемое отношение подвижностей задают
только PVT и давление, а подстраивается насыщенность. При p >= pb имеем
Rs = Rs0 и корень Sg = 0; при p < pb дефицит Rs0 - Rs(p) > 0 компенсируется
потоком свободного газа, что требует Sg > 0.

Найдя Sg(p), подставляем в уравнение нефтяного компонента:

    dp/d(ln r) = q_o/(2 pi k h) · mu_o(p) Bo(p) / kro(Sg(p)).        (2)

Правая часть — функция только p. Разделяя переменные, получаем дебит
НАПРЯМУЮ, одной квадратурой, без итераций:

    q_o = 2 pi k h / ln(Re/rw) · int_{p_wf}^{p_e} kro(Sg(p))/(mu_o Bo) dp.  (3)

Это радиальный аналог функции Маскета (Мускат, «Течение однородных
жидкостей в пористых средах», глава о двухфазном стационарном притоке).
Профиль p(r) восстанавливается интегрированием (2) от контура внутрь.

Какое p_wf подставлять — определяет ПОСЛЕДНИЙ интервал истории: решение
описывает предел t -> inf при удержании последнего режима. При управлении
по давлению это его уставка (FEAT-022). При управлении по дебиту нефти
(FEAT-020) p_wf* находится обращением (3): q_o(p_wf) монотонно убывает,
корень q_o(p_wf*) = q_last единственный; если q_last недостижим и при
min_bhp — стационар при min_bhp (ограничение активно), при q_last = 0 —
p_wf* = p_e.

──────────────────────────────────────────────────────────────────
Область применимости и точность

Проверено на всех двухфазных примерах набора (03-10). Расхождение по
дебиту с расчётом на сетке N = 50 составляет 0.10-0.58 % и убывает
первым порядком при измельчении сетки (см.
05_standing_table_rp/closed_form_convergence.py) — то есть это
погрешность конечных объёмов, а не ошибка вывода.

Ограничение: изотермическое приближение. PVT прототипа не зависит от T,
гидродинамика и энергия расщеплены, обратной связи T -> p в модели нет,
поэтому уравнение энергии в это решение не входит.

──────────────────────────────────────────────────────────────────
Фронт разгазирования

Определяется условием p(r_b) = pb, а НЕ обнулением аналитической Sg.
Разница существенна для ОФП Кори с порогом подвижности S_gc: там вблизи
фронта требуемое отношение krg/kro так мало, что корень уравнения (1)
падает ниже S_gc, где krg тождественно нулевая, и обращение возвращает
ноль, хотя газ физически есть, и фронт выходит заниженным. Критерий по
давлению от этого свободен.

Радиус — rs.isobar_radius: интерполяция ln r по p между соседними
центрами; если профиль ниже pb во всех ячейках — между последним центром
и контуром, где p = p_e.
"""

from __future__ import annotations

import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.optimize import brentq

from .rs import isobar_radius


def kr_max_Sg(relperm, Sg_hi=0.999):
    """Верхняя граница поиска корня: Sg, при которой нефть ещё подвижна.

    Выше этой точки kro = 0 и отношение krg/kro обращается в бесконечность —
    брать её правым концом брекета нельзя.
    """
    S = np.linspace(0.0, Sg_hi, 2000)
    dead = np.where(relperm.kro(S) <= 0.0)[0]
    return float(S[dead[0]]) * 0.999 if dead.size else Sg_hi


class Closure:
    """Замыкание GOR = Rs0: Sg(p) и подвижность нефти как функции p."""

    def __init__(self, pvt, relperm, Rs0):
        self.pvt = pvt
        self.rp = relperm
        self.Rs0 = Rs0
        self.S_hi = kr_max_Sg(relperm)

    def props(self, p):
        """PVT при Rs = min(Rs_eq(p), Rs0). Возвращает (Rs, Bo, mu_o, Bg, mu_g)."""
        pa = np.array([float(p)])
        # Ниже pb нефть насыщена: Rs = Rs_eq(p). Выше — Rs держится на Rs0.
        Rs = min(float(self.pvt.Rs_eq(pa)[0]), self.Rs0)
        Rsa = np.array([Rs])
        return (Rs, float(self.pvt.Bo(pa, Rsa)[0]), float(self.pvt.mu_o(pa, Rsa)[0]),
                float(self.pvt.Bg(pa)[0]), float(self.pvt.mu_g(pa)[0]))

    def _residual(self, Sg, p):
        """Невязка уравнения (1): Rs + krg/kro · (mu_o Bo)/(mu_g Bg) - Rs0."""
        Rs, Bo, mu_o, Bg, mu_g = self.props(p)
        S = np.array([Sg])
        return (Rs + self.rp.krg(S)[0] / self.rp.kro(S)[0]
                * (mu_o * Bo) / (mu_g * Bg) - self.Rs0)

    def Sg(self, p):
        """Корень уравнения (1). Sg = 0 при p >= pb (дефицита газа нет)."""
        if self._residual(0.0, p) >= 0.0:
            return 0.0
        # krg/kro монотонно растёт по Sg → невязка монотонна, корень один
        return brentq(self._residual, 0.0, self.S_hi, args=(p,), xtol=1e-15)

    def mob_o(self, p):
        """Подвижность нефти kro(Sg(p))/(mu_o·Bo) — подынтегральная функция в (3)."""
        _, Bo, mu_o, _, _ = self.props(p)
        return float(self.rp.kro(np.array([self.Sg(p)]))[0]) / (mu_o * Bo)


_CACHE = {}


def _rate_closed(config, clo, pb, p_wf):
    """Дебит стационара при забойном давлении p_wf, м³ст/с. Ур. (3)."""
    p_e = config.initial_conditions.p0
    k, h = config.rock.permeability, config.geometry.h
    r_w, R_e = config.geometry.r_well, config.geometry.R_ext
    # points=[pb]: подынтегральная функция негладкая в точке насыщения
    # (ниже pb включается разгазирование, kro начинает падать). Точку
    # передаём, только если она внутри отрезка: при заданном дебите p_wf
    # стационара может оказаться выше pb (FEAT-020).
    pts = [pb] if p_wf < pb < p_e else None
    integral, _err = quad(clo.mob_o, p_wf, p_e, points=pts,
                          limit=200, epsabs=1e-13, epsrel=1e-13)
    return 2.0 * np.pi * k * h / np.log(R_e / r_w) * integral


def stationary_pwf(config, pvt, relperm) -> float:
    """p_wf стационара при удержании последнего интервала истории. Ур. (3)."""
    last = config.time.history[-1]
    if last.control == "pressure":
        return float(last.p_wf)
    # Управление по дебиту (FEAT-020): p_wf* из q_o(p_wf*) = q_last по (3).
    # q_o(p_wf) монотонно убывает, поэтому корень единственный.
    p_e = config.initial_conditions.p0
    q_last = float(last.q_oil)
    if q_last == 0.0:
        return float(p_e)                  # скважина стоит, депрессии нет
    Rs0 = config.initial_conditions.Rs0
    clo = Closure(pvt, relperm, Rs0)
    pb = float(pvt.pb(np.array([Rs0]))[0])
    p_min = float(last.min_bhp)
    if _rate_closed(config, clo, pb, p_min) <= q_last:
        return p_min                       # в пределе действует ограничение
    # xtol = 1 Па: отклонение дебита от q_last ~ xtol / (p_e - p_wf*) ~ 1e-7
    return float(brentq(lambda x: _rate_closed(config, clo, pb, x) - q_last,
                        p_min, p_e, xtol=1.0, rtol=1e-12))


# Замкнутое решение (3)+(2) шапки модуля. Результат кэшируется: квадратура (3)
# и интегрирование (2) стоят заметно дороже словаря, а вызывают функцию
# несколько overlay подряд. В ключ входят параметры задачи, а не только сетка:
# у разных конфигов сетки могут совпадать, и ключ по одной сетке дал бы коллизию
def solve_closed(config, pvt, relperm, r):
    """Стационарное двухфазное решение без расчёта на сетке: дебит, профили давления и газонасыщенности, радиус фронта.

    Предел при неограниченном времени для последнего режима скважины из
    истории. Из условия, что в стационаре газовый фактор равен начальному
    газосодержанию, газонасыщенность — функция давления; дебит нефти —
    одной квадратурой по давлению (радиальный аналог функции Маскета),
    профиль давления — интегрированием от контура к забою. Из расчёта не
    берётся ничего; годится для любых PVT и ОФП.

    Параметры
    ---------
    config : SimulationConfig
        Конфигурация расчёта.
    pvt : HydroPVT
        PVT-модель.
    relperm : RelPermModel
        Модель ОФП.
    r : numpy.ndarray
        Радиусы точек профиля, м, по возрастанию (обычно центры ячеек).

    Возвращает
    ----------
    dict
        ``q_o`` — дебит нефти, м³ст/с; ``p_wf`` — забойное давление
        стационара, Па; ``p``, ``Sg`` — профили в точках ``r``, Па и доли;
        ``pb`` — давление насыщения при Rs0, Па; ``r_b`` — радиус фронта
        разгазирования (изобары p = p_b), м, ``nan`` — газа нет;
        ``closure`` — объект замыкания (газонасыщенность и подвижность нефти
        как функции давления).
    """
    r = np.asarray(r, float)
    Rs0 = config.initial_conditions.Rs0
    p_e = config.initial_conditions.p0
    k = config.rock.permeability
    h = config.geometry.h
    r_w, R_e = config.geometry.r_well, config.geometry.R_ext

    # Ключ — по параметрам последнего интервала, а не по вычисленному
    # p_wf: при управлении по дебиту обращение (3) стоит 1.2-4 с (FEAT-020).
    last = config.time.history[-1]
    key = (float(r[0]), float(r[-1]), len(r), Rs0, p_e, last.control,
           last.p_wf, last.q_oil, last.min_bhp, k, h,
           config.pvt.model, config.relperm.model)
    if key in _CACHE:
        return _CACHE[key]

    # p_wf стационара — предел t -> inf при удержании последнего режима:
    # при давлении — уставка последнего интервала (а не первого: уставка
    # может меняться по ходу расчёта), при дебите — обращение (3) по его
    # дебиту (FEAT-020).
    p_wf = stationary_pwf(config, pvt, relperm)

    clo = Closure(pvt, relperm, Rs0)
    pb = float(pvt.pb(np.array([Rs0]))[0])

    # ── Дебит по формуле (3) ──
    q_o = _rate_closed(config, clo, pb, p_wf)

    # ── Профиль по уравнению (2), от контура внутрь ──
    C = q_o / (2.0 * np.pi * k * h)

    def rhs(_x, y):
        return [C / clo.mob_o(y[0])]

    lnr = np.log(r)
    sol = solve_ivp(rhs, [np.log(R_e), lnr[0]], [p_e], t_eval=lnr[::-1],
                    rtol=1e-11, atol=1e-4, method="Radau")
    p_ana = sol.y[0][::-1]
    Sg_ana = np.array([clo.Sg(p) for p in p_ana])

    # Фронт — по условию p = pb, а не по обнулению Sg_ana: см. docstring
    # модуля, у Кори с порогом S_gc второй критерий занижает r_b на 13 %.
    # Узел контура (R_e, p_e) — точка, от которой интегрировалось (2): если
    # профиль ниже pb во всех ячейках (пример 11), фронт между последним
    # центром и контуром, а не в центре последней ячейки (DEBT-065).
    r_b = isobar_radius(r, p_ana, pb, R_e, p_e)

    _CACHE[key] = dict(q_o=q_o, p_wf=p_wf, p=p_ana, Sg=Sg_ana, pb=pb, r_b=r_b,
                       closure=clo)
    return _CACHE[key]


def saturation_from_numeric(config, history, pvt, relperm):
    """Sg из замыкания (1) при ЧИСЛЕННОМ давлении, [N].

    Отличается от Sg внутри solve_closed: там p берётся из автономного
    решения, здесь — из расчёта. Это разделяет два разных вопроса:

      выполняется ли САМО замыкание   — эта функция (ошибка p не влияет);
      точен ли автономный профиль     — solve_closed (ошибка p наследуется).

    Первое — проверка решателя, второе — проверка всей конструкции разом.
    Замыкание строится напрямую, без квадратуры: профиль давления здесь
    не нужен, нужна только функция Sg(p).
    """
    clo = Closure(pvt, relperm, config.initial_conditions.Rs0)
    return np.array([clo.Sg(pp) for pp in history.states[-1].p])
