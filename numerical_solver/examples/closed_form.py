"""Замкнутое решение стационарной двухфазной задачи — общее для всех примеров.

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

Подставляя выражения для потоков (eq. 8, 9 problem_statement.tex),

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
ноль, хотя газ физически есть. В примере 03 это давало r_b = 0.175 м
вместо 0.199 м (13 % занижения) при том, что численный расчёт даёт газ
в шести ячейках, а не в пяти. Критерий по давлению от этого свободен.
"""

from __future__ import annotations

import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.optimize import brentq


def _kr_max_Sg(relperm, Sg_hi=0.999):
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
        self.S_hi = _kr_max_Sg(relperm)

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


def solve_closed(config, pvt, relperm, r):
    """Замкнутое решение (3)+(2) на сетке r. Возвращает dict.

    Ключи: q_o (дебит, м³ст/с), p [N], Sg [N], pb, r_b, closure.

    Результат кэшируется: квадратура (3) и интегрирование (2) стоят заметно
    дороже словаря, а вызывают функцию несколько overlay подряд. В ключ
    входят параметры задачи, а не только сетка: у примеров 04 и 07-09 сетки
    совпадают при разных конфигах, и ключ по одной сетке дал бы коллизию.
    """
    r = np.asarray(r, float)
    Rs0 = config.initial_conditions.Rs0
    p_e = config.initial_conditions.p0
    # p_wf ПОСЛЕДНЕГО интервала: стационар — предел t -> inf при
    # удержании последнего режима. У примеров с постоянным p_wf это то
    # же значение; у 13a первый интервал — 14.4 МПа, последний — 6 МПа
    # (FEAT-022).
    p_wf = config.time.history[-1].p_wf
    k = config.rock.permeability
    h = config.geometry.h
    r_w, R_e = config.geometry.r_well, config.geometry.R_ext

    key = (float(r[0]), float(r[-1]), len(r), Rs0, p_e, p_wf, k, h,
           config.pvt.model, config.relperm.model)
    if key in _CACHE:
        return _CACHE[key]

    clo = Closure(pvt, relperm, Rs0)
    pb = float(pvt.pb(np.array([Rs0]))[0])

    # ── Дебит по формуле (3) ──
    # points=[pb]: подынтегральная функция негладкая в точке насыщения
    # (ниже pb включается разгазирование, kro начинает падать).
    integral, _err = quad(clo.mob_o, p_wf, p_e, points=[pb],
                          limit=200, epsabs=1e-13, epsrel=1e-13)
    q_o = 2.0 * np.pi * k * h / np.log(R_e / r_w) * integral

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
    r_b = _front_radius(r, p_ana, pb)

    _CACHE[key] = dict(q_o=q_o, p=p_ana, Sg=Sg_ana, pb=pb, r_b=r_b, closure=clo)
    return _CACHE[key]


def _front_radius(r, p, pb):
    """Радиус фронта: интерполяция условия p(r_b) = pb по ln r.

    Профиль логарифмичен, поэтому интерполируем ln r, а не r. np.interp
    здесь не годится: он требует возрастающие узлы, а p и ln r монотонны
    в противоположные стороны — молча вернул бы мусор.
    """
    if not np.any(p < pb):
        return np.nan
    j = int(np.searchsorted(p, pb))          # p возрастает с ростом r
    if not (0 < j < len(p)):
        return float(r[p < pb].max())
    w = (pb - p[j - 1]) / (p[j] - p[j - 1])
    return float(np.exp(np.log(r[j - 1]) + w * (np.log(r[j]) - np.log(r[j - 1]))))


# ── Хуки для example_runner ──────────────────────────────────────

def _prepare(history, grid, simulator, config):
    """Общая подготовка overlay: PVT, ОФП и решение на сетке примера."""
    from gpn_multiphase_solver.factory import _create_relperm

    pvt = simulator._energy._pvt
    relperm = _create_relperm(config)
    return solve_closed(config, pvt, relperm, grid.r_centers)


def make_overlay_pressure(config):
    """Overlay замкнутого решения p(r) для профилей давления."""
    def overlay(ax, history, grid, simulator):
        cl = _prepare(history, grid, simulator, config)
        ax.semilogx(grid.r_centers, cl["p"], "k--", lw=2.0, zorder=5,
                    label=rf"замкнутое решение: $q_o$ = {cl['q_o']:.4e} м³ст/с")
        ax.axhline(cl["pb"], color="gray", lw=1.0, ls="-.",
                   label=rf"$p_b$ = {cl['pb'] / 1e6:.2f} МПа")
        if np.isfinite(cl["r_b"]):
            ax.axvline(cl["r_b"], color="gray", lw=1.5, ls=":",
                       label=rf"фронт $r_b$ = {cl['r_b']:.3f} м")
    return overlay


def saturation_from_numeric(config, history, simulator):
    """Sg из замыкания (1) при ЧИСЛЕННОМ давлении, [N].

    Отличается от Sg внутри solve_closed: там p берётся из автономного
    решения, здесь — из расчёта. Это разделяет два разных вопроса:

      выполняется ли САМО замыкание   — эта функция (ошибка p не влияет);
      точен ли автономный профиль     — solve_closed (ошибка p наследуется).

    Первое — проверка решателя, второе — проверка всей конструкции разом.
    Замыкание строится напрямую, без квадратуры: профиль давления здесь
    не нужен, нужна только функция Sg(p).
    """
    from gpn_multiphase_solver.factory import _create_relperm

    clo = Closure(simulator._energy._pvt, _create_relperm(config),
                  config.initial_conditions.Rs0)
    return np.array([clo.Sg(pp) for pp in history.states[-1].p])


def make_overlay_saturation(config):
    """Overlay замкнутого решения Sg(r) для профилей газонасыщенности.

    Наносятся ДВЕ кривые, отвечающие на разные вопросы (см.
    saturation_from_numeric): кружки — замыкание при численном p,
    пунктир — полностью автономное решение.
    """
    def overlay(ax, history, grid, simulator):
        cl = _prepare(history, grid, simulator, config)
        r = grid.r_centers

        clo = cl["closure"]
        Sg_at_p_num = np.array([clo.Sg(pp) for pp in history.states[-1].p])
        two = Sg_at_p_num > 1e-9
        if two.any():
            ax.semilogx(r[two], Sg_at_p_num[two], "ko", ms=5,
                        markerfacecolor="none", zorder=6,
                        label=r"$S_g$ из $k_{rg}/k_{ro} = (R_{s,0}-R_s)\mu_g B_g/(\mu_o B_o)$")

        ax.semilogx(r, cl["Sg"], "k--", lw=1.8, zorder=5,
                    label=r"автономно: $S_g(p_{ана}(r))$")
        if np.isfinite(cl["r_b"]):
            ax.axvline(cl["r_b"], color="gray", lw=1.5, ls=":",
                       label=rf"фронт $r_b$ = {cl['r_b']:.3f} м")
    return overlay


def report_closed(config, history, grid, simulator) -> dict:
    """Печать сверки замкнутого решения с расчётом. Возвращает сводку."""
    cl = _prepare(history, grid, simulator, config)

    p_num = history.states[-1].p
    Sg_num = history.states[-1].Sg
    q_num = abs(history.hydro_results[-1].G_o[0])
    # Та же депрессия, по которой построено решение (solve_closed)
    dep = config.initial_conditions.p0 - config.time.history[-1].p_wf
    d_p = float(np.abs(cl["p"] - p_num).max())

    print("── Замкнутое решение (GOR = Rs0): из расчёта ничего не берётся ──")
    print(f"  q_o: {cl['q_o']:.6e} аналитика vs {q_num:.6e} расчёт "
          f"({abs(cl['q_o'] - q_num) / q_num * 100:.3f} %)")
    print(f"  max|p_ана - p_чис| = {d_p / 1e3:.2f} кПа "
          f"({d_p / dep * 100:.3f} % депрессии)")
    print(f"  Sg макс: {cl['Sg'].max():.5f} аналитика vs "
          f"{Sg_num.max():.5f} расчёт")
    print(f"  фронт r_b = {cl['r_b']:.4f} м (p = pb = {cl['pb'] / 1e6:.3f} МПа)")

    # Проверка самого замыкания, без наследования ошибки давления:
    # подставляем численное p и смотрим, даёт ли оно численную Sg.
    Sg_at_p_num = saturation_from_numeric(config, history, simulator)
    two = Sg_num > 1e-12
    d_abs = float(np.abs(Sg_at_p_num - Sg_num).max())
    d_rel = (float((np.abs(Sg_at_p_num - Sg_num)[two] / Sg_num[two]).max()) * 100
             if two.any() else 0.0)
    print(f"  замыкание при численном p: max|dSg| = {d_abs:.2e} "
          f"({d_rel:.4f} % в двухфазной зоне)")

    return dict(q_o=cl["q_o"], q_num=q_num, d_p=d_p, r_b=cl["r_b"],
                dSg_closure=d_abs)
