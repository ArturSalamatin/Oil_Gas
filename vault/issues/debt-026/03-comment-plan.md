### План готов

План: `vault/plans/debt-026 rs-check-any-pressure-history.md`. Ветка: `refactor/debt-026/rs-check-any-pressure-history`. Шагов: 7.

**Решения пользователя (2026-10-03):**
- однофазные ячейки: только $R_s \le R_s^{eq}(p)$ (вариант 2); число ячеек с $R_s > R_{s,0}$ печатается как наблюдение, не как нарушение;
- `rs_profiles.png`: кружки $R_s^{eq}(p)$ только в двухфазных ячейках (`regime == 1`) + линия $R_{s,0}$;
- вертикальная линия: «фронт $r_b$», если маски $p < p_b$ и `regime == 1` совпадают, иначе «изобара $p_b$» (ожидается у 04a, 12, 13b);
- README: сводный `examples/README.md`, 03 (описание рисунка), 04, 04a, 05, 12, 13b; утверждения в 03 §3, 19, 20, 21 не трогаются. Плюс фраза докстринга `pvt_plot._physical_rs`.

**Шаги:**
1. Скрипт замера `vault/issues/debt-026/probes/rs_check_numbers.py` и замер до правки — гейт: маски `regime == 1` и $S_g > 10^{-12}$ совпадают у всех 18 примеров с газом, ячейки $p < p_b$ образуют префикс.
2. `rs_analytics.py`: `rs_error` по двухфазным, новая `rs_supersaturation`, `RS_TOL = 1e-10`, новый `_draw_rs` и `report_rs`; `rs_expected`, `front_radius`, `make_overlay_rs` — прежние. Тесты `tests/test_rs_analytics.py` (10, быстрый уровень, синтетические состояния на PVT примеров 04 и 03).
3. Общий slow-тест `TestSharedChecks::test_rs_check_all_two_phase_examples`: у 18 примеров ошибка в двухфазных $\le 10^{-10}$, пересыщенных 0; у 12 и 13b однофазных ниже $p_b$ $\ge 1$.
4. Докстринг `pvt_plot._physical_rs`.
5. Замер после правки (блоки решения побитово равны замеру до), визуальная проверка `rs_profiles.png` у 03, 04a, 12, 13b.
6. README.
7. Vault.

**Тесты:** 1210 → 1221 (быстрый уровень 987 → 997). Ядро решателя и прототип не меняются.

**Обнаружено:** DEBT-037 — `SHARED_CHECK_MODULES` не защищает `rs_analytics.py`, `closed_form.py`, `relperm_plot.py`, `figure_io.py` от копий в папках примеров.
