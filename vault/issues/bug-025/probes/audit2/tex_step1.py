"""BUG-025, аудит 2: шаг 1 плана на копии постановки — блок «До» найден дословно, «После» собирается.

Копия problem_statement.tex с заменой «До → После» из шага 1 плана пишется сюда как
problem_statement_step1.tex; затем (PowerShell, из этого каталога):
    pdflatex -interaction=nonstopmode problem_statement_step1.tex   # дважды
Рабочий файл numerical_solver/doc/problem_statement.tex не меняется. Выходы pdflatex
(.aux, .log, .pdf, .toc, .out) — удалить после разбора.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3].parent
plan = (HERE.parents[3] / "plans" / "bug-025 short-step-residual-floor.md").read_text(encoding="utf-8")
step1 = plan[plan.index("### Шаг 1:"):plan.index("### Шаг 2:")]
before, after = re.findall(r"```latex\n(.*?)\n```", step1, re.S)[:2]
tex = (ROOT / "numerical_solver" / "doc" / "problem_statement.tex").read_text(encoding="utf-8")
n = tex.count(before)
print(f"блок «До» найден в постановке: {n} раз")
assert n == 1
(HERE / "problem_statement_step1.tex").write_text(tex.replace(before, after), encoding="utf-8")
print("problem_statement_step1.tex записан")
