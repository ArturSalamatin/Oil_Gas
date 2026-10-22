## Реализация завершена

**Ветка:** `feat/feat-035/workbook-to-config` (worktree `.worktrees/feat-035`, от `numerical_scheme/implementation` `4b67213`)
**План:** `vault/plans/feat-035 workbook-to-config.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..feat/feat-035/workbook-to-config`

### Изменения
- `numerical_solver/gpn_multiphase_solver/io/workbook_convert.py` (новый) — перевод книги в `config.json` и CSV таблиц в СИ:
  - `convert_workbook`, `workbook_to_config`, `write_files`;
  - `WorkbookContentError(WorkbookError)` — все ошибки ячеек сразу, с листом и адресом;
  - моменты SCHEDULE переводятся в целые миллисекунды;
  - $\varphi_0 \le 1$ проверяется у ячейки $\varphi_{ref}$.
- `numerical_solver/gpn_multiphase_solver/cli.py` — подкоманда `gpn-solver convert книга.xlsx каталог`, коды возврата 0 / 2. Решатель, scipy и прототип она не импортирует.
- `numerical_solver/tests/test_workbook_convert.py` (новый, 100 тестов) и `numerical_solver/tests/test_cli.py` (+7 тестов).
- vault:
  - заметка «перевод книги в конфиг проверяет только книгу — моменты SCHEDULE в целых мс»;
  - контракт перевода в плане FEAT-036;
  - ссылки в заметке о формате книги и в `index.md`.

### Тесты
- Было: 2288 тестов.
- Стало: 2395 тестов (+107 новых).
- Полный прогон: 2394 passed, 1 skipped. Пропущен тест черновика руководителя: черновика нет в git.
- Все зелёные: ✅

### Проверка на книге генератора
| Проверка | Результат |
|---|---|
| `convert configs/INPUT_TEMPLATE_v1.xlsx` | код 0, 4 файла |
| `run` по её `config.json` | код 0, 29.5 с, 22 интервала, 2 592 000 с |
| Предупреждения расчёта | нет |

Прототип, загрузчик конфига, фабрика и пример 18 не менялись.
