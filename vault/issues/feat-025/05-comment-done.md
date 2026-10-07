## Реализация завершена

**Ветка:** `feat/feat-025/standing-corey-cooling-examples` (worktree `.worktrees/feat-025`)
**План:** `vault/plans/feat-025 standing-corey-cooling-examples.md`
**Коммиты:**
```
a08d2bb vault: FEAT-025 реализован — примеры 19–21, реестр, план, индекс
a4ea29d feat: примеры 19–21 — охлаждение забоя на корреляциях Стендинга и Кори (R_s0 = 150, 500, 100), сверка d по слагаемым ячейки
bdecdc3 vault: FEAT-025 начало реализации
```

### Изменения
- `numerical_solver/examples/19_rs150_cooling/`, `20_rs500_cooling/`, `21_rs100_cooling/` — новые: `config.json` (PVT `standing`, ОФП `corey`, $S_{gc} = 0.1$, $S_{or} = 0.05$, $N = 350$, 30 × 1 сут), `main.py` (`steady_state=False`), `README.md`.
- `numerical_solver/tests/test_examples.py` — `ALL_EXAMPLES` +3; класс `TestStandingCoreyCooling` (7 тестов × 3 примера).
- `numerical_solver/tests/test_energy_matrix_examples.py` — `ALL_EXAMPLES` +3; сверка правой части $d$ — допуск от суммы модулей слагаемых ячейки (`_ref_d_scale`, флаг `build_reference(with_scale=False)`).
- `numerical_solver/examples/README.md` — подраздел 19–21, строки таблиц и перечни, время прогона.

### Результат (30 сут)
| Пример | $T(r_w)$, К | $\Delta T$, К | $S_g^{max}$ | $q_o$, м³ст/с | невязка баланса |
|---|---|---|---|---|---|
| 19 ($R_{s,0} = 150$) | 396.369 | −3.631 | 0.44319 | 2.8564e-03 | 1.78e-12 |
| 20 ($R_{s,0} = 500$) | 371.400 | −8.600 | 0.49512 | 1.2532e-02 | 3.26e-13 |
| 21 ($R_{s,0} = 100$) | 397.521 | −2.479 | 0.40831 | 1.9356e-03 | 3.92e-12 |

Все числа плана воспроизведены `main.py` до последнего знака.

### Тесты
- Было: 1035
- Стало: 1098 (+63)
- Все зелёные: ✅ (649 с)
