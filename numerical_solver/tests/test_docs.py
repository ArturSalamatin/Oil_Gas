"""HTML-документация пакета: таблица номеров уравнений, перечень публичного интерфейса, правило докстрингов (FEAT-031).

Документация собирается Sphinx из README.md и докстрингов (doc/source/).
Метки постановки в докстрингах при сборке заменяются номерами уравнений по
таблице doc/source/eq_numbers.json — её строит tools/eq_numbers.py из
doc/problem_statement.aux. Здесь проверяется, что таблица не отстала от
постановки.
"""

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]                  # numerical_solver/
TEX = ROOT / "doc" / "problem_statement.tex"
AUX = ROOT / "doc" / "problem_statement.aux"
TABLE = ROOT / "doc" / "source" / "eq_numbers.json"
# Объявление метки в .tex — тот же шаблон, что в tests/test_eq_references.py
LABEL_DEF = re.compile(r"\\label\{((?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+)\}")


def _load_tool(name: str):
    """Модуль скрипта из tools/ (каталог — не пакет, импортировать по пути)."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Таблица «метка → номер» ──────────────────────────────────

def test_eq_numbers_cover_tex_labels():
    """Метки таблицы — ровно метки постановки.

    Работает и без .aux: ловит метку, добавленную в problem_statement.tex или
    удалённую из него без пересборки таблицы (tools/eq_numbers.py). На
    FEAT-031 — 161 метка (130 уравнений).
    """
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    labels = set(LABEL_DEF.findall(TEX.read_text(encoding="utf-8")))
    assert len(labels) > 100          # разбор .tex не сломан
    assert set(table) == labels, (
        f"нет в таблице: {sorted(labels - set(table))}; "
        f"лишние в таблице: {sorted(set(table) - labels)} — tools\\eq_numbers.py")


def test_eq_numbers_match_aux():
    """Номера таблицы равны номерам свежего .aux (после pdflatex).

    .aux в git не хранится: без него сверять нечем. .aux старше .tex —
    PDF собран до последней правки постановки; это не ошибка таблицы.
    """
    if not AUX.is_file():
        pytest.skip("нет problem_statement.aux — таблицу сверить нечем")
    if AUX.stat().st_mtime < TEX.stat().st_mtime:
        pytest.skip("problem_statement.aux старше problem_statement.tex — пересоберите PDF")
    eq_numbers = _load_tool("eq_numbers")
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    assert table == eq_numbers.read_aux(AUX), "таблица устарела — tools\\eq_numbers.py"
