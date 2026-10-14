## Реализация завершена

**Ветка:** `refactor/debt-069/stage-attempts-failure-report` (worktree `.worktrees/debt-069`, от `numerical_scheme/implementation` `458f5c0` — уже с влитой BUG-028)
**План:** `vault/plans/debt-069 stage-attempts-failure-report.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-069/stage-attempts-failure-report`

### Изменения
- `radial_blackoil/blackoil.py`:
  - тип `StageAttempt(stage, branch, report)`, где `report` — копия отчёта попытки;
  - поле `BlackOilNewtonReport.attempts`;
  - `_fallback(…, stage=2)` записывает каждую ветку; ветка, которая сошлась, но несогласована, записывается отказом `branch`;
  - `advance` собирает попытки по порядку, как только ступень 1 не решила шаг, — и у отказа, и у принятого шага;
  - `advance_fourth_stage` отдаёт попытки своих веток;
  - подмена DEBT-030 не меняется.
- `hydro/prototype_adapter.py`: `_attempts_text` — строка «; попытки ступеней: [1 — …; 2 открыта — …; 2 закрыта — ветвь скважины несогласована (итераций 0); …]» в конце текста отказа. Прежний текст остаётся её началом.
- `CHANGELOG_1.0.3.md`, `docs/OUTPUT_FORMAT.md` — описание поля.
- Тесты:
  - `tests/test_prototype_stage_attempts.py` — новый, 14 тестов;
  - проверки попыток добавлены в `test_real_total_failure_only_cell_test` (BUG-018, N = 350) и `test_bhp_shutin_step_without_open_branch`;
  - `test_adapter_message_cell_test_only` проверяет строку попыток на реальном отказе;
  - в прототипе — `tests/test_failure_report.py` (+2).

### Тесты
- Было: 1948 (после BUG-028).
- Стало: 1962 (+14), полный прогон 1962 passed ✅.
- Прототип: 101 → 103 passed. Регрессия: `--quick` 11/11, полная 17/17 PASS. Все CSV 11 кейсов побайтно совпали с прогоном до правки.

### Метрики
| Метрика | Значение | Ожидание | Статус |
|---|---|---|---|
| истории 5 сценариев (BUG-018, примеры 14, 16, 17, суточный останов) | побитово | побитово | ✅ |
| тексты отказов без строки попыток | побуквенно прежние, 15 из 15 | прежние | ✅ |
| строка попыток в отказах | 15 из 15 | в каждом | ✅ |
| BUG-018: `attempts` против перехвата `_advance_phases` | 7 = 7 | совпадают | ✅ |
| шаг, решённый ступенью 1 (пример 19 после BUG-028) | `attempts` пуст | пуст | ✅ |

Ветка «открыта» ступени 2 у BUG-018 повторяет ступень 1 побитово. Теперь это видно в тексте отказа; задача на этот повтор — DEBT-072 (в реестре, без issue).
