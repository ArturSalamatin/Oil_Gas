## Описание

В `io/config.py` объявлено **12 полей конфига, которые никто не читает**. Они загружаются, проходят `_validate` (после DEBT-051 — только проверку «конечное число»), но на расчёт не влияют: фабрика и прототип берут вместо них свои значения. Пользователь, изменивший такое поле, не получает ни отказа, ни предупреждения и не узнаёт, что правка ничего не дала. Для `grid.type` то же касается строкового литерала: проверки допустимых значений нет.

Приоритет низкий: на корректность текущих расчётов не влияет (все примеры держат умолчания). Влияет на диагностику ошибок конфига и на доверие к спецификации — заметка P8 и докстринг `NumericsConfig` обещают поведение, которого в коде нет.

## Текущее состояние

Перечень на `26ddb34` (grep по `numerical_solver/**/*.py`, без прототипа: кроме объявлений — только тесты умолчаний):

| Поле | Объявление | Что происходит на деле | В JSON |
|---|---|---|---|
| `grid.type` | `io/config.py:33` | фабрика всегда строит `LogRadialGrid` (`factory.py:48-54`) и `RadialGrid` прототипа (`factory.py:407`) | все 32 конфига, `"log_radial"` |
| `rock.p_ref` | `io/config.py:49` | `CompressibleRock(p_ref_bar = ic.p0)` (`factory.py:411-415`); комментарий секции `:48` «Компрессия породы (пока не используется)» неверен и для `compressibility` — она передаётся (`factory.py:414`) | нет |
| `time.start_day` | `io/config.py:132` | история всегда начинается с $t = 0$; P8 (`:128-153`) обещает абсолютное время | все 32, `0.0` |
| `numerics.dt_min`, `dt_max` | `io/config.py:140-141` | дробление шага — `max_retries` в `Simulator` (DEBT-015), нижней границы подшага нет; P8 (`:199`) уже помечает поля как нечитаемые | все 32 |
| `numerics.newton_max_iter` | `io/config.py:143` | `advance(max_newton=15)` — умолчание прототипа (`blackoil.py:348`); адаптер вызывает `advance(proto_state, dt)` без лимитов (`prototype_adapter.py:105`) | нет |
| `numerics.newton_rtol`, `newton_atol` | `io/config.py:144-145` | умолчания `_newton_fixed_active_set` (`blackoil.py:315`) и `_newton_switching` (`:489`); `_advance_phases` передаёт только `max_iter` (`:452`) — допуски не провести даже через `advance` | нет |
| `numerics.max_active_set_iter` | `io/config.py:146` | `advance(max_active_iter=12)` — умолчание прототипа (`blackoil.py:348`) | нет |
| `numerics.rs_switch_tol`, `sg_switch_tol` | `io/config.py:147-148` | аргументы конструктора `RadialBlackOilModel` (`blackoil.py:65`), фабрика их не передаёт (`factory.py:428-440`) | нет |
| `output.format` | `io/config.py:169` | ни один модуль не запрашивает; `test_examples.py:200-209` запрещает поле в конфигах примеров | `configs/`: 3 файла, `"npz"` |

Итого 12 полей. Все умолчания GPN **совпадают** с умолчаниями прототипа (15, 1e-8, 1e-11, 12, 1e-5, 1e-9); `p_ref` не влияет ни на один конфиг, потому что во всех $c_r = 0$ (grep `"compressibility"` по примерам, `configs/`, `tests/data/` — ни одного вхождения).

Неверные описания:
- докстринг `NumericsConfig` (`io/config.py:139`): «передаются в Newton-солвер прототипа» (BUG-022 исправляет докстринг, поля не трогает);
- P8 (`:202`): «`newton_*`, `max_active_set_iter`, `*_switch_tol`… — передаются в RadialBlackOilModel и advance()»;
- P8 (`:128-153`): `start_day` — абсолютное время истории;
- `json-config-schema.md` (`:166-172`): проектные имена `newton_tol_abs`, `newton_tol_rel` (BUG-022, шаг 6, п. 2a — заменяет таблицу).

Смежный дефект того же рода (литерал проглатывается): `output.log_level` с опечаткой молча заменяется на `INFO` — `getattr(logging, level.upper(), logging.INFO)` (`log.py:18`).

### Воспроизведение

Проба на `26ddb34` (`configs/baseline.json`, поля подменены после `load_config`):

```python
cfg.grid.type = "ЭТО_ЧУШЬ_А_НЕ_СЕТКА"; cfg.output.format = "xlsx"
cfg.time.start_day = -1e6;            cfg.rock.p_ref = -5.0
cfg.numerics.dt_min = cfg.numerics.dt_max = -1.0
cfg.numerics.newton_max_iter = -3;    cfg.numerics.max_active_set_iter = 0
cfg.numerics.newton_rtol = cfg.numerics.newton_atol = -1.0
cfg.numerics.rs_switch_tol = cfg.numerics.sg_switch_tol = -1.0
_validate(cfg); SimulatorFactory.from_config(cfg)
```

Результат:
```
validate+factory OK
_grid LogRadialGrid
proto rs_switch_tol: 1e-05 sg_switch_tol: 1e-09 rock p_ref_bar: 200.0
NaN dt_min rejected: numerics.dt_min должно быть конечным числом, получено nan
```

Последняя строка — следствие DEBT-051: NaN в мёртвом поле теперь отвергается, хотя само поле ни на что не влияет. Запись реестра («`start_day = NaN` — расчёт проходит») описывает состояние до DEBT-051.

## Целевое состояние

Каждое поле конфига либо **влияет на расчёт** и проверяется в `_validate` (диапазон, допустимые литералы), либо **отсутствует** в dataclass. Ключи, удалённые из схемы, в старых конфигах не проглатываются молча. Спецификация (P8, `json-config-schema.md`, докстринги, README примеров) описывает фактическое поведение. Тест-страж не даёт добавить новое нечитаемое поле.

## Затронутые файлы

| Файл | Строки | Роль |
|---|---|---|
| `numerical_solver/gpn_multiphase_solver/io/config.py` | 33, 48-49, 132, 139-148, 169 | объявления полей, докстринг `NumericsConfig` |
| `numerical_solver/gpn_multiphase_solver/io/config.py` | 291-325 | `load_config`: строгая распаковка `XxxConfig(**raw[...])` — удалённое поле даёт `TypeError` на старом конфиге; образец отказа с объяснением — `save_every` (`:313-322`, DEBT-013) |
| `numerical_solver/gpn_multiphase_solver/io/config.py` | 370+ | `_validate`: проверок литералов `grid.type`, `log_level` нет |
| `numerical_solver/gpn_multiphase_solver/factory.py` | 48-54, 407-415, 428-440 | сетка; порода прототипа (`p_ref_bar = ic.p0`); конструктор `RadialBlackOilModel` |
| `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py` | 105 | `advance(proto_state, dt)` — без лимитов Ньютона |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` | 65, 315, 348, 445-452, 489 | аргументы и умолчания прототипа; `_advance_phases` не пробрасывает `rtol`/`atol` |
| `numerical_solver/gpn_multiphase_solver/log.py` | 18 | смежное: подмена неизвестного `log_level` на `INFO` |
| `numerical_solver/tests/test_config.py` | 55, 161-162, 193-198, 216-217, 281-282, 289 | тесты умолчаний мёртвых полей |
| `numerical_solver/tests/test_examples.py` | 200-209 | `test_no_dead_output_format` |
| 30 отслеживаемых JSON: `examples/*/config.json` (22), `configs/` (3), `tests/data/*/config.json` (5) | — | `grid.type`, `time.start_day`, `numerics.dt_min`, `dt_max`; `output.format` — только `configs/` |
| `numerical_solver/deliverables/rs150_for_sergey/*.json` (2, не в git) | — | те же ключи; конфиги переданы разработчику прототипа |
| README примеров 01–10, 19–21 (13 файлов) | например 03: 368-369; 19: 203-205 | «`grid.type` и `output.format` не трогать: объявлены, но не читаются» |
| `vault/knowledge/decisions/P8-формат-ввода-json.md` | 128-153, 184-202, 296-348 | спецификация полей |
| `vault/knowledge/decisions/json-config-schema.md` | 166-172 | таблица `numerics` (после BUG-022) |

## Анализ вариантов решения

### Вариант 1. Удалить все 12 полей, старые ключи — отказ с объяснением

**Суть:** убрать поля из dataclass; в `load_config` до распаковки — `ValueError` с именем ключа и причиной, по образцу `save_every`.
**Изменения:** `io/config.py`, 30 JSON, `test_config.py`, `test_examples.py`, 13 README, P8.
**Плюсы:** схема честная, ничего лишнего. **Минусы:** перестают загружаться все старые конфиги — пробы vault, переданные `deliverables/`; отказ из-за поля, которое и раньше ни на что не влияло, несоразмерен (у `save_every` отказ оправдан: молчаливый пропуск менял бы состав вывода, здесь результат не меняется). Шесть полей Ньютона теряются, хотя прототип их аргументы уже имеет.

### Вариант 2. Удалить все 12 полей, старые ключи — предупреждение в журнал и пропуск

**Суть:** как вариант 1, но известные удалённые ключи вырезаются из `raw` с `logger.warning` («поле X удалено, DEBT-008: …»). Неизвестные ключи по-прежнему дают ошибку распаковки.
**Плюсы:** старые конфиги работают, пользователь узнаёт о пропуске. **Минусы:** те же потери полей Ньютона; предупреждение на каждом запуске, пока JSON не вычищены.

### Вариант 3. Задействовать все поля

**Суть:** провести шесть полей Ньютона в прототип, `p_ref` — в `CompressibleRock`, `start_day` — сдвиг времени истории, `dt_min`/`dt_max` — границы подшага дробления, `output.format` — выбор `save_npz`/`save_csv`.
**Плюсы:** спецификация P8 выполняется. **Минусы:** `dt_min`/`dt_max` и `output.format` не имеют места в нынешней архитектуре (дробление задаёт `max_retries`, формат вывода — вызывающий код); вариант 3 из issue #23 («дробить, пока `dt_sub > dt_min`») отклонён в плане DEBT-007. `start_day` никому не нужен (во всех конфигах 0). Добавление механизмов ради полей — абстракции сверх задачи.

### Вариант 4 (рекомендуемый). Решение по каждому полю

| Поле | Решение | Обоснование |
|---|---|---|
| `newton_max_iter`, `max_active_set_iter` | провести: адаптер → `advance(..., max_active_iter, max_newton)` | аргументы у прототипа уже есть (`blackoil.py:348`) |
| `rs_switch_tol`, `sg_switch_tol` | провести: фабрика → конструктор | аргументы конструктора есть (`blackoil.py:65`) |
| `newton_rtol`, `newton_atol` | провести: `advance` → `_advance_phases` → `_newton_fixed_active_set` и `_newton_switching` | нужна правка прототипа (разрешена); тот же путь, что `cell_tol` BUG-022 |
| `rock.p_ref` | провести (`p_ref_bar = rc.p_ref`), умолчание `null` → $p_0$ | при $c_r = 0$ во всех конфигах побитово; снимает отказ конвертера VAL-005 при Reference pressure $\ne p_0$ |
| `grid.type` | проверка литерала в `_validate` (`"log_radial"`) | 32 JSON не трогать; по образцу `pvt.model`, `relperm.model` |
| `dt_min`, `dt_max`, `start_day`, `output.format` | удалить; удалённые ключи — предупреждение и пропуск (вариант 2) | смысла в архитектуре нет; убрать из 30 отслеживаемых JSON |
| `output.log_level` (смежное) | проверка литерала в `_validate` | `log.py:18` молча подменяет на `INFO` |

Умолчания проводимых полей совпадают с умолчаниями прототипа — истории примеров должны совпасть побитово. Проверки диапазонов для проведённых полей: `newton_max_iter`, `max_active_set_iter` — целое ≥ 1; допуски — > 0.

**Решить при `/plan-improve`:** проводить или удалять поля Ньютона (вариант 4 против 2 для них); `start_day` — удалить или реализовать сдвиг времени (P8); удалённые ключи — предупреждение или отказ.

## План решения

1. **Подготовка (baseline).** Выполнять после BUG-022 (#82) и DEBT-048 (#78): оба правят `blackoil.py` (`advance`, ступень 4), BUG-022 — ещё докстринг и хвост `NumericsConfig`, таблицу `json-config-schema.md` и P8. Зафиксировать число тестов, быстрый уровень, перечень мёртвых полей на новой базе.
2. **Тесты (красные).** Для каждого проводимого поля — значение доходит до модели прототипа / до `advance`; для `grid.type`, `log_level` — недопустимый литерал отвергается с именем поля; для удалённых ключей — предупреждение и успешная загрузка; страж — каждое поле dataclass-секций входит в явный перечень «читается кем» (по образцу `test_field_list_covers_known_fields`, DEBT-051).
3. **Реализация по полям** — инкрементально, по строкам таблицы варианта 4; правка прототипа — по образцу BUG-020/BUG-022, умолчания прежние, эталон регрессии прототипа побитово.
4. **Данные и документация.** 30 JSON; тесты умолчаний в `test_config.py`; `test_no_dead_output_format` — убрать или заменить стражем удалённых ключей; 13 README («не трогать» → актуальный текст); P8, `json-config-schema.md`, комментарий секции породы.
5. **Верификация.** Быстрый уровень после каждого шага, полный — в конце; истории примеров побитово совпадают с базой (умолчания не изменились).

## Ветка

`refactor/debt-008/dead-config-fields`

## Связанные issues

- Related: #82 (BUG-022 — `newton_cell_tol`, правит `NumericsConfig`; выполнять раньше)
- Related: #78 (DEBT-048 — правит `blackoil.py`; выполнять раньше)
- Related: #79 (VAL-005 — конвертер книги прототипа отвергает Reference pressure $\ne p_0$ из-за мёртвого `p_ref`)
- Related: #85 (DEBT-051 — проверка конечности числовых полей, затронула и мёртвые)
- Related: #23 (DEBT-007 — `dt_min` и вариант 3 дробления), #56 (DEBT-026 — допуск пересыщения константой из-за непереданного `rs_switch_tol`)

## Связанные заметки в vault

- `vault/roadmap/известные баги и технический долг.md` — DEBT-008
- `vault/knowledge/decisions/P8-формат-ввода-json.md`
- `vault/knowledge/decisions/json-config-schema.md`
- `vault/plans/bug-022 newton-cell-relative-tolerance.md` (решение 4, вариант D, шаг 6)
- `vault/plans/val-005 prototype-template-example.md` (мёртвый `p_ref`)
