"""Сборка HTML-документации пакета gpn_multiphase_solver (Sphinx).

Из каталога numerical_solver:

    .venv\\Scripts\\python -m sphinx -W -b html doc/source doc/build/html

Главный файл — doc/build/html/index.html. Состав: README.md пакета,
техническое описание (докстринги пакета и подпакетов), публичный интерфейс
(api.rst). Прототип и примеры не входят.
"""

import json
import re
import sys
from pathlib import Path

from sphinx.util import logging

ROOT = Path(__file__).resolve().parents[2]                  # numerical_solver/
# Документируется код этого дерева, а не установленный пакет: в worktree
# общий venv указывает на основной каталог (так же pythonpath pytest в pyproject.toml)
sys.path[:0] = [str(ROOT), str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")]

import gpn_multiphase_solver  # noqa: E402

project = "gpn-multiphase-solver"
version = release = gpn_multiphase_solver.__version__
language = "ru"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "myst_parser"]
html_theme = "alabaster"
html_title = f"gpn-multiphase-solver {release}"
autodoc_member_order = "bysource"

# ── Докстринги в стиле NumPy с русскими заголовками ──
# Синоним стандартного раздела — подписи полей переводит language = "ru"
# («Параметры», «Результат», «Исключение»). «Примечания» — простой строкой:
# синоним Notes вышел бы рубрикой «Заметки». Подразделы технического
# описания — тоже простыми строками (рубрики); необъявленный подраздел
# вышел бы заголовком страницы (проба FEAT-031). Объявлены ли все заголовки
# документируемых модулей — проверяет tests/test_docs.py
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_custom_sections = [
    ("Параметры", "Parameters"), ("Возвращает", "Returns"),
    ("Исключения", "Raises"), ("Атрибуты", "Attributes"),
    ("Примеры", "Examples"),
    "Примечания",
    "Назначение и границы модели", "Устройство пакета", "Поток данных расчёта",
    "Связь с прототипом", "Конвенция знаков", "Связь формула → код",
    "Шаг по времени и сходимость", "Тесты", "Расширение", "Соглашения кода",
    "Модули",
]

# ── README (MyST) ──
# Ссылки README на файлы и каталоги в HTML не разрешаются (README не
# правится ради документации — решение пользователя); их существование
# проверяет tests/test_docs.py::test_readme_links_exist
myst_enable_extensions = ["dollarmath"]
suppress_warnings = ["myst.xref_missing"]

# ── Метки постановки → номера (таблица — tools/eq_numbers.py) ──
_logger = logging.getLogger(__name__)
_NUMBERS = json.loads((Path(__file__).parent / "eq_numbers.json").read_text(encoding="utf-8"))
_REF = re.compile(r"\(?((?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+)\)?")


def _numbers(app, what, name, obj, options, lines):
    """Метка eq: → «(N)», раздела → «п. N»; метки нет в таблице — предупреждение."""
    def sub(m):
        label = m.group(1)
        n = _NUMBERS.get(label)
        if n is None:
            _logger.warning(f"{name}: метки {label} нет в eq_numbers.json")
            return m.group(0)
        return f"({n})" if label.startswith("eq:") else f"п. {n}"
    lines[:] = [_REF.sub(sub, s) for s in lines]


def setup(app):
    app.connect("autodoc-process-docstring", _numbers)
