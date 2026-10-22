"""Проба DEBT-086, шаг 3 плана: образец пункта в /implement 4.1 проходит проверку формы шага 2.

Запуск: numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-086\\probes\\p5_sample_check.py <корень дерева>
Образец – блок ```markdown после «**Образец:**» в <корень>/.claude/commands/implement.md (отступ 3 пробела
снимается); проверка – _changelog_format_problems из <корень>/numerical_solver/tests/test_packaging.py.
Ожидание: «нарушений нет».
"""

import importlib.util
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    sys.exit(__doc__)
TREE = Path(sys.argv[1]).resolve()
cmd = TREE / ".claude" / "commands" / "implement.md"
tests = TREE / "numerical_solver" / "tests" / "test_packaging.py"
print("команда:", cmd)
print("тест:   ", tests)

spec = importlib.util.spec_from_file_location("test_packaging", tests)
tp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tp)
if not hasattr(tp, "_changelog_format_problems"):
    sys.exit("в test_packaging.py нет _changelog_format_problems – дерево до шага 2")

m = re.search(r"\*\*Образец:\*\*\n   ```markdown\n(.*?)\n   ```", cmd.read_text(encoding="utf-8"), re.S)
if m is None:
    sys.exit("в 4.1 нет блока «**Образец:**» – дерево до шага 3")
lines = [s[3:] if s.startswith("   ") else s for s in m[1].splitlines()]
problems = tp._changelog_format_problems(["### Добавлено", ""] + lines)
print(f"строк образца: {len(lines)};", problems or "нарушений нет")
