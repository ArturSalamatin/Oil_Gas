### План готов

План: `vault/plans/feat-036 run-from-workbook.md`. Ветка: `feat/feat-036/run-from-workbook`. Шагов: 6. Модель: — (инфраструктура).

**Решения пользователя при планировании (2026-10-18):**

- **Каталог вывода у книги очищается до перевода** (вариант Г): правило FEAT-030 «очистка после расчёта» для расчёта по книге отменено. При ошибке конфига или отказе решателя прежних результатов нет, в каталоге остаётся `input/` — вход, на котором расчёт остановился. Умолчание плана: перевод в памяти до очистки, поэтому книга с ошибкой каталог не трогает.
- **Книгу принимает `run_case`** (вход по расширению `.xlsx`, `.xlsm`, `.xls`, `.xlsb` без учёта регистра): команда и Python одинаковы; печать «Книга: …», ошибки называют книгу.
- **Пример 22 — в общем списке тестов примеров**: книга переводится во временный каталог сессии, идут все общие проверки.
- **Книга примера — `22_workbook_input.xlsx`** (шаблон `gpn-solver template`).

**Шаги:** 1 — `run_case` и `_translate_workbook` (`report/pipeline.py`) + `tests/test_workbook_run.py`; 2 — командная строка; 3 — строка «Run» листа COMMENTS, пересоздание `configs/INPUT_TEMPLATE_v1.xlsx`; 4 — пример 22, `tests/test_examples.py`, сверка матрицы энергии (`tests/test_energy_matrix_examples.py`), `examples/check_energy_balance_all.py`; 5 — README пакета §3.6, `examples/README.md`, `CHANGELOG.md`, `CLAUDE.md`; 6 — vault.

**Тесты:** 2421 → 2459 (+38: 30 быстрых, 8 `slow`).

**Проверка плана на копии дерева** (`vault/issues/feat-036/probes/plan_apply.py`): быстрый уровень — 2152 passed; 12 порч кода — каждую ловит тест; `tests/test_examples.py` целиком — 487 passed; пример 22 — код 0, ~23 с, $T(r_w)$ = 350.105 К на 30 сут, баланс энергии $5.5\cdot10^{-15}$.

**Найдено при планировании:** `tests/test_energy_matrix_examples.py` и `examples/check_energy_balance_all.py` ищут примеры по `config.json` — первая проба уронила `test_coverage_matches_disk`; учтено в шаге 4. Новых задач нет.
