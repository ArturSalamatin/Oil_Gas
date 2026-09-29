"""Проверка происхождения двух линейных участков профиля T(ln r).

В логарифмической шкале профиль температуры состоит из двух линейных
участков с плавным переходом. Скрипт проверяет, что их наклоны
определяются двумя разными механизмами:

  ближний (r мал)  — JT-стационар:
      dT/dlnr = mu_JT * C
  дальний (r велик) — замороженный след адиабатического импульса 1-го шага:
      dT/dlnr = phi * (1 + rho*cp*mu_JT) / (rho*cp)_eff * C

где C = dp/dlnr = (p0 - p_wf)/ln(R_e/r_w) — наклон профиля Дюпюи.

Гипотеза проверяема: при удвоении mu_JT ближний наклон обязан
удвоиться (он линеен по mu_JT), а дальний — измениться лишь в
(1 + 2*rho*cp*mu_JT)/(1 + rho*cp*mu_JT) раза. При mu_JT = -4e-7 это
-0.835: удвоенный mu_JT делает множитель адиабатики (= alpha*T)
отрицательным. Физически так не бывает, но формулу наклона это не
отменяет — проверка формальная.
Скрипт считает базовый и удвоенный варианты и сверяет оба предсказания.

Диагностический скрипт, из main.py не вызывается.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\02_single_phase_jt\\check_slopes.py
"""

import json
import sys
import warnings
from copy import deepcopy
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = HERE.parents[1]
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory

# Множители mu_JT относительно конфига. 1.0 — базовый вариант.
MU_FACTORS = [1.0, 2.0]


def theoretical_slopes(config, pvt, rock, mu_JT):
    """Предсказанные наклоны dT/dlnr для ближней и дальней зон, К.

    Возвращает (near, far, C).
    """
    r_w = config.geometry.r_well
    R_e = config.geometry.R_ext
    p0 = config.initial_conditions.p0
    T0 = config.initial_conditions.T0
    p_wf = config.time.history[0].p_wf
    phi = config.rock.porosity

    # Наклон профиля Дюпюи: p линеен по ln r, dp/dlnr = const
    C = (p0 - p_wf) / np.log(R_e / r_w)

    rho_o = pvt.rho_o(np.array([p0]), np.array([0.0]))[0]
    c_p_o = pvt.c_p_oil(np.array([p0]), np.array([T0]))[0]
    rho_cp_eff = (1 - phi) * rock.rho_cp_solid + phi * rho_o * c_p_o

    # Ближняя зона: конвекция + JT уже переработали профиль до стационара
    near = mu_JT * C

    # Дальняя зона: конвекция ещё не дошла, держится профиль от
    # адиабатического импульса 1-го шага с множителем (1 + rho*cp*mu_JT)
    adiab_factor = 1.0 + rho_o * c_p_o * mu_JT
    far = phi * adiab_factor * C / rho_cp_eff

    return near, far, C


def measured_slopes(r, T):
    """Наклоны dT/dlnr, измеренные на краях профиля.

    Ближний — среднее по первым ячейкам, дальний — по последним, но не
    по самой приконтурной: там ГУ Дирихле T = T_ext искажает наклон.
    """
    d = np.gradient(T, np.log(r))
    return float(np.mean(d[:4])), float(np.mean(d[-8:-3]))


def run(config_base, factor):
    """Прогон с mu_JT, умноженным на factor. Возвращает срез результатов."""
    config = deepcopy(config_base)
    mu_JT = config_base.thermal.mu_JT_oil * factor
    config.thermal.mu_JT_oil = mu_JT

    sim, initial = SimulatorFactory.from_config(config)
    history = sim.run(initial)
    grid = sim._grid

    near_th, far_th, C = theoretical_slopes(
        config, sim._energy._pvt, sim._energy._rock, mu_JT)

    # Ближний наклон меряем на финале: там конвекция уже вывела
    # приствольную зону на JT-стационар.
    near_ms, _ = measured_slopes(grid.r_centers, history.states[-1].T)

    # Дальний — на 1-м шаге, сразу после адиабатического импульса.
    # К финалу конвекция успевает подобраться и к дальней зоне, наклон
    # начинает дрейфовать в сторону JT-стационара (см. таблицу дрейфа).
    _, far_ms = measured_slopes(grid.r_centers, history.states[1].T)
    _, far_ms_final = measured_slopes(grid.r_centers, history.states[-1].T)

    # Дрейф дальнего наклона по шагам — показывает, что отклонение
    # от теории накапливается со временем, а не является ошибкой формулы.
    drift_steps = [1, 6, 24, len(history.times) - 1]
    drift = [(n, measured_slopes(grid.r_centers, history.states[n].T)[1])
             for n in drift_steps]

    return dict(
        factor=factor, mu_JT=mu_JT, C=C,
        r=grid.r_centers, T=history.states[-1].T,
        near_th=near_th, far_th=far_th,
        near_ms=near_ms, far_ms=far_ms, far_ms_final=far_ms_final,
        drift=drift, times=history.times,
    )


def main():
    config_base = load_config(HERE / "config.json")
    results = [run(config_base, f) for f in MU_FACTORS]

    C = results[0]["C"]
    print(f"Наклон профиля Дюпюи: C = dp/dlnr = {C:.0f} Па\n")

    print("Наклоны dT/dlnr, К (теория / измерено):")
    print(f"  {'mu_JT':>10s}  {'ближний (финал)':>19s}  {'дальний (шаг 1)':>19s}")
    for res in results:
        print(f"  {res['mu_JT']:.1e}  "
              f"{res['near_th']:8.4f} /{res['near_ms']:9.4f}  "
              f"{res['far_th']:8.4f} /{res['far_ms']:9.4f}")

    # ── Проверка предсказаний при удвоении mu_JT ──
    base, doubled = results[0], results[1]
    print("\nОтношение при удвоении mu_JT:")

    near_ratio = doubled["near_ms"] / base["near_ms"]
    print(f"  ближний наклон: {near_ratio:.3f}  (ожидаем 2.000 — линеен по mu_JT)")

    far_ratio = doubled["far_ms"] / base["far_ms"]
    far_expected = doubled["far_th"] / base["far_th"]
    print(f"  дальний наклон: {far_ratio:.3f}  (ожидаем {far_expected:.3f} — "
          f"растёт только через множитель адиабатики)")

    # ── Дрейф дальнего наклона ──
    # Формула для дальней зоны точна сразу после адиабатического импульса.
    # Затем конвекция добирается и туда, вытягивая наклон к JT-стационару.
    print("\nДрейф дальнего наклона (конвекция доходит до дальней зоны):")
    hdr_base = f"mu={base['mu_JT']:.0e}"
    hdr_dbl = f"mu={doubled['mu_JT']:.0e}"
    print(f"  {'шаг':>5s} {'t, ч':>7s} {hdr_base:>10s} {hdr_dbl:>10s} "
          f"{'отнош.':>8s}")
    for (n, v_base), (_, v_dbl) in zip(base["drift"], doubled["drift"]):
        t_h = base["times"][n] / 3600.0
        print(f"  {n:5d} {t_h:7.1f} {v_base:10.4f} {v_dbl:10.4f} "
              f"{v_dbl / v_base:8.3f}")
    print(f"  теория:              {base['far_th']:10.4f} "
          f"{doubled['far_th']:10.4f} {far_expected:8.3f}")

    # ── График ──
    fig, ax = plt.subplots(figsize=(8, 5.5))
    colors = ['tab:blue', 'tab:red']

    # Общий размах для смещения опорных прямых вниз от кривых
    span = max(res["T"].max() - res["T"].min() for res in results)

    for res, col in zip(results, colors):
        r, T = res["r"], res["T"]
        ax.semilogx(r, T, color=col, linewidth=1.6,
                    label=fr"расчёт, $\mu_{{JT}}$ = {res['mu_JT']:.0e}")

        # Опорные прямые — короткие отрезки, смещённые вниз, иначе
        # ложатся прямо на кривые и наклон не читается.
        r_near = np.array([r[0], 1.0])
        ax.semilogx(r_near,
                    T[0] - 0.10 * span + res["near_th"] * np.log(r_near / r[0]),
                    color=col, linestyle='--', linewidth=2.0, alpha=0.8)

        r_far = np.array([8.0, r[-1]])
        ax.semilogx(r_far,
                    T[-1] - 0.22 * span + res["far_th"] * np.log(r_far / r[-1]),
                    color=col, linestyle=':', linewidth=2.4, alpha=0.8)

    # Записи в легенду для наклонов — по одной, без дублей на каждый прогон
    ax.plot([], [], 'k--', linewidth=2.0,
            label=r"наклон $\mu_{JT}\,C$ (JT-стационар)")
    ax.plot([], [], 'k:', linewidth=2.4,
            label=r"наклон $\varphi(1{+}\rho c_p \mu_{JT})C/(\rho c_p)_{eff}$ (адиабатика)")

    ax.set_xlabel("r, м")
    ax.set_ylabel("T, К")
    ax.set_title("Два линейных участка профиля T(ln r) и их наклоны\n"
                 "(финальный момент, 3 суток)")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(True, alpha=0.3, which="both")

    fig.tight_layout()
    out_dir = HERE / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "slopes.png"
    # Стираем результат прошлого прогона. Остальные файлы в output/ пишет
    # main.py примера, и трогать их нельзя: этот скрипт их не восстановит.
    out_path.unlink(missing_ok=True)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"\nСохранён: {out_path}")


if __name__ == "__main__":
    main()
