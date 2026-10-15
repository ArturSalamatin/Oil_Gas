## Реализация завершена

**Ветка:** `refactor/debt-073/relperm-mobile-oil-edge` (worktree `.worktrees/debt-073`, от `numerical_scheme/implementation` `dd7f155`)
**План:** `vault/plans/debt-073 relperm-mobile-oil-edge.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-073/relperm-mobile-oil-edge`

### Изменения
- `numerical_solver/gpn_multiphase_solver/factory.py`:
  - `_check_relperm_table(Sg, kro, relperm_file)` — новая проверка `kro[-1] > 0` → `ValueError`. Она идёт последней, после проверок числа строк и роста $S_g$, поэтому прежние тексты на пустой таблице и на таблице из одной строки не изменились. Сравнение строгое. Текст отказа: файл, $S_g$ и $k_{ro}$ последней строки, следствие («нефть подвижна при любой S_o») и требование «таблица кончается строкой с k_ro = 0 — при S_g = 1 − S_or или выше».
  - `create_relperm` передаёт `kro`.
- `numerical_solver/tests/test_factory_prototype.py` — в `TestCSVValueChecks` три теста: `test_relperm_mobile_oil_at_edge_raises`, `test_relperm_rounding_noise_at_edge_raises` ($10^{-30}$ — тоже отказ), `test_project_relperm_tables_accepted` (все 16 таблиц проекта проходят).
- `numerical_solver/tests/test_table_range_warnings.py` — тест DEBT-071 `test_relperm_above_table_before_failure` заменён на `test_mobile_oil_edge_rejected_before_run`: таблица до 0.01 теперь отвергается в `from_config`. Константа `RELPERM_ABOVE` удалена.
- `numerical_solver/examples/04_table_table/README.md`, `05_standing_table_rp/README.md`, `vault/knowledge/decisions/P8-формат-ввода-json.md` — правило последней строки.
- Заметка: `vault/knowledge/debugging/таблица ОФП с k_ro больше нуля в последней строке даёт корень с S_o меньше нуля — дробление шага не помогает.md`.

### Тесты
- Было: 1993 теста, быстрый уровень 1717.
- Стало: 1996 (+3), быстрый уровень 1720.
- Полный прогон: 1996 passed за 579 с на `2c70cf6` ✅
- Прототип не менялся, истории примеров прежние: меняется только проверка ввода, а все таблицы проекта её проходят.
