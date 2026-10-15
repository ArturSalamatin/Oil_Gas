### План готов

План: `vault/plans/debt-073 relperm-mobile-oil-edge.md`. Ветка: `refactor/debt-073/relperm-mobile-oil-edge`. Шагов: 3. База: `0d5c491` (после влития DEBT-071).

- **Шаг 1.** `_check_relperm_table(Sg, kro, relperm_file)` — `ValueError` при `kro[-1] > 0`. Сравнение строгое (решение пользователя 2026-10-15: шум округления — тоже отказ). Проверка идёт последней, после числа строк и роста $S_g$: так сохраняются прежние тексты на пустой таблице и таблице из одной строки. Новых тестов три: подвижная нефть на краю, шум $10^{-30}$, все 16 таблиц проекта проходят. Тест DEBT-071 `test_relperm_above_table_before_failure` заменён на `test_mobile_oil_edge_rejected_before_run` — отказ фабрики на той же таблице.
- **Шаг 2.** Правило в `examples/04_table_table/README.md`, `examples/05_standing_table_rp/README.md`, `vault/knowledge/decisions/P8-формат-ввода-json.md`.
- **Шаг 3.** vault.

**Почему тест DEBT-071 заменяется, а не переносится на допустимую таблицу.** Проба `vault/issues/debt-073/probes/edge_zero_scan.py`: пример 05 с таблицами, у которых последняя строка $k_{ro} = 0$ при $S_g$ = 0.01–0.1, сходится, и max $S_g$ = 0.006–0.012 — ниже края. Узел $k_{ro} = 0$ держит $S_g$ внутри таблицы, сценарий «запись вне таблиц, затем отказ» не воспроизводится. Текст записи и вызов проверки после каждого шага по-прежнему проверяют `test_relperm_above_table_reported_alone` и `test_checked_after_every_accepted_step`.

**Эмуляция.** Код шага 1 в памяти на `0d5c491`: 8 PASS (`plan_tests_emulate.out.txt`). Тестов 1993 → 1996, быстрый уровень 1717 → 1720. Прототип не меняется, истории примеров прежние.

Лист RELPERM шаблона книги Excel (FEAT-033, `INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx`) кончается строкой `0.85, 0, 0.8` и проверку проходит.
