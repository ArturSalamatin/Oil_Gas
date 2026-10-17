"""Команда расчёта по конфигу: python -m gpn_multiphase_solver run config.json (FEAT-030).

Штатный набор — run_case (report/pipeline.py): CSV истории и профилей,
рисунки, печать проверок. Коды возврата: 0 — расчёт завершён; 1 — решатель
отказал на шаге по времени; 2 — ошибка аргументов или конфига (расчёт не
начат). Та же команда — gpn-solver run config.json ([project.scripts]).

Шаблон книги ввода Excel: gpn-solver template книга.xlsx (FEAT-033) — новый
файл с демонстрационными значениями; существующий файл не перезаписывается
(код 2).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


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
    """Разбор аргументов: подкоманда run и её параметры."""
    p = argparse.ArgumentParser(
        prog=prog,
        description="Расчёт притока газированной нефти к скважине с температурой "
                    "(gpn_multiphase_solver).")
    sub = p.add_subparsers(dest="command", required=True, metavar="команда")
    run = sub.add_parser(
        "run", help="расчёт по конфигу: CSV, рисунки, печать проверок",
        description="Расчёт по JSON-конфигу: история скважины и профили (CSV), "
                    "штатные рисунки (PNG), печать проверок.",
        epilog="Коды возврата: 0 — расчёт завершён; 1 — решатель отказал; "
               "2 — ошибка аргументов или конфига. Каталог вывода после "
               "расчёта очищается целиком.")
    run.add_argument("config", type=Path, help="JSON-конфиг расчёта")
    run.add_argument("--output", type=Path, default=None,
                     help="каталог результатов (по умолчанию — output рядом с "
                          "конфигом); очищается целиком")
    run.add_argument("--title", default=None,
                     help="заголовок рисунков и печати (по умолчанию — "
                          "output.title конфига или имя его папки)")
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


def main(argv: list[str] | None = None, prog: str | None = None) -> int:
    """Точка входа команды: разбор аргументов → run_case → код возврата. FEAT-030."""
    configure_batch_run()
    args = _parser(prog).parse_args(argv)   # ошибка аргументов — SystemExit(2)
    if args.command == "template":
        return _template(args.workbook.resolve())
    # Импорт конвейера — после configure_batch_run и разбора: --help не
    # тянет scipy, решатель и прототип (matplotlib и numpy импортирует
    # configure_batch_run — режим Agg)
    from .report.pipeline import CaseConfigError, CaseRunError, run_case
    # Абсолютные пути: печать «Конфиг: …» однозначна при любом каталоге
    # запуска (и совпадает с прежней печатью main.py примеров)
    config = args.config.resolve()
    output = args.output.resolve() if args.output is not None else None
    try:
        run_case(config, output, title=args.title, n_profiles=args.profiles)
    except CaseConfigError as exc:
        print(f"Ошибка конфига: {exc}", file=sys.stderr)
        return 2
    except CaseRunError as exc:
        print(f"Расчёт не завершён: {exc}", file=sys.stderr)
        return 1
    # Прочие исключения (ошибка кода) — с трассировкой и кодом 1: она нужна
    # отделу разработки
    return 0
