План: `vault/plans/debt-053 simulator-output-config-retry-terms.md`. Ветка: `refactor/debt-053/simulator-output-config-retry-terms`. Шагов: 6.

Решения пользователя (2026-10-10):
- `output_config` удаляется из `Simulator.__init__`, вызова `factory.py:77` и заметки `модули-simulator-оркестратор.md` (вариант А1).
- `test_retry_steps_match_their_neighbours` и `DT_WITH_RETRY` (`test_dt_convergence.py`) удаляются.

Замер при планировании (`d0a8c05`, проба `vault/issues/debt-053/probes/splitting_ex07.py`): шаг примера 07 не дробится ни при одном dt из `DT_LIST` (1800…360 с), в том числе при 1200, 720, 450, 400 с, где тест утверждал дробление. Условие удаляемого теста $e(dt) \le 2\max(\text{соседи})$ следует из `test_temperature_converges_monotonically_in_dt` ($e(dt) \le 1.5\,e(\text{крупнее})$). Механизм BUG-010 остаётся под проверкой `test_simulator.py:471` (двойник) и `test_energy_matrix_examples.py:788` (пример 10).

Расчётный код не меняется; тестов −1. Термин «A-retry» заменяется на «локальное дробление (DEBT-015)» в `test_energy_matrix_examples.py`, `test_rate_control.py`, `examples/05_standing_table_rp/closed_form_convergence.py`. Дополнения для DEBT-052 (#83) записаны в реестр: сигнатура `Simulator` без `output_config`, термин в `P8-формат-ввода-json.md:199`.
