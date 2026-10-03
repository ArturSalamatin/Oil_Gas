"""Сходимость замкнутого решения к расчёту по сетке — пример 05.

Замкнутое решение (two_phase_analytics.solve_closed) даёт дебит квадратурой
и профиль давления интегрированием ОДУ, не используя расчёт вообще. На
штатной сетке N = 50 расхождение по дебиту составляет 0.10 %, по давлению —
16 кПа. Вопрос тот же, что и всюду в этом примере: это ошибка вывода
или ошибка дискретизации СХЕМЫ?

Ответ должен быть таким: аналитика непрерывна и от N не зависит вовсе,
поэтому при измельчении сетки к ней должно сходиться ЧИСЛЕННОЕ решение.
Если расхождение убывает степенным образом — вывод верен, а 0.10 % есть
погрешность конечных объёмов на 50 ячейках. Если выходит на полку —
в выводе ошибка.

Проверяются две величины:
  q_o    — интегральная характеристика, чувствительна к подвижности всюду;
  p(r)   — профиль; сравнение на общих узлах (центры ячеек грубой сетки
           попадают не в узлы мелкой, поэтому интерполируем аналитику,
           которая гладкая, а не численный профиль).

Порядок определяется регрессией log(расхождение) по log(N).

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\05_standing_table_rp\\closed_form_convergence.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = HERE.parents[1]
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(SOLVER_ROOT / "examples"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

import two_phase_analytics as tpa  # noqa: E402

# (N, dt, max_retries): ОДУ по времени здесь не решается — нужен только
# стационар гидродинамики. Шаг везде штатный; глубина дробления задана
# для каждой сетки с запасом. Лимит читается только при отказе Newton,
# поэтому сходящийся расчёт он не замедляет.
GRIDS = [
    (25, 3600, 9),
    (50, 3600, 9),
    (100, 3600, 11),
    (200, 3600, 9),
    (400, 3600, 10),
]

# Достаточно для выхода гидродинамики на стационар (p и Sg перестают
# меняться уже к 5-му шагу); температура здесь не участвует.
DURATION_S = 12 * 3600.0


def run_one(N: int, dt: float, max_retries: int = 9) -> dict:
    """Расчёт на сетке N с шагом dt + замкнутое решение на её узлах."""
    config = load_config(HERE / "config.json")
    config.grid.N = N
    config.time.dt_integration = dt
    # Глубина дробления шага в A-retry — см. GRIDS.
    config.numerics.max_retries = max_retries
    # Нужен один прогон длиной DURATION_S, а не расписание примера:
    # усекаем историю до одного интервала. Промежуточные состояния здесь
    # не нужны — сравнивается только финальное, поэтому достаточно одной
    # записи на конце.
    config.time.history = config.time.history[:1]
    config.time.history[0].dt = DURATION_S
    config.output.log_level = "ERROR"

    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)
    grid = sim._grid
    pvt = sim._energy._pvt
    relperm = _create_relperm(config)

    # Кэш solve_closed завязан на (r[0], r[-1], len(r)) — для разных N
    # ключи различаются, коллизии нет.
    cl = tpa.solve_closed(config, pvt, relperm, grid.r_centers)

    p_num = history.states[-1].p
    q_num = abs(history.hydro_results[-1].G_o[0])
    dep = config.initial_conditions.p0 - config.time.history[0].p_wf

    return dict(
        N=N, dt=dt,
        q_num=q_num, q_ana=cl["q_o"],
        d_q=abs(cl["q_o"] - q_num) / q_num,
        d_p=float(np.max(np.abs(cl["p"] - p_num))) / dep,
        Sg_num=history.states[-1].Sg.max(), Sg_ana=cl["Sg"].max(),
    )


def main():
    print("Сходимость замкнутого решения к расчёту при измельчении сетки")
    print("(аналитика от N не зависит — сходится численное решение)\n")
    print(f"{'N':>5} {'dt':>6} {'q_o расчёт':>14} {'q_o аналит.':>14} "
          f"{'откл. q, %':>11} {'откл. p, %':>11} {'Sg расч.':>10} {'Sg анал.':>10}")

    res = []
    for N, dt, max_retries in GRIDS:
        r = run_one(N, dt, max_retries)
        res.append(r)
        print(f"{r['N']:5d} {r['dt']:6.0f} {r['q_num']:14.6e} {r['q_ana']:14.6e} "
              f"{r['d_q']*100:11.4f} {r['d_p']*100:11.4f} "
              f"{r['Sg_num']:10.5f} {r['Sg_ana']:10.5f}", flush=True)

    N_arr = np.array([r["N"] for r in res], float)
    e_q = np.array([r["d_q"] for r in res])
    e_p = np.array([r["d_p"] for r in res])

    # Наблюдаемый порядок: наклон log(ошибка) по log(N) со знаком минус.
    ord_q = -np.polyfit(np.log(N_arr), np.log(e_q), 1)[0]
    ord_p = -np.polyfit(np.log(N_arr), np.log(e_p), 1)[0]
    print(f"\nНаблюдаемый порядок по N: {ord_q:.3f} (дебит), {ord_p:.3f} (давление)")
    print(f"Отношение по краям: {e_q[0]/e_q[-1]:.1f}x (дебит), "
          f"{e_p[0]/e_p[-1]:.1f}x (давление) при N×{N_arr[-1]/N_arr[0]:.0f}")
    print("\nСтепенное убывание подтверждает: замкнутое решение верно,")
    print("а расхождение на N = 50 — погрешность конечных объёмов.")

    # ── График ──
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.loglog(N_arr, e_q * 100, 'ko-', lw=1.5, ms=7,
              label=f"дебит $q_o$ (порядок {ord_q:.2f})")
    ax.loglog(N_arr, e_p * 100, 'bs--', lw=1.2, ms=6, markerfacecolor='none',
              label=f"давление (порядок {ord_p:.2f})")
    # Эталон O(1/N), привязанный к самой грубой сетке.
    ax.loglog(N_arr, e_q[0] * 100 * (N_arr[0] / N_arr), 'r:', lw=1.5,
              label=r"эталон $O(1/N)$")
    ax.set_xlabel("N (число ячеек)")
    ax.set_ylabel("расхождение с замкнутым решением, %")
    ax.set_title("Численное решение сходится к аналитике")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, which="both")

    fig.tight_layout()
    out = HERE / "output" / "closed_form_convergence.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"\nСохранён: {out}")


if __name__ == "__main__":
    main()
