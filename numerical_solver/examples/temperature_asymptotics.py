"""Однофазная асимптотика температуры — общая проверка для примеров.

Стационарный предел в ОДНОФАЗНОЙ зоне имеет замкнутый вид:

    T(r) = T_ext + mu_JT,o·[p(r) - p_ext],    p_ext = p_0 — давление на контуре

Скорость сокращается, поэтому профиль не зависит от дебита. Проверка
применима к любому примеру, где есть однофазная зона (Sg = 0).

ДВУХФАЗНОЙ АСИМПТОТИКИ НЕТ. Схема собирает конвекцию, JT и дегазацию в
АДВЕКТИВНОЙ форме — как вклады граней с разностью переносимой величины.
Сумма по ячейкам к крайним граням не сворачивается, и явного выражения
стационарной T в двухфазной зоне нет. Схему на двухфазных сценариях
проверяют:

  - tests/test_energy_matrix_examples.py — поэлементная сверка матрицы
    с постановкой, независимая реализация по тексту .tex;
  - tests/test_energy_balance_examples.py — интегральный баланс энергии,
    невязка на машинном уровне (с DEBT-043 — 0…8e-17 на укороченных
    сценариях, порог 1e-12).

Запуск:
    .venv\\Scripts\\python examples\\temperature_asymptotics.py 02
"""

import sys
from pathlib import Path

import numpy as np

# Порог, ниже которого ячейка считается однофазной
SG_EPS = 1e-12


def single_phase_asymptote(config, history):
    """Однофазная асимптотика: T = T_ext + mu_JT,o·(p - p_0), [N].

    Опорная точка — контур r = R_e, где ГУ задаёт T_ext при p = p_0
    (factory.py: p_ext=ic.p0), а не центр последней ячейки. Схема учитывает
    перепад ext['p'] - p[N-1] на контурной грани (compute_jt), поэтому JT
    работает уже на полуячейке у контура (при mu_JT,o < 0 нефть там
    греется), и асимптота в ячейке N-1 равна T_ext - mu_JT,o·(p_0 - p[N-1]).
    Если ГУ по давлению когда-нибудь отделят от начального давления, p_ext
    надо брать из ГУ, а не из initial_conditions.

    От формы дискретизации НЕ зависит: в однофазной зоне Phi почти постоянен
    (D_j ~ 1e-12, машинный ноль), и адвективная форма даёт тот же результат,
    что дивергентная. Подтверждено VAL-002, кейс B: ошибка против аналитики
    0.0001 %. Эталон VAL-002 (tests/test_val002.py) отсчитывает тоже от p_ext.
    """
    p = history.states[-1].p
    ic = config.initial_conditions
    # Отсчёт от контура: ГУ задаёт T0 при p = p0 (factory.py, p_ext=ic.p0).
    return ic.T0 + config.thermal.mu_JT_oil * (p - ic.p0)


def report_asymptotics(config, history, grid, simulator) -> dict:
    """Печать однофазной проверки. Возвращает сводку.

    Двухфазной части нет — см. шапку модуля. Вызывается
    example_runner.run_example для всех примеров.
    """
    Sg = history.states[-1].Sg
    T = history.states[-1].T
    mask1 = Sg <= SG_EPS

    print("── Асимптотика температуры (однофазная зона) ──")

    if not mask1.any():
        print("  не проверяется: однофазных ячеек нет "
              "(газ во всей области)")
        return dict(applicable=False, err_1ph=np.nan, n_cells=0,
                    T_asymptote=None)

    T_as = single_phase_asymptote(config, history)
    err_1ph = float(np.max(np.abs(T[mask1] - T_as[mask1])))

    print(f"  T = T_ext + mu_JT·(p − p_ext) на {int(mask1.sum())} ячейках "
          f"из {len(Sg)}: max|ΔT| = {err_1ph:.4f} К")
    print("    (расхождение — незавершённая релаксация T к асимптотике)")

    if not mask1.all():
        print("  двухфазная зона: аналитической проверки нет.")
        print("    Схема верифицируется сверкой матрицы с постановкой")
        print("    (test_energy_matrix_examples.py) и балансом энергии.")

    return dict(applicable=True, err_1ph=err_1ph,
                n_cells=int(mask1.sum()), T_asymptote=T_as)


if __name__ == "__main__":
    _HERE = Path(__file__).resolve().parent
    sys.path.insert(0, str(_HERE))
    sys.path.insert(0, str(_HERE.parent))
    # radial_blackoil (прототип гидродинамики) — установленный дистрибутив (DEBT-059)

    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config

    if len(sys.argv) < 2:
        raise SystemExit(
            "укажите пример: python examples\\temperature_asymptotics.py 02")

    name = sys.argv[1]
    root = Path(__file__).parent
    folder = next(d for d in root.iterdir()
                  if d.is_dir() and d.name.startswith(name))

    cfg = load_config(folder / "config.json")
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    report_asymptotics(cfg, hist, sim.grid, sim)
