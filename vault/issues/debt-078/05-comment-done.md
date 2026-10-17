## Реализация завершена

**Ветка:** `refactor/debt-078/co-undersaturated-table-check` (worktree `.worktrees/debt-078`, от `numerical_scheme/implementation` `8028420`)
**План:** `vault/plans/debt-078 co-undersaturated-table-check.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-078/co-undersaturated-table-check`

### Изменения
- `numerical_solver/gpn_multiphase_solver/factory.py`: `create_pvt`, ветвь `"table"` — `ValueError` при `co_undersaturated ≠ 0`, рядом с проверкой `mu_o_undersaturated` (FEAT-027). Явный 0 проходит (неотличим от умолчания).
- `numerical_solver/gpn_multiphase_solver/io/config.py`: `_validate` — `ValueError` при `co_undersaturated < 0` при любой модели PVT, в блоке «PVT» DEBT-076 после проверки плотностей; заголовок блока называет обе задачи; комментарий у полей Стендинга в `PVTConfig`.
- `numerical_solver/tests/test_factory_standing_hydro.py`: `test_co_with_table_raises`.
- `numerical_solver/tests/test_config.py`: класс `TestValidationOilCompressibility` — отказ при $c_o$ = −1e-9, −3.3e-9, −5e-324 и при табличной модели; приём 0 и 3.3e-9.
- Документы: P8 (§2 — поля Стендинга при таблице; §5 — `co_undersaturated` ≥ 0 в группе «PVT (…)», строка `create_pvt` с отказами FEAT-027 и DEBT-078, абзац о $c_o$), `json-config-schema.md`, `pvt-корреляции-стендинг.md`; `numerical_solver/README.md` п. 3.1 — в основном каталоге (файл вне git).

Прототип и предупреждение `_warn_negative_compressibility` (BUG-019) не менялись: для табличных данных отрицательная сжимаемость по-прежнему — предупреждение.

### Тесты
- Было: 2129 тестов (быстрый уровень 1853)
- Стало: 2136 тестов (+7 новых), быстрый уровень 1860
- Все зелёные: ✅ — быстрый уровень после каждого шага, полный прогон 2136 passed (597 с, на `1953006`)

### Проверка поведения
Проба `vault/issues/debt-078/probes/co_after.py` на коде ветки (`co_after.out.txt`):

| Случай | До | После |
|---|---|---|
| пример 04 (таблица), $c_o = 3.3\cdot10^{-9}$ | молча, $B_o$ побитово как при $c_o = 0$ | `ValueError` в `create_pvt`: «co_undersaturated = 3.3e-09 1/Па — только для model = 'standing' …» |
| пример 04, $c_o = 0$ | — | без отказа |
| пример 03 (Стендинг), $c_o = -10^{-9}$ | предупреждение BUG-019; расчёт молча при шаге 3600 / 1800 с, отказ при 900 с | `ValueError` в `load_config`: «pvt.co_undersaturated = -1e-09 1/Па < 0 …» |
| пример 04 (таблица), $c_o = -10^{-9}$ | — | `ValueError` в `load_config` с тем же сообщением о знаке |
