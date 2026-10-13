---
tags:
  - план
  - исправление
date: 2026-10-11
issue: BUG-025
github: 105
branch: fix/bug-025/short-step-residual-floor
status: в процессе
worktree: .worktrees/bug-025
audit:
  date: 2026-10-13
  round: 2
  found: 8
  auto-fixed: 8
  manual-required: 0
---

# BUG-025: допуск Ньютона не ниже предела округления накопления — короткий шаг на старте останова

**Подтип:** исправление дефекта (прототип `radial_blackoil` + постановка + тесты).
**База:** `numerical_scheme/implementation`, `015a297` (DEBT-054 влита: `288a65d`). Все замеры плана — на этой базе. **Аудит 2 (2026-10-13): база `3f3df63`** — влита DEBT-011 (`7f8d879`, +58 тестов: 1768 → 1826). Прототип, постановка и тестовые файлы плана с `015a297` не менялись. Числа шагов 3 и 5 на `3f3df63` перепроверены и совпали побитово (`vault/issues/bug-025/probes/audit2/audit2.out.txt`).
**Ветка:** `fix/bug-025/short-step-residual-floor`, worktree `.worktrees/bug-025`.
**Issue:** [#105](https://github.com/ArturSalamatin/Oil_Gas/issues/105).

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись BUG-025 в `vault/roadmap/известные баги и технический долг.md`. Для контекста — записи BUG-022 и DEBT-054 там же: условие сходимости по ячейке и отчёт Ньютона, на которые опирается план.
3. **Материалы задачи — в базу до worktree (аудит 2).** Пробы `vault/issues/bug-025/probes/` (скрипты и `*.out.txt`) и этот план на `3f3df63` в git не внесены. Команды ниже запускают их из worktree (`..\vault\issues\bug-025\probes\…`), а в worktree попадает только то, что закоммичено. `/implement` делает это первым коммитом («план и материалы задачи» в базовую ветку). Проверка после него:
   ```powershell
   git ls-tree -r --name-only numerical_scheme/implementation -- vault/issues/bug-025/probes | Select-String "floor_probe.py|histories.py|census.py|ramp_with_floor.py|fix_k4_r200.out.txt"
   ```
   Должно быть 5 строк. `*.npz` проб в git не идут (`.gitignore`). Пробы FEAT-032 (`ramp_probe.py`) и VAL-004 (`dt_series.py`), которые вызывают `ramp_with_floor.py` и `floor_probe.py series`, в базе уже есть.
   Рабочее дерево — по `/implement`:
   ```powershell
   git worktree add .worktrees/bug-025 -b fix/bug-025/short-step-residual-floor numerical_scheme/implementation
   ```
   Интерпретатор — `numerical_solver\.venv\Scripts\python.exe` **основного** каталога по абсолютному пути (в worktree `.venv` нет). Пробы этого плана сами ставят в начало `sys.path` каталог запуска и прототип из него и печатают, откуда взят код (`Код: …`, `Прототип: …`). Проверяй по этим строкам, что код взят из worktree.
4. Базовый вариант (из `<worktree>\numerical_solver`):
   ```powershell
   $PY = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   & $PY -m pytest tests/ --collect-only -q          # ожидается 1826 (на 3f3df63)
   & $PY -m pytest tests/ -m "not slow" -q           # запиши число passed и время, ~70 с
   & $PY ..\vault\issues\bug-025\probes\histories.py save before   # ~3 мин, 26 сценариев
   & $PY ..\vault\issues\bug-025\probes\floor_probe.py scan        # ~10 с: дефект виден (см. 1.2)
   cd HydroSolverPrototype\Prototype_1.0.3
   & $PY -m pytest tests -q                          # ожидается 97 passed, ~45 с
   ```
   Регрессию прототипа до правки запускать не нужно: она сравнивает с эталоном `regression/golden/`, а не с прошлым прогоном. Запускается после шага 3.
5. Если база к началу реализации ушла вперёд, запиши фактические числа. Снимок `histories.py save before` снимай **до** правки кода.
   **Проверка на FEAT-032 (аудит 1).** FEAT-032 (`vault/plans/feat-032 ramp-step-after-control-change.md`) с 2026-10-13 в реализации: worktree `.worktrees/feat-032`, ветка `feat/feat-032/ramp-step-after-control-change`; на `3f3df63` в базу не влита (аудит 2). Она включает в примерах 16 и 17 нарастающий шаг после останова: `time.dt_after_control_change` = 2 с, первый подшаг 1.76 с. В примере 16 ($M_{max}$ = 5.49e4 м³ст) у этого подшага κ* = $10^{-11}\cdot1.76/(\varepsilon_{маш}\cdot5.49\cdot10^4)$ ≈ 1.4 < 4. Значит, если FEAT-032 влита в базу раньше BUG-025, предел округления в допуске изменит решения подшагов и историю 16 (возможно, и 17: там κ* ≈ 8.8), а ожидание «все примеры побитово» станет неверным. Проверить до шага 1:
   ```powershell
   git grep -n "dt_after_control_change" numerical_scheme/implementation -- numerical_solver/examples/16_well_shut_in/config.json
   ```
   Пусто (код возврата 1 — так `git grep` сообщает «не найдено», на `015a297` так и есть) — FEAT-032 нет, план как есть. Есть — до правки кода перемерить `& $PY ..\vault\issues\bug-025\probes\census.py` на новой базе (перепись не зависит от правки). Каждый сценарий с решениями κ* < 4 — **стоп, решение пользователя**: история примера и закреплённые FEAT-032 числа (отпечаток 16 в `vault/issues/feat-032/probes/fingerprint_examples.py`, README и тесты 16) сдвинутся. Обратный порядок (BUG-025 первым) план FEAT-032 обрабатывает сам (его П15).
6. Начни с шага 1. После каждого шага — тест шага и регресс по полю «Регресс». Полный прогон `tests/` и полная регрессия прототипа — в шаге 5.

---

## 0. Решения пользователя (2026-10-11, при планировании)

1. **Вариант 2 issue — допуск не ниже предела округления, κ = 4.** Абсолютный допуск обоих Ньютонов прототипа:
   $$\text{tol} = \max\Bigl(\varepsilon^{abs},\ \kappa\,\frac{\varepsilon_{маш} M_{max}}{\Delta t}\Bigr) + \varepsilon^{rel}\max(\|F_0\|_\infty, 10^{-9}),\qquad \kappa = 4,$$
   $M_{max}$ — наибольший запас ячейки на старом слое (нефть; газ / $s_g$), из кэша `_old_inventories`. Отвергнуты:
   - «принимать застой линейного поиска на пределе округления» — точнее, когда оценка $\varepsilon_{маш}M_{max}$ сильно завышена, но сложнее: у ступени 4 нет линейного поиска, нужна своя логика, иначе 40 итераций впустую; меняется смысл отказа `line_search` DEBT-054;
   - «запрет коротких шагов и диагностика» — дефект остаётся, FEAT-032 и BUG-026 упираются в предел ~0.02–0.1 с;
   - (аудит 1, не обсуждался при планировании) предел по ячейке, $|F_i| \le \max(\varepsilon^{abs}, \kappa\varepsilon_{маш}M_i/\Delta t) + \varepsilon^{rel}\|F_0\|$. Он точнее при большом $R_{ext}$: шум идёт от ячеек, которые за шаг меняются, а $M_i$ крупнейшей может быть ни при чём. Но допуск перестаёт быть одним числом: отчёт DEBT-054 (`residual_tol`) и текст отказа адаптера сравнивают $\|F\|_\infty$ с одним допуском, их пришлось бы переделать. Цена варианта 2 ограничена: ошибка массы за шаг ≤ $\kappa\varepsilon_{маш}M_{max}$.

   Пользователь принял цену варианта: при сильно завышенной оценке Ньютон может остановиться на итерацию раньше. Ошибка массы за шаг при этом не больше $\kappa\varepsilon_{маш}M_{max}$ (Nabor_1b, Δt = 1e-3 с: 5.6e-12 м³ст вместо 3e-16).

---

## 1. Контекст и замеры

### 1.1. Механизм

**Невязка и условие.** Невязка прототипа — в м³ст/с (`blackoil.py`, `physical_residual`, `:258-260`):
$F_i = (M_i^{n+1} - M_i^{n})/\Delta t + q_i$, где запасы считает `component_inventories` (`:209-214`): нефть $V_p S_o/B_o$, газ $V_p(R_s S_o/B_o + S_g/B_g)$. Газовые строки делятся на $s_g$ = `gas_residual_scale` = $\max(R_{s,ext}, 1)$ (`residual`, `:261-262`).

Абсолютное условие сходимости (`ssec:convergence` постановки; код — `:373` в `_newton_fixed_active_set`, ступени 1–3, и `:596` в `_newton_switching`, ступень 4):
$\|F\|_\infty \le \varepsilon^{abs} + \varepsilon^{rel}\max(\|F_0\|_\infty, 10^{-9})$, $\varepsilon^{abs}$ = 1e-11 м³ст/с, $\varepsilon^{rel}$ = 1e-8. Условие по ячейке BUG-022 (`eq:newton_cell_tol`) от Δt не зависит и здесь ни при чём: в отказах ниже мера ячеек 3.8e-16…2.6e-11 при пороге 1e-8.

**Предел округления.** $M^{n+1}$ и $M^n$ вычисляются по отдельности, каждый с ошибкой ~$\varepsilon_{маш}M$. Ошибка разности от Δt не зависит, после деления на Δt невязка ниже ~$\varepsilon_{маш}M/\Delta t$ не опускается. При Δt ≲ 0.1 с это больше $\varepsilon^{abs}$.

**Как проявляется.** Линейный поиск ступеней 1–3 требует строгого уменьшения $\|F\|$. На пределе он не принимает ни одной точки (выход `line_search`, DEBT-054). У ступени 4 линейного поиска нет: она стоит на пределе 40 итераций (выход `max_iter`). Отказывают все четыре ступени `advance`, и `Simulator` дробит шаг до `dt/512` без толку.

### 1.2. Замеры планирования

Пробы — `vault/issues/bug-025/probes/`. Выходы `*.out.txt` лежат там же. Предел округления в допуске в режимах `fix` и `series` проб подставлен заменой методов класса, без правки прототипа, с той же арифметикой, что в шаге 3.

**Сценарий** `numerical_solver/tests/data/bug020_rs150/config.json`: $N$ = 350, $R_{ext}$ = 200 м, $r_w$ = 0.1 м, $h$ = 10 м, $\phi$ = 0.2, Стендинг, $R_{s0}$ = 150; 10 сут добычи при 3 МПа (интервал 1 сут — один шаг, ~1 с), затем $q_{oil}$ = 0. На конец добычи двухфазных ячеек 332, max $S_g$ = 0.441. $M_{max}$ = 7.205e3 м³ст (ячейка 349, внешняя; газ / $s_g$ — столько же). $\varepsilon_{маш}M_{max}$ = 1.600e-12 м³ст.

**(а) Первый шаг останова длины Δt без правки** (`floor_probe.py scan`, `scan_r200.out.txt`):

| Δt, с | advance | выход ступени 1 | итераций | $\|F\|$ | допуск | $\|F\|\cdot\Delta t$, м³ст |
|---|---|---|---|---|---|---|
| 0.439 | сошёлся, ст. 1 | converged | 4 | 2.37e-12 | 3.98e-11 | 1.04e-12 |
| 0.110 | сошёлся, ст. 1 | converged | 3 | 3.07e-11 | 3.98e-11 | 3.37e-12 |
| 0.0275 | сошёлся, ст. 1 | converged | 4 | 3.34e-11 | 3.98e-11 | 9.17e-13 |
| 0.01 | **отказ всех ступеней** | line_search | 6 | 7.13e-11 | 3.98e-11 | 7.13e-13 |
| 1e-3 | **отказ** | line_search | 8 | 4.95e-10 | 3.98e-11 | 4.95e-13 |
| 1e-4 | **отказ** | line_search | 5 | 5.95e-9 | 3.98e-11 | 5.95e-13 |

- $\|F\|\cdot\Delta t$ на остановке Ньютона почти постоянен (5–7e-13 м³ст). Предел округления действительно $\propto 1/\Delta t$.
- Максимум $|F|$ на остановке — в ячейках 307–331 (крупные, у внешней границы), а не у забоя.
- Ступень 4 отдельно (`advance_fourth_stage`, `stage4_short.out.txt`): при 1e-2, 1e-3, 1e-4 с — 40 итераций, выход `max_iter`, $\|F\|$ = 7.5e-11, 9.6e-10, 7.7e-9.

**(б) Почему в VAL-004 отказывал шаг 0.0549 с, а здесь он сходится.** В VAL-004 отказ случился не на первом подшаге останова. После нескольких принятых подшагов приток к забою спадает, и с ним $\|F_0\|$: допуск падает с 3.98e-11 до 1.33e-11, а предел округления прежний. Повтор исходной команды на `015a297` (`floor_probe.py series 0 6 9`, `series_k0_6-9.out.txt`): $k$ = 6 (первый шаг 0.110 с) проходит, $k$ = 7 (0.0549 с) падает. Последний отказ: «dt = 1.073e-04 с, итераций 4, невязка 5.00e-09 (допуск 1.33e-11), мера ячеек 2.60e-11 … выход: линейный поиск не принял ни одной точки — не выполнено только абсолютное условие». Минимальное воспроизведение на уровне `Simulator` (`floor_probe.py repro 0 16 <dt>`, `repro_nabor.out.txt`): 16 интервалов по 0.0549 с — отказ на 5-м шаге (t − 10 сут = 0.22 с); по 0.01 с — на первом; расчёт падает за ~4.5 с.

**(в) Масштаб по $R_{ext}$** (`scan_r50.out.txt`, `scan_r800.out.txt`):

| $R_{ext}$, м | $M_{max}$, м³ст | $\varepsilon_{маш}M_{max}$ | $\|F\|\cdot\Delta t$ на остановке | доля от $\varepsilon_{маш}M_{max}$ | граница Δt (первый шаг) |
|---|---|---|---|---|---|
| 50 | 370 | 8.2e-14 | 5.5e-14 | 0.67 | между 1e-4 и 1e-3 с |
| 200 | 7.2e3 | 1.6e-12 | 5–7e-13 | 0.3–0.45 | между 0.01 и 0.027 с |
| 800 | 1.36e5 | 3.0e-11 | 2.1–2.7e-12 | 0.07–0.09 | между 0.027 и 0.055 с |

Предел округления растёт с $R_{ext}$ заметно медленнее, чем $M_{max}$. Вероятная причина: за малый Δt давление меняется не во всех ячейках, а в ячейке с побитово прежним состоянием разность запасов ровно ноль. **Поэтому $\varepsilon_{маш}M_{max}$ — верхняя оценка предела округления.** Оценка issue «при $R_{ext}$ = 1 км критический шаг ~5 с» завышена: по замеру при 800 м граница первого шага ~0.03–0.05 с.

**(г) С пределом округления в допуске, κ = 4** (`fix_k4_r200.out.txt`, `fix_k4_r800.out.txt`, `fix_k4_r50.out.txt`): при всех Δt от 0.44 до 1e-4 с и $R_{ext}$ = 50, 200, 800 м `advance` сходится **первой ступенью** за 1–5 итераций; $\|F\|\cdot\Delta t \le$ 1.0e-11 м³ст (наибольшее — $R_{ext}$ = 800 м, Δt = 1e-4 с, 1 итерация). При κ = 1 запас мал: $R_{ext}$ = 50 м, Δt = 1e-3 с — невязка 8.0e-11 при допуске 1.16e-10 (`fix_k1_r50.out.txt`). Ступень 4 отдельно при κ = 4 (`stage4_short.out.txt`): 1e-2, 1e-3, 1e-4 с — сошлась за 3, 2, 2 итерации; допуск тот же, что у ступени 1 (6.697e-10, 6.429e-9, 6.402e-8).

**(д) Ряд VAL-004 продолжается** (`floor_probe.py series 4 6 9`, `series_k4_6-9.out.txt`; первый час нарастающими шагами от $3600/2^{9+k}$, без отказов):

| $k$ | первый шаг, с | $R_s(r_w)$ на 1 ч | $p(r_w)$, бар | $T(r_w)$, К | счёт, с |
|---|---|---|---|---|---|
| 6 | 0.1099 | 40.6122232 (без предела округления 40.6122229) | 185.4210591 | 398.0221281 | 27 |
| 7 | 0.0549 | 40.9026572 | 185.4411049 | 398.0227055 | 44 |
| 8 | 0.0275 | 41.0521992 | 185.4511178 | 398.0229940 | 78 |
| 9 | 0.0137 | 41.1284813 | 185.4561224 | 398.0231382 | 162 |

Разности $R_s$: 0.290, 0.150, 0.076 — порядок → 1, предел ≈ 41.20. Это совпадает с оценкой VAL-004 (≈ 41.2), полученной по $k$ = 4…6. Данные для BUG-026 и FEAT-032 (шаг 6).

**(е) Где предел округления меняет допуск.** Предел округления меняет допуск решения, только если κ > κ* = $\varepsilon^{abs}\Delta t/(\varepsilon_{маш}M_{max})$; иначе `max` возвращает $\varepsilon^{abs}$ тем же числом.
- Все решения Ньютона во всех 23 примерах и трёх сценариях тестов с мелкими шагами (`census.py`, `census.out.txt`): наименьшее κ* = **63.1** (пример 18, шаг 10 с), у остальных ≥ 2950. Решений с κ* < 4 — ни одного.
- Регрессия прототипа (`census_regression.py`, `census_regression.out.txt`; $M_{max}$ — по начальному состоянию и давлению границы, Δt — наименьший шаг эталонного `step_log.csv`): наименьшее κ* = **34.3** (T05S_N200_DT5m, 2.81 с); T03 — 37.5.
- Тесты с короткими шагами: `tests/test_val004.py` (первые шаги 0.11–0.44 с, κ* < 4) — допуск меняется. Тесты там проверяют порядок и пределы $p$, $T$ с допусками 1e-3 бар / 5e-4 К и побитовое совпадение дробления с более мелкой серией: предел округления — функция старого состояния и Δt, у обеих серий он одинаков. $R_s(r_w)$ при $k$ = 6 сдвинулся на 3e-7; $p$, $T$ совпали до 7 знаков. Остальные тесты — шаги ≥ 168.75 с.

**(ж) Добыча и грубая сетка (аудит 1, `ramp_with_floor.py`, `ramp_with_floor.out.txt`).** План FEAT-032 нашёл тот же предел округления на старте добычи. В его эмуляции (нарастающий шаг после смены управления, $h_0$ = 0.44 с) падали примеры 15 и 13b: $N$ = 50, внешняя ячейка в ~6 раз крупнее, чем при $N$ = 350. Пример 15: «невязка 1.26e-11 (допуск 1.03e-11) … не выполнено только абсолютное условие», дробление до 8.6e-4 с не помогает. На глубоких подшагах выход `max_iter` (15 итераций на пределе округления), а не только `line_search`. $|F|\cdot\Delta t$ = 4.9–5.5e-12 м³ст = (0.41–0.45)$\varepsilon_{маш}M_{max}$ ($M_{max}$ = 5.49e4). Пробой FEAT-032 с подменой допуска (предел округления, κ = 4):

| пример | без предела округления | с пределом округления, κ = 4 |
|---|---|---|
| 15, $h_0$ = 0.44 с | отказ при $t$ = 2 сут + 0.44 с | 0 отказов, 542 подшага, отпечаток `5d462f35ce3e39b9` |
| 13b, $h_0$ = 0.44 с | 0 отказов, `7551ba45d679a11b` | 0 отказов, `f5e0ec0140f3b420` (предел округления сработал на подшагах 0.44 с) |
| 15, 13b, 19 штатно (`orig`) | `a6e91358e1482446`, `041bc876f88d8cd1`, `bc6b6a0079e71ea9` | те же — побитово |

Граница шага зависит от сетки: при $N$ = 350, $R_{ext}$ = 200 м — ~0.01–0.05 с, при $N$ = 50 ($R_{ext}$ примеров 12–16) — ~0.5 с. Формулировки «при Δt ≲ 0.1 с» в постановке, коде и CHANGELOG поэтому заменены на зависящие от сетки.

**Ожидание:** истории всех примеров и сценариев, тесты прототипа и регрессия 17/17 — побитово; `test_val004.py` — зелёный. Регрессия на базе: 17/17 PASS при реализации DEBT-054 (`431d3c6`); код прототипа после этого не менялся, поэтому её прогон до правки не нужен.

### 1.3. Что не меняется

Уравнения невязки, $\varepsilon^{abs}$ и $\varepsilon^{rel}$, условие по ячейке BUG-022, линейные поиски, ограничения шага Ньютона, логика ступеней `advance`, адаптер (`prototype_adapter.py`) и `Simulator`. Текст отказа уже печатает фактический допуск (`residual_tol`, DEBT-054), и править его не нужно. Поля конфига не добавляются: κ — константа прототипа.

### 1.4. Связь формула → код

| Формула | Код | Тест |
|---|---|---|
| `eq:newton_abs_tol` (новая, шаг 1) — абсолютное условие с пределом округления | `blackoil.py`: `ROUNDOFF_KAPPA`, `_EPS`, `RadialBlackOilModel._absolute_tol`; вызовы в `_newton_fixed_active_set`, `_newton_switching` | `tests/test_prototype_residual_floor.py`; прототип — `tests/test_residual_floor.py` |
| `eq:residual_oil`, `eq:residual_gas` — накопление $(M^{n+1}-M^n)/\Delta t$ | `physical_residual`, `component_inventories`, `_old_inventories` | без изменений |
| `eq:newton_cell_tol` | `_cell_weights`, `_cell_measure`, `_cells_converged` | без изменений |

---

## 2. Подводные камни

| Пункт | Оценка | Чем адресован |
|---|---|---|
| Побочные эффекты | ✅ | `_absolute_tol` новая. Вызовы `_newton_fixed_active_set`: `_advance_phases` (все ступени 1–3), тесты `test_prototype_cell_tolerance.py`, `test_prototype_failure_diagnostics.py`, прототип `test_newton_last_iteration.py`. `_newton_switching`: `_advance_phases` при `_phase_switching`, тесты. Сигнатуры не меняются. |
| Граничные случаи | ✅ | Δt > 0 всегда (`advance` не зовётся с 0). Запасы старого слоя ≥ 0; `np.abs` — страховка, `max` неотрицательных он не меняет. Однофазное состояние: газ = $R_s\cdot$нефть, учитывается через / $s_g$. $N$ = 1: `np.max` по одному элементу. |
| Производительность | ✅ | Два `np.max` по $N$ на решение Ньютона; запасы — из кэша (`_old_inventories` по ключу байтов, DEBT-036). |
| Обратная совместимость | ✅ | `max(atol, предел)` при пределе ≤ atol возвращает atol тем же числом: допуск и решения побитово прежние. Перепись 1.2(е): ни одно решение примеров и регрессии не затронуто. |
| Порядок вызовов | ✅ | В `_newton_fixed_active_set` `residual(z,…)` (`:372`) уже заполнил кэш до допуска; в `_newton_switching` `residual` стоит в той же строке раньше (`:596`). Кэш даёт те же значения при любом порядке. |
| Состояние при ошибке | ✅ | Метод ничего не пишет в модель, кроме кэша запасов (как и `residual`). |
| Численная устойчивость | ⚠️ | Оценка $\varepsilon_{маш}M_{max}$ — верхняя (1.2(в)): при большом $R_{ext}$ допуск на коротком шаге шире реального шума. Ошибка массы за шаг ограничена $\kappa\varepsilon_{маш}M_{max}$ (решение пользователя, раздел 0). Малые ячейки защищает условие по ячейке BUG-022 (в GPN включено, 1e-8). |
| Связь с задачами | ⚠️ | DEBT-055 — тот же механизм для условия по ячейке, его предел округления от Δt не зависит; здесь не решается. FEAT-032 (#103), BUG-026 — этим исправлением разблокируются (шаг 6). **FEAT-032 в реализации параллельно** (`.worktrees/feat-032`, аудит 2): если она влита раньше, предел округления меняет историю примера 16 — проверка в «Как начать», п. 5 (аудит 1). Её ветка правит `bc.py`, `io/config.py`, `simulator.py`, `factory.py`, `test_config.py`, `test_rate_control.py`, `test_simulator.py`, `test_val004.py` и конфиги 16/17 — не файлы этого плана; конфликт только в vault (записи FEAT-032, BUG-025, BUG-026). Её новый `TestRampAfterShutIn` (сценарий `bug020_rs150`, $h_0$ = 2 с, первый подшаг 1.76 с, κ* ≈ 11 > 4) пределом округления не затрагивается. Если BUG-025 влита первой, а FEAT-032 ещё в работе, её П15 требует перемерить числа на новой базе — об этом комментарий в #103 (шаг 6). DEBT-065 (в реализации, `.worktrees/debt-065`) правит радиус изобары в диагностике — не пересекается. BUG-028 (старт добычи 19, 21): на его последних подшагах ≲ 0.01 с стоит предел округления BUG-025, но главный отказ — набор фаз; правка его не закрывает (шаг 6 — отметка в записи). DEBT-011 влита (`7f8d879`, аудит 2): `blackoil.py`, постановку и тесты плана не тронула, числа плана на новой базе те же. |
| Быстрый отказ → долгий счёт (аудит 1) | ⚠️ | Правка делает разрешимыми самые мелкие подшаги. Если подшаги покрупнее отказывают по **другой** причине, вместо `RuntimeError` на дне дробления идёт счёт мелкими подшагами. Замер (`ramp_with_floor_19.out.txt`): пример 19, эмуляция FEAT-032 с нарастанием на старте добычи (BUG-028). Без предела округления в допуске — отказ за ~3 с, с ним — ~35 мин без результата, прогон остановлен. В штатном `Simulator` счёт ограничен: не больше $2^{\text{max\_retries}}$ подшагов на шаг (`simulator.py:260`), при 9 — 512. Это возможно лишь при `dt_integration`/512 ниже границы предела округления (~0.01–0.5 с), то есть в нештатных конфигах. В нарастании FEAT-032 единица дробления — $dt/2^{\text{max\_retries}+m}$, и предела фактически нет. Предпосылка плана FEAT-032 «отказ при слишком малом $h_0$ — понятный `RuntimeError`» (его П4) после BUG-025 неверна. Код этого плана не меняется; факт — в записи FEAT-032 и BUG-028 (шаг 6). |
| Import-цепочки | ✅ | Новое имя `ROUNDOFF_KAPPA` в `radial_blackoil.blackoil`; GPN-тест читает его в теле тестов (`blackoil.ROUNDOFF_KAPPA`), не при импорте, — до шага 3 падают отдельные тесты, а не сбор модуля. |
| Соответствие формулам | ✅ | Шаг 1 вводит `eq:newton_abs_tol`; код шага 3 — та же формула; тест сверяет допуск отчёта с формулой побитово. |
| Прототип | ⚠️ | Меняется `radial_blackoil/blackoil.py` → тесты прототипа (97 → 101) и регрессия: `--quick` после шага 3, полная в шаге 5. Ожидание — 11/11 и 17/17 PASS побитово (κ* ≥ 34 > 4). FAIL — не пересъёмка эталона: разобрать (раздел «Правка прототипа» команды), решение за пользователем. Запись в `CHANGELOG_1.0.3.md` — шаг 4. |

**Новых проблем при планировании не найдено.** Исправлена оценка issue (1.2(в)) — комментарием в issue (раздел «Сохранение»).

---

## 3. Шаги

### Шаг 1: постановка — абсолютное условие с пределом округления

**Цель:** формула с меткой `eq:newton_abs_tol` до кода и тестов (на метку ссылаются докстринги шагов 2–3; `tests/test_eq_references.py` требует, чтобы метка была в `.tex`).
**Файлы:** `numerical_solver/doc/problem_statement.tex`.

**Контекст:** абсолютное условие записано без номера (`\[ … \]`, строки ~2134-2143 на `015a297`), ссылаться на него меткой нельзя.

**Что сделать:** в `\subsection{Критерии сходимости}\label{ssec:convergence}` заменить абзац «\emph{Абсолютное} …» до «\emph{По~ячейке:}» (не включая).

**Изменения.**
До:
```latex
\emph{Абсолютное} (по всей сетке, невязки~--- в~м$^3$ст/с):
\[
  \max_j \max\Bigl(|F_j^{\text{oil}}|,\ \frac{|F_j^{\text{gas}}|}{s_g}\Bigr)
  \leqslant \varepsilon^{\text{abs}} + \varepsilon^{\text{rel}}\max\bigl(\|F_0\|_\infty,\,10^{-9}\bigr),
\]
где $s_g = \max(R_{s,\text{ext}}, 1)$~--- масштаб газовой невязки,
$\|F_0\|_\infty$~--- та~же норма на~начальном приближении,
$\varepsilon^{\text{abs}} = 10^{-11}$~м$^3$ст/с, $\varepsilon^{\text{rel}} = 10^{-8}$.
Значения заданы в~решателе; поля \texttt{newton\_atol}, \texttt{newton\_rtol}
конфигурационного файла ему не~передаются.
```
После:
```latex
\emph{Абсолютное} (по всей сетке, невязки~--- в~м$^3$ст/с):
% BUG-025: второй член под max — предел округления накопления; до исправления
% допуск был eps_abs + eps_rel*max(||F_0||, 1e-9), и шаг короче ~0.05 с на старте
% останова не сходился ни при каком дроблении.
\begin{equation}\label{eq:newton_abs_tol}
  \boxed{\max_j \max\Bigl(|F_j^{\text{oil}}|,\ \frac{|F_j^{\text{gas}}|}{s_g}\Bigr)
  \leqslant \max\Bigl(\varepsilon^{\text{abs}},\
    \kappa\,\frac{\varepsilon_{\text{маш}} M_{\max}}{\Delta t}\Bigr)
  + \varepsilon^{\text{rel}}\max\bigl(\|F_0\|_\infty,\,10^{-9}\bigr),}
\end{equation}
где $s_g = \max(R_{s,\text{ext}}, 1)$~--- масштаб газовой невязки,
$\|F_0\|_\infty$~--- та~же норма на~начальном приближении,
$\varepsilon^{\text{abs}} = 10^{-11}$~м$^3$ст/с, $\varepsilon^{\text{rel}} = 10^{-8}$,
$M_{\max} = \max_j \max\bigl(M_j^{\text{oil}},\ M_j^{\text{gas}}/s_g\bigr)$~--- наибольший
запас ячейки на~слое~$n$ (м$^3$ст; $M_j^{\text{oil}}$, $M_j^{\text{gas}}$~--- величины,
разность которых стоит в~числителях накопления \eqref{eq:residual_oil},
\eqref{eq:residual_gas}, умноженные на~$V_j\phi$), $\varepsilon_{\text{маш}} = 2.2\cdot10^{-16}$,
$\kappa = 4$. Значения заданы в~решателе; поля \texttt{newton\_atol},
\texttt{newton\_rtol} конфигурационного файла ему не~передаются.

Второй член под~$\max$~--- предел округления. Накопление~--- разность запасов, делённая
на~шаг; каждый запас вычисляется с~ошибкой $\sim\varepsilon_{\text{маш}} M_j$, и~ниже
$\sim\varepsilon_{\text{маш}} M_{\max}/\Delta t$ невязка не~опускается. На~коротких шагах
это больше $\varepsilon^{\text{abs}}$; граница растёт с~размером крупнейшей ячейки:
$\sim$0.01--0.05~с при~$N = 350$, $\Rext = 200$~м и~$\sim$0.5~с при~$N = 50$. На~старте
останова после добычи с~развитой газовой зоной ($N = 350$, $\Rext = 200$~м,
$M_{\max} = 7.2\cdot10^{3}$~м$^3$ст) линейный поиск вставал при
$\|F\|_\infty\Delta t \approx (5\text{--}7)\cdot10^{-13}$~м$^3$ст, и~шаг
$10^{-2}\text{--}10^{-4}$~с не~сходился ни~при каком дроблении; при~$N = 50$ на~старте
добычи так же не~сходился подшаг 0.44~с. Замеренный предел~---
$(0.07\text{--}0.7)\,\varepsilon_{\text{маш}} M_{\max}$: ячейки, состояние которых за~шаг
не~изменилось, ошибки не~вносят; оценка по~$M_{\max}$~--- верхняя. При~шагах от~секунд
и~больше $\max$ даёт $\varepsilon^{\text{abs}}$ (в~примерах и~регрессии прототипа предел
округления ниже $\varepsilon^{\text{abs}}$ не~менее чем в~$34/\kappa$ раз). Решение, принятое
по~пределу округления, ошибается в~массе за~шаг не~более чем на~$\kappa\,\varepsilon_{\text{маш}} M_{\max}$.
```
`\Rext` — макрос постановки (есть в документе: `\paragraph{Контур питания ($r = \Rext$, …`).

**Проверка после шага:**
- Сборка (из `<worktree>\numerical_solver\doc`): `pdflatex -interaction=nonstopmode problem_statement.tex` дважды. Нет `Undefined control sequence`, нет `undefined references` (`Select-String -Path problem_statement.log -Pattern "undefined|Undefined"`). PDF не коммитится.
- Тест: `& $PY -m pytest tests/test_eq_references.py -q` → 2 passed.
- Регресс: `--collect-only -q` (меняется только документ) → 1826.

**Подводные камни:** нумерация уравнений ниже сдвигается на 1 — ссылки в коде по меткам (DEBT-010), не страдают. Формула в `\boxed{}` длиннее соседней `eq:newton_cell_tol`. Проверить в `problem_statement.log` строку `Overfull \hbox` у этого уравнения; при переполнении — разбить на две строки: `\boxed{\begin{aligned} … &\leqslant \max\Bigl(…\Bigr) \\ &\quad + \varepsilon^{\text{rel}}\max(…) \end{aligned}}` (аудит 1). **Замер аудита 2** (`audit2/tex_step1.py` — блок «До → После» на копии постановки, `pdflatex` дважды): блок «До» найден дословно, сборка без ошибок и неопределённых ссылок, формула **помещается**. Новый абзац пояснения даёт `Overfull \hbox` на 10 pt (длинные строчные формулы не переносятся). В документе таких переполнений 19, до 104 pt; править не обязательно.
**Зависимости:** Блокирует: шаги 2, 3.
**Оценка:** ~35 строк `.tex`, ~15 мин.

---

### Шаг 2: тесты-воспроизводители (красные до шага 3)

**Цель:** зафиксировать дефект тестами GPN и прототипа до правки.
**Файлы:** `numerical_solver/tests/test_prototype_residual_floor.py` (новый), `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_residual_floor.py` (новый).

**Контекст:** воспроизведения быстрые (1.2(б)): конец добычи сценария `bug020_rs150` — ~1 с, расчёт `Simulator` с 16 короткими интервалами — ~1 с после правки (до правки ~4.5 с до отказа). На кейсе прототипа Nabor_1b дефект **не** воспроизводится: из однородного состояния дальние ячейки за малый шаг не меняются, шума нет (`repro_nabor.out.txt`). Поэтому тест прототипа проверяет формулу `_absolute_tol`, а воспроизведение — в тестах GPN.

**Что сделать — 1. `numerical_solver/tests/test_prototype_residual_floor.py`:**
```python
"""BUG-025: допуск Ньютона прототипа не ниже предела округления накопления — короткий шаг останова сходится.

Невязка прототипа — в м³ст/с: накопление (M^{n+1} - M^n)/Δt, каждый запас — с ошибкой
округления ~ε_маш·M. Ниже ~ε_маш·M_max/Δt невязка не опускается, и на коротком шаге это
больше абсолютного допуска 1e-11 м³ст/с (граница — от ~0.01–0.05 с при N = 350 до ~0.5 с
при N = 50: растёт с крупнейшей ячейкой). На старте останова после 10 сут добычи
(bug020_rs150, M_max = 7.2e3 м³ст) линейный поиск вставал при |F|·Δt = 5–7e-13 м³ст,
отказывали все четыре ступени advance, дробление до dt/512 не помогало. Теперь допуск —
max(1e-11, κ·ε_маш·M_max/Δt) + 1e-8·max(‖F₀‖, 1e-9), κ = 4 (Ур. (eq:newton_abs_tol)
problem_statement.tex); M_max — наибольший запас ячейки старого слоя (нефть; газ / s_g).

План: vault/plans/bug-025 short-step-residual-floor.md; замеры —
vault/issues/bug-025/probes/*.out.txt.
"""

import copy
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.hydro.base import HydroConvergenceError
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.units import BAR_TO_PA, DAY_TO_S
from radial_blackoil import blackoil
from radial_blackoil.state import BlackOilState

CFG = Path(__file__).parent / "data" / "bug020_rs150" / "config.json"
N_PROD = 10                       # интервалов добычи в конфиге, по 1 сут
ATOL, RTOL = 1e-11, 1e-8          # умолчания обоих Ньютонов прототипа (atol_sm3s, rtol)
EPS = float(np.finfo(float).eps)
SHORT_DTS = (1e-2, 1e-3, 1e-4)    # до BUG-025 все три — отказ всех ступеней advance


def _m_max(model, state):
    """M_max теми же операциями, что _absolute_tol прототипа: нефть и газ / s_g старого слоя, м³ст."""
    oi0, gi0 = model._old_inventories(state)
    return max(float(np.max(np.abs(oi0))), float(np.max(np.abs(gi0))) / model.gas_residual_scale)


def _tol(model, state, dt):
    """Допуск Ньютона из старого состояния по Ур. (eq:newton_abs_tol) — те же операции, что в прототипе."""
    z0 = model.pack(state)
    f0 = model.residual(z0, state, dt, state.gas_active)
    floor = max(ATOL, blackoil.ROUNDOFF_KAPPA * EPS * _m_max(model, state) / float(dt))
    return floor + RTOL * max(float(np.linalg.norm(f0, np.inf)), 1e-9)


@pytest.fixture(scope="module")
def shutin():
    """Модель фабрики и состояние прототипа на конец 10 сут добычи; управление — останов q_oil = 0 (~1 с)."""
    cfg = load_config(CFG)
    shut = cfg.time.history[N_PROD]
    cfg.time.history = cfg.time.history[:N_PROD]
    sim, s0 = SimulatorFactory.from_config(cfg)
    st = sim.run(s0).states[-1]
    model = sim._hydro._model
    # Управление — как ставит адаптер перед advance (prototype_adapter.solve, шаг 1): м³ст/сут, бар
    model.set_oil_rate_control(shut.q_oil * DAY_TO_S, shut.min_bhp / BAR_TO_PA)
    ps = BlackOilState(pressure_bar=st.p / BAR_TO_PA, rs_sm3_sm3=st.Rs.copy(),
                       sg=st.Sg.copy(), gas_active=(st.regime == 1))
    return model, ps


# ═══════════════════════════════════════════════════════════
# A. Формула допуска
# ═══════════════════════════════════════════════════════════

class TestToleranceFloor:
    """Предел округления включается только на коротком шаге; на обычном допуск прежний побитово."""

    def test_long_step_tolerance_unchanged(self, shutin):
        """Δt = 3600 с: κ·ε·M_max/Δt = 1.8e-15 < 1e-11 — допуск atol + rtol·‖F₀‖, как до BUG-025, побитово.

        Ловит: предел, сложенный с atol вместо max (допуск сдвинулся бы на всех шагах,
        истории примеров — не побитово).
        """
        model, ps = shutin
        dt = 3600.0
        f0 = model.residual(model.pack(ps), ps, dt, ps.gas_active)
        _, rep = model._newton_fixed_active_set(model.pack(ps), ps, dt, ps.gas_active)
        assert rep.residual_tol == ATOL + RTOL * max(float(np.linalg.norm(f0, np.inf)), 1e-9)

    def test_short_step_tolerance_floor(self, shutin):
        """Δt = 1e-3 с: допуск — по Ур. (eq:newton_abs_tol), 6.43e-9 против 3.98e-11 без предела (замер).

        Ловит: M_max не по старому слою, газовые строки без деления на s_g, другой κ,
        предел только в одной из функций Ньютона.
        """
        model, ps = shutin
        dt = 1e-3
        _, rep = model._newton_fixed_active_set(model.pack(ps), ps, dt, ps.gas_active)
        assert rep.residual_tol == _tol(model, ps, dt)
        assert rep.residual_tol > 100 * ATOL


# ═══════════════════════════════════════════════════════════
# B. Первый шаг останова
# ═══════════════════════════════════════════════════════════

class TestShortShutinStep:
    """Первый шаг останова 1e-2…1e-4 с из конца добычи (332 двухфазных ячейки, max S_g = 0.441)."""

    @pytest.mark.parametrize("dt", SHORT_DTS)
    def test_first_stage_converges(self, shutin, dt):
        """advance сходится первой ступенью; ошибка массы за шаг не больше κ·ε·M_max.

        Замер (fix_k4_r200.out.txt): 3, 2, 2 итерации, |F|·Δt = 1.07e-12, 1.12e-12,
        8.95e-13 м³ст при κ·ε·M_max = 6.4e-12. До исправления — отказ всех ступеней,
        ступень 1 — выход 'line_search' (scan_r200.out.txt).
        """
        model, ps = shutin
        _, rep = model.advance(ps.copy(), dt)
        assert rep.converged and rep.exit_reason == "converged"
        assert not rep.fallback and not rep.phase_switching
        assert rep.residual_inf <= rep.residual_tol
        assert rep.residual_inf * dt <= blackoil.ROUNDOFF_KAPPA * EPS * _m_max(model, ps)

    def test_fourth_stage_short_step(self, shutin):
        """Ступень 4 отдельно (её зовёт адаптер по памяти, DEBT-048) на Δt = 1e-3 с сходится с тем же допуском.

        Замер (stage4_short.out.txt): 2 итерации, допуск 6.429e-9; до исправления —
        40 итераций на пределе, выход 'max_iter'. Ловит предел только в ступенях 1–3.
        """
        model, ps = shutin
        dt = 1e-3
        _, rep = model.advance_fourth_stage(ps.copy(), dt)
        assert rep.converged and rep.exit_reason == "converged" and rep.phase_switching
        assert rep.residual_tol == _tol(model, ps, dt)


# ═══════════════════════════════════════════════════════════
# C. Simulator: останов короткими интервалами
# ═══════════════════════════════════════════════════════════

class TestShortShutinIntervals:
    """10 сут добычи + 16 интервалов останова по dt: каждый — один шаг, без отказов гидродинамики."""

    @pytest.mark.parametrize("dt", [3600.0 / 2 ** 16, 0.01])
    def test_no_hydro_failures(self, dt):
        """dt = 3600/2**16 = 0.0549 с — первый шаг серии k = 7 VAL-004; 0.01 с.

        До исправления (repro_nabor.out.txt): отказ гидродинамики на 5-м шаге (0.0549 с; к
        тому времени приток к забою спал, ‖F₀‖ и с ним допуск упали до 1.33e-11) и на
        первом (0.01 с), дробление до dt/512 не помогало, расчёт падал. После: 0 отказов.
        """
        cfg = load_config(CFG)
        prod, shut = cfg.time.history[:N_PROD], cfg.time.history[N_PROD]
        tail = []
        for _ in range(16):
            x = copy.deepcopy(shut)
            x.dt = dt
            tail.append(x)
        cfg.time.history = list(prod) + tail
        # dt_integration = 1 сут длиннее интервала: каждый интервал — один шаг, если сошёлся
        assert cfg.time.dt_integration > dt
        sim, s0 = SimulatorFactory.from_config(cfg)
        fails = []
        solve = sim._hydro.solve

        def counting(state, h, bc):
            try:
                return solve(state, h, bc)
            except HydroConvergenceError:
                fails.append((state.t, h))
                raise

        sim._hydro.solve = counting
        hist = sim.run(s0)
        assert fails == []
        assert len(hist.times) == 1 + N_PROD + 16
        # время копится сложением t + dt: ulp(8.64e5 с) = 1.2e-10, 16 сложений — до ~1e-9
        assert hist.times[-1] == pytest.approx(N_PROD * DAY_TO_S + 16 * dt, abs=1e-6)
```

**Что сделать — 2. `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_residual_floor.py`** (стиль тестов прототипа — `unittest`, комментарии по-английски):
```python
import unittest, numpy as np
from tests.helpers import model_and_state
from radial_blackoil import blackoil

# BUG-025: the absolute Newton tolerance is not below the round-off floor of the storage
# term, max(atol, ROUNDOFF_KAPPA*eps*M_max/dt), M_max -- the largest cell inventory of
# state_old (oil rows, gas rows / gas_residual_scale).  Without it a GPN shut-in step
# shorter than ~0.05 s stalled at |F|*dt = 5-7e-13 m3st and no stage of advance converged.
# The defect itself needs a developed transient (GPN tests); on Nabor_1b from a uniform state
# far cells do not change in a short step and carry no round-off.  These tests check the formula.
EPS=float(np.finfo(float).eps); ATOL=1e-11

def _m_max(m,s):
    oi,gi=m._old_inventories(s)
    return max(float(np.max(np.abs(oi))),float(np.max(np.abs(gi)))/m.gas_residual_scale)

class ResidualFloorTests(unittest.TestCase):
    def test_long_step_returns_atol(self):
        # dt = 1 h: the floor 4*eps*3.8e4/3600 = 9e-15 is below atol, so the tolerance is atol
        # itself and every solve is bitwise the former one
        _,m,s=model_and_state(n=12)
        self.assertEqual(m._absolute_tol(s,3600.0,ATOL),ATOL)
    def test_short_step_floor(self):
        # dt = 1 ms: the floor 3.4e-8 m3st/s is above atol
        _,m,s=model_and_state(n=12); dt=1e-3
        tol=m._absolute_tol(s,dt,ATOL)
        self.assertEqual(tol,blackoil.ROUNDOFF_KAPPA*EPS*_m_max(m,s)/dt); self.assertGreater(tol,100*ATOL)
    def test_gas_rows_scaled(self):
        # Undersaturated state: gas inventory = Rs*oil inventory; with gas_residual_scale = 1 the
        # gas rows set M_max, with the default scale (Rs_ext) both rows give the same value
        _,m,s=model_and_state(n=12); dt=1e-3
        oil=float(np.max(m._old_inventories(s)[0]))
        m.gas_residual_scale=1.0
        tol=m._absolute_tol(s,dt,ATOL)
        self.assertEqual(tol,blackoil.ROUNDOFF_KAPPA*EPS*_m_max(m,s)/dt)
        self.assertGreater(tol,blackoil.ROUNDOFF_KAPPA*EPS*oil/dt)
    def test_newton_reports_floored_tolerance(self):
        # _newton_fixed_active_set reports tol = _absolute_tol + rtol*max(||F0||, 1e-9)
        _,m,s=model_and_state(n=12); dt=1e-3; z0=m.pack(s)
        f0=m.residual(z0,s,dt,s.gas_active)
        _,rep=m._newton_fixed_active_set(z0,s,dt,s.gas_active)
        self.assertEqual(rep.residual_tol,m._absolute_tol(s,dt,ATOL)+1e-8*max(np.linalg.norm(f0,np.inf),1e-9))

if __name__=='__main__': unittest.main()
```
Проверено при планировании (`model_and_state(n=12)`): $R_s$ = 50 = $s_g$, запас нефти max 3.78e4, газа 1.89e6 м³ст. При $s_g$ = 1 газовые строки дают $M_{max}$ в 50 раз больше нефтяных. Предел при 3600 с — 9.3e-15, при 1e-3 с — 3.36e-8.

**Проверка после шага (до правки кода — красные):**
- Проверено в аудите 2 (`audit2/extract.py` извлекает оба блока дословно, `audit2/emulate_step3.py` подставляет шаг 3): исходы ниже совпали; до правки — 13 с, с правкой — 8 passed за 4 с; тесты прототипа — 4 failed / 4 passed за 1 с.
- `& $PY -m pytest tests/test_prototype_residual_floor.py -q` → ожидается: `test_long_step_tolerance_unchanged` — passed; `test_short_step_tolerance_floor` — AttributeError (`ROUNDOFF_KAPPA`); `test_first_stage_converges[*]` (3) — assert `rep.converged`; `test_fourth_stage_short_step` — assert `rep.converged`; `test_no_hydro_failures[*]` (2) — `RuntimeError` из `sim.run`. Итого 1 passed, 7 failed.
- Из `HydroSolverPrototype\Prototype_1.0.3`: `& $PY -m pytest tests/test_residual_floor.py -q` → 4 failed (AttributeError `_absolute_tol` / `ROUNDOFF_KAPPA`).
- Регресс: не запускать (красные — по плану).
- **Коммит:** шаг 2 отдельно не коммитится. Красные тесты уходят одним коммитом с правкой шага 3, чтобы в истории ветки не было коммита с падающими тестами (аудит 1).

**Подводные камни:** `blackoil.ROUNDOFF_KAPPA` читается в теле тестов, не при импорте (раздел 2, «Import-цепочки»).
**Зависимости:** Требует: шаг 1 (метка). Блокирует: шаг 3.
**Оценка:** ~190 строк тестов, ~30 мин.

---

### Шаг 3: правка прототипа — `_absolute_tol` в обоих Ньютонах

**Цель:** допуск по `eq:newton_abs_tol`.
**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`.

**Контекст:** раздел 1.1. Арифметика — та же, что у подмены в пробе (`floor_probe.py`, `patch`): `ROUNDOFF_KAPPA*_EPS*m/float(dt_s)` — слева направо `((4.0*eps)*m)/dt`, `m` — тем же выражением. Тогда числа шага 5 совпадут с замерами 1.2(г), (д) побитово.

**Что сделать:**
1. Докстринг модуля (после абзаца DEBT-054, строка ~37) — абзац:
   ```
   BUG-025: the absolute Newton tolerance is not below the round-off floor of the storage
   term, max(atol, ROUNDOFF_KAPPA*eps*M_max/dt) (_absolute_tol): a shut-in step shorter than
   ~0.05 s after production with a developed gas zone failed every stage of advance.
   ```
2. После `from .units import …` (строка ~45) — константы:
   ```python
   # BUG-025: machine epsilon and the factor of the round-off floor of the absolute Newton
   # tolerance (_absolute_tol)
   _EPS=float(np.finfo(float).eps)
   ROUNDOFF_KAPPA=4.0
   ```
3. Комментарий `BlackOilNewtonReport` (строки ~59-60): `residual_tol -- atol + rtol*scale of the absolute test` → `residual_tol -- max(atol, round-off floor) + rtol*scale of the absolute test (BUG-025)`.
4. Новый метод после `_newton_report` (строка ~281):
   ```python
       def _absolute_tol(self,state_old,dt_s,atol_sm3s):
           """BUG-025: atol of the absolute Newton test, not below the round-off floor ROUNDOFF_KAPPA*eps*M_max/dt of the storage term."""
           # The storage term of the residual is (M_new - M_old)/dt in m3st/s, each inventory
           # carries a round-off error ~eps*M, and the residual does not go below ~eps*M_max/dt
           # (the largest cell of state_old; oil rows, gas rows / gas_residual_scale as in
           # residual).  At short steps this is above atol = 1e-11, the bound grows with the
           # largest cell: GPN bug020_rs150 (N = 350, r_e = 200 m, M_max = 7.2e3 m3st), shut-in
           # after 10 days of production -- the line search stalled at |F|*dt = 5-7e-13 m3st for
           # dt = 1e-2...1e-4 s and no stage of advance converged at any split; GPN example 15
           # (N = 50, M_max = 5.5e4) -- a production substep of 0.44 s failed the same way.  The measured stall is (0.07-0.7)*eps*M_max (R_ext = 800...50 m): cells
           # whose state did not change carry no round-off, so eps*M_max is an upper estimate.
           # ROUNDOFF_KAPPA = 4 keeps a margin of 6 over it.  Where the floor is below atol, max
           # returns atol itself and the solve is bitwise the former one: so in every GPN example
           # and every regression case (smallest atol*dt/(eps*M_max): 34, T05S_N200_DT5m; 63,
           # GPN example 18).  A solve accepted at the floor errs by at most ROUNDOFF_KAPPA*eps*M_max m3st.
           oi0,gi0=self._old_inventories(state_old)
           m=max(float(np.max(np.abs(oi0))),float(np.max(np.abs(gi0)))/self.gas_residual_scale)
           return max(atol_sm3s,ROUNDOFF_KAPPA*_EPS*m/float(dt_s))
   ```
5. `_newton_fixed_active_set`, строка ~373.
   До:
   ```python
           scale=max(nrm,1e-9); tol=atol_sm3s+rtol*scale
   ```
   После:
   ```python
           # BUG-025: atol not below the round-off floor of the storage term (_absolute_tol)
           scale=max(nrm,1e-9); tol=self._absolute_tol(state_old,dt_s,atol_sm3s)+rtol*scale
   ```
6. `_newton_switching`, строка ~596.
   До:
   ```python
           scale=max(np.linalg.norm(self.residual(z,state_old,dt_s,mask),np.inf),1e-9); tol=atol_sm3s+rtol*scale
   ```
   После:
   ```python
           # BUG-025: atol not below the round-off floor of the storage term (_absolute_tol)
           scale=max(np.linalg.norm(self.residual(z,state_old,dt_s,mask),np.inf),1e-9); tol=self._absolute_tol(state_old,dt_s,atol_sm3s)+rtol*scale
   ```

**Проверка после шага:**
- `& $PY -m pytest tests/test_prototype_residual_floor.py -q` → 8 passed.
- Из `HydroSolverPrototype\Prototype_1.0.3`: `& $PY -m pytest tests -q` → 101 passed; `& $PY regression\run_regression.py --quick` → 11/11 PASS (~8 мин). Ожидание — побитово (1.2(е)).
- Регресс: быстрый → прежнее число passed + 8.
- Пробы на настоящем коде (без подмены, из `<worktree>\numerical_solver`):
  - `& $PY ..\vault\issues\bug-025\probes\floor_probe.py scan` → строки `dt = …` и `ступень 1: …` **совпадают** со строками `fix_k4_r200.out.txt` (там та же арифметика подменой). Время счёта в скобках «(ступень 1, X с)» может отличаться — его не сравнивать. Команда (так сверял аудит 2; ожидается «строк 16, различий 0»):
    ```powershell
    $p = "..\vault\issues\bug-025\probes"; $rx = "\(ступень (\d), [0-9.]+ с\)"
    $new = & $PY $p\floor_probe.py scan 2>&1 | Select-String "^dt =|^    ступень" | ForEach-Object { $_.Line -replace $rx, '(ступень $1)' }
    $old = Get-Content $p\fix_k4_r200.out.txt -Encoding utf8 | Select-String "^dt =|^    ступень" | ForEach-Object { $_.Line -replace $rx, '(ступень $1)' }
    "строк $($new.Count), различий $(@(Compare-Object $old $new).Count)"
    ``` Различие хотя бы в одной цифре невязки, допуска или числа итераций означает, что арифметика `_absolute_tol` не та (порядок умножений, `abs`, деление на `gas_residual_scale`): исправить, а не принять.
  - `& $PY ..\vault\issues\bug-025\probes\floor_probe.py repro 0 16 0.054931640625` → «прошёл, R_s(r_w) = 22.4587978; отказов гидродинамики 0».

**Подводные камни:** раздел 2, «Порядок вызовов», «Обратная совместимость».
**Зависимости:** Требует: шаг 2. Блокирует: шаги 4, 5.
**Оценка:** ~25 строк, ~20 мин + регрессия 8 мин.

---

### Шаг 4: CHANGELOG прототипа и вспомогательный допуск тестов DEBT-054

**Цель:** запись о правке прототипа; помощник `_tol` тестов DEBT-054 — по новой формуле.
**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`, `numerical_solver/tests/test_prototype_failure_diagnostics.py`.

**Что сделать:**
1. `CHANGELOG_1.0.3.md` — в конец раздел:
   ```markdown
   ## Local changes — GPN project (BUG-025): absolute Newton tolerance not below the round-off floor
   - Problem: the residual is in m3st/s, its storage term is the difference of two inventories divided by dt, and each inventory carries a round-off error ~eps*M. Below ~eps*M_max/dt the residual does not go down, and at short steps this is above atol = 1e-11 m3st/s (in GPN below ~0.01-0.05 s at N = 350, ~0.5 s at N = 50). In a GPN shut-in after 10 days of production with a developed gas zone (N = 350, r_e = 200 m, M_max = 7.2e3 m3st) the line search of stages 1-3 stalled at |F|*dt = 5-7e-13 m3st and the fourth stage ran 40 iterations at the floor for dt = 1e-2...1e-4 s; the first shut-in step of 0.0549 s failed at every split down to dt/512. At N = 50 (GPN example 15) a production substep of 0.44 s failed the same way.
   - New method `_absolute_tol` and module constant `ROUNDOFF_KAPPA = 4.0`: both Newton solvers (`_newton_fixed_active_set`, `_newton_switching`) test ||F||_inf <= max(atol, ROUNDOFF_KAPPA*eps*M_max/dt) + rtol*max(||F0||_inf, 1e-9), M_max -- the largest cell inventory of `state_old` (oil rows; gas rows divided by `gas_residual_scale`, as in `residual`), from the inventory cache. The measured stall is (0.07-0.7)*eps*M_max, so a solve accepted at the floor errs by at most 4*eps*M_max m3st per step. `residual_tol` of the report is this tolerance.
   - Where the floor is below atol, `max` returns atol itself: prototype tests <101> passed, regression 17/17 PASS bitwise (smallest atol*dt/(eps*M_max) over the regression cases 34, T05S_N200_DT5m). In GPN all 23 examples are bitwise; the shut-in step converges with the first stage down to dt = 1e-4 s at r_e = 50, 200, 800 m.
   - Physics, residual equations, the per-cell test, line searches and well semantics are unchanged. The distribution version stays `1.0.3+gpn.1`. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
   - Tests: `tests/test_residual_floor.py` (4); `numerical_solver/tests/test_prototype_residual_floor.py` of the GPN project (8).
   - Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/105; plan: `vault/plans/bug-025 short-step-residual-floor.md` of the GPN project.
   ```
   Числа в `<…>` — подставить фактические после шага 5: тесты прототипа и регрессию.
2. `tests/test_prototype_failure_diagnostics.py`, помощник `_tol` (строки ~37-40): сейчас `ATOL + RTOL*max(...)`. Он верен только там, где предел ниже atol: так во всех его вызовах (Nabor_1b при 3600 с — предел 9e-15; ступень 4 rs300 при 168.75 с — 2.7e-14). Заменить на формулу `eq:newton_abs_tol`, чтобы помощник был верен при любом шаге:
   ```python
   def _tol(model, z0, s_old, dt, mask):
       """Абсолютный допуск Ньютона по Ур. (eq:newton_abs_tol) — те же операции, что в прототипе."""
       # max(atol, κ·ε·M_max/Δt) + rtol·max(‖F(z0)‖∞, 1e-9); M_max — запасы старого слоя
       # (нефть; газ / s_g). Во всех вызовах ниже предел ниже atol, и max возвращает atol
       f0 = model.residual(z0, s_old, dt, mask)
       oi0, gi0 = model._old_inventories(s_old)
       m = max(float(np.max(np.abs(oi0))), float(np.max(np.abs(gi0))) / model.gas_residual_scale)
       floor = max(ATOL, blackoil.ROUNDOFF_KAPPA * float(np.finfo(float).eps) * m / float(dt))
       return floor + RTOL * max(float(np.linalg.norm(f0, np.inf)), 1e-9)
   ```
   Импорт: `from radial_blackoil import blackoil` (рядом с `from radial_blackoil.blackoil import BlackOilNewtonReport`, строка 25; имя `blackoil` в модуле не занято — проверено в аудите 2).
3. Докстринг того же модуля (строки 3–4) описывает абсолютный критерий в старом виде: «||F||_inf <= atol + rtol*max(||F_0||_inf, 1e-9)». Дописать после него: «(с BUG-025 atol не ниже предела округления κ·ε·M_max/Δt, Ур. (eq:newton_abs_tol) problem_statement.tex)» — аудит 2.

**Проверка после шага:**
- `& $PY -m pytest tests/test_prototype_failure_diagnostics.py -q` → прежнее число passed (26 по CHANGELOG DEBT-054).
- Регресс: быстрый.

**Зависимости:** Требует: шаг 3. Блокирует: шаг 5.
**Оценка:** ~20 строк, ~15 мин.

---

### Шаг 5: верификация

**Цель:** побитовость историй и регрессии, полный прогон, числа ряда VAL-004 на настоящем коде.
**Файлы:** не меняются (выходы проб — `vault/issues/bug-025/probes/`).

**Что сделать (из `<worktree>\numerical_solver`, HEAD зафиксирован — регрессия перечитывает код в каждом кейсе):**
1. `& $PY ..\vault\issues\bug-025\probes\histories.py save after`, затем `… histories.py compare > ..\vault\issues\bug-025\probes\histories_compare.out.txt` → 26 строк «побитово», «ИТОГ: OK».
2. `& $PY ..\vault\issues\bug-025\probes\floor_probe.py series 0 6 9 > ..\vault\issues\bug-025\probes\impl_series_6-9.out.txt` (~5 мин) → $R_s(r_w)$ = 40.6122232, 40.9026572, 41.0521992, 41.1284813, отказов 0 — как `series_k4_6-9.out.txt`.
3. Добыча на грубой сетке (аудит 1): `& $PY ..\vault\issues\bug-025\probes\ramp_with_floor.py 0 example 15_oil_rate_ramp_up 0 0.44 > ..\vault\issues\bug-025\probes\impl_ramp_15.out.txt` (~20 с; `0` — без подмены, код ветки как есть). Ожидание — как строка «с пределом округления» в 1.2(ж): `orig` — отпечаток `a6e91358e1482446`; `h0=0.44` — 0 отказов, отпечаток `5d462f35ce3e39b9`. Запускать именно `ramp_with_floor.py`, а не `ramp_probe.py` FEAT-032: тот не ставит прототип каталога запуска в `sys.path`, и в worktree взял бы прототип основного каталога (установка `radial-blackoil` указывает туда).
4. Полный прогон: `& $PY -m pytest tests/ -q` → 1834 passed (1826 + 8 на `3f3df63`; если база ушла дальше — её число + 8), ~10 мин. `test_val004.py` — зелёный.
5. Из `HydroSolverPrototype\Prototype_1.0.3`: `& $PY regression\run_regression.py` (полная, ~45 мин) → 17/17 PASS. Выход `OUTPUT/REGRESSION_<время>/` удалить после разбора.
6. Подставить фактические числа в запись CHANGELOG (шаг 4).

**Проверка:** пункты 1–5. Регресс: **полный** — итоговый прогон реализации и регрессия с T05 (кейс с наименьшим κ* = 34).
**Если не побитово:** найти первое решение, где допуск изменился. Для этого `census.py` с подменой не нужен: он считает κ* на коде до правки; на ветке достаточно сравнить `residual_tol` отчётов. Разобрать, решение — за пользователем.
**Зависимости:** Требует: шаги 1–4.
**Оценка:** ~1 ч счёта.

---

### Шаг 6: vault и issue

**Цель:** отразить исправление и новые данные.
**Файлы:** `vault/roadmap/известные баги и технический долг.md`, `vault/roadmap/планируемые фичи.md`, `vault/knowledge/debugging/` (новая заметка), `vault/00-home/index.md`, `vault/issues/bug-025/05-comment-done.md`.

**Что сделать:**
1. Реестр, BUG-025: статус ✅ ИСПРАВЛЕНО (дата), ветка, коммиты, числа тестов. Поправить «Причину»: $\varepsilon_{маш}M_{max}$ — верхняя оценка предела округления; замер 1.2(в) вместо оценки «растёт с $M_{max}$». В «Не проверено» снять «добыча» и «другие сценарии»: проверено (1.2(ж), `impl_ramp_15.out.txt`). Граница шага — по сетке: ~0.01–0.05 с при $N$ = 350, ~0.5 с при $N$ = 50.
1а. Реестр, BUG-028: в «Связано с» уточнить: предел округления BUG-025 на последних подшагах снят (дата, коммит), главный отказ — набор фаз — остаётся. Следствие (`ramp_with_floor_19.out.txt`, аудит 1): эмуляция нарастания на старте добычи 19 больше не падает за ~3 с, а считается мелкими подшагами (> 35 мин, остановлено).
2. Реестр, BUG-026: строка «Чем закрывается»: «шаг короче 0.1 с невозможен (BUG-025)» → «BUG-025 исправлен: ряд нарастающих шагов до первого 0.0137 с без отказов, $R_s(r_w)$ на 1 ч = 40.612, 40.903, 41.052, 41.128 при первом шаге 0.110…0.0137 с, порядок → 1, предел ≈ 41.20» (из `impl_series_6-9.out.txt`).
3. `планируемые фичи.md`, FEAT-032: «меньше ~0.2 с не даёт BUG-025» → «ограничения на $h_0$ снизу от BUG-025 нет (исправлен)» + те же числа $R_s$ + пример 15 при $h_0$ = 0.44 с проходит (`impl_ramp_15.out.txt`). Запись могла измениться при планировании FEAT-032 — перед правкой прочитать её. Ограничение от BUG-028 (старт добычи) остаётся. Дописать в запись FEAT-032 и комментарием в issue #103 (тело — `vault/issues/bug-025/06-comment-feat032.md`, `gh issue comment 103 --body-file …`): после BUG-025 отказ на мелких подшагах из-за другой причины (BUG-028) — не быстрый `RuntimeError`, а долгий счёт. Единица дробления нарастания $dt/2^{\text{max\_retries}+m}$ не ограничивает число подшагов, поэтому предпосылка П4 плана FEAT-032 неверна; нужен предел (решение — при её реализации). Если FEAT-032 к этому моменту ещё не влита (на 2026-10-13 она в реализации), тот же комментарий сообщает: BUG-025 влит (коммит), срабатывает П15 её плана — до влития FEAT-032 перемерить на новой базе числа 16/17 и `EXPECTED` пробы (аудит 2). План FEAT-032 не править: его П15 сам перемеряет числа на базе с BUG-025.
4. Заметка `vault/knowledge/debugging/невязка в м³ст за секунду на шаге короче 0.1 с стоит на пределе округления запасов — допуск Ньютона не ниже 4ε·M_max на шаг.md`: механизм (1.1), замеры (1.2(а)–(в)), исправление и почему κ = 4, ссылка на план и issue.
5. `index.md`: заметка — в раздел knowledge/debugging; строка плана — «реализован».
6. `05-comment-done.md` и `gh issue comment 105 --body-file …`.

**Проверка:** `--collect-only -q` → 1834 (база + 8).
**Зависимости:** Требует: шаг 5.
**Оценка:** ~30 мин.

---

## 4. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `TestToleranceFloor::test_long_step_tolerance_unchanged` | `tests/test_prototype_residual_floor.py` (новый) | конец добычи bug020_rs150, Δt = 3600 с | `residual_tol == 1e-11 + 1e-8·max(‖F₀‖, 1e-9)` побитово | предел, сложенный с atol, — сдвиг допуска на всех шагах |
| `TestToleranceFloor::test_short_step_tolerance_floor` | то же | Δt = 1e-3 с | `residual_tol` = формула `eq:newton_abs_tol` побитово, > 1e-9 | не тот $M_{max}$ (слой, строки, $s_g$), не тот κ |
| `TestShortShutinStep::test_first_stage_converges[1e-2, 1e-3, 1e-4]` | то же | первый шаг останова | сходится ступенью 1, `exit_reason == 'converged'`, $\|F\|\Delta t \le \kappa\varepsilon M_{max}$ | возврат дефекта; предел не в ступенях 1–3 |
| `TestShortShutinStep::test_fourth_stage_short_step` | то же | `advance_fourth_stage`, 1e-3 с | сходится, допуск = формула | предел только в `_newton_fixed_active_set` |
| `TestShortShutinIntervals::test_no_hydro_failures[0.0549, 0.01]` | то же | `Simulator`: 10 сут добычи + 16 интервалов по dt | 0 отказов гидродинамики, 27 записей | исходный симптом BUG-025 (отказ после спада притока) |
| `ResidualFloorTests` (4) | прототип `tests/test_residual_floor.py` (новый) | Nabor_1b, $N$ = 12 | `_absolute_tol` = atol при 3600 с; формула при 1e-3 с; газ / $s_g$; допуск отчёта | ошибки формулы в поставке прототипа без тестов GPN |
| существующие | `test_val004.py`, `test_prototype_failure_diagnostics.py`, `test_prototype_cell_tolerance.py`, прототип `test_newton_last_iteration.py` | — | зелёные без изменений (кроме помощника `_tol`, шаг 4) | регресс |

Все новые тесты GPN — быстрого уровня (фикстура ~1 с, расчёты `Simulator` ~1 с).

## 5. Критерии завершения

- [ ] `eq:newton_abs_tol` в постановке, PDF собирается, `test_eq_references.py` зелёный
- [ ] Тесты-воспроизводители красные до шага 3 (1 passed, 7 failed; прототип 4 failed) и зелёные после
- [ ] `tests/`: 1834 passed (полный прогон; база `3f3df63` + 8)
- [ ] Прототип: 101 passed; регрессия `--quick` 11/11 и полная 17/17 PASS побитово
- [ ] `histories.py compare`: 26 сценариев побитово
- [ ] `floor_probe.py scan` совпадает с `fix_k4_r200.out.txt` (кроме времени счёта); ряд `series 0 6 9` — как `series_k4_6-9.out.txt`
- [ ] Добыча, $N$ = 50: пример 15 при $h_0$ = 0.44 с (`ramp_with_floor.py 0 …`) — 0 отказов, отпечаток `5d462f35ce3e39b9`
- [ ] Если FEAT-032 влита раньше — перепись `census.py` на новой базе и решение пользователя по примеру 16 («Как начать», п. 5)
- [ ] CHANGELOG прототипа с фактическими числами
- [ ] Vault: BUG-025 ✅, BUG-026 и FEAT-032 обновлены, заметка в `knowledge/debugging/`, index
- [ ] Issue #105 прокомментирован

## 6. Файлы плана

| Файл | Шаг | Изменение |
|---|---|---|
| `numerical_solver/doc/problem_statement.tex` | 1 | `eq:newton_abs_tol` + абзац о пределе округления |
| `numerical_solver/tests/test_prototype_residual_floor.py` | 2 | новый, 8 тестов |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_residual_floor.py` | 2 | новый, 4 теста |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` | 3 | `_EPS`, `ROUNDOFF_KAPPA`, `_absolute_tol`, 2 вызова, докстринг, комментарий отчёта |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` | 4, 5 | раздел BUG-025 |
| `numerical_solver/tests/test_prototype_failure_diagnostics.py` | 4 | помощник `_tol` по `eq:newton_abs_tol` |
| `vault/…` | 6 | реестры, заметка, index, комментарий issue |

Не меняются: `prototype_adapter.py`, `simulator.py`, `io/config.py` (текст `_NEWTON_TOL_REMOVED` называет умолчания atol и rtol — они прежние), README примеров, `examples/mass_balance.py` и `tests/test_mass_balance.py` (комментарии об atol 1e-11 верны для их шагов).

## 7. Пробы планирования (`vault/issues/bug-025/probes/`)

| Скрипт | Режим / выход | Что показывает |
|---|---|---|
| `floor_probe.py` | `scan [R_ext]` → `scan_r200`, `scan_r50`, `scan_r800.out.txt` | первый шаг останова без правки: отказ, |F|·Δt на остановке, ячейка максимума |
| | `fix KAPPA [R_ext]` → `fix_k1_r200`, `fix_k4_r200`, `fix_k4_r800`, `fix_k1_r50`, `fix_k4_r50.out.txt` | то же с пределом (подмена методов) |
| | `series KAPPA k1 k2` → `series_k0_6-9`, `series_k4_6-9.out.txt` | ряд VAL-004: отказ при $k$ = 7 без правки; $R_s(r_w)$ с пределом |
| | `repro KAPPA n dt`, `nabor KAPPA dt…` → `repro_nabor.out.txt` | минимальное воспроизведение в `Simulator`; Nabor_1b не воспроизводит |
| (инлайн, `stage4_short.out.txt`) | `advance_fourth_stage` при 1e-2…1e-4 с | ступень 4 без предела — 40 итераций, с пределом — 2–3 |
| `census.py` → `census.out.txt` | все решения Ньютона 23 примеров и 3 сценариев | наименьшее κ* = 63.1 |
| `census_regression.py` → `census_regression.out.txt` | кейсы регрессии по эталонным `step_log.csv` | наименьшее κ* = 34.3 |
| `audit2/extract.py`, `audit2/emulate_step3.py`, `audit2/tex_step1.py` → `audit2/audit2.out.txt` (аудит 2) | тесты шага 2 дословно из плана; эмуляция шага 3 (`BUG025_EMULATE=1`); шаг 1 на копии постановки | GPN 1 passed / 7 failed → 8 passed; прототип 4 failed → 4 passed; `.tex` собирается, формула помещается |
| `ramp_with_floor.py KAPPA <аргументы ramp_probe.py>` → `ramp_with_floor.out.txt`, `ramp_with_floor_19.out.txt` (аудит 1) | проба FEAT-032 с подменой допуска | добыча, $N$ = 50: пример 15 при $h_0$ = 0.44 с — отказ без предела округления, 0 отказов с ним; штатные истории 15, 13b, 19 побитово |
| `histories.py` | `save before/after`, `compare` (шаг 0, шаг 5) | побитовость историй 26 сценариев |
