## Реализация завершена

**Ветка:** `refactor/debt-044/csv-table-value-checks` (worktree `.worktrees/debt-044`, от `numerical_scheme/implementation` `cf86aa2`)
**План:** `vault/plans/debt-044 csv-table-value-checks.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-044/csv-table-value-checks`

### Изменения
- `numerical_solver/gpn_multiphase_solver/factory.py`:
  - пределы столбцов `_OIL_PVT_LIMITS`, `_GAS_PVT_LIMITS`, `_RELPERM_LIMITS`: $R_s \ge 0$; $p$, $B_o$, $\mu_o$, $B_g$, $\mu_g > 0$; $S_g$, $k_{ro}$, $k_{rg} \in [0, 1]$. Проверяет `_read_numeric_csv` при разборе строки: `gas_pvt.csv: строка 3, столбец Bg: '-0.008' — должно быть > 0.`;
  - новые `_check_gas_pvt_table`, `_check_relperm_table`: не меньше двух строк, строгий рост давления / $S_g$ — до конструкторов прототипа, на русском, с именем файла;
  - `_check_pvto_branches`: не меньше двух ветвей $R_s$ (раньше — `OIL_PVT needs >=2 Rs branches` из `pvt.py:46` без имени файла).
- `numerical_solver/tests/test_factory_prototype.py`: раздел I, `TestCSVValueChecks` — 26 тестов (17 случаев пределов, граничные значения, путь через `from_config`, 7 правил таблицы целиком).
- `numerical_solver/examples/04_table_table/README.md`, `vault/knowledge/decisions/P8-формат-ввода-json.md`: допустимые значения и правила таблиц.

Код, тесты и документы совпадают с блоками плана побайтно (сверка программой после каждого шага). Прототип не менялся.

### Тесты
- Было: 1344 теста (быстрый уровень 1108)
- Стало: 1370 (+26, все в быстром уровне: 1134 passed)
- Полный прогон: 1370 passed, 379 с ✅

### Проверки
| Проверка | Результат |
|---|---|
| Красное состояние на коде ветки до правки | совпало с замером плана (`red_state.out.txt`) |
| Испорченные таблицы `configs/table_pvt`, $p_{wf}$ = 15 и 10 МПа (`green_state.out.txt`) | 48 из 48 отвергнуты в `from_config` с именем файла; эталон без подмены не изменился ✅ |
| Таблицы проекта (`tables_check.out.txt`) | 47 таблиц, 17 табличных конфигов — 0 отказов ✅ |
| Чтение таблиц (`debt-042/probes/tables_check.py --compare`) | побитово совпадает со снимком ✅ |
| `TestReadme` после правки README 04 | 55 passed ✅ |
