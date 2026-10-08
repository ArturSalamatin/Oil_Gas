## Реализация завершена

**Ветка:** `feat/feat-029/shutin-strong-cooling-example` (worktree `.worktrees/feat-029`, от `numerical_scheme/implementation` `770fae2`)
**План:** `vault/plans/feat-029 shutin-strong-cooling-example.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..feat/feat-029/shutin-strong-cooling-example`

### Изменения
- `numerical_solver/examples/17_shut_in_strong_cooling/` — новый пример: `config.json` (конфиг 20, $N = 200$, 15 сут при 5 МПа + 15 сут останова по дебиту, `dt_integration` = 3600 с), `main.py` (7 моментов профилей, без стационарной аналитики), `README.md`.
- `numerical_solver/tests/test_examples.py` — 17 в `ALL_EXAMPLES` и `ENDS_SHUT_IN`; класс `TestShutInStrongCooling` (10 тестов: конфиг, конец добычи, останов, рост давления, кольцо газа, прогрев забоя, кольцо теплее $T_0$, источники тепла, диапазоны рисунков, `main.py`).
- `numerical_solver/tests/test_energy_matrix_examples.py`, `tests/conftest.py` — список примеров и комментарии.
- `numerical_solver/examples/README.md` — 17 во всех таблицах и перечнях; `examples/16_well_shut_in/README.md` — ссылка на 17.

### Тесты
- Было: 1344 теста
- Стало: 1366 тестов (+22)
- Полный прогон: 1366 passed, 535 с (17 — 99 с в фикстуре и 95 с в сверке матрицы энергии)
- Все зелёные: ✅

### Пример 17
| Величина | Значение |
|---|---|
| $T(r_w)$: конец добычи → 1 ч останова → 30 сут | 365.017 → 368.779 → 377.309 К (недогрев 2.69 К) |
| давление у забоя выше $p_b$ | через 12 ч; к 27 сут $p = p_0$ |
| газ у забоя | растворился за первый час, $R_s(r_w) = 79.5$ |
| кольцо газа | 3.6–24 м, $R_s = R_s^{eq}(p_0) = 332.4 > R_{s,0}$, теплее $T_0$ на 0.22 К |
| невязка баланса энергии / массы | $1.5\cdot10^{-15}$ / $\le 2.3\cdot10^{-10}$ |
| время `main.py` | 112 с (расчёт 96.5 с) |

Числа `plan_numbers.py` на папке примера совпали с планом побитово. Механизм прогрева забоя (теплопроводность после первого часа, а не приток тёплой нефти) — заметка `vault/knowledge/science/после останова из развитой газовой зоны забой прогревается теплопроводностью, а не притоком тёплой нефти.md`.
