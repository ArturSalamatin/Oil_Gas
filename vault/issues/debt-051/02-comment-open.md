### Контекст при открытии

- **Ветка:** `refactor/debt-051/config-numeric-fields-finite`
- **Коммит:** `d3aabff`
- **Мотивация:** NaN в числовом поле конфига должен давать отказ при загрузке с именем поля, а не дробление первого шага до dt/512 с советом увеличить `max_retries` (11 полей) или сообщение прототипа без имени.
- **Затронутые модули:** `gpn_multiphase_solver/io/config.py` (`_validate`, `_validate_interval`, `_expand_history`); `tests/test_config.py`; P8 §5; возможно `gpn_multiphase_solver/pvt/relperm.py` (`CoreyRP`, `n_o <= 0`).
- **Рекомендуемый вариант:** 1 — общий проход конечности по полям dataclass-секций, поля истории — в `_validate_interval` и `_expand_history`; диапазонные проверки не меняются.
- **Оценка сложности:** простой.
