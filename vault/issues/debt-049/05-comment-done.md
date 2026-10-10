## Реализация завершена

**Ветка:** `refactor/debt-049/thermal-scalars-finite-check` (worktree `.worktrees/debt-049`, от `numerical_scheme/implementation` `15cdd0a`)
**План:** `vault/plans/debt-049 thermal-scalars-finite-check.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-049/thermal-scalars-finite-check`

### Изменения
- `numerical_solver/gpn_multiphase_solver/io/config.py` (`_validate`): $L$, $\mu_{JT,o}$, $\mu_{JT,g}$ — условие `-inf < v < inf`, иначе `ValueError: thermal.<параметр> должно быть конечным числом (знак любой), получено …`; проверка — до предупреждений о знаке. При $\mu_{JT,o} > 0$ — предупреждение в журнале, расчёт идёт ($\mu_{JT} = v(\alpha T - 1)/c_p$, у нефти $\alpha T \approx 0.3$; плюс — след $\varepsilon = -\mu_{JT}$ из литературы). $\mu_{JT,g} < 0$ — без предупреждения.
- `numerical_solver/tests/test_config.py`: +13 тестов в `TestValidationThermal` — `test_nonfinite_scalar_rejected` ×9, `test_nonfinite_no_sign_warning` ×2, `test_positive_mu_JT_oil_warns`, `test_negative_mu_JT_gas_no_warning`.
- `vault/knowledge/decisions/P8-формат-ввода-json.md`: §5 — девять тепловых параметров с проверкой конечности, предупреждение о $\mu_{JT,o} > 0$; образец JSON — `mu_JT_oil = -4.0e-7`, `mu_JT_gas = 4.0e-6`.
- Заметка о нефизичной температуре (DEBT-047): пункт про NaN в $L$, $\mu_{JT}$ закрыт; новая заметка — «положительный μ_JT нефти — след знака ε из литературы; тепловые скаляры проверяются на конечность при загрузке».

### Тесты
- Было: 1481 тест (быстрый уровень 1231)
- Стало: 1494 (+13 новых), быстрый уровень 1244 passed, полный — 1494 passed (590 с)
- Все зелёные: ✅

### Замер (`vault/issues/debt-049/probes/`)
| Случай | До (`red_state.out.txt`) | После (`green_state.out.txt`) |
|---|---|---|
| $L$, $\mu_{JT,o}$, $\mu_{JT,g}$ = NaN, ±inf (18 случаев: 10 и 6 МПа) | `run`: отказ scipy без имени параметра | `load_config: ValueError: thermal.<параметр> …` |
| эталон (10 и 6 МПа) | ПРОШЛИ | построчно так же |
| раздел 2: NaN в прочих полях (к DEBT-051) | — | построчно так же (0 различий) |
