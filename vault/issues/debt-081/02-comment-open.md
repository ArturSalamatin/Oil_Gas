### Контекст при открытии

- **Ветка:** `refactor/debt-081/grid-n-integer-check`
- **Коммит:** `4b67213` (воспроизведение; код `io/config.py` и `grid/log_radial.py` с замера в реестре на `55868a6` не менялся)
- **Мотивация:** `grid.N` — единственное поле конфига с аннотацией `int` без проверки на целое; `"N": true` даёт расчёт на сетке из одной ячейки без сообщения.
- **Затронутые модули:** `gpn_multiphase_solver/io/config.py` (`_validate`), `tests/test_config.py` (`TestValidationGrid`)
- **Рекомендуемый вариант:** 1 — проверка `isinstance(N, bool) or not isinstance(N, int) or N < 1` в `_validate`, в том же виде, что у `newton_max_iter`; предохранитель `LogRadialGrid` не трогаем
- **Оценка сложности:** простой
