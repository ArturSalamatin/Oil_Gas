"""Сборка problem_statement.tex с правкой шага 1 плана DEBT-060 — на копии.

Запуск из numerical_solver/:  python ..\\vault\\issues\\debt-060\\probes\\tex_check.py
Копия и выходы сборки — в probes/tex_check/ (каталог удалить после проверки).
Берёт блоки «До»/«После» шага 1 из плана, три прохода pdflatex, счёт ошибок,
неопределённых ссылок, Overfull; печатает номера и страницы меток центра.
"""
import re
import subprocess
from pathlib import Path

SOLVER = Path.cwd()
print("solver:", SOLVER)
PLAN = SOLVER.parent / "vault" / "plans" / "debt-060 cell-center-name.md"
OUT = Path(__file__).resolve().parent / "tex_check"
OUT.mkdir(exist_ok=True)

latex = re.findall(r"```latex\n(.*?)```", PLAN.read_text(encoding="utf-8"), flags=re.S)
old, new = latex[0], latex[1]
src = (SOLVER / "doc" / "problem_statement.tex").read_text(encoding="utf-8")
assert src.count(old) == 1, "блок «До» шага 1 не найден в .tex однозначно"
(OUT / "problem_statement.tex").write_text(src.replace(old, new), encoding="utf-8")

for _ in range(3):
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                    "problem_statement.tex"], cwd=OUT, capture_output=True)
log = (OUT / "problem_statement.log").read_text(encoding="utf-8", errors="replace")
aux = (OUT / "problem_statement.aux").read_text(encoding="utf-8", errors="replace")
print("errors:", len(re.findall(r"^!", log, flags=re.M)))
print("undefined:", log.count("undefined"))
print("overfull:", log.count("Overfull"))
print(re.search(r"Output written.*", log).group())
for lab in ("eq:log_grid", "eq:cell_center_def", "eq:cell_center", "eq:volume"):
    m = re.search(r"\\newlabel\{" + re.escape(lab) + r"\}\{\{(\d+)\}\{(\d+)\}", aux)
    print(f"{lab}: ур. {m.group(1)}, с. {m.group(2)}")
