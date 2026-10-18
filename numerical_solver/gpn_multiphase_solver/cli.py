"""Команда расчёта по конфигу: python -m gpn_multiphase_solver run config.json (FEAT-030).

Штатный набор — run_case (report/pipeline.py): CSV истории и профилей,
рисунки, печать проверок. Коды возврата: 0 — расчёт завершён; 1 — решатель
отказал на шаге по времени; 2 — ошибка аргументов или конфига (расчёт не
начат). Та же команда — gpn-solver run config.json ([project.scripts]).

Шаблон книги ввода Excel: gpn-solver template книга.xlsx (FEAT-033) — новый
файл с демонстрационными значениями; существующий файл не перезаписывается
(код 2).

Перевод книги в конфиг: gpn-solver convert книга.xlsx каталог (FEAT-035) —
config.json и CSV таблиц в СИ в новом или пустом каталоге; ошибки книги, файла
и каталога — код 2.

Расчёт по книге: gpn-solver run книга.xlsx (FEAT-036) — run_case переводит
книгу в output/input/ и считает по переводу; каталог вывода очищается до
расчёта. Ошибки книги — код 2, сообщение «Ошибка книги: …».

Номер версии: gpn-solver --version (FEAT-037) — номер решателя; решатель
и прототип не импортируются.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def configure_batch_run() -> None:
    """Консоль UTF-8 и matplotlib без окна (Agg) — для расчёта из командной строки. FEAT-030."""
    # Консоль Windows по умолчанию cp1251, а печать проверок содержит
    # символы вне неё (м³ст/с, λ, μ, ≠, →): print упал бы с
    # UnicodeEncodeError уже после расчёта. Файлы (CSV, PNG) пишутся своими
    # кодировками и этим не затрагиваются. Прежде это делал импорт
    # examples/example_runner — модуль пакета так поступать не должен.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    # Agg — без окон: в консоли и на сервере без графики интерактивный
    # режим падает. Переключение после импорта pyplot допустимо — режим
    # выбирается при первой фигуре (проба аудита FEAT-030).
    import matplotlib
    matplotlib.use("Agg")


def _profiles(text: str) -> int:
    """Аргумент --profiles: целое не меньше двух."""
    try:
        n = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"нужно целое число, получено {text!r}")
    if n < 2:
        raise argparse.ArgumentTypeError(f"нужно не меньше двух моментов, получено {n}")
    return n


def _parser(prog: str | None) -> argparse.ArgumentParser:
    """Разбор аргументов: подкоманды run, template, convert и их параметры."""
    p = argparse.ArgumentParser(
        prog=prog,
        description="Расчёт притока газированной нефти к скважине с температурой "
                    "(gpn_multiphase_solver).")
    # Номер решателя (FEAT-037). Строка — имя дистрибутива, а не %(prog)s:
    # prog зависит от способа запуска (gpn-solver.exe, python -m …), а
    # строка совпадает с первой строкой versions.txt. argparse печатает её в
    # stdout и выходит с кодом 0 до проверки обязательной подкоманды.
    # Прототип не импортируется — как и для --help.
    p.add_argument("--version", action="version",
                   version=f"gpn-multiphase-solver {__version__}")
    sub = p.add_subparsers(dest="command", required=True, metavar="команда")
    run = sub.add_parser(
        "run", help="расчёт по конфигу или книге Excel: CSV, рисунки, печать проверок",
        description="Расчёт по JSON-конфигу или книге ввода Excel (.xlsx): история "
                    "скважины и профили (CSV), штатные рисунки (PNG), печать "
                    "проверок. Книга переводится в config.json и CSV таблиц в "
                    "каталоге input внутри каталога вывода; по ним расчёт "
                    "повторяется без книги.",
        epilog="Коды возврата: 0 — расчёт завершён; 1 — решатель отказал; "
               "2 — ошибка аргументов, конфига или книги. Каталог вывода "
               "очищается целиком: при расчёте по конфигу — после расчёта, "
               "по книге — до него.")
    run.add_argument("config", type=Path, metavar="вход",
                     help="JSON-конфиг расчёта или книга ввода Excel (.xlsx)")
    run.add_argument("--output", type=Path, default=None,
                     help="каталог результатов (по умолчанию — output рядом с "
                          "конфигом или книгой); очищается целиком")
    run.add_argument("--title", default=None,
                     help="заголовок рисунков и печати (по умолчанию — "
                          "output.title конфига или имя его папки; у книги — "
                          "её имя без расширения)")
    run.add_argument("--profiles", type=_profiles, default=None, metavar="N",
                     help="число моментов на профильных графиках (по умолчанию "
                          "— output.n_profiles конфига)")
    tpl = sub.add_parser(
        "template", help="шаблон книги ввода Excel с демонстрационными значениями",
        description="Шаблон книги ввода Excel (.xlsx, формат версии 1) с "
                    "демонстрационными значениями. Существующий файл не "
                    "перезаписывается.",
        epilog="Коды возврата: 0 — шаблон записан; 2 — ошибка аргументов, файл "
               "уже существует или не записывается.")
    tpl.add_argument("workbook", type=Path, help="путь новой книги .xlsx")
    cnv = sub.add_parser(
        "convert", help="перевод книги ввода Excel в JSON-конфиг и CSV таблиц (СИ)",
        description="Перевод книги ввода Excel (.xlsx, формат версии 1) в config.json "
                    "и CSV таблиц PVT и ОФП в единицах СИ. Проверяется книга: листы, "
                    "заголовки, ключи, единицы, типы и пределы ячеек; конфиг и таблицы "
                    "целиком проверяет расчёт (gpn-solver run config.json).",
        epilog="Коды возврата: 0 — файлы записаны; 2 — ошибка аргументов, книги или "
               "каталога. Каталог — новый или пустой: файлы в непустом не меняются.")
    cnv.add_argument("workbook", type=Path, help="книга ввода .xlsx")
    cnv.add_argument("output", type=Path, help="каталог для config.json и CSV, новый или пустой")
    return p


def _template(path: Path) -> int:
    """Подкоманда template: шаблон книги в новый файл → код возврата (FEAT-033)."""
    # Импорт здесь: шаблону не нужны решатель, scipy и прототип (импорт
    # конвейера run — ниже, в main)
    from .io.workbook_template import write_template
    try:
        write_template(path)
    except FileExistsError:
        # Подкласс OSError — ловится первым: заполненная книга не затирается (решение 58)
        print(f"Ошибка: файл {path} уже существует — шаблон не записан, файл не "
              f"изменён. Удалите его или укажите другое имя.", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Ошибка: не удалось записать {path}: {exc.strerror or exc}", file=sys.stderr)
        return 2
    print(f"Шаблон книги записан: {path}")
    return 0


def _convert(workbook: Path, output: Path) -> int:
    """Подкоманда convert: книга → config.json и CSV таблиц в каталог → код возврата (FEAT-035)."""
    # Импорт здесь, как у template: переводу не нужны решатель, scipy и прототип
    from .io.workbook_convert import convert_workbook
    from .io.xlsx_reader import WorkbookError
    try:
        config = convert_workbook(workbook, output)
    except WorkbookError as exc:
        # Разбор (файл не книга .xlsx) и перевод (значения ячеек) — сообщение как есть
        print(f"Ошибка книги: {exc}", file=sys.stderr)
        return 2
    except FileExistsError as exc:
        # Подкласс OSError — ловится первым: непустой каталог не трогается (решение 10)
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print(f"Ошибка: книга {workbook} не найдена", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Ошибка: {exc.filename or workbook}: {exc.strerror or exc}", file=sys.stderr)
        return 2
    print(f"Конфиг записан: {config}")
    print(f"Таблицы {', '.join(sorted(p.name for p in config.parent.glob('*.csv')))} — там же. "
          f"Конфиг и таблицы целиком проверяются при расчёте: gpn-solver run {config}")
    return 0


def main(argv: list[str] | None = None, prog: str | None = None) -> int:
    """Точка входа команды: разбор аргументов → run_case → код возврата. FEAT-030."""
    configure_batch_run()
    args = _parser(prog).parse_args(argv)   # ошибка аргументов — SystemExit(2)
    if args.command == "template":
        return _template(args.workbook.resolve())
    if args.command == "convert":
        return _convert(args.workbook.resolve(), args.output.resolve())
    # Импорт конвейера — после configure_batch_run и разбора: --help не
    # тянет scipy, решатель и прототип (matplotlib и numpy импортирует
    # configure_batch_run — режим Agg)
    from .report.pipeline import EXCEL_SUFFIXES, CaseConfigError, CaseRunError, run_case
    # Абсолютные пути: печать «Конфиг: …» и «Книга: …» однозначна при любом каталоге
    # запуска (и совпадает с прежней печатью main.py примеров)
    config = args.config.resolve()
    output = args.output.resolve() if args.output is not None else None
    try:
        run_case(config, output, title=args.title, n_profiles=args.profiles)
    except CaseConfigError as exc:
        # Книга (FEAT-036): и ошибки ячеек, и отказ проверки конфига по её
        # переводу — ключ строки книги равен пути поля JSON (FEAT-035)
        what = "книги" if config.suffix.lower() in EXCEL_SUFFIXES else "конфига"
        print(f"Ошибка {what}: {exc}", file=sys.stderr)
        return 2
    except CaseRunError as exc:
        print(f"Расчёт не завершён: {exc}", file=sys.stderr)
        return 1
    # Прочие исключения (ошибка кода) — с трассировкой и кодом 1: она нужна
    # отделу разработки
    return 0
