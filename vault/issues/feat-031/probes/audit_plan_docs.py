"""Аудит плана FEAT-031: сборка документации ровно по шагу 3 плана + покрытие api.rst импортами примеров.

1. Пишет doc/source/ в КОПИЮ среза (conf.py, index.md, readme.md, package.rst,
   api.rst — как в плане; eq_numbers.json — из doc/problem_statement.aux копии),
   собирает HTML без -W и с -W; печатает предупреждения по группам.
2. Мини-сборка с conf.py плана: dataclass с разделом «Атрибуты» под autoclass
   без :members: — нет ли дублей описаний; autoexception.
3. Разбор AST examples/**/*.py: имена from gpn_multiphase_solver… import …,
   кроме констант и скриптов белого ящика, — все ли есть в api.rst плана.

Запуск — из корня репозитория, интерпретатором пробного окружения (Sphinx):

    dist\\probe-feat031\\venv\\Scripts\\python vault\\issues\\feat-031\\probes\\audit_plan_docs.py dist\\probe-feat031\\slice
"""

import ast
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

SLICE = Path(sys.argv[1]).resolve()
SRC = SLICE / "doc" / "source"
P = "gpn_multiphase_solver"

# ── conf.py — дословно шаг 3 плана ──
CONF = r'''"""Сборка HTML-документации пакета gpn_multiphase_solver (Sphinx)."""
import json
import re
import sys
from pathlib import Path

from sphinx.util import logging

ROOT = Path(__file__).resolve().parents[2]                  # numerical_solver/
sys.path[:0] = [str(ROOT), str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")]

import gpn_multiphase_solver  # noqa: E402

project = "gpn-multiphase-solver"
version = release = gpn_multiphase_solver.__version__
language = "ru"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "myst_parser"]
html_theme = "alabaster"
html_title = f"gpn-multiphase-solver {release}"
autodoc_member_order = "bysource"

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

myst_enable_extensions = ["dollarmath"]
suppress_warnings = ["myst.xref_missing"]

_logger = logging.getLogger(__name__)
_NUMBERS = json.loads((Path(__file__).parent / "eq_numbers.json").read_text(encoding="utf-8"))
_REF = re.compile(r"\(?((?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+)\)?")


def _numbers(app, what, name, obj, options, lines):
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
'''

INDEX = """# gpn-multiphase-solver

Документация пакета `gpn_multiphase_solver`: сведения для пользователя
(README), техническое описание и публичный интерфейс.

```{toctree}
:maxdepth: 2

readme
package
api
```
"""

PACKAGE = ["Техническое описание", "====================", "",
           f".. automodule:: {P}", "", "Подпакеты", "---------", ""]
PACKAGE += [f".. automodule:: {P}.{m}\n" for m in
            ("pvt", "energy", "hydro", "grid", "io", "diagnostics", "report")]

# ── api.rst — разделы шага 3 плана ──
API = {
    "Расчёт": [("function", "report.pipeline.run_case"), ("class", "report.pipeline.CaseResult"),
               ("exception", "report.pipeline.CaseConfigError"),
               ("exception", "report.pipeline.CaseRunError"),
               ("function", "cli.configure_batch_run"), ("function", "cli.main")],
    "Конфигурация и книга ввода": [("function", "io.config.load_config")]
        + [("class", f"io.config.{c}") for c in (
            "SimulationConfig", "GeometryConfig", "GridConfig", "RockConfig", "PVTConfig",
            "RelPermConfig", "ThermalConfig", "InitialConfig", "HistoryInterval", "TimeConfig",
            "NumericsConfig", "OutputConfig")]
        + [("function", "io.workbook_template.write_template"),
           ("function", "io.workbook_convert.convert_workbook")],
    "Сборка решателя": [("class", "factory.SimulatorFactory", "from_config"),
                        ("function", "factory.create_pvt"), ("function", "factory.create_relperm")],
    "Решатель и история расчёта": [("class", "simulator.Simulator", "run, grid, pvt, relperm"),
                                   ("class", "state.SimulationState"), ("class", "state.WellData"),
                                   ("class", "state.SimulationHistory")],
    "Режим работы скважины и граничные условия": [
        ("class", "bc.WellControl"), ("class", "bc.PressureControl", "p_wf"),
        ("class", "bc.RateControl", "q_oil, min_bhp"), ("class", "state.BoundaryConditions")],
    "Сетка": [("class", "grid.base.Grid", ""), ("class", "grid.log_radial.LogRadialGrid")],
    "PVT и ОФП": [("class", f"pvt.base.{c}", "") for c in (
        "HydroPVT", "FullPVT", "DifferentiableHydroPVT", "RelPermModel", "DifferentiableRelPerm")]
        + [("class", "pvt.standing.StandingFullPVT"), ("class", "pvt.table_full.TableFullPVT"),
           ("class", "pvt.relperm.CoreyRP"), ("class", "pvt.prototype_adapter.PrototypeRPAdapter")],
    "Запись результатов и рисунки": [("function", f"io.output.{f}") for f in (
        "save_csv", "save_well_csv", "save_npz", "plot_profiles", "plot_well_rate",
        "plot_wellbore_dynamics", "plot_pvt_properties", "plot_relperm_curves",
        "plot_energy_balance_series", "pvt_table_nodes")]
        + [("function", "io.figures.save_figure"), ("function", "io.figures.export_emf")],
    "Балансы": [("function", "energy.balance.compute_energy_balance"),
                ("function", "mass_balance.compute_mass_balance")],
    "Проверки": [("function", "diagnostics.closed_form.solve_closed"),
                 ("function", "diagnostics.rs.front_radius"),
                 ("function", "diagnostics.temperature.single_phase_asymptote")]
        + [("function", f"diagnostics.two_phase.{f}") for f in (
            "compute_gor", "compute_free_gas_prediction", "predict_saturation",
            "dupuit_check", "degassing_front")]
        + [("function", "report.relperm.report_relperm")],
    "Единицы": [("module", "units")],
}


def api_rst() -> str:
    out = ["Публичный интерфейс", "===================", ""]
    for title, items in API.items():
        out += [title, "-" * len(title), ""]
        for it in items:
            kind, name = it[0], f"{P}.{it[1]}"
            out.append(f".. auto{kind}:: {name}")
            if len(it) == 3:
                out.append("   :members:" + (f" {it[2]}" if it[2] else ""))
            out.append("")
    return "\n".join(out)


def write_sources() -> None:
    if SRC.exists():
        shutil.rmtree(SRC)
    SRC.mkdir(parents=True)
    (SRC / "conf.py").write_text(CONF, encoding="utf-8")
    (SRC / "index.md").write_text(INDEX, encoding="utf-8")
    (SRC / "readme.md").write_text("```{include} ../../README.md\n```\n", encoding="utf-8")
    (SRC / "package.rst").write_text("\n".join(PACKAGE), encoding="utf-8")
    (SRC / "api.rst").write_text(api_rst(), encoding="utf-8")
    aux = (SLICE / "doc" / "problem_statement.aux").read_text(encoding="utf-8")
    table = dict(re.findall(r"\\newlabel\{((?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+)\}\{\{([^}]*)\}", aux))
    (SRC / "eq_numbers.json").write_text(json.dumps(dict(sorted(table.items())), ensure_ascii=False,
                                                    indent=1) + "\n", encoding="utf-8")


def sphinx(src: Path, out: Path, strict: bool) -> tuple[int, list[str]]:
    if out.exists():
        shutil.rmtree(out)
    warn = out.parent / f"{out.name}.warnings.txt"
    cmd = [sys.executable, "-m", "sphinx", "-b", "html", "-q", "-d", str(out.parent / f"{out.name}.doctrees"),
           "-w", str(warn)] + (["-W"] if strict else []) + [str(src), str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
    lines = [s for s in warn.read_text(encoding="utf-8", errors="replace").splitlines()
             if "WARNING" in s or "ERROR" in s or "CRITICAL" in s] if warn.exists() else []
    return r.returncode, lines


def report(lines: list[str]) -> None:
    kinds = Counter((re.search(r"\[([a-z_.]+)\]\s*$", s) or re.match("", "")).group(1) or "-" for s in lines)
    print(f"  предупреждений: {len(lines)}; по типам: {dict(kinds)}")
    where = Counter(re.sub(r"^.*docstring of ([\w.]+).*$", r"\1", s) if "docstring of" in s
                    else Path(s.split(":")[0] + ":" + s.split(":")[1]).name if ":" in s else s for s in lines)
    for w, n in where.most_common(15):
        print(f"      {n:3d}  {w}")
    for s in lines[:6]:
        print(f"      | {s[:230]}")


def mini_dataclass_build() -> None:
    """dataclass с «Атрибуты» под autoclass без :members:, autoexception — с conf.py плана."""
    src = SLICE / "doc" / "source_dc"
    if src.exists():
        shutil.rmtree(src)
    src.mkdir(parents=True)
    conf = CONF.replace("import gpn_multiphase_solver  # noqa: E402",
                        "import gpn_multiphase_solver  # noqa: E402\nsys.path.insert(0, str(Path(__file__).parent))")
    (src / "conf.py").write_text(conf, encoding="utf-8")
    shutil.copy(SRC / "eq_numbers.json", src / "eq_numbers.json")
    (src / "probe_dc.py").write_text('''from dataclasses import dataclass


@dataclass
class GeometryConfig:
    """Геометрия скважины и пласта — раздел ``geometry`` файла конфигурации.

    Атрибуты
    --------
    r_well : float
        Радиус скважины r_w, м.
    R_ext : float
        Радиус контура питания r_e, м.
    h : float
        Толщина пласта, м.
    """
    r_well: float    # радиус скважины, м
    R_ext: float     # радиус контура питания, м
    h: float         # мощность пласта, м


@dataclass
class OtherConfig:
    """Второй раздел с полем того же имени.

    Атрибуты
    --------
    h : float
        Ещё одна толщина, м.
    """
    h: float


class CaseConfigError(ValueError):
    """Конфиг не читается; расчёт не начат."""
''', encoding="utf-8")
    (src / "index.rst").write_text("Проба\n=====\n\n.. autoclass:: probe_dc.GeometryConfig\n\n"
                                   ".. autoclass:: probe_dc.OtherConfig\n\n"
                                   ".. autoexception:: probe_dc.CaseConfigError\n", encoding="utf-8")
    code, lines = sphinx(src, SLICE / "doc" / "build" / "audit_dc", strict=False)
    html = (SLICE / "doc" / "build" / "audit_dc" / "index.html").read_text(encoding="utf-8")
    print(f"  код {code}; предупреждений {len(lines)}")
    for s in lines:
        print(f"      | {s[:230]}")
    print(f"  r_well в HTML: {'r_well' in html}; «Радиус скважины» в HTML: {'Радиус скважины' in html}")


def examples_coverage() -> None:
    documented = {f"{P}.{it[1]}" for items in API.values() for it in items}
    white_box = {"verify_balance_vs_solver.py"}
    missing = []
    for f in sorted((SLICE / "examples").rglob("*.py")):
        if f.name in white_box:
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(P):
                for a in node.names:
                    if a.name.isupper() or a.name == "*":
                        continue
                    full = f"{node.module}.{a.name}"
                    if full not in documented and node.module not in documented:
                        missing.append(f"{f.relative_to(SLICE)}: {full}")
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith(P) and a.name not in documented:
                        missing.append(f"{f.relative_to(SLICE)}: import {a.name}")
    print(f"  объектов в api.rst: {len(documented)}; не покрыто импортов примеров: {len(missing)}")
    for m in missing:
        print(f"      {m}")


def main() -> None:
    import sphinx as sp
    print(f"Срез: {SLICE}; sphinx {sp.__version__}")
    write_sources()
    print("\n=== 1. Сборка по шагу 3 плана, без -W")
    code, lines = sphinx(SRC, SLICE / "doc" / "build" / "audit_plan", strict=False)
    print(f"  код {code}")
    report(lines)
    html = (SLICE / "doc" / "build" / "audit_plan" / "api.html").read_text(encoding="utf-8")
    print(f"  меток eq: в api.html: {len(re.findall(r'\beq:[A-Za-z]', html))}")
    print("\n=== 1б. С -W")
    code, lines = sphinx(SRC, SLICE / "doc" / "build" / "audit_plan_W", strict=True)
    print(f"  код {code}; первое: {lines[0][:230] if lines else '-'}")
    print("\n=== 2. dataclass «Атрибуты», autoexception")
    mini_dataclass_build()
    print("\n=== 3. Импорты примеров против api.rst")
    examples_coverage()


if __name__ == "__main__":
    main()
