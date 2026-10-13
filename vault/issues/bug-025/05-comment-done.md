## Реализация завершена

**Ветка:** `fix/bug-025/short-step-residual-floor` (worktree `.worktrees/bug-025`, от `numerical_scheme/implementation` `7b636eb`)
**План:** `vault/plans/bug-025 short-step-residual-floor.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..fix/bug-025/short-step-residual-floor`

### Изменения
- `numerical_solver/doc/problem_statement.tex`: абсолютное условие сходимости — уравнение `eq:newton_abs_tol`, $\max(\varepsilon^{abs},\ \kappa\varepsilon_{маш}M_{max}/\Delta t) + \varepsilon^{rel}\max(\|F_0\|, 10^{-9})$, $\kappa$ = 4, и абзац о пределе округления.
- `HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`: метод `_absolute_tol`, константы `ROUNDOFF_KAPPA`, `_EPS`; допуск обоих Ньютонов (`_newton_fixed_active_set`, `_newton_switching`) через `_absolute_tol`.
- `HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`: раздел BUG-025.
- Тесты: `numerical_solver/tests/test_prototype_residual_floor.py` (8), прототип `tests/test_residual_floor.py` (4); помощник `_tol` в `test_prototype_failure_diagnostics.py` — по `eq:newton_abs_tol`.

### Тесты
- Было: 1826 тестов (база `3f3df63`; быстрый уровень 1555 passed), прототип 97.
- Стало: 1834 (+8), полный прогон 1834 passed (522 с); быстрый уровень 1563 passed. Прототип 101 passed (+4).
- Все зелёные: ✅. Новые тесты до правки: 1 passed / 7 failed (GPN), 4 failed (прототип) — как в плане.
- Регрессия прототипа: `--quick` 11/11 PASS до и после, полная 17/17 PASS.

### Метрики
| Метрика | Значение | Ожидание плана | Статус |
|---|---|---|---|
| Истории 23 примеров и 3 сценариев тестов | побитово (26/26) | побитово (κ* ≥ 34 > 4) | ✅ |
| Первый шаг останова 1e-2, 1e-3, 1e-4 с (`bug020_rs150`) | ступень 1, 3/2/2 итерации, $\|F\|\Delta t \le$ 1.1e-12 м³ст | сходится ступенью 1 | ✅ |
| `floor_probe.py scan` против замера планирования | 16 строк, различий 0 | побитово | ✅ |
| `Simulator`: 16 интервалов останова по 0.0549 с | 0 отказов, $R_s(r_w)$ = 22.4587978 | 0 отказов | ✅ |
| Пример 15, $h_0$ = 0.44 с (добыча, $N$ = 50) | 0 отказов, отпечаток `5d462f35ce3e39b9` | так же | ✅ |
| Ряд VAL-004, $R_s(r_w)$ на 1 ч, первый шаг 0.110…0.0137 с | 40.612, 40.903, 41.052, 41.128; предел ≈ 41.20 | без отказов | ✅ |

### Замечания
- Оценка $\varepsilon_{маш}M_{max}$ — верхняя: замеренный предел $(0.07\text{–}0.67)\,\varepsilon_{маш}M_{max}$. Граница шага — ~0.01–0.05 с при $N$ = 350, ~0.5 с при $N$ = 50; оценка в теле issue «~5 с при 1 км» завышена.
- Следствие: если крупные подшаги отказывают по другой причине (BUG-028), мелкие теперь сходятся, и быстрый отказ превращается в долгий счёт. Штатный `Simulator` ограничен 2^max_retries подшагами на шаг; нарастание FEAT-032 — нет (комментарий в #103).
- Параллельно спланирована DEBT-055 (предел округления условия по ячейке): её план учитывает правку BUG-025 в тех же строках.

Заметка: `vault/knowledge/debugging/на коротком шаге невязка Ньютона стоит на пределе округления запасов — допуск не ниже 4ε·M_max на Δt.md`.
