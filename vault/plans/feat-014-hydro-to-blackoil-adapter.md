---
tags:
  - план
  - инфраструктура
date: 2026-09-01
issue: FEAT-014
github: null
branch: feat/feat-014/hydro-to-blackoil-adapter
status: реализован
audit:
  date: 2026-09-01
  found: 0
  auto-fixed: 0
  manual-required: 0
  rounds: 5
---

# FEAT-014: Адаптер HydroPVT → BlackOilPVT для RadialBlackOilModel

## Мотивация

Сейчас `RadialBlackOilModel` (Newton-солвер прототипа) работает только с табличным
`BlackOilPVT`. Из-за этого в `SimulatorFactory` — жёсткая развилка:

- `pvt.model == "table"` → `PrototypeHydroAdapter` (полноценный Newton)
- `pvt.model == "standing"` → `AnalyticalHydroSolver` (заглушка: стационарный лог-профиль, без Ньютона, без разгазирования)

Пользователь, задавший `pvt.model = "standing"`, получает заглушку вместо настоящего
решателя. Это ложное впечатление работающей системы.

**Решение:** написать адаптер `HydroPVTtoBlackOilAdapter`, реализующий интерфейс
`BlackOilPVT` (прототипа), но делегирующий вычисления нашему `HydroPVT`.
Это позволит Factory всегда создавать `PrototypeHydroAdapter` — через адаптер.

## Подтип: Инфраструктура

Новой физики и формул нет. Задача: пересчёт единиц, адаптация интерфейсов,
рефакторинг Factory.


## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай связанные vault-заметки:
   - `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md`
   - `vault/knowledge/decisions/словарь-код-физика.md`
   - `vault/knowledge/decisions/конвенции-знаков.md`
   - `vault/knowledge/decisions/согласованность-pvt-hydro.md` — ключевой инвариант:
     один объект PVT разделяется между прототипом и нашими модулями
3. Создай ветку: `git checkout -b feat/feat-014/hydro-to-blackoil-adapter`
4. Прогони тесты (baseline):
   ```
   cd numerical_solver
   .venv/Scripts/python -m pytest tests/ -v
   ```
5. Начни с шага 0. После каждого шага: pytest


## Архитектура: что есть сейчас

### Два интерфейса PVT

**Наш `HydroPVT`** (`gpn_multiphase_solver/pvt/base.py:19`):
- Единицы: SI (Па, Па·с)
- Методы: `Rs_eq(p)`, `Bo(p, Rs)`, `Bg(p)`, `mu_o(p, Rs)`, `mu_g(p)`, `pb(Rs)`
- Свойства: `rho_o_std`, `rho_g_std`
- Реализации: `StandingFullPVT`, `PrototypePVTAdapter`

**Прототиповый `BlackOilPVT`** (`HydroSolverPrototype/.../radial_blackoil/pvt.py:3`):
- Единицы: бар, сП
- Методы: `rs_sat(p)`, `bo(p, rs)`, `mu_o(p, rs)`, `bg(p)`, `mu_g(p)`, `pb_of_rs(rs)`
- Атрибуты: `rs_values`, `pb` (массивы), `max_rs` (скаляр), `bo_sat`, `mu_sat`, `branches`, `_branch_arrays`
- Реализация: одна, табличная (PVTO)

### Что из `BlackOilPVT` реально используется снаружи

Исследование `blackoil.py` и `diagnostics.py` показало, что `RadialBlackOilModel`
вызывает **только**:

| Что | Где | Зачем |
|---|---|---|
| `bo(p, rs)`, `mu_o(p, rs)`, `bg(p)`, `mu_g(p)`, `rs_sat(p)` | `blackoil.py` | PVT-вычисления |
| `pvt.pb` (массив) | `_pressure_fd_step` (:148) | узлы для FD-шага якобиана |
| `pvt.max_rs` (скаляр) | `_trial_is_reasonable` (:183) | проверка разумности итерации |
| `pvt.rs_values`, `pvt.pb` | `diagnostics.py` | предупреждения о выходе за таблицу |

**НЕ используются** в `blackoil.py`: `bo_sat`, `mu_sat`, `branches`, `_branch_arrays`, `pb_of_rs`.

**Используются в `diagnostics.py`** (но не в `blackoil.py`): `gp` (массив давлений
газовой таблицы), `max_pressure_of_rs(rs)` (метод). `diagnostics.py` вызывается
из `simulation.py`, которую **наш код не использует** — `PrototypeHydroAdapter.solve()`
вызывает `model.advance()` напрямую. Поэтому адаптеру не нужно реализовывать `gp`
и `max_pressure_of_rs`.

### Существующий «обратный» адаптер

`PrototypePVTAdapter` (`gpn_multiphase_solver/pvt/prototype_adapter.py`) — адаптер
`BlackOilPVT → HydroPVT`: конвертирует p бар→Па на входе, μ сП→Па·с на выходе.

Новый `HydroPVTtoBlackOilAdapter` — зеркальный: `HydroPVT → BlackOilPVT`.


## Обратная совместимость

- [x] Существующие тесты пройдут без изменений (если не удалять `AnalyticalHydroSolver`)
- [x] Существующие конфиги работают без изменений (pvt.model="standing" и "table")
- [x] API существующих классов не меняется
- [x] Фича меняет внутреннюю реализацию Factory, но не внешний контракт

### Решение по `AnalyticalHydroSolver`

**Не удалять в этой задаче.** `AnalyticalHydroSolver` используется в 4 тестовых файлах
(test_hydro, test_simulator, test_output, test_val001) для тестирования EnergySolver,
output-системы и VAL-001. Удаление потребует переписывания ~10 тестов.

В этой задаче:
- Factory при `pvt.model = "standing"` переключается на `PrototypeHydroAdapter` (через адаптер)
- `AnalyticalHydroSolver` остаётся в кодовой базе для прямого использования в тестах
- Удаление `AnalyticalHydroSolver` → отдельная задача DEBT (после FEAT-014)


## Подводные камни

- ✅ **Размерности:** пересчёт Па↔бар, Па·с↔сП — зеркально к `PrototypePVTAdapter`
- ⚠️ **`pvt.pb` (массив узлов):** `BlackOilPVT.pb` — массив давлений насыщения на
  сетке `rs_values`. Для корреляции Standing кривая `pb(Rs)` — монотонная гладкая функция.
  Адаптер не имеет табличных «ветвей», поэтому кривая не имеет изломов (kinks).
  Но `_pressure_fd_step` использует `searchsorted` по `pvt.pb` для выбора направления
  FD-шага. Если массив содержит одну точку — `searchsorted` вернёт 0 или 1,
  `lower=-inf`, `upper=knot` (или наоборот) → FD-шаг всегда `+h`. Это корректно
  для гладкой кривой, но лучше задать несколько узлов для робастности диагностики.
  **Решение:** протабулировать `pb` на 10–20 равномерных точках Rs от 0 до `max_rs`.
  Это не «генерация PVT-таблицы» — это одноразовое заполнение вспомогательного массива
  для конечно-разностного якобиана.
- ✅ **`max_rs`:** `Rs_eq(p_max)` при верхнем давлении, задаваемом параметром.
- ✅ **Import-цепочки:** адаптер в `gpn_multiphase_solver/pvt/`, импорт `BlackOilPVT`
  из `radial_blackoil.pvt` — ленивый (lazy), как в `factory.py`. Без circular imports.
- ⚠️ **sys.path для radial_blackoil:** после FEAT-014 Factory **всегда** вызывает
  `_create_prototype_hydro` → ленивые imports `radial_blackoil.*`. Сейчас sys.path
  настроен только в test_factory_prototype.py и test_prototype_adapter.py. Все остальные
  тесты (test_simulator, test_val001, test_output), использующие Factory с standing,
  **сломаются** без централизованного sys.path. **Решение:** шаг 0 — conftest.py.
- ✅ **Обратная совместимость:** `AnalyticalHydroSolver` не удаляется → тесты не ломаются
- ⚠️ **Tolerance тестов VAL-001:** `_run_val001()` использует Factory. После FEAT-014
  Factory будет создавать `PrototypeHydroAdapter` вместо `AnalyticalHydroSolver`.
  Newton-солвер даст **численное** решение, которое не совпадает с аналитикой до `rtol=1e-12`.
  Тест `test_pressure_log_profile` (rtol=1e-12) и `test_G_o_constant` (rtol=1e-12)
  будут падать. **Решение:** ослабить tolerance в VAL-001 pipeline-тестах до rtol=1e-4
  (для Newton-солвера на 20 ячейках) или разделить тест — аналитический отдельно,
  pipeline отдельно.
- ⚠️ **Тесты test_simulator `TestFactory`:** `test_from_baseline` использует Factory →
  baseline.json (standing) → раньше был `AnalyticalHydroSolver`. После FEAT-014 будет
  `PrototypeHydroAdapter`. Тест проверяет `history.n_saved > 1` и `times[-1]` — должен
  пройти. Но `test_pressure_is_analytical_log_profile` (rtol=1e-12) — **в классе
  `TestPhysics`**, который конструирует `AnalyticalHydroSolver` напрямую → не затронут.


## Этапы реализации

### Шаг 0: Централизованный sys.path для radial_blackoil

**Цель:** после FEAT-014 Factory **всегда** вызывает `_create_prototype_hydro`,
что требует ленивых imports `from radial_blackoil.*`. Сейчас sys.path добавляется
только в тестах, которые явно используют прототип (test_factory_prototype.py,
test_prototype_adapter.py — строки 17–20). После FEAT-014 **все** тесты через Factory
(test_simulator, test_val001, test_output) тоже будут требовать radial_blackoil.

**Файлы:**
- Изменить: `numerical_solver/tests/conftest.py`

**Что сделать:**

Добавить в `conftest.py` централизованный sys.path setup:

```python
"""Общие fixtures для тестов gpn_multiphase_solver."""

import sys
from pathlib import Path

import pytest
import numpy as np

# radial_blackoil (прототип коллеги) — не установлен в venv,
# подключается через sys.path. Factory использует ленивые imports.
_PROTO_ROOT = Path(__file__).parent.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROTO_ROOT))
```

После этого удалить дублирующий sys.path setup из:
- `test_factory_prototype.py` (строки 17–20)
- `test_prototype_adapter.py` (строки 24–27)

**Проверка после шага:**
```
cd numerical_solver
.venv/Scripts/python -m pytest tests/ -v
```

**Зависимости:** нет (выполняется первым)
**Оценка:** ~10 строк, ~5 минут


### Шаг 1: Адаптер `HydroPVTtoBlackOilAdapter`

**Цель:** класс, реализующий интерфейс `BlackOilPVT` через делегирование нашему `HydroPVT`.

**Файлы:**
- Создать: `numerical_solver/gpn_multiphase_solver/pvt/hydro_to_blackoil_adapter.py`

**Контекст:**
Зеркало `PrototypePVTAdapter` (`prototype_adapter.py`). Тот конвертирует бар→Па на входе;
этот конвертирует Па→бар на входе. Тот конвертирует сП→Па·с на выходе; этот
конвертирует Па·с→сП на выходе.

`RadialBlackOilModel` работает в барах/сП. Наш `HydroPVT` — в Па/Па·с.

**Что сделать:**

1. Создать класс `HydroPVTtoBlackOilAdapter`:

```python
"""Адаптер HydroPVT (SI) → BlackOilPVT (бар/сП) для RadialBlackOilModel."""

import numpy as np
from ..units import BAR_TO_PA, PA_S_TO_CP


class HydroPVTtoBlackOilAdapter:
    """Обёртка HydroPVT → BlackOilPVT (бар/сП).

    Конвертирует p: бар→Па на входе в HydroPVT, μ: Па·с→сП на выходе.
    Bo, Bg, Rs — безразмерные, конвертация не нужна.
    """

    def __init__(self, hydro_pvt, p_max_pa: float, n_knots: int = 20):
        """
        hydro_pvt  — наш HydroPVT (StandingFullPVT, TableFullPVT._hydro и т.д.)
        p_max_pa   — верхнее давление (Па), определяет max_rs и диапазон rs_values
        n_knots    — число узлов для rs_values/pb (для FD-якобиана и диагностики)
        """
        self._hydro = hydro_pvt
        # Протабулировать кривую насыщения для атрибутов BlackOilPVT
        self.max_rs = float(hydro_pvt.Rs_eq(np.array([p_max_pa]))[0])
        rs_grid = np.linspace(0.0, self.max_rs, n_knots)
        self.rs_values = rs_grid
        # pb[i] = давление насыщения для Rs=rs_grid[i], в барах
        self.pb = hydro_pvt.pb(rs_grid) / BAR_TO_PA
        # bo_sat[i], mu_sat[i] — значения на кривой насыщения
        self.bo_sat = hydro_pvt.Bo(hydro_pvt.pb(rs_grid), rs_grid)
        self.mu_sat = hydro_pvt.mu_o(hydro_pvt.pb(rs_grid), rs_grid) * PA_S_TO_CP

    def _to_pa(self, p_bar):
        return np.asarray(p_bar, float) * BAR_TO_PA

    def rs_sat(self, p_bar):
        return self._hydro.Rs_eq(self._to_pa(p_bar))

    def pb_of_rs(self, rs):
        return self._hydro.pb(np.asarray(rs, float)) / BAR_TO_PA

    def bo(self, p_bar, rs):
        return self._hydro.Bo(self._to_pa(p_bar), np.asarray(rs, float))

    def mu_o(self, p_bar, rs):
        return self._hydro.mu_o(self._to_pa(p_bar), np.asarray(rs, float)) * PA_S_TO_CP

    def bg(self, p_bar):
        return self._hydro.Bg(self._to_pa(p_bar))

    def mu_g(self, p_bar):
        return self._hydro.mu_g(self._to_pa(p_bar)) * PA_S_TO_CP
```

2. Ключевые решения:
   - `p_max_pa` — передаётся извне (Factory знает начальное пластовое давление `p0`).
     `max_rs = Rs_eq(p0)` — максимальное газосодержание при начальном давлении.
   - `n_knots = 20` — достаточно для `searchsorted` в `_pressure_fd_step`.
     Для гладкой корреляции Standing узлы не имеют изломов, поэтому выбор направления
     FD-шага будет всегда `+h` (правильно для гладкой функции).
   - `bo_sat`, `mu_sat` — вычисляются, но не используются `RadialBlackOilModel`.
     Заполняются для полноты интерфейса. Если потребуются (например, в диагностике) —
     уже готовы.
   - Класс **не наследует** `BlackOilPVT` (у того нет ABC). Это duck-typing:
     `RadialBlackOilModel` обращается к методам и атрибутам, не проверяя `isinstance`.

**Проверка после шага:**
- Юнит-тесты адаптера (шаг 2)

**Зависимости:** нет
**Оценка:** ~60 строк, ~15 минут


### Шаг 2: Тесты адаптера

**Цель:** проверить, что `HydroPVTtoBlackOilAdapter(StandingFullPVT)` даёт те же
значения, что прямой вызов Standing с пересчётом единиц.

**Файлы:**
- Создать: `numerical_solver/tests/test_hydro_to_blackoil_adapter.py`

**Что сделать:**

```python
"""Тесты HydroPVTtoBlackOilAdapter — пересчёт единиц HydroPVT → BlackOilPVT."""

import numpy as np
import pytest
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.hydro_to_blackoil_adapter import HydroPVTtoBlackOilAdapter
from gpn_multiphase_solver.units import BAR_TO_PA, CP_TO_PA_S


@pytest.fixture
def standing():
    """StandingFullPVT с типичными параметрами."""
    return StandingFullPVT(
        rho_o_std=850.0, rho_g_std=0.85, T0=350.0, Rs0=50.0,
        co_undersaturated=0.0, c_p_oil=2000.0, c_p_gas=1000.0)


@pytest.fixture
def adapter(standing):
    """Адаптер Standing → BlackOilPVT, p_max = 200 бар."""
    return HydroPVTtoBlackOilAdapter(standing, p_max_pa=200 * BAR_TO_PA)
```

Тесты:

1. **`test_rs_sat_matches_standing`** — `adapter.rs_sat(p_bar)` ==
   `standing.Rs_eq(p_bar * BAR_TO_PA)`. Проверить на массиве p = [50, 100, 150, 200] бар.

2. **`test_bo_matches_standing`** — `adapter.bo(p_bar, rs)` ==
   `standing.Bo(p_bar * BAR_TO_PA, rs)`. Проверить на нескольких (p, rs).

3. **`test_mu_o_matches_standing`** — `adapter.mu_o(p_bar, rs) * CP_TO_PA_S` ==
   `standing.mu_o(p_bar * BAR_TO_PA, rs)`. Единицы: адаптер возвращает сП.

4. **`test_bg_matches_standing`** — аналогично.

5. **`test_mu_g_matches_standing`** — аналогично.

6. **`test_pb_of_rs_matches_standing`** — `adapter.pb_of_rs(rs) * BAR_TO_PA` ==
   `standing.pb(rs)`.

7. **`test_max_rs`** — `adapter.max_rs` == `standing.Rs_eq(p_max)`.

8. **`test_rs_values_monotonic`** — `adapter.rs_values` строго возрастает.

9. **`test_pb_monotonic`** — `adapter.pb` строго возрастает (для Standing).

10. **`test_attributes_shapes`** — `rs_values`, `pb`, `bo_sat`, `mu_sat` — массивы
    длины `n_knots`.

Tolerance: `rtol=1e-12` (прямое делегирование, ошибка только округление float).

**Проверка после шага:**
```
cd numerical_solver
.venv/Scripts/python -m pytest tests/test_hydro_to_blackoil_adapter.py -v
```

**Зависимости:** Требует: шаг 1.
**Оценка:** ~100 строк, ~20 минут


### Шаг 3: Рефакторинг Factory — обобщённая функция `_create_prototype_hydro`

**Цель:** Factory создаёт `PrototypeHydroAdapter` для **любого** `pvt.model`, не только `"table"`.

**Файлы:**
- Изменить: `numerical_solver/gpn_multiphase_solver/factory.py`

**Контекст:**

Сейчас `_create_prototype_hydro` (factory.py:154) предполагает, что PVT уже создан
как `TableFullPVT`, и извлекает `proto_pvt = pvt._hydro._pvt` (BlackOilPVT).
Это работает только для табличного пути.

Для Standing-пути нужно:
1. Из нашего `HydroPVT` (StandingFullPVT или PrototypePVTAdapter) создать
   `HydroPVTtoBlackOilAdapter`
2. Передать его в `RadialBlackOilModel` как `pvt`
3. `PrototypeHydroAdapter` получает наш `HydroPVT` (для пересчёта потоков)

**Что сделать:**

1. Добавить import:
```python
from .pvt.hydro_to_blackoil_adapter import HydroPVTtoBlackOilAdapter
```

2. Убрать развилку в `from_config`:

До:
```python
# 4. HydroSolver
if config.pvt.model == "table":
    hydro = _create_prototype_hydro(config, grid, pvt, relperm)
else:
    hydro = AnalyticalHydroSolver(grid, pvt, relperm)
```

После:
```python
# 4. HydroSolver — всегда PrototypeHydroAdapter (Newton-солвер прототипа)
hydro = _create_prototype_hydro(config, grid, pvt, relperm)
```

3. Переписать `_create_prototype_hydro` — убрать предположение о `TableFullPVT`:

До (factory.py:164–168):
```python
# proto_pvt и proto_rp — извлекаем из наших обёрток
# pvt: TableFullPVT → _hydro: PrototypePVTAdapter → _pvt: BlackOilPVT
proto_pvt = pvt._hydro._pvt
# relperm: PrototypeRPAdapter → _rp: TabulatedRelPerm
proto_rp = relperm._rp
```

После:
```python
# proto_pvt: BlackOilPVT для RadialBlackOilModel
proto_pvt = _get_or_create_proto_pvt(pvt, config.initial_conditions.p0)

# proto_rp: TabulatedRelPerm для RadialBlackOilModel
proto_rp = _get_or_create_proto_rp(relperm)
```

4. Добавить helper-функции:

```python
def _get_or_create_proto_pvt(pvt, p0: float):
    """Получить BlackOilPVT для RadialBlackOilModel.

    Если pvt содержит BlackOilPVT (табличный путь) — извлечь его.
    Иначе — обернуть HydroPVT через HydroPVTtoBlackOilAdapter.
    """
    # Табличный путь: TableFullPVT → PrototypePVTAdapter → BlackOilPVT
    if hasattr(pvt, '_hydro') and hasattr(pvt._hydro, '_pvt'):
        return pvt._hydro._pvt

    # Аналитический путь (Standing и др.): обернуть HydroPVT
    # pvt — FullPVT, который является HydroPVT
    hydro_pvt = pvt  # StandingFullPVT является HydroPVT
    return HydroPVTtoBlackOilAdapter(hydro_pvt, p_max_pa=p0)


def _get_or_create_proto_rp(relperm):
    """Получить TabulatedRelPerm для RadialBlackOilModel.

    Если relperm — PrototypeRPAdapter, извлечь TabulatedRelPerm.
    Если CoreyRP — обернуть через протабулирование.
    """
    if hasattr(relperm, '_rp'):
        return relperm._rp

    # CoreyRP → TabulatedRelPerm: протабулировать на сетке Sg (vectorized)
    from radial_blackoil.relperm import TabulatedRelPerm
    Sg = np.linspace(0.0, 1.0, 101)
    kro = relperm.kro(Sg)
    krg = relperm.krg(Sg)
    return TabulatedRelPerm(Sg, kro, krg)
```

5. Теперь `our_pvt` для `PrototypeHydroAdapter` — нужно подать `HydroPVT`.
   Для Standing-пути: `pvt` сам является `HydroPVT` (через наследование `FullPVT(HydroPVT)`).
   Для табличного пути: `pvt._hydro` — `PrototypePVTAdapter` (тоже `HydroPVT`).

   Изменить последнюю строку `_create_prototype_hydro`:

   До:
   ```python
   return PrototypeHydroAdapter(model, grid, pvt._hydro)
   ```

   После:
   ```python
   # our_pvt: HydroPVT для PrototypeHydroAdapter (пересчёт потоков)
   our_pvt = pvt._hydro if hasattr(pvt, '_hydro') else pvt
   return PrototypeHydroAdapter(model, grid, our_pvt)
   ```

6. Убрать неиспользуемый import `AnalyticalHydroSolver` из factory.py.

**Проверка после шага:**
```
cd numerical_solver
.venv/Scripts/python -m pytest tests/ -v
```

**Подводные камни:**
- `hasattr` проверки — duck-typing. Это осознанный выбор: мы не хотим вводить
  промежуточные ABC для различения «табличного» и «аналитического» пути.
- CoreyRP → TabulatedRelPerm: табуляция на 101 точке Sg ∈ [0,1]. Для Corey
  (степенные функции) это достаточная точность для `np.interp`.
- Ленивые imports `from radial_blackoil.*` теперь вызываются **всегда**, а не только
  для `pvt.model="table"`. Шаг 0 (conftest.py) обеспечивает sys.path для тестов.
  В production (если пользователь запускает из своего кода) — нужен либо `pip install`,
  либо `sys.path` с путём к прототипу.

**Зависимости:** Требует: шаг 0, шаг 1.
**Оценка:** ~60 строк изменений, ~25 минут


### Шаг 4: Тесты Factory с Standing → PrototypeHydroAdapter

**Цель:** проверить, что Factory с `pvt.model="standing"` создаёт `PrototypeHydroAdapter`
и pipeline работает.

**Файлы:**
- Изменить: `numerical_solver/tests/test_factory_prototype.py` (добавить тесты)
- или создать: `numerical_solver/tests/test_factory_standing_hydro.py`

**Что сделать:**

1. **`test_standing_creates_prototype_hydro`** — `SimulatorFactory.from_config(baseline.json)`
   создаёт `simulator._hydro` типа `PrototypeHydroAdapter`.

2. **`test_standing_pipeline_runs`** — baseline.json → Factory → run → history.
   Проверки: `history.n_saved > 1`, финальное давление < начального.

3. **`test_standing_dupuit_pressure`** — однофазный Standing (Rs0 > Rs_eq(p_wf),
   то есть при p_wf нет разгазирования): профиль давления ≈ log-профиль с rtol=1e-3
   (численное решение Newton-солвера, не аналитика).

4. **`test_standing_well_rate_positive`** — дебит > 0.

5. **`test_corey_to_tabulated_rp`** — проверить, что CoreyRP → TabulatedRelPerm
   даёт те же значения: `relperm.kro(Sg)` ≈ `proto_rp.kro(Sg)` с rtol=1e-6.

**Проверка после шага:**
```
cd numerical_solver
.venv/Scripts/python -m pytest tests/test_factory_standing_hydro.py -v
.venv/Scripts/python -m pytest tests/ -v
```

**Зависимости:** Требует: шаг 0, шаг 3.
**Оценка:** ~120 строк, ~30 минут


### Шаг 5: Адаптация VAL-001 pipeline-тестов

**Цель:** VAL-001 pipeline-тесты (через Factory) работают с Newton-солвером.

**Файлы:**
- Изменить: `numerical_solver/tests/test_val001.py`

**Контекст:**

`_run_val001()` → `SimulatorFactory.from_config(val001.json)` → раньше создавало
`AnalyticalHydroSolver`. После шага 3 — `PrototypeHydroAdapter`.

Затронутые тесты (через `_run_val001()`):
- `test_rate_matches_dupuit` (rtol → ослабить)
- `test_pressure_log_profile` (rtol=1e-12 → ослабить)
- `test_G_o_constant` (rtol=1e-12 → ослабить)
- `test_u_r_constant` (аналогично)
- `test_pipeline_roundtrip` (формат — не затронут, но проверка `n_saved` может измениться)

**НЕ затронуты** (конструируют `AnalyticalHydroSolver` напрямую):
- `TestTemperature::test_temperature_converges`

**Что сделать:**

1. Ослабить tolerance в тестах, использующих `_run_val001()`.
   Рекомендация: rtol=1e-6 (не 1e-3), т.к. однофазный стационар с mob_o=const →
   Newton даёт решение с точностью rtol_Newton ≈ 1e-8. При реализации: сначала
   запустить тест без изменения tolerance, посмотреть фактическую ошибку, выбрать
   tolerance с запасом ×10.
   Затронутые тесты:
   - `test_rate_matches_dupuit` (строка 76, rtol=1e-10)
   - `test_pressure_log_profile` (строка 93, rtol=1e-12)
   - `test_G_o_constant` (строка 110, rtol=1e-12)
   - `test_u_r_constant` (строка 120, rtol=1e-10)
   - `test_oil_mass_balance` (строка 138, atol=1e-12)
   - `test_gor_equals_rs0` (строка 150, rel=1e-12)

2. Обновить комментарии: убрать ссылки на `AnalyticalHydroSolver` в тестах pipeline,
   заменить на `PrototypeHydroAdapter (Newton-солвер)`.

3. Проверить `test_pipeline_roundtrip`: количество сохранённых шагов может отличаться
   (Newton может требовать другой dt). Если тест падает — подстроить ожидание.

**Проверка после шага:**
```
cd numerical_solver
.venv/Scripts/python -m pytest tests/test_val001.py -v
.venv/Scripts/python -m pytest tests/ -v
```

**Подводные камни:**
- Однофазный стационар с `co_undersaturated=0` (val001.json) → Bo, μ_o не зависят
  от p при Rs=const → mob_o = const → задача Дюпюи точная → Newton сходится за 1 итерацию.
  Фактическая ошибка будет порядка rtol_Newton (1e-8), не 1e-3.
  **Рекомендация:** ослаблять до rtol=1e-6 (не 1e-3), чтобы тест оставался информативным.
  При реализации: сначала запустить тест, посмотреть фактическую ошибку, выбрать tolerance
  с запасом ×10.

**Зависимости:** Требует: шаг 0, шаг 3.
**Оценка:** ~20 строк изменений, ~15 минут


### Шаг 6: Обновить `pvt/__init__.py` и vault

**Цель:** экспортировать адаптер, обновить документацию.

**Файлы:**
- Изменить: `numerical_solver/gpn_multiphase_solver/pvt/__init__.py`
- Обновить: `vault/roadmap/планируемые фичи.md` (статус FEAT-014)

**Что сделать:**

1. В `pvt/__init__.py` добавить:
```python
from .hydro_to_blackoil_adapter import HydroPVTtoBlackOilAdapter
```

2. В `vault/roadmap/планируемые фичи.md`:
   - Статус: `✅ ГОТОВО (дата)`
   - Ветка: `feat/feat-014/hydro-to-blackoil-adapter`
   - План: `[[feat-014-hydro-to-blackoil-adapter]]`

**Проверка после шага:**
```
cd numerical_solver
.venv/Scripts/python -m pytest tests/ -v
```

**Зависимости:** Требует: шаг 5.
**Оценка:** ~5 строк, ~5 минут


## Тестовая стратегия

| Категория | Что проверяем | Файл |
|---|---|---|
| Инфраструктура | sys.path для radial_blackoil | `conftest.py` |
| Unit | Адаптер: пересчёт единиц | `test_hydro_to_blackoil_adapter.py` |
| Unit | CoreyRP → TabulatedRelPerm | `test_factory_standing_hydro.py` |
| Integration | Factory + Standing → PrototypeHydroAdapter → run | `test_factory_standing_hydro.py` |
| Регрессия | VAL-001 pipeline с Newton | `test_val001.py` |
| Регрессия | Все существующие тесты | `pytest tests/ -v` |

## Критерии завершения

- [ ] `conftest.py` содержит централизованный sys.path для radial_blackoil
- [ ] `HydroPVTtoBlackOilAdapter` реализован и протестирован
- [ ] Factory создаёт `PrototypeHydroAdapter` для `pvt.model="standing"`
- [ ] baseline.json проходит pipeline (Factory → run → history)
- [ ] val001.json проходит pipeline с ослабленным tolerance
- [ ] Все существующие тесты зелёные
- [ ] `pvt/__init__.py` обновлён
- [ ] Vault обновлён


## Новые задачи (зафиксировать после реализации)

1. **DEBT-NNN: Удалить AnalyticalHydroSolver** — после FEAT-014 он больше не нужен
   в production-коде (Factory его не использует). Остаётся только в тестах. Перевести
   тесты на `PrototypeHydroAdapter` и удалить заглушку. Обновить `hydro/base.py` docstring.

2. **DEBT-NNN: Убрать `hasattr` duck-typing в Factory** — ввести метод
   `get_proto_pvt()` или property в ABC, чтобы не полагаться на `hasattr(pvt, '_hydro')`.


## Оценка

- Файлов: 2 новых, 4 изменённых
- Строк: ~370
- Время: ~2 часа
- Шагов: 7 (0–6)
