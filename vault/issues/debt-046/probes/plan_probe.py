"""Пробы плана DEBT-046: проверка имён в скриптах examples/ без расчётов.

Режимы:
  inventory — опись скриптов: защита __main__, код верхнего уровня,
              импорты из examples/ и пакета (верхний уровень / в функциях),
              обращения alias.attr к модулям examples/, вызовы run_example;
  v1        — вариант 1: runpy.run_path + LOAD_GLOBAL по всем code-объектам;
  v2        — вариант 2: разбор AST, hasattr по импортированным модулям;
  red       — красное состояние: подмена имён в общих модулях и пакете,
              какой вариант какой скрипт ловит;
  static_g  — класс (г) статически: LOAD_GLOBAL всех вложенных code-объектов
              против имён, связанных на уровне модуля (AST), без runpy.

Запуск (из numerical_solver/):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-046\\probes\\plan_probe.py <режим>
Вывод — на экран и в <режим>.out.txt рядом со скриптом.
"""
import ast
import builtins
import dis
import importlib
import inspect
import runpy
import sys
import time
import types
from pathlib import Path

SOLVER = Path.cwd()
EXAMPLES_DIR = SOLVER / "examples"
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
# Как conftest.py (прототип) и тесты test_examples.py (examples/ в sys.path).
for _p in (PROTO, SOLVER, EXAMPLES_DIR):
    sys.path.insert(0, str(_p))

OUT = []


def out(*args):
    line = " ".join(str(a) for a in args)
    print(line)
    OUT.append(line)


# Скрипты, которые нельзя исполнять импортом: расчёт на верхнем уровне.
NO_RUNPY = {"01_single_phase_no_jt/spatial_convergence.py"}

SCRIPTS = sorted(p.relative_to(EXAMPLES_DIR).as_posix()
                 for p in EXAMPLES_DIR.rglob("*.py"))


# ── Общее ──────────────────────────────────────────────────────

def is_local(modname, script_dir):
    """Модуль из examples/, из папки скрипта или из пакета решателя."""
    if modname is None:
        return False
    top = modname.split(".")[0]
    if top == "gpn_multiphase_solver":
        return True
    return ((EXAMPLES_DIR / f"{top}.py").is_file()
            or (script_dir / f"{top}.py").is_file())


def has_main_guard(tree):
    for node in tree.body:
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"):
            return True
    return False


def enclosing_map(tree):
    """{узел: True, если внутри def/lambda} — импорт верхнего уровня или нет."""
    inside = {}

    def visit(node, in_func):
        for child in ast.iter_child_nodes(node):
            f = in_func or isinstance(child, (ast.FunctionDef,
                                              ast.AsyncFunctionDef,
                                              ast.Lambda))
            inside[child] = in_func
            visit(child, f)
    visit(tree, False)
    return inside


# ── Вариант 2: AST ─────────────────────────────────────────────

def ast_check(path):
    """(число проверенных имён, список пропавших) — разбор AST, без исполнения."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    script_dir = path.parent
    missing, checked = [], 0
    aliases = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.ImportFrom) and node.level == 0
                and is_local(node.module, script_dir)):
            try:
                mod = importlib.import_module(node.module)
            except ImportError as exc:
                missing.append(f"{node.module} (строка {node.lineno}): {exc}")
                continue
            for a in node.names:
                checked += 1
                if a.name == "*" or hasattr(mod, a.name):
                    continue
                try:   # from пакет import подмодуль
                    importlib.import_module(f"{node.module}.{a.name}")
                except ImportError:
                    missing.append(f"{node.module}.{a.name} (строка {node.lineno})")
        elif isinstance(node, ast.Import):
            for a in node.names:
                if not is_local(a.name, script_dir):
                    continue
                checked += 1
                try:
                    mod = importlib.import_module(a.name)
                except ImportError as exc:
                    missing.append(f"{a.name} (строка {node.lineno}): {exc}")
                    continue
                if a.asname:
                    aliases[a.asname] = mod
                elif "." not in a.name:
                    aliases[a.name] = mod
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases):
            checked += 1
            if not hasattr(aliases[node.value.id], node.attr):
                missing.append(f"{node.value.id}.{node.attr} "
                               f"(строка {node.lineno})")
    return checked, missing


def run_example_kw_check(path):
    """Именованные аргументы run_example(...) против сигнатуры (вопрос 4)."""
    import example_runner
    sig = inspect.signature(example_runner.run_example)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad, calls = [], 0
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "run_example"):
            calls += 1
            try:
                sig.bind(*[None] * len(node.args),
                         **{k.arg: None for k in node.keywords if k.arg})
            except TypeError as exc:
                bad.append(f"строка {node.lineno}: {exc}")
    return calls, bad


# ── Вариант 1: runpy + LOAD_GLOBAL ─────────────────────────────

def code_objects(code):
    yield code
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            yield from code_objects(c)


def runpy_check(path, drop=()):
    """Пропавшие имена: ошибка импорта или LOAD_GLOBAL без определения.

    drop — имена, удаляемые из пространства имён после импорта (имитация
    потерянной строки импорта в самом скрипте, класс (г)).
    """
    saved = list(sys.path)
    try:
        try:
            ns = runpy.run_path(str(path), run_name="__import_check__")
        except ImportError as exc:
            return [f"импорт: {exc}"]
    finally:
        sys.path[:] = saved
    for name in drop:
        ns.pop(name, None)
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    missing = set()
    for co in code_objects(code):
        if co is code:
            continue   # уровень модуля исполнен run_path
        for ins in dis.get_instructions(co):
            if (ins.opname == "LOAD_GLOBAL" and ins.argval not in ns
                    and not hasattr(builtins, ins.argval)):
                missing.add(f"{ins.argval} в {co.co_name}")
    return sorted(missing)


# ── Режимы ─────────────────────────────────────────────────────

def mode_inventory():
    out(f"SOLVER = {SOLVER}")
    out(f"Скриптов: {len(SCRIPTS)}")
    for rel in SCRIPTS:
        path = EXAMPLES_DIR / rel
        tree = ast.parse(path.read_text(encoding="utf-8"))
        inside = enclosing_map(tree)
        top_from, func_from, alias_attr = 0, 0, 0
        aliases = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.ImportFrom) and node.level == 0
                    and is_local(node.module, path.parent)):
                if inside.get(node):
                    func_from += len(node.names)
                else:
                    top_from += len(node.names)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if is_local(a.name, path.parent):
                        aliases.add(a.asname or a.name)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in aliases):
                alias_attr += 1
        # Код верхнего уровня, кроме импортов, определений, присваиваний,
        # докстринга, блока __main__ и типовых настроек.
        heavy = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef,
                                 ast.ClassDef, ast.Assign, ast.AnnAssign)):
                continue
            if isinstance(node, ast.If) and has_main_guard(
                    ast.Module(body=[node], type_ignores=[])):
                continue
            if isinstance(node, ast.Expr):
                src = ast.unparse(node)
                if isinstance(node.value, ast.Constant):
                    continue
                if src.startswith(("sys.path.insert", "matplotlib.use",
                                   "warnings.filterwarnings")):
                    continue
            heavy.append(f"{type(node).__name__}@{node.lineno}")
        calls, _ = run_example_kw_check(path)
        out(f"{rel:55s} main={'да' if has_main_guard(tree) else 'НЕТ':3s} "
            f"from_верх={top_from:2d} from_в_функции={func_from:2d} "
            f"alias.attr={alias_attr:2d} run_example={calls} "
            f"верхний_уровень={heavy if heavy else '—'}")


def mode_v1():
    out(f"SOLVER = {SOLVER}")
    t0 = time.perf_counter()
    total_bad = 0
    for rel in SCRIPTS:
        if rel in NO_RUNPY:
            out(f"{rel:55s} пропущен (расчёт на верхнем уровне)")
            continue
        t = time.perf_counter()
        bad = runpy_check(EXAMPLES_DIR / rel)
        total_bad += len(bad)
        out(f"{rel:55s} {time.perf_counter() - t:6.2f} с  "
            f"{'OK' if not bad else bad}")
    out(f"Итого: {time.perf_counter() - t0:.2f} с, замечаний {total_bad}")
    # Повтор — модули уже загружены, как в сессии pytest.
    t0 = time.perf_counter()
    for rel in SCRIPTS:
        if rel not in NO_RUNPY:
            runpy_check(EXAMPLES_DIR / rel)
    out(f"Повтор (модули загружены): {time.perf_counter() - t0:.2f} с")


def mode_v2():
    out(f"SOLVER = {SOLVER}")
    t0 = time.perf_counter()
    total_checked = total_bad = 0
    for rel in SCRIPTS:
        t = time.perf_counter()
        checked, bad = ast_check(EXAMPLES_DIR / rel)
        calls, kw_bad = run_example_kw_check(EXAMPLES_DIR / rel)
        total_checked += checked
        total_bad += len(bad) + len(kw_bad)
        out(f"{rel:55s} {time.perf_counter() - t:6.2f} с  имён {checked:3d}  "
            f"run_example {calls}  {'OK' if not (bad or kw_bad) else bad + kw_bad}")
    out(f"Итого: {time.perf_counter() - t0:.2f} с, имён {total_checked}, "
        f"замечаний {total_bad}")
    t0 = time.perf_counter()
    for rel in SCRIPTS:
        ast_check(EXAMPLES_DIR / rel)
        run_example_kw_check(EXAMPLES_DIR / rel)
    out(f"Повтор (модули загружены): {time.perf_counter() - t0:.2f} с")


# Подмены для красного состояния: (класс, модуль, имя).
RED_CASES = [
    ("(а) from-импорт верхнего уровня", "figure_io", "export_emf"),
    ("(а) from-импорт верхнего уровня", "closed_form", "solve_closed"),
    ("(б) from-импорт в функции + верхний", "gpn_multiphase_solver.factory",
     "SimulatorFactory"),
    ("(б) from-импорт в функции", "gpn_multiphase_solver.io.config",
     "load_config"),
    ("(в) alias.attr", "two_phase_analytics", "report"),
    ("(в) alias.attr", "temperature_asymptotics", "single_phase_asymptote"),
    ("(в) alias.attr (реэкспорт)", "two_phase_analytics", "solve_closed"),
]


def detect(mod, name):
    """Какие скрипты ловят варианты 1 и 2 при удалённом mod.name."""
    module = importlib.import_module(mod)
    saved = getattr(module, name)
    delattr(module, name)
    try:
        v1, v2 = [], []
        for rel in SCRIPTS:
            path = EXAMPLES_DIR / rel
            if rel not in NO_RUNPY and runpy_check(path):
                v1.append(rel)
            if ast_check(path)[1]:
                v2.append(rel)
    finally:
        setattr(module, name, saved)
    return v1, v2


def users(mod, name):
    """Скрипты, где имя встречается в тексте (грубый список пользователей)."""
    short = mod.split(".")[-1]
    res = []
    for rel in SCRIPTS:
        if Path(rel).stem == short:
            continue
        text = (EXAMPLES_DIR / rel).read_text(encoding="utf-8")
        if name in text:
            res.append(rel)
    return res


def mode_red():
    out(f"SOLVER = {SOLVER}")
    # Загрузить всё заранее — как сессия pytest.
    for rel in SCRIPTS:
        if rel not in NO_RUNPY:
            runpy_check(EXAMPLES_DIR / rel)
    for label, mod, name in RED_CASES:
        v1, v2 = detect(mod, name)
        out(f"\n{label}: удалено {mod}.{name}")
        out(f"  текст упоминает: {users(mod, name)}")
        out(f"  вариант 1 ловит: {v1}")
        out(f"  вариант 2 ловит: {v2}")
        out(f"  только 2: {sorted(set(v2) - set(v1))}; "
            f"только 1: {sorted(set(v1) - set(v2))}")

    # (г): потерянная строка импорта в самом скрипте — имя нужно только
    # в теле функции. Имитация: убрать имя из пространства имён.
    out("\n(г) имя только в теле функции: convergence.py без deepcopy")
    path = EXAMPLES_DIR / "convergence.py"
    out(f"  вариант 1: {runpy_check(path, drop=('deepcopy',))}")
    out("  вариант 2: не проверяет имена самого скрипта (по построению)")

    # Вопрос 4: переименованный параметр run_example.
    import example_runner
    orig = example_runner.run_example

    def renamed(config_path, output_dir, figure_title, overlays=None,
                n_profiles=None, steady_state=True):
        pass
    example_runner.run_example = renamed
    try:
        caught = [rel for rel in SCRIPTS
                  if run_example_kw_check(EXAMPLES_DIR / rel)[1]]
    finally:
        example_runner.run_example = orig
    out(f"\nВопрос 4: run_example(title → figure_title) ловит сверка "
        f"сигнатуры в {len(caught)} скриптах: {caught}")


# ── Класс (г) статически ───────────────────────────────────────

# Имена, которые Python сам кладёт в пространство имён модуля.
MODULE_DUNDERS = {"__file__", "__name__", "__doc__", "__spec__", "__loader__",
                  "__package__", "__builtins__", "__annotations__", "__cached__"}

_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
           ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def module_level_names(tree):
    """Имена, связанные на уровне модуля, включая блок __main__ и global."""
    names = set(MODULE_DUNDERS)

    def visit(node, at_module):
        for child in ast.iter_child_nodes(node):
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


def static_globals_missing(source, path):
    """LOAD_GLOBAL вложенных code-объектов без связанного имени модуля."""
    tree = ast.parse(source)
    bound = module_level_names(tree)
    code = compile(source, str(path), "exec")
    missing = set()
    for co in code_objects(code):
        if co is code:
            continue   # уровень модуля — LOAD_NAME, не LOAD_GLOBAL
        for ins in dis.get_instructions(co):
            if (ins.opname == "LOAD_GLOBAL" and ins.argval not in bound
                    and not hasattr(builtins, ins.argval)):
                missing.add(f"{ins.argval} в {co.co_name} "
                            f"(строка {co.co_firstlineno})")
    return sorted(missing)


# Удаляемые строки: (файл, точный текст строки).
RED_G = [
    ("convergence.py", "from copy import deepcopy\n"),
    ("03_standing_corey/main.py", "import two_phase_analytics as tpa  # noqa: E402\n"),
]


def mode_static_g():
    out(f"SOLVER = {SOLVER}")
    star = [rel for rel in SCRIPTS
            if "import *" in (EXAMPLES_DIR / rel).read_text(encoding="utf-8")]
    out(f"Файлы с 'import *': {star or '—'}")
    t0 = time.perf_counter()
    total = 0
    for rel in SCRIPTS:
        path = EXAMPLES_DIR / rel
        bad = static_globals_missing(path.read_text(encoding="utf-8"), path)
        total += len(bad)
        if bad:
            out(f"{rel:55s} {bad}")
    out(f"Зелёный прогон: {len(SCRIPTS)} файлов, замечаний {total}, "
        f"{time.perf_counter() - t0:.2f} с")
    for rel, line in RED_G:
        path = EXAMPLES_DIR / rel
        src = path.read_text(encoding="utf-8")
        assert src.count(line) == 1, (rel, line)
        bad = static_globals_missing(src.replace(line, ""), path)
        out(f"\nКрасное: {rel} без строки {line.strip()!r}")
        out(f"  статическая (г): {bad}")


if __name__ == "__main__":
    mode = sys.argv[1]
    {"inventory": mode_inventory, "v1": mode_v1, "v2": mode_v2,
     "red": mode_red, "static_g": mode_static_g}[mode]()
    (Path(__file__).parent / f"{mode}.out.txt").write_text(
        "\n".join(OUT) + "\n", encoding="utf-8")
