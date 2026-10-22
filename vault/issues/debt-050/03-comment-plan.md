План: `vault/plans/debt-050 orchestrator-note-local-splitting.md`. Ветка: `refactor/debt-050/orchestrator-note-local-splitting`. Шагов: 10.

- Объём (решение 2026-10-10): вся заметка `модули-simulator-оркестратор.md` — 15 расхождений с кодом на `7b34a33`: сигнатура и вызов с `max_retries`, псевдокод `run` и `_advance` (локальное дробление, DEBT-015), «пробный шаг», `TimeSchedule.n_intervals` и `SimulationHistory.n_saved` — свойства, поля `balance`/`mass_balance`, `_create_prototype_hydro`, ссылки на P4 и заметку о локальном дроблении.
- Код не меняется; baseline — 1429 тестов (`--collect-only`).
- Соседние заметки (`контейнер-simulation-history`, `архитектура библиотеки numerical_solver`, `матрица температурной задачи…`) — в «Обнаруженных проблемах» плана, без правки.
