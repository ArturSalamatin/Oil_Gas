"""DEBT-027: извлечь код тестов шага 2 (п. 9) из плана в emu_tests/test_table_range_warnings.py.

Блок ```python после строки «`tests/test_table_range_warnings.py` — новый файл:», отступ 3 пробела снят.
Запуск из корня проекта: numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-027\\probes\\extract_plan_tests.py
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
plan = (HERE.parents[2] / "plans" / "debt-027 table-range-diagnostics.md").read_text(encoding="utf-8")
start = plan.index("`tests/test_table_range_warnings.py` — новый файл:")
body = plan[start:].split("```python\n", 1)[1].split("\n   ```", 1)[0]
lines = [ln[3:] if ln.startswith("   ") else ln for ln in body.splitlines()]
# Копия лежит не в numerical_solver/tests: ROOT — каталог запуска (numerical_solver/)
assert "ROOT = Path(__file__).parent.parent" in lines
lines[lines.index("ROOT = Path(__file__).parent.parent")] = "ROOT = Path.cwd()"
out = HERE / "emu_tests" / "test_table_range_warnings.py"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{out}: {len(lines)} строк")
