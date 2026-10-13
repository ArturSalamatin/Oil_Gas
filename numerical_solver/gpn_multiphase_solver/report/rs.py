"""Наложение R_s^eq(p) на профиль газосодержания и печать проверки R_s — для run_case (FEAT-030: из examples/rs_analytics.py).

Проверка (равенство в ячейках со свободным газом, неравенство с допуском
решателя без газа) — gpn_multiphase_solver.diagnostics.rs (DEBT-011), там
же её обоснование.
"""

from __future__ import annotations

import numpy as np

from ..diagnostics.rs import (
    SG_GAS, degassed_cells, front_radius, rs_error, rs_supersaturation)


def make_overlay_rs(config):
    """Собрать overlay-функцию для run_case, замкнув на неё config.

    Хук вызывается как overlay(ax, history, grid, simulator) и своего config
    не получает, а Simulator его не хранит — поэтому конфиг замыкается здесь.
    Так один и тот же код годится для любого примера без обёрток в нём.
    """
    def overlay(ax, history, grid, simulator):
        _draw_rs(ax, history, grid, simulator, config)
    return overlay


def _draw_rs(ax, history, grid, simulator, config):
    """Наложить Rs_eq(p) ячеек со свободным газом на профиль газосодержания.

    Вызывается после отрисовки численных кривых, поэтому отдельного PNG
    не создаётся — точки ложатся в rs_profiles.png.
    """
    pvt = simulator.pvt

    st = history.states[-1]
    Rs0 = config.initial_conditions.Rs0
    gas = st.Sg > SG_GAS

    # Кружки — только в ячейках со свободным газом: там Rs обязано равняться
    # Rs_eq(p). В ячейках без газа равенства нет — нефть может быть
    # недонасыщена (DEBT-026), численная кривая там ограничена сверху, а не
    # задана. Без газа линию не строим: пустая дала бы пункт легенды без точек.
    if np.any(gas):
        ax.semilogx(grid.r_centers[gas], pvt.Rs_eq(st.p[gas]), 'ko',
                    markersize=4, markerfacecolor='none', zorder=5,
                    label=r"$R_s = R_s^{eq}(p)$, ячейки с газом")

    # Линия Rs0: при падающем давлении правее фронта нефть исходная и Rs
    # строго равно Rs0, левее — идёт разгазирование.
    ax.axhline(Rs0, color='gray', linestyle='-.', linewidth=1.0,
               label=rf"$R_{{s,0}}$ = {Rs0:.0f} м³ст/м³ст")

    # Изобара p = pb. Фронтом разгазирования она является, только если
    # свободный газ есть ровно в ячейках с p < pb. После восстановления
    # давления (12, 13b) газ остаётся лишь у забоя, а ниже pb лежит и
    # недонасыщенная нефть; у 04a газ остался и за изобарой. Тогда линия
    # подписывается тем, что она есть, — изобарой.
    r_b = front_radius(config, history, grid, pvt)
    if np.isfinite(r_b):
        below, _pb = degassed_cells(config, history, pvt)
        if np.array_equal(below, gas):
            label = rf"фронт $r_b$ = {r_b:.3f} м"
        else:
            label = rf"изобара $p_b$: $r$ = {r_b:.3f} м"
        ax.axvline(r_b, color='gray', linestyle=':', linewidth=1.5,
                   label=label)


def report_rs(config, history, pvt) -> dict:
    """Печать проверки Rs в консоль. Возвращает сводку."""
    Rs0 = config.initial_conditions.Rs0
    if Rs0 <= 0.0:
        print("── Rs: сценарий однофазный (Rs0 = 0), проверять нечего ──")
        return dict(max_abs=0.0, max_rel=0.0)

    st = history.states[-1]
    tol = config.numerics.rs_switch_tol      # допуск пересыщения решателя (DEBT-008)
    d_abs, d_rel = rs_error(config, history, pvt)
    excess, n_bad = rs_supersaturation(history, pvt, tol)
    below, pb = degassed_cells(config, history, pvt)
    gas = st.Sg > SG_GAS
    one = ~gas
    # Нефть без газа ниже pb бывает только недонасыщенной: газ ушёл из
    # ячейки потоком или растворился весь при росте давления (12, 13b).
    # При монотонно падающем давлении таких ячеек нет.
    n_under = int(np.count_nonzero(one & below))
    # Rs > Rs0 — не нарушение: скопившийся у забоя газ при росте давления
    # выше pb(Rs0) растворяется сверх Rs0, если PVT это допускает.
    n_above = int(np.count_nonzero(st.Rs > Rs0 + tol))

    print("── Rs: равновесие Black Oil без кинетики ──")
    print(f"  ячейки с газом (Sg > {SG_GAS:g}) — {int(gas.sum())}: "
          f"max|Rs_числ - Rs_eq(p)| = {d_abs:.3e} м³ст/м³ст "
          f"({d_rel * 100:.2e} % от Rs0)")
    print(f"  ячейки без газа — {int(one.sum())}: пересыщенных "
          f"(Rs > Rs_eq(p) + {tol:g}) — {n_bad}, "
          f"ниже pb (нефть недонасыщена) — {n_under}")
    if n_bad:
        print(f"    наибольшее Rs - Rs_eq(p) = {excess:.3e} м³ст/м³ст")
    print(f"  Rs: {st.Rs.min():.4f} … {st.Rs.max():.4f} при Rs0 = {Rs0:.1f}, "
          f"pb = {pb / 1e6:.4f} МПа; ячеек с Rs > Rs0: {n_above}")

    return dict(max_abs=d_abs, max_rel=d_rel, n_two_phase=int(gas.sum()),
                n_supersaturated=n_bad, max_excess=excess,
                n_single_below_pb=n_under, n_above_rs0=n_above, pb=pb)
