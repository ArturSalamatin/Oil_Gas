## Описание

Литерал JSON `NaN` (и `Infinity`) в числовых полях конфига, кроме девяти тепловых, проходит проверку ввода `load_config`. Почти все проверки записаны как `if v <= 0: raise`, а сравнение с NaN всегда ложно. Дальше расчёт отказывает, но по-разному и чаще всего с сообщением, которое уводит от конфига. Хуже всего с 11 полями: решатель дробит первый шаг девять раз до dt/512 и советует увеличить `numerics.max_retries` или уменьшить `time.dt_integration`, хотя ошибка во вводе.

Молча неверного расчёта не найдено: каждый NaN, который доходит до счёта, даёт отказ. Приоритет низкий: страдают сообщение и время до отказа.

## Текущее состояние

Замер — проба `vault/issues/debt-049/probes/red_state.py`, раздел 2 (`red_state.out.txt`, база `7b34a33`; `configs/baseline.json`, одно поле = NaN, 24 ч при $p_{wf}$ = 6 МПа). Повторён на ветке DEBT-049 (`green_state.out.txt`) — построчно так же.

| Поля | Где отказ | Сообщение |
|---|---|---|
| `rock.porosity`, `pvt.rho_o_std`, `pvt.rho_g_std`, `pvt.co_undersaturated`, `relperm.n_o`, `relperm.n_g`, `initial_conditions.p0`, `T0`, `Rs0`, `numerics.skin`, `history[*].p_wf` (11) | `run`, после дробления до dt/512 (`simulator.py:258`) | `HydroSolver не сошёлся при дроблении шага до dt/512 …` + совет про `max_retries` и `dt_integration` — **ложный след** |
| `time.dt_integration`, `history[*].dt` | `run` (`simulator.py:75`, `int(np.ceil(dt_hist / dt_integration))`) | `ValueError: cannot convert float NaN to integer` |
| `geometry.r_well`, `R_ext`, `h`, `rock.permeability` | `from_config`, прототип (`HydroSolverPrototype/.../radial_blackoil/grid.py:7-8`) | `invalid radial grid parameters` — без имени поля |
| `relperm.S_or`, `S_gc`, `kro_max`, `krg_max` | `from_config`, наш `CoreyRP` (`gpn_multiphase_solver/pvt/relperm.py:13-22`) | английский текст; имя есть у `S_or`, `S_gc`, у `kro_max`/`krg_max` — общее |
| `time.start_day`, `numerics.dt_min`, `numerics.dt_max` | — | расчёт проходит, числа как у эталона: поля нигде не читаются (DEBT-008) |

Почему так: `_validate` (`io/config.py:334-438`) и `_validate_interval` (`:441-473`) проверяют диапазоны условиями вида `v <= 0`, `v < 0`, `v <= 0 or v > 1` — NaN их проходит. Проверки, записанные «от противного», NaN ловят: прототип `not (0 < rw < re and …)` (`grid.py:7`), `CoreyRP` `not (0 <= S_or < 1)` (`relperm.py:13`), девять тепловых параметров `not (0 < v < inf)` / `not (-inf < v < inf)` (DEBT-047, DEBT-049). Но `CoreyRP` проверяет `n_o <= 0 or n_g <= 0` (`relperm.py:19`) — NaN снова проходит.

Не замерено, по коду:
- `rock.compressibility`, `rock.p_ref` (последнее не читается, DEBT-008), `numerics.newton_rtol`, `newton_atol`, `rs_switch_tol`, `sg_switch_tol` (не передаются прототипу, DEBT-008) — проверок нет вовсе;
- `history[*].q_oil`, `min_bhp` (`control = "rate"`, `config.py:460, 465`) — `v < 0`, `v <= 0`, NaN проходит;
- краткие формы истории: `duration`, `dt_out` — `<= 0` (`config.py:233, 236`), затем `round(duration / dt)` (`:239`) — `ValueError: cannot convert float NaN to integer` в `load_config` без имени поля;
- `+inf`: проходит все проверки вида `v <= 0` (например `permeability = Infinity`), дальнейший путь не проверялся;
- строка или `null` в числовом поле — `TypeError` в первом сравнении, без имени поля.

Попутно: сообщения `_validate` для геометрии, породы и начальных условий называют поле без секции (`r_well должен быть > 0`), тепловые (DEBT-047, DEBT-049) и `numerics.max_retries` — с секцией.

## Целевое состояние

Не конечное число в любом числовом поле конфига — `ValueError` при загрузке с полным именем поля (`geometry.r_well`, `history[3].p_wf`). Диапазонные проверки остаются там, где они сейчас (`_validate`, прототип, `CoreyRP`) — P8 §5 отдаёт проверку гидродинамических данных прототипу; конечность — общая проверка ввода, она не зависит от модели.

## Затронутые файлы

| Файл | Строки | Роль |
|---|---|---|
| `numerical_solver/gpn_multiphase_solver/io/config.py` | 17-189 | dataclass-секции: перечень полей и типов |
| там же | 215-266 | `_expand_history`: `duration`, `dt_out`, `round(duration / dt)` |
| там же | 334-438 | `_validate`: проверки вида `v <= 0`; девять тепловых — образец |
| там же | 441-473 | `_validate_interval`: `dt`, `p_wf`, `q_oil`, `min_bhp`; номер объекта JSON в `where` |
| `numerical_solver/gpn_multiphase_solver/pvt/relperm.py` | 13-22 | `CoreyRP`: `n_o <= 0 or n_g <= 0` пропускает NaN |
| `numerical_solver/gpn_multiphase_solver/simulator.py` | 75, 258, 313-332 | место отказа и текст с советом про `max_retries` (не меняется) |
| `numerical_solver/tests/test_config.py` | — | новые тесты |
| `vault/knowledge/decisions/P8-формат-ввода-json.md` | §5 | описание проверок ввода |

## Анализ вариантов решения

### Вариант 1. Общий проход конечности по полям dataclass-секций (рекомендуется)

- **Суть.** В начале `_validate` — обход секций (`geometry`, `grid`, `rock`, `pvt`, `relperm`, `thermal`, `initial_conditions`, `time`, `numerics`) через `dataclasses.fields`; каждое значение типа `float` проверяется условием `-inf < v < inf`, отказ — `ValueError(f"{секция}.{поле} должно быть конечным числом, получено {v}")`. Поля истории — тем же условием в `_validate_interval` (`where` уже несёт номер объекта JSON) и `duration`/`dt_out` — в `_expand_history` до `round`. Диапазонные проверки не меняются.
- **Изменения.** `io/config.py` — ~20 строк; `test_config.py` — параметризованный тест по всем числовым полям (NaN, ±inf) и по полям истории.
- **Плюсы.** Закрывает все поля разом, включая будущие; не трогает распределение диапазонных проверок между `_validate` и прототипом (P8 §5); сообщения единообразны.
- **Минусы.** Отказ и для мёртвых полей (`start_day`, `dt_min`, `dt_max`, `p_ref`, `newton_*`) — безвредно, но решение по ним — DEBT-008. Значения типа `int` в float-поле (JSON `3600`) пропускаются — они конечны.

### Вариант 2. Переписать каждую проверку «от противного»

- **Суть.** `if v <= 0` → `if not (0 < v < inf)` во всех местах; добавить проверки полям без проверок (`rho_o_std`, `co_undersaturated`, `skin`, `compressibility`, …).
- **Плюсы.** Конечность и диапазон в одном условии; заодно сообщения можно привести к `<секция>.<поле>`.
- **Минусы.** Перечень полей ведётся руками — новое поле снова без проверки; диапазоны полей гидродинамики (`rho_o_std > 0`? `skin` любой знак?) пришлось бы решать здесь же, а P8 §5 отдаёт их прототипу. Больше правок и тестов.

### Вариант 3. Запрет литералов `NaN`/`Infinity` при разборе JSON

- **Суть.** `json.load(f, parse_constant=...)`.
- **Минусы.** Без имени поля — ради имени задача и заведена; `1e999` модуль `json` превращает в `inf` через `float()` и `parse_constant` не вызывает (проверено при DEBT-049). Отклонён в DEBT-049 по тем же причинам.

**Рекомендация:** вариант 1. Решить при планировании:
- проверять ли заодно тип (строка, `null` в числовом поле → `ValueError` с именем вместо `TypeError`): аннотации dataclass дают ожидаемый тип;
- исправлять ли `CoreyRP` (`n_o <= 0` → `not (n_o > 0)`) — после варианта 1 NaN туда не дойдёт из конфига, но класс используется и напрямую;
- приводить ли сообщения `_validate` к `<секция>.<поле>`.

## План решения

1. **Исходный замер.** Число тестов, быстрый уровень. Красная проба — раздел 2 пробы DEBT-049, дополненный не замеренными полями (`compressibility`, `p_ref`, `newton_*`, `q_oil`/`min_bhp` при `control = "rate"`, `duration`/`dt_out`, `+inf` в нескольких полях).
2. **Реализация.** Тесты (красные) → общий проход конечности в `_validate` → поля истории в `_validate_interval` и `_expand_history` → P8 §5.
3. **Верификация.** Быстрый и полный уровни; все конфиги примеров загружаются (`test_load_config_passes`); зелёная проба — все случаи раздела 2 отказывают в `load_config` с именем поля, эталон без изменений.

## Ветка

`refactor/debt-051/config-numeric-fields-finite`

## Связанные issues

Related: #81 (DEBT-049 — конечность $L$, $\mu_{JT}$; эта задача — его вариант 2), #76 (DEBT-047 — проверка шести тепловых параметров)

## Связанные заметки в vault

- `vault/roadmap/известные баги и технический долг.md` — записи DEBT-051, DEBT-008 (мёртвые поля конфига, в том числе `start_day`)
- `vault/plans/debt-049 thermal-scalars-finite-check.md` — раздел «Обнаруженные проблемы»
- `vault/issues/debt-049/probes/red_state.py`, `red_state.out.txt` (раздел 2) — замер
- `vault/knowledge/decisions/P8-формат-ввода-json.md` — §5 «Валидация»
- `vault/knowledge/debugging/положительный μ_JT нефти — след знака ε из литературы; тепловые скаляры проверяются на конечность при загрузке.md`
