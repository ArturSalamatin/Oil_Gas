## Реализация завершена

**Ветка:** `feat/feat-024/high-gor-cooling-example` (worktree `.worktrees/feat-024`)
**План:** `vault/plans/feat-024 high-gor-cooling-example.md`
**Коммиты:**
```
9d83f84 vault: FEAT-024 реализован
03721fb docs: README примеров — пример 14 (FEAT-024)
1ac41cf feat: пример 14 — высокий газовый фактор, охлаждение забоя (FEAT-024)
02cc89a vault: FEAT-024 начало реализации
```

### Изменения
- `numerical_solver/examples/14_high_gor_cooling/`: новый пример — `config.json`, `oil_pvt.csv` (ветки $R_s$ = 0, 150, 180), `gas_pvt.csv`, `relperm.csv` (Кори $n_g = 3$, $S_{gc} = 0.1$, шаг 0.05), `main.py` (без стационара на профиле $S_g$), `README.md`.
- `numerical_solver/tests/test_examples.py`: пример 14 в `ALL_EXAMPLES` и `NEEDS_SG_SECTION`, класс `TestHighGorCooling` (6 тестов).
- `numerical_solver/tests/test_energy_matrix_examples.py`: пример 14 в `ALL_EXAMPLES`.
- `numerical_solver/examples/README.md`: пример 14 во всех сводках; полный прогон теперь около 9 мин.
- Библиотека `gpn_multiphase_solver/` не менялась.

### Тесты
- Было: 982
- Стало: 1003 (+15 параметризованных экземпляров, +6 в `TestHighGorCooling`)
- Все зелёные: ✅ (557 с)

### Метрики
| Метрика | Значение | План | Статус |
|---|---|---|---|
| $\Delta T(r_w)$, 30 / 360 сут | −5.554 / −5.769 К | 5–10 К (запрос) | ✅ |
| $T(r_w)$, 360 сут | 344.231 К | 344.231 ± 0.002 | ✅ |
| $S_g(r_w)$, 360 сут | 0.22908 | 0.2291 ± 0.001 | ✅ |
| GOR | 137.63 → 146.36, строго растёт | < 150 | ✅ |
| двухфазные ячейки | 47 = 47 с $p < p_b$ | совпадают | ✅ |
| невязка баланса энергии | $8.69\cdot10^{-13}$ | $< 10^{-10}$ | ✅ |
| `main.py` | 34 с (расчёт 15 с) | — | — |
