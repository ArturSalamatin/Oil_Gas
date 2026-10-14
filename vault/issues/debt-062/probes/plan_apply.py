"""DEBT-062, аудит: применить блоки «До → После» плана к копии дерева базы и прогнать сторож.

Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-062\\probes\\plan_apply.py <коммит базы>

Копия (git archive: пакет, тесты, примеры, постановка) — в probes/tree, удаляется
в конце. Блоки берутся из текста плана, а не переписываются руками: проверяется
сам план — что «До» совпадает с файлом ровно один раз и что после шага 1 сторож
падает ровно на 3 строках, после шага 2 — зелёный, AST эталона без докстрингов
не меняется.
"""

import ast
import io
import re
import tarfile
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path.cwd()
BASE = sys.argv[1]
HERE = Path(__file__).resolve().parent
TREE = HERE / "tree"
PLAN = REPO / "vault" / "plans" / "debt-062 label-number-guard.md"
NS = TREE / "numerical_solver"


def blocks(section):
    """Python-блоки раздела плана по порядку."""
    return re.findall(r"```python\n(.*?)```", section, flags=re.S)


def section(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i)]


def replace_once(path, old, new):
    src = path.read_text(encoding="utf-8")
    n = src.count(old)
    print(f"  «До» в {path.name}: вхождений {n}")
    assert n == 1, old
    path.write_text(src.replace(old, new), encoding="utf-8")


def pytest_eq_refs():
    r = subprocess.run([sys.executable, "-m", "pytest", str(NS / "tests" / "test_eq_references.py"),
                        "-q", "-p", "no:cacheprovider", "--noconftest", "-c", str(NS / "pytest.ini")],
                       capture_output=True, text=True, encoding="utf-8", cwd=NS)
    out = r.stdout.splitlines()
    # Сообщение сторожа: «E   tests\...:N: описание: текст» — префикс E у строк assert.
    viol = [l.lstrip("E ").strip() for l in out
            if "номер после метки «eq:имя (N)»:" in l and "tests" in l
            and "assert" not in l]                    # строка assert — повтор списка
    print(f"  итог: {out[-1] if out else r.stderr[-300:]}")
    print(f"  нарушений «номер после метки»: {len(viol)}")
    for v in viol:
        print(f"    {v}")
    return r.returncode


def strip_doc(src):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                    and isinstance(b[0].value.value, str):
                node.body = b[1:] or [ast.Pass()]
    return ast.dump(tree)


plan = PLAN.read_text(encoding="utf-8")
s1 = blocks(section(plan, "### Шаг 1:", "### Шаг 2:"))
s2 = blocks(section(plan, "### Шаг 2:", "### Шаг 3:"))
s3 = section(plan, "### Шаг 3:", "### Шаг 4:")
print(f"блоков python: шаг 1 — {len(s1)}, шаг 2 — {len(s2)}")
assert len(s1) == 5 and len(s2) == 6

if TREE.exists():
    shutil.rmtree(TREE)
TREE.mkdir()
try:
    arch = subprocess.run(["git", "archive", BASE, "--", "numerical_solver/gpn_multiphase_solver",
                           "numerical_solver/tests", "numerical_solver/examples",
                           "numerical_solver/doc/problem_statement.tex"],
                          capture_output=True, check=True, cwd=REPO).stdout
    with tarfile.open(fileobj=io.BytesIO(arch)) as tar:
        tar.extractall(TREE, filter="data")
    (NS / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    ref = NS / "tests" / "test_eq_references.py"
    emx = NS / "tests" / "test_energy_matrix_examples.py"
    emx_base = emx.read_text(encoding="utf-8")

    print("\n== база")
    pytest_eq_refs()

    print("\n== шаг 1")
    replace_once(ref, s1[0], s1[1])
    replace_once(ref, s1[2], s1[3])
    anchor = "def test_label_references_exist_in_problem_statement"
    replace_once(ref, anchor, s1[4] + "\n\n" + anchor)
    pytest_eq_refs()
    long = [(n, len(l)) for n, l in enumerate(ref.read_text(encoding="utf-8").splitlines(), 1)
            if len(l) > 100]
    print(f"  строк длиннее 100 в test_eq_references.py: {long}")

    print("\n== шаг 2")
    for old, new in zip(s2[0::2], s2[1::2]):
        replace_once(emx, old, new)
    rc = pytest_eq_refs()
    same = strip_doc(emx_base) == strip_doc(emx.read_text(encoding="utf-8"))
    print(f"  AST test_energy_matrix_examples.py без докстрингов совпадает с базой: {same}")
    print(f"  код возврата pytest: {rc}")

    print("\n== шаг 3")
    old = re.search(r"До:\n```\n(.*?)\n```", s3, flags=re.S).group(1)
    new = re.search(r"После:\n```\n(.*?)\n```", s3, flags=re.S).group(1)
    claude = subprocess.run(["git", "show", f"{BASE}:CLAUDE.md"], capture_output=True,
                            check=True, cwd=REPO).stdout.decode("utf-8")
    print(f"  «До» в CLAUDE.md: вхождений {claude.count(old)}; «После» уже есть: {claude.count(new)}")
finally:
    shutil.rmtree(TREE)
