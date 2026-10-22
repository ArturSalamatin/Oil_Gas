"""Строки ```python-блоков плана DEBT-063: длина ≤ 100, правила сторожа DEBT-010, блоки «До».

Запуск из numerical_solver/:  python ..\\vault\\issues\\debt-063\\probes\\plan_lines_check.py
FORBIDDEN, LABEL_REF, LABEL_DEF — из tests/test_eq_references.py; метки —
из .tex и ```latex-блоков плана. Блок «До» — ```python-блок, найденный в
одном из файлов задачи; ожидание — каждый ровно один раз.
"""
import re
import sys
from pathlib import Path

SOLVER = Path.cwd()
print("solver:", SOLVER)
sys.path.insert(0, str(SOLVER / "tests"))
from test_eq_references import FORBIDDEN, LABEL_DEF, LABEL_REF  # noqa: E402

PLAN = SOLVER.parent / "vault" / "plans" / "debt-063 unify-grid-prototype-centers.md"
text = PLAN.read_text(encoding="utf-8")
blocks = re.findall(r"```(\w+)\n(.*?)```", text, flags=re.S)

labels = set(LABEL_DEF.findall((SOLVER / "doc" / "problem_statement.tex")
                               .read_text(encoding="utf-8")))
for lang, body in blocks:
    if lang == "latex":
        labels |= set(LABEL_DEF.findall(body))

bad = 0
py = [ln for lang, body in blocks if lang == "python" for ln in body.splitlines()]
for ln in py:
    if len(ln) > 100:
        bad += 1
        print(f"ДЛИННАЯ {len(ln)}: {ln}")
    for what, rx in FORBIDDEN.items():
        if rx.search(ln):
            bad += 1
            print(f"ЗАПРЕТ {what}: {ln}")
    for m in LABEL_REF.finditer(ln):
        if m.group() not in labels:
            bad += 1
            print(f"НЕТ МЕТКИ {m.group()}: {ln}")
print(f"python-строк: {len(py)}, максимум {max(map(len, py))} симв., нарушений: {bad}")

TARGETS = ["gpn_multiphase_solver/grid/log_radial.py", "tests/test_grid.py",
           "tests/test_prototype_adapter.py", "tests/test_val001.py",
           "tests/test_factory_standing_hydro.py"]
src = {t: (SOLVER / t).read_text(encoding="utf-8") for t in TARGETS}
found = 0
for lang, body in blocks:
    if lang != "python":
        continue
    hits = {t: s.count(body) for t, s in src.items() if body in s}
    if hits:
        found += 1
        print(f"До: {hits} — {body.strip().splitlines()[0][:60]}")
print(f"блоков «До» найдено: {found}")
