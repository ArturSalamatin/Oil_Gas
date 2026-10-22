## Реализация завершена

**Ветка:** `fix/bug-022/newton-cell-relative-tolerance` (worktree `.worktrees/bug-022`, от `numerical_scheme/implementation` `26ddb34`)
**План:** `vault/plans/bug-022 newton-cell-relative-tolerance.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..fix/bug-022/newton-cell-relative-tolerance`

### Изменения
- `HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`: аргумент конструктора `cell_tol` (по умолчанию `None` — выключено), методы `_cell_weights`, `_cells_converged`; решение Ньютона принимается, только если кроме абсолютного критерия в каждой ячейке $\max_c |F_{c,i}|\,\Delta t/V_{p,i} \le$ `cell_tol` — в `_newton_fixed_active_set` (ступени 1–3) и `_newton_switching` (ступень 4).
- `gpn_multiphase_solver/io/config.py`: поле `numerics.newton_cell_tol` = 1e-8 (`null` — выключено), проверка знака в `_validate` (тип и конечность уже проверяет проход DEBT-051); докстринг `NumericsConfig` — какие поля читаются, какие нет (DEBT-008).
- `gpn_multiphase_solver/factory.py`: порог передаётся прототипу.
- Тесты: новый `tests/test_prototype_cell_tolerance.py` (13), `TestNewtonCellTolValidation` (9), `test_wellbore_rs_never_decreases` (воспроизводитель: был −1.84e-2, порог −1e-4), `test_first_day_with_cell_tol`; три теста с числами — по замеру, с причиной в docstring (79.51 → 79.537; 60/34 → 70/41 подшагов; BUG-018 при N = 350 — условие выключено).
- README 16 примеров и сводный — числа консоли (невязки балансов, $R_s$, GOR); таблица ряда README 03.
- `doc/problem_statement.tex`: абзац «Сходимость Ньютона» описывает действующие критерии (прежний текст обещал покомпонентный критерий из конфига — так не было никогда), `eq:newton_cell_tol`.
- `CHANGELOG_1.0.3.md` прототипа, P8, `json-config-schema.md`, `hydro-prototype-анализ.md`, заметка в `knowledge/debugging/`.

### Результат
- Пример 17: наименьшее изменение $R_s(r_w)$ между записями останова −1.84e-2 → −2.0e-5; на 30 сут 79.5125 → 79.5367.
- Истории 22 примеров (отпечатки, число якобианов, шагов, отказов) побитово равны эмуляции плана; якобианов +13 %.
- Прототип с `cell_tol=None`: тесты 97 passed, регрессия `--quick` 11/11 и полная 17/17 PASS — побитово, эталон не менялся.

### Тесты
- Было: 1592 теста
- Стало: 1616 тестов (+24 новых)
- Все зелёные: ✅ (полный прогон 1616 passed, 10 мин 21 с)

После влития — перестроить рисунки примеров (`examples/run_all.py`). Зарегистрированы при планировании: DEBT-054 (отказ только по условию ячейки неотличим в отчёте), DEBT-055 (предел округления условия).
