"""Сводная проверка баланса энергии по всем примерам (BUG-004).

Прогоняет каждый пример и печатает относительную невязку кумулятивного
баланса энергии. Нужен, чтобы одним запуском видеть, что фикс BUG-004
работает везде, а не только на примере 04, где он был обнаружен.

Эталонные значения в EXAMPLES получены при разработке фикса и служат
регрессионным ориентиром: расхождение больше 2 % означает, что что-то
изменилось в решателе или в самом балансе.

Все примеры считаются ОДНИМ кодом — общим examples/energy_balance.py
(FEAT-016). До выноса своя копия была у 01, 02, 03 и 05, а для остальных
приходилось брать версию примера 03; тогда этот скрипт грузил копии через
importlib под разными именами, потому что обычный import вернул бы первую
из них для всех (все копии назывались одинаково). Теперь копий нет, и
обходной путь не нужен.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\check_energy_balance_all.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = HERE.parent
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from energy_balance import compute_balance  # noqa: E402

# (папка примера, эталонная отн. невязка)
EXAMPLES = [
    ("01_single_phase_no_jt",       5.67e-4),
    ("02_single_phase_jt",          1.87e-3),
    ("03_standing_corey",           9.65e-3),
    ("04_table_table",              4.03e-3),
    ("05_standing_table_rp",        9.64e-3),
    ("06_table_corey_rp",           4.55e-3),
    ("07_degassing_adiabatic_only", 5.76e-3),
    ("08_degassing_jt",             1.84e-3),
    ("09_degassing_latent_heat",    2.26e-3),
    # Единственный пример с λ ≠ 0. Эталон 4.74e-3 относился к версии без
    # кондуктивного члена; с ним (FEAT-016, шаг 4а) невязка 4.33e-3, а
    # порядок сходимости по dt восстановился с 0.751 до 0.980.
    ("10_deep_degassing",           4.33e-3),
]

# Порог приёмки: невязка баланса — ошибка расщепления O(dt), на штатных
# конфигах она порядка 1e-3. Всё, что выше 1e-2, означает пропущенный или
# неверно посчитанный член (именно так проявлялся BUG-004: 0.18-0.29).
TOL_ABSOLUTE = 1e-2
# Допуск на отклонение от эталона.
TOL_REFERENCE = 0.02


def check_one(folder: str, expected: float | None) -> dict:
    """Прогон одного примера + баланс энергии.

    Возвращает {name, rel_residual, expected, status}. Падение примера не
    прерывает обход: возвращается status="ОШИБКА" с текстом исключения,
    чтобы сводная таблица собралась целиком.
    """
    example_dir = HERE / folder

    try:
        config = load_config(example_dir / "config.json")
        config.output.log_level = "WARNING"
        # Прежде здесь ставился save_every = 1: баланс суммировал
        # приращения по сохранённым шагам, и пропуск шагов ломал сумму.
        # После DEBT-013 члены копятся на подшагах внутри решателя,
        # поэтому структура истории на баланс не влияет.

        simulator, initial_state = SimulatorFactory.from_config(config)
        history = simulator.run(initial_state)

        bal = compute_balance(history, simulator._grid, config)
        rel = abs(float(bal["rel_residual"][-1]))

        if rel > TOL_ABSOLUTE:
            status = "ПРОВАЛ"
        elif expected is not None and abs(rel - expected) / expected > TOL_REFERENCE:
            status = "СДВИГ"
        else:
            status = "OK"
        return dict(name=folder, rel_residual=rel,
                    expected=expected, status=status)

    except Exception as exc:                       # noqa: BLE001
        return dict(name=folder, rel_residual=float("nan"),
                    expected=expected,
                    status=f"ОШИБКА: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    results = [check_one(folder, expected) for folder, expected in EXAMPLES]

    print()
    print(f"{'пример':32s} {'невязка':>11s} {'эталон':>11s}  статус")
    print("-" * 72)
    for res in results:
        exp = res["expected"]
        exp_str = f"{exp:11.2e}" if exp is not None else f"{'—':>11s}"
        print(f"{res['name']:32s} "
              f"{res['rel_residual']:11.4e} {exp_str}  {res['status']}")

    bad = [r for r in results if r["status"] != "OK"]
    print()
    if bad:
        print(f"НЕ ПРОШЛИ: {len(bad)} из {len(results)}")
        for r in bad:
            print(f"  {r['name']}: {r['status']}")
        sys.exit(1)
    print(f"ВСЕ {len(results)} примеров прошли: "
          f"невязка <= {TOL_ABSOLUTE:.0e}, совпадает с эталоном")
