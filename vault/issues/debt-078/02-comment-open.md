### Контекст при открытии

- **Ветка:** `refactor/debt-078/co-undersaturated-table-check`
- **Коммит:** `8ddb08d`
- **Мотивация:** заданная при табличном PVT сжимаемость нефти $c_o$ молча не используется, тогда как соседняя опция Стендинга `mu_o_undersaturated` в том же случае даёт отказ; знак $c_o$ не проверяется, хотя у $c_r$ — отказ (DEBT-068).
- **Затронутые модули:** `factory.py` (`create_pvt`), `io/config.py` (`_validate`, `PVTConfig`), `tests/test_factory_standing_hydro.py`, `tests/test_config.py`, `numerical_solver/README.md` (п. 3.1), `P8-формат-ввода-json.md` (§5).
- **Рекомендуемый вариант:** 1 + 3 — отказ в `create_pvt` при таблице и $c_o \ne 0$, отказ в `_validate` при $c_o < 0$.
- **Оценка сложности:** простой (две проверки, +3…5 тестов, истории примеров не меняются).
