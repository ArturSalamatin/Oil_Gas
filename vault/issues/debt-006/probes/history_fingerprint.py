"""Отпечаток истории расчёта примеров 03, 04, 05 — побитовая сверка до/после DEBT-006.

Запуск из каталога numerical_solver (основного или worktree), интерпретатор
основного каталога по абсолютному пути:

    cd <корень>\\numerical_solver
    <корень основного каталога>\\numerical_solver\\.venv\\Scripts\\python ^
        <путь к этой пробе> > <файл вывода>

Код берётся из текущего каталога (SOLVER = Path.cwd()), а не из каталога
пробы: иначе в worktree сверка «до/после» молча сравнила бы неизменённый
основной каталог (заметка памяти reference_worktree_pythonpath). Первая
строка вывода — путь импортированного factory.py; её сверять глазами.

Три примера покрывают три пути фабрики:
  03_standing_corey    — Стендинг × Кори: адаптер над StandingFullPVT, ОФП
                         табулируется на 101 узле;
  04_table_table       — таблица × таблица: общий BlackOilPVT и общий
                         TabulatedRelPerm (строка 450 меняет объект PVT
                         адаптера — потоки Q, u, m и через них T);
  05_standing_table_rp — Стендинг × таблица ОФП: адаптер над Стендингом,
                         общий TabulatedRelPerm.

Отпечаток — SHA-256 по байтам всех массивов и repr всех чисел истории:
состояния, потоки HydroResult, скважинные данные, балансы энергии и массы.
Совпадение отпечатков = побитовое совпадение истории.
"""

import hashlib
import sys
import time
from dataclasses import fields, is_dataclass
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из каталога numerical_solver; сейчас {SOLVER}")
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3")]

from gpn_multiphase_solver import factory  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

EXAMPLES = ("03_standing_corey", "04_table_table", "05_standing_table_rp")


def _feed(h, obj) -> None:
    """Добавить объект в хеш: массивы — байтами, числа — repr, рекурсивно."""
    if isinstance(obj, np.ndarray):
        h.update(str(obj.dtype).encode())
        h.update(str(obj.shape).encode())
        h.update(np.ascontiguousarray(obj).tobytes())
    elif is_dataclass(obj):
        for f in fields(obj):
            h.update(f.name.encode())
            _feed(h, getattr(obj, f.name))
    elif isinstance(obj, dict):
        for k in sorted(obj):
            h.update(str(k).encode())
            _feed(h, obj[k])
    elif isinstance(obj, (list, tuple)):
        h.update(f"[{len(obj)}]".encode())
        for x in obj:
            _feed(h, x)
    else:
        # float, int, None, строки — repr различает последний бит float
        h.update(repr(obj).encode())


def main() -> None:
    print(f"Код: {factory.__file__}")
    for name in EXAMPLES:
        t0 = time.perf_counter()
        config = load_config(SOLVER / "examples" / name / "config.json")
        # Журнал по интервалам (72 строки на пример) сверке не нужен
        config.output.log_level = "WARNING"
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)
        h = hashlib.sha256()
        for part in (history.times, history.states, history.hydro_results,
                     history.well_data, history.balance, history.mass_balance):
            _feed(h, part)
        last, wd = history.states[-1], history.well_data[-1]
        print(f"{name}: записей {len(history.states)}, sha256 {h.hexdigest()}")
        # Контрольные числа — чтобы при расхождении сразу видеть масштаб
        print(f"  p[0] = {float(last.p[0])!r} Па, T[0] = {float(last.T[0])!r} К, "
              f"q_o = {float(wd.q_o_std)!r} м³ст/с")
        # Время — в stderr: в файле вывода оно мешало бы сверке
        print(f"  {name}: {time.perf_counter() - t0:.1f} с", file=sys.stderr)


if __name__ == "__main__":
    main()
