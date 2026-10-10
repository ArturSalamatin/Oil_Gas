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

Правила разбора — общие для трёх таблиц (`_read_numeric_csv`, DEBT-042). Первая строка — заголовок, имена столбцов точно как в образцах ниже, в том же порядке (пробелы вокруг имён допустимы, BOM допустим). Разделитель столбцов — запятая, десятичный разделитель — точка. В каждой непустой строке столько же полей, сколько столбцов в заголовке (запятая в конце строки — лишнее поле), каждое поле — конечное число (`nan`, `inf` — ошибка). Пустые строки и строки из пустых полей (`,,,`) пропускаются. Строк-комментариев нет: строка `# …` или с пояснением текстом — ошибка (до DEBT-042 такие строки молча пропускались). Нарушение — `ValueError` фабрики с именем файла, номером строки и столбцом.

Допустимые значения (DEBT-044, проверка при разборе, сообщение с номером строки и столбцом): $R_s \ge 0$; давление, $B_o$, $\mu_o$, $B_g$, $\mu_g$ больше нуля; $S_g$, $k_{ro}$, $k_{rg}$ — от 0 до 1 включительно. Значение проверяется в единицах файла. До DEBT-044 недопустимое значение проходило молча или роняло счёт: при $B_o < 0$ расчёт `configs/table_pvt` шёл до конца с $T = -246$ К (проба `vault/issues/debt-044/probes/red_state.py`).

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

Ветвь — все строки с одним $R_s$. В ветви не меньше двух строк: первая — насыщенная точка $p_b(R_s)$, дальше давление строго растёт по порядку строк. Давление насыщения $p_b$ строго растёт с $R_s$. Ветвей не меньше двух. Нарушение — `ValueError` фабрики с именем файла и ветвью (`_check_pvto_branches`, DEBT-038; число ветвей — DEBT-044, до него отказывал `BlackOilPVT` без имени файла). OPM допускает ветвь из одной строки (кроме последней) и достраивает её по следующей ветви с недонасыщенными строками; решатель так не делает, поэтому такая ветвь — ошибка.

### Формат gas_pvt.csv

```csv
pressure_Pa,Bg,mu_g_Pa_s
1000000,0.05,0.000012
5000000,0.01,0.000014
...
```

Не меньше двух строк, давление строго растёт по порядку строк (`_check_gas_pvt_table`, DEBT-044). Убывание $B_g$ с давлением, которого требует PVDG (OPM Flow Manual, табл. 8.127), не проверяется: рост $B_g$ — отрицательная сжимаемость газа, о ней фабрика предупреждает (BUG-019), расчёт продолжается.

### Формат relperm.csv

```csv
Sg,kro,krg
0.00,1.00,0.00
0.05,0.85,0.00
0.10,0.70,0.01
...
```

Безразмерные — конвертация не нужна.

Не меньше двух строк, $S_g$ строго растёт (`_check_relperm_table`, DEBT-044). Монотонность $k_{rg}$ (не убывает) и $k_{ro}$ (не возрастает), которой требует SGOF (OPM Flow Manual, табл. 8.165), не проверяется.

## 3. TimeSchedule → Schedule прототипа

### Формат в JSON

```json
"time": {
    "start_day": 0.0,
    "dt_integration": 3600,
    "history": [
        {"dt": 86400, "control": "pressure", "p_wf": 15000000},
        {"dt": 172800, "control": "pressure", "p_wf": 12000000},
        {"dt": 604800, "control": "rate", "q_oil": 0.001, "min_bhp": 5000000}
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
                oil_rate_sm3_day=interval.q_oil * DAY_TO_S,  # дебит нефти
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
    "linear_solver": "sparse",
    "max_retries": 9
}
```

- `dt_integration` — шаг интегрирования (= dt_initial для прототипа). Дублируется из секции time.
- `dt_min`, `dt_max` — ⚠️ объявлены в `NumericsConfig`, но **никакой модуль их не читает** (проверено grep при DEBT-007). A-retry их не использует: глубина дробления задаётся `max_retries`, а не нижней границей подшага. Учтено в DEBT-008
- `max_retries` — глубина дробления шага в `Simulator` (локальное, DEBT-015): подшаг, на котором Newton не сошёлся, делится пополам, наименьший подшаг `dt_integration`/2**max_retries. Допустимо 0…20, по умолчанию 9 (dt/512). Значение — измеренный порог DEBT-007; порог немонотонен по сетке, для отдельных конфигураций нужно 10–11
  - Уточнение (DEBT-041, 2026-10-07): порог DEBT-007 снят BUG-014, порог BUG-003 (04a, $N = 80$) — BUG-016; 9 теперь запас, а не порог. Обоснование — комментарий `NumericsConfig.max_retries` (`io/config.py`); пример 03 требует не больше 4 удвоений (README 03).
- `newton_*`, `max_active_set_iter`, `*_switch_tol`, `jacobian_mode`, `linear_solver` — передаются в RadialBlackOilModel и advance()
- Если параметр не задан в JSON — берётся default из прототипа

Примечание: dt_integration из секции `time` и из `numerics` — одна и та же величина. Хранить в одном месте (в `time`), в `numerics` не дублировать.

## 5. Валидация

Валидация данных для гидро — ответственность прототипа (конструкторы BlackOilPVT, TabulatedRelPerm, RadialGrid проверяют входные данные).

Валидация данных для температуры — ответственность нашего config (`_validate`, `io/config.py`; DEBT-047):
- `thermal.c_p_oil`, `thermal.c_p_gas`, `rock.rho_cp_solid` — конечные и > 0
- `rock.lambda_solid`, `rock.lambda_oil`, `rock.lambda_gas` — конечные и ≥ 0: λ = 0 отключает теплопроводность (примеры 01–09, 04a). До DEBT-047 здесь стояло «λ > 0», но проверки не было, а примеры с λ = 0 ему противоречили
- `thermal.L_degas` — конечное, любой знак (физически); L < 0 — предупреждение в журнале, расчёт идёт. Для Стендинга L > 0: $p_b$ растёт с T, растворение газа экзотермично, дегазация поглощает теплоту; L < 0 возможен для систем, где растворимость газа растёт с T
- `thermal.mu_JT_oil`, `thermal.mu_JT_gas` — конечные, любой знак (DEBT-049). $\mu_{JT,o} > 0$ — предупреждение в журнале, расчёт идёт: $\mu_{JT} = v(\alpha T - 1)/c_p$ (`problem_statement.tex`, `eq:muJT_def`), у нефти $\alpha T \approx 0.3$ и $\mu_{JT,o} \approx -4\cdot10^{-7}$ К/Па (нагрев при дросселировании); положительный знак — вероятно $\varepsilon = -\mu_{JT}$ из литературы (Шарафутдинов и др., 2019). $\mu_{JT,g} < 0$ — без предупреждения: у газа законно выше давления инверсии
- `initial_conditions.T0` > 0
- для девяти тепловых параметров ($c_p$, $(\rho c_p)_s$, λ — DEBT-047; $L$, $\mu_{JT}$ — DEBT-049) литералы JSON `NaN`, `Infinity`, `-Infinity` отвергаются теми же проверками, сообщение называет параметр. Прочие числовые поля конфига NaN пропускают — [[DEBT-051]]

Температура в расчёте — `Simulator._advance` после каждого подшага энергии (DEBT-047): $T \le 0$ или не конечная $T$ → `RuntimeError` с $\Delta t$ подшага, временем его конца, ячейкой, $r$ и значением. Правдоподобную, но неверную $T$ эта проверка не ловит: $c_{p,o} = 0$ в обход проверки ввода даёт $T_{\min} = 11.8$ К (`vault/issues/debt-047/probes/red_state.out.txt`).

Общая валидация (geometry, grid) — наш Factory:
- rw > 0, re > rw, h > 0, N ≥ 1
- 0 < φ ≤ 1, k > 0

Начальное состояние против PVT — наш Factory (`from_config`, BUG-017):
- табличная PVT: `Rs0` в диапазоне веток `oil_pvt.csv` — иначе `ValueError`
- обе модели PVT: недонасыщенный старт `Rs0 <= Rs_eq(p0)` (допуск 1e-5 м³ст/м³ст) — иначе `ValueError`
- табличная PVT: выход начального состояния за PVT- и ОФП-таблицы прототипа — предупреждение в журнале

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
        "mu_JT_oil": -4.0e-7,
        "mu_JT_gas": 4.0e-6,
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
        "linear_solver": "sparse",
        "max_retries": 9
    },
    "output": {
        "log_level": "INFO",
        "format": "npz"
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
