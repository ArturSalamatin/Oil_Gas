## Реализация завершена

**Ветка:** `fix/bug-017/rs0-table-range-check` (от `numerical_scheme/implementation`, `4bd1e8c`)
**План:** `vault/plans/bug-017 rs0-table-range-check.md`
**Коммиты:**
```
vault: BUG-017 — реализован: реестр, схема конфига, P8, заметка
docs: README табличных примеров — Rs0 выше таблицы не загрузится (BUG-017)
fix: BUG-017 — проверка начального состояния против PVT в фабрике
vault: BUG-017 начало реализации
```

### Изменения
- `numerical_solver/gpn_multiphase_solver/factory.py`:
  - `Rs0` вне диапазона веток PVTO → `ValueError` (`_check_rs0_in_table`, в `_create_pvt`);
  - пересыщенный старт $R_{s,0} > R_s^{eq}(p_0) + 10^{-5}$ → `ValueError` с $p_b(R_{s,0})$, обе модели PVT (`_check_undersaturated_start`);
  - табличный путь: `pvt_range_warnings` прототипа для начального состояния → журнал (`_warn_initial_table_range`).
- `numerical_solver/tests/test_factory_prototype.py` (+10), `numerical_solver/tests/test_factory_standing_hydro.py` (+4).
- README 04, 11, 12, 13a, 13b, 15 — `Rs0` выше последней ветки таблицы не загрузится.
- vault: `json-config-schema.md` (`Rs0` обязателен, ограничения), P8 §5, реестр, заметка `пересыщенный старт решатель молча уравновешивает скачком давления`.

Код решателя и прототипа не менялся.

### Проверка
- Воспроизведение (пример 12, `Rs0 = 150`): было `RuntimeError … Увеличьте numerics.max_retries`, стало `ValueError: Rs0 = 150 м³ст/м³ст вне диапазона таблицы oil_pvt.csv …` из `from_config`.
- Все 20 конфигов проекта загружаются без ошибок и `[WARNING]`.

### Тесты
- Было: 1035 (все зелёные)
- Стало: 1049 (+14 новых; до правки 6 из них красные)
- Все зелёные: ✅
