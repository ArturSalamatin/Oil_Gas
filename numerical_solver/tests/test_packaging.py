"""Установка пакетов: зависимости, версии решателя (FEAT-037) и прототипа, код своего дерева в тестах (DEBT-059)."""

import ast
import importlib
import re
import sys
from pathlib import Path

import pytest
# packaging — зависимость pytest (packaging>=22), не пакета решателя
from packaging.version import Version

SOLVER = Path(__file__).resolve().parents[1]                 # numerical_solver/
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"  # дистрибутив radial-blackoil
SOLVER_INIT = SOLVER / "gpn_multiphase_solver" / "__init__.py"  # литерал __version__ решателя

# Модуль импорта → дистрибутив (имя по PEP 503). Новый сторонний импорт
# в пакете — добавить сюда и в dependencies его pyproject.toml.
DIST_OF_MODULE = {
    "numpy": "numpy",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
    "xlsxwriter": "xlsxwriter",
    "radial_blackoil": "radial-blackoil",
}


def _pyproject(path: Path) -> dict:
    """pyproject.toml как словарь; tomllib — с Python 3.11, на 3.10 тест пропускается."""
    tomllib = pytest.importorskip("tomllib")
    with open(path, "rb") as f:
        return tomllib.load(f)


def _req_name(req: str) -> str:
    """Имя дистрибутива из строки требования по PEP 503: строчные, разделители — «-»."""
    name = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", req).group(1)
    return re.sub(r"[-_.]+", "-", name).lower()


def _imported_top_modules(package_dir: Path) -> set:
    """Верхние имена абсолютных импортов во всех модулях пакета, включая импорты внутри функций."""
    names = set()
    for path in package_dir.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names.add(node.module.split(".")[0])
    return names


def _static_version(init_py: Path) -> str:
    """__version__ из литерала в __init__.py — так, как его читает setuptools (без импорта)."""
    for node in ast.parse(init_py.read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "__version__"):
            # Не литерал — setuptools стал бы импортировать пакет, а в
            # изолированной сборке numpy нет (DEBT-059, П4 плана)
            assert isinstance(node.value, ast.Constant), "__version__ — не литерал"
            return node.value.value
    raise AssertionError(f"нет __version__ в {init_py}")


class TestDistributions:
    """pyproject.toml обоих дистрибутивов согласованы с кодом."""

    def test_gpn_pins_prototype_version(self):
        """GPN требует ровно ту версию radial-blackoil, что в radial_blackoil.__version__."""
        # Сменили версию прототипа в одном месте и забыли во втором — pip
        # откажется ставить пару (или поставит не ту, если границу ослабить).
        version = _static_version(PROTO / "radial_blackoil" / "__init__.py")
        deps = _pyproject(SOLVER / "pyproject.toml")["project"]["dependencies"]
        pins = [d for d in deps if _req_name(d) == "radial-blackoil"]
        assert pins == [f"radial-blackoil=={version}"]

    def test_prototype_version_is_dynamic_from_literal(self):
        """Версия дистрибутива прототипа — из radial_blackoil.__version__: один источник номера."""
        proj = _pyproject(PROTO / "pyproject.toml")
        assert proj["project"]["dynamic"] == ["version"]
        assert proj["tool"]["setuptools"]["dynamic"]["version"] == {
            "attr": "radial_blackoil.__version__"}

    def test_solver_version_is_dynamic_from_literal(self):
        """Версия дистрибутива решателя — из gpn_multiphase_solver.__version__: один источник номера (FEAT-037)."""
        proj = _pyproject(SOLVER / "pyproject.toml")
        assert proj["project"]["dynamic"] == ["version"]
        # Статический номер рядом с dynamic — второй источник (setuptools
        # отвергает сборку), его возврат при правке pyproject.toml ловится здесь
        assert "version" not in proj["project"]
        assert proj["tool"]["setuptools"]["dynamic"]["version"] == {
            "attr": "gpn_multiphase_solver.__version__"}

    def test_solver_version_literal_follows_rule(self):
        """__version__ решателя — литерал, каноническая форма PEP 440, ровно три числа MAJOR.MINOR.PATCH."""
        # _static_version отвергает вычисляемое значение (не ast.Constant)
        text = _static_version(SOLVER_INIT)
        version = Version(text)            # InvalidVersion — не PEP 440
        assert str(version) == text, f"не каноническая форма PEP 440: {text!r} → {version}"
        # '1.0' по PEP 440 канонична (проба plan_checks.py) — число частей отдельно
        assert len(version.release) == 3, f"не MAJOR.MINOR.PATCH: {text!r}"

    def test_changelog_has_section_for_version(self):
        """Журнал согласован с номером: до выпуска — раздел «Не выпущено», выпуск — раздел своего номера (FEAT-037)."""
        # is_prerelease истинно для .devN, aN, bN, rcN. Ловит выпуск без
        # раздела журнала. Суффикс .dev, забытый после выпуска, не ловит:
        # номер ставит выпуск (FEAT-031), журнал за него не отвечает
        version = Version(_static_version(SOLVER_INIT))
        lines = (SOLVER / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
        if version.is_prerelease:
            assert "## Не выпущено" in lines, "номер до выпуска, а раздела «Не выпущено» нет"
        else:
            head = re.compile(rf"## {re.escape(str(version))}( |$)")
            assert any(head.match(s) for s in lines), f"нет раздела «## {version} — <дата>»"

    def test_prototype_installs_only_its_package(self):
        """В дистрибутив прототипа попадает только radial_blackoil (рядом tests/ — тоже пакет)."""
        # Без include в site-packages лёг бы пакет верхнего уровня tests
        proj = _pyproject(PROTO / "pyproject.toml")
        assert proj["tool"]["setuptools"]["packages"]["find"]["include"] == ["radial_blackoil*"]

    @pytest.mark.parametrize("package_dir, pyproject", [
        (SOLVER / "gpn_multiphase_solver", SOLVER / "pyproject.toml"),
        (PROTO / "radial_blackoil", PROTO / "pyproject.toml"),
    ], ids=["gpn-multiphase-solver", "radial-blackoil"])
    def test_declared_dependencies_cover_imports(self, package_dir, pyproject):
        """Каждый сторонний импорт пакета (и внутри функций) объявлен в его dependencies."""
        # Необъявленный импорт в репозитории незаметен (в общем venv всё
        # стоит), а в чистом окружении после установки — ModuleNotFoundError
        third_party = (_imported_top_modules(package_dir)
                       - set(sys.stdlib_module_names) - {package_dir.name})
        unknown = third_party - DIST_OF_MODULE.keys()
        assert not unknown, (f"новый сторонний импорт {sorted(unknown)}: "
                             "добавить в DIST_OF_MODULE и в dependencies")
        declared = {_req_name(d) for d in _pyproject(pyproject)["project"]["dependencies"]}
        missing = {DIST_OF_MODULE[m] for m in third_party} - declared
        assert not missing, f"не объявлены в {pyproject}: {sorted(missing)}"


class TestTestsUseThisTree:
    """pytest проверяет код своего дерева, а не установленный в общий venv."""

    @pytest.mark.parametrize("module, home", [
        ("gpn_multiphase_solver", SOLVER / "gpn_multiphase_solver"),
        ("radial_blackoil", PROTO / "radial_blackoil"),
    ])
    def test_package_imported_from_this_tree(self, module, home):
        """Пакет импортирован из того же дерева, что и тесты (в worktree — из worktree)."""
        # gpn_multiphase_solver — из каталога запуска (python -m pytest из
        # numerical_solver), radial_blackoil — по pythonpath в pyproject.toml.
        # Падение в worktree значит: тесты проверяют код основного каталога.
        mod = importlib.import_module(module)
        assert Path(mod.__file__).resolve().parent == home.resolve()


def _is_path_insert(call: ast.Call) -> bool:
    """Вызов sys.path.insert / sys.path.append или monkeypatch.syspath_prepend."""
    f = call.func
    if not isinstance(f, ast.Attribute):
        return False
    if f.attr == "syspath_prepend":
        return True
    return (f.attr in ("insert", "append") and isinstance(f.value, ast.Attribute)
            and f.value.attr == "path" and isinstance(f.value.value, ast.Name)
            and f.value.value.id == "sys")


def _path_insertions(tree: ast.AST) -> list:
    """Текст каждой вставки в sys.path; для вставки в цикле — вместе с тем, по чему идёт цикл."""
    # Вставка в цикле — sys.path.insert(0, _p): путь виден только в for ... in (...)
    loop_iter = {}
    for loop in ast.walk(tree):
        if isinstance(loop, ast.For):
            for node in ast.walk(loop):
                loop_iter[id(node)] = loop_iter.get(id(node), "") + " | " + ast.unparse(loop.iter)
    return [ast.unparse(n) + loop_iter.get(id(n), "")
            for n in ast.walk(tree) if isinstance(n, ast.Call) and _is_path_insert(n)]


# Пример 23 показывает работу из папки с исходным кодом без установки
# пакетов (FEAT-040): вставка пути к прототипу – суть примера, а не обход
# забытой установки. Исключение – ровно эти файлы;
# test_allowed_file_inserts_prototype_path проверяет, что каждый из них есть
# и вставку делает, – иначе исключение устарело бы молча
PROTO_PATH_ALLOWED = ("examples/23_source_tree_run/main.py",)


class TestNoPrototypePathInsertion:
    def test_code_does_not_insert_prototype_path(self):
        """Ни пакет, ни примеры, ни тесты не вставляют путь к прототипу в sys.path (DEBT-059); исключения – PROTO_PATH_ALLOWED (FEAT-040)."""
        # Вставка маскирует забытую установку: в репозитории работает, у
        # пользователя установленного пакета — ModuleNotFoundError
        found, hits = 0, []
        for base in ("gpn_multiphase_solver", "examples", "tests"):
            for path in sorted((SOLVER / base).rglob("*.py")):
                if path.relative_to(SOLVER).as_posix() in PROTO_PATH_ALLOWED:
                    continue
                for text in _path_insertions(ast.parse(path.read_text(encoding="utf-8"))):
                    found += 1
                    # «proto» ловит и литерал HydroSolverPrototype, и имена _PROTO, PROTO_ROOT
                    if "proto" in text.lower():
                        hits.append(f"{path.relative_to(SOLVER)}: {text}")
        # На c0ec060 вставок 81, после шага 3 — 72 (5 циклов остаются вставками
        # без пути к прототипу, 9 прямых уходят); ноль значит: разбор сломан
        assert found > 10, "сторож не нашёл ни одной вставки в sys.path"
        assert hits == []

    @pytest.mark.parametrize("rel", PROTO_PATH_ALLOWED)
    def test_allowed_file_inserts_prototype_path(self, rel):
        """Файл-исключение существует и вставляет путь к прототипу: исключение не устарело (FEAT-040)."""
        texts = _path_insertions(ast.parse((SOLVER / rel).read_text(encoding="utf-8")))
        assert any("proto" in t.lower() for t in texts), f"{rel}: вставки пути к прототипу нет"


# ── Форма пунктов журнала (DEBT-086) ──
# Пункт – номер задачи (у правки без задачи – область, «README») жирным и
# суть, затем абзацы-блоки с курсивными метками; форма – /implement, фаза 4.1.
# Проверяется только текущий раздел: прошлые выпуски написаны до DEBT-086 и
# не переписываются (решение пользователя 2026-10-22)
CHANGELOG_SUBSECTIONS = ("### Добавлено", "### Изменено", "### Исправлено", "### Удалено")
CHANGELOG_ITEM_RE = re.compile(r"- \*\*([^*]+)\.\*\* \S")     # «- **FEAT-040.** Суть»
CHANGELOG_TASK_ID_RE = re.compile(r"(BUG|DEBT|FEAT|VAL)-\d{3}")
CHANGELOG_LABEL_RE = re.compile(r"  \*([^*]+)\.\* \S")        # «  *Было.* Текст»
CHANGELOG_LABEL_SETS = (["Было", "Стало"], ["Было", "Стало", "Числа"])
CHANGELOG_EM_DASH = chr(0x2014)      # длинное тире U+2014: в тексте раздела запрещено (CLAUDE.md, «Тире»)
# Вывод программ (сообщения решателя, команды) цитируется дословно в `…`:
# в 177 строковых литералах пакета есть «—», поэтому тире и десятичная
# запятая внутри обратных кавычек не проверяются
CHANGELOG_CODE_SPAN_RE = re.compile(r"`[^`]*`")


def _current_changelog_section() -> list:
    """Строки текущего раздела журнала без заголовка: «Не выпущено» до выпуска, раздел своего номера – в метке."""
    # Выбор раздела – как в test_changelog_has_section_for_version: в дереве
    # метки (самопроверка tools/release.py) «Не выпущено» уже переименован
    version = Version(_static_version(SOLVER_INIT))
    lines = (SOLVER / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    head = (re.compile(r"## Не выпущено$") if version.is_prerelease
            else re.compile(rf"## {re.escape(str(version))}( |$)"))
    starts = [i for i, s in enumerate(lines) if head.match(s)]
    assert len(starts) == 1, f"разделов {head.pattern!r}: {len(starts)}, ожидался один"
    end = next((i for i in range(starts[0] + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[starts[0] + 1:end]


def _changelog_format_problems(lines: list) -> list:
    """Нарушения формы пунктов в строках раздела журнала без заголовка «## …»; пусто – форма верна."""
    problems, subsections, labels, prev = [], [], [], ""
    item = None                          # номер строки, с которой начался текущий пункт

    def close_item():
        if item is not None and labels not in CHANGELOG_LABEL_SETS:
            problems.append(f"строка {item}: блоки пункта {labels}, нужны «Было», «Стало» "
                            "и, если изменяются результаты, «Числа» – по порядку")

    for n, line in enumerate(lines, 1):
        plain = CHANGELOG_CODE_SPAN_RE.sub("", line)      # без цитат вывода программ
        if CHANGELOG_EM_DASH in plain:
            problems.append(f"строка {n}: длинное тире (U+2014), нужно «–»")
        if re.search(r"\d,\d", plain):
            problems.append(f"строка {n}: десятичная запятая, нужна точка")
        label = CHANGELOG_LABEL_RE.match(line)
        if line.startswith("#"):
            close_item()
            item = None
            if line not in CHANGELOG_SUBSECTIONS:
                problems.append(f"строка {n}: подраздел {line!r} не из {CHANGELOG_SUBSECTIONS}")
            subsections.append(line)
        elif line.startswith("- "):
            close_item()
            item, labels = n, []
            m = CHANGELOG_ITEM_RE.match(line)
            if m is None:
                problems.append(f"строка {n}: пункт не начинается с «- **<номер задачи или область>.** »")
            elif re.search(r"\d", m[1]) and not CHANGELOG_TASK_ID_RE.fullmatch(m[1]):
                # Цифра в выделении – номер задачи: опечатка «FEAT-40» не должна сойти за область
                problems.append(f"строка {n}: номер {m[1]!r} не вида FEAT-040")
            if prev:
                problems.append(f"строка {n}: перед пунктом нет пустой строки")
            if not subsections:
                problems.append(f"строка {n}: пункт вне подраздела")
        elif (item is not None and prev and label is not None
              and label[1] in CHANGELOG_LABEL_SETS[1]):
            # Метка сразу под текстом: на GitHub блок слился бы с предыдущим абзацем
            problems.append(f"строка {n}: перед меткой *{label[1]}.* нет пустой строки")
        elif (item is not None and not prev and line.startswith("  ")
              and not line.startswith(("  - ", "    "))):
            # Первая строка абзаца внутри пункта – метка блока
            if label is None or label[1] not in CHANGELOG_LABEL_SETS[1]:
                problems.append(f"строка {n}: абзац пункта не начинается с *Было.*, *Стало.* или *Числа.*")
            else:
                labels.append(label[1])
        elif line and not line.startswith(" ") and subsections:
            problems.append(f"строка {n}: текст вне пункта внутри подраздела")
        prev = line
    close_item()
    order = [CHANGELOG_SUBSECTIONS.index(s) for s in subsections if s in CHANGELOG_SUBSECTIONS]
    if order != sorted(set(order)):
        problems.append(f"подразделы {subsections}: порядок – {CHANGELOG_SUBSECTIONS}, каждый один раз")
    return problems


# Минимальный верный пункт – основа образцов нарушений
_GOOD = ["### Добавлено", "", "- **FEAT-001.** Суть.", "", "  *Было.* А.", "", "  *Стало.* Б."]
_ITEM2 = ["- **FEAT-002.** Суть.", "", "  *Было.* А.", "", "  *Стало.* Б."]
_BAD = {   # нарушение → подстрока сообщения
    "без жирного номера": (["### Добавлено", "", "- FEAT-001. Суть.", "", "  *Было.* А.", "", "  *Стало.* Б."],
                           "пункт не начинается"),
    "номер не вида": (["### Добавлено", "", "- **FEAT-1.** Суть.", "", "  *Было.* А.", "", "  *Стало.* Б."],
                      "не вида FEAT-040"),
    "нет Стало": (_GOOD[:5], "блоки пункта"),
    "блоки не по порядку": (_GOOD[:4] + ["  *Стало.* Б.", "", "  *Было.* А."], "блоки пункта"),
    "чужая метка": (_GOOD + ["", "  *Итог.* В."], "абзац пункта не начинается"),
    "абзац без метки": (_GOOD + ["", "  Просто текст."], "абзац пункта не начинается"),
    "метка жирным": (_GOOD[:4] + ["  **Было.** А."] + _GOOD[5:], "абзац пункта не начинается"),
    "нет пустой строки между пунктами": (_GOOD + _ITEM2, "нет пустой строки"),
    "длинное тире": (_GOOD[:4] + [f"  *Было.* А {CHANGELOG_EM_DASH} Б."] + _GOOD[5:], "длинное тире"),
    "десятичная запятая": (_GOOD[:4] + ["  *Было.* 10,67 м."] + _GOOD[5:], "десятичная запятая"),
    "чужой подраздел": (["### Прочее"] + _GOOD[1:], "не из"),
    "подразделы не по порядку": (["### Изменено"] + _GOOD[1:] + ["", "### Добавлено", ""] + _ITEM2, "порядок"),
    "пункт вне подраздела": (_GOOD[2:], "вне подраздела"),
    "текст вне пункта": (_GOOD + ["", "Текст."], "текст вне пункта"),
    "метка без пустой строки": (_GOOD[:3] + ["  *Было.* А.", "", "  *Стало.* Б."],
                                "нет пустой строки"),
}


class TestChangelogFormat:
    """Форма пунктов текущего раздела журнала (DEBT-086): её читает получатель выпуска на GitHub."""

    def test_changelog_current_section_format(self):
        """Пункты текущего раздела – по форме /implement 4.1; в дереве метки – раздел выпуска."""
        # Тот же тест идёт в самопроверке tools/release.py (шаг 3): пункт не
        # по форме останавливает выпуск до публикации, с откатом
        assert _changelog_format_problems(_current_changelog_section()) == []

    def test_changelog_format_accepts_sample(self):
        """Образец со всеми допустимыми элементами нарушений не содержит."""
        # Вступление до подразделов (как у 1.0.5), перенесённая первая строка,
        # пункт без задачи (область README), блок «Числа» с вложенным списком
        # и перенесённой строкой вложенного пункта, два подраздела по порядку,
        # дословная цитата вывода в `…` с длинным тире и запятой между цифрами
        lines = [
            "Код решателя не менялся: числа те же, что в 1.0.4.", "",
            "### Добавлено", "",
            "- **FEAT-039.** Пуск скважины считается", "  сменой режима.", "",
            "  *Было.* Пуск шёл полным шагом.", "",
            "  *Стало.* Первый шаг после пуска", "  начинается с подшага h0.", "",
            "  *Числа.* Изменяются первые записи.",
            "  - пример 22, через 1 мин: дебит 10.67 → 8.21 м³ст/сут,",
            "    p(r_w) 151.79 → 151.38 бар",
            "  - пример 17: T(r_w) +0.050 К на 1 сут", "",
            "- **README.** Раздел «Начало работы»: третий случай.", "",
            "  *Было.* Случая без установки не было.", "",
            "  *Стало.* Описан запуск через `PYTHONPATH`.", "",
            "### Исправлено", "",
            "- **BUG-030.** Суть.", "",
            "  *Было.* А.", "",
            f"  *Стало.* Сообщение `каталог вывода {CHANGELOG_EM_DASH} файл`, интервал `[0,1]`.",
        ]
        assert _changelog_format_problems(lines) == []

    @pytest.mark.parametrize("case", list(_BAD))
    def test_changelog_format_catches(self, case):
        """Каждое нарушение формы найдено, сообщение называет правило."""
        # Без этих образцов проверка текущего раздела проходила бы и сломанной:
        # после выпуска «Не выпущено» пуст
        lines, expected = _BAD[case]
        problems = _changelog_format_problems(lines)
        assert any(expected in p for p in problems), problems
