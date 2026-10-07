"""Проба FEAT-028: код шага 1 плана дословно + утверждения тестов шагов 2 и 4.

Функции ниже — копия того, что план вносит в
gpn_multiphase_solver/io/output.py (раздел «Визуализация: свойства PVT»).
Утверждения — те же, что тесты плана. Превью рисунков пишутся в
vault/issues/feat-028/probes/png/ для просмотра до реализации.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\feat-028\\probes\\plan_code_check.py
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

NS = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(NS / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(NS / "examples"))
sys.path.insert(0, str(NS))

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import _create_pvt  # noqa: E402
from gpn_multiphase_solver.pvt.standing import StandingFullPVT  # noqa: E402
import pvt_plot  # noqa: E402

OUT = Path(__file__).resolve().parent / "png"
OUT.mkdir(exist_ok=True)


# ════════════════ код шага 1 плана (begin) ════════════════

# Ветви R_s = const у корреляции: «круглый» шаг, как у строк настоящей
# таблицы PVTO, и не больше _RS_ROWS_MAX строк на оси, иначе веер
# сливается в заливку (решение пользователя 2026-10-03, FEAT-028).
_RS_STEPS = (1.0, 2.0, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0, 200.0, 250.0, 500.0)
_RS_ROWS_MAX = 7


def _round_rs_rows(pvt, p: np.ndarray) -> np.ndarray:
    """Строки R_s,i корреляции: кратные наименьшему шагу из _RS_STEPS, не больше 7 на оси."""
    # R_s,i берутся из [R_s^eq(p[0]), R_s^eq(p[-1])]: тогда p_b(R_s,i) лежит
    # на оси и каждая ветвь начинается на насыщенной кривой. R_s^eq у
    # Стендинга почти линейна по p, поэтому p_b(R_s,i) почти равномерны.
    rs_lo = float(pvt.Rs_eq(p[:1])[0])
    rs_hi = float(pvt.Rs_eq(p[-1:])[0])
    for step in _RS_STEPS:
        rows = step * np.arange(np.ceil(rs_lo / step), np.floor(rs_hi / step) + 1)
        if rows.size <= _RS_ROWS_MAX:
            break
    return rows


def _pvto_rows(pvt, p: np.ndarray, Rs0: float, table_nodes) -> np.ndarray:
    """Газосодержания тонких ветвей веера (без R_s,0), м³ст/м³ст."""
    # Табличный PVT: ветви — строки таблицы PVTO, как в tNavigator. Строка,
    # чья ветвь начинается правее оси (p_b > p[-1]), на рисунок не попадает;
    # начавшиеся левее оси видны с её левого края.
    rs_tab = None if table_nodes is None else table_nodes.get("rs_values")
    if rs_tab is not None:
        rows = np.asarray(rs_tab, float)
        rows = rows[pvt.pb(rows) <= p[-1]]
    else:
        rows = _round_rs_rows(pvt, p)
    # Ветвь R_s,0 рисуется отдельно и жирно — из веера её исключаем.
    return rows[~np.isclose(rows, Rs0)]


def _table_pb_span(pvt, table_nodes):
    """Границы строк таблицы (p_b(R_s,min), p_b(R_s,max)), Па; None у корреляции."""
    # За этими пределами прототип зажимает R_s^eq (np.interp в rs_sat,
    # radial_blackoil/pvt.py:33): свойства там — экстраполяция, а не данные
    # таблицы. Решатель их использовал (04a опускается до 4 МПа при
    # p_b(0) = 5 МПа), поэтому кривая не обрезается, а рисуется пунктиром.
    rs_tab = None if table_nodes is None else table_nodes.get("rs_values")
    if rs_tab is None:
        return None
    rs_tab = np.asarray(rs_tab, float)
    pb = pvt.pb(np.array([rs_tab.min(), rs_tab.max()]))
    return float(pb[0]), float(pb[1])


def plot_pvt_properties(pvt, Rs0: float, p_range, axes=None,
                        table_nodes=None, label: str = ""):
    """Свойства PVT по давлению в стиле таблицы PVTO: насыщенная кривая и веер ветвей R_s = const.

    Показывает не результат расчёта, а СВОЙСТВА МОДЕЛИ, которой считали.
    На панелях нефти (mu_o, R_s, B_o, rho_o) — как в коммерческих
    симуляторах (таблица PVTO): насыщенная кривая f(p, R_s^eq(p)) на всей
    оси и ветви f(p, R_s,i) при p >= p_b(R_s,i); ветвь R_s,0 — жирная.
    Газ сухой: mu_g, B_g, rho_g — по одной кривой.

    pvt         — HydroPVT/FullPVT: нужны Rs_eq, Bo, mu_o, Bg, mu_g, pb,
                  rho_o, rho_g
    Rs0         — начальное газосодержание, м³ст/м³ст: выделенная ветвь
    p_range     — (p_lo, p_hi), Па: диапазон, который подсветить как рабочий
    axes        — сетка 2x3; создаётся, если None
    table_nodes — узлы табличного PVT, или None для аналитического PVT:
                  'p_gas' — давления газовой таблицы, Па;
                  'rs_values' — строки PVTO, м³ст/м³ст (они же ветви);
                  'p_branch' — давления узлов строки R_s,0, Па (пусто,
                  если R_s,0 не совпадает со строкой)
    label       — подпись модели для заголовка первой панели

    Ветви корреляции — «круглые» R_s,i (_round_rs_rows). Плотности —
    вызовами pvt.rho_o / pvt.rho_g: rho_o = (rho_o_ст + Rs*rho_g_ст)/Bo —
    \\eqref{eq:rho_oil}, rho_g = rho_g_ст/Bg.

    Кривые размечены gid: 'pvto_saturated', 'pvto_saturated_extrap',
    'pvto_branch', 'pvto_rs0' — по ним их находят тесты.

    Возвращает axes. Файл не пишет и не печатает — как остальные plot_*
    этого модуля.
    """
    import matplotlib.pyplot as plt

    p_lo, p_hi = float(p_range[0]), float(p_range[1])
    if axes is None:
        _, axes = plt.subplots(2, 3, figsize=(16, 9))
    axes = np.asarray(axes)

    # Ось шире рабочего диапазона: видно, куда кривые идут за его пределами.
    p = np.linspace(0.8 * p_lo, 1.1 * p_hi, 800)
    pb = float(pvt.pb(np.array([Rs0]))[0])
    two_phase = Rs0 > 0.0

    rows = _pvto_rows(pvt, p, Rs0, table_nodes)
    span = _table_pb_span(pvt, table_nodes)

    # Начала ветвей и границы строк таблицы — точно в узлах сетки по p:
    # тогда первая точка ветви лежит РОВНО на насыщенной кривой, а сплошной
    # и пунктирный участки насыщенной стыкуются без зазора.
    marks = pvt.pb(np.append(rows, Rs0))
    if span is not None:
        marks = np.append(marks, span)
    p = np.union1d(p, marks[(marks > p[0]) & (marks < p[-1])])
    p_MPa = p / 1e6
    Rs_sat = pvt.Rs_eq(p)

    # Участки насыщенной кривой: (маска, экстраполяция ли). У корреляции —
    # один сплошной; у таблицы — сплошной между p_b(R_s,min) и p_b(R_s,max),
    # пунктир за ними. Пустые и одноточечные участки не рисуются.
    if span is None:
        sat_parts = [(np.ones_like(p, dtype=bool), False)]
    else:
        sat_parts = [(p <= span[0], True),
                     ((p >= span[0]) & (p <= span[1]), False),
                     (p >= span[1], True)]

    def _rs(pp, rr):
        """R_s как свойство панели R_s: на ветви — константа R_s,i."""
        return np.asarray(rr, float)

    def _pvto_panel(ax, func, ylabel):
        """Панель величины f(p, R_s): насыщенная кривая, веер ветвей, ветвь R_s,0."""
        y_sat = func(p, Rs_sat)
        labeled = set()
        for mask, extrap in sat_parts:
            if mask.sum() < 2:
                continue
            lab = ("насыщенная: экстраполяция за строки таблицы" if extrap
                   else r"насыщенная: $R_s = R_s^{eq}(p)$")
            ln, = ax.plot(p_MPa[mask], y_sat[mask], "--" if extrap else "-",
                          lw=1.4 if extrap else 1.8, color="C3", zorder=2,
                          label=None if lab in labeled else lab)
            ln.set_gid("pvto_saturated_extrap" if extrap else "pvto_saturated")
            labeled.add(lab)

        def _branch(Rs_i, gid, lab, **style):
            """Ветвь R_s = R_s,i от p_b(R_s,i) (или от левого края оси) вправо."""
            start = max(float(pvt.pb(np.array([Rs_i]))[0]), p[0])
            m = p >= start
            if m.sum() < 2:
                return False
            ln, = ax.plot(p_MPa[m], func(p[m], np.full(m.sum(), Rs_i)),
                          "-", label=lab, **style)
            ln.set_gid(gid)
            return True

        # Тонкие серые ветви — одной записью в легенде: значение R_s,i
        # читается на панели R_s, где ветвь — горизонталь на высоте R_s,i,
        # а ось p у панелей общая (решение 2026-10-03).
        lab = r"ветви $R_s$ = const"
        for Rs_i in rows:
            if _branch(Rs_i, "pvto_branch", lab, lw=0.8, color="0.55", zorder=1):
                lab = None
        _branch(float(Rs0), "pvto_rs0", rf"$R_{{s,0}}$ = {Rs0:g} м³ст/м³ст",
                lw=2.4, color="C2", zorder=3)
        ax.set_ylabel(ylabel)

    # ── Верхний ряд: приоритет задачи — вязкость и газосодержание нефти ──
    _pvto_panel(axes[0, 0], pvt.mu_o, r"$\mu_o$, Па·с")
    # Логарифмическая шкала: у примера 14 веер 4.7e-4…1.6e-2 Па·с (ветвь
    # мёртвой нефти R_s = 0 по таблице растёт до 16 сП), на линейной оси
    # рабочая ветвь R_s,0 = 150 сжалась бы в нижние 3 % панели.
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_title(label if label else r"$\mu_o(p)$", fontsize=8)

    ax_rs = axes[0, 1]
    _pvto_panel(ax_rs, _rs, r"$R_s$, м³ст/м³ст")
    if not two_phase:
        ax_rs.set_title(r"однофазный расчёт: $R_s \equiv 0$", fontsize=8)

    _pvto_panel(axes[0, 2], pvt.Bo, r"$B_o$")

    # ── Нижний ряд: газовая фаза и плотности ──
    axes[1, 0].plot(p_MPa, pvt.mu_g(p), "-", lw=2, color="C0", label="газ")
    axes[1, 0].set_ylabel(r"$\mu_g$, Па·с")

    axes[1, 1].plot(p_MPa, pvt.Bg(p), "-", lw=2, color="C0", label="газ")
    axes[1, 1].set_ylabel(r"$B_g$")

    # Плотности — на двух осях: нефть 730…800, газ 40…140 кг/м³ (измерено
    # на примере 04), на одной оси форма газовой кривой нечитаема. Веер
    # rho_o — на левой оси.
    ax_rho = axes[1, 2]
    _pvto_panel(ax_rho, pvt.rho_o, r"$\rho_o$, кг/м³")
    ax_rho_g = ax_rho.twinx()
    ax_rho_g.plot(p_MPa, pvt.rho_g(p), "-", lw=2, color="C0",
                  label=r"$\rho_g$")
    ax_rho_g.set_ylabel(r"$\rho_g$, кг/м³")

    # ── Узлы табличного PVT ──
    # Газовая таблица — на mu_g/B_g. Нефтяные узлы — начала строк PVTO
    # (p_b,i, f(p_b,i, R_s,i)), они лежат на насыщенной кривой в началах
    # ветвей, и узлы строки R_s,0 на жирной ветви. Ординаты — ВЫЗОВОМ PVT,
    # а не из таблицы: ветвь интерполируется по dp = p - p_b(R_s), иначе
    # маркер не лёг бы на нарисованную кривую.
    if table_nodes is not None:
        p_gas = np.asarray(table_nodes.get("p_gas", []), float)
        p_gas = p_gas[(p_gas >= p[0]) & (p_gas <= p[-1])]
        if p_gas.size:
            axes[1, 0].plot(p_gas / 1e6, pvt.mu_g(p_gas), "o", ms=5,
                            color="C0", zorder=5, label="узлы таблицы")
            axes[1, 1].plot(p_gas / 1e6, pvt.Bg(p_gas), "o", ms=5,
                            color="C0", zorder=5, label="узлы таблицы")

        rs_tab = np.asarray(table_nodes.get("rs_values", []), float)
        pb_tab = pvt.pb(rs_tab) if rs_tab.size else rs_tab
        on = (pb_tab >= p[0]) & (pb_tab <= p[-1])
        pb_tab, rs_tab = pb_tab[on], rs_tab[on]
        p_br = np.asarray(table_nodes.get("p_branch", []), float)
        p_br = p_br[(p_br >= max(pb, p[0])) & (p_br <= p[-1])]
        for ax, func in ((axes[0, 0], pvt.mu_o), (ax_rs, _rs),
                         (axes[0, 2], pvt.Bo)):
            lab = "узлы таблицы"
            if pb_tab.size:
                ax.plot(pb_tab / 1e6, func(pb_tab, rs_tab), "o", ms=4,
                        color="C3", zorder=5, label=lab)
                lab = None
            if p_br.size:
                ax.plot(p_br / 1e6, func(p_br, np.full(p_br.size, float(Rs0))),
                        "o", ms=5, color="C2", zorder=5, label=lab)

    # ── Общее оформление всех панелей ──
    for ax in axes.ravel():
        ax.axvspan(p_lo / 1e6, p_hi / 1e6, color="C2", alpha=0.18)
        # Вертикаль p_b — только если попадает в пределы оси. При Rs0 = 0
        # у Стендинга pb = -0.176 МПа (измерено), условие ложно.
        if p[0] <= pb <= p[-1]:
            ax.axvline(pb / 1e6, color="k", ls=":", lw=1)
        ax.set_xlabel("p, МПа")
        ax.grid(True, alpha=0.3)

    # Легенда панели плотностей собирается из обеих осей: кривая газа живёт
    # на twinx и в легенду первой оси сама не попадает.
    for ax in axes.ravel():
        if ax is ax_rho:
            h1, l1 = ax_rho.get_legend_handles_labels()
            h2, l2 = ax_rho_g.get_legend_handles_labels()
            ax_rho.legend(h1 + h2, l1 + l2, fontsize=7)
        else:
            ax.legend(fontsize=7)

    return axes

# ════════════════ код шага 1 плана (end) ════════════════


def _lines(ax, gid):
    return [ln for ln in ax.get_lines() if ln.get_gid() == gid]


def _plot(pvt, Rs0, p_range, nodes=None):
    fig, axes = plt.subplots(2, 3, figsize=(13.8, 9))
    plot_pvt_properties(pvt, Rs0, p_range, axes=axes, table_nodes=nodes)
    return fig, axes


ok = []


def check(cond, msg):
    assert cond, msg
    ok.append(msg)


# ── Шаг 2: тесты ядра на StandingFullPVT ──
pvt = StandingFullPVT(rho_o_std=850.0, rho_g_std=0.9, T0=350.0, Rs0=50.0)
p_ax = np.linspace(6.4e6, 22e6, 800)
check(_round_rs_rows(pvt, p_ax).tolist() == [40.0, 60.0, 80.0, 100.0, 120.0, 140.0],
      "A: круглые строки Стендинга 40…140 шаг 20")
check(_pvto_rows(pvt, p_ax, 60.0, None).tolist() == [40.0, 80.0, 100.0, 120.0, 140.0],
      "B: R_s,0 = 60 исключено из веера")

fig, axes = _plot(pvt, 50.0, (8e6, 20e6))
check(axes.shape == (2, 3), "C: сетка 2x3")
check((len(_lines(axes[0, 0], "pvto_saturated")), len(_lines(axes[0, 0], "pvto_branch")),
       len(_lines(axes[0, 0], "pvto_rs0"))) == (1, 6, 1), "C: 1 насыщенная + 6 ветвей + R_s,0")

for ax in (axes[0, 0], axes[0, 1], axes[0, 2], axes[1, 2]):
    sat = _lines(ax, "pvto_saturated") + _lines(ax, "pvto_saturated_extrap")
    sx = np.concatenate([ln.get_xdata() for ln in sat])
    sy = np.concatenate([ln.get_ydata() for ln in sat])
    n = 0
    for ln in _lines(ax, "pvto_branch") + _lines(ax, "pvto_rs0"):
        x0, y0 = ln.get_xdata()[0], ln.get_ydata()[0]
        if x0 <= sx.min():
            continue
        idx = np.flatnonzero(sx == x0)
        assert idx.size, f"нет точки насыщенной при x = {x0}"
        assert abs(y0 - sy[idx[0]]) <= 1e-9 * abs(sy[idx[0]]), (ax.get_ylabel(), x0, y0, sy[idx[0]])
        n += 1
    check(n == 7, f"D: {ax.get_ylabel()}: все 7 ветвей начинаются на насыщенной")

lw_br = max(ln.get_linewidth() for ln in _lines(axes[0, 2], "pvto_branch"))
check(all(len(_lines(ax, "pvto_rs0")) == 1 and _lines(ax, "pvto_rs0")[0].get_linewidth() > lw_br
          for ax in (axes[0, 0], axes[0, 1], axes[0, 2], axes[1, 2])), "E: R_s,0 одна и толще ветвей")
check(axes[0, 0].get_yscale() == "log" and axes[0, 2].get_yscale() == "linear", "F: mu_o — лог. шкала")
labels = [t.get_text() for t in axes[0, 0].get_legend().get_texts()]
check(len(labels) == 3, f"H: в легенде mu_o 3 записи: {labels}")
check(not any(_lines(ax, "pvto_saturated_extrap") for ax in axes.ravel()), "I: у корреляции нет пунктира")
fig.savefig(OUT / "core_standing_rs50.png", dpi=90)
plt.close(fig)

pvt0 = StandingFullPVT(rho_o_std=850.0, rho_g_std=0.9, T0=350.0, Rs0=0.0)
fig, axes = _plot(pvt0, 0.0, (15e6, 20e6))
rs0 = _lines(axes[0, 1], "pvto_rs0")
check(len(rs0) == 1 and rs0[0].get_xdata()[0] == 12.0 and np.all(rs0[0].get_ydata() == 0.0),
      "G: R_s,0 = 0 — горизонталь через всю ось")
check(axes[0, 1].get_ylim()[1] > 100.0 and len(_lines(axes[0, 1], "pvto_branch")) >= 3,
      f"G: насыщенная и веер нарисованы, ylim R_s = {axes[0, 1].get_ylim()[1]:.1f}")
check(all(np.min(ln.get_xdata()) >= 12.0 - 1e-12 for ax in axes.ravel() for ln in ax.get_lines()),
      "G: вертикали p_b < 0 нет")
plt.close(fig)


# ── Шаг 4: табличный PVT (узлы — через _pvt_table_nodes + p_branch шага 3) ──
def table_nodes(pv, Rs0):
    nodes = pvt_plot._pvt_table_nodes(pv, Rs0)
    proto = pv._hydro._pvt
    rs_near = min(proto.rs_values, key=lambda r: abs(r - Rs0))
    p_branch = np.array([x[0] for x in proto.branches[rs_near]], float) * 1e5
    nodes["p_branch"] = p_branch if np.isclose(rs_near, Rs0) else np.empty(0)
    return nodes


def ex_pvt(name):
    return _create_pvt(load_config(NS / "examples" / name / "config.json"))


pv14 = ex_pvt("14_high_gor_cooling")
n14 = table_nodes(pv14, 150.0)
fig, axes = _plot(pv14, 150.0, (6e6, 24.5e6), n14)
check(len(_lines(axes[0, 0], "pvto_branch")) == 17 and len(_lines(axes[0, 0], "pvto_rs0")) == 1,
      "J: 14 — 17 тонких ветвей + R_s,0")
check(len(axes[0, 0].get_legend().get_texts()) <= 5, "J: легенда 14 не больше 5 записей")
pb160 = float(pv14.pb(np.array([160.0]))[0])
mk = [ln for ln in axes[0, 0].get_lines() if ln.get_marker() == "o" and ln.get_color() == "C3"][0]
i = np.flatnonzero(np.isclose(mk.get_xdata(), pb160 / 1e6, rtol=0, atol=1e-9))
mu160 = float(pv14.mu_o(np.array([pb160]), np.array([160.0]))[0])
mu150 = float(pv14.mu_o(np.array([pb160]), np.array([150.0]))[0])
check(i.size == 1 and abs(mk.get_ydata()[i[0]] - mu160) <= 1e-12 and abs(mu160 - mu150) / mu150 > 0.05,
      f"L: начало строки 160 — на своей ветви ({mu160:.4e}), не на R_s,0 ({mu150:.4e})")
fig.savefig(OUT / "ex14.png", dpi=90)
plt.close(fig)

pv04 = ex_pvt("04_table_table")
n04 = table_nodes(pv04, 30.0)
check(np.allclose(n04["p_branch"], [15e6, 30e6]), "M: p_branch 04 = 15, 30 МПа")
check(table_nodes(pv04, 20.0)["p_branch"].size == 0, "N: R_s,0 между строками — p_branch пуст")
fig, axes = _plot(pv04, 30.0, (4e6, 20e6), n04)
ext = _lines(axes[0, 0], "pvto_saturated_extrap")
sol = _lines(axes[0, 0], "pvto_saturated")
check(len(ext) == 2 and np.isclose(ext[0].get_xdata().max(), 5.0) and np.isclose(ext[1].get_xdata().min(), 15.0),
      "K: пунктир слева до 5 МПа и справа от 15 МПа")
check(len(sol) == 1 and np.isclose(sol[0].get_xdata().min(), 5.0) and np.isclose(sol[0].get_xdata().max(), 15.0),
      "K: сплошная насыщенная — ровно 5…15 МПа")
fig.savefig(OUT / "ex04a_axis.png", dpi=90)
plt.close(fig)

# ── Превью штатных примеров на оси (min p_wf, p0) ──
for name in ("01_single_phase_no_jt", "03_standing_corey", "20_rs300_cooling"):
    cfg = load_config(NS / "examples" / name / "config.json")
    pv = _create_pvt(cfg)
    pw = [h.p_wf for h in cfg.time.history if getattr(h, "p_wf", None) is not None]
    fig, axes = _plot(pv, cfg.initial_conditions.Rs0, (min(pw), cfg.initial_conditions.p0))
    fig.suptitle(name)
    fig.tight_layout()
    fig.savefig(OUT / f"{name[:2]}.png", dpi=90)
    plt.close(fig)

print("\n".join("OK  " + m for m in ok))
print(f"\nвсе {len(ok)} проверок пройдены; превью: {OUT}")
