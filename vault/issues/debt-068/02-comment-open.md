### Контекст при открытии

- **Ветка:** `refactor/debt-068/rock-compressibility-sign`
- **Коммит:** `40a6acb`
- **Мотивация:** $c_r < 0$ проходит проверку ввода молча (прототип его отвергает), а при $c_r < -c_o$ коэффициент $C_p$ уравнения давления отрицателен — некорректная задача, механизм BUG-019.
- **Затронутые модули:** `gpn_multiphase_solver/io/config.py` (`_validate`); `tests/test_config.py` (`TestValidationRock`); `vault/knowledge/decisions/P8-формат-ввода-json.md` §5; `vault/knowledge/decisions/json-config-schema.md`. По решению в плане — `radial_blackoil/rock.py` (вариант 3), `examples/18_prototype_input/prototype_input.py` (вариант 4).
- **Сдвиги строк относительно записи в реестре (`3f3df63` → `40a6acb`):** `_validate`, порода — `config.py:519-523`; поле `compressibility` — `:56`; `_warn_negative_compressibility` — `factory.py:308`; `CompressibleRock` — `factory.py:420-424`; $C_p$ и условие $C_p \ge 0$ — `problem_statement.tex:603`, `:605-606`.
- **Рекомендуемый вариант:** 1 (отказ `ValueError` в `_validate` с именем поля).
- **Оценка сложности:** простой.
