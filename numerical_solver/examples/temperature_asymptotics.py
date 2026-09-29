"""Однофазная асимптотика температуры — общая проверка для примеров.

Стационарный предел в ОДНОФАЗНОЙ зоне имеет замкнутый вид:

    T(r) = T_ext + mu_JT,o·[p(r) - p_ext],    p_ext = p_0 — давление на контуре

Скорость сокращается, поэтому профиль не зависит от дебита. Проверка
применима к любому примеру, где есть однофазная зона (Sg = 0).

ДВУХФАЗНАЯ АСИМПТОТИКА БОЛЬШЕ НЕ ПОДДЕРЖИВАЕТСЯ (BUG-012, решение
пользователя 2026-09-22).

Прежде модуль содержал «телескопическую формулу» — явное выражение
стационарной T на гранях, полученное сворачиванием суммы к забою и
контуру:

    T_f = [Phi_N·T_ext - J_N + J_f - L·rho_g,ст·(R_N - R_f)] / Phi_f

Вывод опирался на то, что ВСЕ ТРИ пространственных члена (конвекция, JT,
дегазация) дискретизированы в дивергентной форме: тогда при суммировании
внутренние грани входят дважды с противоположными знаками и уничтожаются
взаимно, оставляя только концы.

После BUG-012 схема собирает все три члена в АДВЕКТИВНОЙ форме — как
вклады граней с разностью переносимой величины. Взаимного уничтожения
нет, сумма к крайним граням не сворачивается, и вывод недействителен
целиком.

Отдельно: разложение перепада T на вклады, которое давал
decompose_two_phase, содержало слагаемое «изменение Phi»

    T_фронт·(Phi_фронт - Phi_забой) / Phi_забой      (+1.3066 К для 03)

Это и был паразитный член T_j·D_j, ради устранения которого заводился
BUG-012. Разложение не просто устарело — оно приписывало физический
смысл артефакту дискретизации.

ЧТО ИСПОЛЬЗОВАТЬ ВМЕСТО. Для проверки схемы на двухфазных сценариях:

  - tests/test_energy_matrix_examples.py — поэлементная сверка матрицы
    с постановкой (DEBT-016), независимая реализация по тексту .tex;
  - tests/test_energy_balance_examples.py — интегральный баланс энергии,
    невязка 1e-13...1e-12;
  - examples/measure_*.py — замеры отдельных членов.

Альтернатива существует, но не реализована: при потоке всюду к скважине
(Phi^+ = 0 на всех гранях) стационарное уравнение вырождается в
рекуррентность T_j = T_{j+1} - (J_j + V_j·Q_deg,j)/Phi^-_{j+1/2}, и
проход от контура даёт профиль с точностью 3e-07 К на установившемся
режиме. Проверено, см. examples/probe_advective_asymptotics.py. По
решению пользователя в production не вводится.

Запуск:
    .venv\\Scripts\\python examples\\temperature_asymptotics.py 02
"""

import sys
from pathlib import Path

import numpy as np

# Порог, ниже которого ячейка считается однофазной
SG_EPS = 1e-12


def _pvt_of(simulator):
    """PVT-объект, которым считалась задача (конвенция closed_form._prepare).

    Берём у решателя, а не создаём заново: проверка обязана видеть ровно
    те свойства, что стояли в расчёте.
    """
    return simulator._energy._pvt


def single_phase_asymptote(config, history):
    """Асимптотика примера 02: T = T_ext + mu_JT,o·(p - p_0), [N].

    Опорная точка — контур r = R_e, где ГУ задаёт T_ext при p = p_0
    (factory.py: p_ext=ic.p0), а не центр последней ячейки. Схема учитывает
    перепад ext['p'] - p[N-1] на контурной грани (compute_jt; DEBT-017,
    BUG-012), поэтому JT работает уже на полуячейке у контура (при
    mu_JT,o < 0 нефть там греется), и асимптота в ячейке N-1 равна
    T_ext - mu_JT,o·(p_0 - p[N-1]). Прежний
    отсчёт от p[N-1] давал постоянный сдвиг на эту величину (BUG-013).
    Если ГУ по давлению когда-нибудь отделят от начального давления, p_ext
    надо брать из ГУ, а не из initial_conditions.

    От формы дискретизации НЕ зависит: в однофазной зоне Phi почти постоянен
    (D_j ~ 1e-12, машинный ноль), и адвективная форма даёт тот же результат,
    что дивергентная. Подтверждено VAL-002, кейс B: ошибка против аналитики
    0.0001 % и до, и после правки BUG-012. Эталон VAL-002
    (tests/test_val002.py) отсчитывает тоже от p_ext.
    """
    p = history.states[-1].p
    ic = config.initial_conditions
    # Отсчёт от контура: ГУ задаёт T0 при p = p0 (factory.py, p_ext=ic.p0).
    return ic.T0 + config.thermal.mu_JT_oil * (p - ic.p0)


def report_asymptotics(config, history, grid, simulator) -> dict:
    """Печать однофазной проверки. Возвращает сводку.

    Двухфазная часть отчёта удалена вместе с телескопической формулой
    (BUG-012) — см. шапку модуля. Сигнатура сохранена: её вызывает
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
    print("    (за 3 суток релаксация не завершена — как в примере 02)")

    if not mask1.all():
        print("  двухфазная зона: аналитической проверки нет (BUG-012).")
        print("    Схема верифицируется сверкой матрицы с постановкой")
        print("    (test_energy_matrix_examples.py) и балансом энергии.")

    return dict(applicable=True, err_1ph=err_1ph,
                n_cells=int(mask1.sum()), T_asymptote=T_as)


if __name__ == "__main__":
    _HERE = Path(__file__).resolve().parent
    sys.path.insert(0, str(_HERE))
    sys.path.insert(0, str(_HERE.parent))
    # radial_blackoil (прототип гидродинамики) не установлен в venv —
    # подключается через sys.path, как в tests/conftest.py
    _PROTO = _HERE.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
    if str(_PROTO) not in sys.path:
        sys.path.insert(0, str(_PROTO))

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
    report_asymptotics(cfg, hist, sim._grid, sim)
