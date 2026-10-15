## Реализация завершена

**Ветка:** `refactor/debt-071/standing-relperm-range-check` (worktree `.worktrees/debt-071`, от `numerical_scheme/implementation` `eddebfd`)
**План:** `vault/plans/debt-071 standing-relperm-range-check.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-071/standing-relperm-range-check`

### Изменения
- `radial_blackoil/diagnostics.py` (прототип): новая `relperm_range_warnings(model, state)` — две категории ОФП, читает только `model.relperm` и `state.sg`; `pvt_range_warnings` зовёт её последней — тексты и порядок прежние.
- `tests/test_pvt_clamp.py` (прототип): +2 теста; `CHANGELOG_1.0.3.md` — раздел DEBT-071.
- `hydro/prototype_adapter.py`: параметр `table_pvt`; при `False` (PVT Стендинга) `warn_table_range` зовёт только `relperm_range_warnings`.
- `factory.py`: `check_table_range=True` всегда, `table_pvt=isinstance(pvt, TableFullPVT)`; комментарии.
- `pvt/hydro_to_blackoil_adapter.py`: устаревший комментарий о диагностике исправлен.
- `tests/test_table_range_warnings.py`: класс `TestStandingRelperm` (5 тестов), удалён `test_standing_path_not_checked`; `tests/test_factory_standing_hydro.py` — докстринг.

### Тесты
- Было: 1987 тестов GPN, прототип 107
- Стало: 1991 (+5, −1), прототип 109 (+2)
- Все зелёные: ✅ — полный прогон 1991 passed, быстрый уровень 1715 passed; прототип 109 passed, регрессия `--quick` 11/11 и полная 17/17 PASS побитово

### Проверки
| Что | Результат |
|---|---|
| Отпечатки историй 23 примеров | побитово как на базе (шаг 0) |
| Журнал 23 примеров | 3 записи «вне таблиц» — только 04a, у 8 примеров Стендинга 0 — построчно как эмуляция плана |
| 05 с таблицей ОФП до $S_g$ = 0.01 | запись «RELPERM Sg above table: max Sg=0.917, table max=0.01» при 0.000651 сут, затем отказ первого часа (DEBT-073, #123) |
| 05 с таблицей с $S_g$ = 0.05 | одна запись при $t = 0$, дальше не повторяется |
| Длительность журнала 23 примеров | 131.3 → 132.5 с (+0.9 %) |
