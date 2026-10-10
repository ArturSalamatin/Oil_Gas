### Контекст при открытии

- **Ветка:** `refactor/debt-049/thermal-scalars-finite-check`
- **Коммит:** `7b34a33`
- **Мотивация:** NaN в `thermal.L_degas`, `thermal.mu_JT_oil`, `thermal.mu_JT_gas` даёт отказ scipy в СЛАУ энергии без имени параметра — сообщение должно указывать на конфиг, как у шести тепловых параметров после DEBT-047 (#76).
- **Затронутые модули:** `gpn_multiphase_solver/io/config.py` (`_validate`), `tests/test_config.py` (`TestValidationThermal`), `vault/knowledge/decisions/P8-формат-ввода-json.md` (§5).
- **Рекомендуемый вариант:** 1 — проверка конечности трёх скаляров в `_validate`, перед предупреждением о $L < 0$; вопрос о конечности остальных числовых полей (вариант 2) — при планировании.
- **Оценка сложности:** простой.
