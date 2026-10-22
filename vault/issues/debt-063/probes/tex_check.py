"""DEBT-063, проба: сборка problem_statement.tex — база и с правкой шага 1 плана.

Запуск из numerical_solver/:  python ..\\vault\\issues\\debt-063\\probes\\tex_check.py
Копии и выходы сборки — в probes/tex_check/{base,step1}/ (удалить после
проверки). Блоки «До»/«После» шага 1 — первые два ```latex-блока плана.
Три прохода pdflatex; печать ошибок, неопределённых ссылок, Overfull,
числа страниц, номеров и страниц меток раздела «Радиальная сетка».
"""
import re
import subprocess
from pathlib import Path

SOLVER = Path.cwd()
print("solver:", SOLVER)
PLAN = SOLVER.parent / "vault" / "plans" / "debt-063 unify-grid-prototype-centers.md"
OUT = Path(__file__).resolve().parent / "tex_check"

latex = re.findall(r"```latex\n(.*?)```", PLAN.read_text(encoding="utf-8"), flags=re.S)
old, new = latex[0], latex[1]
src = (SOLVER / "doc" / "problem_statement.tex").read_text(encoding="utf-8")
assert src.count(old) == 1, "блок «До» шага 1 не найден в .tex однозначно"

for name, text in (("base", src), ("step1", src.replace(old, new))):
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "problem_statement.tex").write_text(text, encoding="utf-8")
    for _ in range(3):
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                        "problem_statement.tex"], cwd=d, capture_output=True)
    log = (d / "problem_statement.log").read_text(encoding="utf-8", errors="replace")
    aux = (d / "problem_statement.aux").read_text(encoding="utf-8", errors="replace")
    print(f"\n[{name}] errors: {len(re.findall(r'^!', log, flags=re.M))}, "
          f"undefined: {log.count('undefined')}, overfull: {log.count('Overfull')}")
    print("  " + re.search(r"Output written.*", log).group())
    for lab in ("eq:log_grid", "eq:cell_center", "eq:volume", "eq:face_interp"):
        m = re.search(r"\\newlabel\{" + re.escape(lab) + r"\}\{\{(\d+)\}\{(\d+)\}", aux)
        print(f"  {lab}: ур. {m.group(1)}, с. {m.group(2)}")
