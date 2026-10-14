## Реализация завершена

**Ветка:** `fix/bug-026/shutin-first-substep-rs` (worktree `.worktrees/bug-026`, от `numerical_scheme/implementation` `40a6acb`)
**План:** `vault/plans/bug-026 shutin-first-substep-rs.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..fix/bug-026/shutin-first-substep-rs`

### Изменения
- `examples/16_well_shut_in/config.json`, `examples/17_shut_in_strong_cooling/config.json`: `time.dt_after_control_change` 2 → 0.11 с. Первый подшаг останова — 0.11 с, 16 подшагов до 1800 с.
- `gpn_multiphase_solver/io/config.py`: комментарий `TimeConfig` — рекомендация 0.11 с вместо «2 с, мельче 0.5 с не сходится».
- `gpn_multiphase_solver/simulator.py`: подсказка в тексте отказа без устаревшего пола округления (его снял BUG-025).
- `tests/test_val004.py`: класс `TestRampRsAfterShutIn` (+3 теста) — сходимость $R_s(r_w)$ по $h_0$, рекомендация 0.11 с, остаток удвоения подшагов.
- `tests/test_examples.py`: числа 16, 17 ($R_s(r_w)$ финала 5.085 / 88.5826, $T$ по замеру); докстринги `test_energy_matrix_examples.py`, `test_energy_balance_examples.py`, `test_mass_balance.py`.
- README 16, 17 и сводный README: числа, абзац о газосодержании у забоя и остатке удвоения.
- Vault: заметка `debugging/` с механизмом и замерами; заметка-решение FEAT-032 переименована (прежний заголовок «R_s не исправляет, мельче 0.5 с не сходится» после BUG-025 неверен); P4, json-config-schema, временная сетка, заметка VAL-004.

### Тесты
- Было: 1929 тестов
- Стало: 1932 (+3 новых)
- Полный прогон: 1932 passed (563 с); быстрый уровень: 1656 passed
- Все зелёные: ✅

### Метрики
| Метрика | Значение | Ожидание | Статус |
|---|---|---|---|
| $R_s(r_w)$ финал, пример 16 | 4.792 → 5.085 | 5.0847 (замер плана) | ✅ |
| $R_s(r_w)$ финал, пример 17 | 79.59 → 88.58 | 88.5826 | ✅ |
| $R_s(r_w)$ через 1 ч, VAL-004, $h_0$ = 0.11 с | 39.7785 | 39.7785 ± 2e-3 | ✅ |
| Отпечатки историй 23 примеров | 21 прежние, 16 и 17 — новые | `87cd3498258184cf`, `1b97396204eff005` | ✅ |
| Числа README (`readme_numbers.py`), консоль `run` 16 и 17 | совпали с замером плана | побитово по печати | ✅ |

Прототип не менялся. `numerical_solver/README.md` (FEAT-031) в базе пока нет, рекомендация 2 с в нём устарела: обновить при FEAT-031.
