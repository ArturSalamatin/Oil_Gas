"""Код шага 2 плана DEBT-046 совпадает с прогнанной пробой test_plan_debt046.py.

Допустимые отличия: строка EXAMPLES_DIR (с комментарием «ПРОБА») и абзац
docstring «ПРОБА ПЛАНА…». Запуск из любого каталога:
    python vault\\issues\\debt-046\\probes\\plan_code_check.py
"""
import difflib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE.parents[2] / "plans" / "debt-046 examples-scripts-import-check.md"
PROBE = HERE / "test_plan_debt046.py"

text = PLAN.read_text(encoding="utf-8")
start = text.index('```python\n"""Имена, которые скрипты') + len("```python\n")
end = text.index("\n```", start)
plan_code = text[start:end + 1].splitlines()
probe_code = PROBE.read_text(encoding="utf-8").splitlines()

diff = [d for d in difflib.unified_diff(probe_code, plan_code, "проба", "план",
                                        lineterm="", n=0)]
print("\n".join(diff) if diff else "совпадают полностью")
