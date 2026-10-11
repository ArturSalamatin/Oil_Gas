## Реализация завершена

**Ветка:** `refactor/debt-054/cell-test-failure-report` (worktree `.worktrees/debt-054`, от `numerical_scheme/implementation` `87eb55f`)
**План:** `vault/plans/debt-054 newton-failure-diagnostics.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-054/cell-test-failure-report`

### Изменения
- `HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`:
  - в `BlackOilNewtonReport` новые поля `residual_tol`, `cell_measure`, `exit_reason`;
  - они заполняются во всех возвратах `_newton_fixed_active_set` и `_newton_switching` и при исчерпании набора фаз;
  - `_fallback` ставит причину `branch`;
  - подмена DEBT-030 переносит новые поля;
  - отказ ступени 4 пишет фактическое число итераций (DEBT-061);
  - новые методы `_cell_measure`, `_newton_report`.
- `gpn_multiphase_solver/hydro/prototype_adapter.py`: `_failure_details` дописывает к прежнему тексту отказа допуск, меру ячеек с порогом `numerics.newton_cell_tol`, причину выхода, какое условие не выполнено и чьи это числа.
- `gpn_multiphase_solver/simulator.py`: текст `RuntimeError` при исчерпании дробления кончается фразой «Последний отказ гидродинамики: <текст адаптера>».
- `HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`: раздел DEBT-054.
- Тесты: `tests/test_prototype_failure_diagnostics.py` (26, новый), `tests/test_simulator.py` (+1).

Пример — первые сутки сценария BUG-018 при N = 350:
```
advance не сошёлся: dt = 8.640e+04 с, t = 0.0000 сут, итераций 4, невязка 6.51e-15 (допуск 5.35e-07), мера ячеек 2.60e-08 (порог numerics.newton_cell_tol = 1e-08), выход: линейный поиск не принял ни одной точки — не выполнено только условие по ячейке; числа — Ньютона ступени 1
```

### Тесты
- Было: 1741 тест.
- Стало: 1768 (+27 новых); полный прогон — 1768 passed, быстрый уровень — 1497.
- Все зелёные: ✅
- Прототип: тесты 97 passed; полная регрессия 17/17 PASS побитово.

### Проверка неизменности и метрики
| Метрика | Значение | Ожидание | Статус |
|---|---|---|---|
| Истории 5 сценариев (BUG-018 N = 350, примеры 14, 16, 17, суточный останов rs300) | побитово, вызовы гидродинамики те же | побитово | ✅ |
| Новый текст каждого из 10 отказов начинается с прежнего | 10/10 | 10/10 | ✅ |
| Класс и причина выхода в тексте совпадают с независимой переписью | 10/10 («только по ячейке» 5, «оба не выполнены» 5) | 10/10 | ✅ |
| Отказ ступени 4 при обрыве решателя / NaN | 2 / 1 итерация (было 40 / 40) | 2 / 1 | ✅ |
| Регрессия прототипа | 17/17 PASS | 17/17 | ✅ |

DEBT-061 закрыта этой задачей. Заметка результатов: `vault/knowledge/debugging/отказ Ньютона только по условию ячейки выглядел обычным — отчёт называет допуск, меру и причину выхода.md`.
