## Реализация завершена

**Ветка:** `refactor/debt-051/config-numeric-fields-finite` (worktree `.worktrees/debt-051`, от `numerical_scheme/implementation` `3dd0638`)
**План:** `vault/plans/debt-051 config-numeric-fields-finite.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-051/config-numeric-fields-finite`

### Изменения
- `numerical_solver/gpn_multiphase_solver/io/config.py`: `_require_finite_number(value, name)` — число (не строка, `null`, bool) и конечное, иначе `ValueError` с именем; `_check_numeric_fields(obj, where)` — поля `float` / `Optional[float]` dataclass-секции по аннотациям (новое поле — без правки кода) и любое значение `float` в поле другого типа. Вызовы: в начале `_validate` по всем секциям (включая `thermal`; цикл конечности DEBT-049 удалён), в начале `_validate_interval` (`history[i].<поле>`), в `_expand_history` для `duration`, `dt_out` до `round`. Диапазоны не менялись.
- `numerical_solver/tests/test_config.py`: класс `TestValidationNumbers`, 98 тестов — NaN и inf в каждом из 37 float-полей, нечисловые значения, NaN в `grid.N`, поля интервалов истории, краткая форма, целые числа, страж списка полей.
- `vault/knowledge/decisions/P8-формат-ввода-json.md`: §5 — тип и конечность всех чисел.
- Заметки: «NaN и inf в числовых полях конфига давали отказ через dt/512 …» (новая), заметка DEBT-049 — цикл заменён общим проходом.

### Тесты
- Было: 1493 (база после DEBT-053; план считал от 1494 — DEBT-053 убрал один тест)
- Стало: 1591 (+98 новых); быстрый уровень 1341 passed, полный — 1591 passed (524 с)
- Все зелёные: ✅

### Замер (`vault/issues/debt-051/probes/`)
| Случай | До (`red_state.out.txt`) | После (`green_state.out.txt`) |
|---|---|---|
| `skin` = ±inf, `p_wf` = +inf | расчёт без добычи, молча | `load_config: ValueError` с именем |
| `min_bhp` = NaN, ограничение активно | ограничение снято: забой 7.12 МПа при 15 МПа | `ValueError: history[0].min_bhp …` |
| NaN в 13 полях | отказ через dt/512 с советом про `max_retries` | `ValueError` с именем |
| строка, `null`, `true` | `TypeError` без имени / 1 м² | `ValueError: … должно быть числом` |
| всего испорченных случаев | — | 58 из 58 — отказ при загрузке |
| 4 эталонных расчёта | ПРОШЛИ | построчно так же |

Не закрыто (вне задачи): конечные абсурдные значения (`skin` = 1e6, `p_wf` = 1e12) и отрицательный скин стимулированной скважины ($s$ = −0.5 → $T_w < 0$, отказ через dt/512) — DEBT-056.
