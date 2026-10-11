"""Установка пакетов: зависимости, версия прототипа, код своего дерева в тестах (DEBT-059)."""

import ast
import importlib
import re
import sys
from pathlib import Path

import pytest

SOLVER = Path(__file__).resolve().parents[1]                 # numerical_solver/
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"  # дистрибутив radial-blackoil

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


class TestNoPrototypePathInsertion:
    def test_code_does_not_insert_prototype_path(self):
        """Ни пакет, ни примеры, ни тесты не вставляют путь к прототипу в sys.path (DEBT-059)."""
        # Вставка маскирует забытую установку: в репозитории работает, у
        # пользователя установленного пакета — ModuleNotFoundError
        found, hits = 0, []
        for base in ("gpn_multiphase_solver", "examples", "tests"):
            for path in sorted((SOLVER / base).rglob("*.py")):
                for text in _path_insertions(ast.parse(path.read_text(encoding="utf-8"))):
                    found += 1
                    # «proto» ловит и литерал HydroSolverPrototype, и имена _PROTO, PROTO_ROOT
                    if "proto" in text.lower():
                        hits.append(f"{path.relative_to(SOLVER)}: {text}")
        # На c0ec060 вставок 81, после шага 3 — 72 (5 циклов остаются вставками
        # без пути к прототипу, 9 прямых уходят); ноль значит: разбор сломан
        assert found > 10, "сторож не нашёл ни одной вставки в sys.path"
        assert hits == []
