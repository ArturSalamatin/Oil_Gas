"""Имена, которые скрипты examples/ берут из других модулей, на месте (DEBT-046).

Скрипты examples/ — main.py примеров, скрипты сходимости и проверок,
общие модули — запускаются вручную, и тесты их целиком не исполняют:
фикстура results (test_examples.py) считает примеры через SimulatorFactory,
минуя main.py. Имя, удалённое или переименованное в общем модуле examples/,
в пакете решателя или в прототипе, ломало бы скрипт молча — до следующего
ручного запуска, возможно через недели и другим человеком.

Проверка статическая: текст скрипта разбирается модулем ast, сам скрипт
не исполняется — ни расчётов, ни записи файлов, ни блока __main__.
Импортируются только модули, из которых скрипт берёт имена. Ловится:
  (а) from M import name на верхнем уровне;
  (б) from M import name внутри функции или в блоке __main__ — импорт
      файла (runpy, как в DEBT-031) такие строки не исполняет;
  (в) alias.name при import M as alias: tpa.report;
  (г) имя, нужное функции, но не связанное в модуле: потерянная строка
      импорта самого файла (deepcopy в run_series, DEBT-031);
  (д) именованные аргументы вызовов run_example(...) против её сигнатуры.
Приватные атрибуты объектов ловит test_no_private_solver_access (DEBT-011);
типы аргументов не ловятся.
"""

import ast
import builtins
import dis
import functools
import importlib
import importlib.util
import inspect
import types
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# Все .py в examples/ и в папках примеров: main.py, скрипты ручного запуска,
# общие модули. Список строится по диску, как SHARED_EXAMPLE_FILES в
# test_examples.py (DEBT-037): новый файл попадает под проверку сам.
EXAMPLE_SCRIPTS = sorted(p.relative_to(EXAMPLES_DIR).as_posix()
                         for p in EXAMPLES_DIR.rglob("*.py"))

# Пакеты, имена из которых проверяются наравне с общими модулями examples/:
# решатель и прототип гидродинамики (его код правится в проекте). Остальное —
# numpy, scipy, matplotlib, стандартная библиотека — стороннее, имена из него
# не проверяются.
CHECKED_PACKAGES = ("gpn_multiphase_solver", "radial_blackoil")

# Имена, которые Python сам кладёт в пространство имён модуля.
MODULE_DUNDERS = {"__file__", "__name__", "__doc__", "__spec__", "__loader__",
                  "__package__", "__builtins__", "__annotations__", "__cached__"}

# Узлы со своей областью имён: связанное внутри них не видно на уровне модуля.
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
           ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


@pytest.fixture(autouse=True)
def _examples_on_path(monkeypatch):
    """examples/ в sys.path на время теста — общие модули импортируются по имени, как в скриптах."""
    monkeypatch.syspath_prepend(str(EXAMPLES_DIR))


@functools.lru_cache(maxsize=None)
def _load_own(path: Path) -> types.ModuleType:
    """Модуль из папки примера, загруженный по пути файла (один раз на сессию)."""
    # Папку примера в sys.path не кладём: в ней main.py, он перекрыл бы
    # одноимённые модули для всех следующих тестов. Имя модуля уникально
    # по папке, чтобы модули разных примеров не смешались в sys.modules.
    spec = importlib.util.spec_from_file_location(
        f"_script_check_{path.parent.name}_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_for(modname: str, script_dir: Path):
    """Модуль, из которого скрипт берёт имена; None — сторонний, не проверяется."""
    top = modname.split(".")[0]
    if top in CHECKED_PACKAGES or (EXAMPLES_DIR / f"{top}.py").is_file():
        return importlib.import_module(modname)
    # Модуль из папки примера: Python кладёт папку запускаемого скрипта в
    # sys.path, поэтому main.py импортирует соседние модули по имени.
    own = script_dir / f"{top}.py"
    if script_dir != EXAMPLES_DIR and own.is_file():
        return _load_own(own)
    # Модуля нет ни в examples/, ни в папке скрипта, ни среди установленных:
    # удалён или переименован общий модуль.
    if importlib.util.find_spec(top) is None:
        raise ModuleNotFoundError(f"модуль {top} не найден")
    return None


def _module_level_names(tree: ast.Module) -> set:
    """Имена, связанные на уровне модуля: импорты, def/class, присваивания, global, блок __main__."""
    names = set(MODULE_DUNDERS)

    def visit(node, at_module):
        for child in ast.iter_child_nodes(node):
            # global x внутри функции связывает x на уровне модуля.
            if isinstance(child, ast.Global):
                names.update(child.names)
            if at_module:
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    for a in child.names:
                        names.add(a.asname or a.name.split(".")[0])
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                        ast.ClassDef)):
                    names.add(child.name)
                elif (isinstance(child, ast.Name)
                      and isinstance(child.ctx, ast.Store)):
                    names.add(child.id)
                elif isinstance(child, ast.ExceptHandler) and child.name:
                    names.add(child.name)
            visit(child, at_module and not isinstance(child, _SCOPES))
    visit(tree, True)
    return names


def _nested_code(code: types.CodeType):
    """Code-объекты функций, методов, лямбд и генераторов внутри code, рекурсивно."""
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield const
            yield from _nested_code(const)


def _script_problems(path: Path) -> list:
    """Пропавшие имена скрипта: импорты, alias.name, глобальные имена функций, run_example."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems = []
    aliases = {}   # alias → модуль: для проверки alias.name, класс (в)

    def module_or_problem(modname, lineno):
        try:
            return _module_for(modname, path.parent)
        except ImportError as exc:
            problems.append(f"строка {lineno}: нет модуля {modname} ({exc})")
            return None

    # ── (а), (б): импорты на любом уровне вложенности ──
    # ast.walk обходит всё дерево: верхний уровень, тела функций, блок
    # __main__ — независимо от того, что исполнилось бы при импорте файла.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            module = module_or_problem(node.module, node.lineno)
            if module is None:
                continue
            for a in node.names:
                if a.name == "*" or hasattr(module, a.name):
                    continue
                # from пакет import подмодуль: подмодуль может быть ещё не
                # загружен, тогда атрибута у пакета нет.
                try:
                    importlib.import_module(f"{node.module}.{a.name}")
                except ImportError:
                    problems.append(f"строка {node.lineno}: в {node.module} "
                                    f"нет имени {a.name}")
        elif isinstance(node, ast.Import):
            for a in node.names:
                module = module_or_problem(a.name, node.lineno)
                # import пакет.модуль без as связывает имя пакета, не модуля —
                # такие алиасы не проверяем.
                if module is not None and (a.asname or "." not in a.name):
                    aliases[a.asname or a.name] = module

    # ── (в): alias.name — tpa.report ──
    # Ни импорт файла, ни LOAD_GLOBAL этого не видят: LOAD_GLOBAL даёт tpa,
    # а .report берётся у модуля только при вызове.
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases
                and not hasattr(aliases[node.value.id], node.attr)):
            problems.append(f"строка {node.lineno}: в модуле {node.value.id} "
                            f"нет имени {node.attr}")

    # ── (г): глобальные имена функций против имён уровня модуля ──
    # Функция берёт имя модуля инструкцией LOAD_GLOBAL при вызове; если
    # строку импорта удалили, ошибка появится только при вызове функции.
    # Код уровня модуля (LOAD_NAME) пропускаем: его имена — из (а), (б).
    bound = _module_level_names(tree)
    for code in _nested_code(compile(tree, str(path), "exec")):
        for ins in dis.get_instructions(code):
            if (ins.opname == "LOAD_GLOBAL" and ins.argval not in bound
                    and not hasattr(builtins, ins.argval)):
                problems.append(f"{code.co_name} (строка {code.co_firstlineno}): "
                                f"имя {ins.argval} не связано в модуле")

    # ── (д): именованные аргументы run_example(...) ──
    # main.py 17 из 22 примеров — только вызов run_example; переименованный
    # параметр (title → figure_title) ломал бы их TypeError при запуске.
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "run_example"]
    runner = importlib.import_module("example_runner") if calls else None
    if runner is not None and hasattr(runner, "run_example"):
        signature = inspect.signature(runner.run_example)
        for call in calls:
            try:
                signature.bind(*call.args, **{k.arg: k.value
                                              for k in call.keywords if k.arg})
            except TypeError as exc:
                problems.append(f"строка {call.lineno}: run_example(...) — {exc}")

    # Одно пропавшее имя встречается в функции несколько раз — без повторов.
    return list(dict.fromkeys(problems))


@pytest.mark.parametrize("script", EXAMPLE_SCRIPTS)
def test_script_names_resolve(script):
    """Всё, что скрипт берёт из общих модулей, решателя и прототипа, существует."""
    problems = _script_problems(EXAMPLES_DIR / script)
    assert not problems, f"examples/{script}:\n  " + "\n  ".join(problems)


# Поломка каждого класса на синтетическом скрипте. Без этих тестов зелёный
# test_script_names_resolve не отличить от проверки, которая ничего не видит.
# Во всех случаях пропавшее имя содержит «no_such» — проверяем, что замечено
# именно оно, а не что-то постороннее. Ключи — латиницей: pytest экранирует
# не-ASCII в именах тестов (а…), имя упавшего случая было бы нечитаемо.
# Первая буква — класс из docstring: a, b, v, g, d = (а), (б), (в), (г), (д).
BROKEN_SNIPPETS = {
    "a_top_level_import": "from figure_io import no_such_name\n",
    "b_import_in_function": (
        "def f():\n"
        "    from gpn_multiphase_solver.factory import no_such_factory\n"),
    "b_import_in_main_block": (
        'if __name__ == "__main__":\n'
        "    from closed_form import no_such_name\n"),
    "v_module_alias": (
        "import two_phase_analytics as tpa\n\n"
        "def f():\n"
        "    return tpa.no_such_name\n"),
    "v_own_folder_module_alias": (
        "import own_helper\n\n"
        "def f():\n"
        "    return own_helper.no_such_name\n"),
    "g_name_without_import": (
        "def f(config):\n"
        "    return no_such_function(config)\n"),
    "d_run_example_keyword": (
        "from example_runner import run_example\n"
        "run_example(config_path=1, output_dir=2, title=3, no_such_arg=4)\n"),
    "removed_module": "import no_such_module\n",
}


@pytest.mark.parametrize("case", sorted(BROKEN_SNIPPETS))
def test_checker_sees_broken_names(tmp_path, case):
    """Проверка замечает пропавшее имя каждого класса."""
    # Папка примера с соседним модулем own_helper.py — как main.py,
    # импортирующий модуль из своей папки.
    folder = tmp_path / "99_synthetic"
    folder.mkdir()
    (folder / "own_helper.py").write_text("PRESENT = 1\n", encoding="utf-8")
    script = folder / "main.py"
    script.write_text(BROKEN_SNIPPETS[case], encoding="utf-8")

    problems = _script_problems(script)
    assert any("no_such" in p for p in problems), (
        f"{case}: пропавшее имя не замечено, найдено: {problems}")


# ── Приватный доступ (DEBT-011) ──────────────────────────────

# self и cls — доступ объекта к собственным полям: подменённый метод
# решателя в verify_balance_vs_solver.py работает внутри его класса.
_OWN = {"self", "cls"}


def _private_access(tree: ast.AST) -> list[str]:
    """Обращения .имя к приватным полям чужих объектов и from <пакет> import _имя."""
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and node.attr.startswith("_")
                and not node.attr.startswith("__")
                and not (isinstance(node.value, ast.Name)
                         and node.value.id in _OWN)):
            found.append(f"строка {node.lineno}: .{node.attr}")
        elif (isinstance(node, ast.ImportFrom) and node.module
              and node.module.split(".")[0] in CHECKED_PACKAGES):
            found += [f"строка {node.lineno}: from {node.module} import {a.name}"
                      for a in node.names if a.name.startswith("_")]
    return found


@pytest.mark.parametrize("script", EXAMPLE_SCRIPTS)
def test_no_private_solver_access(script):
    """Скрипт examples/ берёт объекты задачи через публичный интерфейс пакета (DEBT-011).

    Примеры передаются заказчику как образец работы с библиотекой:
    sim._energy._pvt в примере стал бы интерфейсом, который нельзя
    менять. Ловится .имя у чужого объекта (sim._grid, tpa._build_relperm)
    и from gpn_multiphase_solver... import _имя. Импорт приватных имён
    между модулями examples/ (_resolve_example) — их внутреннее дело
    до FEAT-030 и не ловится.
    """
    tree = ast.parse((EXAMPLES_DIR / script).read_text(encoding="utf-8"))
    found = _private_access(tree)
    assert not found, f"{script}: приватный доступ — {found}"
