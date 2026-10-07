## Реализация завершена

**Ветка:** `refactor/debt-043/energy-temperature-deviation-solve` (worktree `.worktrees/debt-043`, от `79603bc`)
**План:** `vault/plans/debt-043 energy-temperature-deviation-solve.md`
**Коммиты:**
- `e76e79c` refactor: СЛАУ температуры в отклонениях от T_ext — невязка баланса энергии до машинной; matrix_probe с T_ref
- `b75a340` test: решение в отклонениях совпадает с абсолютной формой; страж машинного уровня баланса энергии (1e-14)
- `dec33ca` refactor: порог невязки баланса энергии 1e-12 во всех проверках; NaN — провал; верное объяснение остатка
- `2a956c5` docs: README — невязка баланса энергии на машинном уровне, порог 1e-12

### Изменения
- `energy/tridiag.py`: `solve` подаёт `assemble_tridiag` $T^n - T_{ext}$ и 0 (сборка не меняется — аффинна по $T^n, T_{ext}$), прогонка даёт $\theta$, возврат $\theta + T_{ext}$; накопителю — $\theta$, а не записанная $T$; `matrix_probe` получает `T_ref`.
- `energy/balance.py`, `energy/base.py`: только тексты — механизм невязки, инвариантность накопителя к сдвигу.
- `tests/test_energy_matrix_examples.py`: `build_reference(..., T_ref=0.0)`, проба с `T_ref`.
- `tests/test_energy.py`: `TestDeviationForm::test_solution_matches_absolute_form` (независимая сборка в абсолютной $T$).
- `tests/test_energy_balance_examples.py`: страж `test_energy_balance_machine_precision[03, 04]` ($< 10^{-14}$), `TOL_RESIDUAL = 1e-12`.
- `tests/test_examples.py`: `TestSharedChecks` — порог $10^{-12}$, NaN — провал.
- `examples/check_energy_balance_all.py`, `energy_balance_convergence.py` — порог $10^{-12}$ (было $10^{-10}$, $10^{-9}$), шапки без «Кэхэна»; `energy_balance.py` — без «ошибки расщепления O(dt)»; README общий и 01–05, 04a — новые числа.

### Тесты
- Было: 1307 тестов
- Стало: 1310 (+3 новых)
- Полный прогон: ✅ 1310 passed (313 с); быстрый уровень 1074 passed

### Метрики
| Метрика | До | После | Порог | Статус |
|---|---|---|---|---|
| Невязка баланса энергии, 21 пример | до $4.8\cdot10^{-11}$ (16) | 0…$5.1\cdot10^{-15}$ | $10^{-12}$ | ✅ |
| Серии 01–05, шаг 360 с | до $7.8\cdot10^{-11}$ | до $4.0\cdot10^{-15}$ | $10^{-12}$ | ✅ |
| Укороченные тестовые (6 ч, $N = 25$) | $1.6$–$4.9\cdot10^{-13}$ | 0…$7.8\cdot10^{-17}$ | $10^{-14}$ | ✅ |
| $p$, $S_g$ против базы (03, 16, 21) | — | побитово | — | ✅ |
| $\max\lvert\Delta T\rvert$ против базы | — | $3.1\cdot10^{-11}$ К | $10^{-9}$ К | ✅ |

16 с BUG-020 (замер при планировании): $1.34\cdot10^{-10} \to 1.9\cdot10^{-15}$ — BUG-020 разблокируется после влития.

Обнаружено попутно: DEBT-045 — в таблице баланса README устарел кондуктивный член примера 14 (так и на базе, к DEBT-043 не относится).
