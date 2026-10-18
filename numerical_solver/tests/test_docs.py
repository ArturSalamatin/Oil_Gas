"""HTML-документация пакета: таблица номеров уравнений, перечень публичного интерфейса, правило докстрингов (FEAT-031).

Документация собирается Sphinx из README.md и докстрингов (doc/source/).
Метки постановки в докстрингах при сборке заменяются номерами уравнений по
таблице doc/source/eq_numbers.json — её строит tools/eq_numbers.py из
doc/problem_statement.aux. Перечень публичного интерфейса — директивы
doc/source/api.rst и package.rst. Здесь проверяется, что таблица не отстала
от постановки, а перечень — от кода, README и примеров.
"""

import ast
import importlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]                  # numerical_solver/
TEX = ROOT / "doc" / "problem_statement.tex"
AUX = ROOT / "doc" / "problem_statement.aux"
DOC_SOURCE = ROOT / "doc" / "source"
TABLE = DOC_SOURCE / "eq_numbers.json"
PACKAGE = "gpn_multiphase_solver"
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


# ── Перечень публичного интерфейса ───────────────────────────

# Директива autodoc и строка :members: под ней (без списка — все открытые
# члены, объявленные в самом классе)
DIRECTIVE = re.compile(r"^\.\. auto(function|class|exception|module):: (\S+)\s*$")
MEMBERS = re.compile(r"^\s+:members:(.*)$")


def resolve(name: str):
    """Объект по полному имени: самый длинный импортируемый модуль, дальше — атрибуты."""
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:i]))
        except ImportError:
            continue
        for attr in parts[i:]:
            obj = getattr(obj, attr)
        return obj
    raise ImportError(name)


def api_entries() -> list[tuple[str, str, list[str] | None]]:
    """(полное имя, вид директивы, члены из :members: или None) по api.rst и package.rst."""
    entries = []
    for page in ("api.rst", "package.rst"):
        lines = (DOC_SOURCE / page).read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = DIRECTIVE.match(line)
            if not m:
                continue
            members = None
            mm = MEMBERS.match(lines[i + 1]) if i + 1 < len(lines) else None
            if mm:
                listed = [s.strip() for s in mm.group(1).split(",") if s.strip()]
                if not listed:   # :members: без списка — открытые члены самого класса
                    cls = resolve(m.group(2))
                    listed = [k for k in vars(cls) if not k.startswith("_")]
                members = listed
            entries.append((m.group(2), m.group(1), members))
    return entries


def documented_names() -> set[str]:
    """Полные имена всех документируемых объектов, включая члены классов."""
    names = set()
    for name, _, members in api_entries():
        names.add(name)
        names.update(f"{name}.{m}" for m in members or [])
    return names


# Обязательные имена: README §4 («Использование из Python») и
# tests/test_public_api.py. Подпакеты diagnostics и report README §4
# называет целиком — их описание в package.rst
REQUIRED = {f"{PACKAGE}.{n}" for n in (
    "report.pipeline.run_case", "report.pipeline.CaseConfigError",
    "report.pipeline.CaseRunError", "cli.configure_batch_run",
    "io.config.load_config", "factory.SimulatorFactory",
    "factory.SimulatorFactory.from_config", "factory.create_pvt", "factory.create_relperm",
    "simulator.Simulator", "simulator.Simulator.run", "simulator.Simulator.grid",
    "simulator.Simulator.pvt", "simulator.Simulator.relperm",
    "state.SimulationHistory", "state.SimulationState", "state.WellData",
    "grid.log_radial.LogRadialGrid",
    "io.output.save_csv", "io.output.save_well_csv", "io.output.save_npz",
    "io.output.plot_profiles", "io.output.plot_well_rate",
    "io.output.plot_wellbore_dynamics", "io.output.plot_pvt_properties",
    "io.output.plot_relperm_curves", "io.output.plot_energy_balance_series",
    "io.output.pvt_table_nodes", "io.figures.save_figure", "io.figures.export_emf",
    "energy.balance.compute_energy_balance", "mass_balance.compute_mass_balance",
    "pvt.prototype_adapter.PrototypeRPAdapter", "pvt.relperm.CoreyRP",
    "diagnostics", "report",
)}
# Скрипты примеров, которые нарочно работают с внутренностями пакета (белый
# ящик): verify_balance_vs_solver.py подменяет TridiagEnergySolver.solve
WHITE_BOX = {"verify_balance_vs_solver.py"}


def test_api_objects_importable():
    """Каждый объект перечня импортируется; каждый член из :members: существует."""
    missing = []
    for name, _, members in api_entries():
        try:
            obj = resolve(name)
        except (ImportError, AttributeError) as exc:
            missing.append(f"{name}: {exc!r}")
            continue
        missing += [f"{name}.{m}" for m in members or [] if not hasattr(obj, m)]
    assert not missing, missing


def test_api_covers_required_names():
    """В перечне — имена README §4, test_public_api.py и всё, что импортируют примеры.

    Пример — образец работы с пакетом: всё, что он вызывает, описано.
    Константы (ИМЕНА_ЗАГЛАВНЫМИ) описывает докстринг их модуля.
    """
    documented = documented_names()
    lost = sorted(REQUIRED - documented)
    for path in sorted((ROOT / "examples").rglob("*.py")):
        if path.name in WHITE_BOX:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(PACKAGE):
                lost += [f"{path.relative_to(ROOT)}: {node.module}.{a.name}" for a in node.names
                         if not a.name.isupper() and f"{node.module}.{a.name}" not in documented]
    assert not lost, ("не описано в doc/source/api.rst (или package.rst):\n" + "\n".join(lost))


def test_readme_links_exist():
    """Каждая относительная ссылка README.md ведёт на существующий файл или каталог.

    В HTML эти ссылки не разрешаются (README не правится ради документации,
    предупреждения myst.xref_missing подавлены в conf.py) — проверка здесь.
    """
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)\s]+)\)", text)
    local = [s for s in links if not re.match(r"(https?:|mailto:|#)", s)]
    assert len(local) > 10            # разбор не сломан: на FEAT-031 — 20 ссылок
    broken = [s for s in local if not (ROOT / s.split("#")[0]).exists()]
    assert not broken, broken
