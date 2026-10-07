### Контекст при открытии

- **Ветка:** `refactor/debt-043/energy-balance-rounding-threshold`
- **Коммит:** `3bd659e`
- **Мотивация:** порог $10^{-10}$ лежит на уровне шума округления: у примера 16 после ступени 4 из BUG-020 (#63) невязка $1.34\cdot10^{-10}$ при неизменной схеме энергии, и это блокирует BUG-020.
- **Затронутые модули:** `tests/test_examples.py` (`TestSharedChecks`), `tests/test_energy_balance_examples.py`, `examples/check_energy_balance_all.py`, `examples/energy_balance_convergence.py`, `examples/energy_balance.py`, `examples/README.md`; по вариантам 1–2 — `gpn_multiphase_solver/energy/tridiag.py`, `energy/balance.py`
- **Оценка сложности:** средний. Сначала нужен замер: точная невязка СЛАУ по подшагам. Выбор варианта зависит от того, подтвердит ли замер модель шума $\varepsilon\,T\sum\rho c V\sqrt{N_{sub}}$.
