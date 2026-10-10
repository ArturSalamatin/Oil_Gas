"""Отпечаток истории расчёта примеров 03, 04, 05 — побитовая сверка до/после DEBT-059.

Путей в sys.path проба не добавляет: пакеты берутся из окружения, в котором
запущен интерпретатор — установка (pip install) или PYTHONPATH. В этом смысл
пробы для DEBT-059: она проверяет то, что импортирует пользователь
установленного пакета. Первые строки вывода — откуда импортированы
gpn_multiphase_solver и radial_blackoil и версия дистрибутива прототипа;
их сверять глазами.

Запуск (каталог examples передаётся явно: в установленном пакете его нет):

    <python> [-I] <путь к пробе> --examples <...>\\numerical_solver\\examples --out <файл вывода>

Файл пишет сама проба (UTF-8 без BOM): перенаправление > в Windows PowerShell 5.1
добавляет BOM, и побайтовая сверка двух файлов ложно расходится.

  - чистое окружение после установки: интерпретатор этого окружения с -I
    (без каталога запуска и PYTHONPATH в sys.path);
  - основной каталог до DEBT-059 (прототип не установлен):
    $env:PYTHONPATH = "<...>\\numerical_solver;<...>\\numerical_solver\\HydroSolverPrototype\\Prototype_1.0.3"

Отпечаток — SHA-256 по байтам всех массивов и repr всех чисел истории
(как в пробе DEBT-006): состояния, потоки HydroResult, скважинные данные,
балансы энергии и массы. Совпадение отпечатков = побитовое совпадение истории.
"""

import argparse
import hashlib
import sys
import time
from dataclasses import fields, is_dataclass
from importlib import metadata
from pathlib import Path

import numpy as np

import radial_blackoil
from gpn_multiphase_solver import factory
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

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


def _dist_version(name: str) -> str:
    """Версия установленного дистрибутива или пометка, что он не установлен."""
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "не установлен"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--examples", required=True, type=Path,
                    help="каталог numerical_solver/examples")
    ap.add_argument("--only", nargs="*", default=list(EXAMPLES),
                    help="подмножество примеров (по умолчанию 03, 04, 05)")
    ap.add_argument("--out", type=Path, default=None,
                    help="файл для строк отпечатка (кроме печати в stdout)")
    args = ap.parse_args()
    lines: list[str] = []

    def emit(text: str) -> None:
        """Строка отпечатка: в stdout и в список для файла --out."""
        print(text)
        lines.append(text)

    # Пути импортов и версии — в stderr: в разных окружениях они разные,
    # а файл вывода (stdout) сверяется построчно
    print(f"gpn_multiphase_solver: {factory.__file__}", file=sys.stderr)
    print(f"radial_blackoil: {radial_blackoil.__file__}", file=sys.stderr)
    print(f"radial_blackoil.__version__ = {radial_blackoil.__version__}; "
          f"дистрибутив radial-blackoil: {_dist_version('radial-blackoil')}; "
          f"numpy {np.__version__}", file=sys.stderr)

    for name in args.only:
        t0 = time.perf_counter()
        config = load_config(args.examples / name / "config.json")
        # Журнал по интервалам сверке не нужен
        config.output.log_level = "WARNING"
        simulator, initial = SimulatorFactory.from_config(config)
        history = simulator.run(initial)
        h = hashlib.sha256()
        for part in (history.times, history.states, history.hydro_results,
                     history.well_data, history.balance, history.mass_balance):
            _feed(h, part)
        last, wd = history.states[-1], history.well_data[-1]
        emit(f"{name}: записей {len(history.states)}, sha256 {h.hexdigest()}")
        # Контрольные числа — чтобы при расхождении сразу видеть масштаб
        emit(f"  p[0] = {float(last.p[0])!r} Па, T[0] = {float(last.T[0])!r} К, "
             f"q_o = {float(wd.q_o_std)!r} м³ст/с")
        print(f"  {name}: {time.perf_counter() - t0:.1f} с", file=sys.stderr)

    if args.out is not None:
        args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
