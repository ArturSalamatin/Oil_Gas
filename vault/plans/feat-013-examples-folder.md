---
id: feat-013-examples-folder
title: "FEAT-013: Папка examples — сценарии использования и единый запуск"
type: plan
status: черновик
created: 2026-09-01
updated: 2026-09-01
tags: [plan, feat, infrastructure, examples]
---

# FEAT-013: Папка examples — сценарии использования и единый запуск

## Цель

Создать папку `numerical_solver/examples/` со структурированными сценариями
использования солвера. Каждый сценарий — отдельная подпапка с полным pipeline:
JSON-конфиг → Factory → Simulator.run() → графики (.png) + таблицы (.csv).

Единый `run_all.py` запускает все сценарии последовательно.
Каждый сценарий запускается индивидуально.

**Главная задача examples** — показать пользователю все допустимые комбинации
конкретных модулей (реализаций) библиотеки. Пользователь берёт ближайший
к своей задаче пример и модифицирует конфиг.

---

## 1. Инвентаризация конкретных реализаций

### 1.1 Модули и реализации

| Модуль | ABC | Реализация | JSON-ключ | Комментарий |
|--------|-----|------------|-----------|-------------|
| **Grid** | `Grid` | `LogRadialGrid` | `grid.type = "log_radial"` | единственная |
| **PVT (гидро)** | `HydroPVT` | `StandingFullPVT` | `pvt.model = "standing"` | корреляции, параметры в JSON |
| | | `TableFullPVT` | `pvt.model = "table"` | CSV-таблицы (oil_pvt.csv, gas_pvt.csv) |
| **ОФП** | `RelPermModel` | `CoreyRP` | `relperm.model = "corey"` | аналитическая, параметры в JSON |
| | | `PrototypeRPAdapter` | `relperm.model = "table"` | CSV-таблица (relperm.csv) |
| **HydroSolver** | `HydroSolver` | `PrototypeHydroAdapter` | — | единственный (после FEAT-014) |
| **EnergySolver** | `EnergySolver` | `TridiagEnergySolver` | — | единственный |
| **WellControl** | `WellControl` | `PressureControl` | `control = "pressure"` | единственный |

### 1.2 PVT: тепловая часть (скаляры)

Тепловая часть PVT — одинакова у `StandingFullPVT` и `TableFullPVT`:
скалярные константы из секции `thermal` JSON-конфига.
Каждый эффект включается/выключается числом.

| Коэффициент | JSON | = 0 означает |
|-------------|------|-------------|
| $\mu_{JT,o}$ | `thermal.mu_JT_oil` | нет JT нефти |
| $\mu_{JT,g}$ | `thermal.mu_JT_gas` | нет JT газа |
| $L$ | `thermal.L_degas` | нет теплоты дегазации |

$c_{p,o}$, $c_{p,g}$ — всегда > 0 (знаменатель).

### 1.3 Матрица комбинаций PVT × ОФП

Четыре допустимых комбинации:

| Комбинация | PVT (гидро) | ОФП | Внешние файлы | Когда используется |
|-----------|-------------|-----|---------------|-------------------|
| **A** | `StandingFullPVT` | `CoreyRP` | нет | Параметры известны, данных нет |
| **B** | `TableFullPVT` | `PrototypeRPAdapter` | oil_pvt.csv, gas_pvt.csv, relperm.csv | Полный набор лабораторных данных |
| **C** | `StandingFullPVT` | `PrototypeRPAdapter` | relperm.csv | Корреляции PVT + лабораторные ОФП |
| **D** | `TableFullPVT` | `CoreyRP` | oil_pvt.csv, gas_pvt.csv | Лабораторные PVT, ОФП неизвестны |

---

## 2. Три семейства сценариев

### Семейство 1: однофазные ($R_s = 0$)

Комбинация A (Standing + Corey). $R_s = 0$ → несжимаемая жидкость,
$p_b < 0$, $S_g = 0$ всюду. Варьируются тепловые скаляры.

| № | Название | $\mu_{JT}$ | $L$ |
|---|---------|-----------|-----|
| 01 | `01_single_phase_no_jt` | 0 | 0 |
| 02 | `02_single_phase_jt` | > 0 | 0 |

### Семейство 2: четыре комбинации модулей ($R_s > 0$, полная термика)

Разгазирование, все тепловые эффекты включены ($\mu_{JT,o} > 0$, $\mu_{JT,g} < 0$, $L > 0$).
Одни и те же физические условия, разные модули — пользователь видит,
как задать каждую комбинацию в конфиге.

| № | Название | PVT | ОФП | Комбинация |
|---|---------|-----|-----|-----------|
| 03 | `03_standing_corey` | Standing | Corey | A |
| 04 | `04_table_table` | Table | Table | B |
| 05 | `05_standing_table_rp` | Standing | Table | C |
| 06 | `06_table_corey_rp` | Table | Corey | D |

### Семейство 3: изоляция тепловых эффектов ($R_s > 0$)

Одна комбинация модулей (B: Table + Table), варьируются тепловые скаляры.
Показывает вклад каждого теплового эффекта.

| № | Название | $\mu_{JT}$ | $L$ | $p_{wf}$ |
|---|---------|-----------|-----|----------|
| 07 | `07_degassing_adiabatic_only` | 0 | 0 | 15 МПа |
| 08 | `08_degassing_jt` | > 0 | 0 | 15 МПа |
| 09 | `09_degassing_latent_heat` | 0 | > 0 | 15 МПа |
| 10 | `10_deep_degassing` | > 0 | > 0 | 8 МПа |

Примечание: сценарий с полной термикой при 15 МПа = сценарий 04 (семейство 2).
Поэтому семейство 3 не дублирует его.

---

## 3. Полная таблица сценариев с конкретными классами

| № | PVT гидро | PVT термо (скаляры) | ОФП | HydroSolver | EnergySolver | $R_s$ | $\mu_{JT,o}$ | $\mu_{JT,g}$ | $L$ | $p_{wf}$ |
|---|-----------|--------------------|----|-------------|-------------|-------|-------------|-------------|-----|----------|
| 01 | `StandingFullPVT` | $\mu_{JT}=0$, $L=0$ | `CoreyRP` | `PrototypeHydroAdapter` | `TridiagEnergySolver` | 0 | 0 | 0 | 0 | 15 МПа |
| 02 | `StandingFullPVT` | $\mu_{JT,o}>0$, $L=0$ | `CoreyRP` | `PrototypeHydroAdapter` | `TridiagEnergySolver` | 0 | $4{\times}10^{-7}$ | 0 | 0 | 15 МПа |
| 03 | `StandingFullPVT` | полная | `CoreyRP` | `PrototypeHydroAdapter` | `TridiagEnergySolver` | 50 | $4{\times}10^{-7}$ | $-4{\times}10^{-6}$ | 168000 | 15 МПа |
| 04 | `TableFullPVT` | полная | `PrototypeRPAdapter` | `PrototypeHydroAdapter` | `TridiagEnergySolver` | 30 | $4{\times}10^{-7}$ | $-4{\times}10^{-6}$ | 168000 | 15 МПа |
| 05 | `StandingFullPVT` | полная | `PrototypeRPAdapter` | `PrototypeHydroAdapter` | `TridiagEnergySolver` | 50 | $4{\times}10^{-7}$ | $-4{\times}10^{-6}$ | 168000 | 15 МПа |
| 06 | `TableFullPVT` | полная | `CoreyRP` | `PrototypeHydroAdapter` | `TridiagEnergySolver` | 30 | $4{\times}10^{-7}$ | $-4{\times}10^{-6}$ | 168000 | 15 МПа |
| 07 | `TableFullPVT` | $\mu_{JT}=0$, $L=0$ | `PrototypeRPAdapter` | `PrototypeHydroAdapter` | `TridiagEnergySolver` | 30 | 0 | 0 | 0 | 15 МПа |
| 08 | `TableFullPVT` | $\mu_{JT}>0$, $L=0$ | `PrototypeRPAdapter` | `PrototypeHydroAdapter` | `TridiagEnergySolver` | 30 | $4{\times}10^{-7}$ | $-4{\times}10^{-6}$ | 0 | 15 МПа |
| 09 | `TableFullPVT` | $\mu_{JT}=0$, $L>0$ | `PrototypeRPAdapter` | `PrototypeHydroAdapter` | `TridiagEnergySolver` | 30 | 0 | 0 | 168000 | 15 МПа |
| 10 | `TableFullPVT` | полная | `PrototypeRPAdapter` | `PrototypeHydroAdapter` | `TridiagEnergySolver` | 30 | $4{\times}10^{-7}$ | $-4{\times}10^{-6}$ | 168000 | 8 МПа |

### Замечания

- Сценарии 01–03, 05 используют `StandingFullPVT` → после FEAT-014 (адаптер HydroPVT → BlackOilPVT).
  До FEAT-014: генерируем CSV из Standing.
- Сценарии 03, 05: $R_s = 50$ (Standing), сценарии 04, 06–10: $R_s = 30$ (Table CSV).
  $R_s$ различается, т.к. CSV-таблицы из `configs/table_pvt/` построены для $R_s \leq 30$.
- Сценарий 05 (Standing + Table ОФП): нужен relperm.csv, но не oil/gas CSV.
- Сценарий 06 (Table PVT + Corey ОФП): нужны oil/gas CSV, но не relperm CSV.

---

## 4. Общие параметры (все сценарии)

### Геометрия и порода

| Параметр | Значение |
|----------|----------|
| $r_w$ | 0.1 м |
| $R_e$ | 50 м |
| $h$ | 10 м |
| $\phi$ | 0.2 |
| $k$ | $10^{-13}$ м² (≈ 100 мД) |
| $(\rho c_p)_s$ | $1.25 \times 10^6$ Дж/(м³·К) |
| $\lambda_s$ | 1.5 Вт/(м·К) |
| $\lambda_o$ | 0.14 Вт/(м·К) |
| $\lambda_g$ | 0.04 Вт/(м·К) |

### PVT общие

| Параметр | Значение |
|----------|----------|
| $\rho_{o,\text{ст}}$ | 850 кг/м³ |
| $\rho_{g,\text{ст}}$ | 0.85 кг/м³ |
| $c_{p,o}$ | 2000 Дж/(кг·К) |
| $c_{p,g}$ | 1000 Дж/(кг·К) |

### Тепловые (где включены)

| Параметр | Значение |
|----------|----------|
| $\mu_{JT,o}$ | $4 \times 10^{-7}$ К/Па |
| $\mu_{JT,g}$ | $-4 \times 10^{-6}$ К/Па |
| $L$ | 168000 Дж/кг |

### Время и сетка

| Параметр | Значение |
|----------|----------|
| $p_0$ | 20 МПа |
| $T_0$ | 350 К |
| $N$ | 50 (сц. 01–03, 05), 20 (сц. 04, 06–10) |
| $\Delta t$ | 3600 с |
| Время | 3 суток (сц. 01–03, 05, 10), 1 сутки (сц. 04, 06–09) |

### ОФП Corey (где используется)

| Параметр | Значение |
|----------|----------|
| $S_{or}$ | 0.2 |
| $S_{gc}$ | 0.05 |
| $n_o$ | 2.0 |
| $n_g$ | 2.0 |
| $k_{ro,\max}$ | 1.0 |
| $k_{rg,\max}$ | 0.8 |

---

## 5. Описание семейств

### Семейство 1: однофазные

**01 — Однофазная без JT.** $R_s = 0$, все тепловые = 0.
На первом шаге давление перестраивается из $p_0 = \text{const}$ в стационарный профиль →
$dp/dt \neq 0$ → адиабатический эффект → небольшое отклонение $T$ от $T_0$.
На последующих шагах давление стационарно → $dp/dt \approx 0$ → $T$ возвращается к $T_0$.

**02 — Однофазная + JT.** Добавлен $\mu_{JT,o} > 0$.
Стационарный JT-источник: $\Delta T(r_w) \approx \mu_{JT,o} \cdot (p_0 - p_{wf}) = 2$ К.

### Семейство 2: комбинации модулей

Все четыре сценария (03–06) — разгазирование с полной термикой.
Одни и те же физические условия (насколько позволяют разные PVT-данные).
Пользователь видит, как задать каждую комбинацию PVT × ОФП в конфиге.

**03 — Standing + Corey.** Вся физика из параметров JSON, никаких CSV.

**04 — Table + Table.** Полный набор CSV. Лабораторные данные.

**05 — Standing + Table ОФП.** Корреляции PVT, но лабораторные ОФП (relperm.csv).
Типичная ситуация: PVT по корреляциям, ОФП из керновых экспериментов.

**06 — Table PVT + Corey ОФП.** Табличные PVT из лаборатории,
ОФП неизвестны — используется аналитическая модель Кори.

### Семейство 3: изоляция тепловых эффектов

Одна комбинация модулей (Table + Table), варьируются тепловые скаляры.

**07 — Только адиабатика.** $\mu_{JT} = 0$, $L = 0$.
Единственный источник изменения $T$ — адиабатический эффект $\phi \cdot dp/dt$.
В двухфазной зоне давление меняется нестационарно → $Q_{ad} \neq 0$.

**08 — + JT.** $\mu_{JT} > 0$, $L = 0$.
К адиабатике добавлен JT-эффект. Разница $T_{08} - T_{07}$ — чистый вклад JT.

**09 — + скрытая теплота.** $\mu_{JT} = 0$, $L > 0$.
К адиабатике добавлена теплота дегазации. Разница $T_{09} - T_{07}$ — чистый вклад $L$.

**10 — Глубокое разгазирование.** Полная модель ($\mu_{JT} > 0$, $L > 0$),
$p_{wf} = 8$ МПа. Стресс-тест: высокие $S_g$, сильная нелинейность.
Полная модель при 15 МПа = сценарий 04.

---

## 6. Структура папки

```
numerical_solver/examples/
├── run_all.py
├── _common.py
│
├── 01_single_phase_no_jt/
│   ├── config.json
│   ├── README.md
│   └── main.py
│
├── 02_single_phase_jt/
│   ├── config.json
│   ├── README.md
│   └── main.py
│
├── 03_standing_corey/
│   ├── config.json
│   ├── README.md
│   └── main.py
│
├── 04_table_table/
│   ├── config.json
│   ├── oil_pvt.csv
│   ├── gas_pvt.csv
│   ├── relperm.csv
│   ├── README.md
│   └── main.py
│
├── 05_standing_table_rp/
│   ├── config.json
│   ├── relperm.csv
│   ├── README.md
│   └── main.py
│
├── 06_table_corey_rp/
│   ├── config.json
│   ├── oil_pvt.csv
│   ├── gas_pvt.csv
│   ├── README.md
│   └── main.py
│
├── 07_degassing_adiabatic_only/
│   ├── config.json
│   ├── oil_pvt.csv
│   ├── gas_pvt.csv
│   ├── relperm.csv
│   ├── README.md
│   └── main.py
│
├── 08_degassing_jt/
│   ├── config.json
│   ├── oil_pvt.csv
│   ├── gas_pvt.csv
│   ├── relperm.csv
│   ├── README.md
│   └── main.py
│
├── 09_degassing_latent_heat/
│   ├── config.json
│   ├── oil_pvt.csv
│   ├── gas_pvt.csv
│   ├── relperm.csv
│   ├── README.md
│   └── main.py
│
└── 10_deep_degassing/
    ├── config.json
    ├── oil_pvt.csv
    ├── gas_pvt.csv
    ├── relperm.csv
    ├── README.md
    └── main.py
```

Результаты: `<example>/output/` (в `.gitignore`).

---

## 7. Pipeline (_common.py)

```python
"""Общий pipeline для всех примеров.

run_example(config_path, output_dir, title):
  1. load_config(config_path)
  2. SimulatorFactory.from_config(config) → (simulator, initial_state)
  3. history = simulator.run(initial_state)
  4. save_well_csv(history, output_dir / "well_history.csv")
  5. save_csv(history, grid, output_dir / "profiles.csv")
  6. plot_profiles → .png
  7. plot_wellbore_dynamics → .png
  8. plot_well_rate → .png
"""
```

Новое: `save_well_csv` в `io/output.py`.

### main.py (каждый пример)

```python
"""Сценарий NN: описание."""
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import run_example

if __name__ == "__main__":
    here = Path(__file__).parent
    run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title="NN: описание",
    )
```

### run_all.py

Последовательный запуск через `subprocess.run` (изоляция).
При ошибке — стоп с кодом ≠ 0.

---

## 8. Выходные файлы

### CSV (в output/)

- `well_history.csv` — скважинные данные (1 строка = 1 шаг):
  `time_s,q_o_m3st_s,q_g_m3st_s,p_wf_Pa,T_wf_K`
- `profiles.csv` — профили по сетке (tidy format):
  `step,time_s,r_m,p_Pa,T_K,Sg,Rs`

### Графики (в output/)

| Файл | Содержание |
|------|-----------|
| `pressure_profiles.png` | $p(r)$ на 3–4 моментах (semilogx) |
| `temperature_profiles.png` | $T(r)$ на тех же моментах |
| `saturation_profiles.png` | $S_g(r)$ (семейства 2, 3) |
| `well_rates.png` | $q_o(t)$, $q_g(t)$ |
| `wellbore_dynamics.png` | $p(r_w, t)$, $T(r_w, t)$, $S_g(r_w, t)$ |

---

## 9. Содержание README.md

Каждый README содержит:

1. **Описание** — какая физика моделируется, какой режим.
2. **Комбинация модулей** — какие конкретные классы создаются (таблица).
3. **Параметры** — ключевые числа из config.json с физическим смыслом.
4. **Ожидаемое поведение** — что увидит пользователь на графиках.
5. **Как модифицировать** — какие параметры менять для своей задачи.

---

## 10. Зависимости

- `gpn_multiphase_solver` (pip install -e .)
- `radial_blackoil` (прототип) в PYTHONPATH — для всех сценариев
- matplotlib (графики)
- FEAT-014 — для сценариев 01–03, 05 (Standing + Prototype)

---

## 11. Шаги реализации

### Шаг 1: Инфраструктура
- [ ] Создать `numerical_solver/examples/`
- [ ] Написать `_common.py` с `run_example`
- [ ] Добавить `save_well_csv` в `io/output.py`
- [ ] Написать `run_all.py`
- [ ] Добавить `examples/**/output/` в `.gitignore`

### Шаг 2: Семейство 1 — однофазные (01, 02)
- [ ] config.json, main.py, README.md для каждого
- [ ] Запустить, проверить

### Шаг 3: Семейство 2 — комбинации модулей (03–06)
- [ ] config.json (+ CSV где нужно), main.py, README.md для каждого
- [ ] Запустить, проверить

### Шаг 4: Семейство 3 — изоляция тепловых (07–10)
- [ ] config.json + CSV, main.py, README.md для каждого
- [ ] Запустить, проверить

### Шаг 5: Финализация
- [ ] `python run_all.py` — все 10 без ошибок
- [ ] Обновить vault-реестр (статус → ✅ ГОТОВО)

---

## 12. Открытые вопросы

1. **CSV дублируются** в каждой подпапке (самодостаточность примеров).
   Альтернатива: общая `_data/`. Текущее решение: дублирование (простота).

2. **FEAT-014 блокирует сценарии 01–03, 05** (Standing + Prototype).
   До FEAT-014: либо ждать, либо генерировать CSV из Standing.

3. **Сценарии 03 и 05** ($R_s = 50$, Standing) vs **04 и 06** ($R_s = 30$, Table CSV):
   разные $R_s$ затрудняют прямое сравнение. Альтернатива: сгенерировать Table CSV
   для $R_s = 50$ из Standing-корреляций. Решение: после FEAT-014.
