## Реализация завершена

**Ветка:** `refactor/debt-042/strict-csv-readers` (worktree `.worktrees/debt-042`, от `numerical_scheme/implementation` `e8adf40`)
**План:** `vault/plans/debt-042 strict-csv-readers.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-042/strict-csv-readers`

### Изменения
- `numerical_solver/gpn_multiphase_solver/factory.py`:
  - новая функция `_read_numeric_csv` и константы столбцов `_OIL_PVT_COLUMNS`, `_GAS_PVT_COLUMNS`, `_RELPERM_COLUMNS`;
  - правила разбора: заголовок сверяется по именам (BOM и пробелы вокруг имён допустимы), полей в строке столько же, сколько столбцов, каждое поле — конечное число, пустые строки пропускаются;
  - нарушение — `ValueError` с именем файла, номером строки и столбцом;
  - три ридера стали обёртками, их сигнатуры не изменились. Столбцы ОФП собираются из целых строк и не могут разойтись по длине.
- `numerical_solver/tests/test_factory_prototype.py`: раздел H `TestCSVStrictParsing`, 16 тестов. На старом коде 15 из них красные, 1 зелёный (защита от избыточной строгости).
- `numerical_solver/examples/04_table_table/README.md`, `vault/knowledge/decisions/P8-формат-ввода-json.md`: правила разбора, в том числе что строки-комментарии теперь ошибка.

### Тесты
- Было: 1310 тестов. База за время работы ушла вперёд: DEBT-043 добавил +3, план считал от 1307.
- Стало: 1326 (+16 новых). Быстрый уровень 1090 passed (~70 с), полный прогон 1326 passed (307 с).
- Все зелёные: ✅

### Неизменность поведения
- Разбор 47 CSV-таблиц проекта совпадает побитово со снимком, снятым до правки (`vault/issues/debt-042/probes/tables_check.py --compare`, запуск с кодом worktree).
- Ошибка в `relperm.csv` теперь ловится в `from_config` с именем файла. Раньше `from_config` проходил, а `run` падал в `np.interp`.
- Прототип не менялся.
