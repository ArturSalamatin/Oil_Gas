### Контекст при открытии

- **Ветка:** `refactor/debt-069/stage-attempts-failure-report`
- **Коммит:** `6adea25` (код прототипа и адаптера — без изменений с `75dd8a7`; строки из записи реестра совпадают)
- **Мотивация:** при общем отказе `advance` отчёт ветки «открыта» ступеней 2–4 перезаписывается отчётом ветки «закрыта» и подменой DEBT-030 — причину отказа этих ступеней в BUG-028 пришлось искать отдельной пробой.
- **Затронутые модули:** `radial_blackoil/blackoil.py` (`BlackOilNewtonReport`, `advance`, `advance_fourth_stage`, `_fallback`); `gpn_multiphase_solver/hydro/prototype_adapter.py` (`_failure_details`); `CHANGELOG_1.0.3.md`, `docs/OUTPUT_FORMAT.md`; тесты `test_prototype_failure_diagnostics.py`, `test_prototype_globalization.py`, `test_prototype_stage4_memory.py`.
- **Рекомендуемый вариант:** 1 — поле `attempts` в отчёте + строка попыток в тексте отказа адаптера.
- **Оценка сложности:** средний (числа решения не меняются; основная работа — сбор попыток в `_fallback` и тексты тестов).
