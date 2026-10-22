## Реализация завершена

**Ветка:** `refactor/debt-050/orchestrator-note-local-splitting` (worktree `.worktrees/debt-050`, от `numerical_scheme/implementation` `fa0266e`)
**План:** `vault/plans/debt-050 orchestrator-note-local-splitting.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-050/orchestrator-note-local-splitting`

### Изменения
- `vault/knowledge/decisions/модули-simulator-оркестратор.md` — сверена с `simulator.py`, `state.py`, `factory.py`, `io/config.py` на `81d1474`, сняты 17 расхождений:
  - шапка: description без «адаптации dt», плашка об обновлении;
  - `Simulator.__init__` с `max_retries: int = 9`; что делают `max_retries` и `output_config` (последний `Simulator` не хранит и не читает);
  - «Цикл по времени»: три уровня; псевдокод `run` (накопители, начальная запись с `mass_balance`, вызов `_advance`) и `_advance` (G1a: подшаг пополам при `HydroConvergenceError`, рост ×2 с выравниванием, `_failure_message`, `energy.solve(hydro_result, state, h, bc, collect=balance)`, `_check_temperature`); «пробного шага» больше нет; ссылки на P4 и заметку о локальном дроблении;
  - `TimeSchedule`: `HistoryInterval` с `q_oil`, `min_bhp`, `RateControl`; `substeps(interval_idx)`; `n_intervals` — свойство;
  - `SimulationHistory`: поля `balance`, `mass_balance`, `append(..., balance=None, mass_balance=None)`, `n_saved` — свойство;
  - фабрика: `_create_prototype_hydro`, вызов `Simulator(..., max_retries=config.numerics.max_retries)`;
  - «Связанные заметки»: P4, локальное дробление, проверка $T$, контейнер истории.
- Пункт DEBT-047 (`_check_temperature`) перенесён дословно.

### Тесты
- Было: 1429 тестов
- Стало: 1429 (код и тесты не менялись, `git diff --stat` — только файл заметки)
- Прогоны: `--collect-only` до и после; быстрый и полный уровень не запускались — на ветке нет изменений в `numerical_solver/`, код совпадает с базой

### Обнаружено (в «Обнаруженных проблемах» плана, не зарегистрировано)
- `контейнер-simulation-history.md`: разделы фазы 3 — `append(t, state, hydro, well)`, «четыре поля», `to_arrays`;
- `архитектура библиотеки numerical_solver.md:181-187` — псевдокод проектного этапа;
- `матрица температурной задачи сверена с постановкой поэлементно.md:39, 127-128` и комментарии `test_energy_matrix_examples.py:547, 620-622` — термин «A-retry»;
- `simulator.py:101, 109, 119-121` — параметр `output_config` мёртвый, docstring и комментарий утверждают обратное.
