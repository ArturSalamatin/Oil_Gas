"""Строки ```python-блоков плана DEBT-060: длина ≤ 100 и правила сторожа DEBT-010.

Запуск из numerical_solver/:  python ..\\vault\\issues\\debt-060\\probes\\plan_lines_check.py
Берёт FORBIDDEN, LABEL_REF, LABEL_DEF из tests/test_eq_references.py; метки
считает объявленными, если они есть в .tex или в ```latex-блоках плана (шаг 1).
"""
import re
import sys
from pathlib import Path

SOLVER = Path.cwd()
print("solver:", SOLVER)
sys.path.insert(0, str(SOLVER / "tests"))
from test_eq_references import FORBIDDEN, LABEL_DEF, LABEL_REF  # noqa: E402

PLAN = SOLVER.parent / "vault" / "plans" / "debt-060 cell-center-name.md"
text = PLAN.read_text(encoding="utf-8")
blocks = re.findall(r"```(\w+)\n(.*?)```", text, flags=re.S)

labels = set(LABEL_DEF.findall((SOLVER / "doc" / "problem_statement.tex")
                               .read_text(encoding="utf-8")))
for lang, body in blocks:
    if lang == "latex":
        labels |= set(LABEL_DEF.findall(body))

bad = 0
py_lines = [ln for lang, body in blocks if lang == "python" for ln in body.splitlines()]
for ln in py_lines:
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
print(f"python-строк: {len(py_lines)}, максимум {max(map(len, py_lines))} симв., "
      f"нарушений: {bad}")

# Блоки «До»: ```python-блок, дословно (ровно один раз) найденный в файлах задачи.
TARGETS = ["gpn_multiphase_solver/grid/log_radial.py", "tests/test_grid.py",
           "tests/test_prototype_adapter.py", "tests/test_val001.py"]
sources = {t: (SOLVER / t).read_text(encoding="utf-8") for t in TARGETS}
found = 0
for lang, body in blocks:
    if lang != "python":
        continue
    hits = {t: s.count(body) for t, s in sources.items() if body in s}
    if hits:
        found += 1
        first = body.splitlines()[0].strip()
        print(f"До найден: {hits} — {first[:60]}")
print(f"блоков «До» найдено: {found} (ожидание 7, каждый — 1 раз)")
