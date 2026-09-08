"""Сводная проверка баланса энергии по всем примерам (BUG-004).

Прогоняет каждый пример и печатает относительную невязку кумулятивного
баланса энергии. Нужен, чтобы одним запуском видеть, что фикс BUG-004
работает везде, а не только на примере 04, где он был обнаружен.

Эталонные значения в EXAMPLES получены при разработке фикса и служат
регрессионным ориентиром: расхождение больше 2 % означает, что что-то
изменилось в решателе или в самом балансе.

Почему у примеров разные источники скрипта: свою копию energy_balance.py
имеют только 01, 02, 03 и 05. Примеры 04 и 06-10 её не имеют (их main.py
идёт через example_runner, который баланс не считает), поэтому для них
берётся полная двухфазная версия из примера 03.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\check_energy_balance_all.py
"""

import sys
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = HERE.parent
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402

# (папка примера, откуда брать energy_balance, эталонная отн. невязка)
#   "self" — своя копия в папке примера
#   "03"   — полная двухфазная версия из 03_standing_corey
EXAMPLES = [
    ("01_single_phase_no_jt",       "self", 5.67e-4),
    ("02_single_phase_jt",          "self", 1.87e-3),
    ("03_standing_corey",           "self", 9.65e-3),
    ("04_table_table",              "03",   4.03e-3),
    ("05_standing_table_rp",        "self", 9.64e-3),
    ("06_table_corey_rp",           "03",   4.55e-3),
    ("07_degassing_adiabatic_only", "03",   5.76e-3),
    ("08_degassing_jt",             "03",   1.84e-3),
    ("09_degassing_latent_heat",    "03",   2.26e-3),
    ("10_deep_degassing",           "03",   4.74e-3),
]

# Порог приёмки: невязка баланса — ошибка расщепления O(dt), на штатных
# конфигах она порядка 1e-3. Всё, что выше 1e-2, означает пропущенный или
# неверно посчитанный член (именно так проявлялся BUG-004: 0.18-0.29).
TOL_ABSOLUTE = 1e-2
# Допуск на отклонение от эталона.
TOL_REFERENCE = 0.02


def _load_balance_module(folder_path: Path, alias: str):
    """Загрузить копию energy_balance.py под уникальным именем модуля.

    Обычный import кэширует первую копию в sys.modules и возвращает её для
    всех последующих (все копии называются одинаково), из-за чего таблица
    считалась бы одним и тем же кодом. Поэтому загружаем явно, каждую под
    своим alias.
    """
    spec = importlib.util.spec_from_file_location(
        alias, folder_path / "energy_balance.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module          # должно стоять до exec_module
    spec.loader.exec_module(module)
    return module


def check_one(folder: str, source: str, expected: float | None) -> dict:
    """Прогон одного примера + баланс энергии.

    Возвращает {name, rel_residual, expected, status}. Падение примера не
    прерывает обход: возвращается status="ОШИБКА" с текстом исключения,
    чтобы сводная таблица собралась целиком.
    """
    example_dir = HERE / folder
    src_dir = example_dir if source == "self" else HERE / "03_standing_corey"

    try:
        balance = _load_balance_module(src_dir, f"eb_{folder}")
        config = load_config(example_dir / "config.json")
        config.output.log_level = "WARNING"
        # Баланс суммирует приращения по шагам — нужны все шаги.
        config.output.save_every = 1

        simulator, initial_state = SimulatorFactory.from_config(config)
        history = simulator.run(initial_state)

        bal = balance.compute_balance(history, simulator._grid, config)
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
    results = [check_one(folder, source, expected)
               for folder, source, expected in EXAMPLES]

    print()
    print(f"{'пример':32s} {'источник':9s} {'невязка':>11s} "
          f"{'эталон':>11s}  статус")
    print("-" * 82)
    for (folder, source, _), res in zip(EXAMPLES, results):
        exp = res["expected"]
        exp_str = f"{exp:11.2e}" if exp is not None else f"{'—':>11s}"
        print(f"{res['name']:32s} {source:9s} "
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
