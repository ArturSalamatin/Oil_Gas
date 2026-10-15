## Реализация завершена

**Ветка:** `fix/bug-029/skin-zone-throttling-temperature` (worktree `.worktrees/bug-029`, от `numerical_scheme/implementation` `3fba142`)
**План:** `vault/plans/bug-029 skin-zone-throttling-temperature.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..fix/bug-029/skin-zone-throttling-temperature`

По решению пользователя модель не меняется: скин по-прежнему входит только в гидродинамику, а пользователь, задавший `numerics.skin` > 0, теперь получает предупреждение.

### Изменения
- `numerical_solver/gpn_multiphase_solver/io/config.py`: `_warn_skin_not_in_energy` — при $s > 0$ после `_validate` предупреждение в журнале: скин учитывается только в гидродинамике (сопротивление забойной грани), дросселирование и разгазирование на перепаде скин-зоны в температуру не входят, $T_{wf}$ их не содержит; в тексте — доля депрессии на скин-зоне в установившемся однофазном притоке $s/(\ln(R_{ext}/r_w) + s)$. При $s > 50$ — два предупреждения (о доле притока, DEBT-056, и о температуре). Комментарий `NumericsConfig.skin`.
- `numerical_solver/gpn_multiphase_solver/state.py`: комментарий к `WellData.T_wf`.
- `numerical_solver/tests/test_config.py`, `TestValidationWell`: `test_skin_up_to_threshold_silent` (фиксировал молчание при $0 < s \le 50$ — сам дефект) заменён на `test_zero_skin_silent`, `test_positive_skin_warns_energy` ($s$ = 0.01, 5, 50), `test_skin_energy_warning_gives_drawdown_share` ($s = 2$ → 24.3 %); `test_large_skin_warns` ждёт два сообщения; сообщения различаются по тексту, а не по порядку.
- vault: P8 §5, схема конфига, заметка о температуре ячейки 0; проба `vault/issues/bug-029/probes/warn_visible.py`.
- Не менялись: `problem_statement.tex` (ограничение уже записано в `ssec:bc_disc` после BUG-015; повторять в абзаце о скине — не нужно, решение пользователя), `energy/tridiag.py`, итоговая сводка `run`.

### Тесты
- Было: 1987 тестов
- Стало: 1989 (`TestValidationWell` 22 → 24)
- По шагам: тесты до кода — 7 failed / 17 passed, после — 24 passed; быстрый уровень 1711 → 1713 passed
- Полный прогон: 1989 passed (595 с) ✅

### Проба видимости (свежий процесс, без перехвата журнала)
| $s$ | Сообщения в stderr |
|---|---|
| 0 | нет |
| 2 | одно: скин не входит в уравнение энергии, 24.3 % депрессии |
| 100 | два: 5.9 % от притока без скина; 94.1 % депрессии |

Расчётный код не менялся; во всех конфигах проекта $s = 0$ — результаты примеров прежние.
