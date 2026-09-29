---
tags:
  - план
  - режим
date: 2026-09-29
issue: FEAT-022
github: 40
branch: feat/feat-022/daily-bhp-schedule-examples
model_level: null
status: в процессе
audit:
  date: 2026-09-29
  round: 1
  found: 4
  auto-fixed: 4
  manual-required: 0
  note: раунд 1 — предметная суть; прогоном проверены генератор конфига, тесты класса M, solve_closed при 6 МПа, форматы подписей, постоянство p_wf у 13 конфигов, голый импорт, базовый уровень 879 / 468.8 с
---

# FEAT-022: Пример 13a — ступенчатое снижение забойного давления + время в сутках на графиках

## Цель

1. Добавить в `numerical_solver/examples/` самостоятельный сценарий
   `13a_pwf_ramp_down`: конфиг примера 12 ($R_{ext} = 200$ м, $p_0 = 15.5$ МПа,
   $p_b = 15$ МПа, $N = 50$, табличные PVT и ОФП, полная термика), в котором
   забойное давление раз в сутки ступенью снижается на 0.6 МПа: 14.4 → 6.0 МПа
   за 15 сут. Запись каждые 0.5 сут (31 запись), профили — на каждую запись.
2. Ввести правило проекта: **время на всех графиках — в сутках**.
3. Стационарное (замкнутое) решение на графиках строить по $p_{wf}$
   **последнего** интервала истории, а не первого.

Ядро (гидродинамика, энергия) не меняется. Меняются: библиотечный модуль
рисования `io/output.py` (единицы), общие модули `examples/` (`example_runner`,
`closed_form`, `two_phase_analytics`, `energy_balance`), три отдельных
скрипта (единицы), тесты, README.

**Подтип:** режим (новый режим использования ГУ в примерах: $p_{wf}$ меняется
между интервалами истории) + инфраструктура (единицы времени на графиках).
Новых формул нет.

**Вне объёма:** пример 13б и флаг отключения стационарной аналитики —
[[FEAT-023]], заблокирован [[BUG-014]] (см. §0 и §10).

---

## 0. Решения пользователя

| № | Вопрос | Решение | Дата |
|---|---|---|---|
| 1 | Моменты профилей | **на каждый шаг истории**: начальное состояние и конец каждого интервала `time.history`. Шаг истории = интервал истории (0.5 сут) → 31 кривая | 2026-09-28, уточнено 2026-09-29 |
| 2 | Легенда | **не перерабатывать**: существующий механизм `ax.legend()`, без столбцов, вынесения за оси, цветовой шкалы. Качество рисунков — отдельное обсуждение позже | 2026-09-29 |
| 3 | Единицы времени | **сутки на всех графиках** — правило проекта, не только для 13a. PNG всех примеров меняются | 2026-09-29 |
| 4 | Ступени 13a | от $p_b = 15$ МПа, шаг 0.6 МПа: $p_{wf,k} = 15 - 0.6k$ МПа, $k = 1\ldots15$ | 2026-09-28 |
| 5 | Частота записи | каждые 0.5 сут: 30 интервалов по 43 200 с | 2026-09-28 |
| 6 | Стационарные кривые 13a | по $p_{wf}$ последнего интервала (6 МПа) — предел $t \to \infty$ при удержании последнего режима | 2026-09-29 |
| 7 | Разделение задачи | FEAT-022 = 13a + общие правки; 13б и флаг отключения стационарной аналитики — [[FEAT-023]] после [[BUG-014]] | 2026-09-29 |
| 8 | Связь с другими примерами | **нет** (правило проекта, решение по FEAT-021 2026-09-25): README и тесты 13a не сравнивают его ни с 12, ни с другими; конфиг 12 — только заготовка | 2026-09-25 |

**Трактовки плана (не решения пользователя; при несогласии — поправить на
аудите):**

- **Δt — не время.** В `energy_balance_convergence.py` шаг интегрирования
  подписан «Δt = 3600 с» в легенде и «Δt, с» на оси второй панели. Это
  численный параметр, а не координата времени; в сутках он нечитаем
  (360 с = 0.004167 сут). **Остаётся в секундах.** В сутки переводится только
  ось времени $t$.
- **Формат подписи момента:** `f"t = {t_сут:.4g} сут"` — 0 → «0», 43 200 с →
  «0.5», 10 800 с → «0.125», 3600 с → «0.04167», 86 400 с → «1».
- **Имя параметра** `run_example(..., all_profiles: bool = False)`; моменты
  выбирает вспомогательная функция `_profile_times(times, all_profiles)`
  (её удобно тестировать отдельно от рисования).
- **Латиница в именах:** папка и заголовки графиков — `13a` (как `04a`),
  не кириллическая «а».
- **Генератор конфига** — `vault/issues/feat-022/probes/make_13a_config.py`
  (одноразовый, рядом с пробами), а не в папке примера: у 04a генератор лежит
  в папке примера (`rewrite_history.py`), но там он переписывает уже
  существующий конфиг; здесь конфиг создаётся один раз.
- **`two_phase_analytics.py:376`** — **менять вместе с `closed_form`**
  (исправлено аудитом 2026-09-29; прежняя трактовка «не трогать» оставляла
  рассогласование). Модуль в стр. 372 вызывает `solve_closed`, который после
  шага 5 строит решение по `history[-1]`, а в стр. 376 нормирует отклонение
  давления на депрессию по `history[0]` — внутри одного отчёта «E. Замкнутое
  решение» два разных $p_{wf}$. У 03, 04, 05 (единственных пользователей)
  $p_{wf}$ постоянно, поэтому численно ничего не меняется; правка убирает
  ловушку для будущих конфигов с меняющимся $p_{wf}$ (FEAT-023). Скрипты
  отдельных примеров (`05/closed_form_convergence.py:102`,
  `05/compare_with_corey.py:124`, `01/main.py`, `02/main.py` и др.) берут
  `history[0]` у своих постоянных конфигов и **не трогаются**.

---

## 1. Предусловия

1. **FEAT-021 влит в базовую ветку.** На 2026-09-29 ветка
   `feat/feat-021/large-drainage-radius-example` (HEAD `91485a4`) **не влита**
   в `numerical_scheme/implementation`: там нет `examples/12_large_drainage_radius/`,
   а конфиг и CSV примера 12 — заготовка 13a. Вливает **пользователь**
   (`--no-ff`). Шаг 1 проверяет это и **останавливается**, если не влито.
2. **Незакоммиченные vault-файлы** (созданы на ветке feat-021 при
   `/issue` и `/plan-feature`):
   ```
    M vault/roadmap/планируемые фичи.md                     (FEAT-022, FEAT-023)
    M vault/roadmap/известные баги и технический долг.md    (BUG-014)
    M vault/00-home/index.md                                (ссылка на план)
   ?? vault/issues/feat-022/                                (issue, комментарии, probes/)
   ?? vault/plans/feat-022 daily-bhp-schedule-examples.md
   ```
   Их коммитит пользователь отдельным vault-коммитом в базу до создания ветки
   (прецедент FEAT-021: при согласии пользователя — сам `/implement`).
   Шаг 1 проверяет чистоту дерева.
3. **Базовый уровень тестов** (итог FEAT-021, 2026-09-28): **879 passed,
   ~463 с**. Перепроверено аудитом 2026-09-29 на `91485a4` (ветка FEAT-021 —
   то, что окажется в базе после вливания): **879 passed, 468.8 с**, 1
   предупреждение pytest. Перепроверить на шаге 1.

---

## 2. Физика сценария 13a

### 2.1 Расписание

| сутки $k$ | интервалы | $p_{wf}$, МПа | депрессия $p_0 - p_{wf}$, МПа |
|---|---|---|---|
| 1 | 1, 2 | 14.4 | 1.1 |
| 2 | 3, 4 | 13.8 | 1.7 |
| … | … | $15 - 0.6k$ | $0.5 + 0.6k$ |
| 14 | 27, 28 | 6.6 | 8.9 |
| 15 | 29, 30 | 6.0 | 9.5 |

Первая ступень — скачок $15.5 \to 14.4$ МПа (1.1 МПа, почти две ступени):
отсчёт от $p_b$, а не от $p_0$ (решение 4). Уже с первых суток $p_{wf} < p_b$,
газ выделяется у забоя.

### 2.2 Что происходит (замер §3)

- **Каждая ступень — новое разгазирование.** Депрессия растёт, фронт
  разгазирования уходит от скважины: центр самой дальней двухфазной ячейки
  4.8 м (0.5 сут) → 117.9 м (14.5 сут); двухфазных ячеек 26 → 47.
- **Дебит нефти** растёт от суток к суткам ($4.99\cdot10^{-4}$ → $3.157\cdot10^{-3}$
  м³ст/с в конце суток) и **спадает внутри суток**: сразу после ступени
  перепад у забоя максимален, дальше воронка депрессии расширяется. Выполняется
  на всех 15 сутках.
- **Газовый фактор выше $R_{s,0} = 30$** на всей истории (30.2 → 56.3): каждая
  ступень высвобождает новый свободный газ у скважины, он подвижен и
  добывается. GOR так же растёт от суток к суткам и спадает внутри суток.
- **Температура у забоя** убывает на каждой записи: 350 → 345.682 К за 15 сут
  (ΔT = −4.318 К). Не утверждать, что $T$ выходит на стационар
  (правило проекта).
- **Скважина ни разу не закрывается:** $p[0] > p_{wf}$ на всех 360 подшагах,
  запас $p[0] - p_{wf}$ 12 кПа (0.5 сут) … 124 кПа (15 сут). Поэтому
  [[DEBT-019]] и [[BUG-014]] к 13a не относятся: у 13a $p_{wf}$ только
  снижается.
- **Гидравлический шаг не дробится** ни на одной ступени, включая первую:
  360 подшагов по 3600 с. Поэтому 13a **не входит** в `SUBDIVIDING_EXAMPLES`.
- **Контурная ячейка однофазна:** $\min_t p_{N-1} - p_b = +426.5$ кПа,
  $S_{g,N-1} \equiv 0$.

### 2.3 Стационарное решение на графиках (решение 6)

`closed_form.solve_closed` строит решение, в котором из расчёта не берётся
ничего: компонентные потоки постоянны по $r$, газ входит через контур только
растворённым (GOR $= R_{s,0}$). Дебит — одной квадратурой:

$$
q_o = \frac{2\pi k h}{\ln(R_e/r_w)}\int_{p_{wf}}^{p_e}\frac{k_{ro}(S_g(p))}{\mu_o B_o}\,dp,
\qquad
\frac{k_{rg}}{k_{ro}}(S_g) = \bigl[R_{s,0}-R_s(p)\bigr]\frac{\mu_g B_g}{\mu_o B_o}.
$$

Сейчас нижний предел $p_{wf}$ берётся из `history[0]` (`closed_form.py:145`),
и у 13a пунктир описывал бы режим **первых** суток (14.4 МПа). После правки —
из `history[-1]`: предел $t \to \infty$ при удержании последнего режима
(6 МПа). У примеров 01–12 $p_{wf}$ постоянно на всей истории
(проверяется на шаге 5), и для них ничего не меняется.

На 15 сут 13a далёк от стационара — это свойство режима, а не погрешность:
последняя ступень сделана всего сутки назад, GOR = 54.9 при $R_{s,0} = 30$.
Поэтому:

| величина | расчёт, 15 сут | стационар при 6 МПа | расхождение |
|---|---|---|---|
| $q_o$, м³ст/с | $3.157066\cdot10^{-3}$ | $3.282724\cdot10^{-3}$ | 3.98 % |
| $\max\lvert\Delta p\rvert$ | — | — | 59.00 кПа (0.621 % депрессии 9.5 МПа) |
| $S_g^{max}$ | 0.03610 | 0.01931 | — |
| фронт $r_b$ | — | 117.58 м | — |
| замыкание при численном $p$ | — | — | $\max\lvert\Delta S_g\rvert = 1.68\cdot10^{-2}$ (90.3 %) |

Последняя строка — не дефект: замыкание подставляет GOR $= R_{s,0} = 30$, а в
расчёте GOR = 54.9, поэтому $S_g$ из замыкания ниже численной почти вдвое.
README обязан это объяснить.

### 2.4 Время в сутках (решение 3)

Перевод $t_{\text{сут}} = t\,[\text{с}] / 86400$; константа уже есть:
`gpn_multiphase_solver/units.py:19` — `S_TO_DAY = 1.0 / 86400.0`. Времена в
`SimulationHistory` и аргумент `times_to_plot` функции `plot_profiles`
**остаются в секундах** — меняется только то, что рисуется (данные по оси и
подписи). API не меняется, существующие вызовы `plot_profiles(history, grid,
[0.0, 10800.0])` в тестах работают как прежде.

---

## 3. Ожидаемый результат (замер 2026-09-29)

Воспроизводится `vault/issues/feat-022/probes/plan_numbers.py` (из
`numerical_solver/`). `sim.run` 13.6 с; 31 запись; 360 подшагов по 3600 с;
закрытий скважины 0; переходов ячеек 1 → 2 (двухфазная → однофазная) 0.

$q_o$ в м³ст/с; «фронт» — центр самой дальней ячейки с $S_g > 0$, м.

| сут | $p_{wf}$ | $q_o$ | GOR | $T(r_w)$, К | $S_g(r_w)$ | $n_{2ф}$ | фронт | $p[0]$, МПа |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 15.500* | 0 | — | 350.000 | 0.0000 | 0 | — | 15.5000 |
| 0.5 | 14.400 | 5.0914e-04 | 30.63 | 349.589 | 0.0015 | 26 | 4.8 | 14.4117 |
| 1.0 | 14.400 | 4.9917e-04 | 30.20 | 349.575 | 0.0013 | 27 | 5.6 | 14.4115 |
| 1.5 | 13.800 | 7.4916e-04 | 35.34 | 349.320 | 0.0057 | 35 | 19.0 | 13.8182 |
| 2.0 | 13.800 | 7.4531e-04 | 33.45 | 349.303 | 0.0045 | 35 | 19.0 | 13.8180 |
| 2.5 | 13.200 | 9.9288e-04 | 37.98 | 349.042 | 0.0087 | 38 | 30.0 | 13.2253 |
| 3.0 | 13.200 | 9.8069e-04 | 36.88 | 349.026 | 0.0080 | 39 | 35.0 | 13.2250 |
| 3.5 | 12.600 | 1.2229e-03 | 41.01 | 348.763 | 0.0120 | 40 | 40.7 | 12.6327 |
| 4.0 | 12.600 | 1.2060e-03 | 39.97 | 348.747 | 0.0113 | 41 | 47.4 | 12.6322 |
| 4.5 | 12.000 | 1.4396e-03 | 43.53 | 348.484 | 0.0150 | 42 | 55.1 | 12.0403 |
| 5.0 | 12.000 | 1.4221e-03 | 42.38 | 348.466 | 0.0142 | 42 | 55.1 | 12.0398 |
| 5.5 | 11.400 | 1.6455e-03 | 45.66 | 348.204 | 0.0177 | 43 | 64.2 | 11.4481 |
| 6.0 | 11.400 | 1.6281e-03 | 44.50 | 348.186 | 0.0170 | 43 | 64.2 | 11.4475 |
| 6.5 | 10.800 | 1.8414e-03 | 47.60 | 347.924 | 0.0204 | 44 | 74.7 | 10.8561 |
| 7.0 | 10.800 | 1.8242e-03 | 46.42 | 347.905 | 0.0196 | 44 | 74.7 | 10.8555 |
| 7.5 | 10.200 | 2.0292e-03 | 49.30 | 347.645 | 0.0229 | 44 | 74.7 | 10.2642 |
| 8.0 | 10.200 | 2.0120e-03 | 48.10 | 347.625 | 0.0221 | 44 | 74.7 | 10.2635 |
| 8.5 | 9.600 | 2.2084e-03 | 50.82 | 347.367 | 0.0253 | 45 | 87.0 | 9.6725 |
| 9.0 | 9.600 | 2.1929e-03 | 49.54 | 347.346 | 0.0244 | 45 | 87.0 | 9.6718 |
| 9.5 | 9.000 | 2.3823e-03 | 52.09 | 347.089 | 0.0275 | 45 | 87.0 | 9.0809 |
| 10.0 | 9.000 | 2.3667e-03 | 50.82 | 347.067 | 0.0266 | 45 | 87.0 | 9.0802 |
| 10.5 | 8.400 | 2.5488e-03 | 53.25 | 346.813 | 0.0296 | 46 | 101.3 | 8.4895 |
| 11.0 | 8.400 | 2.5341e-03 | 51.95 | 346.790 | 0.0288 | 46 | 101.3 | 8.4888 |
| 11.5 | 7.800 | 2.7110e-03 | 54.20 | 346.536 | 0.0316 | 46 | 101.3 | 7.8982 |
| 12.0 | 7.800 | 2.6973e-03 | 52.86 | 346.512 | 0.0307 | 46 | 101.3 | 7.8975 |
| 12.5 | 7.200 | 2.8684e-03 | 55.00 | 346.260 | 0.0335 | 46 | 101.3 | 7.3070 |
| 13.0 | 7.200 | 2.8551e-03 | 53.66 | 346.234 | 0.0326 | 46 | 101.3 | 7.3064 |
| 13.5 | 6.600 | 3.0208e-03 | 55.70 | 345.984 | 0.0353 | 46 | 101.3 | 6.7160 |
| 14.0 | 6.600 | 3.0080e-03 | 54.35 | 345.958 | 0.0344 | 46 | 101.3 | 6.7153 |
| 14.5 | 6.000 | 3.1689e-03 | 56.29 | 345.709 | 0.0370 | 47 | 117.9 | 6.1250 |
| 15.0 | 6.000 | 3.1571e-03 | 54.91 | 345.682 | 0.0361 | 47 | 117.9 | 6.1243 |

\* Запись 0 — начальное состояние; `WellData.p_wf` там равно $p[0]$
(`simulator.py:268`), а не заданному значению.

Забой на 15 сут: $p$ в ячейке у забоя 6.124 МПа, $R_s(r_w) = 3.373$ м³ст/м³ст,
$T(r_w) = 345.682$ К (ΔT = −4.318 К), $q_o = 3.1571\cdot10^{-3}$ м³ст/с,
$q_g = 0.17337$ м³ст/с.

Консоль `run_example` (после правки `closed_form`, §2.3):

| проверка | вывод |
|---|---|
| `report_rs` | $\max\lvert R_s^{числ} - R_s^{равн}\rvert = 6.750\cdot10^{-14}$; $R_s$ 3.3730 … 30.0000; ячеек с $p < p_b$: 47, с $S_g > 0$: 47 — совпадают: **True** |
| `report_closed` | см. таблицу §2.3 |
| `report_asymptotics` | однофазная асимптотика на 3 ячейках из 50: $\max\lvert\Delta T\rvert = 0.0567$ К; печатает общую фразу модуля «(за 3 суток релаксация не завершена …)» — известная особенность (FEAT-021, §11 его плана), не трогать |
| баланс энергии | относительная невязка $9.80\cdot10^{-12}$ (максимум по записям $1.90\cdot10^{-11}$); $E_{конд} = +1.422\cdot10^{7}$ Дж |
| контур | $\min_t p_{N-1} - p_b = +426.5$ кПа; $S_{g,N-1} = 0$ на всех записях |

Время `main.py` не замерено (будет на шаге 9): ожидается ~13.6 с расчёта +
~9 с графиков и проверок ≈ 23 с.

---

## 4. Затронутые файлы

| Файл | Строки (на `91485a4`) | Что меняется |
|---|---|---|
| `numerical_solver/gpn_multiphase_solver/io/output.py` | 18–21 (импорты), 155–158, 177–190, 203–208, 226–234 | время в сутках: легенда `plot_profiles`, оси `plot_wellbore_dynamics`, `plot_well_rate`, `plot_2d_map` |
| `numerical_solver/examples/energy_balance.py` | 73–79 (импорт), 132–162 | ось «Время, сут» |
| `numerical_solver/examples/energy_balance_convergence.py` | 93–96 (импорт), 165–167 | ось «Время, сут» (легенда Δt — без изменений) |
| `numerical_solver/examples/01_single_phase_no_jt/spatial_convergence.py` | 37–38 (импорт), 138–141 | ось «Время, сут» |
| `numerical_solver/examples/04a_high_gas_saturation/plot_profiles_50k.py` | 25, 61, 64 | легенда и заголовок в сутках |
| `numerical_solver/examples/example_runner.py` | 78–94 (сигнатура, docstring), 128–132 | `all_profiles`, `_profile_times` |
| `numerical_solver/examples/closed_form.py` | 145, 280 | `history[0]` → `history[-1]` |
| `numerical_solver/examples/two_phase_analytics.py` | 376 | `history[0]` → `history[-1]` — согласованность с `solve_closed` (стр. 372) |
| `numerical_solver/examples/04a_high_gas_saturation/grid_convergence.py` | 82–83 | комментарий: номер строки `report_closed` → описание |
| `numerical_solver/examples/13a_pwf_ramp_down/` | новые | `config.json`, `oil_pvt.csv`, `gas_pvt.csv`, `relperm.csv`, `main.py`, `README.md` |
| `vault/issues/feat-022/probes/make_13a_config.py` | новый | генератор конфига 13a |
| `numerical_solver/tests/test_output.py` | класс `TestPlots` (281–310) | тесты единиц времени |
| `numerical_solver/tests/test_examples.py` | 28–42, 51–56, после 489, конец файла (1331) | списки, `_profile_times`, класс `TestPwfRampDown` |
| `numerical_solver/tests/test_energy_matrix_examples.py` | 29, 54, 57–71 | докстринг, комментарий, `ALL_EXAMPLES` |
| `numerical_solver/examples/README.md` | 13–24, после 97, 117–126, 137–150, 223–240, 269–283, 299–320, 346–351, 405–425, 437 | 13a во всех сводках; время в сутках |

**Не меняется:** ядро (`hydro/`, `energy/`, `simulator.py`, `factory.py`),
прототип `radial_blackoil`, README других примеров,
`run_all.py` и `check_energy_balance_all.py` (находят примеры по папкам сами:
`run_all.py:27`, `check_energy_balance_all.py:65`).

---

## 5. Варианты решения

### 5.1 Где переводить время в сутки

| вариант | суть | плюсы | минусы |
|---|---|---|---|
| **А (выбран)** | внутри библиотечных функций рисования `io/output.py` и общих модулей `examples/` | одно место на функцию; все примеры получают сутки без правки `main.py`; API не меняется | меняются PNG всех примеров (это и требуется — решение 3) |
| Б | параметр `time_unit="s"｜"day"` в функциях | умолчание прежнее | правило «сутки везде» пришлось бы включать в каждом вызове; лишний параметр без второго потребителя |

### 5.2 Профили на каждую запись

| вариант | суть | плюсы | минусы |
|---|---|---|---|
| **А (выбран)** | параметр `run_example(..., all_profiles=False)` + функция `_profile_times` | умолчание прежнее (04a — 865 записей); тестируется отдельно | ещё один параметр `run_example` |
| Б | всегда все записи | проще | у 04a 865 кривых; решение 1 касается 13a |
| В | overlay-функции примера | без правки runner | overlays дорисовывают к уже нарисованным четырём моментам, а не заменяют их |

### 5.3 $p_{wf}$ стационарного решения

| вариант | суть | плюсы | минусы |
|---|---|---|---|
| **А (выбран, решение 6)** | `history[-1].p_wf` в `closed_form` | две строки; для 01–12 тождественно | — |
| Б | параметр `p_wf` в `make_overlay_*` / `report_closed` | явность | правка сигнатур трёх функций и их вызовов ради одного примера |

---

## 6. Подводные камни

| # | Проверка | Статус |
|---|---|---|
| 1 | **Размерности.** $t_{сут} = t \cdot S\_TO\_DAY$; в `plot_profiles` выбор ближайшей записи идёт по секундам (`np.argmin(np.abs(times - t_target))`), переводится только подпись | ✅ |
| 2 | **Поведение 01–12 при `history[-1]`.** Совпадает с `history[0]`, только если $p_{wf}$ постоянно. Шаг 5 проверяет это по всем 13 конфигам одной командой (аудит 2026-09-29: у всех 13 — одно значение) | ⚠️ адресовано шагом 5 |
| 2a | **Парные вычисления с тем же $p_{wf}$** (аудит): `two_phase_analytics.py:376` нормирует на депрессию по `history[0]` рядом с `solve_closed` (стр. 372). Правится в том же шаге 5 | ⚠️ адресовано шагом 5 |
| 2b | **`test_energy_balance_examples.py:48-52`** меняет `history[0].p_wf`, но предварительно усекает историю до одного интервала — смешанного расписания не возникает, `closed_form` там не вызывается | ✅ |
| 3 | **Кэш `closed_form._CACHE`** — ключ включает $p_{wf}$ (`closed_form.py:150`), поэтому смена источника $p_{wf}$ коллизий не даёт | ✅ |
| 4 | **Тесты графиков** проверяют только, что функция не падает (`test_output.py:281-310`); проверок подписей нет — сломаться нечему, новые тесты добавляются | ✅ |
| 5 | **Импорт `units` в `io/output.py`**: `from ..units import S_TO_DAY` (по образцу `from ..state import ...`, стр. 20); циклов нет — `units.py` без импортов | ✅ |
| 6 | **Импорт в `examples/`**: `energy_balance.py` и `energy_balance_convergence.py` добавляют пути в `sys.path` (стр. 73–78 и 86–91) — импорт `gpn_multiphase_solver.units` ставить **после** этого блока; пакет и так установлен (`pip install -e .`) | ✅ |
| 7 | **`test_no_extra_example_folders` и `test_coverage_matches_disk`** требуют, чтобы папка `13a_*` и оба списка `ALL_EXAMPLES` появились **в одном шаге** | ⚠️ шаг 6 |
| 8 | **`TestReadme[13a]` и `TestStructure::test_required_files[13a]`** падают до шага 9 (нет README) — ожидаемо (урок FEAT-021) | ⚠️ ожидаемо |
| 9 | **31 кривая в легенде** закроет часть поля графика — принято (решение 2), обсуждение качества рисунков отложено | ✅ принято |
| 10 | **`report_asymptotics` печатает «за 3 суток»** — общая фраза модуля (`temperature_asymptotics.py:123`); не трогать, в README 13a пояснить (как в README 12) | ✅ |
| 11 | **`test_energy_matrix_examples`** на забойной грани требует $Q_\alpha[0] \le 0$ (`:199-206`); у 13a $G_o[0] < 0$ на всех 360 подшагах (замер) | ✅ |
| 12 | **`test_oil_production`, `TestTwoPhase`** (все `ALL_EXAMPLES` / `TWO_PHASE`): $q_o[-1] > 0$, $\max S_g > 0$, $\min R_s < R_{s,0}$, $q_g[-1] > 0$ — у 13a выполнены (§3) | ✅ |
| 13 | **Производительность:** 13a считается 13.6 с; в тестах — дважды (`results` + матрица энергии), +~30–45 с к 463 с | ✅ |
| 14 | **Связь с другими задачами:** [[FEAT-023]] добавит флаг `stationary` в тот же `run_example` — не вводить его здесь (без потребителя). [[BUG-014]] к 13a не относится (§2.2) | ✅ |
| 15 | **Формулы vs код:** новых вычислений нет; единственная арифметика — умножение на `S_TO_DAY` | ✅ |

---

## 7. Шаги реализации

Все команды — из `D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver`,
если не сказано иное.

### Шаг 1: Подготовка

**Цель:** ветка от базы с примером 12, зелёный базовый уровень.

```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas
# 1. Рабочее дерево чистое. Если нет — ОСТАНОВИТЬСЯ (§1, п. 2).
git status --short
# 2. FEAT-021 в базе: должна быть папка 12. Если пусто — ОСТАНОВИТЬСЯ (§1, п. 1).
git ls-tree numerical_scheme/implementation --name-only numerical_solver/examples/ | Select-String "12_large"
# 3. Папки 13a ещё нет
git ls-tree numerical_scheme/implementation --name-only numerical_solver/examples/ | Select-String "13a"
# 4. Ветка
git checkout numerical_scheme/implementation
git checkout -b feat/feat-022/daily-bhp-schedule-examples
cd numerical_solver
.venv\Scripts\python -m pytest tests/ -q
```

**Ожидание:** 879 passed (±, если в базу пришло что-то ещё — зафиксировать
фактическое число), ~460 с.

### Шаг 2: Время в сутках — библиотека `io/output.py` (тесты вперёд)

**Цель:** все графики `io/output.py` показывают время в сутках.

**Файлы:** `numerical_solver/tests/test_output.py`,
`numerical_solver/gpn_multiphase_solver/io/output.py`

**2.1. Тесты** — в класс `TestPlots` (`test_output.py:281`), после
`test_plot_2d_map_pressure`:

```python
    def test_profile_legend_in_days(self, small_history):
        """Момент в легенде профиля — в сутках (правило проекта, FEAT-022).

        small_history: один интервал 10800 с, записи t = 0 и 10800 с.
        Ожидание: подписи «t = 0 сут» и «t = 0.125 сут» (10800/86400).
        Аргумент times_to_plot по-прежнему в секундах — API не меняется.
        Ловит: возврат подписи в секунды или перевод, сделанный дважды.
        """
        history, grid = small_history
        ax = plot_profiles(history, grid, [0.0, 10800.0], field='T')
        labels = [t.get_text() for t in ax.get_legend().get_texts()]
        assert labels == ["t = 0 сут", "t = 0.125 сут"]

    def test_time_axes_in_days(self, small_history):
        """Оси времени — в сутках: и подпись, и сами данные (FEAT-022).

        Последняя запись small_history — 10800 с = 0.125 сут. Проверяется
        не только подпись оси, но и абсцисса кривой: переименованная ось
        при данных в секундах — худший вариант ошибки.
        """
        history, grid = small_history
        ax = plot_well_rate(history)
        assert ax.get_xlabel() == "t, сут"
        assert ax.get_lines()[0].get_xdata()[-1] == pytest.approx(0.125)

        axes = plot_wellbore_dynamics(history)
        assert axes[2].get_xlabel() == "t, сут"
        assert axes[0].get_lines()[0].get_xdata()[-1] == pytest.approx(0.125)

        ax = plot_2d_map(history, grid, field='T')
        assert ax.get_ylabel() == "t, сут"
```

Прогнать — оба теста падают (подписи в секундах).

**2.2. Код** (`io/output.py`):

1. Импорт после `from ..grid.base import Grid` (стр. 21):
   ```python
   from ..units import S_TO_DAY
   ```
2. `plot_profiles`, стр. 155–158. До:
   ```python
       for t_target in times_to_plot:
           idx = int(np.argmin(np.abs(times - t_target)))
           ax.semilogx(r, arrays[field][idx, :],
                        label=f"t = {times[idx]:.0f} с")
   ```
   После:
   ```python
       for t_target in times_to_plot:
           # Ближайшая запись ищется в секундах — в них хранится история
           # и задаются times_to_plot. В сутки переводится только подпись:
           # время на всех графиках проекта — в сутках (FEAT-022).
           idx = int(np.argmin(np.abs(times - t_target)))
           ax.semilogx(r, arrays[field][idx, :],
                        label=f"t = {times[idx] * S_TO_DAY:.4g} сут")
   ```
3. `plot_wellbore_dynamics`, стр. 178: `t = arrays['times']` →
   `t = arrays['times'] * S_TO_DAY   # сутки (FEAT-022)`; стр. 190:
   `axes[2].set_xlabel('t, с')` → `axes[2].set_xlabel('t, сут')`.
4. `plot_well_rate`, стр. 204 и 208 — то же.
5. `plot_2d_map`, стр. 228 и 234 — то же (`set_ylabel('t, сут')`).
6. Докстринги функций не упоминают единиц — не менять.

**Проверка после шага:**
```powershell
.venv\Scripts\python -m pytest tests/test_output.py -v
```

**Оценка:** ~12 строк кода, ~30 строк тестов, 20 мин.

### Шаг 3: Время в сутках — общие модули и отдельные скрипты

**Цель:** оставшиеся оси времени — в сутках.

**Файлы и правки:**

1. `numerical_solver/examples/energy_balance.py`:
   - после блока `sys.path` (стр. 73–78) добавить
     `from gpn_multiphase_solver.units import S_TO_DAY  # noqa: E402`;
   - стр. 132: `t_hours = bal["t"] / 3600.0` →
     `t_days = bal["t"] * S_TO_DAY    # время на графиках — в сутках (FEAT-022)`;
   - все `t_hours` в функции `plot_energy_balance` (стр. 137–161) → `t_days`;
   - стр. 162: `"Время, ч"` → `"Время, сут"`.
2. `numerical_solver/examples/energy_balance_convergence.py`:
   - после `from convergence import run_series` (стр. 96) —
     `from gpn_multiphase_solver.units import S_TO_DAY  # noqa: E402`;
   - стр. 165: `bal["t"] / 3600.0` → `bal["t"] * S_TO_DAY`;
   - стр. 167: `"Время, ч"` → `"Время, сут"`;
   - легенда `f"Δt = {bal['value']} с ..."` (стр. 166) и ось `"Δt, с"`
     (стр. 181) — **без изменений**: Δt — шаг, а не время (трактовка §0).
3. `numerical_solver/examples/01_single_phase_no_jt/spatial_convergence.py`:
   - после `from gpn_multiphase_solver.factory import SimulatorFactory`
     (стр. 38) — `from gpn_multiphase_solver.units import S_TO_DAY`;
   - стр. 138: `t_hours = np.arange(1, len(errors) + 1) * config_base.time.dt_integration / 3600`
     → `t_days = np.arange(1, len(errors) + 1) * config_base.time.dt_integration * S_TO_DAY`;
     стр. 139 `t_hours` → `t_days`; стр. 141 `"Время, ч"` → `"Время, сут"`.
4. `numerical_solver/examples/04a_high_gas_saturation/plot_profiles_50k.py`
   (скрипт читает CSV, без импорта пакета — перевод константой в файле):
   - после `T_MAX = 50_000.0` (стр. 25) добавить
     `S_TO_DAY = 1.0 / 86400.0   # время на графиках — в сутках (FEAT-022)`;
   - стр. 61: `label=f"t = {times[i]:.0f} с"` → `label=f"t = {times[i] * S_TO_DAY:.4g} сут"`;
   - стр. 64: `(0…{T_MAX:.0f} с)` → `(0…{T_MAX * S_TO_DAY:.3g} сут)`;
   - докстринг модуля (стр. 1: «на интервале 0…50000 с») не трогать — это
     описание, а не график.

**Проверка после шага:**
```powershell
.venv\Scripts\python -m pytest tests/test_examples.py -k "energy_balance or shared" -v
Select-String -Path examples\*.py, examples\*\*.py, gpn_multiphase_solver\io\output.py -Pattern 'Время, ч', "'t, с'", '\} с"'
```
Второй вызов должен вернуть **ровно три** строки — консольную печать, не
графики (правило касается графиков, печать не трогать):
`examples\04a_high_gas_saturation\diag_n500_aset.py:53`,
`examples\example_runner.py:270` («Время расчёта»),
`examples\run_all.py:89` («Суммарное время»). До правки их 11 (замер
2026-09-29). Шаблон `\} с"` — подпись, оканчивающаяся на «с» перед
закрывающей кавычкой; новая «сут"» под него не попадает.

**Оценка:** ~15 строк, 20 мин.

### Шаг 4: `run_example` — профили на каждую запись

**Цель:** параметр `all_profiles` и функция `_profile_times`.

**Файлы:** `numerical_solver/examples/example_runner.py`,
`numerical_solver/tests/test_examples.py`

**4.1. Тест** — в `test_examples.py` после `test_pipeline_writes_output`
(стр. 489):

```python
def test_profile_times_default_and_all():
    """Моменты профильных графиков: 4 опорных по умолчанию, все — по флагу.

    31 запись (как у 13a): по умолчанию начало, 1/3, 2/3 и конец —
    индексы 0, 10, 20, 30; при all_profiles=True — все 31 момент
    (решение пользователя 2026-09-28 для 13a). Умолчание не меняется:
    у 04a 865 записей.
    """
    import sys
    sys.path.insert(0, str(EXAMPLES_DIR))
    from example_runner import _profile_times

    times = [43200.0 * n for n in range(31)]
    assert _profile_times(times, all_profiles=False) == [
        times[0], times[10], times[20], times[30]]
    assert _profile_times(times, all_profiles=True) == times
```

**4.2. Код** (`example_runner.py`):

1. Сигнатура (стр. 78–79):
   ```python
   def run_example(config_path: str | Path, output_dir: str | Path,
                   title: str, overlays: dict | None = None,
                   all_profiles: bool = False) -> tuple:
   ```
   В докстринг после абзаца про `overlays`:
   ```
       all_profiles — профили на КАЖДУЮ запись истории (начальное состояние и
       конец каждого интервала), а не на четыре опорных момента. Для
       коротких историй с меняющимся p_wf (13a: 31 запись); у 04a (865
       записей) не включать.
   ```
2. Стр. 128–132. До:
   ```python
       # ── Графики ──
       # 4 момента времени, равномерно по сохранённым шагам: начало,
       # две промежуточные точки и конец расчёта.
       times = history.times
       idx = [0, len(times) // 3, 2 * len(times) // 3, len(times) - 1]
       times_to_plot = [times[i] for i in sorted(set(idx))]
   ```
   После:
   ```python
       # ── Графики ──
       times_to_plot = _profile_times(history.times, all_profiles)
   ```
3. Новая функция перед `_plot_field` (стр. 244):
   ```python
   def _profile_times(times, all_profiles: bool) -> list:
       """Моменты профильных графиков, с: все записи или четыре опорных."""
       if all_profiles:
           # Начальное состояние и конец каждого интервала истории (FEAT-022)
           return list(times)
       # 4 момента, равномерно по сохранённым шагам: начало,
       # две промежуточные точки и конец расчёта.
       idx = [0, len(times) // 3, 2 * len(times) // 3, len(times) - 1]
       return [times[i] for i in sorted(set(idx))]
   ```

**Проверка после шага:**
```powershell
.venv\Scripts\python -m pytest tests/test_examples.py -k "profile_times or pipeline_writes" -v
```

**Оценка:** ~20 строк, 15 мин.

### Шаг 5: `closed_form` — $p_{wf}$ последнего интервала

**Цель:** стационарное решение по последнему режиму (решение 6).

**Файлы:** `numerical_solver/examples/closed_form.py`,
`numerical_solver/examples/two_phase_analytics.py`,
`numerical_solver/examples/04a_high_gas_saturation/grid_convergence.py`
(комментарий)

**Все пользователи `solve_closed` / `report_closed`** (аудит, grep): `closed_form._prepare`
→ `make_overlay_pressure`, `make_overlay_saturation`, `report_closed`
(`example_runner.py:140-141, 218`); `two_phase_analytics.py:372` (03, 04, 05);
`04_table_table/grid_convergence.py:97`; `04a_high_gas_saturation/grid_convergence.py:75`;
`05_standing_table_rp/closed_form_convergence.py:98`. Все конфиги этих
вызовов — с постоянным $p_{wf}$ (п. 1), поведение не меняется.

1. Сначала — доказательство, что для 01–12 ничего не меняется (у всех
   конфигов одно значение $p_{wf}$ на всей истории):
   ```powershell
   .venv\Scripts\python -c "import json,glob; [print(f, len({h['p_wf'] for h in json.load(open(f,encoding='utf-8'))['time']['history']})) for f in sorted(glob.glob('examples/*/config.json'))]"
   ```
   **Ожидание:** 13 строк, у каждой `1`. Если где-то не 1 — ОСТАНОВИТЬСЯ:
   правка изменит стационарные кривые этого примера.
2. Стр. 145. До: `p_wf = config.time.history[0].p_wf`. После:
   ```python
       # p_wf ПОСЛЕДНЕГО интервала: стационар — предел t -> inf при
       # удержании последнего режима. У примеров с постоянным p_wf это то
       # же значение; у 13a первый интервал — 14.4 МПа, последний — 6 МПа
       # (FEAT-022).
       p_wf = config.time.history[-1].p_wf
   ```
3. Стр. 280. До: `dep = config.initial_conditions.p0 - config.time.history[0].p_wf`.
   После:
   ```python
       # Та же депрессия, по которой построено решение (solve_closed)
       dep = config.initial_conditions.p0 - config.time.history[-1].p_wf
   ```
4. `numerical_solver/examples/two_phase_analytics.py`, стр. 376 (раздел
   «E. Замкнутое решение»; `solve_closed` вызывается в стр. 372 и после
   п. 2 берёт `history[-1]`). До:
   `dep = config.initial_conditions.p0 - config.time.history[0].p_wf`.
   После:
   ```python
       # Та же депрессия, по которой solve_closed строит решение (FEAT-022)
       dep = config.initial_conditions.p0 - config.time.history[-1].p_wf
   ```
5. `numerical_solver/examples/04a_high_gas_saturation/grid_convergence.py`,
   стр. 82–83 — комментарий ссылается на номер строки, который после п. 2–3
   сдвинется (285 → ~290). До:
   ```python
           # Нормировка на РАСЧЁТ, а не на аналитику — как в closed_form.
           # report_closed (строка 285). Разные знаменатели дали бы 1.683 % и
   ```
   После:
   ```python
           # Нормировка на РАСЧЁТ, а не на аналитику — как в closed_form.
           # report_closed (печать расхождения q_o). Разные знаменатели дали бы 1.683 % и
   ```

Тест — на шаге 7 (`test_closed_form_uses_last_interval_pwf`): без 13a
различие $[0]$ и $[-1]$ проверить не на чем.

**Проверка после шага:**
```powershell
.venv\Scripts\python -m pytest tests/test_examples.py -q
```

**Оценка:** ~8 строк, 10 мин.

### Шаг 6: Папка 13a — конфиг, данные, `main.py`, списки тестов

**Цель:** пример считается; тестовые списки согласованы с диском.

**Файлы:** `numerical_solver/examples/13a_pwf_ramp_down/`,
`vault/issues/feat-022/probes/make_13a_config.py`,
`numerical_solver/tests/test_examples.py`,
`numerical_solver/tests/test_energy_matrix_examples.py`

1. Генератор — сохранить как
   `vault/issues/feat-022/probes/make_13a_config.py`:
   ```python
   """FEAT-022: конфиг примера 13a из конфига 12 — меняется только time.history.

   30 интервалов по 43200 с (запись каждые 0.5 сут). Сутки k = 1..15 —
   интервалы 2k-1 и 2k, p_wf = 15 - 0.6·k МПа (от p_b = 15 МПа, решение
   пользователя 2026-09-28). Остальное — копия конфига 12.

   Запуск (из numerical_solver):
       .venv\\Scripts\\python ..\\vault\\issues\\feat-022\\probes\\make_13a_config.py
   """

   import json
   import shutil
   from pathlib import Path

   HERE = Path(__file__).resolve().parent
   EX = HERE.parents[3] / "numerical_solver" / "examples"
   SRC = EX / "12_large_drainage_radius"
   DST = EX / "13a_pwf_ramp_down"

   DST.mkdir(exist_ok=True)
   for f in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
       shutil.copyfile(SRC / f, DST / f)

   cfg = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
   # Целочисленная арифметика в Па: 15e6 - 0.6e6·k без ошибок округления
   cfg["time"]["history"] = [
       {"dt": 43200.0, "control": "pressure", "p_wf": float(15_000_000 - 600_000 * k)}
       for k in range(1, 16) for _ in range(2)
   ]
   (DST / "config.json").write_text(
       json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
   print("записан", DST / "config.json")
   ```
   Запустить. Проверка:
   ```powershell
   .venv\Scripts\python -c "import json; c=json.load(open('examples/13a_pwf_ramp_down/config.json',encoding='utf-8')); h=c['time']['history']; print(len(h), sum(x['dt'] for x in h)/86400, h[0]['p_wf'], h[1]['p_wf'], h[2]['p_wf'], h[-1]['p_wf'], c['time']['dt_integration'], c['geometry']['R_ext'], c['initial_conditions']['p0'], c['grid']['N'])"
   ```
   **Ожидание:** `30 15.0 14400000.0 14400000.0 13800000.0 6000000.0 3600 200.0 15500000.0 50`.
   Сверить `git diff --no-index examples/12_large_drainage_radius/config.json examples/13a_pwf_ramp_down/config.json` —
   различается **только** `time.history`.
2. `numerical_solver/examples/13a_pwf_ramp_down/main.py`:
   ```python
   """Сценарий 13a: ступенчатое снижение p_wf 14.4 -> 6 МПа за 15 сут (R_ext = 200 м)."""

   import sys
   from pathlib import Path

   # examples/ в sys.path — для импорта example_runner.
   sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

   from example_runner import run_example  # noqa: E402

   if __name__ == "__main__":
       here = Path(__file__).parent
       run_example(
           config_path=here / "config.json",
           output_dir=here / "output",
           title="13a: ступенчатое снижение забойного давления",
           # Профили на каждую запись истории — 31 кривая (решение
           # пользователя 2026-09-28): видна каждая ступень p_wf.
           all_profiles=True,
       )
   ```
3. `tests/test_examples.py`:
   - `ALL_EXAMPLES` (стр. 28–42): последней строкой `"13a_pwf_ramp_down",`;
   - `NEEDS_SG_SECTION` (стр. 51–56): добавить `"13a_pwf_ramp_down",` — ОФП
     табличная, README обязан объяснять, как увеличить $S_g$.
4. `tests/test_energy_matrix_examples.py`:
   - стр. 29: «λ_eff = 0 везде, кроме 10, 11 и 12» → «кроме 10, 11, 12 и 13a»;
   - стр. 54: «Те же 13 сценариев» → «Те же 14 сценариев»;
   - `ALL_EXAMPLES` (стр. 57–71): добавить `"13a_pwf_ramp_down",`;
   - `SUBDIVIDING_EXAMPLES` — **не добавлять**: у 13a дробления нет (§2.2).

**Проверка после шага:**
```powershell
.venv\Scripts\python -m pytest tests/test_examples.py -k "13a or no_extra" -v
.venv\Scripts\python -m pytest tests/test_energy_matrix_examples.py -k "13a or coverage" -v
```
`TestReadme[13a]` и `TestStructure::test_required_files[13a]` падают до
шага 9 — ожидаемо (§6, п. 8).

**Оценка:** ~60 строк, 20 мин.

### Шаг 7: Класс тестов `TestPwfRampDown`

**Файл:** `numerical_solver/tests/test_examples.py` — в конец файла, после
раздела `L. Сценарий 12`. Буквы A–L заняты, новый раздел — **M**.

```python
# ═══════════════════════════════════════════════════════════
# M. Сценарий 13a: ступенчатое снижение p_wf (FEAT-022)
# ═══════════════════════════════════════════════════════════

class TestPwfRampDown:
    """Сценарий 13a: конфиг 12, p_wf раз в сутки снижается на 0.6 МПа.

    Сутки k = 1..15: p_wf = 15 - 0.6·k МПа (14.4 -> 6.0), отсчёт от p_b.
    Запись каждые 0.5 сут: 30 интервалов, 31 запись; интервалы 2k-1 и 2k
    — сутки k. p_wf только снижается, поэтому p[0] > p_wf на всех
    подшагах и скважина не закрывается (к 13a не относится BUG-014).
    """

    NAME = "13a_pwf_ramp_down"

    def test_pwf_follows_schedule(self, results):
        """Заданное p_wf каждой записи совпадает с расписанием.

        Запись n = 1..30 — конец интервала n, сутки k = (n + 1) // 2.
        Ожидание: p_wf = 15 - 0.6·k МПа точно (целые Па в конфиге).
        Запись 0 — начальное состояние, там p_wf = p[0] (simulator.py:268).
        Ловит: сдвиг расписания на интервал, опечатку в конфиге.
        """
        wd = results[self.NAME]["history"].well_data
        assert len(wd) == 31
        for n in range(1, 31):
            k = (n + 1) // 2
            expected = 15.0e6 - 0.6e6 * k
            assert wd[n].p_wf == pytest.approx(expected, abs=1e-3), \
                f"запись {n}: p_wf = {wd[n].p_wf}, ожидалось {expected}"

    def test_boundary_cell_stays_single_phase(self, results):
        """Контурная ячейка однофазна на всей истории.

        Условия: p0 = 15.5 МПа при p_b = 15 МПа, 31 запись.
        Ожидание: S_g[N-1] = 0 точно, R_s[N-1] = R_s^0 с машинной точностью
        (замер: min_t p_{N-1} - p_b = +426.5 кПа).
        Ловит: опускание p0 к p_b, при котором двухфазность контурной
        ячейки задаётся сеткой, а не физикой.
        """
        r = results[self.NAME]
        for n, st in enumerate(r["history"].states):
            assert st.Sg[-1] == 0.0, \
                f"запись {n}: S_g[N-1] = {st.Sg[-1]:.3e}, контурная ячейка двухфазна"
            assert abs(st.Rs[-1] - r["Rs0"]) < 1e-10, \
                f"запись {n}: R_s[N-1] = {st.Rs[-1]} отличается от R_s^0 = {r['Rs0']}"

    def test_oil_rate_steps_up_daily_and_relaxes_within_day(self, results):
        """Дебит нефти растёт от суток к суткам и спадает внутри суток.

        Физика: каждая ступень увеличивает депрессию на 0.6 МПа, поэтому
        дебит в конце суток k+1 выше, чем в конце суток k (замер:
        4.99e-4 -> 3.157e-3 м³ст/с). Внутри суток после скачка воронка
        депрессии расширяется и дебит убывает: запись середины суток
        (2k-1) выше записи конца суток (2k). Замер: на всех 15 сутках.
        Ловит: потерю ступенчатого режима (p_wf не меняется между
        интервалами) или неверный знак отклика на скачок ГУ.
        """
        q = results[self.NAME]["q_o"]      # запись 0 — нулевой дебит
        day_end = q[2::2]                   # записи 2, 4, ..., 30
        mid_day = q[1::2]                   # записи 1, 3, ..., 29
        assert np.all(np.diff(day_end) > 0.0), f"q_o концов суток не растёт: {day_end}"
        assert np.all(mid_day > day_end), \
            f"q_o внутри суток не спадает: середины {mid_day}, концы {day_end}"

    def test_closed_form_uses_last_interval_pwf(self, results):
        """Замкнутое решение строится при p_wf последнего интервала (6 МПа).

        До FEAT-022 closed_form брал history[0].p_wf — у 13a это 14.4 МПа,
        и пунктир на графиках описывал бы режим первых суток. Теперь —
        предел t -> inf при удержании последнего режима.
        Ожидание: q_o = 3.2827e-3 м³ст/с (замер 2026-09-29: 3.282724e-3).
        Ловит: возврат к history[0].
        """
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from closed_form import solve_closed
        from gpn_multiphase_solver.factory import _create_relperm

        r = results[self.NAME]
        cfg = r["config"]
        cl = solve_closed(cfg, _pvt_of_config(cfg), _create_relperm(cfg),
                          r["grid"].r_centers)
        assert cl["q_o"] == pytest.approx(3.2827e-3, rel=1e-4)

    def test_main_plots_every_interval(self):
        """main.py 13a рисует профили на каждую запись (решение пользователя)."""
        text = (EXAMPLES_DIR / self.NAME / "main.py").read_text(encoding="utf-8")
        assert "all_profiles=True" in text
```

⚠️ `_pvt_of_config` определена в том же файле (стр. 707) — до класса M, её
можно звать. Если на шаге 7 `solve_closed` с PVT из `_pvt_of_config` даст
значение, отличное от 3.282724e-3 больше чем на $10^{-4}$ (в пробе PVT брался
у энергетического решателя) — ОСТАНОВИТЬСЯ и выяснить, а не подгонять допуск.

**Проверка после шага:**
```powershell
.venv\Scripts\python -m pytest tests/test_examples.py -k "PwfRampDown" -v
```

**Оценка:** ~100 строк, 20 мин.

### Шаг 8: Прогон `main.py` и сверка чисел

```powershell
.venv\Scripts\python examples\13a_pwf_ramp_down\main.py
```

Сверить с §3: 31 запись; финал $p(r_w) = 6.124$ МПа, $T(r_w) = 345.682$ К,
$q_o = 3.1571\cdot10^{-3}$, $q_g = 0.17337$; консоль — `report_rs`
«совпадают: True», `report_closed` 3.980 %, асимптотика 0.0567 К, баланс
$9.8\cdot10^{-12}$. Замерить время `main.py` (нужно для `examples/README.md`, шаг 10).
Открыть `output/pressure_profiles.png`, `well_rates.png`,
`energy_balance.png` — оси и легенда в сутках, 31 кривая, пунктир
стационара при 6 МПа (фронт 117.58 м).

Если числа расходятся с §3 больше, чем в последнем знаке, — ОСТАНОВИТЬСЯ:
конфиг отличается от пробы.

### Шаг 9: README примера 13a

**Файл:** `numerical_solver/examples/13a_pwf_ramp_down/README.md`

Правила:
- **без сравнений с другими примерами** (решение 8): не писать «как в 12»,
  «в отличие от 12» и т. п.; конфиг 12 можно назвать заготовкой один раз;
- обязательно для `TestReadme`: раздел «Как модифицировать»; подстрока
  «увеличить газонасыщенность»; классы `PrototypeHydroAdapter`,
  `TridiagEnergySolver`;
- числа — только из §3 и прогона шага 8;
- о температуре — только значения $T(r_w)$; не утверждать выход на стационар;
- время — в сутках.

Структура:

```markdown
# 13a — Ступенчатое снижение забойного давления

## Описание
Конфиг: R_ext = 200 м, p0 = 15.5 МПа (оно же на контуре), p_b = 15 МПа.
Забойное давление раз в сутки снижается на 0.6 МПа: 14.4 → 6.0 МПа за
15 сут. Запись каждые 0.5 сут — 31 запись. Профили рисуются на каждую запись.
Что показывает: отклик пласта на последовательность скачков граничного
условия внутри одного расчёта (§2.2 плана — своими словами).

## Комбинация модулей (B: Table + Table)
(таблица классов как в README 12: LogRadialGrid, TableFullPVT,
PrototypeRPAdapter, PrototypeHydroAdapter, TridiagEnergySolver; блок thermal)

## Ключевые параметры
(R_s0 = 30; p_b = 15; p0 = 15.5; p_wf 14.4 → 6.0; T0 = 350; r_w / R_ext =
0.1 / 200; сетка N = 50; история 30 × 43200 с; dt_integration = 3600 с —
12 подшагов на запись)

## Расписание
(таблица §2.1)

## Ожидаемое поведение
(таблица §3 — все сутки концами суток + 0.5 и 14.5; забой на 15 сут;
контурная ячейка; баланс энергии 9.8e-12, E_конд = +1.42e7 Дж;
«гидравлический шаг ни разу не дробится»)

## Что происходит на каждой ступени
(§2.2: новое разгазирование, фронт 4.8 → 117.9 м; дебит растёт от суток к
суткам и спадает внутри суток; GOR выше R_s0 и почему; скважина не
закрывается — p[0] − p_wf от 12 до 124 кПа)

## Стационарное решение на графиках
(§2.3: пунктир — предел t → ∞ при удержании 6 МПа, строится по p_wf
последнего интервала; таблица «расчёт / стационар»; почему замыкание при
численном p расходится на 90 % — GOR 54.9 ≠ R_s0 = 30)

## Графики
(время — в сутках; на профилях 31 кривая — начальное состояние и конец
каждого полусуточного интервала; фразу модуля асимптотики «(за 3 суток …)»
пояснить: общая фраза, здесь 15 сут)

## Как увеличить газонасыщенность
(те же три способа, что уместны для табличной ОФП: k_rg^max в relperm.csv;
ниже конечное p_wf — последняя ступень в config.json; больше Rs0 с оговоркой
о зазоре p0 − p_b)

## Как модифицировать
- ступени: time.history — p_wf каждого интервала; генератор
  vault/issues/feat-022/probes/make_13a_config.py;
- частота записи — число интервалов на сутки; шаг интегрирования —
  отдельный параметр dt_integration;
- рост p_wf между интервалами сейчас не считается за разумное время
  (BUG-014) — не повышать p_wf выше давления у забоя;
- профили на четыре момента — убрать all_profiles=True из main.py.

## Запуск
## Дальше
```

**Проверка после шага:**
```powershell
.venv\Scripts\python -m pytest tests/test_examples.py -k "13a" -v
```

### Шаг 10: `examples/README.md`

**Файл:** `numerical_solver/examples/README.md` (строки — на `91485a4`)

1. «С какого начать» (стр. 13–24): строка
   `| Забойное давление меняется во времени (ступенями) | **13a** |`.
2. После раздела «Большая область дренирования» (стр. 87–97) — новый раздел:
   ```markdown
   ### Переменное забойное давление

   | № | Папка | $p_{wf}$ | длительность | запись | $T(r_w)$, К |
   |---|---|---|---|---|---|
   | 13a | [13a_pwf_ramp_down](13a_pwf_ramp_down/) | 14.4 → 6 МПа, −0.6 МПа в сутки | 15 сут | 0.5 сут | 345.682 |

   Забойное давление раз в сутки снижается ступенью; $R_{ext} = 200$ м,
   $p_0 = 15.5$ МПа. Каждая ступень — новое разгазирование у скважины:
   дебит растёт от суток к суткам и спадает внутри суток, газовый фактор
   выше $R_{s,0}$ на всей истории. Профили — на каждую запись (31 кривая).
   ```
3. Таблица времени (стр. 117–126): строка `| 13a | <замер шага 8> с |`;
   итог «около 7.5 мин» → пересчитать с 13a.
4. «Что получается на выходе» (стр. 137–150): у `pressure_profiles.png` —
   «на четырёх моментах времени (у 13a — на каждой записи)»; после таблицы
   одна фраза: «Время на всех графиках — в сутках.»
5. «Замкнутое решение» (стр. 223–240): строка
   `| 13a | таблицы / таблицы | $3.1571\cdot10^{-3}$ | $3.2827\cdot10^{-3}$ | 3.98 % |`;
   после абзаца про 12 — абзац: стационар у 13a строится по $p_{wf}$
   **последнего** интервала (6 МПа); на 15 сут режим далёк от стационара
   (последняя ступень сутки назад, GOR = 54.9).
6. «Проверка $R_s$» (стр. 269–283): строка
   `| 13a | таблица | 3.37 … 30 | $6.8\cdot10^{-14}$ | да (47) |`.
7. «Баланс энергии» (стр. 299–320): «(кондукция — в 10, 11 и 12)» →
   «(кондукция — в 10, 11, 12 и 13a)»; строка
   `| **13a** | **1.5 / 0.14 / 0.04** | $9.8\cdot10^{-12}$ | $+1.42\cdot10^{7}$ |`.
8. «Асимптотика температуры» (стр. 346–351): «…у 13a — 0.06 К в трёх ячейках
   у контура».
9. «Общие параметры» (стр. 405–425): $R_e$ «(у 12 и 13a — 200)»; $p_0$
   «(у 11 — 15.05, у 12 и 13a — 15.5 МПа)»; длительность «у 13a — 15 сут,
   запись каждые 0.5 сут, 31 шаг»; $\lambda$ «кроме 10, 11, 12 и 13a»;
   «Между сценариями варьируются» — добавить «$p_{wf}$ во времени (13a)».
10. Таблица модулей (стр. 437): `run_all.py` «(~7 мин)» → новое время.

**Не добавлять** в README общего раздела сравнения 13a с 12 (решение 8).

### Шаг 11: Регрессия

```powershell
.venv\Scripts\python -m pytest tests/ -q
```

**Ожидание:** 0 failed. Число тестов = базовый уровень шага 1 + 15
(параметризованные экземпляры для 13a: 14 в `test_examples.py` — 10 по
`ALL_EXAMPLES`, 3 по `TWO_PHASE`, 1 по `NEEDS_SG_SECTION`; 1 в
`test_energy_matrix_examples.py` — `test_matrix_matches_reference`; в
`SUBDIVIDING_EXAMPLES` 13a не входит, поэтому не 16, как было у 12) + 8
новых (2 в `test_output.py`, 1 `test_profile_times_default_and_all`, 5 в
`TestPwfRampDown`). При базовом уровне 879 — **902** (подсчёт аудита по
декораторам `parametrize`, 2026-09-29). Время ≈ базовое + 30…45 с.

По желанию (≈ 8 мин): `.venv\Scripts\python examples\run_all.py` —
перегенерирует PNG всех примеров с сутками. `output/` в `.gitignore`, в
коммит не идёт.

### Шаг 12: Vault и issue

1. `vault/roadmap/планируемые фичи.md`, FEAT-022: статус ✅ ГОТОВО (дата),
   поле «Результат» (числа шага 8, число тестов и время), отклонения от плана.
2. План: `status: реализован`.
3. `vault/issues/feat-022/05-comment-done.md` → `gh issue comment 40`.
   В комментарии: 13б продолжается в FEAT-023 после BUG-014; issue #40 **не
   закрывать** без решения пользователя (он открыт на обе части).
4. `vault/00-home/index.md` — отметка ✅ у ссылки на план.
5. `vault/knowledge/decisions/модули-io-вывод.md` — эскизы `plot_wellbore_dynamics`
   и `plot_2d_map` (стр. 166, 189) подписывают время `'t, с'`. Эскизы и так
   не совпадают с кодом (`history.to_arrays()`), переписывать их не нужно:
   добавить после них датированную пометку «2026-09-29, FEAT-022: время на
   всех графиках — в сутках (`units.S_TO_DAY`); история и `times_to_plot`
   по-прежнему в секундах».

---

## 8. Тестовая стратегия

| Категория | Тест | Файл | Что ловит |
|---|---|---|---|
| Unit | `test_profile_legend_in_days` | `test_output.py` | подпись момента в секундах / двойной перевод |
| Unit | `test_time_axes_in_days` | `test_output.py` | ось переименована, а данные в секундах |
| Unit | `test_profile_times_default_and_all` | `test_examples.py` | смена умолчания (04a → 865 кривых); неполный набор при флаге |
| Предельный / согласованность | `test_closed_form_uses_last_interval_pwf` | `test_examples.py` | возврат к `history[0]`: стационар по первым суткам |
| Регрессия поведения 01–12 | команда шага 5 (у всех конфигов одно $p_{wf}$) | — | изменение стационарных кривых существующих примеров |
| Интеграционный | `test_pwf_follows_schedule` | `test_examples.py` | сдвиг расписания, опечатка конфига |
| Инвариант | `test_boundary_cell_stays_single_phase` | `test_examples.py` | сеточная двухфазность контура |
| Физика режима | `test_oil_rate_steps_up_daily_and_relaxes_within_day` | `test_examples.py` | потеря ступенчатого режима, неверный отклик на скачок ГУ |
| Инвариант | `test_energy_balance_all_examples` (существующий, 13a в `ALL_EXAMPLES`) | `test_examples.py` | невязка баланса при смене ГУ между интервалами (мотивация FEAT-019, п. 5) |
| Матрица | `test_energy_matrix_examples` (13a в `ALL_EXAMPLES`) | `test_energy_matrix_examples.py` | расхождение матрицы с постановкой на ступенчатом режиме |
| Структура | `test_main_plots_every_interval`, `TestReadme`, `TestStructure`, `TestConfigs` | `test_examples.py` | отсутствие флага, обязательных разделов, CSV |
| Сходимость | не требуется: 13a не вводит численного метода | — | — |

**Сознательно не тестируется:** монотонность числа двухфазных ячеек и
$T(r_w)$ — выполняются на замере, но физически не гарантированы (урок
FEAT-021: «число двухфазных ячеек не убывает» оказалось неверным).
`energy_balance.png` — подпись оси проверяется визуально на шаге 8
(функция возвращает невязку, а не оси).

---

## 9. Критерии завершения

- [ ] Время в сутках: `io/output.py` (4 функции), `energy_balance.py`,
      3 отдельных скрипта; grep шага 3 пуст
- [ ] `run_example(all_profiles=...)`, умолчание прежнее
- [ ] `closed_form` и `two_phase_analytics`: `history[-1]`; у 01–12 $p_{wf}$
      постоянно (шаг 5); комментарий в `04a/grid_convergence.py` без номера строки
- [ ] Папка `13a_pwf_ramp_down/` с конфигом (различие с 12 — только
      `time.history`), CSV, `main.py`, README
- [ ] Числа `main.py` совпадают с §3
- [ ] Все тесты зелёные, 0 failed
- [ ] `examples/README.md` — 13a во всех сводных таблицах, время в сутках
- [ ] Vault обновлён, комментарий в #40

---

## 10. Новые проблемы (обнаружены при планировании)

**Зарегистрированы 2026-09-29:**

1. **[[BUG-014]]** — гидродинамика не сходится при скачке $p_{wf}$ выше
   давления у забоя. Замер: 13б отказывает на первом скачке 6 → 10.75 МПа
   при штатных 512 подшагах; `max_retries = 11` проходит ценой ~130 с на
   скачок (~35 мин на 30 сут), при 10 — отказ. Причина: в режиме закрытой
   скважины Ньютон ведёт $S_g[0]$ ниже −0.05 (весь газ ячейки 0
   растворяется), все пробные точки отвергаются; ослабление границы само по
   себе не помогает. Пробы: `vault/issues/feat-022/probes/upstep_diag.py`,
   `retries_cost.py`, `plan_numbers.py`. **К 13a не относится.**
2. **[[FEAT-023]]** — пример 13б, выделен из FEAT-022 (решение 7); ждёт
   BUG-014.

**Не зарегистрированы (решить пользователю):**

3. **FEAT-019 и DEBT-019 — неточные утверждения.** FEAT-019 называет смену
   знака потока на забое ситуацией DEBT-019 (блокирующей); на деле прототип
   при $p[0] \le p_{wf}$ закрывает скважину (`blackoil.py:78-88`), и знак не
   меняется. Проверка знака $G_o[0]$ в адаптере из плана DEBT-019 при такой
   семантике недостижима. Обе записи не правились — нужна перепроверка.
4. **Постановка не описывает закрытие скважины:** `eq:bc_flux_well` без
   ограничения знака (`problem_statement.tex:1640-1654`). Для 13a не
   проявляется; перенесено в FEAT-023.

---

## 11. Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай записи FEAT-022 и FEAT-023 в `vault/roadmap/планируемые фичи.md`
   и BUG-014 в `vault/roadmap/известные баги и технический долг.md` —
   чтобы не взяться за 13б.
3. Формул в задаче нет; для контекста стационарного решения —
   `numerical_solver/examples/closed_form.py` (шапка модуля) и §2.3.
4. Выполни шаг 1 (проверки §1 — останавливающие).
5. Venv: `.venv\Scripts\python` из `numerical_solver/` напрямую.
6. Базовый уровень: `.venv\Scripts\python -m pytest tests/ -q` — записать
   число и время.
7. Шаги 2 → 12 по порядку; после каждого — указанная проверка.

---

## Связанные заметки

- [[feat-021 large-drainage-radius-example]] — план примера 12 (образец
  структуры шагов и README)
- `vault/roadmap/планируемые фичи.md` — [[FEAT-022]], [[FEAT-023]],
  [[FEAT-019]], [[FEAT-021]]
- `vault/roadmap/известные баги и технический долг.md` — [[BUG-014]],
  [[BUG-008]], [[DEBT-019]], [[DEBT-014]]
- `vault/issues/feat-022/probes/` — замеры плана
- GitHub: [#40](https://github.com/ArturSalamatin/Oil_Gas/issues/40)
