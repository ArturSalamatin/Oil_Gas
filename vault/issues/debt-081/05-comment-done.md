## Реализация завершена

**Ветка:** `refactor/debt-081/grid-n-integer-check` (worktree `.worktrees/debt-081`, от `numerical_scheme/implementation` `42ef497`)
**План:** `vault/plans/debt-081 grid-n-integer-check.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-081/grid-n-integer-check`

### Изменения
- `numerical_solver/gpn_multiphase_solver/io/config.py`: в `_validate` условие `N < 1` заменено на `isinstance(N, bool) or not isinstance(N, int) or N < 1`. Отказ — `ValueError("grid.N должен быть целым ≥ 1, получено …")` при загрузке конфига, до сборки решателя, как у `numerics.newton_max_iter`. Комментарий ссылается на замер. `100.0` к 100 не приводится.
- `numerical_solver/tests/test_config.py`:
  - `TestValidationGrid`: `test_N_not_positive_integer_rejected` (8 случаев: `true`, `false`, `"100"`, `null`, `100.0`, `100.5`, `0`, `-1`) и `test_N_one_accepted`.
  - `TestValidationNumbers`: страж целых полей по аннотациям — `_INT_FIELDS`, `test_int_field_rejects_non_integer` (5 полей × `true`/`2.5`) и `test_int_field_list_covers_known_fields`. На коде до правки страж падал ровно на `grid.N`.
- `vault/knowledge/decisions/P8-формат-ввода-json.md`, заметка о переводе книги — правило `grid.N` и страж.

Тело issue (вариант 1, «минус») говорит, что о новом целом поле напомнит страж `test_field_list_covers_known_fields`. Это неверно: тот страж отбирает только `float`-поля. Исправлено аудитом 1 — добавлен страж целых полей.

### Тесты
- Было: 2401 тест (база `42ef497`); быстрый уровень — 2124 passed, 1 skipped.
- Стало: 2421 (+20; `test_config.py` 338 → 358); быстрый — 2144 passed, 1 skipped, 152 с; полный — 2420 passed, 1 skipped, 617 с.
- Пропуск — `test_xlsx_reader.py:476`: в worktree нет черновика книги руководителя, он не в git.
- Все зелёные: ✅

### Проба (`vault/issues/debt-081/probes/green_state.out.txt`, пример 01, 2 ч)
| `grid.N` | До | После |
|---|---|---|
| `150` | 150 ячеек, `q_o` = 167.847 м³ст/сут, `T_wf` = 349.4773 К | то же |
| `true` | расчёт на 1 ячейке молча, `T_wf` в 2.24 м от оси | `ValueError: grid.N должен быть целым ≥ 1, получено True` |
| `"100"`, `null` | `TypeError` без имени поля | `ValueError … получено '100'` / `None` |
| `100.0`, `100.5` | отказ `LogRadialGrid` по-английски при сборке решателя | `ValueError … получено 100.0` / `100.5` |
| `false`, `0`, `-1` | `ValueError: N должен быть ≥ 1 …` | `ValueError: grid.N должен быть целым ≥ 1 …` |
| `NaN` | `grid.N должно быть конечным числом` | то же |

`LogRadialGrid`, перевод книги, прототип и `CHANGELOG.md` не тронуты. Истории примеров не меняются: правка касается только проверки ввода.
