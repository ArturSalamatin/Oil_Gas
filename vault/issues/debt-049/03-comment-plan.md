### План готов

План: `vault/plans/debt-049 thermal-scalars-finite-check.md`. Ветка: `refactor/debt-049/thermal-scalars-finite-check`. Шагов: 3.

**Решения пользователя (2026-10-10):**
- объём — только три скаляра (вариант 1): `_validate` проверяет `-inf < v < inf` для `thermal.L_degas`, `thermal.mu_JT_oil`, `thermal.mu_JT_gas`, знак не ограничен, проверка — до предупреждения о $L < 0$;
- NaN в прочих числовых полях конфига (вариант 2) — отдельная запись DEBT-051;
- знаки $\mu_{JT}$ в образце JSON P8 исправить в этой задаче.

**Красная проба** (`vault/issues/debt-049/probes/red_state.py`, `7b34a33`, вывод `red_state.out.txt`):
- раздел 1: все 18 случаев ($L$, $\mu_{JT,o}$, $\mu_{JT,g}$ × NaN, +inf, −inf × $p_{wf}$ = 10 и 6 МПа) проходят `load_config` и `from_config`, `run` падает в scipy — `array must not contain infs or NaNs`, без имени параметра;
- раздел 2 (NaN в прочих полях, к DEBT-051): в 11 полях (`porosity`, `p0`, `T0`, `Rs0`, `rho_o_std`, …) — отказ «HydroSolver не сошёлся при дроблении шага до dt/512» с советом увеличить `max_retries`; в `dt_integration` — `cannot convert float NaN to integer`; в геометрии — «invalid radial grid parameters» прототипа; `start_day`, `dt_min`, `dt_max` нигде не читаются (DEBT-008).

**Шаги:**
1. Тесты (11, `TestValidationThermal`) и проверка в `io/config.py` (~13 строк).
2. P8 §5 (девять параметров), образец JSON P8, заметка о нефизичной температуре.
3. Зелёный замер пробы, vault.

**Код плана проверен подменой** (`plan_check.py`): все 6 правок применимы; новые тесты на текущем коде — 10 failed, 135 passed, на коде с правками — 145 passed; раздел 1 пробы — все 18 случаев `load_config: ValueError: thermal.<параметр> должно быть конечным числом (знак любой), …`; быстрый уровень существующих тестов на коде с правками — 1179 passed.

Ожидание: 1429 → 1440 тестов, быстрый уровень 1179 → 1190. Прототип не меняется.
