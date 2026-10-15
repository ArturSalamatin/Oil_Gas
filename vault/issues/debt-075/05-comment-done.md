## Реализация завершена

**Ветка:** `refactor/debt-075/saturation-bounds-check` (worktree `.worktrees/debt-075`, от `numerical_scheme/implementation` `d7054ee`)
**План:** `vault/plans/debt-075 saturation-bounds-check.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-075/saturation-bounds-check`

### Изменения
- `numerical_solver/gpn_multiphase_solver/simulator.py`: `Simulator._check_hydro_state(state, dt)` — после каждого принятого `hydro.solve`, до баланса массы и шага энергии; $S_g \notin [0, 1]$, $p \le 0$, $R_s < 0$ или не конечное значение → `RuntimeError` «Нефизичное состояние после шага гидродинамики dt = … с к t = … сут: в ячейке j (r = … м) <величина> = <значение>; ячеек, где …, — n из N.» Порядок $S_g$, $p$, $R_s$; сравнение точное; подшаг не дробится. Докстринг модуля — цикл подшага.
- `numerical_solver/gpn_multiphase_solver/hydro/base.py`: контракт `HydroSolver.solve` — принятое состояние допустимо точно, иначе расчёт обрывается.
- `numerical_solver/gpn_multiphase_solver/report/pipeline.py`: комментарий `run_case` называет новый источник `RuntimeError` (код тот же: CLI печатает «Расчёт не завершён: …», код 1).
- `numerical_solver/tests/test_simulator.py`: раздел J — обёртка `_CorruptingHydroSolver`, `TestNonphysicalHydroState` (18 тестов: 12 нарушений $S_g$/$p$/$R_s$ включая $1 + 2^{-52}$, $-5\cdot10^{-324}$, NaN, inf; 4 границы $S_g$ = 0, 1, $p$ = 1 Па, $R_s$ = 0; порядок величин; дробление).
- vault: P8 (таблица проверок + абзац), `модули-simulator-оркестратор` (псевдокод, список).

### Тесты
- Было: 1996 тестов (база с DEBT-073), быстрый уровень 1720
- Стало: 2014 тестов (+18), быстрый 1738
- Раздел J до кода: 14 failed / 4 passed; после — 18 passed
- Полный прогон: 2014 passed ✅ (604 с)

### Проверка на реальном сценарии
Пример 05, таблица ОФП до $S_g$ = 0.01, порог $S_g \le 0.98$ прототипа снят в памяти (`vault/issues/debt-075/probes/real_scenario.py real`, вывод `real_scenario_real.out.txt`): прежде расчёт доходил до $S_g[0]$ = 311 к 6 ч; теперь — отказ на первом принятом подшаге: `dt = 450 с к t = 0.0052 сут: в ячейке 0 (r = 0.1064 м) S_g = 6.585189352105805; …, — 2 из 50.`

Прототип, адаптер, фабрика, конфиги и примеры не менялись; на штатных данных проверка не срабатывает (замер: 6161 принятый подшаг 23 примеров — 0 нарушений).
