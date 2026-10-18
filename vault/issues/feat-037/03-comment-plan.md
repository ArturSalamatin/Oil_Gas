### План готов

План: `vault/plans/feat-037 solver-version-changelog.md`. Ветка: `feat/feat-037/solver-version-changelog`. Шагов: 7. Модель: — (инфраструктура).

**Решения пользователя при планировании (2026-10-18):**
- запись версий в `output/` — в этой задаче: файл `versions.txt` и строка «Версии: …» в консоли третьей строкой;
- состав — `gpn-multiphase-solver`, `radial-blackoil`, Python, numpy, scipy;
- журнал между выпусками сводится при выпуске по истории git; здесь — правило номеров и раздел «Не выпущено» с записью этой задачи;
- `gpn-solver --version` — только номер решателя, без импорта решателя и прототипа.

**Шаги:** 1 — литерал `__version__ = "1.0.0.dev0"` + `dynamic` в `pyproject.toml`; 2 — `CHANGELOG.md`; 3 — `--version`; 4 — `versions.txt` и печать в `run_case`; 5 — README и README примеров; 6 — проверка номера в колесе; 7 — vault.

**Тесты:** 2288 → 2294 (+3 `test_packaging.py`, +3 `test_cli.py`); правятся `STANDARD_FILES` и `test_pipeline_writes_output`. Прототип не меняется.

**Проба плана** `vault/issues/feat-037/probes/plan_checks.py --apply-plan`: 22/22 ОК — `--version` при обязательной подкоманде выходит с кодом 0; колесо копии пакета — `gpn_multiphase_solver-1.0.0.dev0-py3-none-any.whl`. Найдено: `'1.0'` по PEP 440 — каноническая форма, поэтому тест правила проверяет ещё и три числа.

**Ловушка:** метаданные редактируемой установки отстают от литерала до `pip install -e` — тесты их не сверяют; в worktree `pip install -e` не запускать (общий venv).
