"""Сводная проверка баланса энергии по всем примерам (BUG-004).

Прогоняет каждый пример и печатает относительную невязку кумулятивного
баланса энергии. Нужен, чтобы одним запуском видеть, что баланс замыкается
везде, а не только на примере, где очередной дефект был обнаружен.

ПРОВЕРЯЕТСЯ УРОВЕНЬ, А НЕ СОВПАДЕНИЕ С ЭТАЛОНОМ (BUG-007, 2026-09-19).
Прежде у каждого примера было своё ожидаемое значение невязки (~1e-3) и
допуск 2 %: невязка считалась физической величиной — ошибкой расщепления
O(dt), — и её уход означал бы изменение в решателе.

Это оказалось неверно. Наблюдавшиеся 1e-3 давал дефект BUG-007:
конвективный член баланса умножал Phi на T^n, тогда как схема неявная и
в матрице стоят T^{n+1}. После исправления невязка на всех 12 примерах
падает до 1e-13...1e-12 — уровня округлений прогонки.

Поэкземплярные эталоны для такой величины бессмысленны: она определяется
порядком суммирования ошибок округления и не воспроизводится между
платформами, версиями numpy и сборками BLAS до второй значащей цифры.
Содержательно проверяемое утверждение одно: баланс замыкается с машинной
точностью. Отсюда единый порог вместо двенадцати эталонов.

Дискретные уравнения схемы — тождество, они замыкаются при ЛЮБОМ dt,
если все члены выписаны на правильных слоях. Поэтому превышение порога
означает дефект в члене, а не грубую дискретизацию. Три известных случая
превышали бы нынешний порог в ~1e9 раз:

    BUG-004 (накопление как разность запасов)      0.20
    FEAT-016 (пропущен кондуктивный член)          4.7e-3 против 4.3e-3
    BUG-007 (конвекция на слое T^n)                1e-3

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

def find_examples() -> list[str]:
    """Папки примеров: NN_имя с config.json внутри, по порядку номера.

    Список строится автодискаверингом, а не перечислением, по той же
    причине, что в run_all.py: жёсткий список молча теряет новые примеры.
    Так уже случилось — пример 11 (создан при DEBT-009) в перечислении не
    появился, и его баланс этой проверкой не покрывался.
    """
    return sorted(d.name for d in HERE.iterdir()
                  if d.is_dir() and (d / "config.json").is_file()
                  and d.name[0].isdigit())


# Порог приёмки. Баланс замыкается с машинной точностью (см. шапку):
# измеренный максимум по 12 примерам — 7.4e-12 при штатном dt. Запас взят
# в два порядка, потому что при измельчении dt невязка растёт: больше
# подшагов — больше операций сложения в кумулятивных суммах.
#
# До BUG-007 порог был 1e-2 и отделял "пропущенный член" (0.18-0.29,
# BUG-004) от мнимой "ошибки расщепления" (~1e-3). Теперь расщепления
# в балансе нет вовсе, и запас между нормой и дефектом — девять порядков
# вместо одного.
TOL_ABSOLUTE = 1e-10


def check_one(folder: str) -> dict:
    """Прогон одного примера + баланс энергии.

    Возвращает {name, rel_residual, status}. Падение примера не прерывает
    обход: возвращается status="ОШИБКА" с текстом исключения, чтобы
    сводная таблица собралась целиком.
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

        status = "OK" if rel <= TOL_ABSOLUTE else "ПРОВАЛ"
        return dict(name=folder, rel_residual=rel, status=status)

    except Exception as exc:                       # noqa: BLE001
        return dict(name=folder, rel_residual=float("nan"),
                    status=f"ОШИБКА: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    examples = find_examples()
    if not examples:
        print(f"В {HERE} не найдено ни одного примера с config.json")
        sys.exit(1)

    results = [check_one(folder) for folder in examples]

    print()
    print(f"{'пример':32s} {'невязка':>12s} {'порог':>12s}  статус")
    print("-" * 70)
    for res in results:
        print(f"{res['name']:32s} {res['rel_residual']:12.4e} "
              f"{TOL_ABSOLUTE:12.0e}  {res['status']}")

    bad = [r for r in results if r["status"] != "OK"]
    print()
    if bad:
        print(f"НЕ ПРОШЛИ: {len(bad)} из {len(results)}")
        for r in bad:
            print(f"  {r['name']}: {r['status']}")
        print("\nНевязка выше порога означает, что какой-то член баланса "
              "выписан неверно\nлибо взят не на том временном слое "
              "(так проявлялись BUG-004 и BUG-007).")
        sys.exit(1)
    print(f"ВСЕ {len(results)} примеров прошли: "
          f"баланс замыкается, невязка <= {TOL_ABSOLUTE:.0e}")
