## Реализация завершена

**Ветка:** `feat/feat-032/ramp-step-after-control-change` (worktree `.worktrees/feat-032`, от `numerical_scheme/implementation` `3545d98`)
**План:** `vault/plans/feat-032 ramp-step-after-control-change.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..feat/feat-032/ramp-step-after-control-change`

### Изменения
- `gpn_multiphase_solver/bc.py`: `PressureControl` и `RateControl` сравниваются и хешируются по значению.
- `gpn_multiphase_solver/io/config.py`: поле `time.dt_after_control_change` (с; `null` — выключено, по умолчанию), проверка «null или > 0».
- `gpn_multiphase_solver/simulator.py`:
  - `TimeSchedule.first_substep_depth(k)` — глубина $m$ первого подшага $dt/2^m \le h_0$ на интервале, где управление отличается от предыдущего; первый интервал сменой не считается (BUG-028);
  - `Simulator._advance(…, depth)` — локальное дробление G1a стартует с $dt/2^m$ и растёт ×2 до $dt/2$; при $m = 0$ код побитово прежний;
  - текст отказа называет поле и `null`.
- `gpn_multiphase_solver/factory.py`: поле передаётся в `TimeSchedule`.
- Примеры 16 и 17: `time.dt_after_control_change = 2` (первый подшаг 1.76 с, 12 подшагов на первый час останова). Тесты, README 16, 17 и сводный README — с новыми числами.
- `tests/test_val004.py`: серии явно без нарастания; `TestRampAfterShutIn` — выигрыш на эталонном сценарии.

### Тесты
- Было: 1826 тестов
- Стало: 1864 тестов (+38 новых, из них 36 быстрых)
- Все зелёные: ✅ (полный прогон 1864 passed, 560 с)

### Метрики
| Метрика | Значение | Ожидание | Статус |
|---|---|---|---|
| Ошибка $T(r_w)$ через 1 ч останова, сценарий VAL-004 | −0.059 К (без нарастания −0.230 К) | < 0.3 прежней | ✅ |
| Отпечатки историй 23 примеров | 0 расхождений | 16, 17 — эмуляция плана; 21 — без изменений | ✅ |
| Числа README 16/17 | совпали с замером плана построчно | побитово | ✅ |
| Пример 17: $T(r_w)$ через 1 ч / 30 сут | 369.258 / 377.351 К | план 1.6 | ✅ |
