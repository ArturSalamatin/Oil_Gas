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

Эскиз, в коде не реализован: тепловой модуль работает в SI, единицы гидродинамики переводят адаптеры прототипа (`units.py`). Если появится тепловой модуль во внутренних единицах — декоратор обеспечит конвертацию; для SI он тождественный (все коэффициенты = 1).

```python
class EnergyUnitDecorator(EnergySolver):
    """Декоратор единиц для теплового модуля.
    
    По умолчанию: SI → SI (тождественный). Переопределить при смене единиц.
    """
    def __init__(self, solver: EnergySolver):
        self._solver = solver
    
    def solve(self, hydro_result, state_prev, dt, bc, collect=None):
        # collect передаётся дальше обязательно: обёртка, его
        # потерявшая, оставит баланс энергии нулевым без ошибки
        return self._solver.solve(hydro_result, state_prev, dt, bc, collect)
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
    "dt_integration": 3600,
    "history": [
        {"dt": 86400, "control": "pressure", "p_wf": 15000000},
        {"dt": 172800, "control": "pressure", "p_wf": 12000000},
        {"dt": 604800, "control": "rate", "q_oil": 0.001, "min_bhp": 5000000}
    ]
}
```

Время расчёта отсчитывается от начала истории ($t = 0$). Поле `start_day` удалено ([[DEBT-008]]): решатель его не читал; в старом конфиге — предупреждение и пропуск (§5).

⚠️ Проектный этап: функции `_build_prototype_schedule` в коде нет — управление скважиной по интервалам задаёт `Simulator` (`WellControl` интервала, [[временная-сетка-и-история]]). `start_day` в псевдокоде ниже — поле, удалённое [[DEBT-008]].

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
    "skin": 0.0,
    "newton_max_iter": 15,
    "max_active_set_iter": 12,
    "rs_switch_tol": 1e-5,
    "sg_switch_tol": 1e-9,
    "jacobian_mode": "grouped",
    "linear_solver": "sparse",
    "max_retries": 9,
    "newton_cell_tol": 1e-8
}
```

- `max_retries` — глубина дробления шага в `Simulator` (локальное, DEBT-015): подшаг, на котором Newton не сошёлся, делится пополам, наименьший подшаг `dt_integration`/2**max_retries. Допустимо 0…20, по умолчанию 9 (dt/512). Значение — измеренный порог DEBT-007; порог немонотонен по сетке, для отдельных конфигураций нужно 10–11
  - Уточнение (DEBT-041, 2026-10-07): порог DEBT-007 снят BUG-014, порог BUG-003 (04a, $N = 80$) — BUG-016; 9 теперь запас, а не порог. Обоснование — комментарий `NumericsConfig.max_retries` (`io/config.py`); пример 03 требует не больше 4 удвоений (README 03).
- `newton_cell_tol` — порог условия сходимости Ньютона по ячейке (BUG-022): решение принимается, если кроме абсолютного критерия прототипа в каждой ячейке $\max_c |F_c|\,\Delta t/V_p \le$ порога. Положительное конечное число или `null` (выключено), по умолчанию 1e-8; передаётся прототипу (`cell_tol`). Порог не достижим ниже предела округления — доли меры вектора $|J|\,\mathrm{ulp}(z)$ (`eq:newton_cell_floor`; Ньютон встаёт на 0.1–0.4 её): предел растёт как $\Delta t$ и как $N^2/\ln^2(R_{ext}/r_w)$ (с ростом $R_{ext}$ при том же $N$ — убывает), шаг ниже предела отвергается и дробится (пример 17 при 1e-10: отказов шагов 214 против 47; при 1e-8 — лишь у $N$ = 350 с шагом 1 сут). Текст отказа печатает предел ([[DEBT-055]])
- `skin`, `jacobian_mode`, `linear_solver`, `newton_cell_tol`, `rs_switch_tol`, `sg_switch_tol` — фабрика передаёт в конструктор `RadialBlackOilModel`
- `newton_max_iter`, `max_active_set_iter` — лимиты Ньютона ступеней 1–3 `advance`: итераций на одно решение при фиксированном наборе фаз; проходов набора фаз с включением газа — проходы, где газ только снимается, не считаются, всего не больше `max_active_set_iter` + $N$ ([[BUG-028]]). Адаптер передаёт их в каждый вызов `advance` и `advance_fourth_stage` ([[DEBT-008]]). Ступень 4 (BUG-020, `_newton_switching`) их не читает: свой предел 40 итераций
- `rs_switch_tol`, `sg_switch_tol` — допуски переключения фаз: газ включается в ячейке при $R_s > R_s^{eq}(p) +$ `rs_switch_tol` (м³ст/м³ст), выключается при $S_g < -$`sg_switch_tol`. `rs_switch_tol` — ещё и допуск проверки недонасыщенного старта (BUG-017) и проверки $R_s$ примеров (`diagnostics/rs.py`, печать — `examples/rs_analytics.py`; DEBT-026, DEBT-011)
- Допуски абсолютного критерия Ньютона ($\|F\|_\infty \le$ atol + rtol·$\max(\|F_0\|_\infty, 10^{-9})$, atol = 1e-11 м³ст/с, rtol = 1e-8) — умолчания прототипа; полей `newton_atol`, `newton_rtol` в конфиге нет ([[DEBT-008]]): прототип не принимает их ни в конструкторе, ни в `advance`
- Не заданный в JSON параметр берёт умолчание `NumericsConfig` (`io/config.py`); умолчания полей, передаваемых прототипу, равны его умолчаниям (тест `test_defaults_match_prototype`)
- Удалены ([[DEBT-008]]): `dt_min`, `dt_max` (шаг — `time.dt_integration`, дробление — `max_retries`), `newton_atol`, `newton_rtol`; в старом конфиге — предупреждение и пропуск (§5)

Примечание: dt_integration из секции `time` и из `numerics` — одна и та же величина. Хранить в одном месте (в `time`), в `numerics` не дублировать.

## 5. Валидация

Кто проверяет входные данные — по коду (сверено при [[DEBT-056]]). До DEBT-056 здесь стояло «валидация данных для гидро — ответственность прототипа»; по коду это не так: скалярные поля проверяет наш config, таблицы и согласованность — наша фабрика, проверки прототипа повторяют часть наших и срабатывают позже — на них не полагаемся.

| Этап | Где | Что |
|---|---|---|
| `load_config` | `io/config.py`: `_drop_removed_keys` (до разбора секций) | удалённые поля ([[DEBT-008]]): ключ убирается, предупреждение — после `_validate` |
| | `_check_numeric_fields`, `_require_finite_number` | тип и конечность всех чисел ([[DEBT-051]]) |
| | `_expand_history`, `_validate_interval` | формы `time.history` (FEAT-018); `control`, `p_wf > 0`, `q_oil ≥ 0`, `min_bhp > 0`, неиспользуемые поля (DEBT-008) |
| | `_validate` | геометрия, сетка, порода (`compressibility` ≥ 0 — DEBT-068), тепловые параметры, начальные условия, `dt_integration`, `max_retries`, `skin`, `grid.type`, `output.log_level`, лимиты и допуски Ньютона (DEBT-008) |
| | предупреждения об удалённых полях, `_warn_large_skin`, `_warn_well_shut` (после `_validate`) | предупреждения: удалённые поля (DEBT-008); `skin` > 50; `p_wf`, `min_bhp` $\ge p_0$ (DEBT-056) |
| `from_config` | `factory.py`: `_read_numeric_csv`, `_check_pvto_branches`, `_check_gas_pvt_table`, `_check_relperm_table` | CSV-таблицы: числа, пределы, монотонность, ветви PVTO (DEBT-042, DEBT-044, DEBT-038) |
| | `_check_rs0_in_table`, `_check_undersaturated_start`; `_warn_negative_compressibility`, `_warn_initial_table_range` | начальное состояние против PVT (BUG-017); предупреждения: $c < 0$ (BUG-019), выход начального состояния за таблицы (BUG-017) |
| расчёт | `hydro/prototype_adapter.py`: `PrototypeHydroAdapter.warn_table_range` | предупреждение: выход принятого состояния за PVT- и ОФП-таблицы на каждом шаге — одна запись на категорию за расчёт, с моментом первого выхода; начальное состояние — тем же методом (`_warn_initial_table_range`), категория при $t = 0$ не повторяется; «кривая насыщения выше таблицы» — только при свободном газе $S_g > 10^{-6}$. Только табличная PVT (DEBT-027) |
| сетка GPN | `grid/log_radial.py` (`LogRadialGrid`) | повтор проверок геометрии |
| прототип | `radial_blackoil/grid.py`, `pvt.py`, `relperm.py`, `blackoil.py` | повтор геометрии; монотонность таблиц; режимы якобиана и решателя СЛАУ; $q \ge 0$. `skin` прототип не проверяет |

Проверки — только на пути JSON → `load_config` → `from_config`. Конфиг, собранный в коде, и прототип, вызванный напрямую, их не получают.

Порода — наш config (`_validate`, `io/config.py`): `porosity` ∈ (0, 1], `permeability` > 0, `compressibility` ≥ 0 ([[DEBT-068]]). $c_r = (1/\varphi)\,d\varphi/dp < 0$ — ошибка знака: загрузчик книги прототипа такое отвергает (`radial_blackoil/input_reader.py`), путь JSON его обходил. Замер на конфиге примера 18 ($c_o = 1.2\cdot10^{-9}$ 1/Па): $c_r = -4.5\cdot10^{-10}$ и $-10^{-9}$ проходили молча с дебитом на 6 и 14 % ниже; при $c_r < -c_o$ — $C_p < 0$ в недонасыщенной зоне (BUG-019) и отказ шага. Верхней границы нет: давление не выше $p_0$, при $c_r \ge 0$ $\varphi(p) \le$ `porosity`.

Тепловые параметры — наш config (`_validate`, `io/config.py`; DEBT-047, DEBT-049):
- `thermal.c_p_oil`, `thermal.c_p_gas`, `rock.rho_cp_solid` — конечные и > 0
- `rock.lambda_solid`, `rock.lambda_oil`, `rock.lambda_gas` — конечные и ≥ 0: λ = 0 отключает теплопроводность (примеры 01 и 02; до DEBT-023 — 01–09 и 04a). До DEBT-047 здесь стояло «λ > 0», но проверки не было, а примеры с λ = 0 ему противоречили
- `thermal.L_degas` — конечное, любой знак (физически); L < 0 — предупреждение в журнале, расчёт идёт. Для Стендинга L > 0: $p_b$ растёт с T, растворение газа экзотермично, дегазация поглощает теплоту; L < 0 возможен для систем, где растворимость газа растёт с T
- `thermal.mu_JT_oil`, `thermal.mu_JT_gas` — конечные, любой знак (DEBT-049). $\mu_{JT,o} > 0$ — предупреждение в журнале, расчёт идёт: $\mu_{JT} = v(\alpha T - 1)/c_p$ (`problem_statement.tex`, `eq:muJT_def`), у нефти $\alpha T \approx 0.3$ и $\mu_{JT,o} \approx -4\cdot10^{-7}$ К/Па (нагрев при дросселировании); положительный знак — вероятно $\varepsilon = -\mu_{JT}$ из литературы (Шарафутдинов и др., 2019). $\mu_{JT,g} < 0$ — без предупреждения: у газа законно выше давления инверсии
- `initial_conditions.T0` > 0

Тип и конечность всех чисел — наш config, до любых проверок диапазона ([[DEBT-051]]; `_check_numeric_fields`, `_require_finite_number` в `io/config.py`):
- каждое поле с аннотацией `float` в секциях `geometry`, `grid`, `rock`, `pvt`, `relperm`, `thermal`, `initial_conditions`, `time`, `numerics` и в интервалах истории (`dt`; `p_wf`, `q_oil`, `min_bhp` — `Optional[float]`, `null` допустим) — число, не строка, `null`, `true`/`false`, и конечное; поля выбираются по аннотациям dataclass — новое поле проверяется без правки кода;
- `duration`, `dt_out` краткой формы истории — так же, до разворачивания блока;
- значение `float` в поле другого типа (NaN в `grid.N`) — на конечность;
- литералы JSON `NaN`, `Infinity`, `-Infinity` (и `1e999`, который `json` читает как inf) отвергаются при загрузке: `<секция>.<поле> должно быть конечным числом`, `history[i].<поле> …`; строка, `null`, bool — `… должно быть числом`.

Замер до DEBT-051 (`vault/issues/debt-051/probes/red_state.out.txt`): `skin` = ±inf и `p_wf` = +inf давали расчёт без добычи, `min_bhp` = NaN снимал ограничение по забою молча (7.12 МПа при 15 МПа), NaN в 13 полях — отказ после дробления до dt/512 с советом увеличить `max_retries`.

Скважина — наш config ([[DEBT-056]]; отказ — `_validate`, предупреждения — `_warn_large_skin`, `_warn_well_shut` после `_validate`, в `io/config.py`):
- `numerics.skin` ≥ 0. $s < 0$ → `ValueError`: проводимость забойной грани прототипа $T_w = 2\pi kh/(\ln(r_1/r_w) + s)$ (`radial_blackoil/grid.py`, `well_transmissibility_m3`) на сетках проекта ($\ln(r_1/r_w) = \ln(R_{ext}/r_w)/(2N) \approx 0.01…0.16$) неположительна уже при $s \approx -0.01…-0.16$; отрицательный скин в проекте не предусмотрен (решение пользователя). Сообщение даёт обход — `geometry.r_well` = $r_w e^{-s}$ (приведённый радиус скважины: тот же установившийся однофазный приток, при разгазировании у забоя — приближённо), `skin` = 0; температура забоя тогда относится к радиусу $r_w e^{-s}$. При $r_w e^{-s} \ge R_{ext}$ сообщение говорит, что обход неприменим
- $s > 50$ — предупреждение с долей установившегося однофазного притока $\ln(R_{ext}/r_w)/(\ln(R_{ext}/r_w) + s)$ (у baseline при $s = 50$ — 11 %), расчёт идёт
- `p_wf` $\ge p_0$ (`control = "pressure"`) или `min_bhp` $\ge p_0$ при `q_oil > 0` (`control = "rate"`) в любом объекте `time.history` — предупреждение `history[i]: …`, одно на объект JSON. Оба предупреждения — после всех отказов `load_config`. При добыче давление в пласте не выше $p_0$, поэтому интервал целиком без притока (`eq:bc_pwf_shutin`). `q_oil = 0` — намеренный останов (примеры 16, 17), без предупреждения

Замер до DEBT-056 (`vault/issues/debt-056/probes/skin_range.out.txt`): $s$ = −0.5, −2 — отказ через dt/512 с советом увеличить `max_retries`; $s$ = 1e6, `p_wf` = 25 МПа, `min_bhp` = 25 МПа при $p_0$ = 20 МПа — расчёт без притока, молча.

Температура в расчёте — `Simulator._advance` после каждого подшага энергии (DEBT-047): $T \le 0$ или не конечная $T$ → `RuntimeError` с $\Delta t$ подшага, временем его конца, ячейкой, $r$ и значением. Правдоподобную, но неверную $T$ эта проверка не ловит: $c_{p,o} = 0$ в обход проверки ввода даёт $T_{\min} = 11.8$ К (`vault/issues/debt-047/probes/red_state.out.txt`).

Геометрия, сетка, порода — наш config (`_validate`); `LogRadialGrid` и `RadialGrid` прототипа повторяют:
- rw > 0, re > rw, h > 0, N ≥ 1
- 0 < φ ≤ 1, k > 0

Начальное состояние против PVT — наш Factory (`from_config`, BUG-017):
- табличная PVT: `Rs0` в диапазоне веток `oil_pvt.csv` — иначе `ValueError`
- обе модели PVT: недонасыщенный старт `Rs0 <= Rs_eq(p0)` (допуск `numerics.rs_switch_tol`, по умолчанию 1e-5 м³ст/м³ст; DEBT-008) — иначе `ValueError`
- табличная PVT: выход начального состояния за PVT- и ОФП-таблицы прототипа — предупреждение в журнале

Численные параметры — наш config (`_validate`):
- `numerics.max_retries` — целое в [0, 20] (DEBT-007)
- `numerics.newton_cell_tol` — положительное конечное число или `null` (BUG-022)
- `numerics.newton_max_iter`, `numerics.max_active_set_iter` — целые ≥ 1, bool отвергается (DEBT-008)
- `numerics.rs_switch_tol`, `numerics.sg_switch_tol` — > 0 (DEBT-008)

Литералы — наш config (`_validate`, [[DEBT-008]]): `grid.type` — только `"log_radial"` (до DEBT-008 любое значение проходило, расчёт шёл на логарифмической сетке); `output.log_level` — `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` без учёта регистра (до DEBT-008 опечатка молча давала `INFO`).

Удалённые поля ([[DEBT-008]]): `rock.p_ref`, `time.start_day`, `numerics.dt_min`, `numerics.dt_max`, `numerics.newton_rtol`, `numerics.newton_atol`, `output.format`. Решатель их не читал, поэтому старый конфиг загружается: ключ убирается до разбора секций, предупреждение с причиной — после `_validate`, как у DEBT-056 (конфиг с ошибкой в другом поле предупреждений не выдаёт). Неизвестный ключ вне этого списка — ошибка распаковки dataclass (`TypeError`). `output.save_every` ([[DEBT-013]]) — отказ: его пропуск изменил бы состав вывода.

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

Центры ячеек — среднее геометрическое граней √(r_{j-1/2}·r_{j+1/2}), как у прототипа (problem_statement.tex, `eq:cell_center`; DEBT-063). До DEBT-063 GPN брал exp⟨ln r⟩ по площади слоя.

### Grid прототипа → общий Grid

Прототип создаёт свой RadialGrid. Мы создаём свой LogRadialGrid. При интеграции нужна согласованность: одни и те же rw, re, N, faces, centers.

Решение: Factory создаёт **один** LogRadialGrid, а для прототипа создаёт RadialGrid с теми же параметрами. Или: прототип получает Grid через конструктор (изменить прототип — отдельная задача).

Временное решение: два объекта Grid с одинаковыми параметрами. Faces совпадают (geomspace с теми же rw, re, N). Centers совпадают побитово (DEBT-063, тест `TestGridsMatchPrototype`).

## Зарегистрированные задачи

### TASK: Изменить формулу центров ячеек в прототипе

**Отменена DEBT-063:** формулы согласованы в обратную сторону — GPN на √ прототипа.

Прототип (grid.py, строка 10): `centers_m = np.sqrt(faces_m[:-1] * faces_m[1:])` — геометрическое среднее.

Нужно: заменить на центр масс кольца (problem_statement.tex eq. 12). Единая формула в обоих модулях.

Приоритет: средний (влияет на точность, не на работоспособность).

### TASK: Передача единого Grid в прототип

**Не нужна (DEBT-063):** две сетки с одинаковыми гранями и центрами, совпадение проверяет тест.

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
        "dt_integration": 3600,
        "history": [
            {"dt": 86400, "control": "pressure", "p_wf": 7e6}
        ]
    },
    "numerics": {
        "skin": 0.0,
        "jacobian_mode": "grouped",
        "linear_solver": "sparse",
        "max_retries": 9,
        "newton_cell_tol": 1e-8
    },
    "output": {
        "log_level": "INFO"
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
