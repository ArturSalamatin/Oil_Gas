"""Наложения замкнутого решения на профили и его сверка с расчётом — для run_example.

Само решение (вывод, формулы (1)–(3), фронт по p = p_b) —
gpn_multiphase_solver.diagnostics.closed_form (DEBT-011). Здесь —
хуки наложений для профилей p и S_g и печать сверки report_closed.
"""

from __future__ import annotations

import numpy as np

from gpn_multiphase_solver.diagnostics.closed_form import (
    saturation_from_numeric, solve_closed)


# ── Хуки для example_runner ──────────────────────────────────────

def _prepare(history, grid, simulator, config):
    """Общая подготовка overlay: PVT, ОФП и решение на сетке примера."""
    # PVT и ОФП — объекты решателя, которыми считалась задача (DEBT-011)
    pvt = simulator.pvt
    relperm = simulator.relperm
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
    dep = config.initial_conditions.p0 - cl["p_wf"]
    d_p = float(np.abs(cl["p"] - p_num).max())

    print("── Замкнутое решение (GOR = Rs0): из расчёта ничего не берётся ──")
    print(f"  q_o: {cl['q_o']:.6e} аналитика vs {q_num:.6e} расчёт "
          f"({abs(cl['q_o'] - q_num) / q_num * 100:.3f} %)")
    if config.time.history[-1].control == "rate":
        # При заданном дебите решение построено обращением (3) по нему:
        # совпадение q_o — по построению, содержательна сверка профиля p.
        print(f"  (дебит задан: совпадение q_o по построению; "
              f"p_wf* = {cl['p_wf'] / 1e6:.4f} МПа)")
    print(f"  max|p_ана - p_чис| = {d_p / 1e3:.2f} кПа "
          f"({d_p / dep * 100:.3f} % депрессии)")
    print(f"  Sg макс: {cl['Sg'].max():.5f} аналитика vs "
          f"{Sg_num.max():.5f} расчёт")
    print(f"  фронт r_b = {cl['r_b']:.4f} м (p = pb = {cl['pb'] / 1e6:.3f} МПа)")

    # Проверка самого замыкания, без наследования ошибки давления:
    # подставляем численное p и смотрим, даёт ли оно численную Sg.
    Sg_at_p_num = saturation_from_numeric(config, history, simulator.pvt,
                                          simulator.relperm)
    two = Sg_num > 1e-12
    d_abs = float(np.abs(Sg_at_p_num - Sg_num).max())
    d_rel = (float((np.abs(Sg_at_p_num - Sg_num)[two] / Sg_num[two]).max()) * 100
             if two.any() else 0.0)
    print(f"  замыкание при численном p: max|dSg| = {d_abs:.2e} "
          f"({d_rel:.4f} % в двухфазной зоне)")

    return dict(q_o=cl["q_o"], q_num=q_num, d_p=d_p, r_b=cl["r_b"],
                dSg_closure=d_abs)
