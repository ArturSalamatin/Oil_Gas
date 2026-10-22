"""DEBT-015, аудит: истории примеров и сквозной останов на коде плана (plan_code — подмена).

Запуск из numerical_solver:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-015\\probes\\plan_code_check.py
Сравнение историй — с history_base (штатный код cf86aa2, снят при планировании):
history_base_plan; ожидание «различий 0». Останов 20B при 1 сут — ожидание 348/187,
сценарий rs150 без ступени 4 — 185.3065 бар, 70/34.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import plan_code  # noqa: E402,F401  — подмена до импорта пробы (ORIG_ADVANCE = код плана)
import local_subdiv  # noqa: E402

names = sorted(d.name for d in (Path.cwd() / "examples").iterdir()
               if (d / "config.json").is_file())
local_subdiv.run_examples("base:plan", names)
local_subdiv.compare("base", "base:plan")
local_subdiv.run_shutin("20", "B", 86400.0, "base", None, 900.0)
local_subdiv.run_case("tests/data/bug020_rs150/config.json", "base", 0)
