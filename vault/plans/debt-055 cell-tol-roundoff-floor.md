---
tags:
  - план
  - рефакторинг
date: 2026-10-13
issue: DEBT-055
github: 107
branch: refactor/debt-055/cell-tol-roundoff-floor
status: реализован
worktree: .worktrees/debt-055; удалён после влития
merged: 0fc309d (2026-10-14)
audit:
  date: 2026-10-13
  found: 9
  auto-fixed: 9
  manual-required: 0
---

# DEBT-055: предел округления условия сходимости по ячейке — верный закон в документах и в отчёте отказа

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай связанные заметки:
   - запись DEBT-055 в `vault/roadmap/известные баги и технический долг.md`;
   - `vault/knowledge/debugging/абсолютный допуск Ньютона один на все ячейки недорешал забойную — условие по ячейке отнесено к её поровому объёму.md` (BUG-022, раздел «Предел» — его исправляет этот план);
   - `vault/knowledge/debugging/отказ Ньютона только по условию ячейки выглядел обычным — отчёт называет допуск, меру и причину выхода.md` (DEBT-054 — отчёт и текст отказа, которые расширяет этот план).
3. Ветка `refactor/debt-055/cell-tol-roundoff-floor` от `numerical_scheme/implementation` в worktree `.worktrees/debt-055` (делает `/implement`). Проверка базы: `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`.
4. Python: `<PY>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe` — venv один, в основном каталоге. В worktree своего `.venv` нет: относительный путь к `.venv` там не найдётся (аудит 1). Все команды плана — `<PY>` из каталога worktree (`<W>\numerical_solver` или `<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3`). pytest берёт код worktree (каталог запуска первый в `sys.path`). Скрипты проб берут код по `Path.cwd()` и печатают путь (`SOLVER = …`) — проверить, что путь — worktree.
5. Baseline (из `numerical_solver/` worktree):
   - `<PY> -m pytest tests/ --collect-only -q` — ожидается **1887** (база `7d8fea7`: влиты FEAT-032, DEBT-065, BUG-025);
   - `<PY> -m pytest tests/ -m "not slow" -q` — ожидается **1614 passed** (273 deselected), ~70 с;
   - прототип (план его меняет), из `numerical_solver/HydroSolverPrototype/Prototype_1.0.3`: `<PY> -m pytest tests -q` — **101 passed**; `<PY> regression\run_regression.py --quick` — **11/11 PASS**;
   - истории пяти сценариев до правки: `<PY> ..\vault\issues\debt-055\probes\histories.py save before` (≈1 мин; ожидается: bug018_n350 — 5 вызовов гидро, 2 отказа; ex14 — 362 и 1; ex16 — 731 и 0; ex17 — 733 и 1; daily_shutin — 27 и 7, как в `histories_save_base7d8fea7.out.txt`). Если база ушла дальше `7d8fea7` и числа другие — сверить с этим файлом, разобрать причину (как FEAT-032 в разделе 1.6) до правки.
6. Запомни числа и время быстрого уровня. Начни с шага 1. После каждого шага — тест шага и регресс по полю «Регресс»; полный прогон и полная регрессия прототипа — шаг 6.

## Резюме

Условие сходимости Ньютона по ячейке (BUG-022, `eq:newton_cell_tol`) недостижимо ниже предела, который задают округления. Шесть документов проекта называют этот предел $\sim\varepsilon_{маш}V_{p,\max}/V_{p,\min} \approx \varepsilon_{маш}(R_{ext}/r_w)^2$. **Замер планирования опроверг эту оценку по форме**:

- предел — изменение невязки при сдвиге каждой неизвестной на один шаг представимых чисел: мера ячеек вектора $|J|\,\mathrm{ulp}(z)$;
- он растёт как $\Delta t$ и на логарифмической сетке как $N^2/\ln^2(R_{ext}/r_w)$, а с ростом $R_{ext}$ при фиксированном $N$ **убывает**;
- дробление шага его снимает, поэтому при пороге по умолчанию 1e-8 он даёт лишь несколько лишних отказов, и только при $N$ = 350 с суточным шагом.

Решение пользователя (2026-10-13): вариант «документы + диагностика».
1. Верный закон — в `problem_statement.tex` (новая формула `eq:newton_cell_floor`), комментарии поля конфига, комментарии прототипа, P8, CHANGELOG прототипа, заметке BUG-022.
2. Отчёт отказа Ньютона прототипа получает поле `cell_floor` — предел на том же приближении, по уже построенному якобиану (одно произведение разреженной матрицы на вектор при отказе).
3. Текст отказа адаптера печатает предел и, если отказ «только по ячейке» стоит на пределе, говорит это.

Принятые шаги, приближения и все прежние поля отчёта — побитово; у прототипа без `cell_tol` поле не вычисляется. Заголовок DEBT-055 в реестре и на GitHub переименовывается (решение пользователя).

## 1. Контекст и замеры планирования

### 1.1 Условие и его предел

Условие BUG-022 (`problem_statement.tex`, `eq:newton_cell_tol`):
$$\max_j \frac{\Delta t}{V_{p,j}} \max\Bigl(|F_j^{oil}|,\ \frac{|F_j^{gas}|}{s_g}\Bigr) \le \varepsilon^{cell},$$
$F$ — невязка `residual()` прототипа (м³ст/с), $V_{p,j}$ — поровый объём на начало шага, $s_g = \max(R_{s,ext}, 1)$. В прототипе — `_cell_weights` (`blackoil.py:272-275`), `_cell_measure` (`:276-280`), `_cells_converged` (`:281-285`), порог `cell_tol` (`:145-147`); в GPN — `numerics.newton_cell_tol` = 1e-8 (`io/config.py:192`), фабрика передаёт его (`factory.py:451`). Номера строк — база `7d8fea7`.

**Гипотеза V (записана в документах, BUG-022):** предел $\sim\varepsilon_{маш}V_{p,\max}/V_{p,\min}$ — не зависит от $\Delta t$, растёт как $(R_{ext}/r_w)^2$. Механизм не устанавливался.

**Гипотеза Q (план):** неизвестные $z_k$ ($p$, $S_g$ или $R_s$) представимы с шагом $\mathrm{ulp}(z_k) \approx \varepsilon_{маш}|z_k|$. Невязку ячейки на решётке представимых чисел нельзя сделать меньше доли $\sum_k |\partial F_j/\partial z_k|\,\mathrm{ulp}(z_k)$ — оценки сверху изменения невязки при сдвиге всех неизвестных на ulp (сумма модулей; ошибки округления отдельных вкладов частично гасят друг друга, поэтому достижимая невязка — доля оценки). Предел меры:
$$m_{окр} = \max_{c,j} \frac{\Delta t}{V_{p,j}} \bigl(|J|\,\mathrm{ulp}(z)\bigr)_{c,j}$$
(газовые строки уже поделены на $s_g$, как в `residual()`). Главный член — давление в потоках через грани ($\mathcal T\lambda(p_j - p_{j+1})$, `eq:flux_oil`, `eq:flux_gas`):
$$m_{окр} \sim \varepsilon_{маш}\,p_j\,\mathcal T_{j\pm1/2}\,\lambda\,\Delta t/V_{p,j}.$$
У забоя логарифмической сетки $\mathcal T/V_{p,1} \approx k/(\varphi r_w^2\ln^2 q)$, $\ln q = \ln(R_{ext}/r_w)/N$. Отсюда предел $\propto \Delta t\,N^2/\ln^2(R_{ext}/r_w)$.

### 1.2 Прямой замер предела (`vault/issues/debt-055/probes/floor_probe.py`, `floor_probe.out.txt`)

Пример 17 (Стендинг, $R_{s0}$ = 300, $p_{wf}$ = 5 МПа), состояние после 2 сут добычи; один шаг `advance` при пороге 1e-8, затем в решении $z^*$:
- $m^*$ — мера;
- $m_{newt}$ — наименьшая мера за 8 итераций чистого Ньютона из $z^*$ (достижимый предел);
- $m_{lat}$ — разброс меры при случайном сдвиге каждой компоненты на −1/0/+1 ulp (без якобиана);
- $m_J$ — оценка Q по якобиану.

| сценарий | $\Delta t$, с | $m^*$ | $m_{newt}$ | $m_{lat}$ | $m_J$ | оценка V |
|---|---|---|---|---|---|---|
| $N$ = 200, $R_{ext}$ = 200 м, добыча | 225 | 6.0e-12 | 3.5e-13 | 2.33e-12 | 2.32e-12 | 8.2e-10 |
| | 900 | 2.9e-12 | 1.9e-12 | 9.31e-12 | 9.29e-12 | 8.2e-10 |
| | 3600 | 1.6e-11 | 7.2e-12 | 3.64e-11 | 3.72e-11 | 8.2e-10 |
| | 14400 | 6.3e-11 | 3.2e-11 | 1.49e-10 | 1.48e-10 | 8.2e-10 |
| | 86400 | 8.8e-9 | 2.0e-10 | 8.88e-10 | 8.86e-10 | 8.2e-10 |
| $N$ = 200, $R_{ext}$ = 200 м, останов | 225 | 3.5e-12 | 3.4e-12 | 1.83e-11 | 1.83e-11 | 8.2e-10 |
| | 3600 | 1.3e-10 | 8.9e-11 | 6.01e-10 | 5.99e-10 | 8.2e-10 |
| | 14400 | 2.2e-10 | 2.2e-10 | 2.42e-9 | 2.41e-9 | 8.2e-10 |
| | 86400 | 4.0e-9 | 3.9e-9 | 1.47e-8 | 1.46e-8 | 8.2e-10 |
| $N$ = 100, останов | 3600 | 6.2e-11 | 2.7e-11 | 1.36e-10 | 1.36e-10 | 7.6e-10 |
| $N$ = 400, останов | 3600 | 5.7e-10 | 5.7e-10 | 2.21e-9 | 2.50e-9 | 8.6e-10 |
| $R_{ext}$ = 1000 м, останов | 3600 | 6.2e-9 | 7.3e-11 | 4.01e-10 | 4.01e-10 | 2.0e-8 |
| $R_{ext}$ = 2000 м, останов | 3600 | 9.0e-11 | 7.2e-11 | 3.44e-10 | 3.44e-10 | 8.0e-8 |

(Шаг останова 900 с из этого состояния не сошёлся: мера 691, отказ не по пределу — см. 2.6 п. 3.)

Выводы:
- $m_{lat} \approx m_J$ в пределах 12 % (у 14 строк из 17 — в пределах 3 %): предел — шум решётки представимых чисел, оценка по якобиану его воспроизводит.
- $m_{newt}/m_J$ = 0.09–0.26 на 17 сошедшихся шагах: Ньютон доходит до ~0.1–0.3 предела, не ниже.
- По $\Delta t$ — пропорционально: ×4.00, ×3.98 на ×4; ×6.0 на ×6.
- По $N$ (останов, 3600 с) — $N^2$: 1.36e-10 → 5.99e-10 → 2.50e-9 (×4.4, ×4.2).
- По $R_{ext}$ при $N$ = 200 предел **убывает**: 6.0e-10 → 4.0e-10 → 3.4e-10, как $\ln^{-2}(R_{ext}/r_w)$: отношения 0.67 и 0.57 против 0.68 и 0.59 по формуле. Оценка V растёт в 100 раз.

Разложение (`floor_split.py`, `floor_split.out.txt`; пример 17, 3600 с): столбцы давления дают 97–100 % $m_J$ (добыча 3.64e-11 из 3.72e-11, останов 5.99e-10 из 5.99e-10), столбцы $S_g$/$R_s$ — ≤ 1.8e-12.

### 1.3 Отказы «только по ячейке» стоят на пределе (`failures_floor.py`, `failures_floor_bug018_ex14_shutin_ex16_ex17_ex19_ex20_ex21.out.txt`)

Для каждого отказа Ньютона с выполненным абсолютным критерием и невыполненным условием ячейки — $m_J$ в возвращённой точке:

| сценарий | ступени | $\Delta t$, с | мера | $m_J$ | мера/$m_J$ | поячеечно $\max_i |F_i|/(|J|\mathrm{ulp})_i$ |
|---|---|---|---|---|---|---|
| BUG-018, $N$ = 350 | 1–3 (×3) | 86400 | 2.596e-8 | 6.420e-8 | 0.40 | 0.46 |
| | 1–3 (×3) | 43200 | 1.167e-8 | 3.210e-8 | 0.36 | 0.41 |
| пример 14 ($N$ = 350) | 1–3 (×3) | 86400 | 1.139e-8 | 4.942e-8 | 0.23 | 0.33 |
| суточный останов rs300 ($N$ = 350) | 4 (×2) | 86400 | 1.29e-8, 1.25e-8 | 4.65e-8 | 0.27–0.28 | 0.28–0.32 |
| примеры 16, 17, 19, 20, 21 | — | — | отказов «только по ячейке» нет | | | |

Все такие отказы — на пределе: мера 0.23–0.40 предела, предел при $\Delta t/2$ ровно вдвое меньше (0.50000). У всех — $N$ = 350 и шаг 1 сут.

### 1.4 Цена на полном расчёте (`cost17.py`, `cost17_*.out.txt`; пример 17, 30 сут)

| вариант | оценка V | отказов адаптера | из них «только ячейка» | якобианов | $\min\Delta R_s(r_w)$ на останове |
|---|---|---|---|---|---|
| $R_{ext}$ = 2000 м, $N$ = 200, без условия | 8.0e-8 | 0 | — | 3483 | +9.64e-4 |
| $R_{ext}$ = 2000 м, $N$ = 200, 1e-8 | 8.0e-8 | **0** | 0 | 3522 (+1 %) | +9.57e-4 |
| $R_{ext}$ = 200 м, $N$ = 800, без условия | 8.7e-10 | 140 | — | 17141 | −2.85e-2 |
| $R_{ext}$ = 200 м, $N$ = 800, 1e-8 | 8.7e-10 | 83 | 2 | 11742 | +3.07e-6 |

- Гипотеза V предсказывала для $R_{ext}$ = 2000 м при 1e-8 удорожание, как у 17 при 1e-10 (порог в 8 раз ниже оценки): якобианы ×2.9. Замер — +1 % и ни одного отказа.
- При $N$ = 800 условие по ячейке расчёт **удешевляет** (83 против 140 отказов), а не удорожает. До предела ($m_J$ ≈ 1e-8 при 3600 с) доходят лишь 2 отказа.

### 1.5 Итог замеров

- Документы называют неверный по форме предел. Пользователь с большой областью дренирования прочтёт, что порог 1e-8 недостижим (на деле предел у него ниже). Пользователь с мелкой сеткой или длинным шагом не узнает, что предел растёт.
- Поскольку предел $\propto \Delta t$, дробление шага опускает его ниже порога, пока хватает глубины дробления (`max_retries` = 9 — до $\Delta t/512$). Предел абсолютного критерия на коротких шагах с влитием BUG-025 учтён в допуске (`eq:newton_abs_tol`) и дробление больше не останавливает. Срыва расчёта нет — только лишние подшаги, при пороге по умолчанию — единицы за расчёт.
- Отказ на пределе в тексте отказа неотличим от отказа недорешённого Ньютона: текст называет меру и порог, но не предел.

### 1.6 Перепроверка на базе `7d8fea7` (после влития FEAT-032, DEBT-065, BUG-025)

Замеры 1.2–1.4 сняты на `3f3df63`. Что изменилось на новой базе:
- **BUG-025** — абсолютный допуск не ниже $\kappa\varepsilon_{маш}M_{\max}/\Delta t$ (`_absolute_tol`, `eq:newton_abs_tol`). Это предел округления другого критерия, $\propto 1/\Delta t$; на шагах из тестов плана (86400, 43200, 168.75 с) он ниже atol, и `max` возвращает atol. `plan_check.py` на `7d8fea7` дал те же числа до последнего знака: 6.4200e-8, 3.2100e-8, отношение 0.50000, 4.3389e-11.
- **FEAT-032** — примеры 16 и 17 получили `time.dt_after_control_change = 2.0`. Последовательность вызовов у них другая: 731 и 733 вызова вместо 720, у 17 — 1 отказ, «не выполнены оба условия», мера 1.06, не предел (`histories_save_base7d8fea7.out.txt`). В пяти сценариях 11 отказов, «только по ячейке» — по-прежнему 5.
- **DEBT-065** — диагностика примеров, файлов плана не касается.

## 2. Анализ

### 2.1 Baseline

- База `7d8fea7` (`numerical_scheme/implementation`): 1887 тестов, быстрый уровень 1614 passed (273 deselected); прототип — 101 тест, регрессия `--quick` 11/11 PASS, полная 17/17 PASS (BUG-025).
- Отчёт Ньютона `BlackOilNewtonReport` (`blackoil.py:55-77`): поля DEBT-054 `residual_tol`, `cell_measure`, `exit_reason`. Создаётся `_newton_report` (`:286-290`) при каждом выходе `_newton_fixed_active_set` (`:399-439`) и `_newton_switching` (`:606-686`); у `_advance_phases` при исчерпании набора фаз — напрямую (`:582-587`); `advance` при отказе всех ступеней переносит поля исходного алгоритма (`:492-496`, DEBT-030). Сразу за `_newton_report` — `_absolute_tol` BUG-025 (`:291-309`).
- Текст отказа: `_failure_details` (`gpn_multiphase_solver/hydro/prototype_adapter.py:75-114`), вызов — `:234-239`; `Simulator._failure_message` дописывает его в свой текст (`simulator.py:377-…`, DEBT-054).
- Отказы в пяти сценариях DEBT-054 (`histories_save_base7d8fea7.out.txt`): 11 отказов адаптера — BUG-018 $N$ = 350 — 2, пример 14 — 1, пример 17 — 1 (с FEAT-032, «оба не выполнены»), суточный останов — 7. Из них «только ячейка» — 5 (перепись DEBT-054), у всех 11 отчёт Ньютона (выхода `'active_set'` нет).

### 2.2 Целевое состояние

- `BlackOilNewtonReport.cell_floor: float | None` — мера ячеек вектора $|J|\,\mathrm{ulp}(z)$ на возвращённом приближении. $J$ — последний якобиан решения, у выхода `'max_iter'` ступеней 1–3 — якобиан приближения до последнего обновления. Только у отказа с включённым условием, иначе `None`.
- Новый метод `RadialBlackOilModel._cell_floor(J, z, w)`; `_newton_report` принимает `J`, `z`.
- Текст отказа, пример (BUG-018, $N$ = 350, шаг 1 сут):
  `advance не сошёлся: dt = 8.640e+04 с, t = 0.0000 сут, итераций 4, невязка 6.51e-15 (допуск 5.35e-07), мера ячеек 2.60e-08 (порог numerics.newton_cell_tol = 1e-08), предел округления 6.42e-08, выход: линейный поиск не принял ни одной точки — не выполнено только условие по ячейке, мера не выше предела округления (он пропорционален шагу); числа — Ньютона ступени 1`
- `problem_statement.tex`: формула предела `eq:newton_cell_floor` и закон вместо $\varepsilon_{маш}(R_{ext}/r_w)^2$; тот же закон — в комментариях `config.py` и `blackoil.py`, P8, CHANGELOG, заметке BUG-022.
- Не меняется: решения, приближения, принятые шаги, последовательность вызовов, условие сходимости и его порог, поля конфига, фабрика, `Simulator`.

### 2.3 Варианты

**Вариант 1 — только документы.** Исправить текст в шести местах. Кода нет, всё побитово. Минус: отказ на пределе в журнале по-прежнему неотличим.

**Вариант 2 — документы + диагностика (выбран пользователем 2026-10-13).** Вариант 1 плюс поле `cell_floor` и текст адаптера.
- Плюсы: побитово (поле — после решения Ньютона, на приближение не влияет); якобиан уже построен; при `cell_tol=None` ничего не вычисляется; текст сам различает отказ на пределе.
- Минусы: правка прототипа (тесты и регрессия); одно произведение $|J|\cdot v$ на отказ.
- Промежуточные состояния: каждый шаг — зелёные тесты.

**Вариант 3 — пол в условии (самокалибрующийся).** Ячейка проходит при $|F_i| \le \max(\varepsilon\,V_{p,i}/\Delta t,\ \kappa(|J|\mathrm{ulp}(z))_i)$, $\kappa$ = 1 (нужно ≥ 0.46, табл. 1.3). Отказы на пределе исчезают, но истории примера 14 и, возможно, 19–21 ($N$ = 350, 1 сут) меняются на уровне округлений — README. Выигрыш при пороге по умолчанию — единицы отказов за расчёт. Отложен (решение пользователя) — зарегистрирован [[DEBT-067]].

**Вариант 4 — пол нормировки $V_i \to \max(V_i, \kappa\varepsilon_{маш}V_{\max}/\varepsilon)$ (запись реестра, замер BUG-022 1.4).** Опровергнут: исходит из формы V. Включился бы при большой $R_{ext}$, где предел ниже, и не включился бы при мелкой сетке, где предел растёт.

**Вариант 5 — предупреждение фабрики до расчёта.** По форме V — неверно. По форме Q нужна оценка до расчёта: подвижности и давления у забоя после разгазирования неизвестны. На начальном однофазном состоянии предел занижен на порядок: предел останова в 16 раз выше предела добычи (табл. 1.2). Не рекомендуется.

### 2.4 Выбор

Вариант 2: минимальный diff, побитово, тестируемо (предел — функция приближения и якобиана, проверяется точным равенством), обратная совместимость (новое поле со значением по умолчанию; подставные отчёты тестов без поля дают прежний текст).

### 2.5 Подводные камни

| # | Пункт | Статус | Как адресован |
|---|---|---|---|
| 1 | Все места создания отчёта | ✅ | `_newton_report` — 7 вызовов (grep `_newton_report(`): `:419`, `:423`, `:436`, `:438`, `:439`, `:652`, `:683`. Прямое создание — `_advance_phases` `:585` (`'active_set'`, Ньютон не решал — поле `None`, без правки). Подмена DEBT-030 `:492-496` — дописать `cell_floor=orig.cell_floor`, иначе текст напечатает меру ступени 1 и `None`. Конструкторы в тестах (`test_prototype_globalization.py`, `test_prototype_well_branch.py`, `test_prototype_phase_switching.py`, `test_prototype_activation_cap.py`) — позиционно 3–5 полей; новое поле последнее, со значением по умолчанию — не затронуты |
| 2 | Зависимости пакетов | ✅ | Новых нет: `abs()` разреженной матрицы и `np.spacing` — scipy/numpy |
| 3 | Обратная совместимость | ✅ | Поле в конце датакласса со значением по умолчанию; `_newton_report(J=None, z=None)` — ключевые аргументы; `_failure_details` читает поле через `getattr` (подставные отчёты — прежний текст, 11 случаев `test_failure_details` не меняются) |
| 4 | Состояние при ошибке | ✅ | Поле вычисляется после решения Ньютона, приближение `z` и `J` не меняются: `abs(J)` создаёт новую матрицу |
| 5 | Тесты | ✅ | Тексты DEBT-054 проверяются подстроками и `endswith("; числа — Ньютона ступени 1")` — вставки идут в середину, конец прежний (`test_adapter_message_cell_test_only`, `test_simulator_message_ends_with_adapter_text`). README текст отказа не цитируют (grep `мера ячеек`, `порог numerics` по `*.md` — пусто); начало текста Simulator, которое цитируют README 03, 05, 06, 07, 10, не меняется |
| 6 | Циклические импорты | ✅ | Новых импортов нет |
| 7 | Ссылки на уравнения | ⚠️ | Новая метка `eq:newton_cell_floor` объявляется в шаге 1 до того, как на неё сошлются тесты и `config.py` (шаги 2–5): `test_eq_references.py` требует, чтобы каждая метка из `.py` ядра, тестов и примеров была в `.tex` |
| 8 | Конфиги | ✅ | Поля конфига не меняются |
| 9 | Связь с другими задачами | ⚠️ | **BUG-025, FEAT-032, DEBT-065 влиты** (база `7d8fea7`, раздел 1.6): номера строк плана — по ней. BUG-025 стоит в тех же двух Ньютонах (строки `tol=…` и `_absolute_tol` после `_newton_report`) — правки плана в другие строки; новый метод `_cell_floor` — после `_cell_measure`, до `_newton_report`. **FEAT-030** (в работе, `.worktrees/feat-030`) правит в `config.py` `OutputConfig` (сразу после `NumericsConfig`) и комментарий `:155`; комментарий `newton_cell_tol` (`:187-189`) — отдельный кусок, при втором влитии возможен конфликт соседних строк, разрешается объединением. Файлов прототипа, адаптера и тестов диагностики FEAT-030 не касается |
| 10 | Производительность | ✅ | Одно произведение разреженной матрицы $2N\times2N$ (~6 ненулевых в строке) на вектор — на отказ; якобиан не строится заново |
| 11 | Прототип | ⚠️ | Меняется `radial_blackoil/blackoil.py` → тесты прототипа (101, новых нет) и регрессия: `--quick` после шага 3, полная — шаг 6. Ожидание: **11/11 и 17/17 PASS побитово** — без `cell_tol` (собственные расчёты прототипа) `_cell_floor` возвращает `None` до вычислений. FAIL — не пересъёмка эталона: разобрать (шапка `/plan-improve`, «Правка прототипа»), решение за пользователем. Запись в `CHANGELOG_1.0.3.md` — шаг 5 |
| 12 | Выход `'max_iter'` ступеней 1–3 | ⚠️ | Последний якобиан — приближения до последнего обновления; предел берётся с ним и ulp возвращённого $z$. Разница — на шаг Ньютона; в докстринге поля и CHANGELOG это сказано. Тесты на этот выход не опираются |
| 13 | `jacobian_mode='reference'` | ✅ | Плотная матрица: `abs(J) @ v` работает так же (ndarray) |
| 14 | Оговорка «мера не выше предела» сравнивает максимумы по сетке | ⚠️ | Ячейки максимума меры и максимума предела могут не совпадать (BUG-018: мера — o16, предел — g13). Сравнение — факт, как и классы DEBT-054, но толкование «точнее не решить» строго верно поячеечно. Поячеечный множитель $\max_i |F_i|/(|J|\mathrm{ulp})_i$ во всех пяти отказах на пределе — 0.28–0.46 (табл. 1.3), то есть там оговорка верна и поячеечно. Отдельное поле с поячеечным отношением — не нужно (вариант 2 решения пользователя) |
| 15 | Поле отчёта в журналах шагов | ✅ | `asdict`, `fields(`, `vars(` по `radial_blackoil/`, `run_prototype.py`, `gpn_multiphase_solver/` — нет (аудит 1): `step_log.csv`, `run_summary.json` перечисляют поля явно, новое поле туда не попадает, регрессия по ним не меняется |

### 2.6 Обнаруженные проблемы

1. **Отказы на пределе остаются (вариант 3 отложен).** При $N$ = 350 и шаге 1 сут Ньютон ступеней 1–3 упирается в предел и отказывает, шаг дробится; у ступени 4 по памяти — 40 итераций впустую (суточный останов, 2 отказа). Цена при пороге по умолчанию — единицы отказов за расчёт. **Зарегистрировано [[DEBT-067]]** (2026-10-13, решение пользователя). Её реализация переведёт тесты этого плана, воспроизводящие отказ на пределе (BUG-018 при $N$ = 350), на другой сценарий отказа.
2. **Запись реестра DEBT-055 исходит из неверной оценки:** «при большой области дренирования ($R_{ext} \ge$ 1–2 км) … расчёт молча дорожает в разы» — опровергнуто (табл. 1.4); «приоритет низкий: ни одному примеру не нужно» — отказы на пределе есть у примера 14 и тестовых сценариев BUG-018, TestDailyShutin. Запись правится при планировании (раздел 5) — дополнением, исходный текст сохраняется.
3. **Не по пределу:** шаг останова 900 с после 2 сут добычи примера 17 не сошёлся (мера 691), а 225 и 3600 с из того же состояния — сошлись (`floor_probe.out.txt`). Первый шаг после смены управления — предмет FEAT-032 (влит: в примерах 16, 17 первый подшаг останова 2 с) и BUG-026. Не блокирует; отмечено в записи DEBT-055 (реестр).
4. **Два предела Ньютона — по разные стороны шага.** Абсолютный критерий имеет предел $\propto 1/\Delta t$ (накопление крупнейшей ячейки; с BUG-025 допуск его учитывает, `eq:newton_abs_tol`), условие по ячейке — $\propto \Delta t$ (учёт — [[DEBT-067]]). При мелкой сетке и большой области окно шагов без лишних отказов сужается с обеих сторон. Записать в заметку (шаг 7), отдельной задачи не нужно.

## 3. Шаги

### Шаг 1: Формула предела в постановке

**Цель:** `problem_statement.tex` называет верный закон и объявляет метку `eq:newton_cell_floor`, на которую сошлются код и тесты.

**Файлы:** `numerical_solver/doc/problem_statement.tex`.

**Контекст:** абзац после `eq:newton_cell_tol` (строки 2184–2185 на `7d8fea7`) повторяет гипотезу V. Выше, у абсолютного условия, BUG-025 уже описал предел округления накопления (`eq:newton_abs_tol`, $\propto 1/\Delta t$) — новый текст ссылается на него для контраста. Метка нужна до шагов 2–5: `tests/test_eq_references.py::test_label_references_exist_in_problem_statement` падает на ссылку без объявления (сканирует `.py` ядра, тестов, примеров и README примеров; прототип — нет).

**Что сделать:** заменить две строки.

До:
```latex
Порог заметно ниже $\sim\varepsilon_{\text{маш}}(R_{\text{ext}}/r_w)^2$ не~достигается
из-за округлений, и~шаги дробятся.
```
После:
```latex
Порог не~достижим ниже предела округления. Неизвестные $z_k$ ($p$, $S_g$ или~$R_s$
ячеек) представимы лишь с~шагом $\operatorname{ulp}(z_k) \approx
\varepsilon_{\text{маш}}|z_k|$, и~невязку ячейки нельзя сделать меньше доли
изменения, которое даёт сдвиг каждой неизвестной на~этот шаг. Оценка этого изменения
сверху (сумма модулей вкладов):
\begin{equation}\label{eq:newton_cell_floor}
  m_{\text{окр}} = \max_j \frac{\Delta t}{V_{p,j}}
    \max\Bigl(\sum_k \Bigl|\frac{\partial F_j^{\text{oil}}}{\partial z_k}\Bigr|
      \operatorname{ulp}(z_k),\
      \frac{1}{s_g}\sum_k \Bigl|\frac{\partial F_j^{\text{gas}}}{\partial z_k}\Bigr|
      \operatorname{ulp}(z_k)\Bigr).
\end{equation}
В~замерах Ньютон останавливается на~$0.1$--$0.4\,m_{\text{окр}}$. Предел задают давления
в~потоках через грани~\eqref{eq:flux_oil}, \eqref{eq:flux_gas}:
$m_{\text{окр}} \sim \varepsilon_{\text{маш}}\,p_j\,\mathcal{T}_{j\pm\half}\,
\lambda\,\Delta t/V_{p,j}$, где $\lambda$~--- подвижность компонента на~грани
(например, $k_{ro}/(\mu_o B_o)$). Поэтому предел растёт пропорционально~$\Delta t$,
а~у~забоя логарифмической сетки~--- как $\mathcal{T}_{j+\half}/V_{p,j} \propto
N^2/\ln^2(R_{\text{ext}}/r_w)$. С~отношением поровых объёмов крайних ячеек
$\sim(R_{\text{ext}}/r_w)^2$ он не~растёт: при том~же~$N$ с~ростом $R_{\text{ext}}$
предел убывает как $\ln^{-2}(R_{\text{ext}}/r_w)$. В~отличие от~предела абсолютного
условия~\eqref{eq:newton_abs_tol}, который растёт с~уменьшением шага, этот растёт
с~его увеличением. Шаг, на~котором порог ниже предела, отвергается и~дробится, пока
предел не~опустится ниже порога; в~расчётах проекта с~порогом по~умолчанию так было
лишь при $N = 350$ и~суточном шаге.
```

**Проверка после этого шага:**
- Сборка: из `numerical_solver/doc` — `pdflatex -interaction=nonstopmode problem_statement.tex` дважды; в `problem_statement.log` нет `! ` (ошибок) и нет `Overfull \hbox` у новой формулы (при переполнении — перенести второй аргумент `\max` на новую строку окружением `aligned` внутри `equation`). `\half` — макрос постановки (`\newcommand{\half}`, строка 12). Аудит 1 собрал копию с этим текстом (`vault/issues/debt-055/probes/audit1/tex_check.py`): ошибок нет, неопределённых ссылок нет, у формулы переполнения нет. `Overfull \hbox (14.1pt)` в абзаце «где $V_{p,j}$~--- …» сразу после `eq:newton_cell_tol` (~2175 строка), который захватывает начало вставки, **есть и в базе без правки** — не новый, не чинить.
- `<PY> -m pytest tests/test_eq_references.py -q` — passed.
- Регресс: `--collect-only -q` (только документ) — 1887.

**Подводные камни:** 2.5 п. 7; нумерация уравнений ниже сдвигается на 1 — ссылки в коде по меткам (DEBT-010), не страдают.

**Зависимости:** блокирует шаги 2, 4, 5.

**Оценка:** ~20 строк, 15 мин.

### Шаг 2: Тесты поля `cell_floor` (красные)

**Цель:** тесты фиксируют определение предела, его отсутствие там, где Ньютон не отказал или условие выключено, пропорциональность шагу, отказ ступеней 1–3 и 4 на пределе, перенос подменой DEBT-030.

**Файлы:** `numerical_solver/tests/test_prototype_failure_diagnostics.py`.

**Контекст:** файл DEBT-054 уже содержит все нужные сценарии и помощники: `_nabor` (Nabor_1b, $N$ = 12), `_bug018_model()` (BUG-018 при $N$ = 350, шаг 86400 с), фикстуру `shutin` (rs300 после 10 сут добычи, $q_{oil}$ = 0), `CELL_TOL`, `DT`, `DT_STAGE4`. Числа — `vault/issues/debt-055/probes/plan_check.out.txt` (эмуляция поля на коде базы).

**Что сделать:**

1. Docstring модуля — дописать абзац после строки «…(DEBT-061, поглощена DEBT-054).»:
```
DEBT-055: отчёт отказа несёт ещё cell_floor — предел округления меры ячеек на том же
приближении, меру вектора |J|·ulp(z) (eq:newton_cell_floor); текст отказа его печатает и
говорит, если отказ «только по ячейке» стоит на пределе.
План: vault/plans/debt-055 cell-tol-roundoff-floor.md; замеры —
vault/issues/debt-055/probes/.
```
2. `TestSwitching.test_converged_report` — после последнего `assert` добавить:
```python
        assert rep.cell_floor is None      # DEBT-055: предел — только у отказа
```
3. `TestBranchAndTotalFailure.test_total_failure_carries_original_diagnostics`:
   - в `orig` добавить `cell_floor=6.4e-8`, в `other` — `cell_floor=2.0e-7`;
   - после последнего `assert` добавить:
```python
        assert rep.cell_floor == 6.4e-8      # DEBT-055: предел — тоже исходного алгоритма
```
   и в docstring строку «Ловит: …» дополнить: «…; предел округления последней попытки (DEBT-055)».
4. Новый раздел перед «F. Текст отказа адаптера»:
```python
# ═══════════════════════════════════════════════════════════
# E2. Предел округления меры ячеек (DEBT-055)
# ═══════════════════════════════════════════════════════════

class TestRoundoffFloor:
    """DEBT-055: отчёт отказа несёт cell_floor — меру ячеек вектора |J|·ulp(z) (eq:newton_cell_floor).

    Неизвестные представимы с шагом ulp, и невязку ячейки нельзя сделать меньше доли
    (|J|·ulp(z))_i: Ньютон встаёт на 0.1–0.4 этой меры (замеры плана —
    vault/issues/debt-055/probes/floor_probe.out.txt, failures_floor_*.out.txt). Предел
    растёт как Δt: дробление шага его снимает. Числа тестов — plan_check.out.txt.
    """

    def test_definition_at_linear_solver_exit(self, monkeypatch):
        """Выход 'linear_solver' на первой итерации: якобиан построен в z0 — предел ровно мера |J(z0)|·ulp(z0).

        Ловит: предел по другому приближению, другому якобиану или другим весам.
        """
        model, state = _nabor(12, cell_tol=CELL_TOL)

        def broken(*args, **kwargs):
            raise np.linalg.LinAlgError("вырожденная матрица (тест)")

        monkeypatch.setattr(model, "_linear_solve", broken)
        z0 = model.pack(state)
        _, rep = model._newton_fixed_active_set(z0, state, DT, state.gas_active)
        J0, _ = model.finite_difference_jacobian(z0, state, DT, state.gas_active)
        expected = model._cell_measure(abs(J0) @ np.spacing(np.abs(z0)),
                                       model._cell_weights(state, DT))
        assert rep.exit_reason == "linear_solver"
        assert rep.cell_floor == expected

    def test_none_without_failure_or_cell_test(self):
        """Предела нет у сошедшегося решения и при выключенном условии (собственные расчёты прототипа).

        Ловит: лишнее произведение |J|·v на каждом решении; предел без условия по ячейке.
        """
        model, state = _nabor(12, cell_tol=CELL_TOL)
        _, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active)
        assert rep.converged and rep.cell_floor is None
        # Без cell_tol: max_iter = 1 при трёх нужных итерациях — отказ, но весов нет
        model, state = _nabor(12)
        _, rep = model._newton_fixed_active_set(model.pack(state), state, DT, state.gas_active,
                                                max_iter=1)
        assert not rep.converged and rep.cell_floor is None

    def test_bug018_failure_at_floor(self):
        """BUG-018 при N = 350, шаг 86400 с: ступень 1 встала на пределе — мера 2.60e-8 > 1e-8, предел 6.42e-8.

        Замер (plan_check.out.txt, B): линейный поиск после 4 итераций, мера 2.5962e-8,
        предел 6.4200e-8, отношение 0.40. Ловит: отказ на пределе неотличим от отказа
        недорешённого Ньютона (у того мера много выше предела).
        """
        model, ps, dt = _bug018_model()
        _, rep = model._advance_phases(ps, dt)
        assert not rep.converged and rep.exit_reason == "line_search"
        assert CELL_TOL < rep.cell_measure <= rep.cell_floor
        assert rep.cell_floor == pytest.approx(6.42e-8, rel=1e-3)

    def test_floor_proportional_to_dt(self):
        """Тот же старт при dt/2: предел ровно вдвое меньше — дробление шага его снимает.

        Замер (plan_check.out.txt, B): 3.2100e-8 против 6.4200e-8 — 0.50000. Предел задают
        давления в потоках через грани (eq:newton_cell_floor): вес dt/V_p, производные
        потоков от dt не зависят. При dt/2 мера 1.17e-8 ещё выше порога — Simulator
        отвергает и этот подшаг; dt/4 сходится (история сценария: 86400 и 43200 с —
        отказ, 21600 с — принят; histories_save_base7d8fea7.out.txt).
        Ловит: предел, не зависящий от шага (оценка eps_маш·V_max/V_min до DEBT-055).
        """
        model, ps, dt = _bug018_model()
        _, full = model._advance_phases(ps, dt)
        _, half = model._advance_phases(ps, dt / 2)
        assert not half.converged and half.cell_measure > CELL_TOL
        assert half.cell_floor / full.cell_floor == pytest.approx(0.5, rel=1e-3)

    def test_switching_limit_stops_at_floor(self, shutin):
        """Ступень 4 при недостижимом пороге 1e-30: 40 итераций, мера встала на 0.23 предела.

        Замер (plan_check.out.txt, C): мера 9.77e-12, предел 4.34e-11. Отказы ступени 4
        по памяти на суточном останове — тот же класс: мера 1.29e-8 при пределе 4.65e-8
        (failures_floor_*.out.txt). Порог возвращается в finally: фикстура модульная.
        """
        model, ps = shutin
        try:
            model.cell_tol = 1e-30
            _, rep = model._newton_switching(ps, DT_STAGE4)
        finally:
            model.cell_tol = CELL_TOL
        assert not rep.converged and rep.exit_reason == "max_iter"
        assert rep.cell_measure <= rep.cell_floor
        assert rep.cell_floor == pytest.approx(4.34e-11, rel=1e-2)
```

**Проверка после этого шага:**
- `<PY> -m pytest tests/test_prototype_failure_diagnostics.py -q` — ожидается **7 failed** (5 новых: `AttributeError: … 'cell_floor'`; `test_converged_report` ступени 4 — `AttributeError`; `test_total_failure_carries_original_diagnostics` — `TypeError: … unexpected keyword argument 'cell_floor'`), остальные passed.
- Регресс: нет (красный шаг; следующий шаг его закрывает).

**Подводные камни:** `_bug018_model()` ставит управление `set_bhp_control` (как адаптер) — `_advance_phases` вызывать на нём, не на `advance`: отчёт ступени 1 — тот, что печатает адаптер после подмены DEBT-030, а `advance` при dt/2 мог бы сойтись ступенью 4 (не проверялось) и отчёта ступени 1 не вернуть. Фикстура `shutin` импортирована в модуль из `test_prototype_cell_tolerance` (`from .test_prototype_cell_tolerance import (… shutin)` в начале файла) — как аргумент метода класса работает. Помощник `_tol` с BUG-025 считает допуск по `eq:newton_abs_tol` — новые тесты его не используют.

**Зависимости:** требует шаг 1 (docstring ссылается на `eq:newton_cell_floor`); блокирует шаг 3.

**Оценка:** ~110 строк, 30 мин.

### Шаг 3: Поле `cell_floor` в прототипе

**Цель:** отчёт отказа Ньютона несёт предел; всё остальное побитово.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`.

**Что сделать (номера строк — база `7d8fea7`):**

1. Docstring модуля (после абзаца BUG-025, `:38-40`) — добавить:
```
DEBT-055: a failed Newton report also carries the rounding limit of the per-cell measure
(cell_floor): the measure of |J| @ ulp(z), the change of the residual when every unknown
moves by one ulp; the Newton does not get far below it, and it grows as dt.
```
2. `BlackOilNewtonReport` (поля DEBT-054 `:75-77`) — после `exit_reason: str = ''` (`:77`):
```python
    # DEBT-055: rounding limit of cell_measure on the same iterate -- the per-cell measure of
    # |J| @ ulp(z): the unknowns are representable to ulp(z) only, and the Newton stops at
    # 0.1-0.4 of it (GPN probes).  J is the last Jacobian of the solve; for the 'max_iter' exit
    # of _newton_fixed_active_set it is the Jacobian of the iterate before the last update.
    # Only on a failed solve with the per-cell test on; None otherwise ('active_set': no Newton
    # failed; 'branch': the Newton converged).
    cell_floor: float | None = None
```
3. Комментарий конструктора (`:141-144`).

До:
```python
        # the Rs error of a step is estimated by cell_tol*Bo*(gas_residual_scale + Rs).  Far
        # below ~eps_mach*PV_max/PV_min the test is not met and steps are split (GPN example
        # 17 at cell_tol = 1e-10: 214 rejected steps against 47; the mechanism is not
        # established -- both the line search and the stage-4 Newton stall).
```
После:
```python
        # the Rs error of a step is estimated by cell_tol*Bo*(gas_residual_scale + Rs).
        # DEBT-055: below a rounding limit the test is not met.  The unknowns are representable
        # to ulp(z) only, and the measure does not get far below that of |J| @ ulp(z)
        # (cell_floor of a failed report; the Newton stops at 0.1-0.4 of it).  It is the
        # pressure term of the face fluxes, ~eps_mach*p*T*lambda*dt/PV_i: it grows as dt and,
        # near the well of the log grid, as N^2/ln^2(r_e/r_w) -- not as PV_max/PV_min, as
        # BUG-022 assumed.  A step below it fails and is split until the limit drops (GPN
        # example 17 at cell_tol = 1e-10: 214 rejected steps against 47; at 1e-8 only N = 350
        # with daily steps meets it).
```
4. После `_cell_measure` (`:276-280`), перед `_cells_converged` — новый метод:
```python
    def _cell_floor(self,J,z,w):
        """DEBT-055: rounding limit of the per-cell measure -- _cell_measure of |J| @ ulp(z); None when the test is off or there is no Jacobian."""
        if w is None or J is None: return None
        return self._cell_measure(abs(J)@np.spacing(np.abs(z)),w)
```
5. `_newton_report` (`:286-290`; за ним `_absolute_tol` BUG-025 — не трогать).

До:
```python
    def _newton_report(self,converged,iterations,nrm,tol,f,w,reason,**fields):
        """DEBT-054: report of a Newton solve -- ||F||_inf, its absolute tolerance, the per-cell measure of the same f, the exit reason."""
        return BlackOilNewtonReport(converged,iterations,float(nrm),
                                    residual_tol=None if tol is None else float(tol),
                                    cell_measure=self._cell_measure(f,w),exit_reason=reason,**fields)
```
После:
```python
    def _newton_report(self,converged,iterations,nrm,tol,f,w,reason,J=None,z=None,**fields):
        """DEBT-054: report of a Newton solve -- ||F||_inf, its absolute tolerance, the per-cell measure of the same f, the exit reason; DEBT-055: on a failure the rounding limit of the measure at (J, z)."""
        return BlackOilNewtonReport(converged,iterations,float(nrm),
                                    residual_tol=None if tol is None else float(tol),
                                    cell_measure=self._cell_measure(f,w),exit_reason=reason,
                                    cell_floor=None if converged else self._cell_floor(J,z,w),**fields)
```
6. `_newton_fixed_active_set`:
   - после `:419` (`if nrm<=tol and self._cells_converged(f,w): return …`) — строки
```python
        # DEBT-055: the last Jacobian goes into a failure report (rounding limit of the measure)
        J=None
```
   - `:423` → `except Exception: return z,self._newton_report(False,it,nrm,tol,f,w,'linear_solver',J=J,z=z)`
   - `:436` → `if not accepted: return z,self._newton_report(False,it,nrm,tol,f,w,'line_search',J=J,z=z)`
   - `:439` → `return z,self._newton_report(False,max_iter,nrm,tol,f,w,'max_iter',J=J,z=z)`
   - `:438` (сошлось) — без изменений.
7. `_newton_switching`:
   - `:652-653` → `return new,self._newton_report(ok,it-1,nrm,tol,f,w,'converged' if ok else 'sg_bound',J=J,z=z,` / `active_set_iterations=1,phase_switches=total)` — у `'sg_bound'` предел на $z$ того же прохода;
   - `:683-684` → `return self.unpack(z,mask),self._newton_report(False,it-1,np.linalg.norm(f,np.inf),tol,f,w,reason,J=J,z=z,` / `active_set_iterations=1,phase_switches=total)`. Якобиан последнего прохода построен в том же $z$: выход по лимиту — на проходе `it > max_iter` после `J,f=…` (`:643`); `'linear_solver'` и `'nonfinite'` — до обновления $z$.
   - Комментарий DEBT-054 перед `:682` (`:678-681`) дополнить: «…(DEBT-054); the rounding limit -- with the Jacobian of the last pass, built at the same z (DEBT-055)».
8. `advance` (`:492-496`): в `replace(...)` после `exit_reason=orig.exit_reason` добавить `,cell_floor=orig.cell_floor`; комментарий DEBT-054 над ним (`:490-491`) дополнить: «…and the rounding limit of the measure (DEBT-055)».

**Проверка после этого шага:**
- `<PY> -m pytest tests/test_prototype_failure_diagnostics.py -q` — все passed (было 7 failed).
- Регресс: быстрый — `1619 passed` (1614 + 5 новых).
- Регресс прототипа: из `numerical_solver/HydroSolverPrototype/Prototype_1.0.3` — `<PY> -m pytest tests -q` (101 passed) и `<PY> regression\run_regression.py --quick` — ожидание **11/11 PASS побитово** (`cell_tol=None` → `_cell_floor` возвращает `None` до вычислений). Выход `OUTPUT/REGRESSION_<время>/` удалить после разбора.

**Подводные камни:** 2.5 п. 1, 4, 11, 12. Строки прототипа — стиль без пробелов вокруг операторов (как соседние): так и писать.

**Зависимости:** требует шаг 2; блокирует шаг 4.

**Оценка:** ~30 строк, 30 мин + регрессия ~8 мин.

### Шаг 4: Текст отказа адаптера

**Цель:** текст печатает предел и говорит, когда отказ «только по ячейке» стоит на пределе.

**Файлы:** `numerical_solver/tests/test_prototype_failure_diagnostics.py`, `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`.

**Что сделать — сначала тесты (красные):**

1. `_rep` — новый аргумент:
```python
def _rep(res, tol=None, meas=None, reason="", floor=None):
    """Отчёт отказа с полями DEBT-054 (и предела DEBT-055) для проверки текста."""
    return BlackOilNewtonReport(False, 3, res, residual_tol=tol, cell_measure=meas,
                                exit_reason=reason, cell_floor=floor)
```
2. В `@pytest.mark.parametrize` `test_failure_details` — три случая после первого:
```python
    # DEBT-055: только ячейка, мера не выше предела округления — отказ на пределе
    (_rep(1e-15, 1e-9, 3e-8, "line_search", 6e-8), 1e-8, 1,
     " (допуск 1.00e-09), мера ячеек 3.00e-08" + _THRESHOLD + ", предел округления 6.00e-08, "
     "выход: линейный поиск не принял ни одной точки — не выполнено только условие по ячейке, "
     "мера не выше предела округления (он пропорционален шагу); числа — Ньютона ступени 1"),
    # DEBT-055: только ячейка, мера выше предела — Ньютон недорешал, предел только числом
    (_rep(1e-15, 1e-9, 3e-8, "max_iter", 1e-9), 1e-8, 4,
     " (допуск 1.00e-09), мера ячеек 3.00e-08" + _THRESHOLD + ", предел округления 1.00e-09, "
     "выход: исчерпан лимит итераций — не выполнено только условие по ячейке; числа — Ньютона ступени 4"),
    # DEBT-055: оба не выполнены — предел только числом
    (_rep(1e-3, 1e-9, 1.0, "max_iter", 1e-9), 1e-8, 1,
     " (допуск 1.00e-09), мера ячеек 1.00e+00" + _THRESHOLD + ", предел округления 1.00e-09, "
     "выход: исчерпан лимит итераций — не выполнены оба условия сходимости; числа — Ньютона ступени 1"),
```
3. `test_adapter_message_cell_test_only` — в кортеж `part` добавить `", предел округления 6.42e-08"` и `", мера не выше предела округления (он пропорционален шагу)"`; в docstring: «…хвост — допуск, мера, предел округления (DEBT-055), выход, невыполненное условие».
4. `test_simulator_message_ends_with_adapter_text` — после последнего `assert`:
```python
    assert "мера не выше предела округления" in tail      # DEBT-055: отказ на пределе
```

Проверка красного: `pytest tests/test_prototype_failure_diagnostics.py -q` — **5 failed** (3 новых случая и 2 расширенных теста).

**Затем код** — `_failure_details` (`prototype_adapter.py:75-114`):
- docstring: `"""Хвост текста отказа: допуск, мера ячеек, предел округления, причина выхода, невыполненное условие (DEBT-054, DEBT-055)."""`
- комментарий `:77-79` → «Поля residual_tol, cell_measure, exit_reason несёт BlackOilNewtonReport с DEBT-054, cell_floor — с DEBT-055. Подставные отчёты тестов (SimpleNamespace, отчёт без этих полей) их не имеют — хвоста нет, текст прежний.»
- после `measure = getattr(...)`: `floor = getattr(report, "cell_floor", None)`
- в блоке `if measure is not None:` после печати порога:
```python
        # DEBT-055: предел округления меры на том же приближении — мера вектора |J|·ulp(z)
        # (eq:newton_cell_floor); есть только у отказа Ньютона с условием по ячейке
        if floor is not None:
            text += f", предел округления {floor:.2e}"
```
- в ветви `else:` классов (после `text += " — " + {...}[...]`):
```python
            # DEBT-055: только условие ячейки, и мера не выше предела округления — точнее
            # на этом шаге не решить; предел пропорционален шагу, дробление его снимает.
            # Сравнение — факт, как и классы выше
            if abs_ok and measure > cell_tol and floor is not None and measure <= floor:
                text += ", мера не выше предела округления (он пропорционален шагу)"
```
- docstring модуля (`:32-35`) → «Текст отказа (DEBT-054): прежний текст (dt, t, итерации, невязка) и хвост из отчёта Ньютона — абсолютный допуск, мера условия по ячейке с порогом numerics.newton_cell_tol и её предел округления (DEBT-055), причина выхода, какое условие сходимости не выполнено (отказ на пределе округления — отдельной оговоркой) и чья это статистика (ступень 1 после подмены DEBT-030 или ступень 4 по памяти).»

**Проверка после этого шага:**
- `pytest tests/test_prototype_failure_diagnostics.py -q` — все passed.
- Регресс: быстрый — **1622 passed** (1614 + 8).

**Подводные камни:** 2.5 п. 3, 5. Точное число `6.42e-08` в тексте: предел ступени 1 на выходе `'line_search'` — якобиан построен в том же $z$, совпадает с пробой (6.4200e-8 → формат `.2e` → `6.42e-08`).

**Зависимости:** требует шаг 3.

**Оценка:** ~40 строк, 25 мин.

### Шаг 5: Документы — конфиг, P8, CHANGELOG

**Цель:** верный закон в комментарии поля, в P8 и в журнале изменений прототипа.

**Файлы:** `numerical_solver/gpn_multiphase_solver/io/config.py`, `vault/knowledge/decisions/P8-формат-ввода-json.md`, `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`.

**Что сделать:**

1. `config.py:187-189` (комментарий `newton_cell_tol`, база `7d8fea7`).

До:
```python
    # Порог на порядок ниже ~2.2e-16·(R_ext/r_w)^2 не выполняется, шаги дробятся: при
    # 1e-10 у 17 отказов шагов 214 против 47, якобианов ×2.9 (оценка для 17 — 8e-10;
    # при R_ext/r_w = 1e4 и 1e-8 — вдвое ниже оценки — лишь +8 отказов из 38). null — выкл.
```
После:
```python
    # Предел округления (DEBT-055, eq:newton_cell_floor): неизвестные представимы с шагом
    # ulp, и меру нельзя сделать меньше доли меры вектора |J|·ulp(z) — Ньютон встаёт на
    # 0.1–0.4 её. Это давление в потоках через грани, ~2.2e-16·p·T·λ·Δt/V_p: предел растёт
    # как Δt и у забоя логарифмической сетки как N²/ln²(R_ext/r_w) (с ростом R_ext при том
    # же N — убывает). Шаг ниже предела отвергается и дробится, пока предел не опустится:
    # у 17 при 1e-10 отказов шагов 214 против 47, якобианов ×2.9; при 1e-8 — лишь у N = 350
    # с шагом 1 сут (пример 14, BUG-018). Предел шага — в тексте отказа. null — выкл.
```
2. P8 (`:200`) — хвост строки `newton_cell_tol`.

До: «Порог заметно ниже $\sim 2.2\cdot10^{-16}(R_{ext}/r_w)^2$ не достигается из-за округлений — шаги дробятся (пример 17 при 1e-10: отказов шагов 214 против 47; [[DEBT-055]])»

После: «Порог не достижим ниже предела округления — доли меры вектора $|J|\,\mathrm{ulp}(z)$ (`eq:newton_cell_floor`; Ньютон встаёт на 0.1–0.4 её): предел растёт как $\Delta t$ и как $N^2/\ln^2(R_{ext}/r_w)$ (с ростом $R_{ext}$ при том же $N$ — убывает), шаг ниже предела отвергается и дробится (пример 17 при 1e-10: отказов шагов 214 против 47; при 1e-8 — лишь у $N$ = 350 с шагом 1 сут). Текст отказа печатает предел ([[DEBT-055]])»
3. CHANGELOG:
   - в разделе BUG-022 (`:121`) после «…the mechanism is not established).» дописать « The estimate is wrong in form: see DEBT-055 below.»
   - в конец файла, после раздела BUG-025 (`:157-…`), — раздел (числа итога — из шага 6; если разойдутся с ожиданием — подставить фактические):
```
## Local changes — GPN project (DEBT-055): rounding limit of the per-cell measure in a failure report
- Problem: the BUG-022 entry above estimates the limit below which the per-cell test cannot be met as ~eps_mach*PV_max/PV_min ~ eps_mach*(r_e/r_w)^2. The estimate is wrong in form. The unknowns are representable to ulp(z) only, and the residual of cell i does not get far below (|J| @ ulp(z))_i. GPN probes: from 17 converged steps a pure Newton reached 0.09-0.26 of the per-cell measure of |J| @ ulp(z), failed solves stopped at 0.23-0.40 of it; a random +-1 ulp shift of z changes the measure by the same amount within 12 %. The pressure columns give 97-100 % of it, the face-flux term ~eps_mach*p*T*lambda*dt/PV_i: the limit grows as dt (x4.0 from 900 to 3600 s; x0.50000 from 86400 to 43200 s) and, near the well of the log grid, as N^2/ln^2(r_e/r_w) (GPN example 17, shut-in step of 3600 s: N = 100, 200, 400 -- 1.4e-10, 6.0e-10, 2.5e-9; r_e = 200, 1000, 2000 m -- 6.0e-10, 4.0e-10, 3.4e-10, while PV_max/PV_min grows 100 times). Step splitting lowers it; at cell_tol = 1e-8 only N = 350 with daily steps meets it (GPN BUG-018 case, example 14, a daily shut-in: 5 failures). A failure report did not show it.
- `BlackOilNewtonReport`: new field `cell_floor` -- the per-cell measure of |J| @ ulp(z) for the iterate reported, J the last Jacobian of the solve (for the 'max_iter' exit of `_newton_fixed_active_set`, the Jacobian of the iterate before the last update); only on a failed solve with `cell_tol` set, otherwise None. New method `_cell_floor`; `_newton_report` takes the Jacobian and the iterate; `advance()` carries the field of the original algorithm (DEBT-030). One sparse matrix-vector product per failed solve, no additional Jacobians.
- Accepted steps, iterates and all former report fields are bitwise unchanged; with the default `cell_tol=None` the field is None and nothing is computed: tests 101 passed, regression 17/17 PASS bitwise. In GPN five runs (BUG-018 at N = 350, examples 14, 16, 17, a daily shut-in) reproduce their histories and step sequences bitwise; the failure message names the limit and, where a per-cell failure is at it, says so (5 of 11 failures). The limit of the per-cell test grows with dt, the round-off floor of the absolute test (BUG-025 above) -- as 1/dt.
- Tests: `numerical_solver/tests/test_prototype_failure_diagnostics.py` of the GPN project (+8). Physics, residual equations, convergence tests and their tolerances, Newton/active-set logic and well semantics are unchanged. The distribution version stays `1.0.3+gpn.1`. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/107; plan: `vault/plans/debt-055 cell-tol-roundoff-floor.md` of the GPN project.
```

**Проверка после этого шага:**
- `pytest tests/test_eq_references.py -q` — passed (`config.py` ссылается на `eq:newton_cell_floor`).
- Регресс: `--collect-only -q` — 1895.

**Подводные камни:** правило «Без англицизмов» — в русских текстах «предел округления», «мера», без «floor». В `config.py` комментарии — Юникод (×, ², λ) как в соседних строках.

**Зависимости:** требует шаг 1; числа CHANGELOG — шаг 6.

**Оценка:** ~30 строк, 20 мин.

### Шаг 6: Итоговая проверка

**Цель:** побитовость историй, полный прогон, полная регрессия прототипа.

**Что сделать:**
1. `<PY> ..\vault\issues\debt-055\probes\histories.py save after`, затем `… compare > ..\vault\issues\debt-055\probes\histories_compare.out.txt`. Ожидание:
   - пять сценариев побитово (p, S_g, R_s, T, режим, моменты, последовательность вызовов);
   - отказов 11 → 11; без вставок DEBT-055 каждый текст побуквенно прежний;
   - «текстов с пределом округления 11, из них «мера не выше предела» 5» (классы «только ячейка» переписи DEBT-054; отказ примера 17 после FEAT-032 — «оба не выполнены», мера 1.06 — получает только число предела). Иное число — разобрать по выводу (у выхода `'active_set'` предела нет — таких отказов в базе нет).
2. Полный прогон: `<PY> -m pytest tests/ -q` — **1895 passed**.
3. Полная регрессия прототипа: зафиксировать HEAD (`git rev-parse --short HEAD`), из `numerical_solver/HydroSolverPrototype/Prototype_1.0.3` — `<PY> regression\run_regression.py` (~45 мин, в фоне) — **17/17 PASS**. Выход `OUTPUT/REGRESSION_<время>/` удалить после разбора.
4. Числа итога — в CHANGELOG (шаг 5, п. 3), если отличаются от ожидаемых.

**Регресс:** полный — конец реализации (`/implement` §3.1).

**Оценка:** 1 ч (из них ~45 мин — регрессия в фоне).

### Шаг 7: Vault

**Файлы:**
- `vault/roadmap/известные баги и технический долг.md` (DEBT-055);
- `vault/knowledge/debugging/абсолютный допуск Ньютона один на все ячейки недорешал забойную — условие по ячейке отнесено к её поровому объёму.md`;
- `vault/knowledge/debugging/отказ Ньютона только по условию ячейки выглядел обычным — отчёт называет допуск, меру и причину выхода.md`;
- новая заметка `vault/knowledge/numerics/предел округления условия сходимости по ячейке растёт с шагом и числом ячеек, а не с размером области.md`;
- `vault/00-home/index.md`.

**Что сделать:**
1. Заметка BUG-022, раздел «Предел» (`:42-44`) — переписать: закон Q, таблица 1.2 (сжато), «оценка $\varepsilon_{маш}(R_{ext}/r_w)^2$ неверна по форме — [[DEBT-055]]».
2. Заметка DEBT-054, строка 53 («мера пропорциональна шагу ($\approx 3\cdot10^{-13}\,\Delta t$) … [[DEBT-055]]») — дописать: «механизм — предел округления $|J|\,\mathrm{ulp}(z)$, отчёт с DEBT-055 его печатает».
3. Новая заметка (numerics) — механизм, формула, замеры 1.2–1.4, урок:
   - оценка предела без замера связи с $\Delta t$ и $N$ ушла в шесть документов;
   - $m_{lat}$ (сдвиг на ulp) — дешёвая проверка гипотезы о пределе округления без якобиана;
   - два предела Ньютона по разные стороны шага: абсолютный $\propto 1/\Delta t$ (BUG-025, заметка [[на коротком шаге невязка Ньютона стоит на пределе округления запасов — допуск не ниже 4ε·M_max на Δt]]), по ячейке $\propto \Delta t$ (2.6 п. 4, [[DEBT-067]]).
4. Реестр: статус DEBT-055 → ✅ ГОТОВО с числами шага 6; index — ссылка на новую заметку.
5. Комментарий в issue #107 — `vault/issues/debt-055/05-comment-done.md` (делает `/implement`).

**Регресс:** `--collect-only -q`.

**Оценка:** 40 мин.

## 4. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `TestRoundoffFloor::test_definition_at_linear_solver_exit` | `tests/test_prototype_failure_diagnostics.py` (существующий) | Nabor_1b $N$ = 12, решатель СЛАУ падает на 1-й итерации | `cell_floor` == `_cell_measure(abs(J0) @ spacing(abs(z0)), w)` побитово | предел по другому приближению, якобиану, весам |
| `…::test_none_without_failure_or_cell_test` | там же | сходимость с `cell_tol`; отказ `max_iter=1` без `cell_tol` | `None` в обоих | лишнее вычисление; предел без условия (регрессия прототипа) |
| `…::test_bug018_failure_at_floor` | там же | BUG-018 $N$ = 350, `_advance_phases`, 86400 с | `'line_search'`; 1e-8 < мера ≤ предел; предел ≈ 6.42e-8 (rel 1e-3) | отказ на пределе неотличим |
| `…::test_floor_proportional_to_dt` | там же | то же при dt/2 | отказ; предел(dt/2)/предел(dt) ≈ 0.5 (rel 1e-3) | предел, не зависящий от шага (форма V) |
| `…::test_switching_limit_stops_at_floor` | там же | `shutin`, ступень 4, порог 1e-30 | `'max_iter'`; мера ≤ предел; предел ≈ 4.34e-11 (rel 1e-2) | ступень 4 без поля; предел не того прохода |
| `TestSwitching::test_converged_report` (+1 assert) | там же | ступень 4 сходится | `cell_floor is None` | — |
| `…::test_total_failure_carries_original_diagnostics` (+поле) | там же | подмена DEBT-030 | предел исходного алгоритма | предел последней попытки при мере ступени 1 |
| `test_failure_details` (+3 случая) | там же | на пределе / выше предела / оба не выполнены | тексты 4.2 | неверная оговорка, оговорка не у того класса |
| `test_adapter_message_cell_test_only` (+2 части) | там же | реальный текст BUG-018 | «предел округления 6.42e-08», оговорка | — |
| `test_simulator_message_ends_with_adapter_text` (+1 assert) | там же | `max_retries = 0` | оговорка в конце текста Simulator | — |

Неизменность поведения: все 1887 тестов базы; регрессия прототипа 11/11 (шаг 3), 17/17 (шаг 6); истории пяти сценариев побитово (шаг 6, `histories.py`). Новых тестов 8: 1887 → 1895; быстрый уровень 1614 → 1622 (новые — не `slow`: без фикстуры `results`, сетка $N \le$ 350, ~1 с каждый).

## 5. Связь формула → код

| Формула | Код | Тесты |
|---|---|---|
| `eq:newton_cell_tol` | `_cell_weights`, `_cell_measure`, `_cells_converged` (`blackoil.py`) | без изменений |
| `eq:newton_cell_floor` (новая, шаг 1) | `RadialBlackOilModel._cell_floor`, поле `BlackOilNewtonReport.cell_floor`; печать — `prototype_adapter._failure_details` | `TestRoundoffFloor`, `test_failure_details` |

## 6. Критерии завершения

- [ ] Шаги 1–7 выполнены.
- [ ] Все тесты зелёные: 1895 passed (полный), быстрый 1622.
- [ ] Прототип: тесты 101 passed; регрессия `--quick` 11/11 и полная 17/17 PASS побитово.
- [ ] Истории пяти сценариев побитово, тексты отказа без вставок — прежние (`histories_compare.out.txt`, «ИТОГ: OK»).
- [ ] `problem_statement.tex` собирается без ошибок и без переполнения строки у `eq:newton_cell_floor`.
- [ ] Ни одного упоминания предела $\varepsilon_{маш}(R_{ext}/r_w)^2$ / `PV_max/PV_min` как действующего закона: grep `(R_ext/r_w)^2`, `PV_max/PV_min`, `R_{\text{ext}}/r_w)^2`, `r_e/r_w)^2` по `numerical_solver/` (без `regression/`) и по `vault/knowledge/`; каждое попадание просмотреть. Допустимы:
  - упоминания **отношения поровых объёмов** — `config.py:176`, `test_prototype_cell_tolerance.py:4`, `problem_statement.tex` абзац под `eq:newton_cell_tol` («в $\sim(R_{ext}/r_w)^2$ раз меньше»), заметка BUG-022 строка 18, комментарий прототипа «~(r_w/r_e)^2 of the outer cell's pore volume»;
  - противопоставление в новом тексте шага 1 («с отношением поровых объёмов … он не растёт»), шага 3 («not as PV_max/PV_min, as BUG-022 assumed») и CHANGELOG (BUG-022 с отсылкой, раздел DEBT-055).
- [ ] Vault: реестр, две заметки, новая заметка numerics, index; комментарий в #107; issue закрывается при `/merge`.

## 7. Оценка

Файлов: 4 кода/тестов (`blackoil.py`, `prototype_adapter.py`, `config.py`, `test_prototype_failure_diagnostics.py`), 3 документа (`problem_statement.tex`, `CHANGELOG_1.0.3.md`, P8), 5 vault. Строк ~260. Время ~4 ч, из них ~1 ч — регрессии прототипа.

## 8. Аудит 1 (2026-10-13, база `7d8fea7`; фокус — предметная суть)

**Прогон в коде** (`vault/issues/debt-055/probes/audit1/`):
- `conftest.py` применяет правки шагов 3 и 4 к исходникам `blackoil.py` и `prototype_adapter.py` в памяти, дословно по блокам «До → После». Все 15 цитат «До» найдены ровно по одному разу.
- `test_plan_apply.py` — новые тесты шага 2 дословно, копии расширенных тестов и строки шага 4.
- Результаты:
  - с правками: 10 тестов эмуляции + `tests/test_prototype_failure_diagnostics.py` + `tests/test_prototype_cell_tolerance.py` — 49 passed;
  - только шаг 3: падают ровно тексты адаптера — красное состояние шага 4;
  - без правок: падают тесты отчёта (`AttributeError`/`TypeError`, как в шаге 2) и тексты.
- Реальный текст отказа BUG-018 на эмуляции совпал с разделом 2.2.
- `tex_check.py` собрал копию постановки с текстом шага 1: без ошибок, ссылки определены, у формулы переполнения нет.
- Базовые числа сверены: 1887 / 1614 (273 deselected), тесты прототипа 101 passed (34.8 с), HEAD `7d8fea7`; у прототипа после BUG-025 изменений нет.

Запуск эмуляции (из `numerical_solver/`): `<PY> -m pytest ..\vault\issues\debt-055\probes\audit1 -q -p no:cacheprovider`. Переменная `DEBT055_PATCH` = `all` | `proto` | `none` — какие правки применены.

**Находки (все исправлены в плане):**
- 🟡 Команды «Как начать» и шагов — относительный путь к `.venv` из worktree, а в worktree `.venv` нет (`Test-Path` — False). Заменено на `<PY>` — venv основного каталога (п. 4 «Как начать»).
- 🟡 Текст шага 1 (постановка), комментарий `config.py`, P8, docstring тестов: «невязка не опускается заметно ниже $|J|\mathrm{ulp}$» противоречил замеру «Ньютон встаёт на 0.1–0.4 её». Сумма модулей — оценка сверху, достижима доля. Формулировки: «нельзя сделать меньше доли», формула названа оценкой сверху.
- 🔵 «От отношения поровых объёмов он не зависит», «от $R_{ext}$ почти не зависит» — неточно: при том же $N$ предел убывает как $\ln^{-2}(R_{ext}/r_w)$ (−43 % от 200 до 2000 м). Исправлено в `.tex`, `config.py`, P8.
- 🔵 Постановка обобщала «при пороге по умолчанию это случается лишь при мелкой сетке и суточном шаге» по пяти сценариям проекта — переписано как наблюдение.
- 🔵 1.5: «пока шаг не упрётся в предел абсолютного критерия (≲ 0.1 с, BUG-025)» устарело после влития BUG-025 — теперь ограничение одно: глубина дробления.
- 🔵 Шаг 1: переполнение 14.1 pt в абзаце под `eq:newton_cell_tol` уже есть в базе — отмечено, чтобы его не чинили как новое.
- 🔵 Docstring `test_floor_proportional_to_dt`: «при dt/4 мера ~0.4 — сходится» не замерялось — заменено фактом из истории сценария (21600 с принят).
- 🔵 2.5: добавлен п. 14 — оговорка сравнивает максимумы по сетке, ячейки могут не совпадать; в пяти отказах на пределе она верна и поячеечно.
- 🔵 Критерий grep по старой оценке ловил бы законные упоминания отношения поровых объёмов и противопоставления — перечислены допустимые попадания.
