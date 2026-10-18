## Реализация завершена

**Ветка:** `feat/feat-034/xlsx-cell-reader` (worktree `.worktrees/feat-034`, от `numerical_scheme/implementation` `4815c4e`)
**План:** `vault/plans/feat-034 xlsx-cell-reader.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..feat/feat-034/xlsx-cell-reader` — `774a134`…`badedb2` (5 коммитов)

### Изменения
- `numerical_solver/gpn_multiphase_solver/io/xlsx_reader.py` (новый, 352 строки) — разбор книги стандартной библиотекой. `read_workbook(path) → Workbook`: листы в порядке книги и пометка `recalc_on_open`. У ячейки есть адрес и `ref` (`MODEL!C5`), тип `kind` (number / string / bool / error / empty), признак даты `is_date`, текст формулы `formula` и `formula_without_value`. Любой отказ из-за содержимого файла — `WorkbookError(ValueError)` с подсказкой.
- `numerical_solver/tests/test_xlsx_reader.py` (новый) — 152 теста:
  - ловушки XlsxWriter и правки XML;
  - 14 случаев отказа;
  - корпус из 45 книг прототипа (сверка с `radial_blackoil.xlsxio`);
  - книга генератора (сверка с `tests/_xlsx.py`);
  - черновик руководителя (пропускается без файла);
  - книги настоящего Excel;
  - импорт только стандартной библиотеки.
- `numerical_solver/tests/data/feat034_excel/` — книги, сохранённые пользователем в Excel 16: `traps.xlsx` и `template_saved.xlsx` (книга генератора после Excel).
- Vault: заметка `разбор книги xlsx сообщает тип ячейки — отказ по типу решает перевод`; решение 18 в плане FEAT-035 (API разбора); контракт исключений в плане FEAT-036; вывод пробы `probes/excel_book.out.txt`.

### Тесты
- Было: 2136 тестов
- Стало: 2288 (+152; полный прогон — 2287 passed, 1 skipped: черновик руководителя вне git), 570 с
- Все зелёные: ✅

### Проверка допущения решения 9
| Что | Результат |
|---|---|
| Книга генератора (XlsxWriter, `fullCalcOnLoad="1"`) после сохранения в Excel | пометки нет, `recalc_on_open = False` ✅ |
| Формула `=0.2/2` в `geometry.r_well` | `formula = "0.2/2"`, значение 0.1 ✅ |

Excel пользователя — с английскими настройками (десятичная точка). Поэтому ловушка русского Excel «1.5 → 1 мая» в фикстурах не воспроизведена: «1,5» и «01.05.2026» остались текстом. Признак даты на настоящем Excel проверяет время 10:30 (встроенный формат 20); форматы 14 и 16 проверяются книгами XlsxWriter.
