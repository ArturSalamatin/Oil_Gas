"""Проба плана DEBT-070: применить правки «До/После» из текста плана к копии дерева.

Запуск из корня репозитория (основного каталога или worktree):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-070\\probes\\plan_apply.py [коммит] [--keep]

Что делает:
  1. git archive <коммит> → probes/tree (файлы правок + всё, что читает сторож меток);
  2. правки T, C, V из плана — по порядку, каждая «До» должна встретиться ровно один раз;
  3. pdflatex дважды в tree/numerical_solver/doc: страницы, undefined, LaTeX Warning, Overfull;
  4. запрещённые шаблоны старого соглашения в .tex и в заметках vault — 0;
  5. ast изменённых .py без докстрингов совпадает с базой; длина изменённых строк ≤ 79;
  6. сторож меток tests/test_eq_references.py на копии дерева.
Выход — probes/plan_apply.out.txt; tree удаляется в конце (кроме --keep).
"""

import ast
import io
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                    cwd=HERE, text=True).strip())
PLAN = ROOT / "vault" / "plans" / "debt-070 statement-boundary-notation.md"
TREE = HERE / "tree"
OUT = HERE / "plan_apply.out.txt"
TEX = "numerical_solver/doc/problem_statement.tex"

# Блок правки в плане: заголовок «#### Правка <id> — `<путь>`», затем «До:» и «После:»
# в блоках из четырёх обратных кавычек (внутри могут быть строки с тремя).
EDIT_RE = re.compile(
    r"#### Правка (\S+) — `([^`]+)`\s*\n+До:\n````[^\n]*\n(.*?)\n````\s*\n+"
    r"После:\n````[^\n]*\n(.*?)\n````", re.S)

# Сторожу меток нужны все источники, которые он обходит (.py ядра, тестов,
# примеров и README примеров) и сам .tex.
ARCHIVE_PATHS = ["numerical_solver/doc", "numerical_solver/gpn_multiphase_solver",
                 "numerical_solver/tests", "numerical_solver/examples",
                 "vault/knowledge", "CLAUDE.md"]

# Шаблоны старого соглашения: после плана — 0 вхождений (шаг 4 плана).
FORBIDDEN_TEX = [r"N+\half", r"\half+1", r"1+\half", "G_{3/2}", r"\Phi_{N}^",
                 r"\Phi_{1}^", r"\text{конт}", r"r_{\half} = \rw", "(p_0, T_0)",
                 r"\phi(p_0)", "R_{s,0} = 500", r"\newcommand{\ppl}{p_0}",
                 r"\newcommand{\Tpl}{T_0}"]
FORBIDDEN_VAULT = ["T_{1/2}", "T_{N+1/2}", "N+1/2", r"\Phi^+_{1/2}", r"\Phi^-_{1/2}",
                   "r_{f+1/2}"]
VAULT_NOTES = [
    "vault/knowledge/decisions/словарь-код-физика.md",
    "vault/knowledge/decisions/модули-grid-сетка.md",
    "vault/knowledge/decisions/свойства-фаз-на-контурной-грани-берутся-из-ГУ-при-притоке.md",
    "vault/knowledge/numerics/температура ячейки 0 — центр, не забой.md",
]

lines_out = []


def say(msg=""):
    print(msg)
    lines_out.append(msg)


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def strip_docstrings(tree):
    """AST без докстрингов модуля, классов и функций — для сравнения «правки только в тексте»."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    getattr(body[0], "value", None), ast.Constant) and isinstance(
                    body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    keep = "--keep" in sys.argv
    commit = args[0] if args else "HEAD"
    sha = subprocess.check_output(["git", "rev-parse", "--short", commit],
                                  cwd=ROOT, text=True).strip()
    say(f"Проба плана DEBT-070 на {commit} ({sha}); план: {PLAN.relative_to(ROOT)}")

    edits = EDIT_RE.findall(read(PLAN).replace("\r\n", "\n"))
    say(f"Правок в плане: {len(edits)} "
        f"(T: {sum(e[0].startswith('T') for e in edits)}, "
        f"C: {sum(e[0].startswith('C') for e in edits)}, "
        f"V: {sum(e[0].startswith('V') for e in edits)})")

    # ── Копия дерева ──
    if TREE.exists():
        shutil.rmtree(TREE)
    TREE.mkdir()
    tar_bytes = subprocess.check_output(["git", "archive", "--format=tar", sha, *ARCHIVE_PATHS],
                                        cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tf:
        tf.extractall(TREE)

    # ── Применение правок ──
    files = {}
    base_text = {}
    ok = True
    for eid, rel, before, after in edits:
        p = TREE / rel
        if rel not in files:
            files[rel] = read(p)
            base_text[rel] = files[rel]
        text = files[rel]
        crlf = "\r\n" in text
        b = before.replace("\n", "\r\n") if crlf else before
        a = after.replace("\n", "\r\n") if crlf else after
        n = text.count(b)
        if n != 1:
            ok = False
            say(f"  ✗ {eid} {rel}: «До» найден {n} раз")
            continue
        if b == a:
            ok = False
            say(f"  ✗ {eid} {rel}: «До» и «После» совпадают")
        files[rel] = text.replace(b, a)
    say(f"Каждая «До» найдена ровно один раз: {'да' if ok else 'НЕТ'}")
    for rel, text in files.items():
        write(TREE / rel, text)
    say(f"Изменено файлов: {len(files)}")

    # ── PDF ──
    doc = TREE / "numerical_solver" / "doc"
    # Три прохода: на чистой копии нет .aux, а ширины колонок longtable и номера
    # страниц сходятся только к третьему («Label(s) may have changed» после второго).
    for _ in range(3):
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "problem_statement.tex"],
                       cwd=doc, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log = (doc / "problem_statement.log").read_text(encoding="latin-1")
    m = re.search(r"\((\d+) pages", log)
    say(f"PDF: страниц {m.group(1) if m else '— (сборка не прошла)'}, "
        f"undefined {log.count('undefined')}, LaTeX Warning {log.count('LaTeX Warning')}, "
        f"Overfull {log.count('Overfull')}")
    for mm in re.finditer(r"Overfull \\hbox \(([\d.]+)pt too wide\) (?:in paragraph at lines|"
                          r"in alignment at lines|detected at line) ([\d-]+)", log):
        say(f"    Overfull {mm.group(1)} pt — строки {mm.group(2)}")
    aux = (doc / "problem_statement.aux").read_text(encoding="utf-8", errors="replace")
    for lab in ("ssec:grid", "ssec:bc_disc"):
        mm = re.search(r"\\newlabel\{" + re.escape(lab) + r"\}\{\{[^}]*\}\{(\d+)\}", aux)
        say(f"  {lab}: страница {mm.group(1) if mm else '?'}")

    # ── Запрещённые шаблоны ──
    tex = files.get(TEX, read(TREE / TEX))
    bad = {pat: tex.count(pat) for pat in FORBIDDEN_TEX if tex.count(pat)}
    say(f"Запрещённые шаблоны в .tex: {sum(bad.values())} {bad if bad else ''}")
    say("Оставшиеся индексы ½ без минуса (ожидаются: правая грань ячейки 0, случай N = 1):")
    for i, line in enumerate(tex.splitlines(), 1):
        # «{\half}» и «,\half}» — индекс ровно ½; «-\half}», «j+\half}», «N-\half}» не берутся
        if re.search(r"[{,]\\half\}", line):
            say(f"    {i}: {line.strip()}")
    say(f"Вхождений «-\\half»: {tex.count('-' + chr(92) + 'half')}")
    vbad = {}
    for rel in VAULT_NOTES:
        # «ΔT_{1/2}» в заметке BUG-015 — JT полуячейки, не индекс грани
        t = read(TREE / rel).replace(r"\Delta T_{1/2}", "")
        for pat in FORBIDDEN_VAULT:
            if t.count(pat):
                vbad[f"{Path(rel).name}: {pat}"] = t.count(pat)
    say(f"Запрещённые шаблоны в заметках vault: {sum(vbad.values())} {vbad if vbad else ''}")

    # ── .py: ast без докстрингов, длина изменённых строк ──
    for rel in files:
        if not rel.endswith(".py"):
            continue
        same = strip_docstrings(ast.parse(base_text[rel])) == strip_docstrings(ast.parse(files[rel]))
        base_lines = set(base_text[rel].splitlines())
        long = [ln for ln in files[rel].splitlines() if ln not in base_lines and len(ln) > 79]
        say(f"  {rel}: ast без докстрингов {'совпадает' if same else 'ОТЛИЧАЕТСЯ'}; "
            f"новых строк длиннее 79: {len(long)}")

    # ── Сторож меток на копии ──
    r = subprocess.run([sys.executable, "-m", "pytest",
                        str(TREE / "numerical_solver" / "tests" / "test_eq_references.py"),
                        "-q", "-p", "no:cacheprovider", "--noconftest",
                        "--rootdir", str(TREE / "numerical_solver")],
                       cwd=TREE / "numerical_solver", capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    say(f"Сторож меток: {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]}")

    OUT.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    if not keep:
        shutil.rmtree(TREE, ignore_errors=True)


if __name__ == "__main__":
    main()
