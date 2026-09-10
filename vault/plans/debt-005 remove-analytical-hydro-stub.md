---
tags:
  - план
  - удаление
date: 2026-09-10
issue: DEBT-005
github: 28
branch: refactor/debt-005/remove-analytical-hydro-stub
status: в процессе
audit:
  date: 2026-09-10
  round: 4
  found: 1
  auto-fixed: 1
  manual-required: 0
---

# DEBT-005: удалить AnalyticalHydroSolver из production-пакета

**GitHub issue:** [#28](https://github.com/ArturSalamatin/Oil_Gas/issues/28)
**Ветка:** `refactor/debt-005/remove-analytical-hydro-stub` (база: `numerical_scheme/implementation`)
**Подтип:** удаление мёртвого кода (с оговоркой — см. §2.3, код не мёртвый в тестах)
**Рабочий каталог:** `numerical_solver/`

---

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай связанные vault-заметки (§9).
3. Создай ветку от базовой:
   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   git checkout numerical_scheme/implementation
   git checkout -b refactor/debt-005/remove-analytical-hydro-stub
   ```
   ⚠️ Не ветвись от `master` — там нет каталога `numerical_solver/`.
4. Прогони baseline:
   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver
   .venv\Scripts\python -m pytest tests/ -q
   ```
5. Ожидаемый baseline: **812 passed, 1 warning, ~135 с** (замерено 2026-09-10 на `52e4588`).
   Если число другое — **остановись** и выясни причину до начала работы.
6. Начни с шага 1. После каждого шага — pytest.

---

## 1. Задача

### 1.1. Что не так

`AnalyticalHydroSolver` (`numerical_solver/gpn_multiphase_solver/hydro/analytical.py`) — заглушка. Она не решает уравнение фильтрации, а подставляет заранее известный стационарный логарифмический профиль:

$$p(r) = p_{wf} + (p_{ext} - p_{wf})\,\frac{\ln(r/r_w)}{\ln(R/r_w)}$$

с жёстко зашитыми $S_g = 0$, $R_s = R_{s,ext}$, `regime = 2`. Результат не зависит ни от `dt`, ни от входного `state.p` — это записано в её собственном docstring (`analytical.py:38-40`) и закреплено тестом `test_pressure_independent_of_input` (`test_hydro.py:120`).

После FEAT-014 `SimulatorFactory` всегда создаёт `PrototypeHydroAdapter`. В production-пути заглушка не вызывается **ни разу**.

### 1.2. Почему это долг

Класс наследует ABC `HydroSolver` и лежит в production-пакете. Значит, его можно подставить в `Simulator` одной строкой — расчёт пройдёт без ошибок и выдаст правдоподобный, но физически бессмысленный результат: без разгазирования, без сжимаемости, без зависимости от времени.

Угроза не гипотетическая: сигнатура совпадает с настоящим решателем полностью.

### 1.3. Что НЕ является целью

- Не менять `compute_fluxes()` — заглушка вызывает его штатно (`analytical.py:64`), логика потоков едина и корректна.
- Не менять `PrototypeHydroAdapter`, `TridiagEnergySolver`, `Simulator` (кроме одной строки docstring).
- Не менять численные результаты ни одного теста.

---

## 2. Анализ

### 2.1. Baseline

| Параметр | Значение |
|---|---|
| Коммит | `52e4588` |
| Тесты | **812 passed**, 1 warning |
| Время | ~135 с |
| Дата замера | 2026-09-10 |

✅ **План прогнан целиком (аудит 2026-09-10).** Шаги 1–6 применены к копии дерева в scratchpad (проект не затрагивался). Результат:

| Проверка | Результат |
|---|---|
| Полный набор после рефакторинга | **812 passed** / 140 с — ни одного потерянного теста |
| `test_hydro.py` | 16 passed |
| `test_simulator.py` | 21 passed |
| `test_output.py` | 26 passed |
| `test_val001.py` | 9 passed |
| `test_G_o_concrete_number` (якорь) | прошёл без изменения числа |
| `test_pressure_is_analytical_log_profile` | прошёл (`rtol=1e-12`) |
| Импорт из пакета после удаления | `ModuleNotFoundError` — цель достигнута |
| Обратная зависимость пакет → tests | отсутствует |

То есть план исполним ровно как написан; числа ниже — измеренные, не оценочные.

**Раунд 2 (2026-09-10) — повторный прогон исправленного плана.** Применены относительная форма импорта, переименование шага 5.3 и обе правки docstring шага 6. Результат: **812 passed** / 142 с; `hydro/base.py` и `simulator.py` после правок читаются корректно (кодировка UTF-8 цела); `AnalyticalHydroSolver` в пакете отсутствует полностью.

⚠️ В записи реестра до правки стояло **595**, в DEBT-007 — **772**. Оба числа устарели; ориентир — 812.

### 2.2. Полный scope (grep подтверждён, case-insensitive)

**Production (2 упоминания, оба — docstring):**

| Файл | Строка | Что |
|---|---|---|
| `numerical_solver/gpn_multiphase_solver/hydro/analytical.py` | 1–69 | сам класс |
| `numerical_solver/gpn_multiphase_solver/hydro/base.py` | 18 | перечень реализаций в docstring ABC |
| `numerical_solver/gpn_multiphase_solver/simulator.py` | 100 | перечень в docstring |

**Тесты (4 файла):**

| Файл | Строки | Характер использования |
|---|---|---|
| `numerical_solver/tests/test_hydro.py` | 1–13, 24, 66 | весь файл тестирует именно этот класс (16 тестов) |
| `numerical_solver/tests/test_simulator.py` | 4, 22, 52, 59, 250, 266, 324, 331 | `_make_simulator`, `TestPhysics` (21 тест в файле) |
| `numerical_solver/tests/test_output.py` | 29, 59 | фикстура `small_history` (26 тестов в файле) |
| `numerical_solver/tests/test_val001.py` | 27, 174 | `TestTemperature::test_temperature_converges` (9 тестов в файле) |

**Важно — scope закрыт:**
- `gpn_multiphase_solver/hydro/__init__.py` — **пустой файл**. Класс никогда не реэкспортировался на уровне пакета, значит внешних импортов вида `from gpn_multiphase_solver.hydro import AnalyticalHydroSolver` быть не может.
- `gpn_multiphase_solver/__init__.py` — упоминаний нет (grep пустой).
- В `examples/` и `configs/` упоминаний нет — Factory создаёт солвер по строке `"prototype"`, имени класса в JSON нет.
- Совпадения `analytical` в `test_fluxes.py:203`, `test_val002.py:344`, `test_examples.py:808` — **не связаны** с этим классом (речь про аналитические эталоны и аналитический PVT). Не трогать.

### 2.3. Ключевая находка: код не мёртвый

Формально подтип задачи — «удаление мёртвого кода», но это неточно. Тесты используют заглушку **не за неимением альтернативы, а ради её главного свойства — детерминированности**. Это несущий элемент их конструкции:

1. **`test_simulator.py::test_pressure_is_analytical_log_profile`** (стр. 321–341) сверяет `history.states[-1].p` с аналитической формулой при `rtol=1e-12`. С Newton-солвером сверять не с чем — тест исчезает целиком.

2. **`test_simulator.py::TestPhysics`** глушит тепловые эффекты по одному и опирается на то, что после первого шага $dp/dt = 0 \Rightarrow Q_{ad} = 0$ (комментарий на стр. 250–252). С настоящим солвером давление релаксирует, адиабатический источник не занулится — изоляция эффектов разрушается.

3. **`test_val001.py::test_temperature_converges`** и **`test_output.py::small_history`** — нужен дешёвый воспроизводимый прогон, а не физика гидродинамики.

4. **`test_hydro.py`** — 16 тестов, проверяющих ровно четыре действия заглушки.

Плюс `PrototypeHydroAdapter` дороже: Newton + возможные A-retry подшаги, а `test_output.py` гоняет фикстуру на 26 тестах.

**Вывод:** формулировка из реестра «перевести тесты на `PrototypeHydroAdapter`» невыполнима без потери проверочной способности.

### 2.4. Варианты

#### Вариант 1. Перевести тесты на `PrototypeHydroAdapter`, файл удалить

- **Суть:** заменить конструктор в четырёх файлах.
- **Минусы:** разрушает `test_pressure_is_analytical_log_profile` и изоляцию эффектов в `TestPhysics` (см. §2.3). `test_hydro.py` теряет предмет целиком. Время прогона растёт.
- **Риск:** высокий — молчаливая потеря покрытия.
- **Отклонён.**

#### Вариант 2. Оставить, добавить предупреждение в docstring

- **Плюсы:** ноль работы.
- **Минусы:** не устраняет угрозу — класс по-прежнему экспортируется и подставляется одной строкой. Docstring не защищает.
- **Отклонён.**

#### Вариант 3 (выбран). Перенести в тестовую оснастку

- **Суть:** класс не удаляется по смыслу, а **переезжает из production-пакета в `tests/`** под именем `LogProfileHydroStub`.
- **Изменения:** новый `numerical_solver/tests/_doubles.py`; импорты в 4 тестовых файлах; удаление `hydro/analytical.py`; чистка 2 docstring.
- **Промежуточные состояния:** да — каждый шаг оставляет тесты зелёными (см. §3).
- **Плюсы:**
  - цель DEBT-005 достигнута: из `gpn_multiphase_solver` уходит объект, который можно принять за решатель; импортировать его оттуда больше нельзя (проверено на прогоне — `ModuleNotFoundError`);
  - ни один тест не теряет проверочную способность;
  - время прогона не растёт;
  - имя `LogProfileHydroStub` содержит `Stub` — само по себе предупреждение.
- **Минусы:** 69 строк продолжают существовать, просто в `tests/`. Осознанный размен: тестовый двойник в `tests/` — нормальная практика, заглушка в production-пакете — нет.
- **Трудоёмкость:** 5 файлов, ~90 строк изменений, ~40 минут.

⚠️ **Насколько высок барьер (уточнено аудитом 2026-09-10, проверено прогоном).**
Барьер **не абсолютный**. Скрипт, запущенный из `numerical_solver/` (как `examples/*/main.py`), по-прежнему может сделать `from tests._doubles import LogProfileHydroStub` — `tests/` является пакетом (`__init__.py` на месте), и рабочий каталог попадает в `sys.path`.

Что именно даёт перенос:
- заглушка исчезает из пространства имён `gpn_multiphase_solver.*` — случайный импорт «по соседству» с `PrototypeHydroAdapter` невозможен (проверено: `ModuleNotFoundError`);
- имя `LogProfileHydroStub` содержит `Stub`, а модуль `_doubles` — подчёркивание: обе метки кричат «не для production»;
- импорт из `tests.*` в production-скрипте выглядит явной аномалией при code review.

То есть это **защита от случайности, а не технический запрет**. Формулировать в отчётах как «нельзя подставить» — неверно; корректно: «нельзя подставить незаметно».

### 2.5. Критерий выбора

- **Минимальность diff:** вариант 3 ≈ вариант 1 по объёму, но без переписывания логики тестов.
- **Инкрементальность:** вариант 3 разбивается на 7 шагов, каждый зелёный.
- **Обратная совместимость:** внешний API не ломается — класс не был в `__init__.py`.
- **Тестируемость:** не ухудшается.

### 2.6. Подводные камни

| Проверка | Статус |
|---|---|
| Все call sites найдены | ✅ grep case-insensitive по всему `numerical_solver/`; 2 production-docstring + 4 тестовых файла |
| Реэкспорт в `__init__.py` | ✅ `hydro/__init__.py` пуст, `gpn_multiphase_solver/__init__.py` не упоминает |
| Зависимости пакетов | ✅ `pyproject.toml` не затрагивается |
| Обратная совместимость API | ✅ класс не входил в публичный экспорт |
| Circular imports | ⚠️ `tests/_doubles.py` импортирует из `gpn_multiphase_solver` — направление «тесты → пакет», цикла не создаёт. Обратного импорта быть не должно |
| Configs | ✅ имя класса в JSON не фигурирует |
| Docstrings / `\eqref{}` | ✅ формула лог-профиля переносится вместе с классом |
| Конфликт с другими задачами | ⚠️ см. §2.7 |
| Производительность | ✅ логика не меняется, время прогона то же |
| Ложные grep-совпадения | ✅ `test_fluxes.py:203`, `test_val002.py:344`, `test_examples.py:808` — другое значение слова «analytical», не трогать |

### 2.7. Связь с другими задачами

- **FEAT-014** — причина появления долга (после неё Factory перестала использовать заглушку). Завершена, конфликта нет.
- **DEBT-013** — уже затронула `test_simulator.py` (`_make_simulator` возвращает пятым элементом `None` — рудимент `save_every`, комментарий на стр. 62–64). **Не трогать этот рудимент** в рамках DEBT-005: он к задаче не относится, а распаковку принимают два десятка тестов.
- **BUG-004** — ✅ ИСПРАВЛЕНО (2026-09-08), ветка `fix/bug-004/energy-balance-table-pvt` слита в базу, расхождений по файлам с базой нет (проверено `git diff --name-only` — пусто). Конфликта нет.
- **BUG-006** — 🔴 открыт, план `vault/plans/bug-006 ode-front-discretization.md` не упоминает `test_val001.py` ни разу (проверено grep). Пересечения нет.
- Правка в `test_val001.py` здесь — замена имени класса в двух строках, по смыслу с обоими багами не пересекается.

### 2.8. Обнаруженные проблемы

**Новых задач для реестра не выявлено.** Зафиксированы две неточности в существующих записях — обе уже исправлены при `/issue` (2026-09-10):
1. `simulator.py:100` отсутствовал в поле «Файл» записи DEBT-005 — добавлен.
2. Baseline 595/772 устарел — заменён на 812 с датой замера.

---

## 3. Шаги реализации

### Шаг 1: Создать тестовый двойник `tests/_doubles.py`

**Цель:** перенести логику заглушки в тестовую оснастку, не удаляя пока оригинал.

**Файлы:** `numerical_solver/tests/_doubles.py` (новый)

**Контекст:**
Класс переносится **без изменения логики** — побайтово та же арифметика. Меняются только имя (`AnalyticalHydroSolver` → `LogProfileHydroStub`), пути импортов (`..state` → `gpn_multiphase_solver.state`, так как файл теперь вне пакета) и docstring (акцент на «это тестовый двойник, а не решатель»).

Имя `_doubles.py` выбрано как маркер служебного модуля. ⚠️ **Уточнение (аудит, раунд 2):** от сбора pytest-ом защищает не подчёркивание, а отсутствие префикса `test_`. В `pyproject.toml` параметр `python_files` не задан, значит действует дефолт pytest — `test_*.py` и `*_test.py`. Проверено прогоном: файл `tests/_probe_collect.py` с заведомо падающим `test_`-методом **не был собран** (812 passed, без изменений). Подчёркивание — соглашение о приватности, не механизм.

**Форма импорта задаётся здесь и действует во всех шагах 2–5:** внутри тестовых модулей — только относительная `from ._doubles import LogProfileHydroStub`. Обоснование и таблица проверенных форм — в шаге 2.

**Что сделать:**

1. Создать `numerical_solver/tests/_doubles.py` со следующим содержимым:

```python
"""Тестовые двойники для gpn_multiphase_solver.

LogProfileHydroStub — НЕ решатель. Подставляет заранее известный
стационарный логарифмический профиль давления вместо решения уравнения
фильтрации. Существует только ради детерминированности: тесты энергии,
Simulator и вывода нуждаются в точно известном p(r), чтобы изолировать
проверяемый эффект от гидродинамики.

Жил в gpn_multiphase_solver/hydro/analytical.py до DEBT-005. Вынесен в
tests/, чтобы его нельзя было по ошибке подставить в production-расчёт
(сигнатура совпадает с настоящим PrototypeHydroAdapter).
"""

import numpy as np

from gpn_multiphase_solver.hydro.base import HydroSolver
from gpn_multiphase_solver.state import (
    SimulationState, HydroResult, BoundaryConditions)
from gpn_multiphase_solver.grid.base import Grid
from gpn_multiphase_solver.pvt.base import HydroPVT, RelPermModel
from gpn_multiphase_solver.fluxes import compute_fluxes


class LogProfileHydroStub(HydroSolver):
    """Стационарный логарифмический профиль давления (однофазный).

    Тестовый двойник, не решатель. См. модульный docstring.
    """

    def __init__(self, grid: Grid, pvt: HydroPVT, relperm: RelPermModel):
        self._grid = grid
        self._pvt = pvt
        self._relperm = relperm

    def solve(self, state: SimulationState, dt: float,
              bc: BoundaryConditions) -> HydroResult:
        """Построить стационарный профиль и вычислить потоки.

        Результат не зависит от dt и от входного state.p —
        давление вычисляется аналитически из p_wf и p_ext.
        dt влияет только на state.t.
        """
        grid = self._grid
        N = grid.N

        # Забойное давление из стратегии управления
        p_wf = bc.well.boundary_pressure(state, grid, self._pvt, self._relperm)

        # Логарифмический профиль давления (точное решение стационарного
        # уравнения фильтрации при постоянных свойствах)
        log_ratio = np.log(grid.r_centers / grid.r_well) / np.log(grid.R_ext / grid.r_well)
        p = p_wf + (bc.p_ext - p_wf) * log_ratio

        # Однофазное состояние: Sg=0, Rs=Rs_ext, regime=2
        new_state = SimulationState(
            p=p,
            Sg=np.zeros(N),
            Rs=np.full(N, bc.Rs_ext),
            T=state.T.copy(),                     # гидро не трогает T
            regime=np.full(N, 2, dtype=int),
            t=state.t + dt,
        )

        # Потоки — через compute_fluxes (единая логика upstream, знаков, формул)
        result = compute_fluxes(new_state, grid, self._pvt, self._relperm, bc)

        # compute_fluxes возвращает HydroResult с state=new_state (без изменений),
        # что и нужно: state содержит обновлённые p, Sg, Rs, T, t.
        return result
```

**Проверка после этого шага:**
```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver
.venv\Scripts\python -m pytest tests/ -q
```
Ожидание: **812 passed** — ничего не изменилось, файл пока никем не импортируется.

Дополнительно — проверить, что новый модуль импортируется:
```powershell
.venv\Scripts\python -c "from tests._doubles import LogProfileHydroStub; print(LogProfileHydroStub)"
```
⚠️ Эта команда запускается из `numerical_solver/` **вне pytest**, поэтому здесь работает `tests._doubles` (обычный пакет от рабочего каталога). Внутри тестовых модулей — только относительная форма `from ._doubles import ...`.

**Подводные камни:**
- Импорты абсолютные (`gpn_multiphase_solver.*`), не относительные — файл вне пакета.
- Не переименовывать `solve`, не менять сигнатуру — иначе ABC не удовлетворён.

**Зависимости:** требует — нет. Блокирует — шаги 2, 3, 4, **5** (все четыре тестовых файла импортируют двойник) и, транзитивно, шаг 6.

**Оценка:** ~70 строк, ~10 минут.

---

### Шаг 2: Переключить `test_output.py`

**Цель:** самый дешёвый переключатель — один вызов в одной фикстуре.

**Файлы:** `numerical_solver/tests/test_output.py`

**Что сделать:**

1. Строка 29 — заменить импорт:

До:
```python
from gpn_multiphase_solver.hydro.analytical import AnalyticalHydroSolver
```
После:
```python
from ._doubles import LogProfileHydroStub
```

2. Строка 59 (внутри фикстуры `small_history`):

До:
```python
    hydro = AnalyticalHydroSolver(grid, pvt, rp)
```
После:
```python
    hydro = LogProfileHydroStub(grid, pvt, rp)
```

**Проверка:**
```powershell
.venv\Scripts\python -m pytest tests/test_output.py -q
```
Ожидание: **26 passed**. Затем полный прогон — 812 passed.

**Подводные камни:**
- ✅ **Форма импорта проверена эмпирически (2026-09-10), гадать не нужно.** В `numerical_solver/tests/` есть `__init__.py`, то есть `tests/` — настоящий пакет. Проверены три формы:

  | Форма | Результат |
  |---|---|
  | `from _doubles import ...` | ❌ `ModuleNotFoundError: No module named '_doubles'` |
  | `from tests._doubles import ...` | ❌ `ModuleNotFoundError: No module named 'tests._doubles'` |
  | `from ._doubles import ...` | ✅ работает (одиночный файл и полный прогон) |

  **Использовать относительную форму `from ._doubles import LogProfileHydroStub`** во всех четырёх тестовых файлах (шаги 2–5). Ни один существующий тест не импортирует другой тестовый модуль, поэтому образца в коде нет — отсюда и проверка.

**Зависимости:** требует — шаг 1.

**Оценка:** 2 строки, ~5 минут.

---

### Шаг 3: Переключить `test_val001.py`

**Цель:** один вызов в одном тесте.

**Файлы:** `numerical_solver/tests/test_val001.py`

**Что сделать:**

1. Строка 27 — заменить импорт (по образцу шага 2).
2. Строка 174:

До:
```python
        hydro = AnalyticalHydroSolver(grid, pvt, rp)
```
После:
```python
        hydro = LogProfileHydroStub(grid, pvt, rp)
```

**Проверка:**
```powershell
.venv\Scripts\python -m pytest tests/test_val001.py -q
```
Ожидание: **9 passed**, в том числе `TestTemperature::test_temperature_converges`.

**Подводные камни:**
- Тест проверяет $\max|T - 350| < 1$ К. Число не должно измениться ни на бит — логика двойника идентична оригиналу.

**Зависимости:** требует — шаг 1.

**Оценка:** 2 строки, ~5 минут.

---

### Шаг 4: Переключить `test_simulator.py`

**Цель:** переключить `_make_simulator` и два прямых вызова в `TestPhysics`.

**Файлы:** `numerical_solver/tests/test_simulator.py`

**Что сделать:**

1. Строка 22 — заменить импорт.
2. Строка 59 (в `_make_simulator`) и строка 266 (в `test_T_converges_to_T_ext_without_JT`) — заменить конструктор на `LogProfileHydroStub(grid, pvt, rp)`.
3. Обновить упоминания в docstring — **не косметика, а суть**: они объясняют, почему эффект изолирован.
   - Строка 4 (модульный docstring): `Используют AnalyticalHydroSolver + TridiagEnergySolver` → `Используют LogProfileHydroStub + TridiagEnergySolver (реальный энергетический солвер, гидродинамика — двойник)`.
   - Строка 52: `"""Создать Simulator с AnalyticalHydroSolver (без Factory)."""` → `"""Создать Simulator с LogProfileHydroStub (без Factory)."""`
   - Строка 250: `Адиабатический: AnalyticalHydroSolver даёт стационарный p(r)` → `... LogProfileHydroStub даёт стационарный p(r)`.
   - Строки 324, 331 (в `test_pressure_is_analytical_log_profile`) — аналогично.

**Проверка:**
```powershell
.venv\Scripts\python -m pytest tests/test_simulator.py -q
```
Ожидание: **21 passed**, в том числе `test_pressure_is_analytical_log_profile` (сверка с формулой при `rtol=1e-12`) и все три теста `TestPhysics`.

**Подводные камни:**
- ⚠️ **Не трогать** пятый элемент возврата `_make_simulator` (`None`, рудимент `save_every` из DEBT-013, комментарий стр. 62–64). Он к DEBT-005 не относится.
- Название теста `test_pressure_is_analytical_log_profile` **оставить как есть** — слово «analytical» здесь описывает профиль (аналитическая формула), а не класс.

**Зависимости:** требует — шаг 1.

**Оценка:** ~8 строк, ~10 минут.

---

### Шаг 5: Переключить и переформулировать `test_hydro.py`

**Цель:** файл перестаёт быть тестом production-кода; переформулировать его предмет, сохранив все проверки.

**Файлы:** `numerical_solver/tests/test_hydro.py`

**Контекст:**
Это единственный содержательный шаг. Все 16 тестов **остаются** — решение принято ниже, см. «Что с 16 тестами».

**Что сделать:**

1. Строка 24 — заменить импорт на `from ._doubles import LogProfileHydroStub` (относительная форма — единственная работающая, см. таблицу в шаге 2).
2. Строка 66 (фикстура `solver`) — `return LogProfileHydroStub(grid, pvt, relperm)`.
3. Строка 104 — переименовать `test_analytical_is_hydro_solver` → `test_stub_is_hydro_solver`.
4. Переписать модульный docstring (строки 1–13):

До:
```python
"""Тесты для HydroSolver ABC и AnalyticalHydroSolver (фаза 4).

AnalyticalHydroSolver выполняет 4 действия:
  ...
```
После:
```python
"""Тесты для ABC HydroSolver и тестового двойника LogProfileHydroStub.

Предмет теста двойной:
  1. Контракт ABC HydroSolver — нельзя инстанцировать, реализация проходит
     isinstance (класс A).
  2. Сам двойник LogProfileHydroStub (tests/_doubles.py) — он используется
     как опора в test_simulator.py, test_output.py и test_val001.py, поэтому
     его собственная корректность должна быть проверена, иначе те тесты
     опираются на непроверенный фундамент.

Двойник выполняет 4 действия, и на каждое есть блок тестов:
  1. Вычисляет p_wf из bc.well.boundary_pressure()      → класс B
  2. Строит логарифмический профиль p(r)                → класс B
  3. Создаёт новый SimulationState (Sg=0, Rs=Rs_ext,
     T скопирована, t+=dt)                              → класс C
  4. Вызывает compute_fluxes() → HydroResult            → класс D

Классы E и F (сквозной дебит, повторные шаги) проверяют композицию
этих действий.

Свойства потоков (знаки, стационарность, баланс масс) покрыты в
test_fluxes.py и здесь не дублируются — test_all_fields_match_compute_fluxes
доказывает, что двойник делегирует fluxes.py, а не дублирует его логику.

До DEBT-005 двойник жил в gpn_multiphase_solver/hydro/analytical.py под
именем AnalyticalHydroSolver.
"""
```
5. Строки 158 и 194 — в docstring заменить `analytical.py` на `_doubles.py`.

**Что с 16 тестами (решение):**
В issue #28 значилось «пересмотреть, какие из 16 тестов остаются осмысленными». **Решение: оставить все 16.** Обоснование:
- двойник — фундамент для 56 тестов в трёх других файлах (26 + 21 + 9); если он сломается, те упадут с непонятной диагностикой;
- `test_all_fields_match_compute_fluxes` (стр. 190) доказывает делегирование в `fluxes.py` — это защита от дублирования логики потоков, ценна независимо от местоположения класса;
- `test_G_o_concrete_number` (стр. 227) — регрессионный якорь с конкретным числом $-0.009138144903103$;
- удаление тестов ради «чистоты» уменьшило бы покрытие, не дав ничего взамен.

Если при реализации какой-то тест окажется действительно избыточным — **зафиксировать это в отчёте с обоснованием**, а не удалять молча.

**Проверка:**
```powershell
.venv\Scripts\python -m pytest tests/test_hydro.py -v
```
Ожидание: **16 passed**, имена классов A–F без изменений (кроме переименованного `test_stub_is_hydro_solver`).

⚠️ **Переименование `test_analytical_is_hydro_solver` (стр. 104) массовой заменой не ловится.** Замена `AnalyticalHydroSolver(` → `LogProfileHydroStub(` бьёт только по вызовам конструктора (со скобкой), а имя теста содержит `analytical` в нижнем регистре и без скобок. При аудите этот шаг воспроизводился скриптом — тесты остались зелёными (16 passed), но имя сохранилось старым. Переименовать **вручную**; забытое переименование тесты не поймают.

**Подводные камни:**
- `test_G_o_concrete_number` — число не должно измениться. Если изменилось, логика при переносе была искажена: откатить шаг 1 и перенести побайтово.
- Имена тестов, содержащие «analytical» в смысле «аналитическая формула» (`test_G_o_analytical_value`, стр. 211) — **оставить**.

**Зависимости:** требует — шаг 1.

**Оценка:** ~25 строк, ~15 минут.

---

### Шаг 6: Удалить production-файл и почистить docstring

**Цель:** убрать класс из пакета — собственно цель DEBT-005.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/hydro/analytical.py` (удаление)
- `numerical_solver/gpn_multiphase_solver/hydro/base.py` (строка 18)
- `numerical_solver/gpn_multiphase_solver/simulator.py` (строка 100)

**Что сделать:**

1. Удалить файл:
   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   git rm numerical_solver/gpn_multiphase_solver/hydro/analytical.py
   ```

   ⚠️ **`cd` в корень обязателен** (аудит, раунд 3). После шага 1 читатель находится в `numerical_solver/` — последний `cd` в плане переводит именно туда. Если выполнить `git rm` с путём от корня, не сменив каталог, команда падает:
   ```
   fatal: pathspec 'numerical_solver/gpn_multiphase_solver/hydro/analytical.py' did not match any files
   ```
   (проверено). Альтернатива без `cd` — относительный путь `git rm gpn_multiphase_solver/hydro/analytical.py`.

2. `hydro/base.py`, строка 18:

До:
```python
    Конкретные реализации:
      - AnalyticalHydroSolver (заглушка, стационарный профиль)
      - PrototypeHydroAdapter (обёртка прототипа коллеги)
      - NewtonHydroSolver (собственный блочный Ньютон, будущее)
```
После:
```python
    Конкретные реализации:
      - PrototypeHydroAdapter (обёртка прототипа коллеги)
      - NewtonHydroSolver (собственный блочный Ньютон, будущее)

    Тестовый двойник LogProfileHydroStub (tests/_doubles.py) намеренно
    держится вне пакета: он подставляет готовый лог-профиль вместо решения
    уравнения фильтрации и не должен попадать в production-расчёт (DEBT-005).
```

3. `simulator.py`, строка 100:

До:
```python
        hydro         — гидродинамический солвер (ABC: AnalyticalHydroSolver, PrototypeHydroAdapter, ...)
```
После:
```python
        hydro         — гидродинамический солвер (ABC: PrototypeHydroAdapter, ...)
```

**Проверка:**
```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver
.venv\Scripts\python -m pytest tests/ -q
```
Ожидание: **812 passed** (см. §4 — если число иное, разбираться).

⚠️ Шаг 6 переключает каталог дважды: `git rm` и `git grep` требуют корня репозитория, а `pytest` и `.venv\Scripts\python` — каталога `numerical_solver/`. Каждая команда ниже снабжена своим `cd`; не опускать их (аудит, раунд 3).

Проверка чистоты пакета — **должно быть пусто**:
```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas
git grep -n "AnalyticalHydroSolver" -- numerical_solver/gpn_multiphase_solver/
```

⚠️ **Проверить и `tests/` тоже** (аудит, раунд 2 — этот пробел был найден прогоном):
```powershell
git grep -n "AnalyticalHydroSolver" -- numerical_solver/tests/
```
Ожидание: **пусто**. Старое имя остаётся в тестах только в прозе docstring-ов — шаг 4 (стр. 4, 52, 250, 324, 331 `test_simulator.py`) и шаг 5 (стр. 1, 3 `test_hydro.py`). Ни одна из этих строк не влияет на исполнение, поэтому **тесты остаются зелёными даже при полном пропуске правки** — при прогоне аудита так и вышло: 812 passed при семи оставшихся упоминаниях. Единственная защита — этот grep.

Проверка, что файла нет:
```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas
Test-Path numerical_solver\gpn_multiphase_solver\hydro\analytical.py
```
Ожидание: `False`.

🔴 **`cd` здесь критичен — без него проверка даёт ложный успех** (аудит, раунд 3). `Test-Path` с несуществующим путём возвращает `False` независимо от причины: и когда файл действительно удалён, и когда путь просто не резолвится из текущего каталога. Из `numerical_solver/` (где читатель оказывается после шага 1) эта команда возвращает `False` **при живом файле** — проверено. То есть критерий «файл удалён» был бы засчитан при полностью пропущенном шаге.

Надёжнее — проверка, не зависящая от каталога, через git:
```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas
git ls-files numerical_solver/gpn_multiphase_solver/hydro/analytical.py
```
Ожидание: **пусто**. Непустой вывод = файл всё ещё в индексе, `git rm` не отработал.

**Подводные камни:**
- Удалять **после** шагов 2–5, иначе тесты упадут на импорте.
- Не удалять `hydro/__init__.py` (он пуст, но нужен как маркер пакета).
- Проверить, что нигде не осталось `.pyc` от удалённого модуля: `__pycache__` пересоберётся сам, но при странных ошибках импорта — удалить `numerical_solver/gpn_multiphase_solver/hydro/__pycache__/`.

**Зависимости:** требует — шаги 2, 3, 4, 5.

**Оценка:** ~10 строк, ~10 минут.

---

### Шаг 7: Синхронизировать проектные заметки vault

**Цель:** убрать из действующей документации описание модуля, которого больше нет.

**Контекст:**
Заметки в `vault/knowledge/decisions/` — это **действующая проектная документация**, а не архив: они описывают, как устроена библиотека сейчас. После шага 6 восемь из них будут описывать несуществующий модуль. Тесты этого не ловят вовсе — как и прозу docstring-ов (шаг 6), но здесь цена выше: по этим заметкам ориентируется разработчик, читающий архитектуру с нуля.

**Прецедент в проекте:** так делали в аналогичных задачах. Запись DEBT-007 завершается словами «Проектные заметки P1, P4, P8 синхронизированы», план DEBT-013 содержит шаги правки заметок `[[json-config-schema]]`, `[[P8-формат-ввода-json]]`. DEBT-005 без такого шага выбивалась бы из практики.

**Файлы (11 упоминаний в 8 заметках, найдено аудитом раунда 4):**

| Заметка | Упом. | Характер правки |
|---|---|---|
| `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md` | 1 | стр. 68 — строка `analytical.py # AnalyticalHydroSolver` в дереве модулей: удалить |
| `vault/knowledge/decisions/модули-hydro-newton.md` | 2 | стр. 69, 74 — целый раздел «Аналитическая заглушка» с листингом класса: переписать под тестовый двойник или пометить как исторический |
| `vault/knowledge/decisions/порядок-реализации-модулей.md` | 2 | стр. 83, 88 — модуль в порядке реализации фаз |
| `vault/knowledge/decisions/модули-simulator-оркестратор.md` | 2 | упоминание в списке реализаций |
| `vault/knowledge/decisions/вопросы-реализации-2.md` | 2 | упоминание |
| `vault/knowledge/decisions/решения-финальные.md` | 1 | упоминание |
| `vault/knowledge/decisions/P5-pvt-архитектура.md` | 1 | упоминание |
| `vault/knowledge/decisions/P1-адаптер-единицы.md` | 1 | упоминание |

**Что сделать:**
1. В каждой заметке заменить описание production-модуля на указание, что заглушка вынесена в `tests/_doubles.py` под именем `LogProfileHydroStub` (DEBT-005).
2. Формулировка — единая: «тестовый двойник, не решатель; в пакете отсутствует с DEBT-005».
3. Где упоминание чисто историческое (описание уже пройденной фазы реализации) — оставить, но пометить: «(удалён в DEBT-005)». Переписывать историю не нужно.

**Что НЕ трогать:**
Файлы в `vault/plans/` — исторический архив выполненных задач (`feat-014` — 16 упоминаний, `val-001` — 4, `feat-012` — 3). Они фиксируют состояние на момент своей реализации и правке не подлежат.

**Проверка:**
```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas
git grep -n "AnalyticalHydroSolver" -- vault/knowledge/
```
Ожидание: либо пусто, либо только строки с явной пометкой «удалён в DEBT-005».

**Зависимости:** требует — шаг 6 (сначала удалить, потом описывать удаление).

**Оценка:** 8 файлов, ~11 строк, ~15 минут.

---

## 4. Тестовая стратегия

Ключевое для DEBT — **неизменность поведения**. Новых тестов не пишется: логика не меняется, меняется местоположение.

### 4.1. Regression (главный критерий)

**Тест:** весь набор
**Файл:** `numerical_solver/tests/`
**Сценарий:** после каждого шага — полный прогон
**Ожидание:** **812 passed** на каждом шаге, от 1 до 6
**Baseline:** 812 passed / ~135 с на `52e4588`
**Предотвращает:** любую регрессию при переносе

⚠️ **Число тестов не должно измениться ни на одном шаге.** Класс не удаляется по смыслу, а переезжает; все 16 тестов `test_hydro.py` сохраняются (решение §Шаг 5). Если после шага 5 стало 811 или 813 — искать причину, не «принимать как есть».

### 4.2. Численная идентичность

**Тест:** `test_hydro.py::TestEndToEndRate::test_G_o_concrete_number`
**Файл:** `numerical_solver/tests/test_hydro.py:227`
⚠️ Тест с таким же именем есть и в `tests/test_fluxes.py:214` (другая фикстура `result_1ph`, другое число). Запускать с полным путём: `pytest "tests/test_hydro.py::TestEndToEndRate::test_G_o_concrete_number" -v`
**Сценарий:** $G_o[0]$ при $p_{wf} = 10$ МПа, $p_{ext} = 20$ МПа, $N = 20$
**Ожидание:** $-0.009138144903103$ при `rel=1e-10` — **бит в бит как до переноса**
**Предотвращает:** искажение арифметики при копировании класса

**Тест:** `test_simulator.py::TestPhysics::test_pressure_is_analytical_log_profile`
**Файл:** `numerical_solver/tests/test_simulator.py:321`
**Сценарий:** полный цикл Simulator, сверка $p$ с формулой лог-профиля
**Ожидание:** совпадение при `rtol=1e-12`
**Предотвращает:** потерю детерминированности двойника — свойства, ради которого он и сохраняется

### 4.3. Чистота пакета

**Проверка:** `git grep -n "AnalyticalHydroSolver" -- numerical_solver/gpn_multiphase_solver/`
**Ожидание:** пусто
**Предотвращает:** забытое упоминание в docstring

**Проверка:** `git grep -n "hydro.analytical" -- numerical_solver/`
**Ожидание:** пусто
**Предотвращает:** оставшийся импорт удалённого модуля

### 4.4. Производительность

**Ожидание:** время полного прогона ~135 с, без роста.
**Обоснование:** двойник дешевле `PrototypeHydroAdapter` (нет Newton-итераций), и он сохраняется — значит деградации быть не может. Если время выросло существенно — где-то случайно подставлен настоящий солвер.

---

## 5. Критерии завершения

🔴 **Все `git grep` ниже исполнять из корня репозитория** (аудит, раунд 3). Пути в них заданы от корня, а `git grep` разрешает pathspec относительно текущего каталога: из `numerical_solver/` они молча возвращают **пустой вывод и код 0** — то есть засчитывают критерий при полностью невыполненной работе (проверено). Перед блоком проверок:
```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas
```

- [ ] Все 7 шагов выполнены
- [ ] `pytest tests/ -q` → **812 passed** (из `numerical_solver/`; или обоснованное отличие, зафиксированное в отчёте)
- [ ] `git ls-files numerical_solver/gpn_multiphase_solver/hydro/analytical.py` → пусто (файл удалён и выведен из индекса; надёжнее `Test-Path`, см. шаг 6)
- [ ] `git grep "AnalyticalHydroSolver" -- numerical_solver/gpn_multiphase_solver/` → пусто
- [ ] `git grep "AnalyticalHydroSolver" -- numerical_solver/tests/` → пусто (проза docstring-ов; тесты этого не ловят)
- [ ] `git grep "hydro.analytical" -- numerical_solver/` → пусто
- [ ] `git grep "test_analytical_is_hydro_solver" -- numerical_solver/` → пусто (переименование шага 5.3)
- [ ] `tests/_doubles.py` создан, содержит `LogProfileHydroStub`
- [ ] Docstring в `hydro/base.py` и `simulator.py` не упоминают удалённый класс
- [ ] `test_G_o_concrete_number` даёт прежнее число
- [ ] Время прогона не выросло
- [ ] Import graph чистый: `tests/ → gpn_multiphase_solver/`, обратного направления нет
- [ ] `git grep "AnalyticalHydroSolver" -- vault/knowledge/` → пусто либо только строки с пометкой «удалён в DEBT-005» (шаг 7)
- [ ] Vault обновлён: статус DEBT-005 → ✅ ГОТОВО, с датой и фактическим числом тестов
- [ ] GitHub issue #28 прокомментирован результатом

---

## 6. Оценка

| Параметр | Значение |
|---|---|
| Файлов затронуто | 16 (1 новый, 1 удалён, 6 правок кода, 8 заметок vault) |
| Строк изменений | ~101 (~70 — перенос без изменений, ~20 код/docstring, ~11 vault) |
| Шагов | 7 |
| Время | ~70 минут |
| Риск | низкий — логика не меняется, покрытие сохраняется полностью |

---

## 7. Порядок коммитов

Пользователь коммитит сам. Рекомендуемое разбиение (каждый коммит — зелёные тесты):

1. `test: тестовый двойник LogProfileHydroStub` — шаг 1
2. `test: переключить тесты на LogProfileHydroStub` — шаги 2–5
3. `refactor: удалить AnalyticalHydroSolver из пакета` — шаг 6
4. `vault: синхронизировать заметки после удаления заглушки` — шаг 7
5. `vault: DEBT-005 закрыт` — статус в реестре

Коммиты 4 и 5 — vault, отдельно от кода (конвенция проекта: vault-изменения не смешиваются с кодом). Шаг 7 идёт отдельным коммитом от закрытия задачи, потому что это правка проектной документации, а не отчёт о статусе.

Merge в `numerical_scheme/implementation` через `--no-ff`.

---

## 8. Что зафиксировать в отчёте после реализации

1. Фактическое число тестов после каждого шага (ожидание, проверенное аудитом: 812 на всех шагах).
2. Подтверждение, что `test_G_o_concrete_number` дал прежнее число.
3. Подтверждение, что `test_analytical_is_hydro_solver` **переименован вручную** — массовая замена его не ловит (см. шаг 5).
4. Если какой-то тест `test_hydro.py` признан избыточным — какой и почему.

Пункт про форму импорта снят: вопрос закрыт до реализации — внутри тестов только `from ._doubles import ...` (проверено, см. шаг 2).

---

## 9. Связанные заметки

- `vault/roadmap/известные баги и технический долг.md` → `### DEBT-005`
- `vault/plans/feat-014-hydro-to-blackoil-adapter.md` — FEAT-014, после которой возник долг
- `vault/plans/debt-013 remove-save-every.md` — DEBT-013, затронувшая `test_simulator.py`
- `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md`
- `vault/knowledge/decisions/конвенции-знаков.md` — знак $G_o < 0$ при притоке к скважине
