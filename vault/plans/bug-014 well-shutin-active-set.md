---
tags:
  - план
  - баг
  - гидродинамика
  - прототип
date: 2026-09-29
issue: BUG-014
github: 42
branch: fix/bug-014/well-shutin-active-set
status: реализован
implemented: 2026-09-30
audit:
  date: 2026-09-29
  round: 2
  found: 7
  auto-fixed: 7
  manual-required: 0
  note: "раунд 2 — реализуемость: код шагов 2–3 извлечён ТЕКСТОМ из плана (audit2_apply_plan_text.py) и применён к копии прототипа — все «До» находятся ровно по разу, файл компилируется, сценарии тестов 17/17, тесты адаптера/фабрики/симулятора 85 passed + 1 удаляемый; baseline перемерен на 9e43027 (904 passed, 491 с); найдены неучтённые изменения баланса энергии примера 03 и сдвиг строк README 13a. Раунд 1 (18 находок, вариант F, решения №4–6) — см. историю issue #42"
---

# BUG-014: Гидродинамика не сходится при скачке $p_{wf}$ выше давления у забоя

## Цель

Сделать так, чтобы шаг гидродинамики сходился при повышении забойного давления
выше давления в ячейке у забоя: скважина «только добыча» закрывается, давление
восстанавливается, при $p[0] > p_{wf}$ скважина снова добывает. Критерий приёмки —
расписание 13б (сутки 6 МПа ↔ сутки 10.75 МПа, 30 сут, конфиг примера 12) проходит
при штатном `numerics.max_retries = 9` примерно за минуту; результаты
существующих примеров не меняются, кроме примера 03 (§1.7).

Правка — в прототипе `radial_blackoil/blackoil.py`. **Вариант F — запасной путь**:

1. `advance` сначала решает шаг **исходным алгоритмом** без изменений (выбор ветки
   скважины по текущей итерации, граница $S_g \ge -0.05$ двухфазной ячейки в
   поиске по направлению). Сошёлся — ответ тот же, побитово.
2. Только при отказе — **запасной путь**:
   - ветка скважины «открыта / закрыта» фиксируется на всё время решения
     (Ньютон + цикл набора фаз) и проверяется после сходимости; начальная ветка —
     по состоянию на начало шага, при отказе Ньютона или несогласованности —
     другая ветка, не более двух решений (стратегия PB, §1.4);
   - нижняя граница $S_g$ снята (метод отрицательных насыщенностей, §1.3).

Физика не меняется: скважина по-прежнему «только добыча», закачки нет.
Адаптер, энергия, формулы постановки — без изменений.

**Вне объёма:** управление по дебиту с нижней границей $p_{wf}$
(`blackoil.py:56-77`) выбирает ветку тем же способом — [[FEAT-020]] (запасной
путь с отрицательными насыщенностями на него распространяется, цикл по ветке —
нет); неравномерное дробление шага в адаптере — [[DEBT-015]]; пример 13б —
[[FEAT-023]]; расхождение постановки (`eq:bc_flux_well` без ограничения знака) —
[[FEAT-023]].

---

## 0. Решения пользователя

| № | Вопрос | Решение | Дата |
|---|---|---|---|
| 1 | Можно ли править код прототипа (`HydroSolverPrototype/Prototype_1.0.3`) | **да**, «это разрешено» | 2026-09-29 |
| 2 | С чего начинать | «начнём с пункта 1» (ветка скважины во внешнем цикле) | 2026-09-29 |
| 3 | Замер: пункт 1 сам по себе 13б не разблокирует (§1.2). Как строить план | **«исследовать, потом план»** | 2026-09-29 |
| 4 | Аудит: метод N «всегда» ухудшает глубокую депрессию (§1.7). Какой вариант | **F — запасной путь** (исходный алгоритм, при отказе — ветка во внешнем цикле + без границы $S_g$) | 2026-09-29, аудит |
| 5 | Пример 03 меняется (первый шаг без дробления). README 03 и `max_retries: 10` в конфиге 03 | **обновить в рамках BUG-014**: README 03 по новым порогам, `max_retries` из конфига 03 убрать | 2026-09-29, аудит |
| 6 | `test_factory_standing_hydro.py::…::test_fails_one_below_threshold` падает после правки (сценарий DEBT-007 сходится без дробления) | **удалить**; docstring класса — с пояснением; умолчание 9 обосновано примером 04a | 2026-09-29, аудит |

---

## 1. Измерения (2026-09-29)

Пробы — `vault/issues/bug-014/probes/`, запуск из `numerical_solver/`
(`.venv\Scripts\python ..\vault\issues\bug-014\probes\<файл>.py`). Пробы —
**только локально**: исключены из git (`.gitignore`, блок BUG-014), после
реализации удаляются (§8); в git из каталога — только `t08c_softness.py`. В §1.1–1.6
прототип не менялся: правка подставлялась на экземпляре модели
(`method_n_runs_lib.install` — метод N «всегда», стратегия PB). В §1.7 — блоки
этого плана, применённые текстом к **копии** прототипа (аудит).

### 1.1 Два механизма отказа

Замеры `vault/issues/feat-022/probes/upstep_diag.py`.

1. **Ветка скважины выбирается по текущей итерации.** $q = WI\,\lambda\,\max(p[0]-p_{wf},0)$
   вычисляется в `_well_fluxes` (`blackoil.py:78-88`) при каждой оценке невязки.
   Стартовая итерация $p[0] = 6.13 < p_{wf} = 10.75$ МПа — ветка «закрыта»,
   $\partial q/\partial p[0] = 0$, линейная модель скважины не видит. При dt = 3600 с
   на этой ветке нет согласованного решения (правильный ответ — «открыта»,
   $p[0] = 10.784$ МПа).
2. **Исчезновение газа внутри Ньютона.** Давление в зоне у забоя растёт, свободный
   газ растворяется, пробные точки получают $S_g < -0.05$ и отвергаются
   `_trial_is_reasonable` (`blackoil.py:184`); цикл набора фаз
   (`blackoil.py:204-218`) переводит ячейки в однофазный режим только **после**
   сходимости — до неё не доходит.

### 1.2 Пункт 1 отдельно — недостаточно

`well_branch_outer_loop.py`, `where_4day_fails.py`, `second_upstep_reason.py`.

| Замер | Результат |
|---|---|
| одиночный скачок из состояния 1 сут (6 → 6.2 / 7 / 8 / 10.75 МПа, dt = 3600 с) | ✓ все (раньше ✗ при 6.2 МПа и выше) |
| 13б, 4 сут, `max_retries = 9` | **отказ** на втором скачке вверх (t = 3 сут, $p[0] = 6.127$ МПа) при любом дроблении |
| причина отказа на t = 3 сут | линейный поиск отвергает точки с $S_g < -0.05$ в 1–6 ячейках (1…9) — механизм 2 |
| `max_newton` 15 → 40 | без изменений: дело не в лимите итераций |
| граница $S_g$: −0.05 → −1 | первый проход сходится (12 переключений фаз), второй — отказ ($S_g < -1$ в ячейке 4) |

### 1.3 Методы для механизма 2

`phase_switch_newton.py`, `s_first_step_debug.py`, `hybrid_methods.py`,
`method_n_runs.py`. Везде — с веткой скважины во внешнем цикле.

| Метод | Суть | Результат |
|---|---|---|
| C | ограничение приращения (Appleyard): $\lvert\Delta S_g\rvert \le 0.2$, $\lvert\Delta p\rvert \le 0.3p$; фазы — после сходимости | ✗ на t = 3 сут при всех dt |
| S | переключение переменных на **каждой** итерации, полный шаг | ✓ оба скачка при всех dt; но зацикливание на первом шаге из начального состояния при dt ≤ 900 с: ячейка фронта 21 ↔ 22, $\lvert f\rvert$ 3.7e-2 ↔ 2.8 |
| F′, L, FL | S + заморозка ячейки / поиск по направлению | ✗ начальное состояние |
| **N** | **без нижней границы $S_g$ двухфазной ячейки; фазы — после сходимости (как сейчас)** | **✓ все случаи** при `max_iter = 30`; при штатных 15 — §1.5 |

Почему N корректен. При $S_g < 0$ уравнения ячейки — гладкое продолжение:
запасы $V_p(1-S_g)/B_o$, $V_p[R_{s}(1-S_g)/B_o + S_g/B_g]$ линейны по $S_g$; PVT от
$S_g$ не зависят; ОФП в прототипе — только таблицы `TabulatedRelPerm` с
`np.interp` (`relperm.py:7-8`), за краем таблицы берётся крайнее значение; фабрика
всегда строит `TabulatedRelPerm` (`factory.py:143-144, 231-235`). Цикл набора фаз
(`blackoil.py:209, 213-217`) переводит ячейку с $S_g < 0$ в однофазный режим и
решает шаг заново; итоговое решение физично ($S_g \ge 0$), отрицательна только
промежуточная итерация. Метод отрицательных насыщенностей (Abadpour, Panfilov,
*Transport in Porous Media*, 2009, 79:197–214; в `Refs/` нет, ссылка по памяти —
сверить).

### 1.4 Начальная ветка и запасная ветка

`cheap_reproducer.py`, `branch_strategy.py`. Дешёвые случаи — фикстура
прототипа `Nabor_1b` ($p_e = 200$ бар, $p_b = 180$ бар): отбор, затем скачок
на +5 / +40 / 170 / 195 бар при dt = 3600 / 300 / 60 / 7 / 1 с, 80 случаев.

| Стратегия (с методом N) | Отказов из 80 |
|---|---|
| исходный прототип | 20 |
| A — всегда «открыта», без запасной | 12, в том числе регрессии: 67 → 195 бар при 60 с исходный проходит, A — нет (ветка «открыта» = огромная закачка) |
| B — «открыта», при отказе Ньютона — «закрыта» | 0 |
| P — по старому состоянию ($p[0] \le p_{wf}$ → «закрыта»), без запасной | 0 |
| **PB — P + при отказе Ньютона другая ветка** | **0** |

PB: начальная ветка та же, что берёт исходный код на первой итерации; при
длительном останове «закрыта» сходится сразу; запасная ветка страхует оба
направления.

### 1.5 Метод N + PB «всегда» (до аудита)

`method_n_runs.py`, `branch_strategy.py`, `test_expectations.py`,
`adapter_reproducer.py`, `t08c_with_fix.py`.

| Проверка | Результат |
|---|---|
| 13б 30 сут, `max_retries = 9` | OK за 61–68 с; дробление: первый час 128 × 28.125 с (было и раньше), первый скачок 2 × 1800 с |
| одинаковые шаги (128 × 28.125 с + 23 × 3600 с), N против исходного | max\|Δp\| = 9.9e-6 Па, маска фаз совпадает |
| баланс массы шага при смене ветки (`step_global_balance`) | $\sim 10^{-16}$ от запаса |
| адаптер, фикстуры `test_prototype_adapter.py` | исходный — `RuntimeError` на любом скачке вверх при 3600 с; с правкой — `n_substeps = 1` |

T08c прототипа (скачок BHP 100 → 175 бар на 5 сут, штатный `simulate_schedule`;
исходные цифры — `t08c_softness.py`, заметка
[[прототип переживает скачок p_wf вверх, падает равномерное дробление адаптера]]).
**Вариант F даёт те же числа** (`audit_t08c_variant.py`):

| $k$, мД | строка «+1 мин» | до скачка (принято / отказов) | отказов подряд: было → стало | первый принятый шаг: было → стало |
|---|---|---|---|---|
| 1 | есть | 160 / 0 → 160 / 0 | 0 → 0 | 60 → 60 с |
| 1 | нет | 160 / 0 → 160 / 0 | 4 → **0** | 190.7 → **3051 с** |
| 100 | есть | 153 / 3 → 153 / 3 | 5 → **0** | 1.875 → **60 с** |
| 100 | нет | 153 / 3 → 153 / 3 | 9 → **1** | 2.77 → **710 с** |

Порог «$\Delta t_{\text{пред}} \propto 1/k$» из заметки — свойство исходного Ньютона;
правка его снимает. Неравномерное дробление в адаптере для BUG-014 не нужно
(остаётся темой [[DEBT-015]]).

### 1.6 Попутные наблюдения

- Первый час примера 12 дробится на 128 подшагов (13.6 с из 13.7 с на 1 сут) —
  лимит `max_newton = 15`; → [[DEBT-025]].
- Тесты прототипа в venv: 70 проходят, 10 падают — нет `xlsxwriter`
  (`test_cli_workflow.py`, `test_output_contract.py`, `test_runner_failure.py`);
  упавший `test_cli_workflow` оставляет `Prototype_1.0.3/OUTPUT/short_run/` —
  удалять после прогона; → [[DEBT-024]].
- `PACKAGE_MANIFEST_SHA256.txt:20` уже сейчас не совпадает с файлом
  (`2d929db1…` против `7868c2e5…`; вероятно, перевод строк при checkout).
  Манифест не обновлять — изменения фиксируются в CHANGELOG (шаг 5).

### 1.7 Аудит: регрессия N «всегда» и вариант F

Блоки «До/После» применены текстом к копии прототипа
(`audit_apply_plan.py`, `audit_variant_f.py`), сценарии тестов —
`audit_check_scenarios.py` (N) и `audit_check_f.py` (F), примеры —
`audit_examples_run.py`, пороги — `retries_threshold_tables.py` и
`audit_variant_f.py check`, полный набор — `audit_preimport.py`. Копии прототипа
(`_audit_copy/`) и прогоны примеров (`_audit_examples/`) после аудита удалены;
`audit_apply_plan.py` и `audit_variant_f.py build` создают копии заново.

**Регрессия N «всегда»:** пример 03, $N = 150$, минимальный `max_retries`:

| $p_{wf}$, МПа | 8…5 | 4 | 2 | 0.5 |
|---|---|---|---|---|
| исходный (README 03) | 9–10 | 10 | **9** | **9** |
| N «всегда» | 0 | 1 | **12** | **11** |
| **F** | 0 | 1 | **9** | **9** |

При штатном лимите 9 метод N «всегда» уронил бы глубокие депрессии, которые
исходный код проходит: граница −0.05 служит страховкой при массовом появлении газа.
F по построению не хуже исходного алгоритма.

| Проверка (на копии) | N «всегда» | **F** |
|---|---|---|
| сценарии тестов шага 1 | 17/17 | **17/17** (редакция под F) |
| дешёвая матрица (80) / состояния 13б (32) | 0 / 1 | **0 / 1** (запасной путь — в 20 случаях из 80) |
| 13б 30 сут | OK, 67.8 с | **OK, 66.5 с** |
| 14 примеров против исходного | 13 — до допуска Ньютона (≤ 7.4e-6 Па) | **13 — побитово** (Δ = 0) |
| пример 03 | 512 → 0 подшагов | **512 → 0 подшагов**, \|ΔT_wf\| 0.24 К на 1 ч, 0.075 К на 2 ч, 4.3e-5 К на 72 ч; $T_{wf}$ в конце 352.7680 К в обоих; время 14.5 → 1.2 с |
| полный набор `numerical_solver/tests` | 902 passed, 2 failed | **903 passed, 1 failed** — `test_fails_one_below_threshold` (удаляется, решение 6) |
| таблица README 04 | — | совпадает с записанной: $N = 50$ — (0, 5, 0, 0, 1, 0, 0, 3, 1, 4); $N$ = 100 / 150 — 5 / 10; $N = 200$ — > 10 |

Второй отказ у N — `test_energy_balance_all_examples` (пример 10, невязка
2.1e-10 при пороге 1e-10) — был и на исходном прототипе (1.9e-10): рабочее
дерево тогда содержало незакоммиченные правки знака $\mu_{JT}$ параллельной
сессии без новой нормировки невязки. К прогону F нормировку уже поменяли
(закоммичено как `4129d07` «невязка баланса энергии нормируется на сумму модулей
членов»), и тест прошёл. К BUG-014 не относится.

**Пример 03** — первый шаг (20 → 8 МПа, Standing) раньше дробился на 512
подшагов; [[DEBT-007]] объяснял это нелинейностью $B_g$. С запасным путём шаг
сходится при dt = 3600 с — значит, ограничивала и граница −0.05; объяснение
DEBT-007 неполное (шаг 7).

---

## 2. Анализ

### 2.1 Воспроизведение

Теста на скачок $p_{wf}$ вверх в наборе нет. Воспроизводители — шаг 1:

- прототип, `Nabor_1b`, 12 ячеек: отбор 12 × 300 с при 100 бар ($p[0] = 111.67$
  бар, $S_g[0] = 0.0672$, 5 двухфазных), затем `advance` при 150 и 195 бар,
  dt = 3600 с — **исходный: не сходится**;
- адаптер, фикстуры `test_prototype_adapter.py` (N = 20): отбор 6 × 3600 с при
  80 бар ($p[0] = 84.12$ бар, 11 двухфазных), затем `solve` при 114 бар, 3600 с —
  **исходный: `RuntimeError`**.

### 2.2 Цепочка

`Simulator` → `PrototypeHydroAdapter.solve` (`prototype_adapter.py:49-134`) →
`RadialBlackOilModel.advance` (`blackoil.py:202-219`, цикл набора фаз) →
`_newton_fixed_active_set` (`:186-201`, Ньютон + поиск по направлению) →
`residual` → `physical_residual` → `net_component_outflow` →
`face_component_fluxes_sm3s` → `_well_fluxes` (`:52-90`).

1. Скачок $p_{wf}$ выше $p[0]$ → `_well_fluxes` на первой итерации выбирает
   «закрыта» (механизм 1) → Ньютон ищет решение без отбора, которого при длинном
   шаге нет.
2. Давление у забоя растёт → газ растворяется → пробные точки с $S_g < -0.05$
   отвергаются (механизм 2) → `converged = False`.
3. Адаптер дробит интервал на $2^k$ равных подшагов (до 512); при 100 мД порог —
   ~1 с → `RuntimeError` (`prototype_adapter.py:128-134`).

### 2.3 Целевое состояние

- `advance` при сходимости исходного алгоритма возвращает **побитово** прежний
  ответ; отчёт дополнительно сообщает ветку (`well_branch`, для управления по
  давлению — по принятому состоянию) и `fallback = False`.
- При отказе исходного алгоритма — запасной путь: управление по давлению —
  согласованный ответ («открыта» → $p[0] \ge p_{wf}$, $q \ge 0$; «закрыта» →
  $p[0] \le p_{wf}$, $q = 0$); управление по дебиту — повтор без границы $S_g$.
  `fallback = True`, `well_switches` — число смен ветки.
- Вне `advance` (`well_rates`, `face_component_fluxes_sm3s` из адаптера и
  `simulation.py`) — прежний выбор ветки по $p[0]$; на согласованном состоянии он
  совпадает с принятой веткой. `_well_branch` вне `advance` — `None`,
  `_sg_lower_bound` — −0.05, в том числе после исключения.
- Примеры: 13 — побитово прежние; пример 03 — без дробления первого шага (§1.7).
- Зелёные: новые тесты шага 1; все существующие, кроме удаляемого
  `test_fails_one_below_threshold`; тесты прототипа — 70 (10 известных отказов
  `xlsxwriter` — те же).

### 2.4 Варианты

| Вариант | Суть | Плюсы | Минусы / риски |
|---|---|---|---|
| **F — запасной путь** (выбран, решение 4) | исходный `advance` без изменений; при отказе — ветка во внешнем цикле (PB) + без границы $S_g$ | где исходный сходился — побитово то же; нигде не хуже исходного (пороги 03 при 2 / 0.5 МПа — 9, как было); 13б ~66 с; T08c — порог снят | лишняя неудачная попытка исходным алгоритмом на трудных шагах; два пути в `advance` |
| N «всегда» (план до аудита) | ветка во внешнем цикле + без границы на каждом шаге | проще код | регрессия при глубокой депрессии (пороги 12 / 11 вместо 9, §1.7); не побитово на 13 примерах |
| 1 без N | только ветка | проще | 13б падает на втором скачке (§1.2) |
| 1 + S | переключение переменных на каждой итерации | 13б 29 с | зацикливание на фронте (§1.3); новый Ньютон |
| 1 + C | ограничение приращения | стандарт OPM Flow | не работает здесь (§1.3) |
| 3 | неравномерное дробление в адаптере | прототип не трогается | лечит цену, не причину; меняет контракт `HydroResult.n_substeps` ([[BUG-010]]) |
| NCP | условие дополнительности скважины гладкой функцией (Фишера–Бурмейстера) прямо в невязке, BHP — неизвестное | без внешнего цикла по ветке | не проверялся; новое неизвестное и строка якобиана; механизм 2 не устраняет |

### 2.5 Выбор

**F** (решение 4): закрывает оба механизма там, где исходный алгоритм
отказывает, и не трогает шаги, где он сходится. Порядок реализации: шаг 2 —
атрибуты и поля без изменения поведения, шаг 3 — `advance` с запасным путём.

### 2.6 Подводные камни

| Пункт | Статус | Комментарий |
|---|---|---|
| Кто вызывает `advance` | ✅ | адаптер (`prototype_adapter.py:89`), `simulation.py:81`, тесты прототипа, `examples/04a_high_gas_saturation/diag_n_threshold.py:66`, пробы; сигнатура `advance(state_old, dt_s, max_active_iter=12, max_newton=15)` не меняется |
| Кто вызывает `_well_fluxes` вне `advance` | ✅ | `face_component_fluxes_sm3s` из адаптера (`prototype_adapter.py:147`), `simulation.py:91`, `well_rates`; при `_well_branch = None` — прежний выбор по $p[0]$ |
| Восстановление атрибутов | ⚠️ | исключение в исходном вызове — атрибуты не менялись; в запасном пути — `try/finally` восстанавливает `_sg_lower_bound = -0.05`, `_well_branch = None`. Тесты 6a, 6b |
| `_newton_fixed_active_set` из диагностик 04a (`diag_n500_aset.py`, `diag_n_threshold.py`) | ✅ | вне `advance` атрибуты по умолчанию — поведение прежнее |
| `BlackOilNewtonReport` — новые поля | ✅ | с умолчаниями, в конце dataclass; позиционный конструктор `blackoil.py:219` и `runner.py:32, 90-91`, `test_failure_semantics.py:10` не затронуты |
| Отрицательная $S_g$ в свойствах | ✅ | только в запасном пути; `TabulatedRelPerm` — `np.interp`; PVT и `_pressure_fd_step` от $S_g$ не зависят |
| Граничные случаи | ✅ | $p[0]_{old} = p_{wf}$ → старт «закрыта»; «открыта» с $p[0] = p_{wf}$ → $q = 0$, согласована |
| Зацикливание ветки | ✅ | не более двух решений в запасном пути (`tried`); тест 12c |
| Производительность | ✅ | на шагах, где исходный сходится, — ни одного лишнего действия; на трудных — неудачная попытка + запасной путь. Примеры: время то же (§1.7), 03 — 14.5 → 1.2 с |
| Обратная совместимость | ✅ | 13 примеров побитово; пример 03 меняется (решение 5, шаг 7); тест `test_fails_one_below_threshold` удаляется (решение 6) |
| Существующий тест, закрепляющий старое поведение | ⚠️ | `tests/test_factory_standing_hydro.py:126-138` — шаг 4. `test_converges_at_default_limit` (`:107-124`) с правкой проходит ($p[0] = 6126105.6$ Па) |
| Устаревающая документация | ⚠️ | README 03 (`:81`, баланс энергии `:278-283` и `:299-306`, `:360`, `:401-425`), `examples/README.md` (`:139` время 03, `:339` невязка баланса 03), README 13a (`:211-213`), DEBT-007 (первопричина), `vault/knowledge/decisions/hydro-prototype-анализ.md:87-89` — шаг 7 |
| Параллельные пути: баланс энергии | ⚠️ | невязка баланса 03 за весь расчёт зависит от числа шагов: 5.499e-12 → 4.176e-14 (абс. 0.263 → 0.002 Дж), $\Delta E$ — сдвиг 7e-5 отн. (`audit2_ex03_balance.py`). Тесты баланса проверяют только верхний порог — не ломаются (полный набор на копии F зелёный) |
| Управление по дебиту | ✅ | запасной путь — повтор без границы $S_g$, без цикла ветки; тест 12f |
| [[FEAT-020]] (параллельно) | ⚠️ | его план не меняет `_well_fluxes`, $p_{wf}$ берёт из `well_rates(new_proto)` — совместимо. Ссылки его плана на `blackoil.py` сдвинутся. Кто вливается вторым — перебазирует |
| Незакоммиченные правки параллельной сессии | ⚠️ | на момент аудита в рабочем дереве — правки знака $\mu_{JT}$ в конфигах и README примеров 02–13a (в том числе `03/config.json`, `03/README.md`, которые правит шаг 7), `tests/test_examples.py`, `tests/test_config.py`. Шаг 0: начинать только с чистого дерева |
| Импорт прототипа вне pytest | ⚠️ | `python -c "import radial_blackoil"` из `numerical_solver/` — `ModuleNotFoundError` (проверено); `tests/conftest.py:9-13` подключает прототип только для pytest. Скрипты шагов 0, 6, 7 добавляют `Prototype_1.0.3` в `sys.path` сами (все пробы так делают) |
| Имя пакета `tests` | ⚠️ | у проекта `numerical_solver/tests/__init__.py`, у прототипа — свой пакет `tests` (`helpers.py`). В тестах проекта модель `Nabor_1b` строить напрямую (шаг 1) |
| Язык комментариев | ✅ | в `blackoil.py` — английский (как во всём файле); ссылка на BUG-014 |
| Манифест | ✅ | не обновлять (§1.6) |

### 2.7 Новые проблемы (зарегистрированы при планировании)

- [[DEBT-024]] — 10 тестов прототипа падают без `xlsxwriter`.
- [[DEBT-025]] — первый час примера 12 дробится на 128 подшагов (лимит 15 итераций).

### 2.8 Затронутые файлы

| Файл | Шаг | Что |
|---|---|---|
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` | 2, 3, 5 | поля отчёта `:15-21`; `__init__` `:36`; `_well_fluxes` `:78-88`; `_trial_is_reasonable` `:184`; `advance` → `_advance_phases` + новый `advance` `:202-219`; docstring модуля `:1-6` |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` | 5 | раздел «Local changes — GPN project (BUG-014)» |
| `numerical_solver/tests/test_prototype_well_branch.py` | 1 | новый: тесты 1–9, 12a–f |
| `numerical_solver/tests/test_prototype_adapter.py` | 1 | новый класс `TestAdapterPwfUpStep`: тесты 10, 11 |
| `numerical_solver/tests/test_factory_standing_hydro.py` | 4 | удалить `test_fails_one_below_threshold` (`:126-138`), переписать docstring класса (`:83-94`) |
| `numerical_solver/examples/03_standing_corey/config.json` | 7 | убрать `"max_retries": 10` (`:415`) |
| `numerical_solver/examples/03_standing_corey/README.md` | 7 | `:81`, `:278-283` и `:299-306` (баланс энергии), `:360`, раздел `:401-425` |
| `numerical_solver/examples/README.md` | 7 | `:139` — время примера 03; `:339` — невязка баланса 03 |
| `numerical_solver/examples/13a_pwf_ramp_down/README.md` | 7 | `:211-213` — пункт про рост $p_{wf}$ |
| `vault/issues/bug-014/probes/examples_regression.py` | 0, 6 | сравнение 14 примеров до/после (есть, написан при аудите) |
| `vault/issues/bug-014/probes/retries_threshold_tables.py` | 7 | пороги для таблиц README 03 / 04 (есть) |
| `vault/issues/bug-014/probes/verify_fix.py` | 6 | новый: скачки, дешёвая матрица, 13б 30 сут |
| `vault/roadmap/известные баги и технический долг.md` (BUG-014, DEBT-007), `vault/roadmap/планируемые фичи.md` (FEAT-023), `vault/knowledge/numerics/<новая заметка>.md`, `vault/knowledge/debugging/прототип переживает скачок p_wf вверх, падает равномерное дробление адаптера.md`, `vault/knowledge/decisions/hydro-prototype-анализ.md`, `vault/00-home/index.md`, `vault/issues/bug-014/05-comment-done.md` | 7 | статус, поправка DEBT-007, блокировка FEAT-023, итоговая заметка, строка-итог, описание прототипа, индекс, комментарий |

Не меняются: `gpn_multiphase_solver/**`, конфиги кроме 03, `problem_statement.tex`,
`PACKAGE_MANIFEST_SHA256.txt`.

---

## 3. Шаги

### Шаг 0: Подготовка

**Цель:** чистая база, ветка, исходный уровень, эталон примеров.

1. **Предусловие — чистое дерево.** `git status --short numerical_solver` —
   пусто. В раунде 1 аудита там были незакоммиченные правки параллельной сессии
   (знак $\mu_{JT}$, нормировка невязки); к раунду 2 они закоммичены
   (`4129d07`…`9e43027`) и дерево чистое. Если снова не чисто — ветка унесёт
   чужие правки с собой, а шаг 7 правит `03/config.json` и `03/README.md`: стоп,
   спросить пользователя.
2. `git checkout numerical_scheme/implementation`;
   `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`
   (должен быть); `git checkout -b fix/bug-014/well-shutin-active-set`.
3. Исходный уровень (из `numerical_solver/`): `.venv\Scripts\python -m pytest tests -q`.
   Замер раунда 2 аудита на `9e43027`: **904 passed, 0 failed, 491 с**. Если база
   ушла вперёд — записать фактическое (число, время, отказы) и сравнивать с ним.
4. Тесты прототипа (из `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/`):
   `..\..\.venv\Scripts\python -m pytest tests -q -p no:cacheprovider` →
   70 passed, 10 failed (`xlsxwriter`, [[DEBT-024]]). Удалить `OUTPUT/short_run/`
   (`OUTPUT/README.txt` не трогать).
5. Воспроизвести: `.venv\Scripts\python ..\vault\issues\bug-014\probes\adapter_reproducer.py`
   — строки `правка=False` — «ОТКАЗ», `правка=True` — `n_sub=1`.
6. Эталон 14 примеров **до правки**:
   `.venv\Scripts\python ..\vault\issues\bug-014\probes\examples_regression.py run before`
   (~2.5 мин; `probes/regression_runs/before/`). Скрипт: список примеров — как
   `tests/test_examples.py:28-43`; по записям `p, Sg, Rs, T, regime`, из
   `WellData` — `q_o_std, q_g_std, T_wf` (`state.py:80-90`); число вызовов энергии
   с `dt < dt_integration`; прототип подключает сам. Это разовая проверка, **не
   тест и не часть примеров** (примеры не сравниваются между собой и с
   контрольными прогонами). В выводе: 03 — 512 мелких подшагов, 04a — 512,
   12 — 128, 11 — 16, 10 — 2, остальные — 0.

**Оценка:** ~20 мин (прогоны).

---

### Шаг 1: Тесты-воспроизводители (красные)

**Цель:** зафиксировать ожидаемое поведение до правки кода.
**Файлы:** `numerical_solver/tests/test_prototype_well_branch.py` (новый),
`numerical_solver/tests/test_prototype_adapter.py` (новый класс в конце).

**Контекст.** Пакет `tests` проекта имеет `__init__.py` — `tests.helpers`
прототипа импортировать нельзя. Модель `Nabor_1b` строится напрямую, как в
`Prototype_1.0.3/tests/helpers.py:11-17`: `load_input(PROTO_ROOT / "tests" /
"fixtures" / "Nabor_1b.xlsx")` (свой читатель xlsx, `openpyxl` не нужен),
`RadialGrid(rw, re, h, n, k)`, `CompressibleRock(...)`,
`RadialBlackOilModel(..., skin=..., linear_solver="sparse")`,
`BlackOilState.undersaturated(n, p0, Rs0)`; `PROTO_ROOT = Path(__file__).parent.parent
/ "HydroSolverPrototype" / "Prototype_1.0.3"` (как `tests/conftest.py:11`).
Готовый код всех сценариев под вариант F (не тесты — проверки на копии
прототипа): `vault/issues/bug-014/probes/audit_check_f.py`.

Модульная фикстура `drawn_down` (scope `module`): модель `n = 12`, `bhp = 100`,
`p0 = 200`; 12 шагов `advance(cur, 300.0)`, каждый `converged`: $p[0] = 111.672$
бар, $S_g[0] = 0.0672$, 5 двухфазных. Хелпер `_model(bhp)` — свежая модель с
этим `bhp`. Каждый тест — комментарий: физика, ожидание, что ловит.

Поля отчёта ниже — кортеж (`converged`, `well_branch`, `well_switches`, `fallback`).
Во всех тестах 1–7 после `advance`: `model._well_branch is None`,
`model._sg_lower_bound == -0.05`.

| № | Тест | Сценарий | Ожидание (замер на копии F) | До правки |
|---|---|---|---|---|
| 1 | `test_long_upstep_reopens_well` | $p_{wf}$ = 150 бар, 3600 с | (True, "open", 1, True); $p[0] \ge 150$ (152.605); `well_rates(new)["oil_sm3_s"] > 0` (2.14e-5) | ✗ не сходится |
| 2 | `test_long_upstep_near_reservoir_stays_shut` | 195 бар, 3600 с | (True, "shut", 0, True); $111.672 < p[0] \le 195$ (170.743); дебит `== 0.0` | ✗ |
| 3 | `test_short_upstep_original_path` | 195 бар, 60 с | (True, "shut", 0, **False**) — исходный алгоритм справился; $p[0] \le 195$ (122.297) | ✗ (нет полей) |
| 4 | `test_downstep_original_path` | 105 бар < $p[0]$, 3600 с | (True, "open", 0, False); дебит > 0 (6.43e-5) | ✗ (нет полей) |
| 5 | `test_mass_balance_after_fallback` | случаи 1 и 2 | `step_global_balance(old, new, dt)`: \|ошибка\| / суммарный запас (`component_inventories(old)`) ≤ 1e-12 (замер ~1e-16) | ✗ |
| 6a | `test_exception_in_original_call` | на экземпляре `_advance_phases` = функция, бросающая `RuntimeError` | исключение наружу; `_well_branch is None`, `_sg_lower_bound == -0.05`; `well_rates` на `drawn_down` при $p_{wf}$ = 195: дебит 0, `bhp_bar == p[0]` | ✗ (нет атрибутов) |
| 6b | `test_exception_in_fallback` | подставной `_advance_phases` (механизм — в классе `TestAdvanceBranchLogic` ниже; вынести в общий хелпер модуля): исходный вызов `(None, -0.05)` — отказ, `("shut", None)` — исключение | то же, что 6a | ✗ |
| 7 | `test_rate_control_original_path` | как `Prototype_1.0.3/tests/test_rate_control.py:30-35`: свежая модель, начальное состояние, `set_oil_rate_control(2.0, 100.0)`, `advance(s, 60.0)` | (True, "", 0, False); дебит × 86400 == approx(2.0, rel=1e-10) | ✗ (нет полей) |
| 8 | `test_sg_lower_bound_attribute` | `z = model.pack(drawn_down, mask)`, в двухфазной ячейке $S_g = -0.3$ | по умолчанию `_trial_is_reasonable` → `False`; при `model._sg_lower_bound = None` → `True`; $S_g = 0.99$ при `None` → `False` | ✗ (атрибута нет — `True` не получить) |
| 9 | `test_other_bounds_kept` | по умолчанию: $p = 0.5$ бар, `nan`, однофазная $R_s = -10^{-6}$ | все `False` | ✓ (охраняет) |

Класс `TestAdvanceBranchLogic` — управляющая логика `advance` без Ньютона. На
экземпляре `_advance_phases` подменяется функцией, которая по ключу
`(model._well_branch, model._sg_lower_bound)` в момент вызова возвращает заданный
ответ — копию `state_old` с выставленным `pressure_bar[0]` и
`BlackOilNewtonReport(converged, 3, 0.0)` — или бросает `RuntimeError`; ключи
вызовов записываются. Исходный вызов — ключ `(None, -0.05)`. Модель с
$p_{wf}$ = 150 бар, `state_old` — `drawn_down` (111.67 < 150 → запасной путь
стартует с «закрыта»); для 12d — $p_{wf}$ = 105 бар; для 12f — управление по
дебиту, начальное состояние.

| № | Тест | Подстановка | Ожидание: вызовы; поля |
|---|---|---|---|
| 12a | `test_fallback_second_branch` | исходный — отказ; shut — отказ; open — (да, 151) | `[(None,-0.05), ("shut",None), ("open",None)]`; (True, "open", 1, True) |
| 12b | `test_all_fail` | все — отказ | те же три вызова; (False, "open", 1, True) |
| 12c | `test_both_branches_inconsistent` | исходный — отказ; shut — (да, 160); open — (да, 140) | те же три; (False, "open", 1, True) |
| 12d | `test_fallback_start_from_old_state` | $p_{wf}$ = 105: исходный — отказ; open — (да, 110) | `[(None,-0.05), ("open",None)]`; (True, "open", 0, True) |
| 12e | `test_original_converged_no_fallback` | исходный — (да, 151) | `[(None,-0.05)]`; (True, "open", 0, False) |
| 12f | `test_rate_control_fallback_without_branch` | дебит: исходный — отказ; `(None, None)` — (да, 190) | `[(None,-0.05), (None,None)]`; (True, "", 0, True) |

Во всех 12a–f после вызова: `_well_branch is None`, `_sg_lower_bound == -0.05`.
До правки все красные.

**`test_prototype_adapter.py`, класс `TestAdapterPwfUpStep`** (фикстуры файла
`model`, `adapter`, `initial_state`; хелпер `_bc(p_wf)` как фикстура `bc`,
`:121-125`). Подготовка: 6 × `adapter.solve(state, dt=3600.0, bc=_bc(80e5))` →
$p[0] = 84.12$ бар, 11 двухфазных.

| № | Тест | Сценарий | Ожидание | До правки |
|---|---|---|---|---|
| 10 | `test_long_upstep_single_substep` | `solve(..., dt=3600.0, bc=_bc(114e5))` | нет исключения; `n_substeps == 1`; `G_o[0] < 0` (добыча — к скважине; −4.47e-3); `state.p[0] >= 114e5` (116.57 бар) | ✗ `RuntimeError` |
| 11 | `test_short_upstep_well_shut` | `dt=60.0, bc=_bc(190e5)` | `n_substeps == 1`; `G_o[0] == 0.0`, `G_g[0] == 0.0`, `G_free_gas[0] == 0.0` (−0.0 проходит `==`); `state.p[0] < 190e5` (157.09 бар) | ✗ `n_substeps == 64` |

**Проверка:** `.venv\Scripts\python -m pytest tests/test_prototype_well_branch.py tests/test_prototype_adapter.py -v`
— красные ровно 1–8, 6a, 6b, 10, 11, 12a–f; 9 и прежние тесты адаптера зелёные.
**Зависимости:** шаг 0. **Оценка:** ~300 строк, ~70 мин.

---

### Шаг 2: Атрибуты, поля отчёта, управляемые ветка и граница (поведение не меняется)

**Файл:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`.

1. `BlackOilNewtonReport` (`:15-21`) — три поля в конце:
   ```python
       phase_switches: int = 0
       well_branch: str = ''     # BHP control: branch of the accepted step ('open'/'shut'), BUG-014
       well_switches: int = 0    # branch changes in advance's fallback, BUG-014
       fallback: bool = False    # step solved by advance's fallback, BUG-014
   ```
2. `__init__` (`:36`). Строка `self._last_effective_bhp_bar=self.p_bhp_bar; self._last_constraint_active=False`
   встречается **дважды** (`:36` в `__init__`, `:44` в `set_bhp_control`) — якорь
   брать вместе со следующей строкой `__init__`:
   До:
   ```python
           self._last_effective_bhp_bar=self.p_bhp_bar; self._last_constraint_active=False
           if jacobian_mode not in ('grouped','reference'): raise ValueError(...)
   ```
   После:
   ```python
           self._last_effective_bhp_bar=self.p_bhp_bar; self._last_constraint_active=False
           # BUG-014: set by advance's fallback only.  _well_branch forces the BHP
           # well branch for the whole nonlinear solve (None -> chosen from p0);
           # _sg_lower_bound is the line-search bound on Sg of two-phase cells.
           self._well_branch=None; self._sg_lower_bound=-0.05
           if jacobian_mode not in ('grouped','reference'): raise ValueError(...)
   ```
   (`...` — строка без изменений.) `set_bhp_control` не трогать.
3. `_well_fluxes`, ветка BHP (`:78-88`).
   До:
   ```python
               target=float(self.p_bhp_bar)
               if p0 <= target:
                   bhp=p0; qow=0.0; qgfw=0.0
               else:
                   bhp=target; dpw=p0-bhp
                   qow=float(tw*lo*dpw*BAR_TO_PA); qgfw=float(tw*lg*dpw*BAR_TO_PA)
   ```
   После (комментарий над блоком сохранить):
   ```python
               target=float(self.p_bhp_bar)
               # BUG-014: in advance's fallback the branch is fixed for the whole
               # Newton solve.  Choosing it from the current iterate put Newton on
               # the branch where the step had no consistent solution.
               branch=self._well_branch
               if branch is None: branch='shut' if p0 <= target else 'open'
               if branch=='shut':
                   bhp=p0; qow=0.0; qgfw=0.0
               else:
                   # 'open' without the sign check: q < 0 (injection) is allowed on
                   # intermediate iterates; advance rejects it after convergence.
                   bhp=target; dpw=p0-bhp
                   qow=float(tw*lo*dpw*BAR_TO_PA); qgfw=float(tw*lg*dpw*BAR_TO_PA)
   ```
   Ветка `OIL_RATE` (`:56-77`) — не трогать.
4. `_trial_is_reasonable` (`:184`).
   До:
   ```python
           if np.any(x[gas_active]<-0.05) or np.any(x[gas_active]>0.98): return False
   ```
   После:
   ```python
           # BUG-014: the lower bound on Sg of two-phase cells is an attribute.  The
           # original algorithm keeps -0.05; advance's fallback sets None (method of
           # negative saturations): Sg < 0 is a smooth extension of the cell
           # equations (inventories linear in Sg, PVT independent of Sg, relperm
           # tables clamp at the first row), and the phase active set switches such
           # cells after convergence.  With -0.05 every trial was rejected when free
           # gas dissolved in a whole zone (BHP raised above p0).
           lo=self._sg_lower_bound
           if (lo is not None and np.any(x[gas_active]<lo)) or np.any(x[gas_active]>0.98): return False
   ```

**Проверка:** атрибуты по умолчанию — поведение побитово прежнее: существующие
тесты зелёные (`pytest tests -q -m "not slow"`); из новых зеленеют 7 (поля с
умолчаниями), 8 (атрибут есть), 9 — с шага 1.
**Оценка:** ~30 строк, ~20 мин. **Зависимости:** шаг 1.

---

### Шаг 3: `advance` с запасным путём

**Файл:** `blackoil.py`, `advance` (`:202-219`).

1. Строку `    def advance(self,state_old,dt_s,max_active_iter=12,max_newton=15):\n`
   заменить на: новый `advance` (п. 2) + `    def _advance_phases(<та же сигнатура>):`
   + docstring `"""Phase active-set loop (unchanged Prototype 1 logic)."""`. Тело
   бывшего `advance` — **без изменений**.
2. Новый `advance`:
   ```python
       def advance(self,state_old,dt_s,max_active_iter=12,max_newton=15):
           """One implicit step: the original algorithm; on failure a fallback with the
           BHP well branch as an outer constraint and no lower bound on Sg (BUG-014)."""
           new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
           if rep.converged:
               if self.control_mode=='BHP':
                   # branch the automatic rule takes on the accepted state
                   p0=float(new.pressure_bar[0])
                   rep.well_branch='shut' if p0<=float(self.p_bhp_bar) else 'open'
               return new,rep
           # Fallback only: where the original algorithm converges, results stay
           # bitwise; with the bound removed always, deep drawdowns needed more
           # step splitting than before (BUG-014 audit).
           self._sg_lower_bound=None
           try:
               if self.control_mode!='BHP':
                   new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
                   rep.fallback=True; return new,rep
               target=float(self.p_bhp_bar)
               # Start from the branch of the old state; shut-in steps start on 'shut'.
               branch='shut' if float(state_old.pressure_bar[0])<=target else 'open'
               tried=[]
               while True:
                   tried.append(branch); self._well_branch=branch
                   new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
                   rep.fallback=True; rep.well_branch=branch; rep.well_switches=len(tried)-1
                   if rep.converged:
                       p0=float(new.pressure_bar[0])
                       # open: q = WI*lambda*(p0-target) >= 0; shut: p0 <= target
                       if (p0>=target) if branch=='open' else (p0<=target): return new,rep
                   # Newton failed or the branch is inconsistent: the other branch, once
                   other='open' if branch=='shut' else 'shut'
                   if other in tried:
                       rep.converged=False; return new,rep
                   branch=other
           finally:
               self._sg_lower_bound=-0.05; self._well_branch=None
   ```
3. Модульный docstring (`:1-6`): к фразе «Physics and Newton/active-set logic are
   unchanged…» добавить: `Local changes (GPN project, BUG-014): when the original
   step fails, advance() retries with the BHP well branch as an outer active
   constraint and no lower bound on Sg of two-phase cells.`

**Проверка:** все тесты шага 1 зелёные (на копии F — 17/17, `audit_check_f.py`);
`pytest tests -q` — исходный уровень шага 0 + новые, **кроме**
`test_factory_standing_hydro.py::TestStandingDeepDrawdownDenseGrid::test_fails_one_below_threshold`
(красный — ожидаемо, удаляется в шаге 4; на копии F — единственный отказ из 904).
**Подводные камни:** при неудаче возвращается `new` — вызывающие смотрят только
`rep.converged` (`prototype_adapter.py:91`, `simulation.py:82`).
**Оценка:** ~35 строк, ~25 мин. **Зависимости:** шаг 2.

---

### Шаг 4: удалить тест, закреплявший старое поведение

**Файл:** `numerical_solver/tests/test_factory_standing_hydro.py` (решение 6).

1. Удалить `test_fails_one_below_threshold` (`:126-138`).
2. Docstring класса `TestStandingDeepDrawdownDenseGrid` (`:83-94`) переписать:
   сценарий DEBT-007 (пример 03, $N = 75$, $p_{wf} = 6$ МПа на всех интервалах) до
   BUG-014 требовал 9 удвоений; после BUG-014 первый шаг сходится без дробления —
   запасной путь `advance` (без нижней границы $S_g$) проходит шаг, на котором
   исходный Ньютон отвергал пробные точки; объяснение одной нелинейностью $B_g$
   неполное. Класс остаётся регрессионной привязкой результата
   (`test_converges_at_default_limit`). Умолчание `max_retries = 9` обосновано
   примером 04a (первый шаг — 512 = 2⁹ подшагов,
   `tests/test_examples.py::TestHighGasSaturation::test_dense_grid_converges_at_default_retries`) и
   примером 03 при $p_{wf}$ = 2 и 0.5 МПа, $N = 150$ (порог 9, замер аудита BUG-014).

**Проверка:** `pytest tests/test_factory_standing_hydro.py -v` — зелёный;
`pytest tests -q` — исходный уровень − 1 + новые, все зелёные.
**Оценка:** ~20 строк, ~10 мин. **Зависимости:** шаг 3.

---

### Шаг 5: Документация прототипа

**Файл:** `Prototype_1.0.3/CHANGELOG_1.0.3.md` — в конец раздел
`## Local changes — GPN project (BUG-014)`: запасной путь в `advance`
(`_advance_phases`, стратегия ветки, `_sg_lower_bound`, поля отчёта), issue #42,
этот план. Язык — английский, как в файле. `PACKAGE_MANIFEST_SHA256.txt` — не менять.
**Оценка:** ~15 строк, ~10 мин.

---

### Шаг 6: Верификация

1. `pytest tests -q` — исходный уровень шага 0 − 1 (удалённый тест) + новые, все
   зелёные. Тесты прототипа — 70 passed + 10 failed (`xlsxwriter`); удалить
   `OUTPUT/short_run/`.
2. `vault/issues/bug-014/probes/verify_fix.py` — новый, **без подмен** (правка уже
   в коде; пробы с `method_n_runs_lib.install` после правки не запускать).
   В начале — `sys.path`: `numerical_solver`, `numerical_solver/examples`,
   `Prototype_1.0.3`; модель `Nabor_1b` — напрямую (как в шаге 1), не через
   `tests.helpers`. Содержание и ожидания (замер на копии F, `audit_variant_f.py check`):
   - дешёвая матрица `Nabor_1b` (как `branch_strategy.py`, 80 случаев): **0 отказов**,
     запасной путь — в 20;
   - одиночные скачки из `probes/states_upsteps.npz` (t = 1, 3 сут × 6.2 / 7 / 8 /
     10.75 МПа × 3600 / 60 / 7 / 1 с, как `branch_strategy.py`): **31 из 32**,
     единственный ✗ — t = 1 сут, 10.75 МПа, 3600 с (лимит 15 итераций);
   - 13б 30 сут через `Simulator` (`phase_switch_newton.cfg_schedule`), штатный
     `max_retries`: **OK**, ~65 с.
3. T08c: `.venv\Scripts\python ..\vault\issues\bug-014\probes\t08c_softness.py`
   (теперь с правкой в коде) — таблица как в §1.5 «стало».
4. `examples_regression.py run after`, затем `compare before after`. Ожидание:
   13 примеров — **Δ = 0** по всем полям, дробление то же; пример 03 — мелких
   подшагов 512 → 0, \|ΔT_wf\| ≈ 0.24 К на записи 1, ≈ 4e-5 К на последней.
   Иначе — стоп, разбор с пользователем, не подгонять. После — удалить
   `probes/regression_runs/`.

**Оценка:** ~120 строк, ~40 мин.

---

### Шаг 7: Пример 03, документация, vault, issue

1. **Пример 03** (решение 5):
   - `examples/03_standing_corey/config.json:415` — убрать `"max_retries": 10`
     (и запятую после `"skin": 0.0` в `:414`); остаётся умолчание 9;
   - пороги — `.venv\Scripts\python ..\vault\issues\bug-014\probes\retries_threshold_tables.py HydroSolverPrototype\Prototype_1.0.3 03`
     (~5 мин). Ожидание (замер аудита на копии F): $N = 150$ — $p_{wf}$ 8…5 МПа → 0,
     4 → 1, 2 → 9, 0.5 → 9; $p_{wf} = 8$ МПа — $N$ 50…200 → 0 (строки $N$ под F
     выведены из замера N «всегда», перепроверить);
   - README 03: `:81` — время по факту `main.py` (было ~13 с; расчёт 14.5 → 1.2 с);
     `:360` — «лимите дроблений из конфига (10)» → «по умолчанию (9)»; раздел
     `:401-425` переписать по новым порогам: первый шаг 20 → $p_{wf}$ при
     8…5 МПа больше не дробится; дробление нужно только при глубокой депрессии
     (2 и 0.5 МПа — 9 удвоений, в пределах умолчания); объяснение — BUG-014
     (граница $S_g$ в поиске по направлению), без сравнения с другими примерами;
   - `.venv\Scripts\python examples\03_standing_corey\main.py` — сверить числа
     README при показанной точности (`:74-76`, `:123-125`, `:155`); по замеру
     аудита конечные значения меняются на ≤ 4.3e-5 К и ~1e-3 Па — ниже показанной
     точности; таблица сходимости по сетке `:362-368` — значения на 72 ч,
     не пересчитывать, если `main.py` подтвердит строку $N = 150$.
   - **Баланс энергии 03 меняется** (замер аудита, раунд 2,
     `audit2_ex03_balance.py`: исходный — отн. невязка 5.499e-12, абсолютная
     0.263 Дж, $\Delta E$ = 2.963002e9 Дж; с правкой — 4.176e-14, 0.002 Дж,
     2.962791e9 Дж): 512 подшагов первого часа накапливали невязку. Обновить
     README 03 `:278-283` (таблица «Значение (финал)» — компоненты по выводу
     `main.py`, при 4 значащих цифрах ожидаются прежние; строка невязки —
     новая) и `:299-306` (таблица по $\Delta t$ = 3600 / 900 / 360 с и вывод под
     ней «невязка слегка растёт при измельчении шага» — перепроверить):
     `.venv\Scripts\python examples\energy_balance_convergence.py 03`.
   - `examples/README.md:139` — время примера 03 по факту; `:339` — строка 03
     (отн. невязка, было 5.5e-12) — по выводу `main.py`. Строки 03 в `:243`,
     `:299`, `:429` — значения на конец расчёта, ниже показанной точности не
     меняются; сверить по выводу `main.py`.
2. **README 04, 04a — без изменений.** Замер аудита на копии F
   (`retries_threshold_tables.py … 04`): таблица `04/README.md:346-348` совпала
   целиком (0, 5, 0, 0, 1, 0, 0, 3, 1, 4); $N = 100$ — 5 («укладывается в
   умолчание»), $N = 150$ — 10 за 112 с («требует 10 и ~100 с»), $N = 200$ — не
   сходится при ≤ 10 (в README — «даже при 14», выше 10 не проверялось). 04a при
   штатном конфиге — побитово то же (512 подшагов); пороги для других $N$ вариант F
   может только снизить — утверждения `04a/README.md:153-172, 412, 445` остаются
   верными как верхние оценки.
3. `examples/13a_pwf_ramp_down/README.md:211-213` — пункт «Рост $p_{wf}$ между
   интервалами…»: скачки вверх считаются; при $p[0] < p_{wf}$ скважина закрыта
   (закачки нет); сценарий с чередованием — пример 13б ([[FEAT-023]]). Абзац
   `:136-139` («Скважина ни разу не закрывается… этот пример не проверяет») — верен,
   не трогать.
4. Реестр: BUG-014 — **Статус** `✅ ИСПРАВЛЕНО <дата>` с итогом; «Обходной путь» —
   снят. DEBT-007 (закрыт) — строка «Поправка (BUG-014, <дата>)»: первый шаг
   примера 03 сходится без дробления после снятия границы $S_g \ge -0.05$ в
   запасном пути; объяснение первопричины нелинейностью $B_g$ неполное;
   умолчание 9 по-прежнему нужно (04a, 03 при 2 / 0.5 МПа).
5. `vault/roadmap/планируемые фичи.md`, FEAT-023 — блокировка BUG-014 снята.
6. Новая заметка `vault/knowledge/numerics/запасной путь с отрицательной
   насыщенностью и веткой скважины снимает порог шага на скачке p_wf вверх.md` —
   §1.2–1.7 сжато (методы, стратегии, регрессия N «всегда», вариант F, T08c).
7. [[прототип переживает скачок p_wf вверх, падает равномерное дробление
   адаптера]], раздел «Следствие для фикса», — строка-итог со ссылкой на новую
   заметку: неравномерное дробление не понадобилось.
8. `vault/knowledge/decisions/hydro-prototype-анализ.md:87-89` — `_trial_is_reasonable`:
   нижняя граница $S_g$ — атрибут (−0.05, в запасном пути снята); `advance` —
   исходный цикл набора фаз (`_advance_phases`) + запасной путь (BUG-014).
9. `vault/00-home/index.md` — у строки плана BUG-014 ✅ и итог.
10. Комментарий в #42: `vault/issues/bug-014/05-comment-done.md` →
    `gh issue comment 42 --repo ArturSalamatin/Oil_Gas --body-file ...`.
11. Очистка проб — §8 (последним действием, после п. 1–10: п. 1 и шаг 6
    пользуются `retries_threshold_tables.py`, `examples_regression.py`,
    `verify_fix.py`).

**Оценка:** ~90 мин (включая пороги ~10 мин).

---

## 4. Тестовая стратегия (сводка)

| Уровень | Тесты | Что ловят |
|---|---|---|
| Unit (прототип) | 1–4, 7 | исходный путь не тронут (3, 4, 7); запасной путь сходится к согласованной ветке (1, 2) |
| Unit (логика `advance`) | 12a–f | порядок вызовов, запасная ветка, не более двух решений, старт по старому состоянию, дебит без цикла ветки |
| Unit (поиск по направлению) | 8, 9 | граница $S_g$ управляется атрибутом; прочие проверки на месте |
| Инварианты | 5, 6a, 6b | баланс массы в запасном пути; восстановление атрибутов, в том числе при исключении |
| Интеграционные (адаптер) | 10, 11 | нет `RuntimeError` и дробления на скачке вверх; нулевые потоки закрытой скважины, знак потока |
| Регрессия | весь набор (14 примеров в `test_examples.py`) + `examples_regression.py` | 13 примеров побитово; изменение 03 — ожидаемое |
| Валидация | `verify_fix.py` (13б 30 сут), `t08c_softness.py` | цель задачи; регрессионный кейс прототипа |

## 5. Критерии завершения

- [x] Тесты 1–8, 6a, 6b, 10, 11, 12a–f были красными до правки и зелёные после (до: 18 failed, 9 и 36 прежних зелёные; после: 54 passed)
- [x] `pytest tests -q`: 922 passed, 487 с (исходный уровень 904 / 500 с на `a3f9cd1`; −1 удалённый, +19 новых)
- [x] Тесты прототипа: 70 passed, 10 failed (`xlsxwriter`) — как до правки
- [x] `verify_fix.py`: 0/80 (запасной путь в 20), 31/32, 13б 30 сут OK за 63 с
- [x] T08c — как в §1.5 (отказов подряд 0 / 0 / 0 / 1, первые шаги 60 / 3051 / 60 / 710 с)
- [x] `examples_regression.py`: 13 примеров Δ = 0; 03 — 512 → 0, max\|ΔT\| 0.24 К, \|ΔT_wf\| в конце 4.3e-5 К
- [x] Пример 03: конфиг без `max_retries`, README по новым порогам и времени (+ отклонение, §9)
- [x] README 13a, `examples/README.md` обновлены (README 04/04a — без изменений)
- [x] Реестр (BUG-014 ✅, поправка DEBT-007, FEAT-023), заметки, индекс обновлены
- [x] Issue #42 прокомментирован
- [x] Пробы удалены по списку §8, блок BUG-014 из `.gitignore` убран

## 6. Как начать работу по этому плану

1. Прочитай этот файл целиком; затем запись BUG-014 в
   `vault/roadmap/известные баги и технический долг.md` и заметку
   [[прототип переживает скачок p_wf вверх, падает равномерное дробление адаптера]].
2. `git status --short numerical_solver` — пусто (иначе стоп, шаг 0 п. 1).
3. `git checkout numerical_scheme/implementation; git checkout -b fix/bug-014/well-shutin-active-set`
4. `cd numerical_solver` — все команды отсюда; Python — `.venv\Scripts\python`.
5. Исходный уровень: `.venv\Scripts\python -m pytest tests -q` — ожидается 904 passed (~8 мин, `9e43027`); записать фактическое.
6. Эталон примеров: `.venv\Scripts\python ..\vault\issues\bug-014\probes\examples_regression.py run before` — **до** правки кода.
7. Воспроизведение: `.venv\Scripts\python ..\vault\issues\bug-014\probes\adapter_reproducer.py`.
8. Шаг 1 (тесты красные) → шаги 2–5 → после каждого `pytest` → шаг 6 → шаг 7.

## 7. Связанные

- [[BUG-014]] — запись реестра; issue [#42](https://github.com/ArturSalamatin/Oil_Gas/issues/42)
- [[прототип переживает скачок p_wf вверх, падает равномерное дробление адаптера]] — T08c, цикл по времени прототипа
- [[DEBT-007]] — первопричина дробления первого шага примера 03 (поправка — шаг 7)
- [[BUG-008]] — зеркальный случай (появление газа при $N \ge 200$); 04a после правки — побитово то же (512 подшагов), эта правка его не адресует
- [[DEBT-015]] — стратегия дробления A-retry
- [[BUG-010]] — энергия идёт теми же подшагами, что гидродинамика
- [[FEAT-020]] — управление по дебиту
- [[FEAT-023]] — пример 13б, разблокируется
- [[FEAT-019]] — останов скважины и восстановление давления
- [[DEBT-024]], [[DEBT-025]] — зарегистрированы при планировании

## 8. Очистка после реализации

Выполняется последней (шаг 7, п. 11), когда все критерии §5, кроме этого,
выполнены. Всё ниже — в `vault/issues/bug-014/probes/`, исключено из git
(`.gitignore`, блок «BUG-014: пробы исследования и аудита»), поэтому удаляется
только с диска; коммит не нужен, кроме правки `.gitignore`.

**Удалить** (28 файлов и каталоги данных):

| Группа | Файлы |
|---|---|
| исследование (§1.2–1.6) | `well_branch_outer_loop.py`, `where_4day_fails.py`, `second_upstep_reason.py`, `phase_switch_newton.py`, `s_first_step_debug.py`, `hybrid_methods.py`, `phase_switch_runs.py`, `same_dt_compare.py`, `method_n_runs.py`, `method_n_runs_lib.py`, `cheap_reproducer.py`, `branch_strategy.py`, `test_expectations.py`, `t08c_with_fix.py`, `states_upsteps.npz` |
| аудит (§1.7, раунды 1–2) | `audit_apply_plan.py`, `audit_variant_f.py`, `audit_check_scenarios.py`, `audit_check_f.py`, `audit_examples_run.py`, `audit_preimport.py`, `audit_t08c_variant.py`, `audit2_apply_plan_text.py`, `audit2_ex03_balance.py` |
| реализация (шаги 0, 6, 7) | `adapter_reproducer.py`, `examples_regression.py`, `retries_threshold_tables.py`, `verify_fix.py` |
| данные | `regression_runs/`, `_audit_copy/`, `_audit_examples/` (если есть), `__pycache__/` |

Команда (из корня проекта):
```powershell
cd vault\issues\bug-014\probes
Remove-Item -Recurse -Force -Confirm:$false well_branch_outer_loop.py, where_4day_fails.py, second_upstep_reason.py, phase_switch_newton.py, s_first_step_debug.py, hybrid_methods.py, phase_switch_runs.py, same_dt_compare.py, method_n_runs.py, method_n_runs_lib.py, cheap_reproducer.py, branch_strategy.py, test_expectations.py, t08c_with_fix.py, states_upsteps.npz, audit_apply_plan.py, audit_variant_f.py, audit_check_scenarios.py, audit_check_f.py, audit_examples_run.py, audit_preimport.py, audit_t08c_variant.py, audit2_apply_plan_text.py, audit2_ex03_balance.py, adapter_reproducer.py, examples_regression.py, retries_threshold_tables.py, verify_fix.py -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force -Confirm:$false regression_runs, _audit_copy, _audit_examples, __pycache__ -ErrorAction SilentlyContinue
```
Затем из `.gitignore` убрать блок «BUG-014: пробы исследования и аудита» —
файлов больше нет.

**Не удалять:** `t08c_softness.py` (отслеживается git, из параллельной сессии,
на него ссылается заметка [[прототип переживает скачок p_wf вверх, падает
равномерное дробление адаптера]]); `vault/issues/bug-014/01-issue-body.md` …
`05-comment-done.md` (копии опубликованного в #42).

После очистки ссылки §1 этого плана на пробы остаются как указание источника
замеров; сами числа сохранены в плане и в итоговой заметке `vault/knowledge/numerics/`
(шаг 7, п. 6).

## 9. Итог реализации (2026-09-30)

Коммиты ветки: `a3f9cd1` (vault, начало), `ba87be9` (шаг 2), `a17aaa6` (шаги 1, 3, 4 —
тесты вместе с правкой, чтобы в истории не было красного состояния), `165ba87`
(шаг 5), `cd44e99` (шаг 7, пример 03 и README), затем vault. Все замеры шагов 0 и 6
совпали с планом.

**Отклонение — README 03.** План ожидал, что числа на конец расчёта не сдвинутся
при показанной точности. Физические величины ($q_o$, $T$, $S_g$, $r_b$, баланс по
компонентам) — да. Сдвинулись величины уровня допуска Ньютона и округления:
\|GOR − $R_{s,0}$\| на забое 2.1e-7 → 2.5e-9 (столбец таблицы по сетке при
$N$ = 100 / 150 / 200: 6.1e-8 / 2.1e-7 / 2.0e-7 → 4.7e-9 / 2.5e-9 / 3.6e-9),
Дюпюи 9.3e-9 → 1.9e-8 Па, разброс потоков по граням 1e-9 → 1e-11, свободный газ
7e-8 → 7e-10, $R_s$-равновесие 2e-14 → 1.4e-14, наклон 2.2e-14 → 1.9e-14; баланс
энергии по $\Delta t$ = 3600 / 900 / 360 с: 4.2e-14 / 6.1e-12 / 1.0e-11. Неверным стало
утверждение «на 1-м шаге GOR = $R_{s,0}$ до шести знаков»: первый час — один неявный
шаг, GOR на 1 ч = 49.9907. Проверено пробой `impl_ex03_roundoff.py` на копии
прототипа до правки (воспроизводит README побитово в показанных знаках).
Причина — застывание состояния в стационаре (Ньютон делает 0 итераций): раньше
с 1-го часа, теперь с 3-го. README 03 переписан по факту; разбор — в итоговой
заметке. $T(r_w)$ при $N = 200$ в таблице README 03 — 352.765, замер и до, и после
правки — 352.764 (352.76445): расхождение округления существовало до BUG-014, не
правилось.
