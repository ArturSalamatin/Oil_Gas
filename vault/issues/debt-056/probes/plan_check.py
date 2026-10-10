r"""DEBT-056, аудит плана: блоки «До/После» плана, применённые дословно к копии кода.

Запуск из numerical_solver/ основного каталога:
    .venv\Scripts\python ..\vault\issues\debt-056\probes\plan_check.py
Копия — vault/issues/debt-056/probes/plan_tree/ (gpn_multiphase_solver, tests/conftest.py,
tests/test_config.py, configs/baseline.json, pyproject.toml, doc/problem_statement.tex);
удаляется в конце. Блоки берутся из vault/plans/debt-056 skin-bhp-range-check.md по якорям
пунктов; каждая замена «До → После» должна найти ровно одно вхождение.
Состояния:
  S0 — шаг 2 (тесты), код не тронут: ожидание 13 failed, 8 passed;
  S1 — + шаг 3 (скин): 17 passed, 4 failed;
  S2 — + шаг 4 (забой): 21 passed, весь test_config.py зелёный.
Затем на S2: тексты отказа и предупреждений; все JSON-конфиги проекта через load_config
копии — отказов и предупреждений нет; problem_statement.tex с абзацем шага 5.2 — сборка.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/, не из {SOLVER}")
ROOT = SOLVER.parent
PLAN = ROOT / "vault" / "plans" / "debt-056 skin-bhp-range-check.md"
TREE = Path(__file__).resolve().parent / "plan_tree"
PY = sys.executable


def blocks_after(text: str, anchor: str, count: int) -> list[str]:
    """count блоков кода после якоря; отступ пункта списка (по открывающей ```) снимается."""
    pos = text.index(anchor)
    assert text.count(anchor) == 1, f"якорь не единственный: {anchor}"
    lines = text[pos:].splitlines()
    out, i = [], 0
    while len(out) < count:
        m = re.match(r"^( *)```", lines[i])
        if m:
            ind = len(m.group(1))
            body = []
            i += 1
            while not re.match(r"^ *```\s*$", lines[i]):
                body.append(lines[i][ind:] if lines[i].strip() else "")
                i += 1
            out.append("\n".join(body) + "\n")
        i += 1
    return out


def replace_once(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    assert n == 1, f"{what}: «До» найдено {n} раз"
    return text.replace(old, new)


def append_func(text: str, block: str) -> str:
    return text.rstrip("\n") + "\n\n\n" + block


def pytest(args: list[str]) -> str:
    r = subprocess.run([PY, "-m", "pytest", *args, "-q", "-p", "no:cacheprovider"],
                       cwd=TREE, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip().splitlines()[-1]


def run_py(code: str) -> str:
    r = subprocess.run([PY, "-c", code], cwd=TREE, capture_output=True, text=True,
                       encoding="utf-8")
    return (r.stdout + r.stderr).strip()


def main() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    if TREE.exists():
        shutil.rmtree(TREE)
    shutil.copytree(SOLVER / "gpn_multiphase_solver", TREE / "gpn_multiphase_solver",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (TREE / "tests").mkdir()
    (TREE / "configs").mkdir()
    (TREE / "doc").mkdir()
    for rel in ("tests/conftest.py", "tests/test_config.py", "configs/baseline.json",
                "pyproject.toml", "doc/problem_statement.tex"):
        shutil.copy(SOLVER / rel, TREE / rel)
    cfg_py = TREE / "gpn_multiphase_solver" / "io" / "config.py"
    test_py = TREE / "tests" / "test_config.py"
    try:
        print("код копии:", run_py("import gpn_multiphase_solver.io.config as c; print(c.__file__)"))

        # ── S0: шаг 2 ──
        t = test_py.read_text(encoding="utf-8")
        doc, = blocks_after(plan, "1. Шапка модуля (строки 3-12)", 1)
        t = replace_once(t, "- История: несколько интервалов, control type, p_wf.\n",
                         "- История: несколько интервалов, control type, p_wf.\n" + doc,
                         "шапка")
        tests, = blocks_after(plan, "2. После класса `TestValidationNumbers`", 1)
        marker = "# ═════════════════════════════════════════════════════════════\n# E. Мульти"
        t = replace_once(t, marker, tests + "\n\n" + marker, "тесты")
        test_py.write_text(t, encoding="utf-8")
        print("S0 класс:", pytest(["tests/test_config.py", "-k", "TestValidationWell"]))

        # ── S1: шаг 3 ──
        c = cfg_py.read_text(encoding="utf-8")
        for anchor, what in (("1. Импорт: после строки 12", "импорт"),
                             ("2. Комментарий поля `NumericsConfig.skin`", "поле skin"),
                             ("4. Отказ при $s < 0$ — в `_validate`", "отказ s<0"),
                             ("6. `load_config`, строки 334-335", "вызов skin")):
            old, new = blocks_after(plan, anchor, 2)
            c = replace_once(c, old, new, what)
        const, = blocks_after(plan, "3. Константа порога", 1)
        tail = '"initial_conditions", "time", "numerics")\n'
        c = replace_once(c, tail, tail + "\n" + const, "константа")
        func, = blocks_after(plan, "5. Новая функция — в конец модуля, после `_validate_interval`", 1)
        c = append_func(c, func)
        cfg_py.write_text(c, encoding="utf-8")
        print("S1 класс:", pytest(["tests/test_config.py", "-k", "TestValidationWell"]))
        print("S1 модуль:", pytest(["tests/test_config.py"]))

        # ── S2: шаг 4 ──
        b = blocks_after(plan, "1. `_expand_history` — сигнатура", 4)
        c = replace_once(c, b[0], b[1], "_expand_history сигнатура")
        c = replace_once(c, b[2], b[3], "_expand_history возврат")
        for anchor, what in (("2. `load_config`, строка 303:", "history_blocks"),
                             ("3. `load_config`, конец — вызов после `_warn_large_skin`",
                              "вызов забоя")):
            old, new = blocks_after(plan, anchor, 2)
            c = replace_once(c, old, new, what)
        func, = blocks_after(plan, "4. Новая функция — в конец модуля, после `_warn_large_skin`", 1)
        c = append_func(c, func)
        cfg_py.write_text(c, encoding="utf-8")
        print("S2 класс:", pytest(["tests/test_config.py", "-k", "TestValidationWell"]))
        print("S2 модуль:", pytest(["tests/test_config.py"]))

        # Строки длиннее 100 символов в добавленном коде
        long = [ln for ln in c.splitlines() if len(ln) > 100]
        print("строк > 100 в config.py копии:", len(long))
        for ln in long:
            print("   ", len(ln), ln[:90])

        # ── Тексты сообщений ──
        demo = r'''
import json, logging, tempfile
from pathlib import Path
from gpn_multiphase_solver.io.config import load_config
msgs = []
class H(logging.Handler):
    def emit(self, r): msgs.append(r.getMessage())
logging.getLogger("gpn_multiphase_solver").addHandler(H(logging.WARNING))
base = json.loads(Path("configs/baseline.json").read_text(encoding="utf-8"))
def case(name, change):
    raw = json.loads(json.dumps(base)); change(raw); msgs.clear()
    p = Path(tempfile.mkdtemp()) / "c.json"; p.write_text(json.dumps(raw), encoding="utf-8")
    try:
        load_config(p); out = "OK"
    except ValueError as e:
        out = "ValueError: " + str(e)
    print(f"--- {name}: {out}")
    for m in msgs: print("    WARNING:", m)
case("skin -0.5", lambda r: r.setdefault("numerics", {}).update(skin=-0.5))
case("skin -7", lambda r: r.setdefault("numerics", {}).update(skin=-7.0))
case("skin 50", lambda r: r.setdefault("numerics", {}).update(skin=50.0))
case("skin 1e3", lambda r: r.setdefault("numerics", {}).update(skin=1e3))
case("p_wf 25 МПа", lambda r: r["time"].update(history=[{"dt": 86400, "control": "pressure", "p_wf": 25e6}]))
case("min_bhp 25 МПа", lambda r: r["time"].update(history=[{"dt": 86400, "control": "rate", "q_oil": 1e-3, "min_bhp": 25e6}]))
'''
        print(run_py(demo))

        # ── Конфиги проекта через load_config копии ──
        scan = r'''
import json, logging, sys
from pathlib import Path
from gpn_multiphase_solver.io.config import load_config
SOLVER = Path(sys.argv[1]); msgs = []
class H(logging.Handler):
    def emit(self, r): msgs.append(r.getMessage())
logging.getLogger("gpn_multiphase_solver").addHandler(H(logging.WARNING))
n = bad = 0
for p in sorted(SOLVER.rglob("*.json")):
    rel = p.relative_to(SOLVER)
    if any(x.startswith(".") for x in rel.parts) or rel.parts[0] == "HydroSolverPrototype":
        continue
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(raw, dict) or "time" not in raw or "initial_conditions" not in raw:
        continue
    n += 1; msgs.clear()
    try:
        load_config(p)
    except ValueError as e:
        msgs.append("ValueError: " + str(e))
    if msgs:
        bad += 1; print(rel, msgs)
print(f"конфигов: {n}, с отказом или предупреждением: {bad}")
'''
        r = subprocess.run([PY, "-c", scan, str(SOLVER)], cwd=TREE, capture_output=True,
                           text=True, encoding="utf-8")
        print((r.stdout + r.stderr).strip())

        # ── LaTeX: абзац шага 5.2 ──
        tex = TREE / "doc" / "problem_statement.tex"
        par, = blocks_after(plan, "5.2. **`problem_statement.tex`**", 1)
        s = tex.read_text(encoding="utf-8")
        anchor = "\\paragraph{Забой ($r = \\rw$"
        s = replace_once(s, anchor, par + "\n" + anchor, "tex")
        tex.write_text(s, encoding="utf-8")
        for _ in range(2):
            r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "problem_statement.tex"],
                               cwd=TREE / "doc", capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        log = (TREE / "doc" / "problem_statement.log").read_text(encoding="utf-8", errors="replace")
        print("LaTeX: код", r.returncode, "| ошибок «!»:", log.count("\n!"),
              "| Undefined control sequence:", log.count("Undefined control sequence"),
              "| undefined references:", log.count("undefined"))
    finally:
        shutil.rmtree(TREE, ignore_errors=True)


if __name__ == "__main__":
    main()
