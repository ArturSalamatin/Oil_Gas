## Описание

`SimulatorFactory` решает, извлечь ли готовый объект прототипа из обёртки или создать новый, по наличию **приватных** полей конкретных классов: `hasattr(pvt, '_hydro')`, `hasattr(pvt._hydro, '_pvt')`, `hasattr(relperm, '_rp')`. Фабрика тем самым опирается на внутреннее устройство `TableFullPVT`, `PrototypePVTAdapter` и `PrototypeRPAdapter`, а не на их явный интерфейс. Переименование приватного поля в обёртке меняет выбранную ветку без единой ошибки в месте выбора.

Приоритет низкий: код работает, все 1493 теста зелёные. Задача — архитектурная чистота и защита инварианта «один источник PVT/ОФП для прототипа и наших модулей» ([[согласованность-pvt-hydro]]).

## Текущее состояние

Три проверки `hasattr` в `numerical_solver/gpn_multiphase_solver/factory.py` (реестр называл две, третья — в `_create_prototype_hydro`):

| Строка | Код | Что выбирает |
|---|---|---|
| 460–461 | `if hasattr(pvt, '_hydro') and hasattr(pvt._hydro, '_pvt'): return pvt._hydro._pvt` | табличная PVT — отдать прототипу **тот же** `BlackOilPVT`; иначе обернуть в `HydroPVTtoBlackOilAdapter(pvt, p_max_pa=p0)` |
| 472–473 | `if hasattr(relperm, '_rp'): return relperm._rp` | табличная ОФП — отдать **тот же** `TabulatedRelPerm`; иначе протабулировать на 101 узле `np.linspace(0, 1, 101)` |
| 450 | `our_pvt = pvt._hydro if hasattr(pvt, '_hydro') else pvt` | какой объект PVT получит `PrototypeHydroAdapter` для пересчёта потоков |

Рядом, строка 446, — `isinstance(pvt, TableFullPVT)` перед `_warn_initial_table_range` (BUG-017, #45). Это проверка по типу, а не по приватному полю; фабрика — единственное место, где известны конкретные классы (докстринг модуля, строка 3), так что такая проверка здесь законна.

### Что на самом деле произойдёт при переименовании поля

Запись реестра утверждает, что ошибка «проявится как выбор неверной ветки… для Standing-PVT». Проверка по коду на `3dd0638` даёт другую картину — опасна ветка **ОФП**, а не PVT:

1. **PVT, переименование `PrototypePVTAdapter._pvt` или `TableFullPVT._hydro`.** Фабрика уйдёт в ветку Стендинга и обернёт `TableFullPVT` в `HydroPVTtoBlackOilAdapter`. Затем строка 446 (`isinstance(pvt, TableFullPVT)` — истина) вызовет `pvt_range_warnings(model, …)`, а та обратится к `model.pvt.gp` (`radial_blackoil/diagnostics.py:27`), которого у адаптера нет. Итог — `AttributeError` при сборке симулятора. Ошибка громкая, но её текст указывает на диагностику BUG-017, а не на причину. Защита здесь появилась случайно, после BUG-017, и исчезнет, если проверку диапазона таблиц когда-нибудь переделают.
2. **ОФП, переименование `PrototypeRPAdapter._rp`.** Фабрика молча протабулирует табличную ОФП на равномерной сетке из 101 узла на $[0, 1]$. Последствия:
   - таблица с узлами вне шага 0.01 в прототипе превратится в другую кусочно-линейную функцию, а наши модули (`PrototypeRPAdapter`) продолжат считать по исходной — **рассогласование $k_{ro}, k_{rg}$** между прототипом и пересчётом потоков;
   - табличная ОФП примеров заканчивается на $S_g = 0.8$ (`examples/04_table_table/relperm.csv`), а пересчитанная — на $S_g = 1$. Предупреждение прототипа `RELPERM Sg above table` (`diagnostics.py:51`) пропадёт без следа;
   - `sg_activation_cap` (`blackoil.py:89`) считается по узлам таблицы и тоже может сдвинуться.

   Ни одной ошибки, ни одного предупреждения. Тождество объектов ОФП в тестах **не проверяется**: `TestPVTConsistency` (`tests/test_factory_prototype.py:216–249`) проверяет только PVT.

## Целевое состояние

- В `factory.py` нет ни одного `hasattr` и ни одного обращения к приватному полю чужого класса.
- Изменение внутреннего устройства обёртки ломает сборку сразу и с понятной ошибкой (`AttributeError` на публичном свойстве, `NameError` на имени класса), а не переводит фабрику в другую ветку.
- Тождество объекта прототипа проверено тестами для **обеих** таблиц: PVT и ОФП.
- Числа не меняются: история примеров побитово совпадает с исходной.

## Затронутые файлы

| Файл | Строки | Роль |
|---|---|---|
| `numerical_solver/gpn_multiphase_solver/factory.py` | 382–451 | `_create_prototype_hydro`: строка 450 — третья проверка `hasattr` |
| `numerical_solver/gpn_multiphase_solver/factory.py` | 454–463 | `_get_or_create_proto_pvt` — `hasattr(pvt, '_hydro')`, `hasattr(pvt._hydro, '_pvt')` |
| `numerical_solver/gpn_multiphase_solver/factory.py` | 466–479 | `_get_or_create_proto_rp` — `hasattr(relperm, '_rp')` |
| `numerical_solver/gpn_multiphase_solver/factory.py` | 446–447 | `isinstance(pvt, TableFullPVT)` (BUG-017) — не меняется, упомянута как образец |
| `numerical_solver/gpn_multiphase_solver/pvt/prototype_adapter.py` | 16, 54 | `PrototypePVTAdapter._pvt`, `PrototypeRPAdapter._rp` — поля, которые читает фабрика |
| `numerical_solver/gpn_multiphase_solver/pvt/table_full.py` | 19 | `TableFullPVT._hydro` |
| `numerical_solver/gpn_multiphase_solver/pvt/base.py` | 19, 153 | ABC `HydroPVT`, `RelPermModel` — затрагивается только вариантом 1 |
| `numerical_solver/tests/test_factory_prototype.py` | 216–249 | `TestPVTConsistency`: читают `hydro._pvt._pvt`, `simulator._pvt._hydro` — приватные поля |
| `numerical_solver/tests/test_factory_standing_hydro.py` | 16, 161–181 | импортируют `_get_or_create_proto_rp` напрямую |
| `numerical_solver/tests/test_prototype_activation_cap.py` | 59 | докстринг ссылается на `factory._get_or_create_proto_rp` |

`_create_pvt` и `_create_relperm` — де-факто внешний интерфейс: их зовут около 15 мест в `examples/`, `tests/` и `deliverables/`. Их сигнатуры менять нельзя без правки всех вызовов.

## Анализ вариантов решения

### Вариант 1 — методы-контракты в ABC (предложение реестра)

**Суть.** `HydroPVT.as_blackoil_pvt(p_max_pa)` по умолчанию возвращает `HydroPVTtoBlackOilAdapter(self, p_max_pa)`; `TableFullPVT` и `PrototypePVTAdapter` переопределяют — отдают общий `BlackOilPVT`. `RelPermModel.as_tabulated_relperm()` по умолчанию табулирует на 101 узле; `PrototypeRPAdapter` переопределяет — отдаёт `_rp`. Фабрика вызывает метод, не глядя на тип.

**Изменения.** `pvt/base.py`, `pvt/table_full.py`, `pvt/prototype_adapter.py`, `factory.py`, тесты.

**Плюсы.** Фабрика вообще не различает типы; новая реализация ABC работает без правки фабрики.

**Минусы.**
- ABC физики узнаёт формат конкретного решателя (бар/сП, интерфейс `BlackOilPVT`). Это противоречит принципу, записанному в докстринге `pvt/base.py`: «HydroPVT/FullPVT — что описывает вещество», метод решения отделён.
- Реализация по умолчанию для ОФП требует `radial_blackoil.relperm.TabulatedRelPerm` — модуль ABC начинает зависеть от пакета прототипа (хотя бы ленивым импортом).
- Выбор «101 узел» — дискретизация под прототип — прячется в ABC.
- Методы видны всем потребителям ABC (`TridiagEnergySolver`, `Closure`, примеры), хотя нужны только фабрике.

### Вариант 2 — публичные свойства обёрток + `isinstance` в фабрике

**Суть.** Обёртки получают публичные свойства только для чтения: `PrototypePVTAdapter.proto_pvt`, `TableFullPVT.hydro`, `PrototypeRPAdapter.proto_rp`. Фабрика проверяет тип: `isinstance(pvt, TableFullPVT)` → `pvt.hydro.proto_pvt`; `isinstance(relperm, PrototypeRPAdapter)` → `relperm.proto_rp`; иначе — адаптер или табуляция, как сейчас. Строка 450 сводится к `our_pvt = pvt`: `TableFullPVT` делегирует все методы `HydroPVT` без арифметики, а `rho_o`, `rho_g` — общие методы базового класса, так что результат побитово тот же.

**Изменения.** `pvt/prototype_adapter.py` (2 свойства), `pvt/table_full.py` (1 свойство), `factory.py` (3 места), тесты.

**Плюсы.**
- Минимальная правка; ABC не трогаются.
- Фабрика и так единственное место, знающее конкретные классы, и уже проверяет `isinstance(pvt, TableFullPVT)` в строке 446 — проверки станут единообразными.
- Переименование поля → `AttributeError` на свойстве; переименование класса → `NameError` при импорте. Тихой смены ветки больше нет.

**Минусы.** Остаётся ветвление по типу: новая обёртка над таблицами прототипа потребует строки в фабрике. Но фабрику всё равно придётся править, чтобы такую обёртку создать.

### Вариант 3 — фабрика хранит исходные объекты с момента создания

**Суть.** `from_config` получает `BlackOilPVT` и `TabulatedRelPerm` прямо там, где их создаёт (`_create_pvt`, `_create_relperm`), и передаёт в `_create_prototype_hydro` отдельными аргументами. Разворачивать обёртки не нужно вовсе.

**Изменения.** Внутренние функции `_build_pvt(config) -> (FullPVT, BlackOilPVT | None)` и аналог для ОФП; `_create_pvt`/`_create_relperm` остаются тонкими обёртками ради ~15 внешних вызовов; `_create_prototype_hydro` — 6 аргументов; `_get_or_create_proto_*` исчезают, тесты на них переписываются.

**Плюсы.** Никакой проверки объектов — ни `hasattr`, ни `isinstance`; инвариант «один источник» выражен в месте создания.

**Минусы.** Больше всего правок; пара функций на одну работу (`_build_pvt` и `_create_pvt`); растёт сигнатура `_create_prototype_hydro`; выгода над вариантом 2 только теоретическая.

### Рекомендация

**Вариант 2** с упрощением строки 450 и обязательным тестом тождества ОФП — того самого пути, где сейчас возможен тихий сбой. Вариант 1 устраняет `isinstance` ценой связи ABC физики с форматом прототипа — обмен невыгодный. Окончательный выбор — на этапе `/plan-improve`.

## План решения

1. **Подготовка (исходный замер).**
   - Полный прогон: 1493 теста на `3dd0638`, все зелёные.
   - Сохранить историю примеров с тремя сочетаниями «PVT × ОФП»: `03_standing_corey` (Стендинг × Кори), `04_table_table` (таблица × таблица), `05_standing_table_rp` (Стендинг × таблица ОФП) — для побитового сравнения после правки.
2. **Реализация (по шагам, тесты после каждого).**
   1. Публичные свойства `proto_pvt`, `hydro`, `proto_rp` в обёртках; тесты на них.
   2. `_get_or_create_proto_pvt`, `_get_or_create_proto_rp` — `isinstance` по публичным классам вместо `hasattr`.
   3. Строка 450 → `our_pvt = pvt`.
   4. `TestPVTConsistency` — на публичные свойства вместо приватных полей.
   5. Новые тесты: (а) табличная ОФП — `model.relperm is relperm.proto_rp`; (б) Кори — прототип получает `TabulatedRelPerm` на 101 узле (уже есть, проверить); (в) Стендинг — прототип получает `HydroPVTtoBlackOilAdapter` над **тем же** объектом `StandingFullPVT`, что у энергетического решателя.
   6. Комментарий о BUG-017 у строки 446 — сверить с новой логикой.
3. **Верификация.**
   - `grep "hasattr(" factory.py` — пусто.
   - Полный прогон: 1493 + новые, все зелёные.
   - История трёх примеров побитово совпадает с исходной.
   - Обновить заметку [[согласованность-pvt-hydro]]: как фабрика получает объект прототипа.

## Ветка

`refactor/debt-006/factory-explicit-proto-access`

## Связанные issues

- Related: #45 (BUG-017 — `isinstance(pvt, TableFullPVT)` и `_warn_initial_table_range` в той же функции; именно она сейчас случайно ловит ошибку в ветке PVT)
- Related: #28 (DEBT-005 — уборка наследия FEAT-014 в той же фабрике)

## Связанные заметки в vault

- `vault/knowledge/decisions/согласованность-pvt-hydro.md` — принцип «один объект PVT/ОФП на всю симуляцию»
- `vault/roadmap/планируемые фичи.md` — FEAT-014 (`HydroPVTtoBlackOilAdapter`, откуда пошла развилка в фабрике)
- `vault/roadmap/известные баги и технический долг.md` — DEBT-006
