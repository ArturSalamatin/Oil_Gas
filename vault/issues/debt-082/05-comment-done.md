## Реализация завершена

**Ветка:** `refactor/debt-082/locked-output-dir` (worktree `.worktrees/debt-082`, от `numerical_scheme/implementation` `e39fd5b`)
**План:** `vault/plans/debt-082 locked-output-dir.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-082/locked-output-dir`

### Изменения
- `numerical_solver/gpn_multiphase_solver/report/pipeline.py`: `_check_output_free` (проба переименованием до расчёта по конфигу → `CaseConfigError`, код 2), `_clear_output` (переименование в соседний, затем удаление) после расчёта и у книги, `_sibling` (свободное соседнее имя, `os.path.abspath`, корень диска — отказ), `_busy_message`; занятый после расчёта каталог — результаты в `<имя>_<ГГГГ-ММ-ДД>_<чч-мм-сс>`, предупреждение, код 0.
- `numerical_solver/tests/test_output_dir.py` (новый, 15 тестов, 3 — с настоящей блокировкой на Windows), `tests/test_cli.py` (+1: код 2 без трассировки), `tests/test_workbook_run.py` (тест книги — подмена `os.rename`, каталог не изменён).
- Примеры 01, 02, 05, 18 дописывают рисунки в `r.output_dir`; `.gitignore` — `numerical_solver/examples/**/output[._]*/`.
- `cli.py` (справка `run`), `README.md` §3.4/§3.6, `examples/README.md`, `CHANGELOG.md` («Исправлено»).
- Vault: заметка решения «каталог вывода очищается переименованием — занятый каталог не удаляется частично», правки заметок FEAT-030 и FEAT-036.

### Тесты
- Было: 2461 тест
- Стало: 2477 тестов (+16 новых)
- Быстрый уровень: 2192 passed, 1 skipped; полный: 2476 passed, 1 skipped (черновик книги вне git) за 714 с
- Все зелёные: ✅

### При влитии
База выпустила `1.0.0` после точки ветвления — ожидается конфликт в `numerical_solver/CHANGELOG.md` (пробное слияние: единственный): блок «Исправлено» — под пустым «Не выпущено», раздел `1.0.0` не трогать.
