## Реализация завершена

**Ветка:** `refactor/debt-008/dead-config-fields` (worktree `.worktrees/debt-008`, от `numerical_scheme/implementation` `2dbec0e`)
**План:** `vault/plans/debt-008 dead-config-fields.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-008/dead-config-fields`

### Изменения
- `io/config.py`: удалены `rock.p_ref`, `time.start_day`, `numerics.dt_min`, `dt_max`, `newton_rtol`, `newton_atol`, `output.format`; старый ключ — предупреждение после `_validate` и пропуск (`_drop_removed_keys`, порядок DEBT-056); проверки `grid.type`, `output.log_level`, лимитов Ньютона (целые ≥ 1) и допусков переключения фаз (> 0); комментарии полей — кто их читает.
- `factory.py`: `rs_switch_tol`, `sg_switch_tol` → конструктор `RadialBlackOilModel`; лимиты → адаптер; допуск проверки старта — `numerics.rs_switch_tol` (константа `_RS0_SUPERSAT_TOL` удалена).
- `hydro/prototype_adapter.py`: параметры `max_newton`, `max_active_iter` (умолчания = умолчаниям `advance`), передаются в `advance` и `advance_fourth_stage`.
- `examples/rs_analytics.py`: допуск пересыщения — `config.numerics.rs_switch_tol` (константа `RS_TOL` удалена).
- `examples/18_prototype_input/prototype_input.py`: конвертер не пишет `start_day`.
- 31 JSON-конфиг (примеры, `configs/`, `tests/data/`) без удалённых ключей; 17 README примеров; P8, `json-config-schema.md` и 5 заметок vault.
- Прототип не менялся.

### Тесты
- Было: 1722 (быстрый уровень 1451)
- Стало: 1741 (+19: +28/−16 `test_config.py`, +3 фабрика, +3 адаптер, +1 `rs_analytics`; замена параметризованного теста в `test_examples.py`)
- Полный прогон: 1741 passed, 540 с ✅; быстрый уровень: 1470 passed

### Проверка
| Пункт пробы `red_state.py` | До | После |
|---|---|---|
| 12 абсурдных значений | `_validate` и фабрика проходят | отказ `grid.type` |
| `log_level = 'DEBG'` | молча `INFO` | отказ `output.log_level` |
| `rs_switch_tol = 1e-6`, избыток 3e-6 | старт принят (1e-5 зашит) | отказ «пересыщено» |
| лимиты 7/5, допуски 2e-5/3e-9 | до прототипа не доходят | у адаптера 7/5, у модели 2e-05/3e-09 |
| старый конфиг со `start_day`, `dt_min`, `dt_max` | загружен молча | загружен, 3 предупреждения |

Истории примеров прежние: передаваемые значения по умолчанию совпадают с умолчаниями прототипа (тест `test_defaults_match_prototype`).
