"""BUG-022, аудит раунд 2: исполнимость шагов 5–6 плана (тексты).

1. Таблица правок README шага 5 («файл:строка | было | стало»): для каждой строки — найдены
   ли числа и фразы «было» на указанных строках файла (±2) и сколько раз они встречаются
   во всём файле (> 1 — Edit по подстроке неоднозначен). С ключом --after — то же для «стало»
   (проверка после реализации шага 5).
2. Абзац «Сходимость Ньютона» шага 6: подставить в копию problem_statement.tex
   (probes/tex_check/) и собрать pdflatex — ошибки и предупреждения о символах.
Запуск (из numerical_solver проверяемого дерева):
    .venv\\Scripts\\python <путь>\\check_texts.py [--after] [--tex]
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOLVER = Path.cwd()
if not (SOLVER / "examples").is_dir():
    raise SystemExit(f"запускать из numerical_solver, сейчас {SOLVER}")
PLAN = ROOT / "vault" / "plans" / "bug-022 newton-cell-relative-tolerance.md"
text = PLAN.read_text(encoding="utf-8")
AFTER = "--after" in sys.argv

# ── 1. Таблица шага 5 ──
names = {p.name[:3].rstrip("_"): p for p in (SOLVER / "examples").iterdir() if p.is_dir() and p.name[:2].isdigit()}
names.update({p.name[:3]: p for p in (SOLVER / "examples").iterdir() if p.is_dir() and p.name[:3] in ("04a", "13a", "13b")})
step5 = text.split("### Шаг 5:")[1].split("### Шаг 6:")[0]
rows = re.findall(r"^\| ((?:\d\d\w?|сводный):[\d\-]+) \| (.*?) \| (.*?) \|$", step5, re.M)
MATH = re.compile(r"\$[^$]+\$")
bad = 0
for loc, was, now in rows:
    key, lines = loc.split(":")
    path = (SOLVER / "examples" / "README.md") if key == "сводный" else names[key] / "README.md"
    src = path.read_text(encoding="utf-8").splitlines()
    a, b = (int(x) for x in (lines.split("-") + [lines])[:2])
    window = "\n".join(src[max(a - 3, 0):b + 2])
    cell = now if AFTER else was
    frags = (re.findall(r"`([^`]+)`", cell) or MATH.findall(cell) or re.findall(r"«([^»]+)»", cell)
             or [c.strip() for c in cell.split("\\|")])
    frags = [f.replace("\\|", "|") for f in frags if f.strip() and "строки ниже" not in f and "таблица ниже" not in f
             and "текст ниже" not in f]
    full = "\n".join(src)
    report = []
    for f in frags:
        probe = " ".join(f.split())
        on_line = probe in " ".join(window.split())
        count = " ".join(full.split()).count(probe)
        report.append(f"{'✓' if on_line else '✗'} {f[:40]!r} ×{count}")
        if not on_line:
            bad += 1
    if report:
        print(f"{loc:<14} " + "; ".join(report))
print(f"строк таблицы {len(rows)}; не найдено на указанных строках: {bad}")

# ── 2. LaTeX шага 6 ──
if "--tex" in sys.argv:
    blk = re.search(r"```latex\n(.*?)^   ```", text, re.S | re.M).group(1)
    new_par = "\n".join(l[3:] if l.startswith("   ") else l for l in blk.split("\n")).rstrip() + "\n"
    tex = (SOLVER / "doc" / "problem_statement.tex").read_text(encoding="utf-8")
    start = tex.index("\\paragraph{Сходимость Ньютона.}")
    end = tex.index("\\paragraph{Контроль физичности:}")
    out_dir = HERE / "tex_check"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir()
    (out_dir / "problem_statement.tex").write_text(tex[:start] + new_par + "\n" + tex[end:], encoding="utf-8")
    for _ in range(2):
        r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "problem_statement.tex"], cwd=out_dir,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = (out_dir / "problem_statement.log").read_text(encoding="utf-8", errors="replace")
    errs = [l for l in log.splitlines() if l.startswith("!") or "not set up" in l or "Undefined" in l]
    print(f"pdflatex: код {r.returncode}; строк с ошибками {len(errs)}")
    for l in errs[:10]:
        print("   ", l)
    print("метка eq:newton_cell_tol в .aux:", "eq:newton_cell_tol" in (out_dir / "problem_statement.aux").read_text(
        encoding="utf-8", errors="replace"))
