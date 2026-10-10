"""Сводная проверка баланса энергии по всем примерам.

Прогоняет каждый пример и печатает относительную невязку кумулятивного
баланса энергии. Нужен, чтобы одним запуском видеть, что баланс замыкается
везде.

ПРОВЕРЯЕТСЯ УРОВЕНЬ, А НЕ СОВПАДЕНИЕ С ЭТАЛОНОМ. Дискретные уравнения
схемы — тождество, они замыкаются при ЛЮБОМ dt, если все члены выписаны
на правильных слоях. Невязка — уровень округлений: с DEBT-043 СЛАУ
решается в отклонениях от T_ext, и невязка 0…5e-15. Она определяется
порядком суммирования ошибок округления
и не воспроизводится между платформами, версиями numpy и сборками BLAS до
второй значащей цифры. Поэкземплярные эталоны для такой величины
бессмысленны. Содержательно проверяемое утверждение одно: баланс
замыкается с машинной точностью — отсюда единый порог для всех примеров.
Превышение порога означает дефект в члене, а не грубую дискретизацию.

Все примеры считаются одним кодом — общим examples/energy_balance.py.

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

from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from energy_balance import compute_balance  # noqa: E402

def find_examples() -> list[str]:
    """Папки примеров: NN_имя с config.json внутри, по порядку номера.

    Список строится автодискаверингом, а не перечислением, по той же
    причине, что в run_all.py: жёсткий список молча теряет новые примеры.
    """
    return sorted(d.name for d in HERE.iterdir()
                  if d.is_dir() and (d / "config.json").is_file()
                  and d.name[0].isdigit())


# Порог приёмки. Баланс замыкается с машинной точностью (см. шапку):
# с DEBT-043 (СЛАУ в отклонениях θ = T − T_ext) невязка у всех примеров
# 0…5.2e-15, при измельчении dt до 360 с — до 5.3e-15. Дефектный член
# даёт 5.7e-4 и выше (BUG-007) — на восемь порядков над порогом.
TOL_ABSOLUTE = 1e-12


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
        # Члены баланса копятся на подшагах внутри решателя, поэтому
        # структура истории на баланс не влияет.

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
              "выписан неверно\nлибо взят не на том временном слое.")
        sys.exit(1)
    print(f"ВСЕ {len(results)} примеров прошли: "
          f"баланс замыкается, невязка <= {TOL_ABSOLUTE:.0e}")
