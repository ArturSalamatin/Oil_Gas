"""Проба Sphinx для плана FEAT-031 (2026-10-18).

Что проверяется:
  1. napoleon в стиле NumPy с русскими заголовками разделов через
     napoleon_custom_sections («Параметры» → Parameters и т. д.): распознаётся
     ли раздел и какой подписью он выходит в HTML при language = "ru" и "en";
  2. включение README.md пакета директивой MyST {include}: какие
     предупреждения дают ссылки README на файлы и каталоги, формулы $…$;
  3. autodoc нынешнего публичного интерфейса (README §4, test_public_api.py,
     функции, которые вызывают main.py примеров, абстрактные классы
     расширения): сколько предупреждений даёт сборка из нынешних докстрингов;
  4. замена меток eq:/ssec: в докстрингах номерами из problem_statement.aux
     обработчиком autodoc-process-docstring.

Запуск — из корня репозитория, интерпретатором пробного окружения, в
котором установлены sphinx, myst-parser и оба пакета из среза:

    dist\\probe-feat031\\venv\\Scripts\\python vault\\issues\\feat-031\\probes\\sphinx_probe.py ^
        dist\\probe-feat031\\slice numerical_solver\\doc\\problem_statement.aux

Пишет doc/source/ в КОПИЮ среза (не в рабочее дерево), собирает HTML без -W
в doc/build/<язык>/, печатает подписи полей, рубрики и предупреждения по
группам. Вывод — sphinx_probe.out.txt рядом (перенаправлением).
"""

import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

SLICE = Path(sys.argv[1]).resolve()
AUX = Path(sys.argv[2]).resolve()
SRC = SLICE / "doc" / "source"

# ── Таблица «метка → номер» из .aux (hyperref: \newlabel{x}{{N}{стр}{}{якорь}{}}) ──
NEWLABEL = re.compile(r"\\newlabel\{((?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+)\}\{\{([^}]*)\}")
numbers = dict(NEWLABEL.findall(AUX.read_text(encoding="utf-8")))

# ── Публичный интерфейс для пробы autodoc ──
FUNCTIONS = [
    "gpn_multiphase_solver.report.pipeline.run_case",
    "gpn_multiphase_solver.cli.configure_batch_run",
    "gpn_multiphase_solver.cli.main",
    "gpn_multiphase_solver.io.config.load_config",
    "gpn_multiphase_solver.factory.create_pvt",
    "gpn_multiphase_solver.factory.create_relperm",
    "gpn_multiphase_solver.io.output.save_csv",
    "gpn_multiphase_solver.io.output.save_well_csv",
    "gpn_multiphase_solver.io.output.save_npz",
    "gpn_multiphase_solver.io.output.plot_profiles",
    "gpn_multiphase_solver.io.output.plot_well_rate",
    "gpn_multiphase_solver.io.output.plot_wellbore_dynamics",
    "gpn_multiphase_solver.io.output.plot_pvt_properties",
    "gpn_multiphase_solver.io.output.plot_relperm_curves",
    "gpn_multiphase_solver.io.output.plot_energy_balance_series",
    "gpn_multiphase_solver.io.output.pvt_table_nodes",
    "gpn_multiphase_solver.io.figures.save_figure",
    "gpn_multiphase_solver.io.figures.export_emf",
    "gpn_multiphase_solver.energy.balance.compute_energy_balance",
    "gpn_multiphase_solver.mass_balance.compute_mass_balance",
    "gpn_multiphase_solver.io.workbook_template.write_template",
    "gpn_multiphase_solver.io.workbook_convert.convert_workbook",
    "gpn_multiphase_solver.diagnostics.closed_form.solve_closed",
    "gpn_multiphase_solver.diagnostics.rs.front_radius",
    "gpn_multiphase_solver.diagnostics.temperature.single_phase_asymptote",
    "gpn_multiphase_solver.diagnostics.two_phase.compute_gor",
    "gpn_multiphase_solver.diagnostics.two_phase.compute_free_gas_prediction",
    "gpn_multiphase_solver.diagnostics.two_phase.predict_saturation",
    "gpn_multiphase_solver.diagnostics.two_phase.dupuit_check",
    "gpn_multiphase_solver.diagnostics.two_phase.degassing_front",
    "gpn_multiphase_solver.report.relperm.report_relperm",
]
CLASSES = {   # класс → явный список членов (None — :members: целиком)
    "gpn_multiphase_solver.report.pipeline.CaseResult": "",
    "gpn_multiphase_solver.report.pipeline.CaseConfigError": "",
    "gpn_multiphase_solver.report.pipeline.CaseRunError": "",
    "gpn_multiphase_solver.factory.SimulatorFactory": "from_config",
    "gpn_multiphase_solver.simulator.Simulator": "run, grid, pvt, relperm",
    "gpn_multiphase_solver.state.SimulationState": "",
    "gpn_multiphase_solver.state.WellData": "",
    "gpn_multiphase_solver.state.SimulationHistory": "",
    "gpn_multiphase_solver.state.BoundaryConditions": "",
    "gpn_multiphase_solver.io.config.SimulationConfig": "",
    "gpn_multiphase_solver.io.config.GeometryConfig": "",
    "gpn_multiphase_solver.io.config.GridConfig": "",
    "gpn_multiphase_solver.io.config.RockConfig": "",
    "gpn_multiphase_solver.io.config.PVTConfig": "",
    "gpn_multiphase_solver.io.config.RelPermConfig": "",
    "gpn_multiphase_solver.io.config.ThermalConfig": "",
    "gpn_multiphase_solver.io.config.InitialConfig": "",
    "gpn_multiphase_solver.io.config.HistoryInterval": "",
    "gpn_multiphase_solver.io.config.TimeConfig": "",
    "gpn_multiphase_solver.io.config.NumericsConfig": "",
    "gpn_multiphase_solver.io.config.OutputConfig": "",
    "gpn_multiphase_solver.pvt.base.HydroPVT": None,
    "gpn_multiphase_solver.pvt.base.FullPVT": None,
    "gpn_multiphase_solver.pvt.base.DifferentiableHydroPVT": None,
    "gpn_multiphase_solver.pvt.base.RelPermModel": None,
    "gpn_multiphase_solver.pvt.base.DifferentiableRelPerm": None,
    "gpn_multiphase_solver.pvt.standing.StandingFullPVT": "",
    "gpn_multiphase_solver.pvt.table_full.TableFullPVT": "",
    "gpn_multiphase_solver.pvt.relperm.CoreyRP": "",
    "gpn_multiphase_solver.pvt.prototype_adapter.PrototypeRPAdapter": "",
    "gpn_multiphase_solver.bc.WellControl": "",
    "gpn_multiphase_solver.bc.PressureControl": "p_wf",
    "gpn_multiphase_solver.bc.RateControl": "q_oil, min_bhp",
    "gpn_multiphase_solver.grid.base.Grid": None,
    "gpn_multiphase_solver.grid.log_radial.LogRadialGrid": "",
}
MODULES = ["gpn_multiphase_solver", "gpn_multiphase_solver.diagnostics",
           "gpn_multiphase_solver.report", "gpn_multiphase_solver.units"]

PROBE_MODULE = '''
class C:
    """Класс с атрибутами.

    Атрибуты
    --------
    p_wf : float
        Забойное давление, Па.
    """


def f(p, T, *, strict=False):
    """Плотность нефти при пластовых условиях. Ур. (eq:energy_disc_full) problem_statement.tex.

    Параметры
    ---------
    p : numpy.ndarray
        Давление, Па.
    T : numpy.ndarray
        Температура, К.
    strict : bool, optional
        Проверять пределы таблицы. По умолчанию ``False``.

    Возвращает
    ----------
    numpy.ndarray
        Плотность, кг/м³.

    Исключения
    ----------
    ValueError
        Если давление не положительно.

    Примечания
    ----------
    Схема по времени — параграф ssec:time_scheme; член — eq:Cp.

    Примеры
    -------
    >>> f(1.0e7, 350.0)
    """
'''

CONF = '''
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))   # probe_ru.py

project = "gpn-multiphase-solver"
language = "{lang}"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "myst_parser"]
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_custom_sections = [
    ("Параметры", "Parameters"), ("Возвращает", "Returns"),
    ("Исключения", "Raises"), ("Атрибуты", "Attributes"),
    ("Примечания", "Notes"), ("Примеры", "Examples"),
]
myst_enable_extensions = ["dollarmath"]
autodoc_member_order = "bysource"
html_theme = "alabaster"

NUM = json.loads((Path(__file__).parent / "eq_numbers.json").read_text(encoding="utf-8"))
_REF = re.compile(r"\\(?((?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+)\\)?")

def _sub(m):
    n = NUM.get(m.group(1))
    if n is None:
        return m.group(0)
    return f"({{n}})" if m.group(1).startswith("eq:") else f"п. {{n}}"

def _numbers(app, what, name, obj, options, lines):
    lines[:] = [_REF.sub(_sub, s) for s in lines]

def setup(app):
    app.connect("autodoc-process-docstring", _numbers)
'''


def write_sources(lang: str) -> None:
    """doc/source/ копии среза: conf.py, страницы, пробный модуль, таблица номеров."""
    if SRC.exists():
        shutil.rmtree(SRC)
    SRC.mkdir(parents=True)
    (SRC / "conf.py").write_text(CONF.format(lang=lang), encoding="utf-8")
    (SRC / "probe_ru.py").write_text(PROBE_MODULE, encoding="utf-8")
    (SRC / "eq_numbers.json").write_text(json.dumps(numbers, ensure_ascii=False, indent=0),
                                         encoding="utf-8")
    (SRC / "index.md").write_text(
        "# Проба\n\n```{toctree}\nreadme\nru_sections\napi\n```\n", encoding="utf-8")
    (SRC / "readme.md").write_text("```{include} ../../README.md\n```\n", encoding="utf-8")
    (SRC / "ru_sections.rst").write_text(
        "Русские разделы\n===============\n\n.. autofunction:: probe_ru.f\n\n"
        ".. autoclass:: probe_ru.C\n", encoding="utf-8")
    api = ["Публичный интерфейс", "===================", ""]
    api += [f".. automodule:: {m}\n" for m in MODULES]
    api += [f".. autofunction:: {f}\n" for f in FUNCTIONS]
    for c, members in CLASSES.items():
        api.append(f".. autoclass:: {c}")
        if members is None:
            api.append("   :members:")
        elif members:
            api.append(f"   :members: {members}")
        api.append("")
    (SRC / "api.rst").write_text("\n".join(api), encoding="utf-8")


def build(lang: str) -> tuple[Path, list[str]]:
    """HTML без -W; путь к сборке и строки предупреждений."""
    out = SLICE / "doc" / "build" / lang
    if out.exists():
        shutil.rmtree(out)
    warn = SLICE / "doc" / "build" / f"warnings_{lang}.txt"
    r = subprocess.run([sys.executable, "-m", "sphinx", "-b", "html", "-E", "-q",
                        "-w", str(warn), str(SRC), str(out)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"  sphinx-build: код {r.returncode}")
    lines = [s for s in warn.read_text(encoding="utf-8", errors="replace").splitlines()
             if "WARNING" in s or "ERROR" in s]
    return out, lines


def report_html(out: Path) -> None:
    """Подписи полей и рубрики на странице пробного модуля; номера вместо меток."""
    html = (out / "ru_sections.html").read_text(encoding="utf-8")
    fields = re.findall(r'<dt class="field-(?:odd|even)">([^<]+)', html)
    rubrics = re.findall(r'<p class="rubric">([^<]+)</p>', html)
    print(f"  подписи полей: {fields}")
    print(f"  рубрики: {rubrics}")
    print(f"  «Параметры» сырым текстом (раздел не распознан): {'Параметры</p>' in html or '<p>Параметры' in html}")
    for probe in ("(68)", "п. 4.1", "eq:", "ssec:"):
        print(f"  в тексте {probe!r}: {probe in html}")
    print(f"  атрибут p_wf: {'p_wf' in html}")


def report_warnings(lines: list[str]) -> None:
    """Предупреждения по документу-источнику и типу; по три примера на группу."""
    groups = defaultdict(list)
    for s in lines:
        kind = re.search(r"\[([a-z_.]+)\]\s*$", s)
        src = "README" if "README.md" in s else ("api" if ("gpn_multiphase_solver" in s or "api.rst" in s)
                                                 else ("probe" if "probe_ru" in s else "прочее"))
        groups[(src, kind.group(1) if kind else "-")].append(s)
    print(f"  предупреждений всего: {len(lines)}")
    for (src, kind), items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"  [{src}] {kind}: {len(items)}")
        for s in items[:3]:
            print(f"      {s[:260]}")
    msgs = Counter(re.sub(r"^.*?(WARNING|ERROR): ", "", s)[:70] for s in lines)
    print("  частые сообщения:")
    for m, n in msgs.most_common(12):
        print(f"      {n:4d}  {m}")


def main() -> None:
    import sphinx, myst_parser, docutils
    print(f"Срез: {SLICE}\nAUX: {AUX}, меток в таблице: {len(numbers)} "
          f"(eq: {sum(k.startswith('eq:') for k in numbers)})")
    print(f"sphinx {sphinx.__version__}, myst-parser {myst_parser.__version__}, docutils {docutils.__version__}")
    print(f"Публичный интерфейс пробы: функций {len(FUNCTIONS)}, классов {len(CLASSES)}, модулей {len(MODULES)}")
    for lang in ("ru", "en"):
        print(f"\n=== language = {lang!r}")
        write_sources(lang)
        out, lines = build(lang)
        report_html(out)
        report_warnings(lines)


if __name__ == "__main__":
    main()
