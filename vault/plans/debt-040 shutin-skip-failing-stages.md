---
tags:
  - план
  - рефакторинг
  - prototype
  - newton
date: 2026-10-07
issue: DEBT-040
github: 69
branch: refactor/debt-040/shutin-skip-failing-stages
status: в процессе
worktree: .worktrees/debt-040
audit:
  date: 2026-10-07
  round: 1
  found: 13
  auto-fixed: 13
  manual-required: 0
---

# DEBT-040: запасной путь при BHP не пробует ветку «открыта», если она заведомо несогласована

## Кратко

- **Что не так.** Останов скважины после добычи с развитой газовой зоной: почти каждый шаг решает только ступень 4 `advance` (BUG-020). Перед ней ступени 1–3 перебирают решения Ньютона, которые не принимаются. При останове через забойное давление ($p_{wf} = p_{ext}$, «режим A») среди них ветка скважины «открыта». Она не может быть согласована: на контуре и во всех ячейках давление не выше $p_{wf}$, значит, скважина не может добывать. Замер на конфиге 20: ветку пробовали 1488 раз, ни разу не приняли, на неё ушло 38 % времени останова.
- **Что делаем.** В `_fallback` (прототип) не пробовать ветку «открыта», если $p_{ext} \le p_{wf}$ и $\max_j p_j^{old} \le p_{wf}$. Правка — 2 строки кода и комментарий.
- **Эффект** (замер 1.2): сквозной расчёт 10 сут добычи + 3 сут останова в режиме A — 573 → 391 с (−32 %). История побитово та же. На все 21 пример правка не влияет: условие там не выполняется ни разу. Режим B ($q_{oil} = 0$) не меняется: веток там нет.
- **Вариант 1** (начинать шаг сразу со ступени 4) отклонён решением пользователя — раздел 2.3.

## 0. Решения пользователя (2026-10-07)

1. **Только вариант 2.** Вариант 1 отклонить, причины записать в план (раздел 2.3). Отдельной записью в реестр его не регистрировать.
2. **Вариант 2 действует всегда**, а не под флагом `phase_switching_stage`. Обоснование: принятые шаги не меняются (довод 2.3 и перепись 1.3); поля ветки отчёта не пишутся ни в один выходной файл (проверено поиском `well_branch|well_switches`: только `blackoil.py` и тесты); регрессия прототипа проверит побитовость.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай связанные заметки vault (раздел 6). Главное:
   - [[останов из развитой газовой зоны — забойная ячейка без потока и дребезг ячейки выше по потоку]] — что такое ступени `advance` и почему на останове работает только ступень 4;
   - запись DEBT-040 в `vault/roadmap/известные баги и технический долг.md`.
3. Ветка от **`numerical_scheme/implementation`** (не от `master`: там нет `numerical_solver/`):
   ```powershell
   git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver   # должна быть строка
   git checkout numerical_scheme/implementation
   git checkout -b refactor/debt-040/shutin-skip-failing-stages
   ```
   Если `/implement` работает в worktree (`.worktrees/debt-040`), то все команды ниже выполняются из `<W>\numerical_solver`, где `<W>` — корень worktree. Для проб задать `$env:DEBT040_SOLVER = "<W>\numerical_solver"` и проверить строку `код:` в выводе пробы: оба пути должны вести в `<W>`. Без явного пути скрипт в worktree берёт пакет основного каталога (установка `pip install -e` указывает туда); pytest из `<W>\numerical_solver` берёт код `<W>` корректно.
4. Python. Без worktree — `.venv\Scripts\python` из `numerical_solver/` (команды плана написаны так). В worktree своего venv нет. Задать `$PY = "<КОРЕНЬ>\numerical_solver\.venv\Scripts\python.exe"` и вместо `.venv\Scripts\python` и `..\..\.venv\Scripts\python` писать `& $PY`; каталог запуска — тот же, но внутри `<W>`. `<КОРЕНЬ>` — основной каталог проекта (`D:\Lessons\Grants\2026\GPN\Oil_Gas`).
5. Базовые значения (шаг 0) — сверить с записанными здесь (база `299d6a7`, 2026-10-07):
   - GPN: `pytest tests/ --collect-only -q` → **1344**; быстрый уровень `-m "not slow"` → **1108** выбрано;
   - прототип (из `numerical_solver/HydroSolverPrototype/Prototype_1.0.3`): `..\..\.venv\Scripts\python -m pytest tests -q` → **97 passed**; `..\..\.venv\Scripts\python regression\run_regression.py --quick` → **11/11 PASS**.
6. Начни с шага 0. После каждого шага — тест шага и регресс по полю «Регресс». Полный прогон — в шаге 5.

## 1. Замеры (2026-10-07, база `299d6a7`: BUG-020 и BUG-021 влиты)

Проба `vault/issues/debt-040/probes/stage_profile.py` — код решателя не меняется. Проба оборачивает методы экземпляра модели прототипа:
- `_advance_phases` — одно решение Ньютона (ступень определяется по флагам модели, ветка — по `_well_branch`);
- `advance` — шаг (какая ступень его решила).

Варианты подменяются на экземпляре: `v2` — копия `_fallback` с правкой этого плана, `v1` — память ступени. Режим `e2e` повторяет `vault/issues/bug-020/probes/e2e_shutin.py`: конфиг `20_rs300_cooling`, 10 суточных интервалов добычи при $p_{wf}$ примера, затем 3 сут останова, `dt_integration` = 3600 с. Режим A: $p_{wf} = p_{ext}$ = 330 бар. Режим B: $q_{oil} = 0$, `min_bhp` = 1 атм. Все шесть расчётов шли одновременно (одинаковая загрузка машины), поэтому времена сравнимы между собой, но не с прошлыми замерами.

### 1.1 Профиль ступеней на останове, режим A, код базы (`e2e_20A_0.out.txt`)

Вызовов `advance` на останове — 936, время в них — 560.5 с. Шаг решила ступень: 1 — 230, 3 — 56, 4 — 518; отказов (дальше дробление A-retry) — 132. Решения, которые не приняты, заняли 441.7 с, то есть 79 % этого времени.

| ступень | ветка | решений | сошлось | принято | время, с | впустую, с | итераций ср. |
|---|---|---|---|---|---|---|---|
| 1 | — | 936 | 230 | 230 | 95.7 | 62.4 | 9.6 |
| 2 | open | 706 | 567 | 0 | 86.9 | 86.9 | 12.2 |
| 2 | shut | 706 | 0 | 0 | 61.8 | 61.8 | 8.4 |
| 3 | open | 650 | 515 | 0 | 78.4 | 78.4 | 11.9 |
| 3 | shut | 706 | 56 | 56 | 62.2 | 53.9 | 8.6 |
| 4 | open | 132 | 0 | 0 | 49.3 | 49.3 | 40.0 |
| 4 | shut | 650 | 518 | 518 | 126.1 | 49.0 | 20.5 |

«Сошлось», но не «принято» означает, что Ньютон сошёлся к несогласованному решению. У ветки «открыта» это $p_0 < p_{wf}$: решение означает закачку, и `_fallback` его отвергает (`blackoil.py:424`). Ветка «открыта» на всех ступенях заняла 214.6 с — 38 % времени останова. Ступень 4 на ней каждый раз тратит все 40 итераций.

Режим B (`e2e_20B_0.out.txt`): 969 вызовов, 379.1 с, впустую 66 %. Веток там нет: на трёх ступенях перед четвёртой — по одному решению.

### 1.2 Варианты на сквозном расчёте

| вариант | режим A: счёт, с | режим B: счёт, с | отпечаток истории A / B | вызовов `advance` на останове A / B |
|---|---|---|---|---|
| 0 (база) | 573 | 392 | `dde9d7b665e757d8` / `4a6f0974d3fcb1a9` | 936 / 969 |
| v2 (этот план) | **391** | — (не действует) | `dde9d7b665e757d8` (= база) | 936 |
| v1 | 450 | 331 | `01665e1e60405ee3` / `58f4d40370621440` (≠ база) | 1100 / 1152 |
| v1 + v2 | 328 | — | `01665e1e60405ee3` | 1100 |

Отпечаток — sha256 массивов $p, T, S_g, R_s$ всех записей истории, времён и $q_o$; первые 16 знаков (`stage_profile.fingerprint`). С v2 режим A считается столько же, сколько режим B (391 и 392 с): работа ступеней одинакова, ветка «открыта» ушла целиком. В выводе `e2e_20A_v2.out.txt` строк `open` на останове нет.

### 1.3 Перепись ветки «открыта» (условие варианта 2, принята ли)

Ключ — (условие $p_{ext} \le p_{wf}$ и $\max_j p_j^{old} \le p_{wf}$ выполнено; ветка принята):

| расчёт | (да, нет) | (да, да) | (нет, нет) | (нет, да) |
|---|---|---|---|---|
| e2e, режим A, база | 1488 | **0** | 2 | 2 |
| e2e, режим A, v1 | 717 | **0** | 2 | 2 |
| 21 пример (`examples_0.out.txt`) | 0 | 0 | 14 | 26 |

Условие выполняется только при останове через забойное давление. В примерах оно не выполняется ни разу, поэтому ни один пример правка не затрагивает: отпечатки всех 21 совпадают с базой (`examples_v2.out.txt`, таблица в шаге 3). Строки «(нет, ·)» — обычная работа запасного пути BUG-014 на добыче (примеры 03, 04a, 10, 11, 12, 13b, 14, 16, 19–21): там ветка «открыта» нужна и принимается 26 раз из 40.

### 1.4 Реальный шаг останова (`plan_tests_check.py`, `plan_tests_check.out.txt`)

Сценарий rs300 (`numerical_solver/tests/data/bug020_rs300`, фикстура `shutin_start`): после 10 сут добычи $p_0$ = 50.8965 бар, $\max p$ = 329.7778 бар; $p_{ext}$ = 330 бар. Шаг 168.75 с при $p_{wf} = p_{ext}$:

| | решения (ступень, ветка): сошлось, итераций | итог |
|---|---|---|
| база | 1 −: нет, 4; 2 shut: нет, 15; **2 open: нет, 10**; 3 shut: нет, 15; **3 open: нет, 10**; 4 shut: да, 20 | $p_0$ = 174.434873 бар, двухфазных 250, $\max S_g$ = 0.308417, ветка shut, смен 0 |
| v2 | 1 −: нет, 4; 2 shut: нет, 15; 3 shut: нет, 15; 4 shut: да, 20 | тот же, побитово |

Модель тестов логики (Nabor_1b, `test_prototype_well_branch._build`): $p_{ext}$ = 200 бар. Состояние `drawn_down` (1 ч отбора при 100 бар): $p_0$ = 111.672 бар, $\max p$ = 200.000000 бар — на границе условия при $p_{wf}$ = 200. Поэтому тесты шага 1 берут $p_{wf}$ = 210 бар (условие выполнено с запасом) и отдельно — состояние, обрезанное до 200 бар (равенство $p_{wf} = p_{ext}$).

## 2. Анализ

### 2.1 Текущее состояние

`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`:
- `advance` (`:346-403`) — ступени по порядку, следующая только при отказе предыдущей:
  1. исходный алгоритм `_advance_phases` с границей $S_g \ge -0.05$;
  2. `_fallback` — запасной путь BUG-014 (`:364`);
  3. `_fallback` с поиском по $\lVert F\rVert_2$ и ограничением $\lvert\Delta S_g\rvert \le 0.2$ — BUG-016 (`:372-378`);
  4. `_fallback` с переключением фаз внутри Ньютона, если `phase_switching_stage` — BUG-020 (`:379-391`).
- `_fallback` (`:404-431`), при BHP: ветка старого состояния (`:415`, при $p_0^{old} \le p_{wf}$ — «закрыта»), согласованный результат принимается (`:421-424`), иначе — другая ветка один раз (`:425-429`).
  - Ветка «закрыта»: поток через забой нулевой, согласована при $p_0 \le p_{wf}$.
  - Ветка «открыта»: $q = WI\,\lambda\,(p_0 - p_{wf}) \ge 0$ (отбор), согласована при $p_0 \ge p_{wf}$.
  - Знак: в прототипе дебит $q > 0$ — отбор (комментарий `blackoil.py:423`). В GPN наоборот: поток к скважине отрицателен ($G^o_{\text{забой}} < 0$, CLAUDE.md, «Конвенция знаков»). Правка работает только внутри прототипа и знаков GPN не касается.
- Перед каждым вызовом ступени 4 при BHP-управлении проходят пять неудачных решений: ступень 1, по две ветки на ступенях 2 и 3. Если на ступени 4 отказывает ветка «закрыта», пробуется ещё и «открыта» — до 40 итераций.

### 2.2 Целевое состояние

- `_fallback` при BHP не пробует ветку «открыта», если $p_{ext} \le p_{wf}$ и $\max_j p_j^{old} \le p_{wf}$. Условие считается один раз на вызов `_fallback`. Ветка «закрыта» и все остальные пути — без изменений.
- Шаг, на котором ступень отказала, остаётся отказом. Меняются только поля ветки отчёта отклонённого шага (`well_branch`, `well_switches` — последняя попытка, DEBT-030): вместо «открыта», 1 смена — «закрыта», 0 смен. Эти поля не пишутся ни в `step_log.csv`, ни в `run_summary.json`, ни в отладочный журнал адаптера.
- Принятые шаги — побитово прежние во всех расчётах, где условие выполнено и ветка «открыта» не принималась. По переписи 1.3 это все известные расчёты.
- Без флага: правка действует и в прототипе по умолчанию (решение 2).

### 2.3 Варианты

**Вариант 2 (выбран): не пробовать заведомо несогласованную ветку «открыта».**

Довод. Ветка «открыта» — отбор: $q \ge 0$, забой — сток. Давление на контуре $p_{ext} \le p_{wf}$, давления старого состояния $\le p_{wf}$. Для уравнения давления со стоком и граничным значением $p_{ext}$ принцип максимума даёт $p_j^{new} \le \max(\max_j p_j^{old}, p_{ext}) \le p_{wf}$ во всех ячейках, в том числе $p_0 \le p_{wf}$. Значит, ветка «открыта» либо несогласована, либо при $p_0 = p_{wf}$ совпадает с «закрыта».

Условие берётся по всем ячейкам, а не только по $p_0$ (уточнение к формулировке реестра). Если в глубине пласта давление выше $p_{wf}$ (например, после закачки), приток оттуда может поднять $p_0$ выше $p_{wf}$, и ветка «открыта» станет законной. Это проверяет тест `test_tried_when_old_pressure_above_target`.

Ограничение довода. Для Black Oil с переключением фаз принцип максимума не доказан: при отрицательной суммарной сжимаемости $c_t$ он может нарушаться. $c_t < 0$ встречается в точках перелёта Ньютона (план BUG-020, 1.1) и у насыщенной нефти по Стендингу выше 345 бар (BUG-019). Поэтому довод проверен переписью: 0 принятых из 1488 и 717 попыток (1.3).

Цена ошибки ограничена. Если где-то ветка «открыта» при этом условии всё же оказалась бы согласованной, шаг не был бы принят этой ступенью: следующая ступень или A-retry с половинным шагом. Несогласованное состояние принято не будет: проверка согласованности (`:424`) не меняется. Худший случай — ни одна ступень не решает шаг ни при каком дроблении, и расчёт падает с `HydroSolver не сошёлся после N подшагов` (адаптер), хотя ветка «открыта» его решила бы. Неверного результата не будет, будет отказ.

Симметричный случай рассмотрен и не нужен. Можно было бы так же не пробовать ветку «закрыта», когда все давления не ниже $p_{wf}$ (на добыче: старт с «открыта», «закрыта» после её отказа). По принципу минимума «закрыта» там тоже несогласована, но на сквозном расчёте это 2 решения за всю добычу, 0.1 с (1.1, `e2e_20A_0.out.txt`, `[добыча]`). Выигрыша нет, а это вне DEBT-040.

- Изменения: `_fallback` — условие (1 строка), проверка при смене ветки (1 строка), комментарий, docstring; шапка модуля.
- Промежуточные состояния: один шаг кода; тесты до него красные, после — зелёные.
- Плюсы: −32 % времени сквозного расчёта в режиме A; принятые шаги побитово; правка локальная, затрагивает один метод.
- Минусы: режим B не ускоряется; в режиме A остаётся 67 % неудачных решений ступеней 1–3 (1.2: `e2e_20A_v2` — 252.8 с впустую из 378.7 с).
- Риски: довод неверен на каком-то будущем сценарии — отказ ступени вместо принятия, см. «цена ошибки».
- Трудоёмкость: 1 файл кода (~12 строк с комментарием), 1 новый файл тестов (~150 строк), CHANGELOG.

**Вариант 1 (отклонён): помнить ступень, решившую прошлый шаг, и начинать следующий шаг сразу с неё.**

Замер 1.2: ещё −16 % в обоих режимах (A: 391 → 328 с вместе с v2; B: 392 → 331 с). Отклонён (решение 1) по трём причинам:
- **меняет истории.** В примере 16 после первого вызова ступени 4 ещё 358 шагов останова решает ступень 4 вместо ступени 1 (`examples_v1.out.txt`: ступени {1: 360, 4: 358} против {1: 717, 4: 1}). Корень тот же с точностью ~$10^{-9}$ бар (план BUG-020, 1.5), но не побитово: README 16 и тесты 16 пришлось бы пересверять;
- **ломает повторный проход `Simulator`.** При дроблении A-retry `Simulator._advance` (`numerical_solver/gpn_multiphase_solver/simulator.py:233-242`) отбрасывает пробный проход и проходит интервал заново тем же дроблением (BUG-010, DEBT-015). Это предполагает, что модель не помнит прошлых вызовов и повторный проход побитово повторяет пробный. С памятью повторный проход начинает с другой ступени и может разойтись с пробным или потребовать вложенного дробления;
- **больше отказов подшагов:** 146 против 132 (A), 153 против 137 (B). Ступень 4, начатая первой, отказала в 88 случаях из 586, и после неё шли ступени 1–3.

К варианту 1 можно вернуться после DEBT-015 (A-retry в `Simulator`, без повторного прохода) — записано в разделе 6.

**Вариант 3 (отклонён в issue #69): ступень 4 сразу после ступени 1, если та отказала на первой итерации.** По замерам признак почти не срабатывает. На первом шаге останова ступень 1 стоит 2–4 итерации (1.4: 4 итерации), а не одну. На следующих шагах ступени отказывают по лимиту итераций (план BUG-020, 1.2).

### 2.4 Выбор

Вариант 2. Минимальный дифф (один метод), внешний API не меняется, принятые шаги побитовы, результат проверяется тестами на подмене `_advance_phases` и на реальном шаге.

### 2.5 Подводные камни

- ✅ **Все места вызова.** `_fallback` вызывается только из `advance` (`blackoil.py:364, 374, 387`; поиск `_fallback` по `numerical_solver/*.py`). Тесты его не подменяют, а подменяют `_advance_phases`.
- ✅ **Зависимости пакетов, циклы импорта.** Новых импортов в прототипе нет (`np` уже импортирован). Новый файл тестов импортирует помощники из `test_prototype_phase_switching.py` и `test_prototype_well_branch.py` — так же, как уже делает `test_prototype_phase_switching.py:295`.
- ✅ **Обратная совместимость API.** Сигнатуры не меняются, новых полей и флагов нет.
- ✅ **Состояние при ошибке.** Ранний `return` при пропуске ветки — внутри `try`. `finally` (`:430-431`) по-прежнему возвращает `_sg_lower_bound`, `_well_branch`. Тест `_assert_restored` в каждом тесте логики.
- ✅ **Существующие тесты.** Все тесты логики веток (`test_prototype_well_branch.py`, `test_prototype_globalization.py`, `test_prototype_phase_switching.py`) задают $p_{wf}$ = 100, 105, 150, 195 бар при $p_{ext}$ = 200 бар — условие не выполняется, перебор прежний. Тест `test_bhp_shutin_takes_shut_branch` (реальный шаг при $p_{wf} = p_{ext}$) проверяет итог, а не перебор: итог побитово тот же (1.4).
- ✅ **Docstrings.** Ссылок `\eqref{}` в `_fallback` нет. Docstring дополняется.
- ✅ **Конфиги.** Не меняются.
- ✅ **Связь с другими задачами.**
  - DEBT-030: поля Ньютона отчёта общего отказа — исходного алгоритма, не меняются; поля ветки — последней попытки, теперь это «закрыта».
  - BUG-020: ступень 4 вызывает тот же `_fallback`, правка действует и в ней (1.1: 132 попытки «открыта» по 40 итераций уходят).
  - DEBT-015: правка не трогает A-retry.
  - FEAT-029 (пример останова с сильным охлаждением): если он будет считаться в режиме A, то получит ускорение.
  - BUG-014, выбор стратегии веток ([[запасной путь с отрицательной насыщенностью и веткой скважины снимает порог шага на скачке p_wf вверх]], раздел «Начальная ветка»): «по старому состоянию, при отказе — другая ветка» дала 0 отказов на 80 скачках `Nabor_1b`. Вторая ветка нужна, когда $p_{wf}$ подскочил выше $p_0$, но остался ниже $p_{ext}$: приток с контура может снова открыть скважину. Там $p_{ext} > p_{wf}$, условие не выполнено, перебор прежний (тест `test_tried_when_outer_above_target`).
- ✅ **Параллельная работа** (на 2026-10-07, `6d14a5c`).
  - `refactor/debt-041/example03-max-retries-table` не влита. Меняет README 03, 04a, 05, комментарий `io/config.py` (уже в базе, `e6666df`), docstring двух тестов. С `blackoil.py` и новым файлом тестов не пересекается.
  - DEBT-015: ветки и плана нет, в `vault/issues/debt-015/probes/` идут замеры. Если влить раньше, изменятся отпечатки сквозного расчёта (шаг 0, п. 5).
- ✅ **Производительность.** Добавляются `np.max` по $N$ давлениям на вызов `_fallback` — пренебрежимо. Выигрыш — 1.2.
- ⚠️ **Прототип.** Правка в `HydroSolverPrototype/`, флага нет (решение 2), поэтому она действует и в собственных расчётах прототипа. Нужны тесты прототипа и регрессия (шаги 2 и 4). Ожидание: **побитово**, `--quick` 11/11 PASS, полная 17/17 PASS. Обоснование: принятые шаги меняются, только если ветка «открыта» при условии принималась бы, а перепись этого не видела. `step_log.csv` полей ветки не содержит (`simulation.py:83, 99`). FAIL — не повод переснимать эталон: значит, довод нарушен на кейсе регрессии. Тогда разобрать: найти шаг, где ветка принята при условии (проба `stage_profile.py` с `Profile` на модели кейса), и остановиться с вопросом пользователю.

  Проверено аудитом (2026-10-07, `6d14a5c`). `run_regression.py --quick` на коде шага 2 (подмена `_fallback` блоком «стало» через `probes/regression_hook/sitecustomize.py`, файлы проекта не правились) — 11/11 PASS, на базе — тоже 11/11. Журнал `probes/regression_patch.out.txt`: `_fallback` при BHP вызывается только в T03 (6 раз) и T04 (4 раза), условие пропуска не выполнено ни разу. Значит, регрессия прототипа подтверждает лишь то, что остальное не изменилось. Сам пропуск проверяют только новые тесты (шаг 1) и сквозной расчёт (шаг 3). T05 (полная регрессия) аудитом не прогонялся.

### 2.6 Обнаруженные проблемы

Новых записей в реестр нет.
- Остаток DEBT-040: после правки в обоих режимах останова 66–67 % времени `advance` уходит на неудачные решения ступеней 1–3 (1.2: `e2e_20A_v2` — 252.8 из 378.7 с, `e2e_20B_0` — 251.7 из 379.1 с; с вариантом 1 было бы 54 %). Вариант 1 его сокращает, но отклонён (решение 1). Причины и возврат после DEBT-015 — раздел 2.3; отдельной записи нет (решение пользователя).
- Попутно: при перенаправлении `>` в Windows PowerShell 5.1 вывод Python пишется в UTF-16 с искажённой кириллицей. Пробы шага 3 запускать через `Start-Process -RedirectStandardOutput` или `Tee-Object` (команды ниже).

### 2.7 Затронутые файлы

| файл | шаг | роль |
|---|---|---|
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` | 2 | `_fallback` (`:404-431`): условие и пропуск ветки; шапка модуля (`:21-24`) |
| `numerical_solver/tests/test_prototype_open_branch_skip.py` (новый) | 1 | 7 тестов: 6 на подмене `_advance_phases`, 1 на реальном шаге |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` | 4 | раздел «Local changes — GPN project (DEBT-040)» |
| `vault/issues/debt-040/probes/stage_profile.py` | 3 | проба: отпечатки примеров и сквозной расчёт (не тест, не меняется) |
| `vault/roadmap/известные баги и технический долг.md`, `vault/knowledge/debugging/останов из развитой газовой зоны — ….md`, `vault/issues/debt-040/05-comment-done.md` | 6 | vault и issue |

## 3. Шаги

### Шаг 0: Подготовка

**Цель:** ветка и базовые значения.

**Файлы:** —

**Что сделать:**
1. Ветка — раздел «Как начать», п. 3.
2. Из `numerical_solver/`:
   ```powershell
   .venv\Scripts\python -m pytest tests/ --collect-only -q          # 1344
   .venv\Scripts\python -m pytest tests/ -m "not slow" -q           # 1108 passed, время записать
   ```
3. Из `numerical_solver/HydroSolverPrototype/Prototype_1.0.3` (до правки):
   ```powershell
   ..\..\.venv\Scripts\python -m pytest tests -q                    # 97 passed
   ..\..\.venv\Scripts\python regression\run_regression.py --quick  # 11/11 PASS, ~8 мин
   ```
   Выход регрессии — `OUTPUT/REGRESSION_<время>/`; после разбора удалить.
4. Если числа расходятся с записанными (1344 / 1108 / 97 / 11), остановиться и выяснить: в базу влито что-то после `299d6a7`. Если это меняет `advance`, `_fallback` или `_advance_phases`, номера строк плана нужно сверить заново.
5. **Годны ли отпечатки базы для шага 3.** Они сняты на `299d6a7`. Если с тех пор в базу влит код, меняющий расчёт, шаг 3 покажет ложное расхождение. Проверка (из корня проекта):
   ```powershell
   git diff --stat 299d6a7 HEAD -- numerical_solver/gpn_multiphase_solver numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil numerical_solver/examples ':(exclude)*.md'
   ```
   - Пусто или только комментарии и docstring (проверить `git diff 299d6a7 HEAD -- <файл>`): отпечатки годны. На 2026-10-07 (`6d14a5c`) вывод — одна строка `io/config.py`: комментарий к `max_retries` (DEBT-041, `e6666df`), исполняемый код не менялся.
   - Изменён исполняемый код, конфиг или таблица: до шага 2 снять отпечатки базы заново той же пробой на коде базы. Команды шага 3, вывод — в `base_examples.out.txt`, `base_e2e_20A.out.txt`, `base_e2e_20B.out.txt`. В шаге 3 сравнивать с ними, а не с таблицей плана. Кандидаты: DEBT-015 (перенос A-retry в `Simulator`; в `vault/issues/debt-015/probes/` идут замеры) — меняет сквозной расчёт.

**Проверка:** числа совпадают; отпечатки базы годны или сняты заново.

**Зависимости:** блокирует все шаги.

**Оценка:** ~10 мин (регрессия — 8).

### Шаг 1: Тесты (красные)

**Цель:** зафиксировать нужный перебор веток до правки.

**Файлы:** `numerical_solver/tests/test_prototype_open_branch_skip.py` (новый).

**Контекст.**

Тесты логики устроены как блок C `test_prototype_phase_switching.py`. `_install_fake_phases` подменяет `_advance_phases` и записывает ключ каждого вызова: (ветка, граница $S_g$, поиск по $\lVert F\rVert_2$, ступень 4). Ответ на ключ — из словаря плана: (сошлось, $p_0$, итераций). Константы ключей — оттуда же: `ORIG` — ступень 1, `SHUT`/`OPEN` — ступень 2, `SHUT3`/`OPEN3` — ступень 3, `SHUT4`/`OPEN4` — ступень 4.

Модель — Nabor_1b из `test_prototype_well_branch.py`: 12 ячеек, $p_{ext}$ = 200 бар. Состояние `drawn_down` — после 1 ч отбора при 100 бар: $p_0$ = 111.672, $\max p$ = 200.000000 бар (1.4).

Все тесты логики дают в словаре ответы и для ключей «открыта». Тогда до правки тест падает на сравнении списка вызовов (видно, что ветка пробуется), а не на `KeyError`.

Реальный шаг — фикстура `shutin_start` из `test_prototype_phase_switching.py`: модель GPN-фабрики со ступенью 4 и состояние после 10 сут добычи сценария rs300. Шаг 168.75 с при $p_{wf} = p_{ext}$; числа — 1.4.

**Что сделать:** создать файл с содержимым:

```python
"""DEBT-040: запасной путь advance при BHP не пробует заведомо несогласованную ветку «открыта».

Запасной путь (BUG-014, RadialBlackOilModel._fallback) при управлении забойным
давлением перебирает ветки скважины: «закрыта» (поток через забой нулевой,
согласована при p0 <= p_wf) и «открыта» (отбор q = WI*lambda*(p0 - p_wf) >= 0,
согласована при p0 >= p_wf). Если давление на контуре p_ext и давления
старого состояния во всех ячейках не выше p_wf, то при отборе ни одна ячейка
не поднимется выше p_wf (принцип максимума уравнения давления): p0 <= p_wf,
ветка «открыта» несогласована. Останов «p_wf = p_ext» после добычи — ровно этот
случай: сквозной расчёт конфига 20 пробовал её 1488 раз, принял 0, на неё ушло
38 % времени останова. Теперь в этом случае она не пробуется; принятые шаги не
меняются.

План: vault/plans/debt-040 shutin-skip-failing-stages.md; числа —
vault/issues/debt-040/probes/plan_tests_check.out.txt.
"""

import numpy as np
import pytest

# Логика ступеней без Ньютона (подмена _advance_phases) и реальный шаг останова
# сценария rs300 — помощники и фикстура тестов BUG-020
from .test_prototype_phase_switching import (  # noqa: F401
    DT_STAGE4, OPEN, OPEN3, OPEN4, ORIG, SHUT, SHUT3, SHUT4,
    _assert_restored, _install_fake_phases, shutin_start)
# Модель Nabor_1b (p_ext = 200 бар) и состояние после часа отбора при 100 бар
from .test_prototype_well_branch import _model, drawn_down  # noqa: F401

P_EXT_NABOR = 200.0   # давление на контуре модели Nabor_1b, бар
P_WF_ABOVE = 210.0    # p_wf выше p_ext и всех давлений drawn_down (max 200.0 бар)
ALL_BHP_KEYS = (ORIG, SHUT, OPEN, SHUT3, OPEN3, SHUT4, OPEN4)


# ═══════════════════════════════════════════════════════════
# A. Перебор веток на подмене _advance_phases
# ═══════════════════════════════════════════════════════════

class TestOpenBranchSkipLogic:
    """Какие (ступень, ветка) перебирает advance; старт с «закрыта» (p0 старое = 111.7 бар)."""

    def test_skipped_when_hopeless(self, drawn_down):
        # p_wf = 210 > p_ext = 200 >= max p_old: «открыта» несогласована на всех
        # ступенях. Ступени 1-3 отказывают, ступень 4 на «закрыта» сходится с
        # p0 = 205 <= 210. До DEBT-040: [ORIG, SHUT, OPEN, SHUT3, OPEN3, SHUT4].
        model = _model(P_WF_ABOVE)
        model.phase_switching_stage = True
        assert model.p_outer_bar == P_EXT_NABOR
        assert drawn_down.pressure_bar.max() <= P_WF_ABOVE
        plan = {k: (False, 0.0, 3) for k in ALL_BHP_KEYS}
        plan[SHUT4] = (True, 205.0, 20)
        calls = _install_fake_phases(model, plan)
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG, SHUT, SHUT3, SHUT4]
        assert rep.converged and rep.phase_switching
        assert (rep.well_branch, rep.well_switches) == ("shut", 0)
        _assert_restored(model)

    def test_all_fail_when_hopeless(self, drawn_down):
        # Отказ всех ступеней: ни одной попытки «открыта». Поля Ньютона отчёта —
        # исходного алгоритма (DEBT-030: 15 итераций, невязка 15.0 у подмены),
        # поля ветки — последней попытки: «закрыта», 0 смен (до DEBT-040 —
        # «открыта», 1 смена). Эти поля не пишутся ни в один выходной файл.
        model = _model(P_WF_ABOVE)
        model.phase_switching_stage = True
        plan = {k: (False, 0.0, 9) for k in ALL_BHP_KEYS}
        plan[ORIG] = (False, 0.0, 15)
        calls = _install_fake_phases(model, plan)
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG, SHUT, SHUT3, SHUT4]
        assert not rep.converged
        assert rep.iterations == 15 and rep.residual_inf == 15.0
        assert (rep.well_branch, rep.well_switches) == ("shut", 0)
        _assert_restored(model)

    def test_skipped_at_target_equal_outer(self, drawn_down):
        # Останов «p_wf = p_ext»: условие нестрогое (p_ext <= p_wf, max p_old <= p_wf).
        # Состояние обрезано до 200 бар: у drawn_down max p = 200.000000 на границе.
        model = _model(P_EXT_NABOR)
        model.phase_switching_stage = True
        old = drawn_down.copy()
        old.pressure_bar = np.minimum(old.pressure_bar, P_EXT_NABOR)
        plan = {k: (False, 0.0, 3) for k in ALL_BHP_KEYS}
        plan[SHUT4] = (True, 199.0, 20)
        calls = _install_fake_phases(model, plan)
        _, rep = model.advance(old, 3600.0)
        assert calls == [ORIG, SHUT, SHUT3, SHUT4]
        assert rep.converged and rep.well_branch == "shut"
        _assert_restored(model)

    def test_prototype_default_skips_too(self, drawn_down):
        # Правка без флага (решение пользователя 2026-10-07): прототип по умолчанию
        # (три ступени) тоже не пробует «открыта». «Закрыта» здесь сходится, но
        # несогласована (p0 = 215 > 210 — на настоящем Ньютоне при этих давлениях
        # невозможно, это подмена): ступень отказывает без попытки «открыта».
        model = _model(P_WF_ABOVE)
        assert model.phase_switching_stage is False
        plan = {k: (False, 0.0, 3) for k in ALL_BHP_KEYS}
        plan[ORIG] = (False, 0.0, 15)
        plan[SHUT] = plan[SHUT3] = (True, 215.0, 4)
        calls = _install_fake_phases(model, plan)
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG, SHUT, SHUT3]
        assert not rep.converged
        _assert_restored(model)

    def test_tried_when_outer_above_target(self, drawn_down):
        # p_ext = 200 > p_wf = 195: приток с контура может поднять p0 выше p_wf —
        # ветка «открыта» возможна и пробуется на каждой ступени, как до DEBT-040
        model = _model(195.0)
        model.phase_switching_stage = True
        calls = _install_fake_phases(model, {k: (False, 0.0, 3) for k in ALL_BHP_KEYS})
        model.advance(drawn_down, 3600.0)
        assert calls == [ORIG, SHUT, OPEN, SHUT3, OPEN3, SHUT4, OPEN4]
        _assert_restored(model)

    def test_tried_when_old_pressure_above_target(self, drawn_down):
        # p_ext = 200 <= p_wf = 210, но в старом состоянии ячейка 6 при 215 бар
        # (например, после закачки): приток из неё может поднять p0 выше p_wf.
        # Условия на p0 старого состояния мало — нужен максимум по ячейкам.
        model = _model(P_WF_ABOVE)
        model.phase_switching_stage = True
        old = drawn_down.copy()
        old.pressure_bar[6] = 215.0
        assert old.pressure_bar[0] <= P_WF_ABOVE   # старт — с «закрыта»
        calls = _install_fake_phases(model, {k: (False, 0.0, 3) for k in ALL_BHP_KEYS})
        model.advance(old, 3600.0)
        assert calls == [ORIG, SHUT, OPEN, SHUT3, OPEN3, SHUT4, OPEN4]
        _assert_restored(model)


# ═══════════════════════════════════════════════════════════
# B. Реальный шаг останова «p_wf = p_ext» (сценарий rs300)
# ═══════════════════════════════════════════════════════════

def test_bhp_shutin_step_without_open_branch(shutin_start):
    """Шаг 168.75 с при p_wf = p_ext: ветка «открыта» не пробуется, итог прежний.

    Замер плана (plan_tests_check.out.txt): до DEBT-040 ветки решений по
    ступеням 1-4 — [-, shut, open, shut, open, shut] (обе «open» не сходятся
    за 10 итераций), после — без «open»; итог побитово тот же: p(r_w) =
    174.434873 бар, двухфазных 250, ветка «закрыта», ступень 4.
    """
    model, ps, p_ext = shutin_start
    model.set_bhp_control(p_ext)
    branches = []
    base = model._advance_phases

    def spy(state_old, dt_s, max_active_iter=12, max_newton=15):
        branches.append(model._well_branch)
        return base(state_old, dt_s, max_active_iter, max_newton)

    model._advance_phases = spy
    try:
        new, rep = model.advance(ps, DT_STAGE4)
    finally:
        del model._advance_phases   # вернуть метод класса: фикстура общая для модуля
    assert branches == [None, "shut", "shut", "shut"]
    assert rep.converged and rep.phase_switching and rep.well_branch == "shut"
    assert new.pressure_bar[0] == pytest.approx(174.434873, abs=1e-5)
    assert int(new.gas_active.sum()) == 250
    _assert_restored(model)
```

**Проверка после этого шага** (из `numerical_solver/`):
```powershell
.venv\Scripts\python -m pytest tests/test_prototype_open_branch_skip.py -q
```
Ожидание: **5 failed, 2 passed**.
- Красные: `test_skipped_when_hopeless`, `test_all_fail_when_hopeless`, `test_skipped_at_target_equal_outer`, `test_prototype_default_skips_too` — в списке вызовов есть `OPEN`, `OPEN3` (и `OPEN4` в `test_all_fail_when_hopeless`); `test_bhp_shutin_step_without_open_branch` — `branches == [None, 'shut', 'open', 'shut', 'open', 'shut']`.
- Зелёные уже сейчас: `test_tried_when_outer_above_target`, `test_tried_when_old_pressure_above_target`. Это нормально: они проверяют, что правка не тронет случаи, где ветка нужна.

Если красный упал не на сравнении списка, а на `KeyError` или `AttributeError`, тест написан неверно: сверить ключи с `test_prototype_phase_switching.py:297-300`.

- Регресс: быстрый не нужен — код не менялся. Число тестов: `--collect-only -q` → 1351 (1344 + 7).

**Подводные камни:**
- `drawn_down` и `shutin_start` — фикстуры с областью модуля, общие для тестов файла. Состояние меняется только в копии (`drawn_down.copy()` копирует массивы, `radial_blackoil/state.py:15-16`). Подмена `_advance_phases` на модели `shutin_start` снимается в `finally` (`del` атрибута экземпляра возвращает метод класса).
- `shutin_start` считается в этом модуле заново (~2 с): фикстура с областью модуля, импорт создаёт свой экземпляр.
- Импортировать только помощники и фикстуры, не классы `Test*`: иначе pytest соберёт чужие тесты второй раз.

**Зависимости:** требует шаг 0; блокирует шаг 2.

**Оценка:** ~150 строк, ~20 мин.

### Шаг 2: Правка `_fallback`

**Цель:** не пробовать ветку «открыта», когда она заведомо несогласована.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`.

**Контекст:** раздел 2.3 — довод, его ограничение и цена ошибки. Комментарии прототипа пишутся по-английски, как и весь его код.

**Что сделать.**

**2.1 — шапка модуля** (`:21-24`, после абзаца BUG-020, перед закрывающими `"""`):
- было:
```python
BUG-020: a fourth stage of advance() (phase_switching_stage, off by default): the
BUG-014 fallback with _newton_switching -- phase switches after every Newton
iteration, per-cell update limits, no line search, upstream cells held on faces
whose flow direction flips.
"""
```
- стало:
```python
BUG-020: a fourth stage of advance() (phase_switching_stage, off by default): the
BUG-014 fallback with _newton_switching -- phase switches after every Newton
iteration, per-cell update limits, no line search, upstream cells held on faces
whose flow direction flips.
DEBT-040: under BHP control the fallback does not try the 'open' well branch
where it cannot be consistent (outer and all old cell pressures <= p_wf).
"""
```

**2.2 — `_fallback`** (`:404-431`):
- было:
```python
    def _fallback(self,state_old,dt_s,max_active_iter,max_newton):
        """BUG-014 fallback: no lower bound on Sg; BHP control fixes the well branch
        (start from the old state's branch, accept a consistent result only, try the
        other branch once); OIL_RATE control: a plain retry without the Sg bound."""
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
- стало:
```python
    def _fallback(self,state_old,dt_s,max_active_iter,max_newton):
        """BUG-014 fallback: no lower bound on Sg; BHP control fixes the well branch
        (start from the old state's branch, accept a consistent result only, try the
        other branch once, 'open' only where it can be consistent, DEBT-040);
        OIL_RATE control: a plain retry without the Sg bound."""
        self._sg_lower_bound=None
        try:
            if self.control_mode!='BHP':
                new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
                rep.fallback=True; return new,rep
            target=float(self.p_bhp_bar)
            # Start from the branch of the old state; shut-in steps start on 'shut'.
            branch='shut' if float(state_old.pressure_bar[0])<=target else 'open'
            # DEBT-040: 'open' is accepted only with p0 >= target (production, q >= 0).
            # With the outer pressure and every old cell pressure <= target, a producing
            # well and the outer boundary raise no cell above target (maximum principle
            # of the pressure equation), so p0 <= target and 'open' cannot be consistent.
            # Not proved for black oil with phase switches (c_t < 0 at Newton overshoots);
            # measured: shut-in with BHP raised to the outer pressure after production
            # (GPN example 20, 3 days) tried 'open' 1488 times, accepted it 0 times, and
            # it took 38 % of the shut-in time.  A wrong guess here could only reject a
            # step, never accept an inconsistent one.
            open_hopeless=self.p_outer_bar<=target and float(np.max(state_old.pressure_bar))<=target
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
                if other in tried or (other=='open' and open_hopeless):
                    rep.converged=False; return new,rep
                branch=other
        finally:
            self._sg_lower_bound=-0.05; self._well_branch=None
```

Почему стартовую ветку трогать не нужно: при `open_hopeless` выполняется $\max_j p_j^{old} \le p_{wf}$, значит, и $p_0^{old} \le p_{wf}$, и старт всегда с «закрыта» (`:415`). Пропуск нужен только при смене ветки.

**Проверка после этого шага:**
```powershell
.venv\Scripts\python -m pytest tests/test_prototype_open_branch_skip.py -q    # 7 passed
.venv\Scripts\python -m pytest tests/ -m "not slow" -q                        # 1115 passed (1108 + 7)
```
Регресс прототипа (из `numerical_solver/HydroSolverPrototype/Prototype_1.0.3`):
```powershell
..\..\.venv\Scripts\python -m pytest tests -q                    # 97 passed
..\..\.venv\Scripts\python regression\run_regression.py --quick  # 11/11 PASS, побитово
```
- Регресс: быстрый.
- Регресс прототипа: ожидание **побитово**, 11/11 PASS. При FAIL — раздел 2.5, «Прототип»: эталон не переснимать, найти шаг, остановиться с вопросом пользователю.

**Подводные камни:** 2.5 — «Состояние при ошибке», «Существующие тесты», «Прототип».

**Зависимости:** требует шаг 1; блокирует шаги 3–6.

**Оценка:** ~12 строк, ~20 мин (регрессия — 8).

### Шаг 3: Побитовость на примерах и сквозном расчёте (проба, не тест)

**Цель:** подтвердить замер 1.2–1.3 на коде ветки: история не меняется, ветка «открыта» на останове не пробуется.

**Файлы:** вывод в `vault/issues/debt-040/probes/` (`branch_examples.out.txt`, `branch_e2e_20A.out.txt`, `branch_e2e_20B.out.txt`).

**Контекст.**

Проба `stage_profile.py` с вариантом `0` теперь исполняет код ветки: правка уже в `_fallback`, подменять нечего. Отпечатки базы записаны при планировании (`examples_0.out.txt`, `e2e_20A_0.out.txt`, `e2e_20B_0.out.txt`).

Режим B — контроль нагрузки: правка его не касается (веток нет), поэтому при одновременном запуске время A должно сравняться с временем B. При планировании было A 573 с против B 392 с, с вариантом 2 — 391 против 392 с.

**Что сделать.** Проба и выводы базы лежат в основном каталоге (`<КОРЕНЬ>\vault\issues\debt-040\probes\`); туда же пишутся выводы ветки. Какое дерево считать, задаёт `DEBT040_SOLVER`:
```powershell
$ROOT = "D:\Lessons\Grants\2026\GPN\Oil_Gas"                 # <КОРЕНЬ>
$py = "$ROOT\numerical_solver\.venv\Scripts\python.exe"
$probe = "$ROOT\vault\issues\debt-040\probes\stage_profile.py"
$out = "$ROOT\vault\issues\debt-040\probes"
$env:DEBT040_SOLVER = "<W>\numerical_solver"                 # без worktree: "$ROOT\numerical_solver"
$p1 = Start-Process $py -ArgumentList "`"$probe`" e2e 20 10 3 A 3600 0" -RedirectStandardOutput "$out\branch_e2e_20A.out.txt" -NoNewWindow -PassThru
$p2 = Start-Process $py -ArgumentList "`"$probe`" e2e 20 10 3 B 3600 0" -RedirectStandardOutput "$out\branch_e2e_20B.out.txt" -NoNewWindow -PassThru
$p3 = Start-Process $py -ArgumentList "`"$probe`" examples 0" -RedirectStandardOutput "$out\branch_examples.out.txt" -NoNewWindow -PassThru
$p1, $p2, $p3 | Wait-Process      # ~7–10 мин
```
Проверить:
1. Строка `код:` во всех трёх файлах — пути дерева ветки.
2. `branch_examples.out.txt`: отпечатки всех 21 примера равны отпечаткам `examples_0.out.txt`. Перепись «открыта» по всем: `{(False, True): 26, (False, False): 14}`.

   | пример | отпечаток базы |
   |---|---|
   | 01_single_phase_no_jt | `d3b971afd10493d9` |
   | 02_single_phase_jt | `970bffc3a8bce9bd` |
   | 03_standing_corey | `0f95c6eff3baebbe` |
   | 04_table_table | `32c4139c7325800f` |
   | 04a_high_gas_saturation | `62e5afc33f9ca834` |
   | 05_standing_table_rp | `52748f56d1a21b52` |
   | 06_table_corey_rp | `4b0b1440bfba316f` |
   | 07_degassing_adiabatic_only | `72d0d246396e8d93` |
   | 08_degassing_jt | `5c44a34ca6d8f998` |
   | 09_degassing_latent_heat | `cce80173c5f39d5b` |
   | 10_deep_degassing | `0783a76b95dc50b0` |
   | 11_degassing_at_boundary | `941eea0f0a005317` |
   | 12_large_drainage_radius | `ec0db01f88694d93` |
   | 13a_pwf_ramp_down | `8a9a8bc9eed1a9ee` |
   | 13b_pwf_alternating | `4deb61f2fbdb642f` |
   | 14_high_gor_cooling | `9005c45b81501712` |
   | 15_oil_rate_ramp_up | `69fbfced2088f758` |
   | 16_well_shut_in | `200807cb0ba45a4b` |
   | 19_rs150_cooling | `7d70d92347309bf8` |
   | 20_rs300_cooling | `280897660f6559c8` |
   | 21_rs100_cooling | `1cc433e787ffff46` |

3. `branch_e2e_20A.out.txt`:
   - итог ✓, отпечаток `dde9d7b665e757d8`;
   - на останове нет строк ветки `open`; решила ступень {0: 132, 1: 230, 3: 56, 4: 518};
   - перепись `{(False, False): 2, (False, True): 2}` — попытки на добыче, условие не выполнено.
4. `branch_e2e_20B.out.txt`: отпечаток `4a6f0974d3fcb1a9`. Время A ≈ время B (±10 %) — справочно: время зависит от загрузки машины, расхождение не повод останавливаться. Критерий — отпечатки и отсутствие строк `open` на останове.

Если отпечаток расходится, остановиться. Значит, правка изменила принятый шаг (или проба взяла другое дерево — проверить строку `код:`). Разбор: найти первый расходящийся шаг (проба с журналом `advance`), сообщить пользователю.

- Регресс: не нужен — код не меняется.

**Подводные камни:** не перенаправлять вывод через `>` в Windows PowerShell 5.1: файл получится в UTF-16 с искажённой кириллицей (2.6).

**Зависимости:** требует шаг 2.

**Оценка:** ~10 мин счёта.

### Шаг 4: CHANGELOG прототипа и полная регрессия

**Цель:** записать правку в журнал прототипа, подтвердить 17/17 PASS.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`.

**Что сделать** (сначала регрессия: текст журнала утверждает «17/17 PASS»):
1. Зафиксировать HEAD: каждый кейс регрессии — отдельный процесс, и влитая посреди прогона чужая ветка даст смешанный прогон. Затем полная регрессия из `numerical_solver/HydroSolverPrototype/Prototype_1.0.3`:
```powershell
git rev-parse --short HEAD
..\..\.venv\Scripts\python regression\run_regression.py      # ~45 мин, 17/17 PASS
```
   Выход `OUTPUT/REGRESSION_<время>/` удалить после разбора. FAIL — дальше не идти, раздел 2.5, «Прототип».
2. После PASS — в конец `CHANGELOG_1.0.3.md` (после раздела BUG-020) добавить раздел, текст как есть:
```markdown

## Local changes — GPN project (DEBT-040): BHP fallback skips the 'open' branch where it cannot be consistent
- Problem: under BHP control the BUG-014 fallback (`_fallback()`, used by the second, third and fourth stages of `advance()`) tries the other well branch after the first fails. The 'open' branch is accepted only with p0 >= p_wf (production). In a shut-in with the BHP raised to the outer pressure after production (GPN example 20, 10 days of production + 3 days of shut-in, dt_integration = 3600 s) the 'open' branch was tried 1488 times and never accepted (its Newton converges to p0 < p_wf, or fails; on the fourth stage it runs all 40 iterations); it took 38 % of the shut-in time.
- `_fallback()`: the 'open' branch is not tried when the outer pressure and every old cell pressure are <= p_wf. A producing well and the outer boundary then raise no cell above p_wf (maximum principle of the pressure equation), so p0 <= p_wf and 'open' cannot be consistent. The argument is not proved for black oil with phase switches; it is checked by a census (0 accepted of 1488 and 717 tries) and cannot accept an inconsistent state: a wrong skip could only reject a step. The 'shut' branch, the consistency check and OIL_RATE control are unchanged. No flag: the change applies to the prototype's own runs too.
- Accepted steps are bitwise unchanged: regression 17/17 PASS, the 21 GPN examples bitwise (none of them meets the condition), the GPN shut-in run above bitwise and 573 -> 391 s. Of a rejected step's report only the branch fields change (`well_branch`, `well_switches`: the last attempt is now 'shut', 0 switches); they are not written to any output file.
- Tests: `numerical_solver/tests/test_prototype_open_branch_skip.py` of the GPN project (7). Physics, residual equations, tolerances and Newton/active-set logic are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/69; plan: `vault/plans/debt-040 shutin-skip-failing-stages.md` of the GPN project.
```
   Время 573 → 391 с — замер плана (1.2). Если шаг 3 дал другое время ветки при той же нагрузке, указать оба числа и условия замера.

**Проверка после этого шага:**
- Регресс: `--collect-only -q` → 1351 (меняется только документ).
- Регресс прототипа: полная регрессия 17/17 PASS, побитово. FAIL — раздел 2.5, «Прототип».

**Зависимости:** требует шаги 2, 3.

**Оценка:** ~10 строк, ~50 мин (регрессия).

### Шаг 5: Полный прогон GPN

**Цель:** все тесты зелёные.

**Что сделать** (из `numerical_solver/`):
```powershell
.venv\Scripts\python -m pytest tests/ -q      # 1351 passed, ~10 мин
```

**Проверка:**
- Регресс: полный — конец реализации (`/implement` §3.1). Примеры правка не меняет (шаг 3), поэтому тесты на `results` должны пройти без изменений.

**Зависимости:** требует шаг 4.

**Оценка:** ~10 мин.

### Шаг 6: Vault и issue

**Цель:** зафиксировать результат.

**Что сделать:**
1. `vault/roadmap/известные баги и технический долг.md`, запись DEBT-040:
   - **Статус:** ✅ ЗАКРЫТ (дата, merge-коммит);
   - строка итога: «вариант 2: ветка «открыта» при $p_{ext} \le p_{wf}$, $\max p^{old} \le p_{wf}$ не пробуется; режим A 573 → 391 с, побитово; вариант 1 отклонён (план, 2.3)»;
   - строка остатка, чтобы закрытая запись не вводила в заблуждение своим заголовком: «Остаток: перед ступенью 4 по-прежнему три неудачных решения (ступени 1–3), 66–67 % времени `advance` на останове в обоих режимах (план, 1.2). Отдельной записи нет — решение пользователя 2026-10-07; вернуться после DEBT-015»;
   - **План:** уже `[[debt-040 shutin-skip-failing-stages]]`.
2. `vault/knowledge/debugging/останов из развитой газовой зоны — забойная ячейка без потока и дребезг ячейки выше по потоку.md` — в раздел «Что сработало» одна строка: «DEBT-040: при $p_{wf} = p_{ext}$ запасной путь не пробует ветку «открыта» — режим A 573 → 391 с, побитово». В «Связано» — ссылка на план DEBT-040.
3. `vault/issues/debt-040/05-comment-done.md` — итог: шаги, числа тестов (1351, прототип 97, регрессия 17/17), отпечатки, время; публикация:
   ```powershell
   gh issue comment 69 --repo ArturSalamatin/Oil_Gas --body-file vault/issues/debt-040/05-comment-done.md
   ```
4. Плану — `status: реализован`, коммиты.

**Проверка:** `--collect-only -q` → 1351.

**Зависимости:** требует шаг 5.

**Оценка:** ~15 мин.

## 4. Тестовая стратегия

**Тест:** `test_skipped_when_hopeless`
**Файл:** `numerical_solver/tests/test_prototype_open_branch_skip.py` (новый)
**Сценарий:** BHP $p_{wf}$ = 210 > $p_{ext}$ = 200 ≥ $\max p^{old}$; ступени 1–3 отказывают, ступень 4 на «закрыта» сходится.
**Setup:** Nabor_1b, `drawn_down`, подмена `_advance_phases`.
**Ожидание:** вызовы `[ORIG, SHUT, SHUT3, SHUT4]`; сошлось, ветка «закрыта», 0 смен.
**База:** до правки `[ORIG, SHUT, OPEN, SHUT3, OPEN3, SHUT4]`.
**Предотвращает:** возврат перебора несогласованной ветки.

**Тест:** `test_all_fail_when_hopeless` — общий отказ: без «открыта» на всех ступенях, включая 4-ю; поля Ньютона — исходного алгоритма (DEBT-030 не сломан). **Предотвращает:** поломку отчёта отказа.

**Тест:** `test_skipped_at_target_equal_outer` — $p_{wf} = p_{ext}$ (реальный режим останова), условие нестрогое. **Предотвращает:** строгое `<` в условии — тогда правка не действовала бы ровно в режиме A.

**Тест:** `test_prototype_default_skips_too` — флаг выключен, три ступени; «закрыта» сходится несогласованно. **Предотвращает:** привязку правки к флагу (против решения 2) и попытку «открыта» после несогласованной «закрыта».

**Тест:** `test_tried_when_outer_above_target` — $p_{ext} > p_{wf}$: перебор прежний. **Предотвращает:** пропуск ветки, когда приток с контура может сделать её согласованной (условие без $p_{ext}$).

**Тест:** `test_tried_when_old_pressure_above_target` — ячейка старого состояния выше $p_{wf}$: перебор прежний. **Предотвращает:** условие только по $p_0^{old}$.

**Тест:** `test_bhp_shutin_step_without_open_branch` — реальный Ньютон, сценарий rs300, шаг 168.75 с при $p_{wf} = p_{ext}$. **Ожидание:** ветки `[None, shut, shut, shut]`, $p_0$ = 174.434873 бар, двухфазных 250 (как до правки). **Предотвращает:** изменение итога реального шага останова.

**Неизменность поведения:**
- существующие тесты логики веток и ступеней — `test_prototype_well_branch.py`, `test_prototype_globalization.py`, `test_prototype_phase_switching.py` (в т. ч. `test_bhp_shutin_takes_shut_branch`), `test_failure_report`-тесты прототипа — зелёные без правок;
- регрессия прототипа 11/11 и 17/17 PASS побитово;
- отпечатки 21 примера и сквозного расчёта (шаг 3).

## 5. Критерии завершения

- [ ] Шаги 0–6 выполнены.
- [ ] `pytest tests/ -q` — 1351 passed (1344 + 7).
- [ ] Тесты прототипа 97 passed; полная регрессия 17/17 PASS, эталон не менялся.
- [ ] Отпечатки 21 примера и сквозного расчёта в режимах A и B совпадают с базой (шаг 3); на останове в режиме A нет попыток ветки «открыта».
- [ ] CHANGELOG прототипа дополнен (шаг 4).
- [ ] Vault обновлён: реестр, заметка об останове, план (шаг 6).
- [ ] Комментарий в issue #69 опубликован; issue закрывается при влитии.

## 6. Связанные

- Issue: [#69](https://github.com/ArturSalamatin/Oil_Gas/issues/69); тело и комментарии — `vault/issues/debt-040/`.
- Пробы и замеры: `vault/issues/debt-040/probes/`:
  - `stage_profile.py` — профиль ступеней, варианты, отпечатки;
  - `plan_tests_check.py` — числа тестов;
  - `plan_code.py` (аудит) — блоки кода берутся из текста плана: сверка «было» с `blackoil.py`, запись тестов шага 1, подмена `_fallback` блоком «стало» (`pytest -p plan_code`, каталог проб в `PYTHONPATH`);
  - `regression_hook/sitecustomize.py` (аудит) — та же подмена в процессах `run_regression.py` и журнал `regression_patch.out.txt`;
  - `*.out.txt` — выводы; `audit_regression_quick_*.out.txt` — быстрая регрессия на базе и на коде шага 2.
- [[bug-020 shutin-phase-switching-newton]] — ступень 4; разделы 1.1–1.6 (механизмы отказа и замеры), 2.7 (регистрация DEBT-040).
- [[останов из развитой газовой зоны — забойная ячейка без потока и дребезг ячейки выше по потоку]] — механизмы М1, М2.
- [[запасной путь с отрицательной насыщенностью и веткой скважины снимает порог шага на скачке p_wf вверх]] — BUG-014, ветки скважины.
- [[debt-030 rejected-step-report]] — отчёт отклонённого шага (поля ветки).
- [[известные баги и технический долг]]: BUG-014, BUG-016, BUG-019 ($c_t < 0$ выше 345 бар), BUG-020, BUG-021, DEBT-030, DEBT-015 (вариант 1 пересмотреть после переноса A-retry в `Simulator`), FEAT-029.
