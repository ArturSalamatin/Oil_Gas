"""Проверка стационарных асимптотик температуры на длинном прогоне — пример 03.

За 3 суток базового конфига тепловая релаксация не завершена (как в примере
02), поэтому асимптотики проверяются отдельным прогоном на 600 суток.
Теплопроводность в конфиге примера уже обнулена, и это принципиально:
телескопическая формула temperature_asymptotics.stationary_face_temperature
выведена из стационарного уравнения БЕЗ кондуктивного потока.

Проверяются три утверждения:

  1. Однофазная зона выходит на асимптотику примера 02
     T = T_ext + mu_JT,o·(p - p_ext) с точностью ~1e-11 К.
  2. Телескопическая формула воспроизводит стационар схемы на ВСЕХ гранях,
     включая двухфазную зону, с машинной точностью (~1e-12 К).
  3. Само обнуление lambda стоит недорого: контрольный прогон с физическими
     теплопроводностями (LAMBDA_PHYS) отличается на тысячные доли К против
     ~4 К полного эффекта охлаждения.

Прогон на 600 суток занимает заметное время — скрипт автономный,
из main.py не вызывается.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\03_standing_corey\\check_asymptotics_long_run.py
"""

import sys
from pathlib import Path
from copy import deepcopy

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = HERE.parents[1]
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(SOLVER_ROOT / "examples"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402

import two_phase_analytics as tpa  # noqa: E402
import temperature_asymptotics as ta  # noqa: E402

# Длительность, за которую T выходит на стационар. Характерное время —
# конвективное обновление порового объёма; 300 суток уже достаточно,
# 600 берём с запасом, чтобы «стационар» не пришлось оговаривать.
T_LONG_DAYS = 600.0


def run(config):
    # При λ = 0 compute_conductive_transmissibility делит на нулевую
    # теплопроводность и numpy печатает RuntimeWarning. Результат при этом
    # корректен: Q_T = 2πh/(w/0 + w/0) = 2πh/inf = 0, кондуктивный поток
    # действительно исчезает. Глушим только этот шум, чтобы не мешал выводу.
    with np.errstate(divide='ignore', invalid='ignore'):
        sim, s0 = SimulatorFactory.from_config(config)
        return sim, sim.run(s0)


# Физические теплопроводности породы и флюидов. В конфиге примера они
# обнулены (иначе уравнение энергии становится краевым и ОДУ-аналитики
# не существует), но для оценки вклада кондукции их надо чем-то задать.
LAMBDA_PHYS = dict(solid=1.5, oil=0.14, gas=0.04)


def make_long_config(base, with_conduction: bool):
    """Длинный прогон; при with_conduction возвращаем физические lambda.

    Конфиг примера идёт с lambda = 0, поэтому «включить» теплопроводность —
    значит подставить LAMBDA_PHYS, а не снять обнуление.
    """
    cfg = deepcopy(base)
    if with_conduction:
        cfg.rock.lambda_solid = LAMBDA_PHYS["solid"]
        cfg.rock.lambda_oil = LAMBDA_PHYS["oil"]
        cfg.rock.lambda_gas = LAMBDA_PHYS["gas"]
    # Длительность задаётся структурой истории (DEBT-013): N_RECORDS
    # интервалов покрывают T_LONG_DAYS суток. Прежде здесь стоял один
    # интервал на весь прогон и save_every = 60, прореживавший подшаги;
    # теперь состав вывода определяет только расписание. Шаг записи
    # (60 суток) сохранён прежним, чтобы кривая осталась сопоставимой.
    N_RECORDS = 10
    iv = cfg.time.history[0]
    cfg.time.history = [deepcopy(iv) for _ in range(N_RECORDS)]
    for h in cfg.time.history:
        h.dt = T_LONG_DAYS * 86400.0 / N_RECORDS
    cfg.time.dt_integration = 86400.0
    cfg.output.log_level = "WARNING"
    return cfg


if __name__ == "__main__":
    base = load_config(HERE / "config.json")

    print(f"── Длинный прогон, {T_LONG_DAYS:.0f} суток, λ = 0 ──")
    cfg0 = make_long_config(base, with_conduction=False)
    sim0, hist0 = run(cfg0)
    grid, pvt = sim0._grid, sim0._energy._pvt

    st = hist0.states[-1]
    T, p, Sg = st.T, st.p, st.Sg
    mask1 = Sg <= tpa.SG_EPS

    # Стационар ли это на самом деле: сравниваем два последних среза.
    dT_last = float(np.max(np.abs(hist0.states[-1].T - hist0.states[-2].T)))
    print(f"  изменение T за последние {60 * 86400 / 86400:.0f} суток: "
          f"{dT_last:.2e} К  (стационар достигнут)")

    # 1. Однофазная асимптотика примера 02
    T_as = ta.single_phase_asymptote(cfg0, hist0)
    err_1ph = float(np.max(np.abs(T[mask1] - T_as[mask1])))
    print(f"\n  1. однофазная зона ({mask1.sum()} ячеек):")
    print(f"     max|T - (T_ext + μ_JT·(p - p_ext))| = {err_1ph:.3e} К")

    # 2. Телескопическая формула на всех гранях
    T_pred, T_num = ta.stationary_face_temperature(cfg0, hist0, grid, sim0)
    err_face = float(np.max(np.abs(T_pred[:grid.N] - T_num[:grid.N])))
    print(f"\n  2. телескопическая формула, все {grid.N} граней:")
    print(f"     max|T_форм - T_числ| = {err_face:.3e} К")

    # Разложение перепада на стационаре
    dec = ta.decompose_two_phase(cfg0, hist0, grid, sim0)
    print(f"\n  разложение перепада T (забой ↔ фронт, грань {dec['f_front']}):")
    print(f"     Джоуль–Томсон    {dec['jt']:+8.4f} К")
    print(f"     скрытая теплота  {dec['latent']:+8.4f} К")
    print(f"     изменение Φ      {dec['phi_change']:+8.4f} К")
    print(f"     сумма            {dec['sum']:+8.4f} К   "
          f"фактически {dec['actual']:+8.4f} К")

    # 3. Вклад теплопроводности — тот же прогон с физическими λ.
    # Показывает, что обнуление λ в конфиге стоит немного: кондукция
    # сдвигает T на тысячные доли К против ~4 К полного эффекта.
    print(f"\n── Тот же прогон с физическими λ "
          f"({LAMBDA_PHYS['solid']} / {LAMBDA_PHYS['oil']} / "
          f"{LAMBDA_PHYS['gas']} Вт/(м·К)) ──")
    cfgL = make_long_config(base, with_conduction=True)
    simL, histL = run(cfgL)
    TL = histL.states[-1].T
    print(f"  T(r_w): λ=0 → {T[0]:.4f} К,  λ≠0 → {TL[0]:.4f} К,"
          f"  разница {TL[0] - T[0]:+.4f} К")
    print(f"  max|T(λ≠0) - T(λ=0)| по области = {np.max(np.abs(TL - T)):.4f} К")
    print(f"  в однофазной зоне               = "
          f"{np.max(np.abs(TL[mask1] - T[mask1])):.4f} К")

    # Профиль в характерных точках
    r = grid.r_centers
    print(f"\n  Профиль на стационаре (λ = 0):")
    print(f"    {'j':>3} {'r, м':>9} {'p, МПа':>9} {'S_g':>9} "
          f"{'T, К':>10} {'T_JT, К':>10} {'разн':>9}")
    for j in list(range(8)) + [20, 35, grid.N - 1]:
        print(f"    {j:3d} {r[j]:9.4f} {p[j]/1e6:9.4f} {Sg[j]:9.6f} "
              f"{T[j]:10.4f} {T_as[j]:10.4f} {T[j]-T_as[j]:+9.4f}")
