"""Сохранение результатов и визуализация.

Сериализация:
  save_npz      — SimulationHistory → .npz (numpy)
  save_csv      — SimulationHistory → .csv (tidy format, профили по ячейкам)
  save_well_csv — SimulationHistory → .csv (скважинная история, шаг = строка)

Визуализация (matplotlib):
  plot_profiles        — p(r), T(r), Sg(r) на выбранных моментах (semilogx)
  plot_wellbore_dynamics — p(rw,t), T(rw,t), Sg(rw,t)
  plot_well_rate       — q_o(t), q_g(t) из WellData
  plot_2d_map          — pcolormesh(r, t, field)
  plot_pvt_properties  — mu_o, Rs, Bo, mu_g, Bg, плотности как функции p
"""

from pathlib import Path

import numpy as np

from ..state import SimulationHistory
from ..grid.base import Grid
from ..units import S_TO_DAY


# ═══════════════════════════════════════════════════════════
# Вспомогательная функция: история → словарь массивов
# ═══════════════════════════════════════════════════════════

def history_to_arrays(history: SimulationHistory) -> dict[str, np.ndarray]:
    """Упаковать SimulationHistory в словарь numpy-массивов.

    Возвращает:
      times  — [K]
      p      — [K, N]
      T      — [K, N]
      Sg     — [K, N]
      Rs     — [K, N]
      q_o_std — [K]
      q_g_std — [K]
      p_wf   — [K]
      T_wf   — [K]
    """
    return {
        'times': np.array(history.times),
        'p': np.array([s.p for s in history.states]),
        'T': np.array([s.T for s in history.states]),
        'Sg': np.array([s.Sg for s in history.states]),
        'Rs': np.array([s.Rs for s in history.states]),
        'q_o_std': np.array([w.q_o_std for w in history.well_data]),
        'q_g_std': np.array([w.q_g_std for w in history.well_data]),
        'p_wf': np.array([w.p_wf for w in history.well_data]),
        'T_wf': np.array([w.T_wf for w in history.well_data]),
    }


# ═══════════════════════════════════════════════════════════
# Сохранение: NPZ
# ═══════════════════════════════════════════════════════════

def save_npz(history: SimulationHistory, grid: Grid,
             path: str | Path) -> None:
    """Сохранить SimulationHistory в .npz файл.

    Содержимое:
      r[N], times[K], p[K,N], T[K,N], Sg[K,N], Rs[K,N],
      q_o_std[K], q_g_std[K], p_wf[K], T_wf[K].
    """
    arrays = history_to_arrays(history)
    np.savez(
        path,
        r=grid.r_centers,
        **arrays,
    )


# ═══════════════════════════════════════════════════════════
# Сохранение: CSV (tidy format)
# ═══════════════════════════════════════════════════════════

def save_csv(history: SimulationHistory, grid: Grid,
             path: str | Path) -> None:
    """Сохранить SimulationHistory в CSV (длинная таблица, tidy format).

    Столбцы: step, time_s, r_m, p_Pa, T_K, Sg, Rs.
    Одна строка = одна ячейка на одном сохранённом шаге.
    """
    r = grid.r_centers
    path = Path(path)

    with open(path, 'w', encoding='utf-8') as f:
        f.write("step,time_s,r_m,p_Pa,T_K,Sg,Rs\n")
        for i, state in enumerate(history.states):
            t = history.times[i]
            for j in range(len(r)):
                f.write(
                    f"{i},{t:.6e},{r[j]:.6e},"
                    f"{state.p[j]:.6e},{state.T[j]:.6e},"
                    f"{state.Sg[j]:.6e},{state.Rs[j]:.6e}\n"
                )


# ═══════════════════════════════════════════════════════════
# Сохранение: скважинная история (CSV)
# ═══════════════════════════════════════════════════════════

def save_well_csv(history: SimulationHistory, path: str | Path) -> None:
    """Скважинные данные: одна строка на сохранённый шаг.

    Столбцы: time_s, time_day, q_o_m3st_s, q_g_m3st_s,
             m_o_kg_s, m_g_kg_s, p_wf_Pa, T_wf_K, GOR_m3st_m3st.

    Знак: дебиты > 0 при добыче (q = -G[0], см. WellData).
    GOR = q_g_std / q_o_std; при q_o_std <= 0 записывается пустое поле
    (не NaN — Excel и pandas читают пустое как NaN сами).
    """
    path = Path(path)
    day = 86400.0

    with open(path, 'w', encoding='utf-8') as f:
        f.write("time_s,time_day,q_o_m3st_s,q_g_m3st_s,"
                "m_o_kg_s,m_g_kg_s,p_wf_Pa,T_wf_K,GOR_m3st_m3st\n")
        for t, w in zip(history.times, history.well_data):
            # GOR не определён при нулевом/отрицательном дебите нефти —
            # пустое поле вместо деления на ноль.
            gor = f"{w.q_g_std / w.q_o_std:.6e}" if w.q_o_std > 0.0 else ""
            f.write(
                f"{t:.6e},{t / day:.6e},"
                f"{w.q_o_std:.6e},{w.q_g_std:.6e},"
                f"{w.m_o_well:.6e},{w.m_g_well:.6e},"
                f"{w.p_wf:.6e},{w.T_wf:.6e},{gor}\n"
            )


# ═══════════════════════════════════════════════════════════
# Визуализация
# ═══════════════════════════════════════════════════════════

def plot_profiles(history: SimulationHistory, grid: Grid,
                  times_to_plot: list[float], field: str = 'T',
                  ax=None):
    """Профиль поля (p, T, Sg, Rs) на выбранных моментах времени.

    semilogx — логарифмическая шкала по r (ячейки у скважины мелкие).
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots()

    arrays = history_to_arrays(history)
    r = grid.r_centers
    times = arrays['times']

    labels = {'p': 'p, Па', 'T': 'T, К', 'Sg': 'Sg', 'Rs': 'Rs, м³ст/м³ст'}

    for t_target in times_to_plot:
        # Ближайшая запись ищется в секундах — в них хранится история
        # и задаются times_to_plot. В сутки переводится только подпись:
        # время на всех графиках проекта — в сутках (FEAT-022).
        idx = int(np.argmin(np.abs(times - t_target)))
        ax.semilogx(r, arrays[field][idx, :],
                     label=f"t = {times[idx] * S_TO_DAY:.4g} сут")

    ax.set_xlabel('r, м')
    ax.set_ylabel(labels.get(field, field))
    ax.legend()
    ax.grid(True, alpha=0.3)
    return ax


def plot_wellbore_dynamics(history: SimulationHistory, axes=None):
    """Динамика на забое: p(rw,t), T(rw,t), Sg(rw,t).

    Три графика с общей осью t.
    """
    import matplotlib.pyplot as plt

    if axes is None:
        _, axes = plt.subplots(3, 1, sharex=True, figsize=(8, 8))

    arrays = history_to_arrays(history)
    t = arrays['times'] * S_TO_DAY   # сутки (FEAT-022)

    axes[0].plot(t, arrays['p'][:, 0])
    axes[0].set_ylabel('p(rw), Па')
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(t, arrays['T'][:, 0])
    axes[1].set_ylabel('T(rw), К')
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(t, arrays['Sg'][:, 0])
    axes[2].set_ylabel('Sg(rw)')
    axes[2].set_xlabel('t, сут')
    axes[2].grid(True, alpha=0.3)

    return axes


def plot_well_rate(history: SimulationHistory, ax=None):
    """Дебит скважины: q_o(t) и q_g(t) из WellData."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots()

    arrays = history_to_arrays(history)
    t = arrays['times'] * S_TO_DAY   # сутки (FEAT-022)

    ax.plot(t, arrays['q_o_std'], label='q_o, м³ст/с')
    ax.plot(t, arrays['q_g_std'], label='q_g, м³ст/с')
    ax.set_xlabel('t, сут')
    ax.set_ylabel('Дебит, м³ст/с')
    ax.legend()
    ax.grid(True, alpha=0.3)
    return ax


def plot_2d_map(history: SimulationHistory, grid: Grid,
                field: str = 'T', ax=None):
    """2D карта r-t: pcolormesh(r, t, field).

    Логарифмическая шкала по r.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots()

    arrays = history_to_arrays(history)
    r = grid.r_centers
    t = arrays['times'] * S_TO_DAY   # сутки (FEAT-022)

    labels = {'p': 'p, Па', 'T': 'T, К', 'Sg': 'Sg', 'Rs': 'Rs'}

    c = ax.pcolormesh(r, t, arrays[field], shading='auto', cmap='coolwarm')
    ax.set_xlabel('r, м')
    ax.set_ylabel('t, сут')
    ax.set_xscale('log')
    plt.colorbar(c, ax=ax, label=labels.get(field, field))
    return ax


# ═══════════════════════════════════════════════════════════
# Визуализация: свойства PVT
# ═══════════════════════════════════════════════════════════

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
