## Реализация завершена

**Ветка:** `feat/feat-038/team-releases-script` (worktree `.worktrees/feat-038`, от `numerical_scheme/implementation` `49e75bd`)
**План:** `vault/plans/feat-038 team-releases-script.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..feat/feat-038/team-releases-script`

### Изменения
- `tools/release.py` (новый, 450 строк): выпуск одной командой `numerical_solver\.venv\Scripts\python tools\release.py X.Y.Z`. Содержимое равно коду плана после аудита 1.
- `numerical_solver/pyproject.toml`, `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/__init__.py`: комментарии без буквального «+gpn.1» / «set 1» — теперь «+gpn.N», N повышает скрипт. AST прототипа не изменился.
- `numerical_solver/README.md`: номер прототипа заменён ссылкой на литерал; новый абзац §1 «Из выпуска» — `gh release download`, распаковка архива примеров в каталог выпуска, `pip install` по путям колёс, обновление.
- `numerical_solver/examples/README.md`, `HydroSolverPrototype/Prototype_1.0.3/README.md`: номер прототипа заменён ссылкой на литерал.
- `CLAUDE.md`: строка `tools/release.py` в «Структура проекта», исключение в «Коммиты», тип коммита `release`.
- vault: заметка-решение «выпуск решателя — одна команда, push только после самопроверки сборки из метки».

### Тесты
- Было: 2461 тест
- Стало: 2461 тест (новых нет — решение пользователя)
- Полный прогон на ветке: 2460 passed, 1 skipped, 685 с (на базе: 2460 passed, 1 skipped) ✅
- Тесты прототипа: 109 passed ✅
- Проба `vault/issues/feat-038/probes/plan_check.py` на скрипте worktree — 55 ОК, репозиторий не меняется: `preflight("1.0.0")` даёт прототип `1.0.3+gpn.1 → +gpn.2` от `29a1ffa`; колёса `1.0.0` и `1.0.3+gpn.2` собраны из `git archive`; архив примеров — 124 файла без примера 18; самопроверка прошла в трёх состояниях; откат сохраняет незакоммиченный vault; печать в канал cp1251 не падает.

Скрипт не запускался: первый выпуск `1.0.0` делается после влития (план, §8).
