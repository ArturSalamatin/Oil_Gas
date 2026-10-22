"""Красное состояние кода плана DEBT-046 на настоящих файлах examples/.

Берёт _script_problems из test_plan_debt046.py (копия теста плана), удаляет
имя из общего модуля / пакета или подменяет run_example и печатает, какие
файлы examples/ проверка помечает. Сверка: помечены ровно пользователи имени.

Запуск из numerical_solver/ (основной каталог или worktree):
    .venv\\Scripts\\python <путь>\\red_plan_check.py        # копия теста в пробах
    .venv\\Scripts\\python <путь>\\red_plan_check.py impl   # tests/test_example_scripts.py
Вывод — на экран и в red_<plan|impl>_check.out.txt рядом со скриптом.
"""
import importlib
import sys
from pathlib import Path

SOLVER = Path.cwd()
HERE = Path(__file__).resolve().parent
MODE = sys.argv[1] if len(sys.argv) > 1 else "plan"
for _p in (SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3", SOLVER,
           SOLVER / "examples", HERE):
    sys.path.insert(0, str(_p))

if MODE == "impl":
    sys.path.insert(0, str(SOLVER / "tests"))
    import test_example_scripts as plan  # noqa: E402
else:
    import test_plan_debt046 as plan  # noqa: E402
import gpn_multiphase_solver  # noqa: E402

OUT = []


def out(line=""):
    print(line)
    OUT.append(line)


def flagged():
    return [s for s in plan.EXAMPLE_SCRIPTS
            if plan._script_problems(plan.EXAMPLES_DIR / s)]


def users(name):
    return [s for s in plan.EXAMPLE_SCRIPTS
            if name in (plan.EXAMPLES_DIR / s).read_text(encoding="utf-8")]


CASES = [
    ("figure_io", "export_emf"),
    ("closed_form", "solve_closed"),
    ("gpn_multiphase_solver.factory", "SimulatorFactory"),
    ("gpn_multiphase_solver.io.config", "load_config"),
    ("gpn_multiphase_solver.units", "S_TO_DAY"),
    ("two_phase_analytics", "report"),
    ("two_phase_analytics", "SG_EPS"),
    ("temperature_asymptotics", "single_phase_asymptote"),
    ("two_phase_analytics", "solve_closed"),
    ("example_runner", "_PROTO_ROOT"),
]

out(f"SOLVER = {SOLVER}")
out(f"проверка: {plan.__file__}")
out(f"пакет: {gpn_multiphase_solver.__file__}")
out(f"Файлов: {len(plan.EXAMPLE_SCRIPTS)}; зелёное состояние: "
    f"помечено {flagged()}")
for mod, name in CASES:
    module = importlib.import_module(mod)
    saved = getattr(module, name)
    delattr(module, name)
    try:
        got = flagged()
    finally:
        setattr(module, name, saved)
    # Определение самого имени в его модуле — не пользователь.
    owner = mod.split(".")[-1] + ".py"
    expected = [s for s in users(name) if not s.endswith(owner)]
    extra = sorted(set(got) - set(expected))
    lost = sorted(set(expected) - set(got))
    out(f"\nудалено {mod}.{name}: помечено {len(got)}")
    out(f"  помечены: {got}")
    out(f"  лишние (в тексте нет имени): {extra or '—'}")
    out(f"  упоминают, но не помечены: {lost or '—'}")

# (д): параметр title переименован.
import example_runner  # noqa: E402
orig = example_runner.run_example


def renamed(config_path, output_dir, figure_title, overlays=None,
            n_profiles=None, steady_state=True):
    pass


example_runner.run_example = renamed
try:
    got = flagged()
finally:
    example_runner.run_example = orig
out(f"\nrun_example(title → figure_title): помечено {len(got)}: {got}")

# (г): строка импорта удалена из самого файла — подмена текста при чтении.
real_read = Path.read_text
for rel, line in [("convergence.py", "from copy import deepcopy\n"),
                  ("03_standing_corey/main.py",
                   "import two_phase_analytics as tpa  # noqa: E402\n")]:
    target = plan.EXAMPLES_DIR / rel

    def patched(self, *a, _t=target, _l=line, **k):
        text = real_read(self, *a, **k)
        return text.replace(_l, "") if self == _t else text
    Path.read_text = patched
    try:
        probs = plan._script_problems(target)
    finally:
        Path.read_text = real_read
    out(f"\n{rel} без строки {line.strip()!r}: {probs}")

(HERE / f"red_{MODE}_check.out.txt").write_text("\n".join(OUT) + "\n",
                                            encoding="utf-8")
