## Реализация завершена

**Ветка:** `refactor/debt-079/relperm-immobile-gas-first-row` (worktree `.worktrees/debt-079`, от `numerical_scheme/implementation` `2b71387`)
**План:** `vault/plans/debt-079 relperm-immobile-gas-first-row.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-079/relperm-immobile-gas-first-row`

### Изменения
- `numerical_solver/gpn_multiphase_solver/factory.py`: `_check_relperm_table(Sg, kro, krg, relperm_file)` — `ValueError` при `krg[0] > 0`, строго, после проверок числа строк и роста $S_g$ и до проверки $k_{ro}$ последней строки (DEBT-073). Текст называет файл, $S_g$ и $k_{rg}$ первой строки, следствие и требование («таблица начинается строкой с k_rg = 0 — при S_g = 0 или при критической газонасыщенности»). `create_relperm` передаёт `krg`. Первая строка с $S_g > 0$ и $k_{rg} = 0$ принимается.
- `numerical_solver/tests/test_factory_prototype.py`: +3 теста в `TestCSVValueChecks` — `test_relperm_mobile_gas_at_zero_raises` (0.005), `test_relperm_rounding_noise_at_zero_raises` (1e-30), `test_relperm_critical_gas_saturation_accepted` (первая строка `0.05,1.0,0.0`); `test_project_relperm_tables_accepted` — новая сигнатура, 16 таблиц проекта проходят обе проверки.
- `numerical_solver/tests/test_table_range_warnings.py`: в таблице `test_initial_below_table_not_repeated` (DEBT-071) первая строка `0.05,0.9,0.005` → `0.05,0.9,0.0`; утверждения теста прежние.
- README примеров 04 и 05, заметка P8 (формат `relperm.csv`, перечень проверок), §7 заметки о нуле ОФП — правило первой строки.
- Прототип не менялся.

Код и тесты побайтово совпадают с блоками плана, проверенными аудитом 1 (сборка `vault/issues/debt-079/probes/audit1_apply.py` по базе).

### Тесты
- Было: 2017 тестов, быстрый уровень 1741 passed (145 с)
- Стало: 2020 тестов (+3 новых), быстрый уровень 1744 passed (137 с)
- Полный прогон: 2020 passed (587 с, на `c65c7a7`)
- Все зелёные: ✅

### Замер, на который опирается проверка (до правки, `vault/issues/debt-079/probes/krg0_scan.out.txt`)
| сценарий | $k_{rg}[0]$ | ГФ, м³ст/м³ст | ячеек со свободным газом |
|---|---|---|---|
| `configs/table_pvt`, 24 ч | 0 | 30.00 | 0 из 20 |
| то же | 1e-4 | 31.75 | 19 из 20 |
| то же | 1e-3 | 47.47 | 19 из 20 |
| пример 05, таблица теста DEBT-071, 6 ч | 0.005 | 96.96 | 14 |
| то же | 0 | 50.00 | 6 |

### Вне задачи
Автономный прототип (`run_prototype.py` → `radial_blackoil/input_reader.py`) строит таблицу ОФП без проверок краёв и принимает и $k_{rg}[0] > 0$, и $k_{ro}[-1] > 0$ (§9, п. 4 плана). Все книги прототипа правило соблюдают. Регистрировать ли отдельной задачей — решение пользователя.
