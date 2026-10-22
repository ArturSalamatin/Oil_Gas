"""DEBT-053, аудит плана: применить блоки «До/После» плана к копиям и проверить.

1. Каждый блок «до:» плана встречается в файле ровно один раз.
2. Пропатченные .py разбираются (ast.parse); строки ≤ 100 символов.
3. AST без строковых констант совпадает с исходным с точностью до
   задуманных удалений (импорт, параметр, аргумент фабрики, тест,
   DT_WITH_RETRY): правки тестов и примера — только текст.
4. Итоговые grep плана: «A-retry» — 5 строк, «output_config» в пакете — 1.
5. Сигнатура в заметке vault = сигнатура пропатченного Simulator.
6. Пропатченные simulator/factory считают примеры 07 (первый интервал)
   и 10 побитово как исходные; max_retries = 0 на 10 — отказ в обоих.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-053\\probes\\audit_apply_plan.py
"""
import ast
import copy
import importlib.util
import inspect
import re
import shutil
import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
ROOT = SOLVER.parent
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
for p in (str(SOLVER), str(PROTO)):
    if p not in sys.path:
        sys.path.insert(0, p)

PLAN = ROOT / "vault" / "plans" / "debt-053 simulator-output-config-retry-terms.md"
FILES = {
    "simulator.py": SOLVER / "gpn_multiphase_solver" / "simulator.py",
    "factory.py": SOLVER / "gpn_multiphase_solver" / "factory.py",
    "test_dt_convergence.py": SOLVER / "tests" / "test_dt_convergence.py",
    "test_energy_matrix_examples.py": SOLVER / "tests" / "test_energy_matrix_examples.py",
    "test_rate_control.py": SOLVER / "tests" / "test_rate_control.py",
    "closed_form_convergence.py":
        SOLVER / "examples" / "05_standing_table_rp" / "closed_form_convergence.py",
    "модули-simulator-оркестратор.md":
        ROOT / "vault" / "knowledge" / "decisions" / "модули-simulator-оркестратор.md",
}
STEP_DEFAULT_FILE = {3: "test_dt_convergence.py"}

ok = True


def check(cond, msg):
    global ok
    print(("  OK   " if cond else "  FAIL ") + msg)
    ok = ok and cond


# ── Блоки кода плана ─────────────────────────────────────────
lines = PLAN.read_text(encoding="utf-8").splitlines()
blocks = []          # (предшествующая строка, текст блока, шаг)
step = None
i = 0
while i < len(lines):
    m = re.match(r"### Шаг (\d+)", lines[i])
    if m:
        step = int(m.group(1))
    fm = re.match(r"^(\s*)```\w*\s*$", lines[i])
    if fm:
        ind = len(fm.group(1))
        j, body = i + 1, []
        while not re.match(r"^\s*```\s*$", lines[j]):
            body.append(lines[j][ind:] if lines[j].startswith(" " * ind) else lines[j])
            j += 1
        k = i - 1
        while not lines[k].strip():
            k -= 1
        blocks.append((lines[k].strip(), "\n".join(body) + "\n", step))
        i = j + 1
        continue
    i += 1

pairs = []
for n, (prev, text, st) in enumerate(blocks):
    if prev.lower().endswith("до:") and n + 1 < len(blocks) \
            and blocks[n + 1][0].endswith("После:"):
        mf = re.search(r"`([^`:]+\.(?:py|md)):", prev)
        name = mf.group(1).split("/")[-1] if mf else STEP_DEFAULT_FILE[st]
        pairs.append((st, name, text, blocks[n + 1][1]))

print(f"Пар «до/после» в плане: {len(pairs)}")
orig = {k: p.read_text(encoding="utf-8") for k, p in FILES.items()}
new = dict(orig)

print("\n1. Блоки «до:» в файлах")
for st, name, before, after in pairs:
    cnt = new[name].count(before)
    check(cnt == 1, f"шаг {st}, {name}: вхождений {cnt}")
    if cnt == 1:
        new[name] = new[name].replace(before, after)

# Удаления, описанные в плане прозой
imp = "from .io.config import OutputConfig\n"
check(new["simulator.py"].count(imp) == 1, "шаг 2: импорт OutputConfig найден")
new["simulator.py"] = new["simulator.py"].replace(imp, "")

marker = "\n\n    def test_retry_steps_match_their_neighbours"
idx = new["test_dt_convergence.py"].index(marker)
tail = new["test_dt_convergence.py"][idx:]
check(len(re.findall(r"^\s*(def|class) ", tail, re.M)) == 1,
      "шаг 3: удаляемый метод — последний в файле")
new["test_dt_convergence.py"] = new["test_dt_convergence.py"][:idx + 1]

sig_line = "                 output_config: OutputConfig | None = None,\n"
check(new["модули-simulator-оркестратор.md"].count(sig_line) == 1,
      "шаг 5: строка сигнатуры в заметке найдена")
new["модули-simulator-оркестратор.md"] = new["модули-simulator-оркестратор.md"].replace(sig_line, "")

# ── 2. Разбор и длина строк ──────────────────────────────────
print("\n2. Разбор и длина строк")
trees = {}
for name in FILES:
    if not name.endswith(".py"):
        continue
    trees[name] = (ast.parse(orig[name]), ast.parse(new[name]))
    old_set = set(orig[name].splitlines())
    long = [ln for ln in new[name].splitlines() if ln not in old_set and len(ln) > 100]
    check(not long, f"{name}: разбор, новых строк > 100 символов: {len(long)}")


# ── 3. AST без строк ─────────────────────────────────────────
class Blank(ast.NodeTransformer):
    def visit_Constant(self, node):
        return ast.Constant("") if isinstance(node.value, str) else node

    def visit_JoinedStr(self, node):
        return ast.Constant("")


def norm(tree):
    return ast.dump(Blank().visit(copy.deepcopy(tree)))


print("\n3. AST без строковых констант")
for name in ("test_energy_matrix_examples.py", "test_rate_control.py",
             "closed_form_convergence.py"):
    a, b = trees[name]
    check(norm(a) == norm(b), f"{name}: код не изменился")

a, b = trees["test_dt_convergence.py"]
a = copy.deepcopy(a)
a.body = [n for n in a.body if not (isinstance(n, ast.Assign)
          and any(getattr(t, "id", "") == "DT_WITH_RETRY" for t in n.targets))]
for n in a.body:
    if isinstance(n, ast.ClassDef):
        n.body = [f for f in n.body
                  if getattr(f, "name", "") != "test_retry_steps_match_their_neighbours"]
check(norm(a) == norm(b), "test_dt_convergence.py: = исходный − DT_WITH_RETRY − тест")
cls = [n for n in b.body if isinstance(n, ast.ClassDef)][0]
print("       методы класса:", [f.name for f in cls.body if isinstance(f, ast.FunctionDef)])

a, b = trees["simulator.py"]
a = copy.deepcopy(a)
a.body = [n for n in a.body if not (isinstance(n, ast.ImportFrom) and n.module == "io.config")]
for n in ast.walk(a):
    if isinstance(n, ast.FunctionDef) and n.name == "__init__" and any(
            x.arg == "output_config" for x in n.args.args):
        k = [x.arg for x in n.args.args].index("output_config")
        n.args.args.pop(k)
        n.args.defaults.pop(k - (len(n.args.args) + 1 - len(n.args.defaults)))
check(norm(a) == norm(b), "simulator.py: = исходный − импорт − параметр")

a, b = trees["factory.py"]
a = copy.deepcopy(a)
for n in ast.walk(a):
    if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Simulator":
        n.keywords = [kw for kw in n.keywords if kw.arg != "output_config"]
check(norm(a) == norm(b), "factory.py: = исходный − аргумент output_config")

# ── 4. Итоговые grep ─────────────────────────────────────────
print("\n4. Итоговые grep по numerical_solver/ (без прототипа) после правок")
by_path = {p: new[k] for k, p in FILES.items()}
hits, oc_pkg = [], 0
for p in SOLVER.rglob("*"):
    rel = p.relative_to(SOLVER).as_posix()
    if not p.is_file() or p.suffix not in {".py", ".md", ".json", ".tex", ".txt"} or \
            rel.startswith(("HydroSolverPrototype/", ".venv/")) or "__pycache__" in rel:
        continue
    text = by_path.get(p) or p.read_text(encoding="utf-8", errors="ignore")
    for ln_no, ln in enumerate(text.splitlines(), 1):
        if "A-retry" in ln:
            hits.append(f"{rel}:{ln_no}")
        if "output_config" in ln and rel.startswith(("gpn_multiphase_solver/", "tests/",
                                                     "examples/")):
            oc_pkg += 1
            print(f"       output_config: {rel}:{ln_no}: {ln.strip()}")
print("       A-retry:", hits)
check(len(hits) == 5, f"A-retry — {len(hits)} строк (план: 5)")
check("tests/test_energy_matrix_examples.py:769" in hits, "бывшая :768 теперь :769")
check(oc_pkg == 1, f"output_config в пакете, тестах, примерах — {oc_pkg} (план: 1)")
check("DT_WITH_RETRY" not in new["test_dt_convergence.py"], "DT_WITH_RETRY — 0")

# ── 5. Заметка vault ─────────────────────────────────────────
print("\n5. Сигнатура в заметке")
m_note = re.search(r"    def __init__\(self.*?\):\n", new["модули-simulator-оркестратор.md"], re.S)
m_code = re.search(r"    def __init__\(self, grid.*?\):\n", new["simulator.py"], re.S)
norm_sig = lambda s: " ".join(s.split())  # noqa: E731
check(norm_sig(m_note.group(0)) == norm_sig(m_code.group(0)),
      f"заметка = код: {norm_sig(m_code.group(0))}")
check("output_config" in new["модули-simulator-оркестратор.md"].split("```", 2)[2],
      "абзац об удалении на месте")

# ── 6. Расчёт: пропатченные модули против исходных ───────────
print("\n6. Расчёт")
import gpn_multiphase_solver.factory as orig_factory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

print(f"       пакет: {Path(orig_factory.__file__).parent}")


def run(factory_mod, example, n_iv=None, max_retries=None):
    cfg = copy.deepcopy(load_config(SOLVER / "examples" / example / "config.json"))
    cfg.output.log_level = "ERROR"
    if n_iv:
        cfg.time.history = cfg.time.history[:n_iv]
    if max_retries is not None:
        cfg.numerics.max_retries = max_retries
    sim, init = factory_mod.SimulatorFactory.from_config(cfg)
    try:
        return sim.run(init)
    except RuntimeError as exc:
        return f"RuntimeError: {str(exc).splitlines()[0]}"


cases = [("07_degassing_adiabatic_only", 1, None), ("10_deep_degassing", None, None),
         ("10_deep_degassing", None, 0)]
ref = [run(orig_factory, *c) for c in cases]

tmp = Path(__file__).parent / "_patched"
tmp.mkdir(exist_ok=True)
loaded = {}
try:
    # Модули берутся из loaded, не через import: «import pkg.factory as x»
    # вернул бы атрибут пакета — исходный модуль, а не подменённый в sys.modules.
    for name, mod in (("simulator.py", "gpn_multiphase_solver.simulator"),
                      ("factory.py", "gpn_multiphase_solver.factory")):
        (tmp / name).write_text(new[name], encoding="utf-8")
        spec = importlib.util.spec_from_file_location(mod, tmp / name)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    new_factory = loaded["factory.py"]
    NewSim = loaded["simulator.py"].Simulator
    check(new_factory is not orig_factory, "фабрика — пропатченный модуль")
    params = list(inspect.signature(NewSim.__init__).parameters)
    check(params == ["self", "grid", "hydro", "energy", "pvt", "schedule", "max_retries"],
          f"сигнатура: {params}")
    check(new_factory.Simulator is NewSim, "фабрика берёт пропатченный Simulator")
    out = [run(new_factory, *c) for c in cases]
finally:
    shutil.rmtree(tmp)

for c, a_, b_ in zip(cases, ref, out):
    if isinstance(a_, str) or isinstance(b_, str):
        check(a_ == b_, f"{c}: {a_!r} | {b_!r}")
        continue
    same = len(a_.states) == len(b_.states) and all(
        np.array_equal(getattr(x, f), getattr(y, f))
        for x, y in zip(a_.states, b_.states) for f in ("p", "Sg", "Rs", "T"))
    check(same and np.array_equal(a_.times, b_.times),
          f"{c}: записей {len(a_.states)}, побитово")

print("\nИТОГ:", "все проверки пройдены" if ok else "ЕСТЬ ПРОВАЛЫ")
