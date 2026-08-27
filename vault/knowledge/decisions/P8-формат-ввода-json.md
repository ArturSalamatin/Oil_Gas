---
name: P8-формат-ввода-json
description: P8 — единый JSON для всех модулей, конвертеры единиц (декораторы), CSV для PVT-таблиц, единая Grid, фабрика прототипа
metadata:
  type: project
---

# P8. Формат ввода: единый JSON

## Принципы

1. **Один JSON** для всех модулей (гидро, энергия, PVT, сетка, история). Без XLSX.
2. **PVT-таблицы** — в отдельных CSV-файлах, JSON содержит имена файлов. CSV и JSON в одной папке.
3. **Все внешние данные в SI.** Конвертация в единицы прототипа — через декораторы.
4. **Единая Grid** — один объект, передаётся по ссылке в оба модуля.

## 1. Конвертеры единиц (декораторы)

### Архитектура

Каждый модуль извне выглядит как работающий в SI. Внутренняя конвертация — ответственность декоратора.

```
         SI                     внутренние единицы
Simulator ──→ HydroUnitDecorator ──→ RadialBlackOilModel (бар, сП, мД)
Simulator ──→ EnergyUnitDecorator ──→ TridiagEnergySolver (SI → SI, коэфф. = 1)
```

### HydroUnitDecorator

Обёртка вокруг RadialBlackOilModel (уже реализована как PrototypeHydroAdapter в P1). Расширена формально как декоратор:
- Вход: state в SI (Па), dt в с, BC в SI
- Конвертация: Па → бар, м³ст/с → м³ст/сут
- Вызов: model.advance()
- Обратная конвертация: бар → Па
- Выход: HydroResult в SI

### EnergyUnitDecorator

Для текущей реализации — тождественный (SI → SI, все коэффициенты = 1). Заложен для будущего: если появится тепловой модуль во внутренних единицах — декоратор обеспечит конвертацию.

```python
class EnergyUnitDecorator(EnergySolver):
    """Декоратор единиц для теплового модуля.
    
    По умолчанию: SI → SI (тождественный). Переопределить при смене единиц.
    """
    def __init__(self, solver: EnergySolver):
        self._solver = solver
    
    def solve(self, hydro_result, state_prev, dt, T_ext):
        return self._solver.solve(hydro_result, state_prev, dt, T_ext)
```

### Полиморфизм по единицам

Декораторы реализуют тот же ABC (HydroSolver, EnergySolver), что и обёрнутые модули. Simulator работает с ABC, не зная о декораторах. При смене единиц — подменяется декоратор, не модуль.

Аналогично для PVT: PrototypePVTAdapter — декоратор единиц для BlackOilPVT (бар/сП → Па/Па·с). Для StandingFullPVT декоратор не нужен (уже SI).

## 2. PVT-таблицы в CSV

### JSON-блок для табличного PVT

```json
"pvt": {
    "model": "table",
    "oil_pvt_file": "oil_pvt.csv",
    "gas_pvt_file": "gas_pvt.csv",
    "rho_o_std": 800.0,
    "rho_g_std": 0.78
}
```

CSV и JSON — в одной папке. Factory ищет CSV относительно расположения JSON.

### Формат oil_pvt.csv

```csv
Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s
0.0,5000000,1.05,0.0032
0.0,10000000,1.04,0.0033
0.0,20000000,1.03,0.0035
10.0,7000000,1.12,0.0025
10.0,15000000,1.10,0.0027
...
```

Единицы в CSV: **SI** (Па, Па·с). Factory при создании BlackOilPVT конвертирует в бар/сП.

### Формат gas_pvt.csv

```csv
pressure_Pa,Bg,mu_g_Pa_s
1000000,0.05,0.000012
5000000,0.01,0.000014
...
```

### Формат relperm.csv

```csv
Sg,kro,krg
0.00,1.00,0.00
0.05,0.85,0.00
0.10,0.70,0.01
...
```

Безразмерные — конвертация не нужна.

## 3. TimeSchedule → Schedule прототипа

### Формат в JSON

```json
"time": {
    "start_day": 0.0,
    "dt_integration": 3600,
    "history": [
        {"dt": 86400, "control": "pressure", "p_wf": 15000000},
        {"dt": 172800, "control": "pressure", "p_wf": 12000000},
        {"dt": 604800, "control": "rate", "q_total": 0.001, "min_bhp": 5000000}
    ]
}
```

`start_day` — дата начала истории (по умолчанию 0). Единицы: сутки.

### Конвертация TimeSchedule → Schedule

Factory конвертирует при создании прототипа:

```python
def _build_prototype_schedule(time_config) -> Schedule:
    """Наш TimeSchedule → Schedule прототипа."""
    rows = []
    t_day = time_config.start_day  # абсолютное время (сут)
    
    for i, interval in enumerate(time_config.history):
        if i == 0:
            # Первая строка Schedule: time_day = start_day
            pass  # t_day уже = start_day
        
        # Конвертация управления
        if interval.control == "pressure":
            row = ScheduleRow(
                time_day=t_day,
                mode='BHP',
                bhp_bar=interval.p_wf / BAR_TO_PA
            )
        elif interval.control == "rate":
            row = ScheduleRow(
                time_day=t_day,
                mode='OIL_RATE',
                oil_rate_sm3_day=interval.q_total * DAY_TO_S,
                min_bhp_bar=(interval.min_bhp / BAR_TO_PA 
                             if interval.min_bhp is not None else None)
            )
        rows.append(row)
        t_day += interval.dt / DAY_TO_S   # dt в секундах → сутки
    
    total_time_day = t_day
    return Schedule(rows, total_time_day)
```

Schedule прототипа — более общий формат (абсолютные times, переключение контролей). Наш TimeSchedule — упрощённый (относительные dt).

## 4. Секция numerics в JSON

```json
"numerics": {
    "dt_integration": 3600,
    "dt_min": 1.0,
    "dt_max": 86400,
    "newton_max_iter": 15,
    "newton_rtol": 1e-8,
    "newton_atol": 1e-11,
    "max_active_set_iter": 12,
    "rs_switch_tol": 1e-5,
    "sg_switch_tol": 1e-9,
    "jacobian_mode": "grouped",
    "linear_solver": "sparse"
}
```

- `dt_integration` — шаг интегрирования (= dt_initial для прототипа). Дублируется из секции time.
- `dt_min`, `dt_max` — для A-retry в Adapter и для информации прототипа
- `newton_*`, `max_active_set_iter`, `*_switch_tol`, `jacobian_mode`, `linear_solver` — передаются в RadialBlackOilModel и advance()
- Если параметр не задан в JSON — берётся default из прототипа

Примечание: dt_integration из секции `time` и из `numerics` — одна и та же величина. Хранить в одном месте (в `time`), в `numerics` не дублировать.

## 5. Валидация

Валидация данных для гидро — ответственность прототипа (конструкторы BlackOilPVT, TabulatedRelPerm, RadialGrid проверяют входные данные).

Валидация данных для температуры — ответственность нашего Factory/config:
- c_p > 0
- L_degas — любой знак (физически)
- λ > 0
- T0 > 0

Общая валидация (geometry, grid) — наш Factory:
- rw > 0, re > rw, h > 0, N ≥ 1
- 0 < φ ≤ 1, k > 0

## 6. Единая Grid

### Один объект, две ссылки

```python
grid = LogRadialGrid(rw, re, h, N, k)   # один раз

hydro_adapter = PrototypeHydroAdapter(model, grid, ...)  # ссылка на grid
energy_solver = TridiagEnergySolver(grid, pvt, rock)       # та же ссылка
```

В Python все переменные — ссылки. `grid` передаётся по ссылке, не копируется. Оба модуля работают с **одним и тем же** объектом. Аналог shared_ptr в C++, но без явного управления памятью (GC).

### Grid — immutable

Grid не изменяется после создания. Модули только читают грани, центры, объёмы, проводимости. Гарантируется: конструктор вычисляет всё, после — только чтение.

### Центры ячеек

Используем формулу центра масс кольца из problem_statement.tex (eq. 12). Гидродинамический прототип сейчас использует геометрическое среднее (√). 

**Задача:** изменить формулу центров в прототипе на центр масс кольца. Эта задача зарегистрирована ниже.

### Grid прототипа → общий Grid

Прототип создаёт свой RadialGrid. Мы создаём свой LogRadialGrid. При интеграции нужна согласованность: одни и те же rw, re, N, faces, centers.

Решение: Factory создаёт **один** LogRadialGrid, а для прототипа создаёт RadialGrid с теми же параметрами. Или: прототип получает Grid через конструктор (изменить прототип — отдельная задача).

Временное решение: два объекта Grid с одинаковыми параметрами. Faces совпадают (geomspace с теми же rw, re, N). Centers расходятся (формулы разные). Задача по согласованию зарегистрирована.

## Зарегистрированные задачи

### TASK: Изменить формулу центров ячеек в прототипе

Прототип (grid.py, строка 10): `centers_m = np.sqrt(faces_m[:-1] * faces_m[1:])` — геометрическое среднее.

Нужно: заменить на центр масс кольца (problem_statement.tex eq. 12). Единая формула в обоих модулях.

Приоритет: средний (влияет на точность, не на работоспособность).

### TASK: Передача единого Grid в прототип

Сейчас прототип создаёт свой RadialGrid. Нужно: принимать Grid через конструктор RadialBlackOilModel (вместо создания внутри). Или: GridAdapter обёртывает наш Grid → RadialGrid.

Приоритет: низкий (временное решение — два Grid с одинаковыми rw, re, N — работает).

## Структура JSON (обновлённая)

```json
{
    "geometry": {
        "r_well": 0.1,
        "R_ext": 50.0,
        "h": 10.0
    },
    "grid": {
        "N": 100,
        "type": "log_radial"
    },
    "rock": {
        "porosity": 0.2,
        "permeability": 1e-13,
        "p_ref": 1e7,
        "compressibility": 0.0,
        "rho_cp_solid": 1.25e6,
        "lambda_solid": 1.5,
        "lambda_oil": 0.14,
        "lambda_gas": 0.04
    },
    "pvt": {
        "model": "table",
        "oil_pvt_file": "oil_pvt.csv",
        "gas_pvt_file": "gas_pvt.csv",
        "rho_o_std": 800.0,
        "rho_g_std": 0.78
    },
    "relperm": {
        "model": "table",
        "file": "relperm.csv"
    },
    "thermal": {
        "c_p_oil": 1880.0,
        "c_p_gas": 2800.0,
        "mu_JT_oil": 4.0e-7,
        "mu_JT_gas": -4.0e-6,
        "L_degas": 168000.0
    },
    "initial_conditions": {
        "p0": 1e7,
        "T0": 300.0,
        "Rs0": 50.0
    },
    "time": {
        "start_day": 0.0,
        "dt_integration": 3600,
        "history": [
            {"dt": 86400, "control": "pressure", "p_wf": 7e6}
        ]
    },
    "numerics": {
        "dt_min": 1.0,
        "dt_max": 86400,
        "skin": 0.0,
        "jacobian_mode": "grouped",
        "linear_solver": "sparse"
    },
    "output": {
        "log_level": "INFO",
        "format": "npz",
        "save_every": 1
    }
}
```

## Связанные заметки

- [[P1-адаптер-единицы]] — HydroUnitDecorator (PrototypeHydroAdapter)
- [[P5-pvt-архитектура]] — PVT-стратегии, PrototypePVTAdapter
- [[временная-сетка-и-история]] — TimeSchedule
- [[json-config-schema]] — предыдущая версия (обновить)
- [[модули-grid-сетка]] — LogRadialGrid
- [[hydro-prototype-анализ]] — RadialGrid прототипа
