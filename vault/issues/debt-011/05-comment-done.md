## Реализация завершена

**Ветка:** `refactor/debt-011/diagnostics-into-package` (worktree `.worktrees/debt-011`, от `numerical_scheme/implementation` `87eb55f`)
**План:** `vault/plans/debt-011 diagnostics-into-package.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-011/diagnostics-into-package`

### Изменения
- `gpn_multiphase_solver/diagnostics/` (новый): `closed_form.py` — замкнутое решение стационара; `two_phase.py` — GOR, $S_g$ из замыкания, Дюпюи, фронт; `rs.py` — равновесие $R_s$, радиус изобары; `temperature.py` — однофазная асимптотика $T$.
- `energy/balance.py`: `compute_energy_balance(history)`; `mass_balance.py`: `compute_mass_balance(history)` — ряды балансов рядом с накопителями.
- `io/output.py`: `plot_energy_balance_series`, `plot_mass_balance_series`, `plot_relperm_curves`, `relperm_table_nodes`, `pvt_table_nodes` — рисуют на осях, файлов не пишут.
- `simulator.py`: свойства `grid`, `pvt`, `relperm` (ОФП — аргумент конструктора); `factory.py`: `create_pvt`, `create_relperm` публичные, без псевдонимов.
- `examples/`: приватный доступ к решателю убран (`sim.pvt`, `sim.grid`, `sim.relperm`, `config.rock`); модули проверок оставляют печать, наложения и запись PNG (их переносит FEAT-030); README — ссылки на пакет.
- Тесты: новый `test_public_api.py`; страж `test_no_private_solver_access` в `test_example_scripts.py`; перенаправление тестов на пакет.

### Тесты
- Было: 1741
- Стало: 1799 (+58: 12 в `test_public_api.py`, 46 — страж по каждому скрипту `examples/`)
- Полный прогон: 1799 passed ✅

### Проверка неизменности
| Метрика | Значение | Ожидание | Статус |
|---|---|---|---|
| Печать 23 примеров до/после | совпадает | совпадает | ✅ |
| Файлы `output/` побайтно | 287 из 291 | все, кроме времени выполнения | ✅ (4 файла выхода прототипа у 18 содержат `wall_seconds`, различаются и между двумя прогонами одного кода) |
| Колесо содержит `diagnostics/` | да | да | ✅ |
| CLI проверок (4 скрипта) | код 0 | код 0 | ✅ |

Обнаружено: план пропустил вызывающего `04_table_table/grid_convergence.py` (`SG_EPS` из `two_phase_analytics`) — поймал страж DEBT-046, исправлено. Холостое слияние с базой после DEBT-054 — без конфликтов.
