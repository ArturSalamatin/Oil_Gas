---
tags:
  - план
  - реструктуризация
date: 2026-10-10
issue: DEBT-050
github: 80
branch: refactor/debt-050/orchestrator-note-local-splitting
status: в процессе
worktree: .worktrees/debt-050
audit:
  date: 2026-10-10
  found: 8
  auto-fixed: 8
  manual-required: 0
---

# DEBT-050: заметка `модули-simulator-оркестратор` по коду после DEBT-015

Подтип: **реструктуризация документации** — правится один файл vault, код не меняется.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай правимую заметку `vault/knowledge/decisions/модули-simulator-оркестратор.md` (199 строк) и источник истины — `numerical_solver/gpn_multiphase_solver/simulator.py:91-350`.
3. Для справки (не править): `vault/knowledge/decisions/P4-адаптивный-шаг.md` (строки 1-80 — алгоритм G1a), `vault/knowledge/decisions/контейнер-simulation-history.md`.
4. Ветка `refactor/debt-050/orchestrator-note-local-splitting` от `numerical_scheme/implementation`, worktree `.worktrees/debt-050` (контракт `/implement`).
5. Baseline из `numerical_solver/` worktree: `.venv\Scripts\python -m pytest tests/ --collect-only -q` — **записать число**: 1429 на `7b34a33`/`81d1474` (замер 2026-10-10); если к старту влит DEBT-046 (в работе, `.worktrees/debt-046`, добавляет 52 теста) — 1481. Критерий — число после правки равно числу до неё, а не константе. Быстрый уровень не нужен: код не меняется.
6. Шаги 2–8 правят только заметку; после каждого — сверка правленого фрагмента с кодом (поле «Проверка»).

## Контекст

`Simulator` (`numerical_solver/gpn_multiphase_solver/simulator.py`) — оркестратор: цикл по времени, вызовы гидродинамики (`HydroSolver`) и энергии (`EnergySolver`), накопители балансов, запись истории. DEBT-015 (#61, влит `e684ee2` 2026-10-08) перенёс дробление шага из гидро-адаптера в `Simulator._advance` и сделал его **локальным** (алгоритм G1a): шаг $dt$ меряется в целых единицах наименьшего подшага `dt/2**max_retries`; подшаг, на котором гидродинамика бросила `HydroConvergenceError`, делится пополам и повторяется из того же состояния; после удачи подшаг удваивается, если пройденная часть кратна удвоенному подшагу. DEBT-015 добавил параметр конструктора `max_retries` и не тронул заметку-справочник `модули-simulator-оркестратор.md`. DEBT-047 (#76) дописал в неё пункт о `_check_temperature` уже в терминах DEBT-015 — его не трогать.

Решение пользователя 2026-10-10 (при планировании): править **всю заметку оркестратора** — пункты реестра и попутно найденные расхождения в разделах `TimeSchedule`, `SimulationHistory`, фабрика. Соседние заметки — только в «Обнаруженных проблемах», без правки.

## Расхождения заметки с кодом (на `7b34a33`; до `81d1474` код и заметка не менялись)

| # | Заметка | Сейчас написано | Код | Шаг |
|---|---|---|---|---|
| 1 | `:3` | description: «…адаптация dt…» | дробление локальное, DEBT-015 | 2 |
| 2 | `:20-23` | `__init__` без `max_retries` | `max_retries: int = 9` (`simulator.py:102`) | 3 |
| 3 | `:56` | «двухуровневый цикл» | три уровня: интервалы → шаги $dt$ → подшаги $h$ в `_advance` | 4 |
| 4 | `:58-91` | гидро и энергия прямо в `run`; `self._energy.solve(hydro_result, state, dt, interval.bc.T_ext)` | `run` вызывает `_advance(state, dt, interval.bc, balance, mass)` (`:175-176`); `energy.solve(hydro_result, state, h, bc, collect=balance)` (`:270-271`) | 4 |
| 5 | `:62` | начальный `append` без `mass_balance` | `mass_balance=self._mass_snapshot(mass, state)` (`:152-158`) | 4 |
| 6 | `:58-91` | нет `_advance`, `_failure_message`, `_check_temperature` | `:205-311`, `:313-332`, `:334-350` | 4 |
| 7 | `:96` | «`interval.bc.T_ext` — T_ext берётся из BC» | `energy.solve` получает весь `bc` (`energy/base.py:27-30`) | 4 |
| 8 | `:105-106` | «пробный шаг при дроблении отброшен раньше» | пробного шага нет: отказ до накопителей (`:250-260`) | 4 |
| 9 | `:141` | `substeps(self, k: int)` | `substeps(self, interval_idx: int)` (`:64`) | 5 |
| 10 | `:146` | `def n_intervals(self) -> int` | `@property` (`:84-86`) | 5 |
| 11 | `:155-165` | `SimulationHistory` с 4 полями; `append(self, t, state, hydro, well)`; `def n_saved` | поля `balance`, `mass_balance` (`state.py:162-163`); `append(..., balance=None, mass_balance=None)` (`:165-168`); `n_saved` — `@property` (`:182-183`) | 6 |
| 12 | `:178` | `hydro = PrototypeHydroAdapter(...)` | `hydro = _create_prototype_hydro(config, grid, pvt, relperm)` (`factory.py:66`) | 7 |
| 13 | `:181` | `Simulator(grid, hydro, energy, pvt, schedule, config.output)` | `max_retries=config.numerics.max_retries` (`factory.py:75-78`) | 7 |
| 14 | `:188` | помощники без `_create_prototype_hydro` | `factory.py:383` | 7 |
| 15 | `:192-198` | нет ссылок на P4 и заметку о локальном дроблении | — | 8 |
| 16 | `:124`, `:151` | `HistoryInterval` содержит `dt`, `control`, `p_wf` | ещё `q_oil`, `min_bhp` — управление по дебиту нефти, FEAT-020 (`io/config.py:111-124`) | 5 |
| 17 | `:127` | `HistoryInterval.control + p_wf` → `WellControl` | `"pressure"` → `PressureControl(p_wf)`, `"rate"` → `RateControl(q_oil, min_bhp)` (`factory.py:634-642`) | 5 |

Верно, не правится: `:10-19` (docstring класса), `:33-52` (`SimulationState`, начальное состояние), `:119-123`, `:128-140`, `:148-150`, `:179-180`, `:182-186`, `:190`. Верно по смыслу, но переносится в новый текст шага 4 с правкой формулировок: `:93-104`; дословно — `:109-115` (DEBT-047). Шаг 3 дописывает строки после `:32`.

## Варианты

**A. Точечная правка пунктов реестра** (сигнатура, вызов в фабрике, псевдокод `run`, «пробный шаг»). Минимальный diff; разделы `TimeSchedule` и `SimulationHistory` остаются устаревшими — следующий читатель найдёт то же. Отклонён пользователем.

**B. Псевдокод заменить ссылками на строки кода.** Меньше поводов для расхождений, но заметка теряет самодостаточность, а номера строк устаревают так же, как псевдокод. Отклонён.

**C (выбран). Вся заметка по коду.** Псевдокод `run` и сокращённый псевдокод `_advance` (без журналирования), все расхождения таблицы, ссылки на [[P4-адаптивный-шаг]] и заметку о локальном дроблении. Один файл, ~90 строк правки.

## Подводные камни (чеклист 2.5)

- ✅ **Call sites / import-ы / циклы / configs / прототип** — код не меняется.
- ✅ **Тесты** — не меняются; число тестов 1429 до и после.
- ⚠️ **Псевдокод ≠ код.** Риск — переписать по памяти и внести новое расхождение. Адресовано: каждый блок «После» ниже сверен с `simulator.py` на `7b34a33`; шаг 9 — сверка grep-ом. Нумерация шагов в псевдокоде `_advance` (1, 2, 2a, 3) повторяет комментарии кода (`simulator.py:249, 266, 273, 284`), чтобы читатель находил место.
- ⚠️ **Wiki-ссылки.** Имя заметки о локальном дроблении длинное, с «—» (длинное тире) и «dt_integration»; опечатка даст висячую ссылку. Адресовано: копировать имя из Glob (шаг 9).
- ✅ **Связь с другими задачами** — DEBT-048 (#78) меняет адаптер (`m2s`), не `Simulator`; конфликта по файлам нет. Других открытых задач на `simulator.py` нет.
- ✅ **Пункт DEBT-047** (`:109-115`) уже в терминах DEBT-015 — не трогать.
- ⚠️ **Комментарии кода ≠ код.** `simulator.py:109, 119-121` утверждают, что `output_config` нужен ради `log_level` и `format`, но `Simulator` его не хранит. Адресовано: шаг 3 описывает фактическое поведение, комментарий — «Обнаруженные проблемы», п. 5 (аудит 2026-10-10).
- ⚠️ **Параллельная задача DEBT-046** (worktree `.worktrees/debt-046`, ветка `refactor/debt-046/examples-scripts-import-check`): правит тесты и `examples/`, число тестов после её влития — 1481. Заметку оркестратора и `simulator.py` не трогает (grep её плана). Адресовано: baseline — число на старте, критерий «до = после»; шаг 1 — `git diff --stat` от `81d1474` по файлам-источникам. Реестр техдолга правят обе задачи в разных секциях — конфликт при `/merge` маловероятен.

## Шаги

Номера строк — по файлу до правки. Шаги идут сверху вниз по файлу; после правки верхнего раздела нижние строки сдвигаются — искать по тексту `old_string`, а не по номеру.

### Шаг 1: Подготовка

**Цель:** worktree, baseline.

**Что сделать:** по контракту `/implement` — коммит плана в базу, worktree `.worktrees/debt-050` на ветке `refactor/debt-050/orchestrator-note-local-splitting`; из `numerical_solver/` worktree `.venv\Scripts\python -m pytest tests/ --collect-only -q` — записать число (1429 до влития DEBT-046, 1481 после). Проверить, что код не ушёл от плана: `git diff --stat 81d1474 HEAD -- numerical_solver/gpn_multiphase_solver/simulator.py numerical_solver/gpn_multiphase_solver/factory.py numerical_solver/gpn_multiphase_solver/state.py numerical_solver/gpn_multiphase_solver/io/config.py "vault/knowledge/decisions/модули-simulator-оркестратор.md"` — пусто; иначе сверить номера строк плана с кодом заново.

**Проверка:** число тестов записано; diff пуст.

**Оценка:** ~5 мин.

### Шаг 2: Шапка заметки

**Цель:** description и плашка о пересмотре.

**Файлы:** `vault/knowledge/decisions/модули-simulator-оркестратор.md`

**Контекст:** frontmatter `description` используется при поиске заметок; слова «адаптация dt» описывают отменённую схему. Плашка — по образцу `P4-адаптивный-шаг.md:10-15`.

**Изменения:**

До (`:3`):
~~~
description: Simulator (Mediator) — цикл по времени, расписание BC, адаптация dt, SimulationState, SimulationHistory
~~~
После:
~~~
description: Simulator (Mediator) — цикл по времени, расписание BC, локальное дробление шага в _advance (DEBT-015), SimulationState, SimulationHistory
~~~

До (`:8`):
~~~
# Simulator — оркестратор (Mediator)
~~~
После:
~~~
# Simulator — оркестратор (Mediator)

> **Обновлено 2026-10-10 ([[DEBT-050]]):** цикл шага, конструктор, фабрика и `SimulationHistory` — по коду после [[DEBT-015]] (локальное дробление в `Simulator._advance`, параметр `max_retries`) и [[DEBT-047]] (`_check_temperature`).
~~~
(Дату заменить на дату реализации.)

**Проверка:** Регресс: не нужен (документ). Frontmatter валиден: три строки `name`/`description`/`metadata`, без двоеточий вне значения.

**Оценка:** ~4 строки, 3 мин.

### Шаг 3: Раздел «Класс Simulator» — сигнатура с `max_retries`

**Цель:** сигнатура `__init__` как в `simulator.py:98-102`, смысл параметра.

**Контекст:** `max_retries` — глубина дробления: наименьший подшаг `dt/2**max_retries`. Фабрика передаёт `config.numerics.max_retries`; `_validate` (`io/config.py:404-411`) требует целое в $[0, 20]$; по умолчанию 9 (`io/config.py:160`).

**Изменения:**

До (`:20-24`):
~~~
    def __init__(self, grid: Grid, hydro: HydroSolver,
                 energy: EnergySolver, pvt: HydroPVT,
                 schedule: TimeSchedule,
                 output_config: OutputConfig | None = None):
        ...
~~~
После:
~~~
    def __init__(self, grid: Grid, hydro: HydroSolver,
                 energy: EnergySolver, pvt: HydroPVT,
                 schedule: TimeSchedule,
                 output_config: OutputConfig | None = None,
                 max_retries: int = 9):
        ...
~~~

До (`:31-32`):
~~~
pvt нужен для WellData (rho_o_std, rho_g_std → массовые дебиты).
initial_state передаётся в run() — Factory создаёт его отдельно.
~~~
После:
~~~
pvt нужен для WellData (rho_o_std, rho_g_std → массовые дебиты).
initial_state передаётся в run() — Factory создаёт его отдельно.
max_retries — глубина локального дробления шага (DEBT-015): наименьший
подшаг dt/2**max_retries. Фабрика передаёт `numerics.max_retries`
(целое в [0, 20], по умолчанию 9 — проверка в `_validate`).
output_config Simulator принимает, но не сохраняет и не читает (после
DEBT-013 — только ради сигнатуры); уровень журнала задаёт фабрика
(`setup_logging(config.output.log_level)`).
~~~

**Почему так об `output_config`:** комментарий кода `simulator.py:119-121` («остаётся ради log_level и format») и docstring `:109` создают впечатление, что параметр используется. Grep `output_config` по пакету и тестам: только `simulator.py:101, 109, 120` и вызов `factory.py:77`; атрибута `self._output_config` нет. Журнал настраивает `factory.py:45`. Заметка должна описывать код, а не комментарий — см. «Обнаруженные проблемы», п. 5.

**Проверка:** сигнатура побитно совпадает с `simulator.py:98-102` (имена, типы, умолчания); `Grep "_output_config" numerical_solver/gpn_multiphase_solver` — 0 совпадений (утверждение «не сохраняет» верно). Регресс: не нужен (документ).

**Оценка:** ~7 строк, 3 мин.

### Шаг 4: Раздел «Цикл по времени» — `run`, `_advance`, «Ключевые отличия»

**Цель:** псевдокод `run` и `_advance` по коду; без «пробного шага»; ссылки на P4 и заметку о локальном дроблении.

**Контекст:** это суть задачи (расхождения 3–8). `run` (`simulator.py:123-203`): накопители `EnergyBalanceAccumulator` (всегда) и `MassBalanceAccumulator` (если `hydro.component_inventories(initial_state)` не `None`), начальная запись, два цикла, запись на конце интервала. `_advance` (`:205-311`): цикл G1a. Энергия идёт ровно по подшагам гидро — BUG-010. Отказ гидродинамики случается до накопителей, откатывать нечего. Ловится только `HydroConvergenceError`. Отказ на наименьшем подшаге — `RuntimeError(self._failure_message(state, dt))`; начало этого текста цитируют README примеров 03, 05, 06, 07, 10 и тесты (`simulator.py:318-320`).

**Что сделать:** заменить строки `:54-115` (от `## Цикл по времени` до конца пункта DEBT-047 включительно, перед пустой строкой и `Подробности: [[контейнер-simulation-history]].`) на текст ниже. Строку `:117` «Подробности: [[контейнер-simulation-history]].» оставить. Блок «До» дословно не приводится (62 строки) — перед правкой прочитать заметку и взять `old_string` из файла. Удобнее три Edit: (а) `:54-91` — заголовок, абзац и блок `def run` → новый абзац, `run`, `_advance`, ссылки на P4; (б) `:96` — пункт `interval.bc.T_ext` → пункт `energy.solve получает весь bc` + новый пункт о дроблении; (в) `:99-108` — пункты о накопителях. Пункт DEBT-047 (`:109-115`) не трогать.

До: `:54-115` (см. заметку; ключевые фрагменты — `Двухуровневый цикл: внешний — по интервалам истории, внутренний — по подшагам интегрирования.`, блок `def run` с `self._energy.solve(hydro_result, state, dt, interval.bc.T_ext)`, пункт `- interval.bc.T_ext — T_ext берётся из BC…`, пункт о `MassBalanceAccumulator` со словами «пробный шаг при дроблении отброшен раньше»).

После:
~~~~
## Цикл по времени

Три уровня: интервалы истории (смена граничных условий) → шаги $dt$
расписания (`TimeSchedule.substeps`) → подшаги $h$ локального дробления
внутри `_advance` (DEBT-015). Записи истории — только на концах
интервалов (DEBT-013).

```python
def run(self, initial_state: SimulationState) -> SimulationHistory:
    history = SimulationHistory()
    balance = EnergyBalanceAccumulator(self._grid)    # DEBT-013: всегда
    mass = (MassBalanceAccumulator()                   # DEBT-039
            if self._hydro.component_inventories(initial_state) is not None
            else None)                                 # None — двойник без запаса
    state = initial_state
    history.append(t=state.t, state=state,
                   hydro=self._zero_hydro(state),
                   well=self._zero_well_data(state),
                   mass_balance=self._mass_snapshot(mass, state))

    # ── Внешний цикл: по интервалам истории ──
    for k, interval in enumerate(self._schedule.intervals):
        n_sub, dt = self._schedule.substeps(k)

        # ── Внутренний цикл: шаги dt расписания ──
        for step in range(n_sub):
            # Шаг dt; не сошедшийся подшаг дробится внутри _advance
            state, hydro_result = self._advance(
                state, dt, interval.bc, balance, mass)

            # 4. Запись на конце интервала истории (DEBT-013)
            if step == n_sub - 1:
                history.append(t=state.t, state=state,
                               hydro=hydro_result, well=WellData(...),
                               balance=balance.snapshot(),
                               mass_balance=self._mass_snapshot(mass, state))

    return history
```

### Шаг `_advance` — локальное дробление (DEBT-015)

```python
def _advance(self, state, dt, bc, balance, mass
             ) -> tuple[SimulationState, HydroResult]:
    n_units = 2 ** self._max_retries  # dt в единицах наименьшего подшага
    done = 0                          # пройдено единиц
    size = n_units                    # текущий подшаг, единиц; степень двойки
    while done < n_units:
        h = dt / (n_units // size)    # деление на степень двойки — точно

        # 1. Гидродинамика; отказ сходимости — подшаг пополам, из того же state
        try:
            hydro_result = self._hydro.solve(state, h, bc)
        except HydroConvergenceError as exc:
            if size == 1:             # исчерпан наименьший подшаг dt/2**max_retries
                raise RuntimeError(self._failure_message(state, dt)) from exc
            size //= 2
            continue

        # Баланс массы — только принятый подшаг (DEBT-039)
        if mass is not None:
            mass.add_step(hydro_result)

        # 2. Энергия на замороженных p, Sg, Rs подшага; коэффициенты СЛАУ —
        #    в накопитель баланса энергии (DEBT-013)
        T_new = self._energy.solve(hydro_result, state, h, bc, collect=balance)

        # 2a. T ≤ 0 или не конечная → RuntimeError, не дробится (DEBT-047)
        self._check_temperature(T_new, h, hydro_result.state.t)

        # 3. Новое состояние: T из энергии, остальное из гидро
        state = SimulationState(p=hydro_result.state.p, Sg=hydro_result.state.Sg,
                                Rs=hydro_result.state.Rs, T=T_new,
                                regime=hydro_result.state.regime,
                                t=hydro_result.state.t)
        done += size

        # Рост ×2 — только если граница кратна удвоенному подшагу:
        # подшаги всегда dt/2**k и стыкуются без остатка
        if done < n_units and done % (2 * size) == 0:
            size *= 2

    # Были отказы — user_log.info: число подшагов, наименьший, число отказов
    return state, hydro_result
```

Алгоритм G1a, пример и параметры — [[P4-адаптивный-шаг]]; замеры и
почему локальное, а не равномерное — [[локальное дробление шага проходит останов при суточном dt_integration — равномерное падает на одном подшаге из 512]].

Ключевые отличия от плана:
- `run(initial_state)` — initial_state передаётся извне (Factory создаёт)
- `interval.bc` — полный BoundaryConditions (WellControl + p_ext + T_ext + Rs_ext + Sg_ext)
- `energy.solve` получает весь `bc`: $T_{ext}$ берётся из `bc.T_ext`, а не
  из config (может меняться по интервалам)
- отбор записей — только конец интервала (DEBT-013); второго механизма
  (`save_every`) больше нет, частоту вывода задаёт расписание
- дробление шага — в `Simulator`, а не в адаптере (DEBT-015): адаптер
  делает один шаг и при отказе Ньютона бросает `HydroConvergenceError`,
  `_advance` делит пополам только не сошедшийся подшаг. Энергия идёт
  ровно по подшагам гидродинамики (BUG-010). Ловится только
  `HydroConvergenceError` — иной `RuntimeError` из гидродинамики уходит
  наружу без повторов. Отказ на наименьшем подшаге — `RuntimeError` с
  текстом `_failure_message`: глубина дробления, $t$ подшага, число
  двухфазных ячеек, $\max S_g$ и оба рычага (`numerics.max_retries`,
  `time.dt_integration`); причину текст не называет. Начало текста
  цитируют README примеров 03, 05, 06, 07, 10 и тесты
- накопитель баланса энергии передаётся в `energy.solve(..., collect=)`
  на **каждом** принятом подшаге и вызывается безусловно: баланс должен
  считаться всегда, при любой структуре истории. См. [[модули-energy-tridiag]]
- накопитель баланса массы `MassBalanceAccumulator` (DEBT-039,
  `gpn_multiphase_solver/mass_balance.py`) создаётся, если решатель отдаёт
  запас начального состояния (`HydroSolver.component_inventories` не `None`);
  `_advance` добавляет в него `HydroResult.int_G_*` только принятого
  подшага. Откатывать нечего: отказ гидродинамики случается до обоих
  накопителей. На каждой записи `_mass_snapshot` берёт у решателя запас
  текущего состояния. У двойников без запаса снимки — `None`
- после каждого подшага энергии `_advance` проверяет температуру
  (`_check_temperature`, DEBT-047): $T \le 0$ или не конечная $T$ →
  `RuntimeError` с $\Delta t$ подшага, временем его конца, ячейкой, $r$ и
  значением. Гидродинамика от $T$ не зависит, поэтому без проверки
  нефизичная $T$ доходила до истории молча. Проверка одна на любой
  `EnergySolver`; отказ не дробится — дробление ловит только
  `HydroConvergenceError` (DEBT-015)
~~~~

Последний пункт (DEBT-047) — дословно прежний `:109-115`.

**Проверка:**
- каждая строка псевдокода `run` имеет пару в `simulator.py:132-203`; `_advance` — в `:239-311` (кроме опущенных `n_ok`, `n_fail`, `h_min_ok`, `dev_log`);
- аргументы `energy.solve` — `(hydro_result, state, h, bc, collect=balance)` (`:270-271`);
- аргументы `_check_temperature` — `(T_new, h, hydro_result.state.t)` (`:282`);
- в разделе нет слова «пробн».
- Регресс: не нужен (документ).

**Подводные камни:** псевдокод ≠ код (см. чеклист); вложенные блоки кода внутри списка не ставить.

**Оценка:** ~110 строк вместо ~62, 15 мин.

### Шаг 5: Раздел «TimeSchedule»

**Цель:** поля `HistoryInterval` с управлением по дебиту, преобразование в `WellControl`, имя аргумента `substeps`, `n_intervals` как свойство.

**Контекст:** `run` обращается к `self._schedule.n_intervals` без скобок (`simulator.py:161, 169`) — это `@property` (`:84-86`). FEAT-020 добавил в `HistoryInterval` (`io/config.py:111-124`) поля `q_oil` (дебит нефти в стандартных условиях, м³ст/с) и `min_bhp` (нижняя граница забойного давления, Па) для `control = "rate"`; `_create_well_control` (`factory.py:634-642`) строит `PressureControl(p_wf)` или `RateControl(q_oil, min_bhp)`. Раздел заметки об этом не знает (расхождения 16, 17).

**Изменения:**

До (`:124`):
~~~
`HistoryInterval` (config.py) содержит `dt`, `control`, `p_wf` — сырые данные из JSON.
~~~
После:
~~~
`HistoryInterval` (config.py) содержит `dt`, `control`, `p_wf`, `q_oil`, `min_bhp` (последние два — управление по дебиту нефти, FEAT-020) — сырые данные из JSON.
~~~

До (`:126-127`):
~~~
**Runtime**: Factory (фаза 6) создаёт `TimeSchedule` из `TimeConfig`, преобразуя
каждый `HistoryInterval.control + p_wf` → `WellControl` (см. [[модули-bc-граничные-условия]]).
~~~
После:
~~~
**Runtime**: Factory (фаза 6) создаёт `TimeSchedule` из `TimeConfig`, преобразуя
каждый `HistoryInterval` → `WellControl` (`_create_well_control`: `control = "pressure"` →
`PressureControl(p_wf)`, `"rate"` → `RateControl(q_oil, min_bhp)`; см. [[модули-bc-граничные-условия]]).
~~~

До (`:141-146`):
~~~
    def substeps(self, k: int) -> tuple[int, float]:
        """n_sub = ceil(dt/dt_int), dt_actual = dt/n_sub."""
        ...

    def total_time(self) -> float: ...
    def n_intervals(self) -> int: ...
~~~
После:
~~~
    def substeps(self, interval_idx: int) -> tuple[int, float]:
        """n_sub = ceil(dt/dt_int), dt_actual = dt/n_sub."""
        ...

    def total_time(self) -> float: ...

    @property
    def n_intervals(self) -> int: ...
~~~

До (`:151`):
~~~
Factory создаёт TimeSchedule из TimeConfig, преобразуя `HistoryInterval` (данные: control, p_wf) → `ScheduleInterval` (runtime: BoundaryConditions с WellControl).
~~~
После:
~~~
Factory создаёт TimeSchedule из TimeConfig, преобразуя `HistoryInterval` (данные: control, p_wf, q_oil, min_bhp) → `ScheduleInterval` (runtime: BoundaryConditions с WellControl).
~~~

**Проверка:** совпадает с `simulator.py:64, 80, 84-85`, `io/config.py:111-124`, `factory.py:634-642`. Регресс: не нужен (документ).

**Оценка:** ~7 строк, 4 мин.

### Шаг 6: Раздел «SimulationHistory»

**Цель:** поля и `append` как в `state.py:139-184`.

**Контекст:** `balance` (DEBT-013) — накопленные члены баланса энергии на момент записи; `mass_balance` (DEBT-039) — снимок баланса массы или `None`. `append` без `balance` пишет нулевой снимок `_zero_balance()` (`state.py:175-176`) — так записывается начальное состояние. Подробности — [[контейнер-simulation-history]] (уже есть ссылка на `:167`).

**Изменения:**

До (`:155-165`):
~~~
```python
@dataclass
class SimulationHistory:
    times: list[float]
    states: list[SimulationState]
    hydro_results: list[HydroResult]
    well_data: list[WellData]

    def append(self, t, state, hydro, well): ...
    def n_saved(self) -> int: ...
```
~~~
После:
~~~
```python
@dataclass
class SimulationHistory:
    times: list[float]
    states: list[SimulationState]
    hydro_results: list[HydroResult]
    well_data: list[WellData]
    balance: list[dict]              # DEBT-013: члены баланса энергии
    mass_balance: list[dict | None]  # DEBT-039: None — решатель массу не сохраняет

    def append(self, t, state, hydro, well,
               balance=None, mass_balance=None): ...  # balance=None → нулевой снимок

    @property
    def n_saved(self) -> int: ...
```
~~~

`:167` («Simulator создаёт новый SimulationState на каждом шаге…») не менять — верно (`_advance` создаёт новый объект на каждом подшаге).

**Проверка:** совпадает с `state.py:158-168, 175-176, 182-183`. Регресс: не нужен (документ).

**Оценка:** ~6 строк, 3 мин.

### Шаг 7: Раздел «SimulatorFactory»

**Цель:** вызов `Simulator` с `max_retries`, создание гидро через `_create_prototype_hydro`, список помощников.

**Изменения:**

До (`:178`):
~~~
        hydro = PrototypeHydroAdapter(...)   # было AnalyticalHydroSolver до FEAT-014
~~~
После:
~~~
        hydro = _create_prototype_hydro(config, grid, pvt, relperm)  # PrototypeHydroAdapter; до FEAT-014 — AnalyticalHydroSolver
~~~

До (`:181`):
~~~
        simulator = Simulator(grid, hydro, energy, pvt, schedule, config.output)
~~~
После:
~~~
        simulator = Simulator(grid, hydro, energy, pvt, schedule, config.output,
                              max_retries=config.numerics.max_retries)
~~~

До (`:188`):
~~~
Помощники `_create_pvt`, `_create_relperm`, `_create_schedule`, `_create_well_control` — модульные функции в factory.py.
~~~
После:
~~~
Помощники `_create_pvt`, `_create_relperm`, `_create_prototype_hydro`, `_create_schedule`, `_create_well_control` — модульные функции в factory.py.
~~~

**Проверка:** `factory.py:66, 75-78, 96, 359, 383, 608, 634` — все пять помощников существуют (Grep `^def _create_`). Регресс: не нужен (документ).

**Оценка:** 4 строки, 2 мин.

### Шаг 8: Раздел «Связанные заметки»

**Цель:** ссылки на P4, заметку о локальном дроблении, заметку о проверке $T$.

**Изменения:** после строки `- [[модули-energy-tridiag]] — EnergySolver` (`:196`) добавить:
~~~
- [[P4-адаптивный-шаг]] — локальное дробление шага в `_advance` (DEBT-015)
- [[локальное дробление шага проходит останов при суточном dt_integration — равномерное падает на одном подшаге из 512]] — замеры G1a
- [[нефизичная температура доходила до истории молча — проверка T ловит грубые ошибки, остальное проверка ввода]] — `_check_temperature` (DEBT-047)
- [[контейнер-simulation-history]] — поля и наполнение истории
~~~

**Проверка:** каждая цель существует (шаг 9). Регресс: не нужен (документ).

**Оценка:** 4 строки, 2 мин.

### Шаг 9: Сверка заметки с кодом

**Цель:** доказать, что расхождения 1–15 сняты и новых нет.

**Что сделать** (Grep по `vault/knowledge/decisions/модули-simulator-оркестратор.md` в worktree):
1. `пробн` — 0 совпадений.
2. `interval\.bc\.T_ext\)` — 0 совпадений.
3. `Двухуровневый` — 0 совпадений.
4. `max_retries` — не меньше 5 (сигнатура, абзац шага 3, `_advance` ×2, фабрика).
5. `_advance`, `_failure_message`, `_check_temperature`, `HydroConvergenceError`, `component_inventories`, `@property` — каждый ≥ 1.
6. `collect=balance` — 1 (псевдокод `_advance`); `q_oil` — не меньше 3 (`:124`, `:127`, `:151` прежней нумерации); `RateControl` — 1; `нужен только ради` — 0 (неверная фраза об `output_config` не попала).
7. Wiki-ссылки: Glob каждой цели —
   `vault/knowledge/decisions/P4-адаптивный-шаг.md`,
   `vault/knowledge/numerics/локальное дробление шага проходит останов при суточном dt_integration — равномерное падает на одном подшаге из 512.md`,
   `vault/knowledge/debugging/нефизичная температура доходила до истории молча — проверка T ловит грубые ошибки, остальное проверка ввода.md`,
   `vault/knowledge/decisions/контейнер-simulation-history.md`,
   `vault/knowledge/decisions/модули-energy-tridiag.md`. Записи [[DEBT-050]], [[DEBT-015]], [[DEBT-047]] — заголовки реестра (так же ссылаются другие заметки).
8. Перечитать правленую заметку целиком один раз и пройти таблицу «Расхождения» построчно (1–17).
9. `numerical_solver/`: `.venv\Scripts\python -m pytest tests/ --collect-only -q` → то же число, что в baseline шага 1.

**Проверка:** Регресс: `--collect-only` (код не менялся). Итоговый полный прогон — по контракту `/implement`; изменений кода нет, ожидание — тот же итог, что у базы.

**Оценка:** 10 мин.

### Шаг 10: Vault и issue

**Цель:** статус задачи, комментарий в issue.

**Что сделать:**
1. Реестр `vault/roadmap/известные баги и технический долг.md`, секция DEBT-050: статус по контракту `/implement`.
2. `vault/issues/debt-050/05-comment-done.md` — итог: какие разделы правлены, таблица «расхождение → снято», число тестов 1429 без изменений; `gh issue comment 80 --repo ArturSalamatin/Oil_Gas --body-file vault/issues/debt-050/05-comment-done.md`.
3. `vault/00-home/index.md` — не трогать: новых заметок нет.

**Оценка:** 10 мин.

## Тестовая стратегия

Код не меняется — новых тестов нет. Неизменность поведения подтверждает число тестов (одно и то же до и после; 1429 на `81d1474`). Корректность документа — шаг 9: grep-проверки (отсутствие устаревших формулировок, наличие новых имён) и построчная сверка с `simulator.py`, `state.py`, `factory.py` на базе.

**Тест:** — (документ)
**Предотвращает:** возврат устаревшей схемы шага в справочник.

## Критерии завершения

- [ ] Расхождения 1–17 сняты (шаг 9, пп. 1–8)
- [ ] Пункт DEBT-047 (`_check_temperature`) — дословно прежний
- [ ] Wiki-ссылки разрешаются
- [ ] Число тестов равно baseline шага 1; код и тесты не менялись (`git diff --stat` — только `vault/`)
- [ ] Реестр: статус DEBT-050; issue #80 прокомментирован; закрывается при `/merge`

## Обнаруженные проблемы (не блокируют, не правятся в этой задаче)

1. **`vault/knowledge/decisions/контейнер-simulation-history.md:87-101, 120-125`** — разделы «Методы (будущее, не реализуем в фазе 3)» и «Реализация в фазе 3»: `append(t, state, hydro, well)` (`:90`, `:125`), «`@dataclass` с четырьмя полями» (`:123`), метод `to_arrays` (в коде — модульная функция `history_to_arrays`, `io/output.py:29`, а не метод `SimulationHistory`). Верхняя часть заметки (поля `balance`, `mass_balance`, `:24-25`, `:36-37`) актуальна. Текст помечен как проект фазы 3 — исторический, но читатель может принять его за текущий API. Решение пользователя 2026-10-10: в DEBT-050 не включать.
2. **`vault/knowledge/decisions/архитектура библиотеки numerical_solver.md:181-187`** — псевдокод проектного этапа `energy.solve(state, dt, bc) → T`, без дробления и накопителей. Заметка проектная; актуальная схема — в правимой заметке.
3. **`vault/knowledge/validation/матрица температурной задачи сверена с постановкой поэлементно.md:39, 127-128`** и комментарии **`numerical_solver/tests/test_energy_matrix_examples.py:547, 620-622`** — «при A-retry `Simulator._advance` дробит…», «DEBT-015 … потребует пересмотра теста на сохранение времени». После DEBT-015 утверждение по сути верно (энергия вызывается с длиной подшага $h$), а тест `test_energy_substeps_preserve_total_time` (`:788`) зелёный без пересмотра: $\sum h = dt$ и при локальном дроблении. Устарела только терминология «A-retry» и прогноз.
4. **`vault/knowledge/debugging/энергия решается одним шагом там где гидро раздробило.md:64`** — описание механизма BUG-010 (`n_substeps`, пробный шаг). Заметка-расследование, историческая; P4 (`:144`) описывает то же как историю. Править не нужно.

5. **`numerical_solver/gpn_multiphase_solver/simulator.py:101, 109, 119-121`** (аудит 2026-10-10) — параметр `output_config` мёртвый: `Simulator` его не сохраняет и не читает, а docstring («параметры вывода (log_level, format)») и комментарий («остаётся ради log_level и format») утверждают обратное. Журнал настраивает `factory.py:45`. Варианты — убрать параметр (вызов `factory.py:77`) или поправить комментарий; код, не vault — вне DEBT-050.

Пункты 1–3 — кандидаты на одну запись DEBT «устаревшие описания дробления и SimulationHistory в соседних заметках», пункт 5 — на отдельную (код); регистрация — по решению пользователя.

## Оценка

1 файл vault, ~140 строк правки (из них ~110 — раздел «Цикл по времени»), ~1 ч с проверкой.
