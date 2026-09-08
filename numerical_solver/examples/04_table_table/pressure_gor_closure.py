"""Замкнутое аналитическое решение стационарного профиля давления (пример 04).

В отличие от pressure_analytics.py, здесь НИЧЕГО не берётся из численного
решения: ни Sg(r), ни дебит. Всё выводится из двух условий стационарности.

──────────────────────────────────────────────────────────────────
Постановка

В стационаре покомпонентные потоки не зависят от r:

    G^o(r) = const = -q_o,      G^g(r) = const = -q_g.

Их отношение — газовый фактор — тоже постоянно. Более того, на контуре
питания газовой фазы нет (Sg = 0), поэтому весь газ приходит растворённым:

    GOR = q_g / q_o = R_s,0 = 30 м³ст/м³ст.

Подставляя выражения для потоков (eq. 8, 9 problem_statement.tex),

    G^o = T * kro/(mu_o*Bo) * dp,
    G^g = T * [Rs*kro/(mu_o*Bo) + krg/(mu_g*Bg)] * dp,

множитель T*dp сокращается, и остаётся АЛГЕБРАИЧЕСКОЕ уравнение на Sg:

    Rs(p) + krg(Sg)/kro(Sg) * (mu_o*Bo)/(mu_g*Bg) = R_s,0.        (1)

Это и есть замыкание. При p >= pb имеем Rs = R_s,0 и корень Sg = 0.
При p < pb дефицит R_s,0 - Rs(p) > 0 компенсируется потоком свободного газа,
что требует Sg > 0. Функция krg/kro монотонно растёт по Sg, поэтому корень
единственный.

Найдя Sg(p), подставляем в уравнение для нефтяного компонента:

    dp/d(ln r) = q_o/(2*pi*k*h) * mu_o(p)*Bo(p) / kro(Sg(p)).      (2)

Правая часть — функция только p. Разделяя переменные, получаем квадратуру

    ln(R_e/r_w) = 2*pi*k*h/q_o * integral_{p_wf}^{p_e} kro(Sg(p))/(mu_o*Bo) dp,

откуда дебит вычисляется НАПРЯМУЮ, без итераций:

    q_o = 2*pi*k*h / ln(R_e/r_w) * integral_{p_wf}^{p_e} kro/(mu_o*Bo) dp.  (3)

Это радиальный аналог функции Маскета (Мускат, «Течение однородных жидкостей
в пористых средах», гл. о двухфазном стационарном притоке).

Профиль p(r) затем восстанавливается интегрированием (2) от контура внутрь.

──────────────────────────────────────────────────────────────────
Ограничение

Изотермическое приближение: PVT прототипа не зависит от T, поэтому
уравнение энергии в это решение не входит. Для примера 04 это оправдано —
гидродинамика и энергия расщеплены, обратной связи T -> p в модели нет.
"""

import csv
import importlib.util
from pathlib import Path

import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.optimize import brentq

HERE = Path(__file__).parent
ROOT = HERE.parents[1]  # numerical_solver/

# ── Параметры задачи (config.json) ────────────────────────────────
K_PERM = 1e-13     # проницаемость, м²
H_THICK = 10.0     # мощность пласта, м
R_WELL = 0.1       # радиус скважины, м
R_EXT = 50.0       # радиус контура питания, м
P_EXT = 20e6       # давление на контуре, Па
P_WF = 8e6         # забойное давление, Па
RS0 = 30.0         # газосодержание на контуре, м³ст/м³ст


def load_pvt():
    """PVT прототипа из тех же CSV, что читает решатель.

    Конвертации повторяют factory._read_oil_pvt_csv: p Па→бар, mu Па·с→сП.
    """
    spec = importlib.util.spec_from_file_location(
        "protopvt", ROOT / "HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/pvt.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    oil = [[float(x) for x in row]
           for row in list(csv.reader(open(HERE / "oil_pvt.csv")))[1:]]
    gas = [[float(x) for x in row]
           for row in list(csv.reader(open(HERE / "gas_pvt.csv")))[1:]]
    oil = [[r[0], r[1] / 1e5, r[2], r[3] * 1e3] for r in oil]
    gas = [[r[0] / 1e5, r[1], r[2] * 1e3] for r in gas]
    return mod.BlackOilPVT(oil, gas)


def load_relperm():
    """Табличная ОФП: узлы для линейной интерполяции kro(Sg), krg(Sg)."""
    rows = list(csv.reader(open(HERE / "relperm.csv")))[1:]
    return (np.array([float(r[0]) for r in rows]),
            np.array([float(r[1]) for r in rows]),
            np.array([float(r[2]) for r in rows]))


def load_numeric_profile():
    """Последний (стационарный) срез профилей решателя — для сравнения."""
    rows = list(csv.DictReader(open(HERE / "output/profiles.csv")))
    last = max(int(r["step"]) for r in rows)
    sub = [r for r in rows if int(r["step"]) == last]
    get = lambda key: np.array([float(x[key]) for x in sub])
    return get("r_m"), get("p_Pa"), get("Sg"), get("Rs")


class Closure:
    """Замыкание по постоянству GOR: Sg(p) и подвижность нефти как функции p."""

    def __init__(self, pvt, Sg_t, kro_t, krg_t, Rs0=RS0):
        self.pvt = pvt
        self.Sg_t, self.kro_t, self.krg_t = Sg_t, kro_t, krg_t
        self.Rs0 = Rs0
        # Максимальная Sg таблицы: выше kro = 0, нефть неподвижна
        self.Sg_max = float(Sg_t[np.argmax(kro_t <= 0.0)]) if np.any(kro_t <= 0.0) else float(Sg_t[-1])

    def props(self, p):
        """PVT в точке p при Rs = min(Rs_sat(p), Rs0). Возвращает (Rs, Bo, mu_o, Bg, mu_g)."""
        p_bar = np.array([p / 1e5])
        # Ниже pb нефть насыщена: Rs = Rs_sat(p). Выше — Rs держится на Rs0.
        Rs = min(float(self.pvt.rs_sat(p_bar)[0]), self.Rs0)
        Bo = float(self.pvt.bo(p_bar, np.array([Rs]))[0])
        mu_o = float(self.pvt.mu_o(p_bar, np.array([Rs]))[0]) * 1e-3   # сП → Па·с
        Bg = float(self.pvt.bg(p_bar)[0])
        mu_g = float(self.pvt.mu_g(p_bar)[0]) * 1e-3
        return Rs, Bo, mu_o, Bg, mu_g

    def _residual(self, Sg, p):
        """Невязка уравнения (1): Rs + krg/kro * (mu_o*Bo)/(mu_g*Bg) - Rs0."""
        Rs, Bo, mu_o, Bg, mu_g = self.props(p)
        kro = float(np.interp(Sg, self.Sg_t, self.kro_t))
        krg = float(np.interp(Sg, self.Sg_t, self.krg_t))
        return Rs + krg / kro * (mu_o * Bo) / (mu_g * Bg) - self.Rs0

    def Sg(self, p):
        """Корень уравнения (1). Sg = 0 при p >= pb (нет дефицита газа)."""
        if self._residual(0.0, p) >= 0.0:
            return 0.0
        # Функция krg/kro растёт по Sg → невязка монотонна, корень единственный
        return brentq(self._residual, 0.0, self.Sg_max * 0.99, args=(p,), xtol=1e-14)

    def mob_o(self, p):
        """Подвижность нефти kro(Sg(p))/(mu_o*Bo) — подынтегральная функция в (3)."""
        _, Bo, mu_o, _, _ = self.props(p)
        kro = float(np.interp(self.Sg(p), self.Sg_t, self.kro_t))
        return kro / (mu_o * Bo)


def solve():
    """Замкнутое решение: дебит по (3), профиль по (2). Ничего из расчёта не берётся."""
    pvt = load_pvt()
    clo = Closure(pvt, *load_relperm())

    # ── Дебит по формуле (3) ─────────────────────────────────────
    # Интеграл считаем с точкой излома в pb: подынтегральная функция
    # там негладкая (ниже pb включается разгазирование).
    p_b = float(pvt.pb_of_rs(np.array([RS0]))[0]) * 1e5
    integral, err = quad(clo.mob_o, P_WF, P_EXT, points=[p_b],
                         limit=200, epsabs=1e-12, epsrel=1e-12)
    q_o = 2.0 * np.pi * K_PERM * H_THICK / np.log(R_EXT / R_WELL) * integral

    # ── Профиль по уравнению (2), от контура внутрь ──────────────
    C = q_o / (2.0 * np.pi * K_PERM * H_THICK)

    def rhs(_x, y):
        return [C / clo.mob_o(y[0])]

    return q_o, p_b, clo, C, rhs


_CACHE = {}


def analytic_profile(r):
    """Аналитический профиль p(r) и Sg(r) на заданной сетке.

    Возвращает (p, q_o, Sg, p_b). Результат кэшируется по сетке: оба overlay
    (давление и насыщенность) вызывают эту функцию с одной и той же сеткой,
    а квадратура (3) и интегрирование (2) стоят заметно дороже словаря.
    """
    r = np.asarray(r, float)
    key = (r[0], r[-1], len(r))
    if key in _CACHE:
        return _CACHE[key]

    q_o, p_b, clo, _C, rhs = solve()
    lnr = np.log(r)
    # Интегрируем от контура (там p = P_EXT известно) внутрь, к забою
    sol = solve_ivp(rhs, [np.log(R_EXT), lnr[0]], [P_EXT],
                    t_eval=lnr[::-1], rtol=1e-11, atol=1e-4, method="Radau")
    p_ana = sol.y[0][::-1]
    # Sg находится из того же замыкания (1) — локально, по давлению в точке
    Sg_ana = np.array([clo.Sg(p) for p in p_ana])

    _CACHE[key] = (p_ana, q_o, Sg_ana, p_b)
    return _CACHE[key]


def overlay_pressure(ax, history, grid, simulator=None):
    """Наложить аналитику на график профилей давления (хук example_runner).

    Вызывается из run_example после отрисовки численных профилей, поэтому
    отдельного PNG не создаётся — кривая ложится в штатный pressure_profiles.png.
    """
    r = grid.r_centers
    p_ana, q_o, _Sg, p_b = analytic_profile(r)

    ax.plot(r, p_ana, "k--", lw=2.0, zorder=5,
            label=f"аналитика GOR=$R_{{s,0}}$: $q_o$={q_o:.3e} м³ст/с")

    # Линия p = pb: правее неё Sg = 0, левее идёт разгазирование
    ax.axhline(p_b, color="C4", lw=0.9, alpha=0.6, ls="-.",
               label=f"$p_b$ = {p_b / 1e6:.0f} МПа")


def overlay_saturation(ax, history, grid, simulator=None):
    """Наложить аналитику на график профилей газонасыщенности.

    Sg берётся из того же замыкания (1), что и для давления: это локальное
    соотношение Sg(p), пространственная зависимость возникает как Sg(p(r)).
    """
    r = grid.r_centers
    _p, _q, Sg_ana, _p_b = analytic_profile(r)

    ax.plot(r, Sg_ana, "k--", lw=2.0, zorder=5,
            label="аналитика: $S_g(p(r))$ из GOR=$R_{s,0}$")

    # Фронт разгазирования: наибольший r, где замыкание даёт свободный газ
    if np.any(Sg_ana > 1e-9):
        r_b = r[Sg_ana > 1e-9].max()
        ax.axvline(r_b, color="C4", lw=0.9, alpha=0.6, ls="-.",
                   label=f"фронт $r_b$ = {r_b:.2f} м")


def main():
    """Консольная сверка аналитики с сохранённым расчётом."""
    r_num, p_num, Sg_num, _Rs_num = load_numeric_profile()
    p_ana, q_o, Sg_ana, p_b = analytic_profile(r_num)

    # Дебит решателя — только для сравнения, в аналитику не входит
    hist = list(csv.DictReader(open(HERE / "output/well_history.csv")))
    q_num = float(hist[-1]["q_o_m3st_s"])

    d_p = np.abs(p_ana - p_num).max()
    print("== Замкнутое решение из условия GOR = Rs0 = 30 ==")
    print(f"p_b(Rs0)                 = {p_b / 1e6:.3f} МПа")
    print()
    print(f"q_o аналитика (форм. 3)  = {q_o:.6e} м³ст/с")
    print(f"q_o численно             = {q_num:.6e} м³ст/с")
    print(f"расхождение              = {abs(q_o - q_num) / q_num * 100:.3f} %")
    print()
    print(f"p_забой аналитика        = {p_ana[0] / 1e6:.4f} МПа  (задано {P_WF / 1e6:.1f})")
    print(f"p_забой численно         = {p_num[0] / 1e6:.4f} МПа")
    print(f"макс |p_ана - p_чис|     = {d_p / 1e3:.1f} кПа "
          f"({d_p / (P_EXT - P_WF) * 100:.2f} % депрессии)")
    print()
    print(f"Sg макс аналитика        = {Sg_ana.max():.5f}")
    print(f"Sg макс численно         = {Sg_num.max():.5f}")

    # Точность Sg. Различаем два вопроса:
    #   (а) выполняется ли замыкание (1) — подставляем ЧИСЛЕННОЕ p;
    #   (б) точность автономного решения — Sg(p_ana(r)), где ошибка p наследуется.
    _q, _pb, clo, _C, _rhs = solve()
    Sg_at_p_num = np.array([clo.Sg(p) for p in p_num])
    two_phase = Sg_num > 1e-12
    print()
    print("Проверка замыкания (1) при численном p:")
    print(f"  макс |dSg|             = {np.abs(Sg_at_p_num - Sg_num).max():.3e}")
    print(f"  макс отн. (двухф. зона)= "
          f"{(np.abs(Sg_at_p_num - Sg_num)[two_phase] / Sg_num[two_phase]).max() * 100:.4f} %")
    print("Автономное Sg(p_ana(r)):")
    print(f"  макс |dSg|             = {np.abs(Sg_ana - Sg_num).max():.3e}")
    # Относительная ошибка раздувается у фронта, где Sg -> 0, поэтому
    # отдельно печатаем значение у забоя, где Sg максимальна и значима.
    print(f"  отн. у забоя           = "
          f"{abs(Sg_ana[0] - Sg_num[0]) / Sg_num[0] * 100:.2f} %")

    # Фронт разгазирования: наибольший r, где есть свободный газ
    rb_ana = r_num[Sg_ana > 1e-9].max() if np.any(Sg_ana > 1e-9) else np.nan
    rb_num = r_num[Sg_num > 1e-9].max() if np.any(Sg_num > 1e-9) else np.nan
    print(f"фронт r_b аналитика      = {rb_ana:.3f} м")
    print(f"фронт r_b численно       = {rb_num:.3f} м")


if __name__ == "__main__":
    main()
