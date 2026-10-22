## Реализация завершена

**Ветка:** `refactor/debt-041/example03-max-retries-table` (worktree `.worktrees/debt-041`, от `numerical_scheme/implementation` `cecc250`)
**План:** `vault/plans/debt-041 example03-max-retries-table.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-041/example03-max-retries-table`

Исполняемый код не менялся: правились только README, комментарий и docstring. Числа README взяты из замера на коде ветки (база с BUG-020). Метод замера: $k = \max \log_2 n_{substeps}$ по всем вызовам `hydro.solve` одного прогона при умолчании; контроль — $k - 1$ даёт отказ, $k$ даёт побитно тот же результат. Выводы лежат в `vault/issues/debt-041/probes/*_impl.txt` и совпали с замером аудита на `299d6a7` до знака.

### Изменения
- `examples/03_standing_corey/README.md`:
  - в цепочке ступеней над таблицей добавлена четвёртая ступень `advance` (BUG-020);
  - таблица `max_retries`: при 0.5 МПа **3** вместо 9; условие `dt_integration` = 3600 с; абзац под таблицей и дата замера.
- `examples/04_table_table/README.md`: таблица `max_retries` — при 0.5 МПа **0** вместо 1, дата и условие `dt_integration`.
- `examples/04a_high_gas_saturation/README.md:393`: первый шаг не дробится при $N$ = 80…500 (было «300 — 2 подшага, 500 — 8»).
- `examples/05_standing_table_rp/README.md`, «Снизу»: дробления нет на всём диапазоне 8…2 МПа (было «2 подшага при 5 МПа»).
- `gpn_multiphase_solver/io/config.py`: комментарий к `max_retries = 9` — запас, а не измеренный порог; значение не менялось.
- `tests/test_factory_standing_hydro.py`, `tests/test_config.py`: docstring ссылаются на этот комментарий вместо устаревших порогов.

Что дробление в README 03, 04a и 05 сняла именно четвёртая ступень, проверено: с выключенной ступенью возвращаются ровно прежние числа README — 16, 2 / 8 и 2 подшага (`probes/audit4_stage4_off.txt`).

### Тесты
- Было: 1344 теста; быстрый уровень 1108 passed (90 с)
- Стало: 1344 теста (+0 новых); быстрый уровень 1108 passed (88 с)
- Полный прогон: 1344 passed (353 с) на `e6666df` — последнем коммите кода
- Все зелёные: ✅

### Vault
- Заметка `knowledge/numerics/минимальный max_retries измеряется одним прогоном при умолчании — лимит не меняет путь решения.md`.
- В `P8-формат-ввода-json.md` добавлено уточнение к описанию `max_retries`.
