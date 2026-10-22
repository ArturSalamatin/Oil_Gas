## Реализация завершена

**Ветка:** `refactor/debt-047/temperature-sanity-check` (worktree `.worktrees/debt-047`, от `numerical_scheme/implementation` `51a4d8e`)
**План:** `vault/plans/debt-047 temperature-sanity-check.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-047/temperature-sanity-check`

### Изменения
- `numerical_solver/gpn_multiphase_solver/simulator.py`: метод `_check_temperature`; вызов в цикле `_advance` после каждого подшага энергии. $T \le 0$ или не конечная $T$ → `RuntimeError` с $\Delta t$ подшага, временем его конца, первой от забоя плохой ячейкой, её $r$ и $T$, числом плохих ячеек. Отказ не дробится (дробление ловит только `HydroConvergenceError`).
- `numerical_solver/gpn_multiphase_solver/io/config.py`: в `_validate` — $c_{p,o}$, $c_{p,g}$, $(\rho c_p)_s$ конечные и $> 0$; $\lambda_s$, $\lambda_o$, $\lambda_g$ конечные и $\ge 0$; при $L < 0$ — предупреждение в журнале.
- `numerical_solver/tests/test_simulator.py`: раздел G — 7 тестов (−245.8, 0, NaN, ±inf → отказ с фактами; $T$ = 1 К проходит; отказ на подшаге дробления).
- `numerical_solver/tests/test_config.py`: `TestValidationThermal` — 17 тестов (13 недопустимых значений, λ = 0 допустимо, предупреждение при $L < 0$, нет предупреждения при $L \ge 0$).
- vault: P8 §5 (λ ≥ 0 вместо λ > 0, правила и проверка $T$), `модули-simulator-оркестратор.md`, заметка `knowledge/debugging/нефизичная температура доходила до истории молча — …`.

### Тесты
- Было: 1405 тестов
- Стало: 1429 тестов (+24 новых)
- Полный прогон: 1429 passed (490 с); быстрый уровень 1179 passed
- Все зелёные: ✅

### Зелёное состояние пробы
`vault/issues/debt-047/probes/green_state.out.txt` (против `red_state.out.txt`):

| случай | до | после |
|---|---|---|
| $c_p$, $(\rho c_p)_s$, λ — 11 испорченных значений, включая inf | расчёт проходит ($c_{p,o} = 0$: $T_{\min}$ 11.8 К; $(\rho c_p)_s < 0$: ±7e42 К) или отказ scipy без имени | `ValueError` при загрузке с именем параметра |
| $L < 0$ | нагрев +3.2 К молча | расчёт идёт, предупреждение `thermal.L_degas = … < 0` |
| в обход проверки ввода: $c_{p,o} < 0$, $(\rho c_p)_s < 0$ | $T$ −7947 К, ±7e42 К | `RuntimeError` «Нефизичная температура…» к 0.0417 / 0.1667 сут |
| в обход проверки ввода: $c_{p,o} = 0$ | $T_{\min}$ 11.8 К | без изменений — ограничение критерия $T > 0$ |

Прототип, `factory.py`, `energy/`, `tests/_doubles.py` не менялись. Зависимость DEBT-015 выполнена: проверка стоит в новом цикле подшагов, тест дробления — на `FailingHydroStub`.
