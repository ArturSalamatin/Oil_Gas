"""Проба DEBT-086, шаг 4 плана: описание выпуска из журнала дерева <корень> – отрисовка GitHub (gh api markdown, gfm).

Запуск: numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-086\\probes\\p4_verify_tree.py <корень дерева>
<корень дерева> – worktree задачи (.worktrees\\debt-086) или основной каталог. release.py берётся из
<корень>/tools, журнал – из <корень>/numerical_solver; оба пути печатаются (в worktree легко взять базу).
Ожидание после задачи: в «Не выпущено» – <br> 0, у каждого пункта <strong>номер</strong>, <em>Было.</em>,
<em>Стало.</em>; release_notes на копии журнала с «Не выпущено» → «## 9.9.9 — …» даёт тот же текст.
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 2:
    sys.exit(__doc__)
TREE = Path(sys.argv[1]).resolve()
OUT = Path(__file__).resolve().parent / "out_p4"
OUT.mkdir(exist_ok=True)

spec = importlib.util.spec_from_file_location("release", TREE / "tools" / "release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
changelog = TREE / "numerical_solver" / "CHANGELOG.md"
print("release.py:", spec.origin)
print("журнал:    ", changelog)
if not hasattr(release, "release_notes"):
    sys.exit("в этом release.py нет release_notes – дерево до DEBT-086")

text = release.read_text(changelog)
# Выпуск переименует «Не выпущено» в «## X.Y.Z — дата» – так же, как changelog_release
notes = release.release_notes(release.changelog_release(text, "9.9.9", "2026-01-01"), "9.9.9")
(OUT / "notes.md").write_text(notes, encoding="utf-8")
r = subprocess.run(["gh", "api", "markdown", "-f", "mode=gfm", "-f", "context=ArturSalamatin/Oil_Gas",
                    "-F", f"text=@{OUT / 'notes.md'}"], capture_output=True, text=True, encoding="utf-8")
if r.returncode != 0:
    sys.exit(f"gh api markdown: {r.stderr}")
html = r.stdout
(OUT / "notes.html").write_text(html, encoding="utf-8")

items = re.findall(r"^- \*\*([^*]+)\.\*\*", release.section_body(text, release.UNRELEASED), re.M)
print("пункты «Не выпущено»:", items)
print("<br>:", html.count("<br>"))
for name in items:
    print(f"  {name}: <strong> {html.count(f'<strong>{name}.</strong>')}")
print("<em>Было.</em>:", html.count("<em>Было.</em>"), "| <em>Стало.</em>:", html.count("<em>Стало.</em>"),
      "| <em>Числа.</em>:", html.count("<em>Числа.</em>"))
print("HTML:", OUT / "notes.html")
