## Реализация завершена

**Ветка:** `refactor/debt-053/simulator-output-config-retry-terms` (worktree `.worktrees/debt-053`, от `numerical_scheme/implementation` `f99cdbe`)
**План:** `vault/plans/debt-053 simulator-output-config-retry-terms.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-053/simulator-output-config-retry-terms`

### Изменения
- `gpn_multiphase_solver/simulator.py`: удалены параметр `output_config`, строка docstring о нём и импорт `OutputConfig`. Комментарий в `__init__` объясняет удаление: журнал настраивает фабрика.
- `gpn_multiphase_solver/factory.py`: вызов `Simulator(...)` без `output_config=config.output`.
- `tests/test_dt_convergence.py`: удалены `test_retry_steps_match_their_neighbours` и `DT_WITH_RETRY`; комментарий модуля переписан по замеру. Шаг примера 07 не дробится ни при одном dt из `DT_LIST` (`vault/issues/debt-053/probes/splitting_ex07.out.txt`). Механизм BUG-010 проверяют `test_simulator.py::TestEnergySubstepsUnderRetry::test_energy_steps_match_hydro_substeps` и `test_energy_matrix_examples.py::test_energy_substeps_preserve_total_time`.
- `tests/test_energy_matrix_examples.py` (5 мест, включая сообщение `assert`), `tests/test_rate_control.py`, `examples/05_standing_table_rp/closed_form_convergence.py`: «A-retry» в настоящем времени заменён на «локальное дробление (DEBT-015)». Вместо «гидро раздробило» теперь «Simulator раздробил».
- `vault/knowledge/decisions/модули-simulator-оркестратор.md`: сигнатура `Simulator` без `output_config`, абзац об удалении.

«A-retry» в `numerical_solver/` (без прототипа) остался в 5 строках, все в прошедшем времени. Расчётный код не менялся: при аудите пропатченные `simulator.py` и `factory.py` посчитали примеры 07 и 10 побитово как исходные. Прототип не затронут.

### Тесты
- Было: 1494 теста
- Стало: 1493 (−1, удалён избыточный тест; новых нет)
- Полный прогон: 1493 passed, 516 с ✅
- Быстрый уровень: 1243 passed

### Связь с DEBT-052
DEBT-052 к моменту реализации не влит. Тот, кто вливается вторым, сверяет сигнатуру `Simulator` в плашке `архитектура библиотеки numerical_solver.md`: после DEBT-053 она без `output_config`.
