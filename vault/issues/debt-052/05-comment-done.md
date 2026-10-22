## Реализация завершена

**Ветка:** `refactor/debt-052/history-step-notes-sync` (worktree `.worktrees/debt-052`, от `numerical_scheme/implementation` `69269f3`)
**План:** `vault/plans/debt-052 history-step-notes-sync.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-052/history-step-notes-sync`

### Изменения (только vault, код не менялся)

| Заметка | Что сделано | Строк |
|---|---|---|
| `контейнер-simulation-history.md` | «Методы» по коду: `append(t, state, hydro, well, balance=None, mass_balance=None)`, `n_saved` — свойство, упаковка — функция `history_to_arrays` (`io/output.py`), а не метод; «Жизненный цикл» — `from_config → (Simulator, initial_state)`, `run(initial_state)`, `save_npz(history, grid, path)`, `plot_wellbore_dynamics` и др.; «Реализация в фазе 3» → короткая «История»; description — балансы энергии и массы | +34 −19 |
| `архитектура библиотеки numerical_solver.md` | плашка «проектный этап» с перечнем 14 расхождений (нет `NewtonHydroSolver`, `StandingPVT`, `*UnitDecorator`, `velocities`, `SimulationResult`; иные имена ABC и проводимостей `Grid`; сигнатуры `solve`, `Simulator`, `from_config`; неполное дерево пакета; JSON и «Связь с внешним модулем» — до прототипа) и ссылками на текущие описания; плашка над псевдокодом §6; две ссылки в «Связанные заметки». Текст разделов не тронут | +13 −0 |
| `модули-io-вывод.md` | плашка над эскизами `output.py`: метода `to_arrays` нет, текущие сигнатуры `save_*`, `plot_*`, состав NPZ | +2 −0 |
| `матрица температурной задачи сверена с постановкой поэлементно.md` | «A-retry», $\Delta t/n_{sub}$ → локальное дробление, подшаги $dt/2^k$; прогноз о пересмотре теста → факт: DEBT-015 менял у `test_energy_substeps_preserve_total_time` только тексты (`639c80f`, `15be88d`, `e75b1d2`), проверка $\sum h = dt$ прежняя | +11 −5 |
| `P8-формат-ввода-json.md:199` | `dt_min`, `dt_max` не использует локальное дробление — без термина A-retry | +1 −1 |
| реестр техдолга | пометка в секции DEBT-053: плашка `архитектура…` содержит сигнатуру `Simulator` с `output_config` (DEBT-053 не влит) — убрать при влитии второй из двух задач | +1 |

### Проверка
- Каждое имя из плашек есть в `numerical_solver/gpn_multiphase_solver/` (21 имя), ни одного из «нет в коде» (6 имён) нет; цели wiki-ссылок существуют.
- `git diff --numstat` совпал с прогнозом пробы аудита построчно; в заметках с плашками удалено 0 строк.
- `numerical_solver/` от точки ветвления не менялся.

### Тесты
- Было: 1494 теста (быстрый уровень на старте — 1244 passed, 77 с)
- Стало: 1494 теста (+0)
- Код не менялся; полный прогон не повторялся — после последнего полного прогона базы (влитие DEBT-049) в неё входили только коммиты vault
