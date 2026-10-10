"""DEBT-010: замены шагов 2–3 плана — на копии дерева (рабочий каталог не трогается).

Запуск из numerical_solver/ (основного каталога или worktree):
    python <путь>\\vault\\issues\\debt-010\\probes\\plan_check.py
План берётся из ../vault/plans/ относительно текущего каталога.
Проверяет: тест-сторож шага 1 на исходной копии (ожидание — 42 нарушения);
каждое «до» встречается в файле ровно один раз и на заявленной строке;
после замен сторож зелёный, AST без докстрингов не изменился, длина
правленых строк; негативная проверка сторожа.
"""
import ast
import re
import shutil
import sys
from pathlib import Path

SOLVER = Path.cwd()
PLAN = SOLVER.parent / "vault" / "plans" / "debt-010 docstring-eq-labels.md"
TREE = Path(__file__).resolve().parent / "tree"      # копия, удаляется в конце
print("пакет:", SOLVER)

plan = PLAN.read_text(encoding="utf-8")

# ── Копия дерева: .py и README трёх каталогов + постановка ──
if TREE.exists():
    shutil.rmtree(TREE)
for d in ("gpn_multiphase_solver", "tests", "examples"):
    for pat in ("*.py", "*.md"):
        for f in (SOLVER / d).rglob(pat):
            dst = TREE / f.relative_to(SOLVER)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dst)
(TREE / "doc").mkdir(parents=True, exist_ok=True)
shutil.copyfile(SOLVER / "doc" / "problem_statement.tex", TREE / "doc" / "problem_statement.tex")

# ── Тест-сторож из плана — в копию ──
m = re.search(r"\*\*Что сделать:\*\* создать файл:\s*```python\r?\n(.*?)```", plan, re.S)
guard = m.group(1)
guard_file = TREE / "tests" / "test_eq_references.py"
guard_file.write_text(guard, encoding="utf-8")
ns = {"__file__": str(guard_file), "__name__": "guard"}
exec(compile(guard, str(guard_file), "exec"), ns)
TESTS = ("test_no_numeric_equation_or_line_references",
         "test_label_references_exist_in_problem_statement")


def run_guard(tag):
    for name in TESTS:
        try:
            ns[name]()
            print(f"[{tag}] {name}: PASSED")
        except AssertionError as e:
            lines = str(e).splitlines()[1:]
            files = {l.split(":")[0] for l in lines}
            print(f"[{tag}] {name}: FAILED — {len(lines)} строк в {len(files)} файлах")


run_guard("до замен")


def section(title_start, next_start):
    i = plan.index(title_start)
    return plan[i:plan.index(next_start, i)]


def code_span(cell):
    """Содержимое ячейки-кода: `x` или ``x``; \\| → |. Иначе None."""
    c = cell.strip()
    mm = re.fullmatch(r"``\s?(.*?)\s?``", c) or re.fullmatch(r"`(.*)`", c)
    return mm.group(1).replace("\\|", "|") if mm else None


edits, described = [], []   # (путь, строка, до, после); строки таблиц со словесным «после»

# ── Шаг 2: файл задаётся строкой-заголовком «`имя.py`…» перед таблицей ──
s2 = section("## Шаг 2.", "## Шаг 3.")
cur = None
for line in s2.splitlines():
    mm = re.match(r"^`([\w/]+\.py)`", line)
    if mm:
        cur = "gpn_multiphase_solver/" + mm.group(1)
        continue
    if line.startswith("| ") and cur:
        cells = re.split(r"(?<!\\)\|", line)[1:-1]
        if len(cells) != 3 or not cells[0].strip()[:1].isdigit():
            continue
        before, after = code_span(cells[1]), code_span(cells[2])
        if before is None or after is None:
            described.append(f"{cur}:{cells[0].strip()}")
        else:
            edits.append((cur, cells[0].strip(), before, after))

# ── Шаг 3: «файл:строка» в первой ячейке ──
s3 = section("## Шаг 3.", "## Шаг 4.")
for line in s3.splitlines():
    if not line.startswith("| `"):
        continue
    cells = re.split(r"(?<!\\)\|", line)[1:-1]
    loc = code_span(cells[0])
    name, ln = loc.rsplit(":", 1)
    path = ("tests/" if name.startswith("test_") else "examples/") + name
    before, after = code_span(cells[1]), code_span(cells[2])
    if before is None or after is None:
        described.append(f"{path}:{ln}")
    else:
        edits.append((path, ln, before, after))

# ── Многострочные замены: блоки «**`путь:N`** — до: ```text … ``` после: ```text … ```» ──
blocks = re.findall(r"\*\*`([^`]+?):(\d+)(?:–\d+)?`\*\* — до:\s*```text\r?\n(.*?)\r?\n```\s*"
                    r"после:\s*```text\r?\n(.*?)\r?\n```", plan, re.S)
for path, ln, before, after in blocks:
    edits.append((path, ln, before, after))
covered = {f"{p}:{n}" for p, n, _, _ in blocks}
for d in described:
    p, n = d.rsplit(":", 1)
    if f"{p}:{n.split('–')[0]}" not in covered:
        print("✗ строка таблицы описана словами, блока нет:", d)
print(f"замен: {len(edits)} (таблицы {len(edits) - len(blocks)}, блоки {len(blocks)})")

# ── Применение: единственность «до» и номер строки ──
problems = 0
orig = {}
for path, ln, before, after in edits:
    f = TREE / path
    text = f.read_text(encoding="utf-8")
    orig.setdefault(path, text)
    n = text.count(before)
    if n != 1:
        print(f"✗ {path}:{ln}: «до» встречается {n} раз: {before[:70]}")
        problems += 1
        continue
    at = text[:text.index(before)].count("\n") + 1
    if at != int(ln):
        print(f"~ {path}:{ln}: «до» найдено на строке {at}")
    f.write_text(text.replace(before, after), encoding="utf-8")
print("файлов изменено:", len(orig), " проблем «до»:", problems)

# ── Длина правленых строк ──
for path in orig:
    old = set(orig[path].splitlines())
    for i, l in enumerate((TREE / path).read_text(encoding="utf-8").splitlines(), 1):
        if l not in old and len(l) > 100:
            print(f"длина {len(l)} > 100: {path}:{i}")


# ── AST без докстрингов ──
def strip(src):
    t = ast.parse(src)
    for node in ast.walk(t):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                    and isinstance(b[0].value.value, str):
                node.body = b[1:] or [ast.Pass()]
    return ast.dump(t)


py = [p for p in orig if p.endswith(".py")]
diff = [p for p in py if strip(orig[p]) != strip((TREE / p).read_text(encoding="utf-8"))]
print(f"AST: .py изменено {len(py)}, с другой логикой: {diff or 0}")

run_guard("после замен")

# ── Негатив: временный файл с номером и несуществующей меткой ──
neg = TREE / "tests" / "_neg_probe.py"
neg.write_text("# (eq. 8)\n# eq:no_such_label\n", encoding="utf-8")
run_guard("негатив")
neg.unlink()

shutil.rmtree(TREE)
sys.exit(1 if problems or diff else 0)
