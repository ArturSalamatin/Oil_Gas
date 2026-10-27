"""Аудит DEBT-087: эмуляция шага 2 плана на копии test_packaging.py.

Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-087\\probes\\audit_emulate.py

Блоки кода берутся из файла плана (не копией), правки шага 2 применяются к
настоящему numerical_solver/tests/test_packaging.py, результат пишется в
probes/emu/numerical_solver/tests/. Рядом – CHANGELOG.md и __init__.py пакета
(SOLVER_INIT). Три прогона `pytest -k changelog`: старая шапка, новая шапка
(header_new.md), новая шапка в форме дерева метки (номер 1.0.7, раздел
«## 1.0.7 — 2026-10-23»). Каталог emu/ удаляется в конце.
"""

import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOLVER = ROOT / "numerical_solver"
PLAN = next((ROOT / "vault" / "plans").glob("debt-087 *.md"))
EMU = HERE / "emu" / "numerical_solver"

plan = PLAN.read_text(encoding="utf-8")
blocks = [textwrap.dedent(b) for b in re.findall(r"```python\n(.*?)\n[ ]*```", plan, flags=re.S)]


def block(marker, nth=0):
    found = [b for b in blocks if marker in b]
    return found[nth]


def indent(text, n):
    return textwrap.indent(text, " " * n)


src = (SOLVER / "tests" / "test_packaging.py").read_text(encoding="utf-8")


def replace_once(text, old, new):
    assert text.count(old) == 1, f"фрагмент встречается {text.count(old)} раз:\n{old}"
    return text.replace(old, new)


# 1. Комментарий над константами: блоки «До»/«После» – первые два с «Проверяется только»
before1, after1 = [b for b in blocks if b.startswith("# Проверяется только текущий раздел")]
src = replace_once(src, before1, after1)
# 2. Комментарий CHANGELOG_EM_DASH
src = replace_once(src, "в тексте раздела запрещено", "в тексте раздела и шапки запрещено")
# 3. Константа после CHANGELOG_CODE_SPAN_RE
span = 'CHANGELOG_CODE_SPAN_RE = re.compile(r"`[^`]*`")\n'
src = replace_once(src, span, span + block("CHANGELOG_RELEASE_HEAD_RE = re.compile") + "\n")
# 4. Три функции перед _changelog_format_problems
head = "def _changelog_format_problems("
src = replace_once(src, head, block("def _changelog_header(") + "\n\n\n" + head)
# 5. Проверка знаков в цикле: «До» и «После» – блоки с «for n, line in enumerate(lines, 1):»
before5, after5 = [b for b in blocks if b.startswith("for n, line in enumerate(lines, 1):")]
src = replace_once(src, indent(before5, 4), indent(after5, 4))
# 6. Докстринг класса
src = replace_once(src, '"""Форма пунктов текущего раздела журнала (DEBT-086): её читает получатель выпуска на GitHub."""',
                   '"""Форма пунктов текущего раздела журнала (DEBT-086) и знаки шапки (DEBT-087): их читает получатель выпуска."""')
# 7. Два теста в конец класса (класс – последний в файле)
src = src.rstrip("\n") + "\n\n" + indent(block("def test_changelog_header_symbols"), 4) + "\n"

old_changelog = (SOLVER / "CHANGELOG.md").read_text(encoding="utf-8")
lines = old_changelog.splitlines()
start = lines.index("## Не выпущено")
new_changelog = (HERE / "header_new.md").read_text(encoding="utf-8") + "\n" + "\n".join(lines[start:]) + "\n"
init = (SOLVER / "gpn_multiphase_solver" / "__init__.py").read_text(encoding="utf-8")
tag_init = re.sub(r'__version__ = "[^"]+"', '__version__ = "1.0.7"', init)
tag_changelog = new_changelog.replace("\n## Не выпущено\n", "\n## 1.0.7 — 2026-10-23\n")


def run(name, changelog, init_text):
    if EMU.exists():
        shutil.rmtree(EMU)
    (EMU / "tests").mkdir(parents=True)
    (EMU / "gpn_multiphase_solver").mkdir()
    (EMU / "tests" / "test_packaging.py").write_text(src, encoding="utf-8")
    (EMU / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    (EMU / "gpn_multiphase_solver" / "__init__.py").write_text(init_text, encoding="utf-8")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/test_packaging.py", "-k", "changelog", "-q",
                        "-p", "no:cacheprovider", "--rootdir", str(EMU), "-c", os.devnull],
                       cwd=EMU, capture_output=True, text=True, encoding="utf-8", env=env)
    out = r.stdout.strip().splitlines()
    print(f"── {name}: {out[-1] if out else r.stderr[-500:]}")
    for s in out:
        if s.startswith(("FAILED", "E  ")) and "строка" in s or s.startswith("FAILED"):
            print("   ", s[:200])
    collect = subprocess.run([sys.executable, "-m", "pytest", "tests/test_packaging.py", "--collect-only", "-q",
                              "-p", "no:cacheprovider", "--rootdir", str(EMU), "-c", os.devnull],
                             cwd=EMU, capture_output=True, text=True, encoding="utf-8", env=env)
    print("   собрано:", collect.stdout.strip().splitlines()[-1])


run("старая шапка", old_changelog, init)
run("новая шапка", new_changelog, init)
run("новая шапка, дерево метки 1.0.7", tag_changelog, tag_init)
shutil.rmtree(HERE / "emu")
