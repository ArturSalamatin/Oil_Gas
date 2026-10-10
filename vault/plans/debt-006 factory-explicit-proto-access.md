---
tags:
  - план
  - рефакторинг
date: 2026-10-10
issue: DEBT-006
github: 88
branch: refactor/debt-006/factory-explicit-proto-access
status: реализован
worktree: .worktrees/debt-006
audit:
  date: 2026-10-10
  found: 3
  auto-fixed: 3
  manual-required: 0
---

# DEBT-006: фабрика выбирает ветку по классу обёртки, а не по её приватным полям

Подтип: **рефакторинг** (способ доступа к объектам прототипа под обёртками). Числа всех расчётов побитово прежние — это проверяет проба-отпечаток (шаги 1, 4, 7).

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Для справки (не править до шага 6): `vault/knowledge/decisions/согласованность-pvt-hydro.md` — принцип «один объект PVT/ОФП на всю симуляцию»; issue [#88](https://github.com/ArturSalamatin/Oil_Gas/issues/88) — анализ вариантов (поправку к его описанию см. в разделе «Контекст»).
3. Ветка `refactor/debt-006/factory-explicit-proto-access` от `numerical_scheme/implementation`, worktree `.worktrees/debt-006` (контракт `/implement`). Основной каталог не переключать: там работают параллельные сессии.
4. Переменные PowerShell для команд ниже:
   ```powershell
   $ROOT = "D:\Lessons\Grants\2026\GPN\Oil_Gas"
   $WT   = "$ROOT\.worktrees\debt-006\numerical_solver"     # код worktree
   $PY   = "$ROOT\numerical_solver\.venv\Scripts\python.exe" # в worktree своего .venv нет
   $P    = "$ROOT\.worktrees\debt-006\vault\issues\debt-006\probes"
   ```
   Все команды pytest — из `$WT` (`cd $WT`): тогда pytest импортирует код worktree (cwd первым в `sys.path`).
5. Baseline (шаг 1): число тестов, быстрый уровень, отпечаток истории **до правок**. На базе планирования `26ddb34`: 1592 теста, быстрый уровень 1342 из 1592. Критерий числа тестов — «после = до + 12», а не константа: к старту могут влить другие задачи (см. «Порядок влития»).
6. Шаги 2–5 правят код и тесты; после каждого — быстрый уровень. Шаг 6 — vault. Шаг 7 — итоговая проверка; полный прогон — там (`/implement`).
7. **Номера строк** в плане — на базе `26ddb34`, до любых правок. Внутри задачи они сдвигаются: шаг 3 заменяет 6 строк `test_factory_prototype.py:163-168` на 19 и дописывает имена в импорт фабрики `:23-26` (всё ниже — примерно +14, в том числе `:219-249` шага 4 → ~`:233-263`) и добавляет 3 строки импортов в `test_factory_standing_hydro.py` (`:44-48` шага 4 → ~`:47-51`); после влития BUG-022 строки `factory.py` ниже `:440` сдвинутся на +3. Искать места правок по цитатам «До», а не по номерам.

## Контекст

`SimulatorFactory` (`numerical_solver/gpn_multiphase_solver/factory.py`) создаёт одну табличную модель PVT или ОФП и раздаёт её **и** прототипу (`RadialBlackOilModel` из `radial_blackoil`), **и** нашим модулям. Прототип работает в барах/сП со своими классами (`BlackOilPVT`, `TabulatedRelPerm`), наши модули — в СИ через обёртки:

```
BlackOilPVT ─▶ PrototypePVTAdapter (поле _pvt) ─▶ TableFullPVT (поле _hydro) ─▶ энергия, Simulator
TabulatedRelPerm ─▶ PrototypeRPAdapter (поле _rp)
```

Чтобы отдать прототипу **тот же** объект, фабрика разворачивает обёртку. Ветку она выбирает по наличию приватных полей:

| Строка `factory.py` | Код | Что выбирает |
|---|---|---|
| 460–461 | `if hasattr(pvt, '_hydro') and hasattr(pvt._hydro, '_pvt'): return pvt._hydro._pvt` | таблица → тот же `BlackOilPVT`; иначе `HydroPVTtoBlackOilAdapter(pvt, p_max_pa=p0)` |
| 472–473 | `if hasattr(relperm, '_rp'): return relperm._rp` | таблица → тот же `TabulatedRelPerm`; иначе табуляция на 101 узле `np.linspace(0, 1, 101)` |
| 450 | `our_pvt = pvt._hydro if hasattr(pvt, '_hydro') else pvt` | какой объект PVT получит `PrototypeHydroAdapter` для пересчёта потоков $Q, u, m$ |

Те же приватные поля читают два скрипта графиков: `numerical_solver/examples/pvt_plot.py:148-151` (`getattr(pvt, "_hydro")`, `getattr(hydro, "_pvt")`) и `numerical_solver/examples/relperm_plot.py:49-51` (`getattr(relperm, "_rp")`).

### Что на самом деле случится при переименовании поля (замер при планировании, `26ddb34`)

Поправка к описанию issue #88: там сказано, что в ветке ОФП «наши модули продолжат считать по исходной таблице — рассогласование $k_{ro}, k_{rg}$ между прототипом и пересчётом потоков». Это неверно: пересчёт потоков в `PrototypeHydroAdapter` идёт от покомпонентных потоков прототипа (`fluxes.phase_fluxes_from_components`) и ОФП не использует; объект `relperm` из `from_config` нужен **только** для сборки ОФП прототипа — его не держат ни `Simulator`, ни решатель энергии, ни адаптер. Также неверно, что пропадёт предупреждение `RELPERM Sg above table`: в GPN `pvt_range_warnings` вызывается только для начального состояния (`factory.py:346-355`, $S_g = 0$), и про ОФП там предупреждать нечего.

Фактические последствия:

1. **PVT** (переименование `PrototypePVTAdapter._pvt` или `TableFullPVT._hydro`). Таблица уходит в ветку `HydroPVTtoBlackOilAdapter`; затем `isinstance(pvt, TableFullPVT)` (`factory.py:446`) зовёт `pvt_range_warnings`, а та читает `model.pvt.gp` (`radial_blackoil/diagnostics.py:27`), которого у адаптера нет → `AttributeError` при сборке. Сбой громкий, но текст указывает на диагностику BUG-017, а не на причину; защита случайная.
2. **ОФП** (переименование `PrototypeRPAdapter._rp`). Прототип молча получает таблицу, пересчитанную на 101 узел. Замер на `examples/04_table_table` и `05_standing_table_rp` (подмена `_get_or_create_proto_rp` в памяти):
   - порог активации газа `sg_activation_cap` (BUG-018, `radial_blackoil/blackoil.py:49-54` — последний узел с $k_{ro} > 0$) сдвигается с **0.6** на **0.79**;
   - история меняется в последних битах: $\max|\Delta p|/\max|p| = 6\cdot10^{-15}$, по $S_g$ — $3\cdot10^{-14}$, по $T$ — $3\cdot10^{-16}$; отпечаток SHA-256 у 04 и 05 другой, у 03 (Кори) — прежний. Контрольные $p(r_w)$, $T(r_w)$, $q_o$ на конце совпадают во всех знаках.

   Сейчас это безвредно: узлы таблиц примеров лежат на сетке с шагом 0.01, а $S_g \le 0.017$ до порога не доходит. Вред появится у таблицы с узлами вне шага 0.01 ($k_r$ прототипа ≠ CSV, а аналитика и графики примеров берут CSV через `_create_relperm`) или при $S_g$ около порога. Ни один числовой тест такого не заметит — допуски крупнее.
3. **Скрипты графиков.** При переименовании поля `_pvt_table_nodes` и `_table_nodes` молча вернут `None` — маркеры узлов таблиц исчезнут с `pvt.png` и `relperm.png`.

Итог: задача — архитектурная гигиена с низким приоритетом. Главная ценность в том, что следующий сбой будет громким.

## Решения пользователя (2026-10-10, при планировании)

1. **Вариант 2** issue #88: публичные свойства только для чтения у обёрток + `isinstance` в фабрике. ABC (`pvt/base.py`) не трогать.
2. **Скрипты графиков** `examples/pvt_plot.py` и `examples/relperm_plot.py` — включить в задачу.
3. **Строка 450:** `PrototypeHydroAdapter` получает сам `FullPVT` (`our_pvt = pvt`), без развёртывания.

## Текущее и целевое состояние

| Место | Сейчас | После |
|---|---|---|
| `pvt/prototype_adapter.py`, `PrototypePVTAdapter` | только приватное `_pvt` | + свойство `proto_pvt` (без сеттера) |
| `pvt/prototype_adapter.py`, `PrototypeRPAdapter` | только приватное `_rp` | + свойство `proto_rp` (без сеттера) |
| `pvt/table_full.py`, `TableFullPVT` | только приватное `_hydro` | + свойство `hydro` (без сеттера) |
| `factory.py:460-461` | `hasattr(pvt, '_hydro') and hasattr(pvt._hydro, '_pvt')` | `isinstance(pvt, TableFullPVT)` → `pvt.hydro.proto_pvt` |
| `factory.py:472-473` | `hasattr(relperm, '_rp')` | `isinstance(relperm, PrototypeRPAdapter)` → `relperm.proto_rp` |
| `factory.py:449-451` | адаптеру — `pvt._hydro` (таблица) или `pvt` | адаптеру — всегда `pvt`, тот же объект, что у энергии и `Simulator` |
| `hydro/prototype_adapter.py:52` | «pvt — наш HydroPVT (PrototypePVTAdapter, обёртка того же BlackOilPVT)» — неверно уже сейчас для Стендинга | «фабрика передаёт тот же FullPVT, что решателю энергии» |
| `examples/pvt_plot.py:135-151` | `getattr` по `_hydro`, `_pvt`, `hasattr(proto, "gp")` | `isinstance(pvt, TableFullPVT)` → `pvt.hydro.proto_pvt` |
| `examples/relperm_plot.py:42-54` | `getattr(relperm, "_rp")`, `hasattr(proto, "sg")` | `isinstance(relperm, PrototypeRPAdapter)` → `relperm.proto_rp` |
| `tests/test_factory_prototype.py:163-168` | `test_relperm_is_prototype_adapter` — **без единого утверждения** | `test_prototype_relperm_from_csv`: узлы CSV и порог 0.6 у прототипа |
| `tests/test_factory_prototype.py:219-249` | читают `hydro._pvt._pvt`, `simulator._pvt._hydro`, `our_pvt._pvt` | публичные свойства + тождество объекта FullPVT у адаптера, энергии, `Simulator` |

Число тестов: **+12** (4 в шаге 2, 4 в шаге 3, 1 в шаге 4, 3 в шаге 5); один тест переименован (шаг 3). Все новые — быстрого уровня. Граф импортов: `examples/pvt_plot.py` начинает импортировать `gpn_multiphase_solver.pvt.table_full`, `examples/relperm_plot.py` — `gpn_multiphase_solver.pvt.prototype_adapter` (локально в функции); `factory.py` оба класса уже импортирует (`:17-18`). Циклов нет: модули `pvt/` пакет `examples` и фабрику не импортируют.

## Зона неприкосновенности

- ABC `HydroPVT`, `FullPVT`, `RelPermModel` (`pvt/base.py`) — вариант 1 отклонён.
- Приватные поля `_pvt`, `_rp`, `_hydro` — **не переименовывать**: свойства их только открывают. Внутренние вызовы обёрток (`self._pvt.bo(...)`, `self._rp.kro(...)`, делегирование `TableFullPVT`) не трогать.
- `HydroPVTtoBlackOilAdapter` (`pvt/hydro_to_blackoil_adapter.py`) — без изменений; его `_hydro` читает только новый тест шага 4 (проверка тождества).
- `factory.py:442-447` — `isinstance(pvt, TableFullPVT)` перед `_warn_initial_table_range` (BUG-017): уже проверка по классу, не трогать.
- Имена `_get_or_create_proto_pvt`, `_get_or_create_proto_rp`, `_create_pvt`, `_create_relperm` — не менять: `_create_*` зовут ~15 мест в `examples/`, `tests/`, `deliverables/`; `_get_or_create_proto_rp` импортирует `tests/test_factory_standing_hydro.py:16` и упоминает docstring `tests/test_prototype_activation_cap.py:59`.
- Прототип (`numerical_solver/HydroSolverPrototype/`) — ни строки; тесты и регрессия прототипа не нужны.
- Исторические планы и пробы (`vault/plans/feat-012…`, `feat-014…`, `feat-017…`, `vault/issues/feat-028/probes/*`, `vault/issues/bug-017/*`) и заметка `vault/knowledge/decisions/P7-офп-без-производных.md` (листинг `PrototypeRPAdapter` с `_rp` — верен и после задачи) — не трогать.

## Анализ вариантов

Полностью — в теле issue #88. Кратко:

| Вариант | Суть | Почему выбран / отклонён |
|---|---|---|
| 1 | `as_blackoil_pvt(p_max_pa)` в `HydroPVT`, `as_tabulated_relperm()` в `RelPermModel` | отклонён: ABC физики узнаёт формат прототипа (бар/сП), `pvt/base.py` зависит от `radial_blackoil`, выбор «101 узел» прячется в ABC |
| **2 (выбран)** | публичные свойства обёрток + `isinstance` в фабрике | правка 3 файлов пакета; фабрика и так единственное место, знающее конкретные классы (докстринг `factory.py:3`), и уже делает `isinstance(pvt, TableFullPVT)` (`:446`) |
| 3 | фабрика запоминает `BlackOilPVT`/`TabulatedRelPerm` при создании | отклонён: пара функций на одну работу (`_build_pvt` рядом с `_create_pvt` ради ~15 внешних вызовов), 6 аргументов у `_create_prototype_hydro` |

**Промежуточные состояния варианта 2:** каждый шаг оставляет тесты зелёными. Шаг 2 только добавляет свойства. Шаг 3 меняет выбор ветки, но для штатных объектов ветка та же. Шаг 4 меняет объект адаптера при побитово тех же числах. Шаг 5 меняет только скрипты графиков.

## Чеклист подводных камней

- ✅ **Все места вызова найдены.** Grep `_hydro\._pvt|pvt\._hydro|relperm\._rp|_pvt\._hydro` по `numerical_solver/`: только `factory.py:450, 460-461, 473` и `tests/test_factory_prototype.py:239`. Grep `getattr\(.*"(_hydro|_pvt|_rp)"`: только `examples/pvt_plot.py:148-149`, `examples/relperm_plot.py:49`. `hydro._pvt._pvt` — `tests/test_factory_prototype.py:230`. Других `hasattr`/`getattr` в `factory.py` нет.
- ✅ **Зависимости пакетов** — не меняются.
- ✅ **Обратная совместимость API.** Свойства — добавление; сигнатуры функций фабрики прежние; `PrototypeHydroAdapter(model, grid, pvt)` прежний, меняется только объект в третьем аргументе.
- ✅ **Тип объекта адаптера (строка 450).** `PrototypeHydroAdapter` зовёт у `self._pvt` только методы `HydroPVT`: `Bo`, `Bg`, `rho_o`, `rho_g`, `rho_o_std`, `rho_g_std`, `mu_o`, `mu_g` (через `fluxes.py:30-33, 80-83, 99-100, 128-131, 152-153`). `TableFullPVT` делегирует их `PrototypePVTAdapter` без арифметики (`table_full.py:26-36`). `rho_o`, `rho_g` ни одна из обёрток не переопределяет — это общий код `HydroPVT.rho_o` (`base.py:68-74`) над теми же `Bo` и `rho_*_std`. Результат побитово тот же; проверяет проба-отпечаток. Стоимость — один лишний вызов-делегирование на метод за шаг: незаметно.
- ✅ **Тождество объектов после шага 4** (проверено на `26ddb34`): сейчас `type(sim._hydro._pvt)` — `PrototypePVTAdapter`, у `sim._energy._pvt` и `sim._pvt` — `TableFullPVT`. После шага 4 у всех трёх — один объект.
- ✅ **Состояние при ошибке.** Объект без нужного свойства → `AttributeError` при сборке, до расчёта; частично собранный `Simulator` наружу не уходит.
- ✅ **Тесты-метки на посторонних полях** (шаг 3) проверены при планировании: текущий код на `StandingFullPVT` с `_hydro = SimpleNamespace(_pvt="marker")` и на `CoreyRP` с `_rp = "marker"` возвращает `"marker"` — тесты будут красными до шага 3. `__slots__`, `frozen`, `__setattr__` в `pvt/` нет — атрибут присваивается.
- ✅ **Циклические импорты** — нет (см. «Текущее и целевое состояние»).
- ✅ **Docstrings / `\eqref{}`** — формулы не затрагиваются.
- ✅ **Конфиги** — не меняются.
- ✅ **`tests/test_example_scripts.py` (DEBT-046)** проверяет, что имена, которые скрипты `examples/` берут из других модулей, существуют. Новые импорты (`TableFullPVT`, `PrototypeRPAdapter`) существуют — тест зелёный.
- ✅ **Одна копия классов при `isinstance` в скриптах графиков** (аудит). `isinstance(pvt, TableFullPVT)` в `pvt_plot.py` верен, только если класс и объект — из одного модуля в `sys.modules`. Перезагрузок (`reload`, правки `sys.modules`) в `tests/` и `examples/` нет; pytest из `$WT` грузит пакет worktree один раз, скрипт примера — пакет того каталога, откуда импортирован (память `reference_worktree_pythonpath`): в обоих случаях фабрика и скрипт видят один и тот же класс.
- ✅ **Утверждения «Контекста» перепроверены аудитом.** Подмена ветки PVT на адаптер для `configs/table_pvt` → `AttributeError: 'HydroPVTtoBlackOilAdapter' object has no attribute 'gp'` при сборке; `pvt_range_warnings` в пакете вызывает только `factory.py:354`; `Simulator`, `TridiagEnergySolver`, `PrototypeHydroAdapter` объект ОФП не принимают.
- ⚠️ **Связь с другими задачами** — раздел «Порядок влития».
- ✅ **Производительность** — не меняется (проба: 03, 04, 05 — 0.5, 0.6, 0.2 с).
- ✅ **Прототип** — не меняется.

## Порядок влития

| Задача | Состояние на 2026-10-10 | Пересечение с DEBT-006 | Что делать |
|---|---|---|---|
| [[BUG-022]] (#82) | реализация начата (`26ddb34`) | `factory.py:428-440` — добавляет `cell_tol=nc.newton_cell_tol,` после `phase_switching_stage=True,` (≈ строка 439). Ближайшая правка DEBT-006 — комментарий `:449`: между ними ≥ 8 неизменных строк, слияние без конфликта. Меняет числа расчётов (условие сходимости Ньютона). | «До»-отпечаток снимать **в worktree на старте** (шаг 1), а не брать из планирования: если BUG-022 влит раньше, отпечаток базы другой. Сверка — «до» против «после» одной базы. Номера строк `factory.py` ниже `:440` после BUG-022 сдвинутся на +3 (2 строки комментария + аргумент) — искать по цитатам. DEBT-006 строк выше `:449` не меняет, поэтому ссылки плана BUG-022 (`:428-440`) верны в любом порядке. |
| [[DEBT-048]] (#78) | план готов, реализация после BUG-022 | переписывает докстринг `PrototypeHydroAdapter.__init__` (`hydro/prototype_adapter.py:48-56`, план DEBT-048 `:822-850`): новый параметр `stage4_memory`, выравнивание всех строк. DEBT-006 меняет строку `pvt` того же докстринга (`:52`) → **конфликт в докстринге**, кто бы ни влился вторым. | Разрешение: взять докстринг DEBT-048 и подставить в его строку `pvt` текст DEBT-006. Если DEBT-006 влит первым — исполнитель DEBT-048 увидит, что блок «До» плана DEBT-048 (`:824-833`) не совпадает в строке `pvt`; это ожидаемо. План DEBT-048 цитирует и вызов `PrototypeHydroAdapter(model, grid, our_pvt)` (`factory.py:452`, «фабрика не меняется»): после DEBT-006 — `PrototypeHydroAdapter(model, grid, pvt)`; его поиск по `PrototypeHydroAdapter(` от этого не ломается. |
| [[DEBT-056]] (#87) | план готов (+21 тест) | правит `io/config.py`, `test_config.py`; файлов DEBT-006 не правит (`factory.py`, `test_factory_*.py` только цитирует). | ничего; число тестов — «baseline + 12» от фактической базы |
| [[VAL-005]] | план готов | новый пример на табличных PVT/ОФП — идёт через общий код фабрики и скриптов графиков; файлов DEBT-006 не правит. | ничего |

## Шаги

### Шаг 1: Подготовка и исходный замер

**Цель:** зафиксировать число тестов, быстрый уровень и отпечаток истории до правок.

**Файлы:** `vault/issues/debt-006/probes/fingerprint_before.out.txt` (новый, вывод пробы).

**Что сделать** (из `$WT`):
1. `& $PY -m pytest tests/ --collect-only -q` — записать число (на `26ddb34` — 1592).
2. `& $PY -m pytest tests/ -m "not slow" -q` — записать число passed и время (на `26ddb34` — 1342 в уровне).
3. Отпечаток истории примеров 03, 04, 05:
   ```powershell
   cd $WT
   & $PY "$P\history_fingerprint.py" > "$P\fingerprint_before.out.txt"
   Get-Content "$P\fingerprint_before.out.txt"
   ```
   Первая строка обязана быть `Код: ...\.worktrees\debt-006\numerical_solver\gpn_multiphase_solver\factory.py`. Путь основного каталога — проба запущена не оттуда, остановиться. Проба берёт код из `Path.cwd()`, поэтому запуск только из `$WT`.
   Для справки — отпечаток планирования на `26ddb34`: `vault/issues/debt-006/probes/fingerprint_plan_26ddb34.out.txt`. Совпадёт с «до», только если между `26ddb34` и стартом не вливали задач, меняющих числа (BUG-022 — меняет).
4. Grep-инвентаризация (инструмент Grep, путь `$WT`, без `HydroSolverPrototype/**`):
   - `hasattr\(|getattr\(` в `gpn_multiphase_solver/factory.py` — ожидается 3 строки: `:450`, `:460`, `:472`;
   - `getattr\(.*"(_hydro|_pvt|_rp)"` в `examples/` — ожидается `pvt_plot.py:148, 149`, `relperm_plot.py:49`.
   Если номера сдвинулись — искать по цитатам из шагов ниже.

**Проверка:** числа и отпечаток записаны.

**Оценка:** ~3 минуты.

### Шаг 2: Публичные свойства обёрток

**Цель:** дать фабрике и скриптам публичный путь к объектам прототипа под обёртками.

**Файлы:** `numerical_solver/gpn_multiphase_solver/pvt/prototype_adapter.py`, `numerical_solver/gpn_multiphase_solver/pvt/table_full.py`, `numerical_solver/tests/test_factory_prototype.py`.

**Контекст:** свойство без сеттера (`@property`) открывает объект только для чтения: `adapter.proto_pvt = x` даёт `AttributeError`. Так внешний код не может подменить общий объект и разорвать «один источник» PVT/ОФП. Приватные поля остаются — свойства их лишь открывают.

**Что сделать:**

1. Тесты (сначала — красные). В `tests/test_factory_prototype.py` после класса `TestPVTConsistency` (кончается на `:249`, перед разделителем секции `E. Ошибки конфигурации`) вставить:
   ```python
   class TestWrapperAccess:
       """Публичный доступ к объектам прототипа под обёртками (DEBT-006).

       Фабрика и скрипты графиков берут BlackOilPVT и TabulatedRelPerm через
       свойства, а не через приватные поля _hydro, _pvt, _rp. Свойства только
       для чтения: подмена объекта разорвала бы «один источник» PVT/ОФП для
       прототипа и наших модулей (vault/knowledge/decisions/согласованность-pvt-hydro.md).
       """

       def _wrappers(self):
           """Три обёртки над объектами-метками: конструкторы лишь сохраняют ссылки."""
           proto_pvt, proto_rp = object(), object()
           adapter = PrototypePVTAdapter(proto_pvt, rho_o_std=850.0, rho_g_std=0.85)
           table = TableFullPVT(adapter, c_p_oil=2000.0, c_p_gas=2200.0,
                                mu_JT_oil=-4e-7, mu_JT_gas=3e-6, L_degas=0.0)
           rp = PrototypeRPAdapter(proto_rp)
           return proto_pvt, proto_rp, adapter, table, rp

       def test_prototype_pvt_adapter_proto_pvt(self):
           """PrototypePVTAdapter.proto_pvt — тот самый объект, что передан в конструктор."""
           proto_pvt, _, adapter, _, _ = self._wrappers()
           assert adapter.proto_pvt is proto_pvt

       def test_table_full_pvt_hydro(self):
           """TableFullPVT.hydro — тот самый адаптер, а через него — объект прототипа."""
           proto_pvt, _, adapter, table, _ = self._wrappers()
           assert table.hydro is adapter
           assert table.hydro.proto_pvt is proto_pvt

       def test_prototype_rp_adapter_proto_rp(self):
           """PrototypeRPAdapter.proto_rp — тот самый объект, что передан в конструктор."""
           _, proto_rp, _, _, rp = self._wrappers()
           assert rp.proto_rp is proto_rp

       def test_accessors_read_only(self):
           """Присвоить свойству нельзя — AttributeError: общий объект не подменить."""
           _, _, adapter, table, rp = self._wrappers()
           for obj, name in ((adapter, "proto_pvt"), (table, "hydro"), (rp, "proto_rp")):
               with pytest.raises(AttributeError):
                   setattr(obj, name, object())
   ```
   `PrototypePVTAdapter`, `PrototypeRPAdapter`, `TableFullPVT`, `pytest` в файле уже импортированы (`:20, 28-29`).
   Прогон: `& $PY -m pytest tests/test_factory_prototype.py -q -k TestWrapperAccess` → **4 failed**: в трёх тестах — `AttributeError` (свойств нет); в `test_accessors_read_only` — `DID NOT RAISE` (без свойства `setattr` просто создаёт новый атрибут экземпляра, исключения нет). После правки — 4 passed.

2. `pvt/prototype_adapter.py`, класс `PrototypePVTAdapter`, после свойства `rho_g_std` (`:27-29`), перед `def Rs_eq`:
   ```python
       @property
       def proto_pvt(self):
           """BlackOilPVT прототипа под адаптером — тот же объект, что у модели (DEBT-006)."""
           # Публичный путь для фабрики и скриптов графиков вместо приватного
           # _pvt. Без сеттера: подмена объекта разорвала бы «один источник PVT»
           # (vault/knowledge/decisions/согласованность-pvt-hydro.md).
           return self._pvt
   ```
3. Там же, класс `PrototypeRPAdapter`, после `__init__` (`:53-54`), перед `def kro`:
   ```python
       @property
       def proto_rp(self):
           """TabulatedRelPerm прототипа под адаптером — тот же объект, что у модели (DEBT-006)."""
           # Без сеттера — по той же причине, что proto_pvt
           return self._rp
   ```
4. `pvt/table_full.py`, после `__init__` (`:15-24`), перед `@property def rho_o_std` — в компактном стиле соседних методов:
   ```python
       # Гидро-часть для фабрики и скриптов графиков (DEBT-006): BlackOilPVT
       # прототипа — table_pvt.hydro.proto_pvt, без приватных полей. Без сеттера.
       @property
       def hydro(self) -> PrototypePVTAdapter: return self._hydro
   ```

**Проверка после шага:**
- `& $PY -m pytest tests/test_factory_prototype.py -q -k TestWrapperAccess` → 4 passed.
- Регресс: быстрый — число = baseline + 4, все зелёные.

**Подводные камни:** `PrototypePVTAdapter.__init__` с `object()` вместо `BlackOilPVT` работает: конструктор только сохраняет ссылку (`:15-18`).

**Зависимости:** требует шаг 1; блокирует шаги 3–5.

**Оценка:** ~15 строк кода, ~45 строк тестов, ~15 минут.

### Шаг 3: Фабрика выбирает ветку по классу

**Цель:** убрать `hasattr` из `_get_or_create_proto_pvt` и `_get_or_create_proto_rp`.

**Файлы:** `numerical_solver/gpn_multiphase_solver/factory.py`, `numerical_solver/tests/test_factory_standing_hydro.py`, `numerical_solver/tests/test_factory_prototype.py`.

**Контекст:** сейчас любой объект с полями `_hydro._pvt` или `_rp` уходит в ветку «извлечь объект прототипа», а переименование поля в обёртке уводит таблицу в ветку «обернуть / протабулировать» (см. «Контекст» — для ОФП это молча сдвигает порог активации газа с 0.6 на 0.79). После шага ветку определяет класс: `TableFullPVT`, `PrototypeRPAdapter`.

**Что сделать:**

1. Тесты, которые красные до правки. В `tests/test_factory_standing_hydro.py`:
   - импорты (`:8-21`): добавить `from types import SimpleNamespace`; в импорт из `gpn_multiphase_solver.factory` (`:15-17`) — `_get_or_create_proto_pvt`; строки `from gpn_multiphase_solver.pvt.hydro_to_blackoil_adapter import HydroPVTtoBlackOilAdapter` и `from radial_blackoil.relperm import TabulatedRelPerm` (прототип в `sys.path` кладёт `tests/conftest.py`);
   - после класса `TestCoreyToTabulated` (кончается на `:181`) вставить:
   ```python
   class TestBranchByClass:
       """Ветку фабрики выбирает класс объекта, а не имена его приватных полей (DEBT-006).

       До DEBT-006 фабрика проверяла hasattr(pvt, '_hydro') и hasattr(relperm,
       '_rp'): любой объект с полями таких имён уходил в ветку «извлечь объект
       прототипа», а переименование поля в обёртке — в ветку «обернуть или
       протабулировать». Обе ошибки молчаливые. Здесь объектам Стендинга и Кори
       подставлены посторонние поля с «нужными» именами — ветка не должна
       измениться.
       """

       def test_pvt_branch_ignores_private_field_names(self):
           """StandingFullPVT с посторонним _hydro._pvt по-прежнему оборачивается адаптером."""
           pvt = _create_pvt(load_config(BASELINE))
           pvt._hydro = SimpleNamespace(_pvt="посторонний объект")
           proto = _get_or_create_proto_pvt(pvt, P0)
           assert isinstance(proto, HydroPVTtoBlackOilAdapter)

       def test_rp_branch_ignores_private_field_names(self):
           """CoreyRP с посторонним _rp по-прежнему табулируется на 101 узле."""
           corey = CoreyRP(S_or=0.2, S_gc=0.05, n_o=2.0, n_g=2.0)
           corey._rp = "посторонний объект"
           proto = _get_or_create_proto_rp(corey)
           assert isinstance(proto, TabulatedRelPerm)
           assert proto.sg.size == 101
   ```
   Прогон: `& $PY -m pytest tests/test_factory_standing_hydro.py -q -k TestBranchByClass` → **2 failed** (функции возвращают строку `"посторонний объект"`; проверено при планировании).

2. Тесты-стражи тождества (зелёные до и после). В `tests/test_factory_prototype.py`:
   - импорт из фабрики (`:23-26`) дополнить: `_create_pvt, _create_relperm, _get_or_create_proto_pvt, _get_or_create_proto_rp`;
   - в класс `TestPVTConsistency` (после `test_bo_consistency`) добавить:
   ```python
       def test_proto_pvt_shared_for_table(self):
           """Табличная PVT: прототипу — тот же BlackOilPVT, что под обёрткой (DEBT-006)."""
           config = load_config(TABLE_CONFIG)
           pvt = _create_pvt(config)
           proto = _get_or_create_proto_pvt(pvt, config.initial_conditions.p0)
           assert proto is pvt.hydro.proto_pvt

       def test_proto_rp_shared_for_table(self):
           """Табличная ОФП: прототипу — тот же TabulatedRelPerm, а не 101 узел (DEBT-006)."""
           relperm = _create_relperm(load_config(TABLE_CONFIG))
           assert _get_or_create_proto_rp(relperm) is relperm.proto_rp
   ```
   - тест без утверждений `test_relperm_is_prototype_adapter` (`:163-168`) **заменить** на:
   ```python
       def test_prototype_relperm_from_csv(self):
           """Прототип получает табличную ОФП с узлами CSV, а не пересчёт на 101 узле (DEBT-006).

           Пересчёт на сетке np.linspace(0, 1, 101) — ветка CoreyRP. Для таблицы
           он дал бы 101 узел и сдвинул порог активации газа sg_activation_cap
           (BUG-018, radial_blackoil/blackoil.py:49-54 — последний узел с
           k_ro > 0) с 0.6 на 0.79: в configs/table_pvt/relperm.csv k_ro = 0
           впервые в узле 0.8, предыдущий узел — 0.6, а на 101 узле — 0.79.
           Замер при планировании DEBT-006: на примерах 04 и 05 такая подмена
           меняет историю лишь в последних битах (отн. ≤ 4e-14) — числовые
           тесты её не видят, видит только этот.
           """
           config = load_config(TABLE_CONFIG)
           assert isinstance(_create_relperm(config), PrototypeRPAdapter)
           simulator, _ = SimulatorFactory.from_config(config)
           model = simulator._hydro._model
           Sg, _, _ = _read_relperm_csv(config.config_dir / config.relperm.file)
           np.testing.assert_array_equal(model.relperm.sg, Sg)
           assert model.sg_activation_cap == 0.6
   ```
   Прежнее имя вводило в заблуждение (тест ничего не проверял); число тестов от замены не меняется. Значения 6 узлов `[0, 0.1, 0.2, 0.4, 0.6, 0.8]` и порог 0.6 проверены при планировании.

3. Правка `factory.py`, `_get_or_create_proto_pvt` (`:454-463`). До:
   ```python
       if hasattr(pvt, '_hydro') and hasattr(pvt._hydro, '_pvt'):
           return pvt._hydro._pvt

       return HydroPVTtoBlackOilAdapter(pvt, p_max_pa=p0)
   ```
   После:
   ```python
       # DEBT-006: ветку выбирает класс, а не наличие приватных полей. Прежняя
       # проверка поля _hydro через hasattr при переименовании поля молча уводила
       # таблицу в ветку адаптера; теперь переименование свойства — AttributeError.
       if isinstance(pvt, TableFullPVT):
           # Тот же объект, что под обёрткой у наших модулей: один источник PVT
           return pvt.hydro.proto_pvt

       return HydroPVTtoBlackOilAdapter(pvt, p_max_pa=p0)
   ```
4. `_get_or_create_proto_rp` (`:466-479`). До:
   ```python
       if hasattr(relperm, '_rp'):
           return relperm._rp
   ```
   После:
   ```python
       # DEBT-006: ветка — по классу, как у PVT
       if isinstance(relperm, PrototypeRPAdapter):
           # Тот же TabulatedRelPerm: узлы таблицы, а с ними и порог активации
           # газа sg_activation_cap (BUG-018) — из CSV, а не из пересчёта на 101 узел
           return relperm.proto_rp
   ```
   Докстринги обеих функций верны и после правки — не трогать.

**Проверка после шага:**
- `& $PY -m pytest tests/test_factory_standing_hydro.py tests/test_factory_prototype.py -q` → все зелёные, в том числе 2 бывших красных.
- Grep `hasattr\(` в `gpn_multiphase_solver/factory.py` → одна строка (`:450`, убирается шагом 4).
- Регресс: быстрый — число = baseline + 8, все зелёные.

**Подводные камни:**
- `isinstance` — по классам, уже импортированным в `factory.py:17-18`; новых импортов в пакете нет.
- Тест `test_prototype_relperm_from_csv` сравнивает `float == 0.6`: значение берётся из массива узлов (`float(sg[k])`), а не вычисляется — равенство точное.

**Зависимости:** требует шаг 2; блокирует шаг 4.

**Оценка:** ~10 строк кода, ~60 строк тестов, ~20 минут.

### Шаг 4: Адаптер получает тот же FullPVT, что энергия и Simulator

**Цель:** убрать третью проверку `hasattr` (`factory.py:450`) и сделать объект PVT общим для адаптера, решателя энергии и `Simulator`.

**Файлы:** `numerical_solver/gpn_multiphase_solver/factory.py`, `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`, `numerical_solver/tests/test_factory_prototype.py`, `numerical_solver/tests/test_factory_standing_hydro.py`, `vault/issues/debt-006/probes/fingerprint_after.out.txt` (новый).

**Контекст:** сейчас табличный путь отдаёт адаптеру `PrototypePVTAdapter` (развёрнутый из `TableFullPVT`), а энергии и `Simulator` — сам `TableFullPVT`; у Стендинга все трое получают один объект. Развёртывание ничего не даёт: `TableFullPVT` делегирует гидро-методы без арифметики. Заметка `P1-адаптер-единицы.md:160-167` изначально задумывала ровно один объект («`energy = EnergySolver(grid, our_pvt, ...)  # тот же our_pvt`»).

**Что сделать:**

1. Тесты (красный — один). В `tests/test_factory_prototype.py`, класс `TestPVTConsistency`, заменить `test_pvt_objects_are_same` и `test_bo_consistency` (`:219-249`). До — см. файл: `hydro._pvt._pvt`, `simulator._pvt._hydro`, `our_pvt._pvt`. После:
   ```python
       def test_pvt_objects_are_same(self):
           """Один BlackOilPVT у прототипа и обёртки; один FullPVT у адаптера, энергии, Simulator."""
           config = load_config(TABLE_CONFIG)
           simulator, _ = SimulatorFactory.from_config(config)

           hydro = simulator._hydro
           assert isinstance(hydro, PrototypeHydroAdapter)

           # Прототип считает тем же BlackOilPVT, что лежит под TableFullPVT
           assert hydro._model.pvt is simulator._pvt.hydro.proto_pvt
           # Пересчёт потоков в адаптере, энергия и Simulator — один объект
           # FullPVT (DEBT-006; прежде адаптер получал развёрнутый PrototypePVTAdapter)
           assert hydro._pvt is simulator._pvt
           assert simulator._energy._pvt is simulator._pvt

       def test_bo_consistency(self):
           """Bo через обёртку и через прототип совпадают."""
           config = load_config(TABLE_CONFIG)
           simulator, _ = SimulatorFactory.from_config(config)

           our_pvt = simulator._pvt.hydro   # PrototypePVTAdapter
           proto_pvt = our_pvt.proto_pvt    # BlackOilPVT
   ```
   — далее тело `test_bo_consistency` без изменений (`:242-249`).
   В `tests/test_factory_standing_hydro.py`, класс `TestFactoryStandingHydro`, после `test_standing_creates_prototype_hydro` (`:44-48`) добавить:
   ```python
       def test_standing_pvt_shared(self):
           """Стендинг: прототипу — адаптер над тем же StandingFullPVT, что у энергии (DEBT-006)."""
           simulator, _ = SimulatorFactory.from_config(load_config(BASELINE))
           model_pvt = simulator._hydro._model.pvt
           assert isinstance(model_pvt, HydroPVTtoBlackOilAdapter)
           # Поле адаптера читает тест, а не фабрика: это проверка тождества,
           # а не выбор ветки
           assert model_pvt._hydro is simulator._pvt
           assert simulator._hydro._pvt is simulator._pvt
           assert simulator._energy._pvt is simulator._pvt
   ```
   Прогон: `& $PY -m pytest tests/test_factory_prototype.py tests/test_factory_standing_hydro.py -q -k "pvt_objects_are_same or bo_consistency or standing_pvt_shared"` → **1 failed** (`test_pvt_objects_are_same`: `hydro._pvt` — `PrototypePVTAdapter`, а не `TableFullPVT`), 2 passed.

2. `factory.py`, конец `_create_prototype_hydro` (`:449-451`). До:
   ```python
       # our_pvt: HydroPVT для PrototypeHydroAdapter (пересчёт потоков)
       our_pvt = pvt._hydro if hasattr(pvt, '_hydro') else pvt
       return PrototypeHydroAdapter(model, grid, our_pvt)
   ```
   После:
   ```python
       # Пересчёт потоков (Q, u, m) — тем же объектом FullPVT, что у решателя
       # энергии и Simulator (DEBT-006). Прежде табличный путь разворачивал
       # TableFullPVT до PrototypePVTAdapter проверкой поля _hydro через hasattr;
       # числа те же побитово: TableFullPVT делегирует гидро-методы без
       # арифметики, а rho_o, rho_g — общие методы HydroPVT.
       return PrototypeHydroAdapter(model, grid, pvt)
   ```
3. `hydro/prototype_adapter.py`, докстринг `__init__` (`:52`). До:
   ```
           pvt         — наш HydroPVT (PrototypePVTAdapter, обёртка того же BlackOilPVT)
   ```
   После:
   ```
           pvt         — наш HydroPVT; фабрика передаёт тот же FullPVT, что решателю энергии (DEBT-006)
   ```
   Аннотацию `pvt: HydroPVT` не менять: адаптеру нужны только гидро-методы. ⚠️ Эту же строку переписывает DEBT-048 — см. «Порядок влития».

4. Отпечаток после правки:
   ```powershell
   cd $WT
   & $PY "$P\history_fingerprint.py" > "$P\fingerprint_after.out.txt"
   Compare-Object (Get-Content "$P\fingerprint_before.out.txt") (Get-Content "$P\fingerprint_after.out.txt")
   ```
   Ожидание: **пустой вывод** — все три отпечатка и контрольные числа совпали; первая строка обоих файлов — путь worktree. Любое расхождение — остановиться: правка строки 450 обязана быть побитовой; разобрать, какой метод `HydroPVT` дал другой результат.

**Проверка после шага:**
- Прогон из п. 1 → 3 passed.
- Grep `hasattr\(|getattr\(` в `gpn_multiphase_solver/factory.py` → пусто.
- Отпечаток — совпал (п. 4).
- Регресс: быстрый — число = baseline + 9, все зелёные.

**Подводные камни:** чеклист, пункты «Тип объекта адаптера» и «Тождество объектов».

**Зависимости:** требует шаг 3.

**Оценка:** ~6 строк кода, ~30 строк тестов, ~15 минут.

### Шаг 5: Скрипты графиков — по классу и публичным свойствам

**Цель:** `_pvt_table_nodes` и `_table_nodes` не читают приватные поля.

**Файлы:** `numerical_solver/examples/pvt_plot.py`, `numerical_solver/examples/relperm_plot.py`, `numerical_solver/tests/test_examples.py`.

**Контекст:** оба скрипта находят узлы таблиц, проходя по цепочке приватных полей через `getattr(..., None)`. Переименование поля молча возвращает `None`, и маркеры узлов исчезают с `pvt.png`/`relperm.png`. `_table_nodes` тестов не имеет; узлы PVT проверяют тесты `TestPvtPlot`, почти все — на фикстуре `results` (метка `slow`), быстрый — только `test_p_branch_follows_rs0_row` (`test_examples.py:1197-1209`, табличный путь).

**Что сделать:**

1. Тесты (зелёные до и после — страж поведения). В `tests/test_examples.py` после класса `TestWorkingRange` (кончается на `:1435`), перед разделителем секции `K. Сценарий 04a` (`:1438-1440`) вставить:
   ```python
   # ═══════════════════════════════════════════════════════════
   # J3. Узлы таблиц на графиках — по классу модели (DEBT-006)
   # ═══════════════════════════════════════════════════════════

   class TestTableNodesByClass:
       """Скрипты графиков находят узлы таблиц по классу модели, а не по приватным полям.

       До DEBT-006 _table_nodes (relperm_plot.py) тестов не имел, а узлы PVT
       проверяли в основном тесты на фикстуре results (метка slow). Здесь —
       быстрые проверки без расчёта.
       """

       def test_relperm_nodes_from_csv(self):
           """Табличная ОФП примера 04: узлы — ровно строки relperm.csv."""
           from gpn_multiphase_solver.factory import _create_relperm, _read_relperm_csv
           cfg = load_config(EXAMPLES_DIR / "04_table_table" / "config.json")
           nodes = _relperm_module()._table_nodes(_create_relperm(cfg))
           expected = _read_relperm_csv(cfg.config_dir / cfg.relperm.file)
           assert nodes is not None, "у табличной ОФП узлы обязаны быть"
           for got, exp in zip(nodes, expected):
               np.testing.assert_array_equal(got, exp)

       def test_relperm_nodes_none_for_corey(self):
           """Кори примера 03: выделенных точек нет — None."""
           from gpn_multiphase_solver.factory import _create_relperm
           cfg = load_config(EXAMPLES_DIR / "03_standing_corey" / "config.json")
           assert _relperm_module()._table_nodes(_create_relperm(cfg)) is None

       def test_pvt_nodes_none_for_standing(self):
           """Стендинг примера 03: узлов PVT нет — None (без фикстуры results, DEBT-006)."""
           cfg = load_config(EXAMPLES_DIR / "03_standing_corey" / "config.json")
           Rs0 = float(cfg.initial_conditions.Rs0)
           assert _pvt_module()._pvt_table_nodes(_pvt_of_config(cfg), Rs0) is None
   ```
   `_relperm_module` (`:1352`), `_pvt_module` (`:918`), `_pvt_of_config` (`:926`), `EXAMPLES_DIR` (`:26`), `load_config` (`:24`), `np` (`:20`) определены выше в файле.
   Прогон: `& $PY -m pytest tests/test_examples.py -q -k TestTableNodesByClass` → 3 passed (до правки скриптов).

2. `examples/pvt_plot.py`:
   - импорт после `:72` (`from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402`):
     ```python
     from gpn_multiphase_solver.pvt.table_full import TableFullPVT  # noqa: E402
     ```
   - `_pvt_table_nodes` (`:132-151`): в докстринге (`:135-136`) «Цепочка обёрток: TableFullPVT._hydro -> PrototypePVTAdapter._pvt ->» → «Цепочка обёрток: TableFullPVT.hydro -> PrototypePVTAdapter.proto_pvt ->». Тело, до:
     ```python
         hydro = getattr(pvt, "_hydro", None)
         proto = getattr(hydro, "_pvt", None) if hydro is not None else None
         if proto is None or not hasattr(proto, "gp"):
             return None
     ```
     После:
     ```python
         # Табличный ли PVT — по классу, BlackOilPVT — через публичные свойства
         # (DEBT-006). Прежде getattr по приватным _hydro, _pvt: их переименование
         # молча убирало бы маркеры узлов с графика.
         if not isinstance(pvt, TableFullPVT):
             return None
         proto = pvt.hydro.proto_pvt
     ```
     Проверка `hasattr(proto, "gp")` уходит: под `TableFullPVT` фабрика всегда кладёт `BlackOilPVT` (`factory.py:132-152`).

3. `examples/relperm_plot.py`, `_table_nodes` (`:42-54`). До:
   ```python
       """Узлы таблицы (Sg, kro, krg), если модель табличная, иначе None.

       PrototypeRPAdapter оборачивает TabulatedRelPerm прототипа в `_rp`;
       там узлы лежат в полях sg / kro_tab / krg_tab (radial_blackoil/relperm.py).
       У аналитических моделей (CoreyRP) выделенных точек нет — возвращаем None.
       """
       proto = getattr(relperm, "_rp", None)
       if proto is None or not hasattr(proto, "sg"):
           return None
   ```
   После:
   ```python
       """Узлы таблицы (Sg, kro, krg), если модель табличная, иначе None.

       PrototypeRPAdapter оборачивает TabulatedRelPerm прототипа (свойство
       proto_rp); там узлы лежат в полях sg / kro_tab / krg_tab
       (radial_blackoil/relperm.py). У аналитических моделей (CoreyRP)
       выделенных точек нет — возвращаем None.
       """
       # Импорт локальный — как _create_relperm в plot_relperm
       from gpn_multiphase_solver.pvt.prototype_adapter import PrototypeRPAdapter
       # По классу, а не по приватному полю _rp через getattr (DEBT-006):
       # переименование поля молча убирало бы узлы с графика
       if not isinstance(relperm, PrototypeRPAdapter):
           return None
       proto = relperm.proto_rp
   ```
   Строки `return (np.asarray(proto.sg, float), ...)` (`:52-54`) не менять.

**Проверка после шага:**
- `& $PY -m pytest tests/test_examples.py -q -k "TestTableNodesByClass or test_p_branch_follows_rs0_row"` → 4 passed.
- `& $PY -m pytest tests/test_example_scripts.py -q` → зелёные (имена импортов скриптов существуют, DEBT-046).
- Grep `getattr\(.*"(_hydro|_pvt|_rp)"` по `examples/` → пусто.
- Регресс: быстрый — число = baseline + 12, все зелёные. Медленные тесты узлов PVT (`test_nodes_units`, `test_nodes_none_for_analytical_pvt`, `test_table_nodes_split_by_phase`, `test_table_nodes_in_working_range`) — в полном прогоне шага 7.

**Подводные камни:** `examples/` — не пакет; модули грузятся через `sys.path.insert(0, EXAMPLES_DIR)` (`test_examples.py:918-923, 1352-1357`). Новые импорты из `gpn_multiphase_solver` работают так же, как уже имеющиеся (`pvt_plot.py:71-72`, `relperm_plot.py:90`).

**Зависимости:** требует шаг 2 (свойства). От шагов 3–4 не зависит.

**Оценка:** ~15 строк кода, ~35 строк тестов, ~15 минут.

### Шаг 6: Vault

**Цель:** заметки отражают новый способ доступа.

**Файлы:** `vault/knowledge/decisions/согласованность-pvt-hydro.md`, `vault/knowledge/decisions/P1-адаптер-единицы.md`.

**Что сделать:**

1. `согласованность-pvt-hydro.md` — перед разделом `## Связанные заметки` (`:100`) вставить:
   ```markdown
   ## Как фабрика получает объекты прототипа (DEBT-006)

   `SimulatorFactory` выбирает ветку по классу, а не по приватным полям обёрток:

   | Объект наших модулей | Прототипу (`RadialBlackOilModel`) |
   |---|---|
   | `TableFullPVT` | `pvt.hydro.proto_pvt` — тот же `BlackOilPVT` |
   | любой другой `HydroPVT` (`StandingFullPVT`) | `HydroPVTtoBlackOilAdapter(pvt, p_max_pa=p0)` |
   | `PrototypeRPAdapter` | `relperm.proto_rp` — тот же `TabulatedRelPerm` |
   | любая другая `RelPermModel` (`CoreyRP`) | `TabulatedRelPerm` на 101 узле `np.linspace(0, 1, 101)` |

   Свойства `hydro`, `proto_pvt`, `proto_rp` — только для чтения. `PrototypeHydroAdapter`, `TridiagEnergySolver` и `Simulator` держат **один** объект `FullPVT`. Объект ОФП из фабрики нужен только для сборки ОФП прототипа: наши модули в расчёте его не держат (пересчёт потоков идёт от покомпонентных потоков прототипа).

   До DEBT-006 ветку выбирали `hasattr(pvt, '_hydro')` и `hasattr(relperm, '_rp')`. Переименование приватного поля молча уводило таблицу ОФП в табуляцию на 101 узле: порог активации газа `sg_activation_cap` (BUG-018) у таблиц примеров сдвигался с 0.6 на 0.79, история менялась в последних битах — числовые тесты этого не видят. Скрипты графиков (`examples/pvt_plot.py`, `examples/relperm_plot.py`) тоже переведены на свойства.
   ```
2. `P1-адаптер-единицы.md` — после блока кода `:161-167` (строка `energy = EnergySolver(grid, our_pvt, ...)   # тот же our_pvt`) вставить:
   ```markdown
   > ⚠️ **DEBT-006 (2026-10):** фабрика передаёт адаптеру не `PrototypePVTAdapter`, а сам `FullPVT` (`TableFullPVT` или `StandingFullPVT`) — тот же объект, что решателю энергии, как и задумано здесь («тот же our_pvt»). До DEBT-006 табличный путь разворачивал `TableFullPVT` до `PrototypePVTAdapter`; числа от этого не зависели.
   ```
   И в том же файле раздел «### 4. PVT для вычисления Bo, Bg, ρ в Adapter — РЕШЕНО» (`:457-463`): строка «**Решение:**» (`:459`) утверждает «Factory гарантирует, что `self._pvt` = `PrototypePVTAdapter(proto_pvt)`» — после шага 4 это неверно. Заменить второе предложение строки `:459`:
   - до: «Factory гарантирует, что `self._pvt` = `PrototypePVTAdapter(proto_pvt)`, где `proto_pvt` — тот же объект `BlackOilPVT`, что и `model.pvt`.»
   - после: «Factory передаёт в `self._pvt` тот же объект `FullPVT`, что решателю энергии и `Simulator` (DEBT-006; до него — развёрнутый `PrototypePVTAdapter`); у табличного PVT под ним — тот же объект `BlackOilPVT`, что и `model.pvt`.»

   Смысл решения («Все модули (Adapter, EnergySolver) получают один объект HydroPVT», `:461`) шаг 4 не отменяет, а восстанавливает: до DEBT-006 адаптер и энергия держали **разные** объекты (`PrototypePVTAdapter` и `TableFullPVT`). Заметка `P5-pvt-архитектура.md:364-366` (`PrototypeHydroAdapter(model, grid, pvt: FullPVT)`) с шагом 4 уже согласна — не править.
3. Реестр (`vault/roadmap/известные баги и технический долг.md`, секция DEBT-006) — статус ✅ и итог ставит `/implement` по своему контракту.

**Проверка:** `& $PY -m pytest tests/ --collect-only -q` — число прежнее (шаг правит только документы).

**Оценка:** ~10 минут.

### Шаг 7: Итоговая проверка

**Цель:** всё зелёное, числа побитово прежние, приватных полей обёрток вне самих обёрток код не читает.

**Что сделать** (из `$WT`):
1. Grep (путь `$WT`, без `HydroSolverPrototype/**`):
   - `hasattr\(|getattr\(` в `gpn_multiphase_solver/factory.py` → пусто (комментарии шагов 3–4 пишут «через hasattr» без скобки — сюда не попадают);
   - `_hydro\._pvt|pvt\._hydro\b|relperm\._rp|getattr\(.*"(_hydro|_pvt|_rp)"` по `gpn_multiphase_solver/` и `examples/` → пусто (внутри обёрток — `self._pvt`, `self._rp`, `self._hydro`: шаблон их не ловит);
   - `hydro\._pvt\._pvt|simulator\._pvt\._hydro|our_pvt\._pvt\b` по `tests/` → пусто. Законные обращения новых тестов — `simulator._hydro._pvt` (поле адаптера-решателя), `model_pvt._hydro` (поле `HydroPVTtoBlackOilAdapter`, проверка тождества, шаг 4) — шаблон не ловит.
2. Отпечаток ещё раз (шаг 5 решатель не трогает, но итог фиксируется на конечном коде):
   ```powershell
   & $PY "$P\history_fingerprint.py" > "$P\fingerprint_after.out.txt"
   Compare-Object (Get-Content "$P\fingerprint_before.out.txt") (Get-Content "$P\fingerprint_after.out.txt")
   ```
   → пусто.
3. Полный прогон: `& $PY -m pytest tests/ -q` → число = baseline + 12, все зелёные (включая медленные тесты узлов PVT и примеров).

**Оценка:** ~12 минут (полный прогон ~10 мин).

## Тестовая стратегия

| Тест | Файл | Шаг | До правки | Предотвращает |
|---|---|---|---|---|
| `TestWrapperAccess::test_prototype_pvt_adapter_proto_pvt` | `tests/test_factory_prototype.py` (новый класс) | 2 | ✗ | свойство отдаёт не тот объект |
| `TestWrapperAccess::test_table_full_pvt_hydro` | там же | 2 | ✗ | то же для `TableFullPVT.hydro` и цепочки |
| `TestWrapperAccess::test_prototype_rp_adapter_proto_rp` | там же | 2 | ✗ | то же для ОФП |
| `TestWrapperAccess::test_accessors_read_only` | там же | 2 | ✗ (`DID NOT RAISE`: без свойства присваивание создаёт атрибут) | появление сеттера — подмена общего объекта |
| `TestBranchByClass::test_pvt_branch_ignores_private_field_names` | `tests/test_factory_standing_hydro.py` (новый класс) | 3 | ✗ (возвращает метку) | выбор ветки PVT по именам полей |
| `TestBranchByClass::test_rp_branch_ignores_private_field_names` | там же | 3 | ✗ (возвращает метку) | выбор ветки ОФП по именам полей |
| `TestPVTConsistency::test_proto_pvt_shared_for_table` | `tests/test_factory_prototype.py` | 3 | ✓ | таблица PVT уходит в ветку адаптера |
| `TestPVTConsistency::test_proto_rp_shared_for_table` | там же | 3 | ✓ | таблица ОФП уходит в табуляцию |
| `TestFactoryTablePVT::test_prototype_relperm_from_csv` (вместо пустого `test_relperm_is_prototype_adapter`) | там же | 3 | ✓ | прототип получает 101 узел и порог 0.79 — сквозная проверка через `from_config` |
| `TestPVTConsistency::test_pvt_objects_are_same` (переписан) | там же | 4 | ✗ (адаптер держит `PrototypePVTAdapter`) | адаптер, энергия, `Simulator` держат разные объекты |
| `TestPVTConsistency::test_bo_consistency` (переписан) | там же | 4 | ✓ | — (тот же смысл, публичный путь) |
| `TestFactoryStandingHydro::test_standing_pvt_shared` | `tests/test_factory_standing_hydro.py` | 4 | ✓ | Стендинг: прототип над другим объектом PVT |
| `TestTableNodesByClass::test_relperm_nodes_from_csv` | `tests/test_examples.py` (новый класс) | 5 | ✓ | маркеры узлов ОФП пропадают с `relperm.png` |
| `TestTableNodesByClass::test_relperm_nodes_none_for_corey` | там же | 5 | ✓ | маркеры на гладкой кривой Кори |
| `TestTableNodesByClass::test_pvt_nodes_none_for_standing` | там же | 5 | ✓ | маркеры на гладкой корреляции Стендинга |

**Прогон плана аудитом (2026-10-10, `4ab46f5`, код = `26ddb34`):** проба `vault/issues/debt-006/probes/plan_tests_check.py` накладывает правки шагов 2–5 в памяти (код не меняется) накопительно по стадиям и гоняет тела всех тестов таблицы выше, плюс существующий `test_p_branch_follows_rs0_row`. Итог (`plan_tests_check.out.txt`): колонка «До правки» подтверждена для всех 16 тестов, после своей правки и после шага 5 — все зелёные; отпечаток истории 03/04/05 с правками шагов 2–5 совпал с исходным побитово. Это проверка плана, а не замена шагов: при реализации тесты пишутся в файлы и гоняются pytest.

**Инвариант чисел:** проба `vault/issues/debt-006/probes/history_fingerprint.py` — SHA-256 по всей истории примеров 03, 04, 05 (состояния, потоки `HydroResult`, скважинные данные, балансы энергии и массы). Три примера покрывают три пути фабрики: Стендинг × Кори, таблица × таблица, Стендинг × таблица ОФП. Чувствительность проверена при планировании: подмена ОФП прототипа пересчётом на 101 узел меняет отпечатки 04 и 05 при изменениях истории порядка $10^{-14}$. Детерминизм проверен: два запуска подряд дали одинаковый вывод.

**Существующие тесты, покрывающие затронутый код** (должны остаться зелёными без правок): `tests/test_factory_prototype.py` (остальные классы), `tests/test_factory_standing_hydro.py::TestCoreyToTabulated` (Кори → 101 узел), `::TestStandingInitialState`, `tests/test_prototype_adapter.py` (адаптер на собственной фикстуре `PrototypePVTAdapter` — `:108-114`), `tests/test_hydro_to_blackoil_adapter.py`, `tests/test_prototype_activation_cap.py` (порог Кори 0.79 — `:59-62`), `tests/test_examples.py::TestPvtPlot` (узлы PVT), `tests/test_example_scripts.py`.

## Критерии завершения

- [ ] Шаги 1–7 выполнены.
- [ ] В `factory.py` нет `hasattr`/`getattr`; в `examples/` нет `getattr` по `_hydro`, `_pvt`, `_rp`.
- [ ] Отпечатки «до» и «после» совпадают (пустой `Compare-Object`), первая строка обоих — путь worktree.
- [ ] Полный прогон: baseline + 12, все зелёные.
- [ ] Заметки vault обновлены (шаг 6); реестр — статус и итог (`/implement`).
- [ ] Issue #88 прокомментирован результатом (`/implement`), закрывается при `/merge`.

## Связь формула → код

Формул задача не затрагивает: меняется только способ доступа к объектам и выбор ветки фабрики.

## Обнаруженные проблемы

1. **Тест без утверждений** `test_relperm_is_prototype_adapter` (`tests/test_factory_prototype.py:163-168`) — обещал проверить ОФП, ничего не проверял. Исправляется в шаге 3; отдельной записи не нужно.
2. **Неверный докстринг** `PrototypeHydroAdapter.__init__` (`hydro/prototype_adapter.py:52`): «PrototypePVTAdapter, обёртка того же BlackOilPVT» — для Стендинга неверно уже сейчас. Исправляется в шаге 4.
3. **Неточность описания issue #88** о последствиях для ОФП (см. «Контекст»): поправка — в комментарии `03-comment-plan.md`.
4. **Неточность записи реестра DEBT-006** («для Standing-PVT будет создан лишний адаптер», «595 тестов») — уточнение добавлено в запись при планировании.

Новых записей в реестрах не требуется.

## Связанные заметки

- [[согласованность-pvt-hydro]] — принцип «один объект PVT/ОФП» (правится в шаге 6)
- [[P1-адаптер-единицы]] — адаптер прототипа и единый `our_pvt` (правится в шаге 6)
- [[feat-014-hydro-to-blackoil-adapter]] — откуда развилка в фабрике
- [[bug-017 rs0-table-range-check]] — `isinstance(pvt, TableFullPVT)` и `_warn_initial_table_range`
- [[bug-022 newton-cell-relative-tolerance]], [[debt-048 shutin-remember-solving-stage]] — порядок влития
