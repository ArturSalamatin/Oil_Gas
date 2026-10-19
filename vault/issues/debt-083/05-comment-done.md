## Реализация завершена

**Ветка:** `refactor/debt-083/output-path-is-file` (worktree `.worktrees/debt-083`, от `numerical_scheme/implementation` `943674a`)
**План:** `vault/plans/debt-083 output-path-is-file.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-083/output-path-is-file`

### Изменения
- `numerical_solver/gpn_multiphase_solver/report/pipeline.py`: `_check_output_path` — первый существующий путь среди каталога вывода и его предков должен быть каталогом, иначе `CaseConfigError` («… — файл, а не каталог» / «диск … не найден»); вызов у конфига (после `_check_inputs_outside`, до `_check_output_free`) и у книги (до чтения книги); докстринги `CaseConfigError` и `run_case` (раздел «Исключения») называют новую причину без номера задачи, номер — в комментариях.
- `numerical_solver/tests/test_output_dir.py`: 4 модульных теста (файл, путь через файл, каталог и несуществующий путь проходят, нет диска) и отказ `run_case` до расчёта.
- `numerical_solver/tests/test_cli.py`: `--output <файл>` → код 2, файл цел.
- `numerical_solver/tests/test_workbook_run.py`: отказ до чтения книги.
- `numerical_solver/README.md` §3.4, `numerical_solver/CHANGELOG.md` («Не выпущено → Изменено»).

### Тесты
- Было: 2616 тестов
- Стало: 2623 тестов (+7 новых)
- Все зелёные: ✅ (полный прогон: 2621 passed, 2 skipped, 658 с)

### Проверка в отдельном процессе
`gpn-solver run config.json --output well_history.csv` (проба `vault/issues/debt-083/probes/audit_symptom.py`, пакет worktree): код 2, расчёт не начат, файл цел — `Ошибка конфига: каталог вывода …\well_history.csv — файл, а не каталог. Укажите другой каталог вывода. Расчёт не начат.` На базе: расчёт выполнен, затем `FileExistsError`, код 1.
