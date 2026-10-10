## Реализация завершена

**Ветка:** `refactor/debt-006/factory-explicit-proto-access` (worktree `.worktrees/debt-006`, от `numerical_scheme/implementation` `a26706a`)
**План:** `vault/plans/debt-006 factory-explicit-proto-access.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-006/factory-explicit-proto-access`

### Изменения
- `gpn_multiphase_solver/pvt/prototype_adapter.py`: свойства только для чтения `PrototypePVTAdapter.proto_pvt`, `PrototypeRPAdapter.proto_rp`.
- `gpn_multiphase_solver/pvt/table_full.py`: свойство только для чтения `TableFullPVT.hydro`.
- `gpn_multiphase_solver/factory.py`: `_get_or_create_proto_pvt` и `_get_or_create_proto_rp` выбирают ветку по `isinstance(pvt, TableFullPVT)` и `isinstance(relperm, PrototypeRPAdapter)` и берут объект через свойства. `PrototypeHydroAdapter` получает сам `FullPVT` — тот же объект, что решатель энергии и `Simulator`. `hasattr`/`getattr` в фабрике не осталось.
- `gpn_multiphase_solver/hydro/prototype_adapter.py`: исправлен докстринг конструктора (параметр `pvt`).
- `examples/pvt_plot.py`, `examples/relperm_plot.py`: узлы таблиц ищутся по классу модели и публичным свойствам, а не через `getattr` по приватным полям.
- `tests/`: `TestWrapperAccess` (4), `TestBranchByClass` (2), стражи тождества для табличной PVT и ОФП (2), `test_standing_pvt_shared` (1), `TestTableNodesByClass` (3). Тест без утверждений `test_relperm_is_prototype_adapter` заменён на `test_prototype_relperm_from_csv`: прототип получает 6 узлов CSV и порог активации газа 0.6, а не 101 узел и 0.79. Тесты `TestPVTConsistency` переведены с приватных полей на свойства и проверяют, что адаптер, энергия и `Simulator` держат один объект `FullPVT`.
- vault: заметки `согласованность-pvt-hydro.md` (новый раздел о том, как фабрика получает объекты прототипа) и `P1-адаптер-единицы.md` (решение раздела 4 приведено в соответствие с кодом).

### Тесты
- Было: 1638 тестов (база `a26706a`, после влития BUG-022 и DEBT-056)
- Стало: 1650 тестов (+12 новых, все быстрого уровня; 7 тестов красные до своей правки)
- Все зелёные: ✅ (полный прогон 565 с; быстрый уровень 1399 passed)

### Неизменность чисел
| Пример | Путь фабрики | Отпечаток SHA-256 истории до → после |
|---|---|---|
| 03_standing_corey | Стендинг × Кори | `14050af4…` → совпал |
| 04_table_table | таблица × таблица | `6cffa254…` → совпал |
| 05_standing_table_rp | Стендинг × таблица ОФП | `99e1b1e5…` → совпал |

Проба: `vault/issues/debt-006/probes/history_fingerprint.py`. Выводы — `fingerprint_before.out.txt`, `fingerprint_after.out.txt`.
