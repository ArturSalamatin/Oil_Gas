"""HTML-документация пакета: таблица номеров уравнений, перечень публичного интерфейса, правило докстрингов (FEAT-031).

Документация собирается Sphinx из README.md и докстрингов (doc/source/).
Метки постановки в докстрингах при сборке заменяются номерами уравнений по
таблице doc/source/eq_numbers.json — её строит tools/eq_numbers.py из
doc/problem_statement.aux. Перечень публичного интерфейса — директивы
doc/source/api.rst и package.rst. Здесь проверяется, что таблица не отстала
от постановки, а перечень — от кода, README и примеров.
"""

import ast
import dataclasses
import importlib
import importlib.util
import inspect
import json
import re
import textwrap
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


# ── Правило докстрингов публичного интерфейса ────────────────
#
# CLAUDE.md, «Файлы и код»: докстринг публичного интерфейса — в стиле NumPy с
# русскими заголовками разделов (napoleon_custom_sections в conf.py). Для
# каждого объекта перечня:
#   D1 — докстринг непуст, первая строка кончается точкой;
#   D2 — функция с параметрами: раздел «Параметры», имена записей = сигнатура;
#   D3 — функция возвращает значение (return с выражением или аннотация
#        результата не None): раздел «Возвращает»;
#   D4 — свойство: без раздела «Параметры»;
#   D5 — dataclass: раздел «Атрибуты», имена = поля; класс с собственным
#        __init__ с параметрами: «Параметры» в докстринге класса;
#   D6 — без ID задач (BUG/DEBT/FEAT/VAL-NNN) и путей vault/ — перечни задач
#        заказчику не передаются (решение пользователя FEAT-031);
#   D7 — модуль: заголовки разделов объявлены в conf.py.
# Докстринг — собственный (__doc__), не inspect.getdoc: тот подставил бы
# докстринг базового класса, и объект без своего прошёл бы проверку.

TASK_ID = re.compile(r"\b(?:BUG|DEBT|FEAT|VAL)-\d{3}\b")
UNDERLINE = re.compile(r"^\s*-{3,}\s*$")
# Запись раздела: строка без отступа «имя», «имя : тип», «a, b : тип», «*args»
ENTRY = re.compile(r"^(\*{0,2}\w+(?:\s*,\s*\*{0,2}\w+)*)\s*(?::.*)?$")

# Объекты, чьи докстринги ещё не переписаны (шаги 5–9 плана FEAT-031):
# строгий xfail — переписанный объект проходит (XPASS) и обязан уйти из
# списка. После шага 9 список пуст и удаляется. Начальный список — по факту
# прогона (91 из 120 объектов), а не руками
PENDING = frozenset(f"{PACKAGE}.{n}" for n in (
    # шаг 7 — PVT и ОФП
    "pvt.base.HydroPVT.Rs_eq", "pvt.base.HydroPVT.Bo", "pvt.base.HydroPVT.Bg",
    "pvt.base.HydroPVT.mu_o", "pvt.base.HydroPVT.mu_g", "pvt.base.HydroPVT.pb",
    "pvt.base.HydroPVT.rho_o", "pvt.base.HydroPVT.rho_g",
    "pvt.base.FullPVT.c_p_oil", "pvt.base.FullPVT.c_p_gas", "pvt.base.FullPVT.mu_JT_oil",
    "pvt.base.FullPVT.mu_JT_gas", "pvt.base.FullPVT.L_degas",
    "pvt.base.DifferentiableHydroPVT.dRs_eq_dp", "pvt.base.DifferentiableHydroPVT.dBo_dp",
    "pvt.base.DifferentiableHydroPVT.dBo_dRs", "pvt.base.DifferentiableHydroPVT.dBg_dp",
    "pvt.base.DifferentiableHydroPVT.dmu_o_dp", "pvt.base.DifferentiableHydroPVT.dmu_g_dp",
    "pvt.base.RelPermModel.kro", "pvt.base.RelPermModel.krg",
    "pvt.base.DifferentiableRelPerm.dkro_dSg", "pvt.base.DifferentiableRelPerm.dkrg_dSg",
    "pvt.standing.StandingFullPVT", "pvt.table_full.TableFullPVT", "pvt.relperm.CoreyRP",
    "pvt.prototype_adapter.PrototypeRPAdapter",
    # шаг 8 — результаты, рисунки, балансы, проверки
    "io.output.save_csv", "io.output.save_well_csv", "io.output.save_npz",
    "io.output.plot_profiles", "io.output.plot_well_rate", "io.output.plot_wellbore_dynamics",
    "io.output.plot_pvt_properties", "io.output.plot_relperm_curves",
    "io.output.plot_energy_balance_series", "io.output.pvt_table_nodes",
    "io.figures.save_figure", "io.figures.export_emf",
    "energy.balance.compute_energy_balance", "mass_balance.compute_mass_balance",
    "diagnostics.closed_form.solve_closed", "diagnostics.rs.front_radius",
    "diagnostics.temperature.single_phase_asymptote", "diagnostics.two_phase.compute_gor",
    "diagnostics.two_phase.compute_free_gas_prediction",
    "diagnostics.two_phase.predict_saturation", "diagnostics.two_phase.dupuit_check",
    "diagnostics.two_phase.degassing_front", "report.relperm.report_relperm",
    # шаг 9 — докстринги подпакетов
    "pvt", "energy", "hydro", "grid", "io", "diagnostics", "report",
))


def api_objects() -> dict[str, tuple[str, object, type | None, str | None]]:
    """Полное имя → (вид, объект, класс-владелец, имя члена) по перечню, с членами классов."""
    out = {}
    for name, kind, members in api_entries():
        obj = resolve(name)
        out[name] = ("module" if kind == "module" else
                     "class" if kind in ("class", "exception") else "function", obj, None, None)
        for m in members or []:
            raw = inspect.getattr_static(obj, m)
            out[f"{name}.{m}"] = ("property" if isinstance(raw, property) else "function",
                                  raw, obj, m)
    return out


API = api_objects()


def _own_doc(kind: str, obj) -> str:
    """Собственный докстринг объекта без отступов."""
    if kind == "property":
        obj = obj.fget
    elif isinstance(obj, (staticmethod, classmethod)):
        obj = obj.__func__
    doc = vars(obj).get("__doc__") if isinstance(obj, type) else obj.__doc__
    return inspect.cleandoc(doc or "")


def sections(doc: str) -> dict[str, list[str]]:
    """Разделы NumPy: заголовок — строка, под ней строка из «---»; тело — до следующего заголовка."""
    lines = doc.splitlines()
    out, current = {}, None
    i = 0
    while i < len(lines):
        if (i + 1 < len(lines) and lines[i].strip() and not lines[i].startswith(" ")
                and UNDERLINE.match(lines[i + 1])):
            current = lines[i].strip()
            out[current] = []
            i += 2
            continue
        if current is not None:
            out[current].append(lines[i])
        i += 1
    return out


def entry_names(body: list[str]) -> set[str]:
    """Имена записей раздела: строки без отступа; «a, b : тип» — два имени."""
    names = set()
    for line in body:
        if line and not line[0].isspace():
            m = ENTRY.match(line.strip())
            if m:
                names.update(s.strip() for s in m.group(1).split(","))
    return names


def _function(obj):
    """Функция за staticmethod/classmethod."""
    return obj.__func__ if isinstance(obj, (staticmethod, classmethod)) else obj


def _param_names(func) -> set[str]:
    """Параметры сигнатуры без self/cls; *args и **kwargs — со звёздочками."""
    names = set()
    for p in inspect.signature(func).parameters.values():
        if p.name in ("self", "cls"):
            continue
        prefix = {p.VAR_POSITIONAL: "*", p.VAR_KEYWORD: "**"}.get(p.kind, "")
        names.add(prefix + p.name)
    return names


def _returns_value(func) -> bool:
    """return с выражением в теле (без вложенных функций) или аннотация результата не None."""
    ann = inspect.signature(func).return_annotation
    if ann not in (inspect.Signature.empty, None, "None"):
        return True
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    stack = list(ast.iter_child_nodes(tree.body[0]))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(node, ast.Return) and node.value is not None:
            return True
        stack.extend(ast.iter_child_nodes(node))
    return False


def _declared_sections() -> set[str]:
    """Заголовки napoleon_custom_sections из conf.py — разбором, без импорта Sphinx."""
    tree = ast.parse((DOC_SOURCE / "conf.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "napoleon_custom_sections":
            return {e if isinstance(e, str) else e[0] for e in ast.literal_eval(node.value)}
    raise AssertionError("нет napoleon_custom_sections в conf.py")


def _check_params(where: str, doc_sections: dict, names: set[str]) -> list[str]:
    """«Параметры» есть, если есть параметры; имена записей совпадают с сигнатурой."""
    if not names:
        return []
    if "Параметры" not in doc_sections:
        return [f"{where}: нет раздела «Параметры» ({sorted(names)})"]
    got = entry_names(doc_sections["Параметры"])
    return [] if got == names else [
        f"{where}: «Параметры» {sorted(got)} ≠ сигнатура {sorted(names)}"]


def docstring_problems(name: str) -> list[str]:
    """Нарушения правил D1–D7 у объекта перечня."""
    kind, obj, owner, _ = API[name]
    doc = _own_doc(kind, obj)
    if not doc:
        return ["D1: докстринга нет"]
    problems = []
    if not doc.splitlines()[0].rstrip().endswith("."):
        problems.append("D1: первая строка не кончается точкой")
    if TASK_ID.search(doc) or "vault/" in doc:
        problems.append("D6: ID задачи или путь vault/ в докстринге")
    secs = sections(doc)
    if kind == "property":
        if "Параметры" in secs:
            problems.append("D4: у свойства раздел «Параметры»")
    elif kind == "function":
        func = _function(obj)
        problems += _check_params("D2", secs, _param_names(func))
        if _returns_value(func) and "Возвращает" not in secs:
            problems.append("D3: нет раздела «Возвращает»")
    elif kind == "class":
        if dataclasses.is_dataclass(obj):
            fields = {f.name for f in dataclasses.fields(obj)}
            got = entry_names(secs.get("Атрибуты", []))
            if got != fields:
                problems.append(f"D5: «Атрибуты» {sorted(got)} ≠ поля {sorted(fields)}")
        elif "__init__" in vars(obj):
            problems += _check_params("D5", secs, _param_names(obj.__init__))
    elif kind == "module":
        undeclared = set(secs) - _declared_sections()
        if undeclared:
            problems.append(f"D7: заголовки не объявлены в conf.py: {sorted(undeclared)}")
    return problems


@pytest.mark.parametrize("name", [
    pytest.param(n, marks=pytest.mark.xfail(
        strict=True, reason="докстринг ещё не переписан (FEAT-031)")) if n in PENDING else n
    for n in API])
def test_public_docstring(name):
    """Докстринг объекта публичного интерфейса — по правилу NumPy с русскими заголовками (D1–D7)."""
    problems = docstring_problems(name)
    assert not problems, problems


def test_pending_names_exist():
    """Каждое имя PENDING — объект перечня: опечатка не должна прятать объект от проверки."""
    assert PENDING <= set(API), sorted(PENDING - set(API))
