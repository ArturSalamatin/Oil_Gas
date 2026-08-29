---
tags:
  - план
  - фича
  - интеграция
id: FEAT-012
date: 2026-08-29
status: реализован
branch: feat/prototype-factory
audit:
  date: 2026-08-29
  found: 1
  auto-fixed: 1
  manual-required: 0
---

# FEAT-012: Интеграция прототипа в Factory: табличный PVT + PrototypeHydroAdapter из JSON

## Мотивация

PrototypeHydroAdapter реализован и протестирован (35 тестов), но доступен только при ручном создании объектов. Factory (`factory.py`) создаёт только AnalyticalHydroSolver. Нужно:

1. Добавить ветку `pvt.model == "table"` → читать CSV, создать BlackOilPVT + PrototypePVTAdapter
2. Добавить ветку `relperm.model == "table"` → читать CSV, создать TabulatedRelPerm + PrototypeRPAdapter
3. Добавить выбор HydroSolver в Factory → PrototypeHydroAdapter при табличном PVT
4. Создать пример конфига с табличным PVT + тесты

После этого: `JSON (model=table) → Factory → Simulator.run()` — полный расчёт через прототип коллеги.

## Как начать

1. Прочитай этот файл целиком
2. Прочитай `gpn_multiphase_solver/factory.py` — текущая структура
3. Прочитай `tests/test_prototype_adapter.py` — как создаются объекты прототипа (фикстуры proto_pvt, proto_rp, model)
4. Прочитай `gpn_multiphase_solver/pvt/table_full.py` — сигнатура `TableFullPVT.__init__` (6 скалярных параметров, не `thermal_config`)
5. Прочитай `gpn_multiphase_solver/io/config.py` — `SimulationConfig` (нет `config_dir`), `PVTConfig` (поля `oil_pvt_file`, `gas_pvt_file`), `NumericsConfig`
6. Прочитай vault-заметки (ключевые для реализации):
   - `vault/knowledge/decisions/P8-формат-ввода-json.md` — формат CSV, пути к файлам, конвертация единиц
   - `vault/knowledge/decisions/P5-pvt-архитектура.md` — двухуровневый ABC (HydroPVT → FullPVT), TableFullPVT, адаптер
   - `vault/knowledge/decisions/P1-адаптер-единицы.md` — конвертация Па↔бар, согласованность PVT через Factory
   - `vault/knowledge/decisions/согласованность-pvt-hydro.md` — принцип: один PVT-объект на всю симуляцию
   - `vault/knowledge/decisions/json-config-schema.md` — структура JSON-конфига, поля pvt/relperm
7. Справочно (читать при необходимости):
   - `vault/knowledge/decisions/hydro-prototype-анализ.md` — обзор прототипа v1.0.3, единицы, конвенции
   - `vault/knowledge/decisions/P7-офп-без-производных.md` — PrototypeRPAdapter (TabulatedRelPerm → RelPermModel)
   - `vault/knowledge/decisions/P6-тепловые-свойства.md` — тепловые через FullPVT (c_p, μ_JT, L)
   - `vault/knowledge/decisions/P3-маппинг-состояния.md` — BlackOilState ↔ SimulationState
   - `vault/knowledge/decisions/P2-знаки-потоков-прототип.md` — конвенция знаков потоков
   - `vault/knowledge/decisions/P4-адаптивный-шаг.md` — A-retry при расходимости
8. Прогони тесты: `cd numerical_solver && .venv\Scripts\python -m pytest tests/ -v`
9. Начни с шага 0

## Зависимости

- Прототип: `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/` (путь относительно корня проекта!)
- В тестах прототип добавляется в `sys.path` в самом файле теста (см. `test_prototype_adapter.py:25–27`)
- В тестах Factory: аналогично, или через `$env:PYTHONPATH = "HydroSolverPrototype\Prototype_1.0.3"` (путь относительно `numerical_solver/`)

## Архитектура решения

```
JSON (pvt.model="table")
  │
  ├─ oil_pvt.csv ──→ _read_oil_pvt_csv() ──→ oil_rows [(Rs, p_bar, Bo, mu_cP), ...]
  ├─ gas_pvt.csv ──→ _read_gas_pvt_csv() ──→ gas_rows [(p_bar, Bg, mu_cP), ...]
  │
  └─→ BlackOilPVT(oil_rows, gas_rows)  ← объект прототипа
        │
        ├─→ PrototypePVTAdapter(proto_pvt, rho_o_std, rho_g_std)  ← наш HydroPVT (SI)
        │     используется: EnergySolver, Simulator (WellData), PrototypeHydroAdapter
        │
        └─→ RadialBlackOilModel(grid, rock, pvt, relperm, ...)  ← прототип
              │
              └─→ PrototypeHydroAdapter(model, grid, our_pvt)  ← наш HydroSolver
```

Ключевой принцип: **один BlackOilPVT** → обёрнут в PrototypePVTAdapter (для нашего кода) и передан в RadialBlackOilModel (для прототипа). Factory гарантирует согласованность.

## Формат CSV (SI → бар/сП)

CSV-файлы содержат данные в **SI** (Па, Па·с). Factory при создании BlackOilPVT конвертирует:
- pressure: Па → бар (делим на BAR_TO_PA = 1e5)
- mu_o: Па·с → сП (делим на CP_TO_PA_S = 1e-3)
- mu_g: Па·с → сП (делим на CP_TO_PA_S = 1e-3)
- Rs, Bo, Bg: без конвертации (безразмерные)

### oil_pvt.csv

```csv
Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s
0.0,5000000,1.05,0.003
0.0,30000000,1.04,0.0032
30.0,15000000,1.20,0.0015
30.0,30000000,1.18,0.0016
```

→ oil_rows = [(Rs, p_bar, Bo, mu_cP), ...] для BlackOilPVT

### gas_pvt.csv

```csv
pressure_Pa,Bg,mu_g_Pa_s
5000000,0.020,0.000012
15000000,0.008,0.000014
30000000,0.004,0.000018
```

→ gas_rows = [(p_bar, Bg, mu_cP), ...] для BlackOilPVT

### relperm.csv

```csv
Sg,kro,krg
0.0,1.0,0.0
0.1,0.8,0.01
0.2,0.6,0.05
0.4,0.3,0.2
0.6,0.1,0.5
0.8,0.0,0.8
```

→ TabulatedRelPerm(Sg, kro, krg) — безразмерные, конвертация не нужна

## Этапы

### Шаг 0: Добавить `config_dir` в SimulationConfig

**Цель:** Factory должен знать директорию JSON для разрешения относительных путей к CSV.
**Файлы:** `gpn_multiphase_solver/io/config.py`

**Почему:** сейчас `SimulationConfig` не хранит путь к директории JSON-конфига. `PVTConfig.oil_pvt_file` и `gas_pvt_file` — относительные пути, а `_create_pvt` получает только `config: SimulationConfig`, без возможности разрешить их в абсолютные.

**Что сделать:**
1. Добавить поле `config_dir: Path` в `SimulationConfig` (после `output`, с `field(default=Path("."))`)
2. В `load_config()` (строка ~172): заполнить `config_dir = path.parent` при создании `SimulationConfig`
3. Тесты, создающие `SimulationConfig` вручную (без `load_config`) — `config_dir` по умолчанию = `Path(".")`

**Проверка:** существующие тесты `test_config.py` не ломаются (default=Path(".")).

### Шаг 1: CSV-ридеры в factory.py

**Цель:** функции чтения CSV-файлов с конвертацией SI → бар/сП.
**Файлы:** `gpn_multiphase_solver/factory.py`
**Зависимости:** шаг 0 (config_dir для разрешения путей)

**Новые импорты в factory.py** (добавить в начало файла):
```python
import csv
from pathlib import Path
from .units import BAR_TO_PA, CP_TO_PA_S, M2_TO_MD
from .pvt.table_full import TableFullPVT
from .pvt.prototype_adapter import PrototypePVTAdapter, PrototypeRPAdapter
from .hydro.prototype_adapter import PrototypeHydroAdapter
```

**Что сделать:**
1. `_read_oil_pvt_csv(csv_path: Path) → list[tuple]` — читает CSV, конвертирует p: Па→бар, μ: Па·с→сП. Возвращает `[(Rs, p_bar, Bo, mu_cP), ...]`.
2. `_read_gas_pvt_csv(csv_path: Path) → list[tuple]` — аналогично: `[(p_bar, Bg, mu_cP), ...]`.
3. `_read_relperm_csv(csv_path: Path) → tuple[list, list, list]` — `(Sg, kro, krg)`.
Использовать `BAR_TO_PA` и `CP_TO_PA_S` из `units.py` для конвертации (не магические константы).

Путь к CSV разрешается через `config.config_dir / pc.oil_pvt_file` (шаг 0 гарантирует наличие `config_dir`).

**Формат CSV:** заголовок обязателен (первая строка). Пустые строки и строки с нечисловыми данными пропускаются.

**Проверка:** unit-тесты с тестовыми CSV.

### Шаг 2: Ветка `pvt.model == "table"` в _create_pvt

**Цель:** создать BlackOilPVT + PrototypePVTAdapter + TableFullPVT из CSV.
**Файлы:** `gpn_multiphase_solver/factory.py`
**Зависимости:** шаг 0, шаг 1

**Что сделать:**
1. В `_create_pvt`: добавить ветку `elif pc.model == "table"`:
   - Прочитать CSV: `oil_rows = _read_oil_pvt_csv(config.config_dir / pc.oil_pvt_file)`
   - Прочитать CSV: `gas_rows = _read_gas_pvt_csv(config.config_dir / pc.gas_pvt_file)`
   - Создать `BlackOilPVT(oil_rows, gas_rows)` — объект прототипа
   - Создать `PrototypePVTAdapter(proto_pvt, pc.rho_o_std, pc.rho_g_std)` — наш HydroPVT
   - Создать `TableFullPVT(hydro=proto_adapter, c_p_oil=tc.c_p_oil, c_p_gas=tc.c_p_gas, mu_JT_oil=tc.mu_JT_oil, mu_JT_gas=tc.mu_JT_gas, L_degas=tc.L_degas)` — наш FullPVT с тепловыми
   - Вернуть `full_pvt` (TableFullPVT). **Не возвращать tuple** — `from_config` ожидает один FullPVT

**Важно:** сигнатура `TableFullPVT.__init__` (table_full.py:15–18):
```python
def __init__(self, hydro: PrototypePVTAdapter,
             c_p_oil: float, c_p_gas: float,
             mu_JT_oil: float, mu_JT_gas: float,
             L_degas: float):
```
Передавать 6 отдельных скаляров, НЕ `thermal_config`.

**Как `_create_prototype_hydro` (шаг 4) получит proto_pvt и proto_rp?**
Вариант (B): `_create_prototype_hydro` создаёт proto_pvt и proto_rp самостоятельно, читая CSV повторно. Это ненужное дублирование чтения CSV.
**Принятый вариант (A — модифицированный):** `_create_pvt` для ветки `table` возвращает `TableFullPVT`, при этом `proto_pvt` (BlackOilPVT) доступен через `full_pvt._hydro._pvt`. Это внутренние атрибуты, но Factory — единственный потребитель, и доступ оправдан. Альтернатива — хранить proto_pvt как атрибут `TableFullPVT.proto_pvt`, добавив одну строку в `table_full.py:__init__`.

### Шаг 3: Ветка `relperm.model == "table"` в _create_relperm

**Цель:** создать TabulatedRelPerm + PrototypeRPAdapter из CSV.
**Файлы:** `gpn_multiphase_solver/factory.py`
**Зависимости:** шаг 0, шаг 1

**Что сделать:**
1. Прочитать relperm.csv: `Sg, kro, krg = _read_relperm_csv(config.config_dir / rc.file)`
2. Создать `TabulatedRelPerm(Sg, kro, krg)` — объект прототипа
3. Обернуть в `PrototypeRPAdapter(proto_rp)` — наш RelPermModel
4. Вернуть `PrototypeRPAdapter` (один объект, как и для Corey). **Не возвращать tuple**.

**Как `_create_prototype_hydro` (шаг 4) получит proto_rp?**
Через `relperm._rp` (внутренний атрибут PrototypeRPAdapter).

### Шаг 4: Выбор HydroSolver в Factory

**Цель:** при `pvt.model == "table"` создавать PrototypeHydroAdapter вместо AnalyticalHydroSolver.
**Файлы:** `gpn_multiphase_solver/factory.py`
**Зависимости:** шаг 2, шаг 3

**Что сделать:**
1. В `from_config` (строка ~52):
   ```python
   if config.pvt.model == "table":
       hydro = _create_prototype_hydro(config, grid, pvt, relperm)
   else:
       hydro = AnalyticalHydroSolver(grid, pvt, relperm)
   ```
2. `_create_prototype_hydro(config, grid, our_pvt: TableFullPVT, our_relperm: PrototypeRPAdapter)`:
   **Импорты прототипа — внутри функции** (ленивые), чтобы `factory.py` не падал при отсутствии прототипа в PYTHONPATH:
   ```python
   from radial_blackoil.grid import RadialGrid
   from radial_blackoil.rock import CompressibleRock
   from radial_blackoil.blackoil import RadialBlackOilModel
   ```
   - Извлечь proto_pvt: `our_pvt._hydro._pvt` (BlackOilPVT)
   - Извлечь proto_rp: `our_relperm._rp` (TabulatedRelPerm)
   - Создать `RadialGrid(rw, R_ext, h, N, k_mD)` — прототип. Параметры из `config.geometry` и `config.rock`. **Внимание:** k нужен в мД, а `config.rock.permeability` в м². Конвертация: `k_mD = config.rock.permeability * M2_TO_MD` (использовать `M2_TO_MD` из `units.py`).
   - Создать `CompressibleRock(phi_ref=config.rock.porosity, p_ref_bar=config.initial_conditions.p0/BAR_TO_PA, cr_per_bar=config.rock.compressibility*BAR_TO_PA)`
   - p_bhp_bar: `config.time.history[0].p_wf / BAR_TO_PA` (первый интервал)
   - p_outer_bar: `config.initial_conditions.p0 / BAR_TO_PA`
   - outer_rs: `config.initial_conditions.Rs0`
   - skin: `config.numerics.skin`
   - jacobian_mode: `config.numerics.jacobian_mode`
   - linear_solver: `config.numerics.linear_solver`
   - Создать `RadialBlackOilModel(grid, rock, pvt, relperm, p_bhp_bar, p_outer_bar, outer_rs_sm3_sm3, skin, jacobian_mode=..., linear_solver=...)`
   - Обернуть в `PrototypeHydroAdapter(model, grid, our_pvt._hydro)` — `our_pvt._hydro` это PrototypePVTAdapter

**Сигнатура RadialBlackOilModel.__init__** (blackoil.py:24–27):
```python
def __init__(self, grid, rock, pvt, relperm, p_bhp_bar, p_outer_bar,
             outer_rs_sm3_sm3, skin=0.0, rs_switch_tol=1e-5,
             sg_switch_tol=1e-9, gas_residual_scale=None,
             jacobian_mode='grouped', linear_solver='sparse'):
```

**Сигнатура PrototypeHydroAdapter.__init__** (hydro/prototype_adapter.py:34):
```python
def __init__(self, model, grid: Grid, pvt: HydroPVT, max_retries: int = 5):
```

### Шаг 5: Пример конфига + тестовые CSV

**Цель:** конфиг с `pvt.model == "table"` и CSV-файлы.
**Файлы:** `configs/table_pvt/config.json`, `configs/table_pvt/oil_pvt.csv`, `configs/table_pvt/gas_pvt.csv`, `configs/table_pvt/relperm.csv`
**Зависимости:** шаги 0–4

**Что сделать:**
1. Создать CSV с простыми таблицами (аналогичные тестовым в test_prototype_adapter.py, но в SI: давление в Па, вязкость в Па·с)
2. JSON: `pvt.model = "table"`, `pvt.oil_pvt_file = "oil_pvt.csv"`, `pvt.gas_pvt_file = "gas_pvt.csv"`, `relperm.model = "table"`, `relperm.file = "relperm.csv"`, все остальные секции как в baseline

### Шаг 6: Тесты

**Файлы:** `tests/test_factory_prototype.py`
**Зависимости:** шаги 0–5

**Тесты:**
1. **CSV-ридеры**: _read_oil_pvt_csv, _read_gas_pvt_csv, _read_relperm_csv — формат, конвертация единиц, пустые строки
2. **Factory с табличным PVT**: `from_config(table_config)` → Simulator создан, HydroSolver = PrototypeHydroAdapter
3. **Pipeline**: `from_config → run → history` — не падает, n_saved > 1, q_o > 0
4. **PVT-согласованность**: `our_pvt.Bo(p) == proto_pvt.bo(p/BAR_TO_PA)` — один BlackOilPVT
5. **Баланс масс**: через `model.step_global_balance()` (независимый эталон)
6. **Ошибки**: pvt.model="table" без CSV файла → ValueError
7. **config_dir**: тест с конфигом, где CSV лежит в поддиректории — путь разрешается корректно

**Требуют PYTHONPATH** или sys.path insert (как test_prototype_adapter.py:25–27).

### Шаг 7: Обновить vault

**Файлы:** vault-заметки

**Что сделать:**
1. Обновить `vault/knowledge/decisions/модули-simulator-оркестратор.md`: Factory поддерживает `pvt.model = "table"`
2. Обновить `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md`: factory.py описание
3. Обновить `vault/knowledge/decisions/порядок-реализации-модулей.md`: фаза 4a — завершена

## Подводные камни

### 1. sys.path для прототипа

Прототип не установлен как пакет. Расположен в `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/`.

**Решение для текущей стадии:** требовать `PYTHONPATH` при запуске с табличным PVT. Factory не управляет sys.path. В тестах — добавлять в sys.path вручную (как test_prototype_adapter.py:25–27).

### 2. Два Grid: наш LogRadialGrid vs RadialGrid прототипа

Прототип создаёт свой RadialGrid. Наш LogRadialGrid имеет другую формулу центров ячеек (центр масс vs √). Проводимости расходятся → баланс масс нашего HydroResult ≠ 0 (допуск ~2% в test_prototype_adapter).

Это известная проблема (зарегистрирована в P8). Временное решение: два Grid с одинаковыми rw, R, N. Баланс масс проверяется через `model.step_global_balance()` (внутренний, через Grid прототипа).

### 3. TableFullPVT

`pvt/table_full.py` уже существует — обёртка PrototypePVTAdapter + скалярные тепловые свойства. **Внимание:** конструктор принимает 6 отдельных скаляров `(hydro, c_p_oil, c_p_gas, mu_JT_oil, mu_JT_gas, L_degas)`, не `thermal_config`.

### 4. p_bhp и p_outer для RadialBlackOilModel

RadialBlackOilModel принимает p_bhp_bar и p_outer_bar в конструкторе. Но BC меняется между интервалами (разные p_wf). PrototypeHydroAdapter вызывает `model.set_bhp_control()` на каждом шаге — начальное p_bhp не критично, но должно быть валидным.

**Решение:** передать p_wf первого интервала и p_ext из initial_conditions. set_bhp_control обновит при первом solve().

### 5. Конвертация единиц проницаемости

`config.rock.permeability` в м², а `RadialGrid` прототипа ожидает k в мД. Конвертация: `k_mD = k_m2 * M2_TO_MD` (использовать `M2_TO_MD` из `units.py`). Пропуск конвертации → заниженная проницаемость на 15 порядков → solver не сойдётся.

### 6. Конвертация сжимаемости породы

`config.rock.compressibility` в 1/Па, а `CompressibleRock` прототипа ожидает `cr_per_bar` в 1/бар. Конвертация: `cr_per_bar = cr_pa * BAR_TO_PA`. Если `compressibility = 0` (по умолчанию), конвертация не влияет.

### 8. Ленивые импорты прототипа

Импорты `radial_blackoil.*` в `_create_prototype_hydro` должны быть **внутри функции**, не на уровне модуля. Иначе `factory.py` упадёт при `import gpn_multiphase_solver` если прототип не в PYTHONPATH — это сломает ВСЮ библиотеку, включая `pvt.model = "standing"`.

### 7. Доступ к proto_pvt и proto_rp из обёрток

`_create_prototype_hydro` достаёт proto_pvt через `our_pvt._hydro._pvt` и proto_rp через `our_relperm._rp`. Это приватные атрибуты. Допустимо, поскольку Factory — единственный потребитель, и это внутренние классы пакета. Альтернатива — добавить публичные свойства, но это усложняет интерфейс без реальной выгоды.

## Критерии завершения

- [ ] `config_dir` добавлен в SimulationConfig, load_config заполняет его
- [ ] CSV-ридеры реализованы и протестированы
- [ ] `pvt.model = "table"` → Factory создаёт PrototypeHydroAdapter
- [ ] `relperm.model = "table"` → Factory создаёт PrototypeRPAdapter
- [ ] Pipeline: table_config.json → Factory → run → history ОК
- [ ] PVT-согласованность: наш pvt обёрт over тот же BlackOilPVT
- [ ] Баланс масс через step_global_balance < 1e-8
- [ ] Все 541+ тестов зелёные
- [ ] Vault обновлён

## Оценка

~1 сессия. 7 функций (3 CSV-ридера, _create_prototype_hydro, 2 ветки в _create_pvt/_create_relperm, расширение config) + тесты + конфиг.
