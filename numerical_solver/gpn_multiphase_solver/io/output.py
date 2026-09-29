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

def _physical_rs(pvt, p: np.ndarray, Rs0: float) -> np.ndarray:
    """Газосодержание, реально бывшее в расчёте: Rs(p) = min(Rs_eq(p), Rs0).

    Две ветви минимума:
      p >= pb — нефть недонасыщена, весь газ растворён, Rs держится на Rs0;
      p <  pb — нефть насыщена, избыток газа выделился, Rs = Rs_eq(p).
    То же выражение, что в аналитике примеров (rs_analytics.rs_expected).
    """
    return np.minimum(pvt.Rs_eq(p), Rs0)


def _branch_visible(y_branch: np.ndarray, y_phys: np.ndarray,
                    rtol: float = 1e-9) -> bool:
    """Ветвь несёт информацию, только если отходит от физической кривой.

    У табличного PVT выше p_b выполняется Rs_eq == Rs0, поэтому насыщенная
    ветвь совпадает с физической тождественно (измерено: 0.000e+00) —
    рисовать её незачем, а легенда с несуществующей линией вводит
    в заблуждение. У Стендинга Rs_eq продолжает расти, и ветвь расходится
    (измерено: 2.341e-01 по Bo выше p_b).
    """
    scale = float(np.max(np.abs(y_phys)))
    return float(np.max(np.abs(y_branch - y_phys))) > rtol * max(scale, 1e-30)


def plot_pvt_properties(pvt, Rs0: float, p_range, axes=None,
                        table_nodes=None, label: str = ""):
    """Свойства PVT как функции давления: mu_o, Rs, Bo, mu_g, Bg, плотности.

    Показывает не результат расчёта, а СВОЙСТВА МОДЕЛИ, которой считали:
    именно PVT определяет и профиль давления, и насыщенность.

    pvt         — HydroPVT/FullPVT: нужны Rs_eq, Bo, mu_o, Bg, mu_g, pb,
                  rho_o, rho_g
    Rs0         — начальное газосодержание, м³ст/м³ст; при 0 расчёт
                  однофазный и вторая ветвь вырождена
    p_range     — (p_lo, p_hi), Па: диапазон, который подсветить как рабочий
    axes        — сетка 2x3; создаётся, если None
    table_nodes — узлы табличного PVT: словарь с ключами 'p_gas', 'p_oil'
                  (давления в Па), или None для аналитического PVT
    label       — подпись модели для заголовка первой панели

    Плотности считаются вызовами pvt.rho_o / pvt.rho_g, а не своей формулой:
    rho_o = (rho_o_ст + Rs*rho_g_ст)/Bo — \\eqref{eq:rho_oil}, rho_g = rho_g_ст/Bg.

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
    p_MPa = p / 1e6
    pb = float(pvt.pb(np.array([Rs0]))[0])
    two_phase = Rs0 > 0.0

    Rs_phys = _physical_rs(pvt, p, Rs0)
    Rs_sat = pvt.Rs_eq(p)                    # насыщенная ветвь: Rs = Rs_eq(p)
    Rs_und = np.full_like(p, float(Rs0))     # недонасыщенная: Rs = Rs0 = const

    # Ветви рисуются только на «чужой» половине от p_b: на «своей» их роль
    # играет физическая кривая, которая по построению min(...) совпадает
    # с одной из них и полностью перекрыла бы тонкий пунктир.
    hi = p >= pb        # выше p_b: куда пошла бы насыщенная нефть
    lo = p <= pb        # ниже p_b: куда пошла бы недонасыщенная

    def _two_branch_panel(ax, func, ylabel):
        """Панель величины, зависящей от (p, Rs): физическая кривая + ветви."""
        y_phys = func(p, Rs_phys)
        if two_phase:
            # При Rs0 = 0 ветви не рисуются вовсе: физическая тождественно
            # совпадает с недонасыщенной, а насыщенная нефизична (Rs_eq
            # до 138 м³ст/м³ст при Rs = 0) и растянула бы ось.
            y_sat = func(p, Rs_sat)
            if hi.any() and _branch_visible(y_sat[hi], y_phys[hi]):
                ax.plot(p_MPa[hi], y_sat[hi], "--", lw=1.0, color="C0",
                        label="насыщенная (экстраполяция)")
            y_und = func(p, Rs_und)
            if lo.any() and _branch_visible(y_und[lo], y_phys[lo]):
                ax.plot(p_MPa[lo], y_und[lo], "--", lw=1.0, color="C1",
                        label="недонасыщенная (экстраполяция)")
        ax.plot(p_MPa, y_phys, "-", lw=2.2, color="C2",
                label=r"физическая: $R_s=\min(R_s^{eq},R_{s,0})$")
        ax.set_ylabel(ylabel)
        return y_phys

    # ── Верхний ряд: приоритет задачи — вязкость и газосодержание нефти ──
    _two_branch_panel(axes[0, 0], pvt.mu_o, r"$\mu_o$, Па·с")
    axes[0, 0].set_title(label if label else r"$\mu_o(p)$", fontsize=8)

    ax_rs = axes[0, 1]
    if two_phase:
        ax_rs.plot(p_MPa, Rs_sat, "--", lw=1.0, color="C0",
                   label=r"$R_s^{eq}(p)$ (насыщение)")
        ax_rs.axhline(float(Rs0), color="C1", ls="--", lw=1.0,
                      label=r"$R_{s,0}$")
    ax_rs.plot(p_MPa, Rs_phys, "-", lw=2.2, color="C2",
               label=r"физическая: $\min(R_s^{eq},R_{s,0})$")
    ax_rs.set_ylabel(r"$R_s$, м³ст/м³ст")
    if not two_phase:
        ax_rs.set_title(r"однофазный расчёт: $R_s \equiv 0$", fontsize=8)

    _two_branch_panel(axes[0, 2], pvt.Bo, r"$B_o$")

    # ── Нижний ряд: газовая фаза и плотности ──
    axes[1, 0].plot(p_MPa, pvt.mu_g(p), "-", lw=2, color="C0", label="газ")
    axes[1, 0].set_ylabel(r"$\mu_g$, Па·с")

    axes[1, 1].plot(p_MPa, pvt.Bg(p), "-", lw=2, color="C0", label="газ")
    axes[1, 1].set_ylabel(r"$B_g$")

    # Плотности — на двух осях: нефть 730…800, газ 40…140 кг/м³ (измерено
    # на примере 04), на одной оси форма газовой кривой нечитаема.
    ax_rho = axes[1, 2]
    ax_rho.plot(p_MPa, pvt.rho_o(p, Rs_phys), "-", lw=2, color="C3",
                label=r"$\rho_o$")
    ax_rho_g = ax_rho.twinx()
    ax_rho_g.plot(p_MPa, pvt.rho_g(p), "-", lw=2, color="C0",
                  label=r"$\rho_g$")
    ax_rho.set_ylabel(r"$\rho_o$, кг/м³")
    ax_rho_g.set_ylabel(r"$\rho_g$, кг/м³")

    # ── Узлы табличного PVT ──
    # Наборы разные по природе и идут на разные панели: газовая таблица —
    # на mu_g/Bg, точки насыщения веток и узлы рисуемой ветки — на нефтяные.
    # Ординаты вычисляются ВЫЗОВОМ PVT в точке узла, а не читаются из
    # таблицы: недонасыщенная ветка интерполируется по dp = p - pb(Rs),
    # поэтому маркер иначе не лёг бы на нарисованную кривую.
    if table_nodes is not None:
        p_gas = np.asarray(table_nodes.get("p_gas", []), float)
        p_gas = p_gas[(p_gas >= p[0]) & (p_gas <= p[-1])]
        if p_gas.size:
            axes[1, 0].plot(p_gas / 1e6, pvt.mu_g(p_gas), "o", ms=5,
                            color="C0", zorder=5, label="узлы таблицы")
            axes[1, 1].plot(p_gas / 1e6, pvt.Bg(p_gas), "o", ms=5,
                            color="C0", zorder=5, label="узлы таблицы")

        p_oil = np.asarray(table_nodes.get("p_oil", []), float)
        p_oil = p_oil[(p_oil >= p[0]) & (p_oil <= p[-1])]
        if p_oil.size:
            Rs_at_nodes = _physical_rs(pvt, p_oil, Rs0)
            for ax, func in ((axes[0, 0], pvt.mu_o), (axes[0, 2], pvt.Bo)):
                ax.plot(p_oil / 1e6, func(p_oil, Rs_at_nodes), "o", ms=5,
                        color="C2", zorder=5, label="узлы таблицы")
            ax_rs.plot(p_oil / 1e6, Rs_at_nodes, "o", ms=5, color="C2",
                       zorder=5, label="узлы таблицы")

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
