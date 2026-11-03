## Реализация завершена

**Ветка:** `refactor/debt-089/release-with-handover` (worktree `.worktrees/debt-089`, от `numerical_scheme/implementation` `27f3114`)
**План:** `vault/plans/debt-089 release-with-handover.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-089/release-with-handover`

### Изменения
- `tools/release.py`: функция `handover_archive` (общий путь архива передачи) и `run_handover` (передача отдельным процессом без перехвата вывода, со сбросом буфера). Передача стала последним действием шага 3, до push, а выпуск состоит из шести файлов. Добавлен ключ `--acceptance`. Шаг 1 первой проверкой требует `pdflatex` и проверяет чистоту всего репозитория. `NOTES_TAIL` называет архив поставки для разработки, сообщение отката – оба каталога `dist/`, докстринг описывает новый порядок.
- `tools/handover.py`: путь архива берётся из `release.handover_archive`; докстринг описывает вызов передачи из выпуска.
- `numerical_solver/tests/test_release_notes.py`: 13 новых тестов (проверка `pdflatex`, разбор аргументов, вызов передачи и её отказы), обновлён тест описания выпуска.
- `numerical_solver/README.md`: папка выпуска из шести файлов с обеими поставками, распаковка архива поставки для разработки из неё, «Из выпуска».
- `numerical_solver/CHANGELOG.md`: пункт DEBT-089 в «Не выпущено», «Изменено».
- `CLAUDE.md`: строки `tools/release.py`, `tools/handover.py`, `tools/acceptance.py` и абзац раздела `numerical_solver`.

### Тесты
- Было: 2677 тестов
- Стало: 2690 тестов (+13 новых)
- Все зелёные: ✅ (полный прогон 2689 passed, 1 skipped)

### Проба `release.build` на `v1.0.6`
| Прогон | Результат |
|---|---|
| основной, вывод в файл | шесть файлов; архив 526 файлов, 4.22 МБ, с PDF и HTML; журнал в одной кодировке, строки выпуска перед выводом передачи; передача 15 с |
| без `pdflatex` | `ReleaseError` «передача v1.0.6: код 1» |
| с приёмкой | `ReleaseError` после 833 с приёмки: не пройдена проверка причин пропуска – BUG-030 (`ALLOWED_SKIPS` в `tools/acceptance.py` отстал от текста пропуска в `test_xlsx_reader.py`), к коду задачи не относится |

Итоги – `vault/issues/debt-089/probe-results.md`.
