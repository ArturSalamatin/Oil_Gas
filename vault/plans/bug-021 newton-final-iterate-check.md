---
tags: [plan, bug, prototype, newton]
date: 2026-10-06
issue: BUG-021
github: https://github.com/ArturSalamatin/Oil_Gas/issues/64
branch: fix/bug-021/newton-final-iterate-check
status: реализован
worktree: .worktrees/bug-021
audit:
  date: 2026-10-06
  round: 1
  found: 9
  auto-fixed: 9
  manual-required: 0
---

# BUG-021: Ньютон прототипа проверяет сходимость на каждом новом приближении

## Сводка

- **Ошибка.** `_newton_fixed_active_set` сверяет $\|F\|_\infty$ с допуском только в начале итерации, до обновления. После обновления на итерации `max_iter` (15) цикл кончается: невязка нового приближения считается, но с допуском не сравнивается. Ньютон, сошедшийся на последнем разрешённом обновлении, записывается отказом, шаг отвергается и дробится.
- **Исправление (вариант 2, решение пользователя).** Сходимость проверяется сразу после каждого принятого шага линейного поиска, по невязке `ft`, которую поиск уже вычислил. Нулевое число обновлений проверяется до цикла по `f_initial`. Это побитно та же невязка, что `finite_difference_jacobian` вернула бы в начале следующей итерации. Поэтому везде, где Ньютон сходился и раньше, приближения, число итераций и невязка прежние. Кроме того, исчезает сборка якобиана, которая шла только на проверку сходимости: по одной на каждый сошедшийся вызов.
- **Измерено при планировании** (код плана подменялся в памяти и в копии прототипа; база `5ce2168`):
  - **Регрессия прототипа:** 16/17 PASS. FAIL — только T05S_N200_DT5m: шаг 3.75 с теперь принимается. Эталон этого расчёта переснимается (решение пользователя).
  - **Примеры GPN:** 19 из 21 побитно. В 14 различие на уровне округления ($\max|\Delta p|$ = 1.5e-8 Па). 13b больше не дробит первый час вторых суток; $\max|\Delta p|$ = 392 Па на 1.5 сут, к 30 сут ~1 Па. Меняются 3 ячейки таблицы README 13b, 3 члена баланса энергии и абзац о дроблении.
  - **Первый шаг примера 05** при $p_{wf}$ = 4 МПа больше не дробится (было 2 подшага).
  - **Варианты 1 и 2** дают побитно одинаковые истории всех 21 примера.
  - **Тесты:** полный прогон тестов GPN на варианте 2 — 1267 passed без правок. Тест третьей ступени теряет покрытие последнего обновления (16 → 13 пар), шаг 3 его возвращает.
  - **Сборки якобиана:** их доля, которая исчезает, — 30–48 % в регрессии и 19–99 % в примерах.
  - **Время** (машина без другой нагрузки): 21 пример GPN — 128.4 → 98.4 с (−23 %); регрессия `--quick` — 174.7 → 129.4 с (−26 %).
- **Шагов:** 7 (подготовка, тест-воспроизводитель, правка, тесты GPN, регрессия прототипа и эталон, примеры GPN и README, итог и vault).
- **Код:** ~25 строк в `blackoil.py` (метод целиком + 3 строки docstring модуля), ~45 строк нового теста прототипа, ~10 строк в двух тестах GPN, комментарий в третьем; README 13b и 05, `CHANGELOG_1.0.3.md`, 5 файлов эталона T05S_N200_DT5m.
- **Оценка:** ~2.5 ч, из них ~35 мин — полная регрессия прототипа (~20 мин; T05 при планировании ≈ 14 мин) с повтором T05S_N200_DT5m (~3 мин) и полный прогон тестов GPN (~6–10 мин).

## Решения пользователя (2026-10-06)

1. **Вариант 2**: проверка после каждого обновления, без якобиана, нужного только для проверки сходимости. Вариант 1 (одна строка после цикла) отклонён: результат тот же, лишний якобиан остаётся.
2. **Эталон T05S_N200_DT5m переснять** — все 5 файлов `golden/T05/T05S_N200_DT5m/`, запись в `CHANGELOG_1.0.3.md`, как в DEBT-029.
3. **Порядок: сначала DEBT-030, потом BUG-021.** DEBT-030 влит, пока план писался (2026-10-06, `7f83ef8`; база плана — `3cdb43f`). Замеры §1.4 сделаны на `5ce2168`, до DEBT-030. Он меняет только отчёт отклонённого шага, поэтому истории, профили и регрессия от него не зависят.
4. **README:** фразу README 05 о дроблении первого шага переписать по замеру целиком (5 МПа — 2 подшага; 4 и 2 МПа — без дробления; 2 МПа устарело ещё до BUG-021). Таблицу `max_retries` README 03 (при 0.5 МПа сейчас 4, в README 9) зарегистрировать отдельной DEBT — в BUG-021 не входит.
5. **Порядок с BUG-020** (аудит раунд 1): BUG-021 вливается раньше BUG-020. Оба плана правят абзац README 13b о дроблении, комментарий `test_energy_matrix_examples.py:761-767`, конец docstring `blackoil.py` и CHANGELOG. После BUG-021 час 25 у 13b решает третья ступень, и ступень 4 BUG-020 туда не доходит. В план BUG-020 (раздел «Порядок с BUG-021») дописаны следствия для его шагов 3.1 и 6.

## Как начать работу по этому плану

1. Прочитай этот файл целиком; затем запись BUG-021 в [[известные баги и технический долг]] и раздел «Порядок влития» ниже.
2. **Проверь, что DEBT-030 влит** (решение 3; влит 2026-10-06, `7f83ef8`):
   ```powershell
   git log --oneline numerical_scheme/implementation | Select-String "debt-030"
   ```
   Нужен merge-коммит `7f83ef8 Merge branch 'refactor/debt-030/rejected-step-report' ...`. Если базовая ветка его не содержит — остановиться и спросить пользователя.
3. **Проверь, что BUG-020 НЕ влит** (решение 5; план `vault/plans/bug-020 shutin-phase-switching-newton.md`): `git log --oneline numerical_scheme/implementation | Select-String "bug-020"` → пусто. Если влит — остановиться и спросить пользователя: якорь шага 3.1 и тексты шага 6 (13b) тогда уже переписаны BUG-020 (раздел «Порядок влития»).
4. Ветка от базовой: `git checkout -b fix/bug-021/newton-final-iterate-check numerical_scheme/implementation` (или worktree, как делает `/implement`).
5. Переменные (PowerShell; в worktree `.venv` нет — интерпретатор основного каталога):
   ```powershell
   $PY = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   $P  = "D:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\bug-021\probes"   # пробы — только в основном каталоге (vault/issues в .gitignore)
   ```
6. Базовое состояние — шаг 1.
7. Воспроизведи баг — шаг 2: новый тест прототипа падает (3 failed, 1 passed).
8. После каждого шага — проверка шага и регресс по полю «Регресс». Полный прогон тестов GPN — в конце (шаг 7).

## Порядок влития

| Порядок | Что меняется в этом плане |
|---|---|
| **DEBT-030 → BUG-021** (решение 3; DEBT-030 влит, `7f83ef8`) | Как написано. Тестов прототипа на базе 93 (92 + `test_failure_report.py`), после шага 2 — 97. Тестов GPN 1270 (1267 + 3 DEBT-030). Docstring модуля кончается строками DEBT-030 (`blackoil.py:16-17`), строка BUG-021 — после них. `step_log.csv` эталона T05S_N200_DT5m после пересъёма содержит отклонённые строки уже по правилу DEBT-030 (поля Ньютона исходного алгоритма). |
| **BUG-021 → BUG-020** (решение 5) | Как написано. План BUG-020 после BUG-021 (его раздел «Порядок с BUG-021», дописан аудитом BUG-021): 13b не трогает — у 13b после BUG-021 нет ни одного общего отказа `advance`, ступень 4 не вызывается; строку docstring и раздел CHANGELOG ставит после строк BUG-021. |
| BUG-020 влит раньше (против решения 5) | Остановиться и спросить пользователя. Что разойдётся: якорь 3.1 (docstring кончается строкой BUG-020); «было» шагов 6.2 и 6.5 — тексты BUG-020, где снятие дробления 13b приписано ступени 4. Ступень 4 включена флагом только в фабрике GPN, поэтому 13b (час 25) и первый шаг 05 при 4 МПа она могла уже решать. Тогда разница «до/после» в шаге 6 меньше или нулевая, а приписывание в README и комментарии — по замеру (`readme_13b.py`, `audit_checks.py`, `run_13b.py`). Прототип и его регрессия ступени 4 не видят (флаг выключен), шаги 3–5 прежние. |

DEBT-030 и BUG-021 правят разные методы `blackoil.py` (`advance` и `_newton_fixed_active_set`); общие — только концы docstring модуля и `CHANGELOG_1.0.3.md`. Тесты DEBT-030 в GPN подменяют `_advance_phases` и Ньютон не исполняют. Тест прототипа DEBT-030 (`test_failure_report.py`, первый шаг T04, 60 с) исполняет настоящий Ньютон, но событий BUG-021 на T04 нет (счётная проба, таблица «Масштаб»). Отчёт отказа у варианта 2 побитно прежний (невязка последнего приближения — та же `residual(z)`), поэтому тест проходит без правок.

## Пробы планирования

Все — в `vault/issues/bug-021/probes/` (основной каталог). Запуск — из каталога `numerical_solver` проверяемого дерева: код берётся из текущего каталога (`Path.cwd()`).

| Проба | Что делает | Вывод |
|---|---|---|
| `planned_code.py` | тексты вариантов 1 и 2 (`NEW_V2` — блок «После» шага 3); `apply(v)` — подмена в памяти, `patch_text` — в исходнике | — |
| `make_copy.py [0\|1\|2]` | копия прототипа `applied_v<v>/` с вариантом (0 — без правки) и тестами `planned_tests/` | — |
| `planned_tests/test_newton_last_iteration.py` | тест шага 2 (копия текста плана) | — |
| `count_last_iter.py regression\|gpn\|script ... [--variant 2]` | счётчики: вызовы Ньютона, события BUG-021 (отказ на `max_iter` с невязкой ниже допуска), шаги `advance`, сборки якобиана | `count_regression_base.txt`, `count_gpn_base.txt`, `count_bug020_ladder*.txt` |
| `history_snapshot.py [--variant v] save <метка>`, `compare a b` | истории 21 примера (p, Sg, Rs, T, regime, t, G_o, G_g) и время, побитовое сравнение | `history_compare_base_v2.txt`, `history_compare_v1_v2.txt`, `time_history_*.txt` |
| `readme_13b.py a b` | числа таблицы README 13b в её формате из двух историй | `readme_13b.txt` |
| `run_13b.py base\|v2` | пример 13b целиком, вывод в `probes/out_13b_<метка>` (баланс энергии) | `run_13b_*.txt` |
| `hour1_13b.py` | $p$ у забоя 13b к концу первого часа после первого скачка вверх | `hour1_13b.txt` |
| `first_step.py` | первый шаг конфигураций с замером дробления в README (03, 04a, 05), текущий код и вариант 2 | `first_step.txt` |
| `planned_gpn_test_check.py` | тело изменённого `test_sg_step_limited_in_third_stage`: пары приближений с последним и без | `planned_gpn_test_check.txt` |
| `planned_plugin.py` | pytest-плагин: подмена варианта до сбора тестов (`$env:BUG021_VARIANT`) | `gpn_tests_full_v2.txt` |
| `compare_golden.py <выход> <golden> <кейс>` | расхождение выхода регрессии с эталоном: шаги, первая различающаяся строка `step_log.csv`, $\Delta p, \Delta S_g, \Delta R_s, \Delta q$ по моментам отчёта | `compare_golden_T05S_N200.txt` |
| `regression_v2_full.txt` | полная регрессия на копии с вариантом 2 | — |
| `apply_plan.py` (запуск из `numerical_solver`) | блоки «было/стало» шагов 2–6 применяются к копиям файлов `probes/applied_plan/`: каждый «было» — ровно один раз; метод = `NEW_V2`; тесты прототипа в копии | `apply_plan.txt` |
| `time_history_compare.txt`, `time_regression_quick.txt` | время без другой нагрузки: 21 пример и `--quick`, база и вариант 2 | — |
| `audit_checks.py` (аудит) | 14: ступень, принявшая шаги 1–3; 05: первый шаг при $p_{wf}$ = 8…2 МПа; текущий код и вариант 2 | `audit_checks.txt` |

## 1. Задача и воспроизведение

### 1.1. Симптом

Эталон регрессии T05S_N200_DT5m, `regression/golden/T05/T05S_N200_DT5m/step_log.csv`, строка 6: $\Delta t$ = 3.75 с, 15 итераций, $\|F\|_\infty$ = 4.169e-16, `accepted = False`. Шаг делится пополам и принимается при 1.875 с.

Ступени `advance` на этом шаге (`count_regression_base.txt`; допуск `atol + rtol·‖F₀‖∞` = 2.68e-11):

| ступень | итераций | $\|F\|_\infty$ после 15-го обновления | ниже допуска |
|---|---|---|---|
| исходный алгоритм | 15 | 4.170e-16 | да — событие BUG-021 |
| запасной путь, ветка «открыта» | 15 | 4.208e-16 | да — событие BUG-021 |
| третья ступень, ветка «открыта» | 15 | 5.16e-10 | **нет** — настоящий отказ |

⚠️ В issue #64 про третью ступень сказано «скорее всего, тоже ниже допуска» — это неверно: 5.16e-10 > 2.68e-11.

### 1.2. Причина (код)

`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`, `_newton_fixed_active_set` (`:292-315` на `5ce2168`; DEBT-030 добавляет 2 строки в docstring модуля — после него `:294-317`):

```python
for it in range(1,max_iter+1):
    J,f=self.finite_difference_jacobian(z,...); nrm=np.linalg.norm(f,np.inf)
    if nrm<=atol_sm3s+rtol*scale: return z,BlackOilNewtonReport(True,it-1,float(nrm))   # проверка ДО обновления
    ...                                                                                  # z=trial — обновление
f=self.residual(z,...); return z,BlackOilNewtonReport(False,max_iter,float(np.linalg.norm(f,np.inf)))   # невязка есть, сравнения нет
```

После $k$ обновлений проверка срабатывает только в начале итерации $k+1$. Значит, при `max_iter = 15` сходимость за 15 обновлений не распознаётся никогда: сошедшийся вызов делает не больше 14 обновлений.

### 1.3. Цепочка

1. `_newton_fixed_active_set` → `BlackOilNewtonReport(False, 15, ‖F‖∞ ≤ допуска)`.
2. `_advance_phases` (`:388`, вызов `:392`) при `not report.converged` (`:393`) возвращает отказ (номера — на `3cdb43f`).
3. `advance` переходит к запасному пути `_fallback`, затем к третьей ступени. Все вызывают тот же Ньютон с `max_newton = 15`.
4. Если ни одна ступень не приняла шаг:
   - прототип (`simulation.py:82-88`) записывает отклонённую строку и делит шаг;
   - решатель GPN (`prototype_adapter.py:104-111`) повторяет интервал с удвоенным числом подшагов.
5. Если шаг приняла другая ступень (пример 14, шаг 2) — результат той ступени: на уровне округления то же решение, другой путь.

### 1.4. Масштаб (замеры при планировании)

**События BUG-021 на текущем коде** (`count_last_iter.py`, база `5ce2168`):

| набор | событий | где |
|---|---|---|
| регрессия прототипа, 17 расчётов | 1 | T05S_N200_DT5m, `advance` №5, 3.75 с (исходный и запасной/«открыта»), шаг отклонён |
| примеры GPN, 21 | 2 | 13b — `advance` №25, 3600 с, третья ступень/«открыта», $\|F\|$ = 2.79e-10 при допуске 2.91e-9, шаг отклонён (адаптер дробит на 2 × 1800 с); 14 — `advance` №2, 86 400 с, исходный и запасной/«открыта», 2.0e-15 при 1.05e-11, шаг принят третьей ступенью |
| лестница останова BUG-020 (конфиг 20, 10 сут добычи + 0.1 сут останова) | 32 шага | 21 отклонённый, 11 принятых другой ступенью; всего отказов 127 — BUG-021 объясняет меньшую часть |

**Сборки якобиана**, которые вариант 2 убирает (= число сошедшихся вызовов Ньютона), в долях всех сборок:

| набор | доля |
|---|---|
| регрессия T00–T11, T05 | 0.30–0.48 |
| примеры GPN | 0.19–0.99: 01, 02 — 0.99, 03 — 0.76, 04 — 0.66, 13b — 0.25, 19–21 — 0.19–0.22 |

**Вариант 2 против текущего кода:**

| набор | результат |
|---|---|
| регрессия (копия с вариантом 2) | 16/17 PASS; FAIL T05S_N200_DT5m (`profiles.csv: row 202 col 4: 102.01582136024327 != golden 102.0031879315949`) |
| примеры GPN (`history_compare_base_v2.txt`) | 19 побитно; 14: $\max|\Delta p|$ 1.5e-8 Па, $|\Delta S_g|$ 8.9e-15, $|\Delta T|$ 1.5e-12 К; 13b: $\max|\Delta p|$ 392 Па, $|\Delta S_g|$ 1.6e-5, $|\Delta R_s|$ 1.2e-3, $|\Delta T|$ 5.9e-4 К |
| 13b, шаги | 724 вызова `advance` (723 принято, 1 отказ, дробление 2 × 1800 с) → 720 вызовов, все приняты |
| 14, вызовы Ньютона | 377 (отказов 5) → 374 (отказов 2); якобианов 1335 → 941 |
| первый шаг с замером в README (`first_step.txt`, `audit_checks.txt`) | 05 при 4 МПа: 2 → 1 подшаг; 05 при 8, 7, 6, 5, 3, 2 МПа, 03 (4, 2, 0.5 МПа), 04a ($N$ = 300, 500) — без изменений |
| 14, шаг 2 (`audit_checks.txt`) | сейчас принимает третья ступень (10 итераций), с вариантом 2 — исходный алгоритм (19 итераций); шаги 1 и 3 — прежние |
| тесты GPN, полный прогон (`gpn_tests_full_v2.txt`) | 1267 passed |
| тесты прототипа в копии (`make_copy.py 2`) | 92 passed + 4 новых passed; в копии без правки (`make_copy.py 0`) новые — 3 failed, 1 passed |
| варианты 1 и 2 (`history_compare_v1_v2.txt`) | побитно на всех 21 примере |
| лестница останова BUG-020, 0.1 сут | 130 принятых / 127 отказов → 118 / 115; BUG-020 не закрывается |
| 13b, $p$ у забоя через час после первого скачка вверх (`hour1_13b.txt`) | 10.7884 → 10.7842 МПа; фраза README «10.78–10.79 МПа» остаётся верной |
| время, без другой нагрузки (`time_history_compare.txt`, `time_regression_quick.txt`) | 21 пример GPN 128.4 → 98.4 с (−23 %; 13b 33.9 → 27.6, 14 12.8 → 9.8, 04a 18.7 → 15.0); регрессия `--quick` 174.7 → 129.4 с (−26 %; по кейсам −17…−38 %) |
| текст плана (`apply_plan.py`, `apply_plan.txt`) | все блоки «было» шагов 3–6 найдены ровно один раз в файлах базы `3cdb43f`; метод после правки = `NEW_V2`; тесты прототипа в копии — 97 passed (с тестом DEBT-030 `test_failure_report.py`) |

**T05S_N200_DT5m против эталона** (`compare_golden_T05S_N200.txt`). Шаги: принято/отклонено 8689/5 → 8675/4. Последовательность шагов расходится со строки 6 `step_log.csv`: 3.75 с принят за 19 итераций (4 + 15 в двух циклах набора фаз), рост шага по `_grow_dt` ×0.75 → 2.8125 с.

| сут | $\max|\Delta p|$, бар | $\max|\Delta S_g|$ | $\max|\Delta R_s|$ | $\Delta q_o$, % | $\Delta q_g$, % | ΔGOR, % |
|---|---|---|---|---|---|---|
| 1 мин | 0.232 | 5.8e-4 | 7.3e-2 | 0.64 | 0.72 | 0.08 |
| 1 | 1.35e-4 | 1.7e-5 | 4.4e-5 | −5e-5 | −0.011 | −0.011 |
| 2 | 2.1e-5 | 7.2e-6 | 6.7e-6 | 1e-4 | −5e-4 | −6e-4 |
| 30 | 2.6e-6 | 2.8e-7 | 8.1e-7 | 9e-6 | 1.5e-5 | 7e-6 |

Внешнего эталона IMEX для T05 нет — это исследование сходимости. Метрика `spatial_100_200` (`regression/evidence/T05_final_metrics_20260825a.json`, $p_{max}$ = 0.060 бар на 1 сут) по неравенству треугольника сдвигается не больше чем на 1.35e-4 бар — 0.2 %. Первая минута в приёмку не входит (DEBT-029: на ней шаг определяют отказы Ньютона, а не точность).

## 2. Целевое состояние

- `_newton_fixed_active_set` возвращает `converged=True`, как только $\|F\|_\infty$ нового приближения не выше допуска, — в том числе после обновления `max_iter`.
- Нулевое число обновлений: начальное приближение, уже удовлетворяющее допуску, возвращается сразу, без сборки якобиана. На этом стоит запасной путь: ветка «закрыта» на неизменном состоянии сходится за 0 итераций (DEBT-030).
- Везде, где Ньютон сходился раньше, — побитно те же `z`, `iterations`, `residual_inf`; отказы — те же `iterations` и `residual_inf`.
- Сошедшийся за $k$ обновлений вызов строит $k$ якобианов (было $k+1$).
- Регрессия прототипа 17/17 (после пересъёма T05S_N200_DT5m); тесты прототипа и GPN зелёные; README 13b, 05 соответствуют расчёту.

**Не меняется:** допуск (`atol_sm3s = 1e-11`, `rtol = 1e-8`, масштаб — $\|F(z_0)\|_\infty$), лимит `max_iter = 15`, линейный поиск (12 делений, `_trial_is_reasonable`, норма BUG-016), ограничитель $|\Delta S_g|$, `advance`/`_fallback`/`_advance_phases`, `_grow_dt`, адаптер GPN, физика и невязка. Критерий сходимости в `numerical_solver/doc/problem_statement.tex` (§`ssec:convergence`) описан для собственного решателя и этой правкой не затрагивается.

## 3. Варианты решения

| № | Суть | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| 1 | После цикла сравнить уже посчитанную невязку с допуском (одна строка в `:315`) | минимальная правка | лишний якобиан у каждого сошедшегося вызова остаётся | отклонён (решение 1) |
| **2** | Проверка после каждого обновления по `ft` линейного поиска; нулевое число обновлений — до цикла по `f_initial` | те же решения, что у 1 (побитно на 21 примере); минус одна сборка якобиана на сошедшийся вызов | перестановка цикла в коде авторов; тест третьей ступени теряет покрытие последнего обновления (шаг 4) | **принят** |
| 3 | Поднять `max_iter` до 16+ | одна константа | ошибку не исправляет — переносит на новую последнюю итерацию; меняет и настоящие отказы | отклонён |
| 4 | Не исправлять | эталон не трогается | лишние дробления (13b, 05, T05S_N200, останов) | отклонён |

**Почему результаты вариантов 1 и 2 совпадают побитно.** `residual` чиста: кеш запасов старого состояния DEBT-036 — по байтам $p, R_s, S_g$. `finite_difference_jacobian` (оба режима, `:244`, `:256` на `3cdb43f`) начинает с `f0=self.residual(z,...)`. Значит:
- `ft` принятого шага поиска — это побитно `f`, который якобиан вернул бы в начале следующей итерации;
- `f_initial` — это `f` первой итерации;
- `scale` и выражение допуска те же.

Отказы: на итерации `it` отчёт `nrm` — невязка того же `z`, что и раньше; после цикла — невязка последнего приближения, побитно та же `residual(z)`. Проба `history_compare_v1_v2.txt` это подтверждает.

## 4. Подводные камни

- ✅ **Побочные эффекты.** `_newton_fixed_active_set` вызывается только из `_advance_phases` (`:392`). В тестах его подменяют на экземпляре: `test_prototype_globalization.py:118-132`, `test_prototype_activation_cap.py:127-135` — сигнатура и возврат те же.
- ⚠️ **Тесты, перехватывающие `finite_difference_jacobian` как «итерации»:**
  - `test_prototype_globalization.py:119-133` (`test_sg_step_limited_in_third_stage`): на варианте 2 пар соседних приближений 13 вместо 16 — последнее обновление каждого сошедшегося вызова выпадает из проверки $|\Delta S_g| \le 0.2$. Тест проходит, но слабее. Шаг 4 добавляет возвращённое приближение (замер: снова 16 пар, max 0.200000).
  - `test_prototype_well_branch.py:234-247`: ищет отрицательную $S_g$ промежуточных приближений; проходит. Шаг 4 правит комментарий.
- ✅ **Граничные случаи:**
  - старт уже сошёлся — 0 итераций, 0 якобианов (тест шага 2);
  - отказ линейного поиска на итерации 15 — `nrm` прежний, выше допуска, не событие;
  - исключение линейного решения — прежний возврат;
  - `max_iter = 1` — одна сборка якобиана, проверка после обновления.
- ✅ **Производительность.** Аллокаций не прибавилось; убрана сборка якобиана (7 невязок при сгруппированном режиме) на каждый сошедшийся вызов и одна невязка после цикла у отказов.
- ⚠️ **Обратная совместимость.** Меняется поведение там, где было событие BUG-021: T05S_N200_DT5m (эталон переснимается, решение 2), 13b (README), 05 при 4 МПа (README), 14 — на уровне округления. Прочее побитно (замер).
- ✅ **Порядок вызовов / состояние при ошибке.** Метод без состояния; атрибуты ступеней (`_line_search_l2`, `_sg_step_max`, `_sg_lower_bound`, `_well_branch`) только читаются.
- ✅ **Численная устойчивость.** Допуск тот же; проверка по `ft` — та же норма $\infty$ (а не `merit`, которая у третьей ступени $L_2$).
- ⚠️ **Связь с другими задачами** — раздел «Порядок влития» (DEBT-030, BUG-020).
- ✅ **Import-цепочки** — без изменений.
- ✅ **Соответствие формулам** — критерий сходимости не меняется.
- ⚠️ **Прототип.** Правка в `HydroSolverPrototype/` — тесты прототипа и регрессия. Ожидание записано заранее: `--quick` 11/11 PASS побитно (шаг 3); полная 16/17, FAIL только T05S_N200_DT5m с числами §1.4 (шаг 5); после пересъёма 17/17.
- ⚠️ **Счёт итераций в отчёте.** Принятый шаг T05S_N200_DT5m на 3.75 с — 19 итераций (4 + 15): `_grow_dt` → ×0.75. Сошедшийся на 15-м обновлении вызов отчитывается `iterations = 15`, как и раньше «отказ».

## 5. Затронутые файлы

| Файл | Шаг | Изменение |
|---|---|---|
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_newton_last_iteration.py` | 2 | новый, 4 теста |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` | 3 | `_newton_fixed_active_set` целиком; строка в docstring модуля |
| `numerical_solver/tests/test_prototype_globalization.py` | 4 | `test_sg_step_limited_in_third_stage`: docstring, перехват Ньютона |
| `numerical_solver/tests/test_prototype_well_branch.py` | 4 | комментарий `:234-235` |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/regression/golden/T05/T05S_N200_DT5m/*` | 5 | 5 файлов переснять |
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` | 5 | раздел BUG-021 |
| `numerical_solver/examples/13b_pwf_alternating/README.md` | 6 | 2 строки таблицы, абзац о дроблении, таблица баланса |
| `numerical_solver/examples/05_standing_table_rp/README.md` | 6 | фраза о дроблении первого шага |
| `numerical_solver/tests/test_energy_matrix_examples.py` | 6 | комментарий `:761-767` |
| `vault/roadmap/известные баги и технический долг.md`, `vault/knowledge/decisions/hydro-prototype-анализ.md`, `vault/00-home/index.md` | 7 | статус, описание Ньютона, индекс |

## 6. Шаги

### Шаг 1: Подготовка и базовое состояние

**Цель:** ветка, числа тестов, зелёная регрессия `--quick`, истории примеров до правки.

**Файлы:** — (только прогоны); вывод — в `$P`.

**Контекст:** база зелёная по правилу мёржа. Истории до правки нужны для сверки в шаге 6. В worktree код берётся из текущего каталога: пробы вставляют `Path.cwd()` в `sys.path`.

**Что сделать:**
1. «Как начать», пункты 2–5.
2. Из `numerical_solver`: `& $PY -m pytest tests/ --collect-only -q` → записать (на `3cdb43f` — 1270; больше, если после него влит DEBT-039: +19 по его плану). Это число — ожидание шага 7; `& $PY -m pytest tests/ -m "not slow" -q` → все passed.
3. Из `numerical_solver/HydroSolverPrototype/Prototype_1.0.3`: `& $PY -m pytest tests -q` → 93 passed; `& $PY regression\run_regression.py --quick` → 11/11 PASS. Удалить `OUTPUT\REGRESSION_*`.
4. Из `numerical_solver`: `& $PY $P\history_snapshot.py save base_impl` (~2.5 мин). Это истории 21 примера в `$P\history_base_impl\`.

**Проверка после шага:** числа записаны; `--quick` 11/11 PASS.
**Регресс:** быстрый (п. 2).
**Зависимости:** блокирует всё.
**Оценка:** ~15 мин.

### Шаг 2: Тест-воспроизводитель в прототипе

**Цель:** тест, который падает на текущем коде и описывает целевое поведение.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_newton_last_iteration.py` (новый).

**Контекст:** регрессионный расчёт T05S_N200_DT5m идёт 3 мин и проверяет не сам Ньютон, а профили. Модульный тест берёт один вызов Ньютона на фиксированном наборе фаз и сравнивает лимиты `max_iter`:
- `max_iter = k`, где $k$ — число обновлений сошедшегося вызова. Должен сойтись с теми же `z`, `iterations` и `residual_inf`; на текущем коде — отказ с невязкой ниже допуска.
- `max_iter = k − 1` — лимит не ослаблен, остаётся отказом.

Сценарий: фикстура прототипа `Nabor_1b`, 8 ячеек, только нефть, BHP 100 бар против 200 бар, $\Delta t$ = 1 ч. Замер: $k$ = 2. Стиль тестов прототипа — `unittest`, английские комментарии, компактный код.

**Что сделать:** создать файл с текстом:

```python
import unittest, numpy as np
from tests.helpers import model_and_state

# BUG-021: _newton_fixed_active_set tested convergence only at the top of an
# iteration, before the update, so a solve that converged on update max_iter was
# reported as failed (T05S_N200_DT5m, dt = 3.75 s: 15 iterations, ||F||_inf =
# 4.2e-16, the step rejected and halved).  Every new iterate is tested now, on the
# residual the line search has already evaluated.  One Newton solve on a fixed
# phase set: 8 oil-only cells, BHP 100 bar against 200 bar, dt = 1 h.
DT=3600.0

def _solve(max_iter,z0=None):
    """(model, state, z0, z, report, Jacobian calls, tolerance) of one solve from the initial state."""
    _,m,s=model_and_state(n=8); mask=s.gas_active
    z0=m.pack(s,mask) if z0 is None else z0
    f0=m.residual(z0,s,DT,mask); tol=1e-11+1e-8*max(np.linalg.norm(f0,np.inf),1e-9)   # defaults of the method
    calls=[0]; jac=m.finite_difference_jacobian
    def counted(*a,**k): calls[0]+=1; return jac(*a,**k)
    m.finite_difference_jacobian=counted
    z,rep=m._newton_fixed_active_set(z0,s,DT,mask,max_iter=max_iter)
    return m,s,z0,z,rep,calls[0],tol

class NewtonLastIterationTests(unittest.TestCase):
    def test_converged_on_last_allowed_update(self):
        # With the default limit the solve converges in k updates.  With max_iter = k
        # it makes the same k updates, and the last iterate must be accepted: before
        # the fix it came back converged=False with ||F||_inf below the tolerance.
        *_,z_ref,ref,_,_=_solve(15); k=ref.iterations
        self.assertTrue(ref.converged); self.assertGreaterEqual(k,2)
        *_,z,rep,_,tol=_solve(k)
        self.assertTrue(rep.converged); self.assertEqual(rep.iterations,k)
        self.assertLessEqual(rep.residual_inf,tol); self.assertEqual(rep.residual_inf,ref.residual_inf)
        self.assertTrue(np.array_equal(z,z_ref))
    def test_one_update_short_still_fails(self):
        # The limit is not relaxed: with max_iter = k-1 the solve stops one update
        # short, above the tolerance, and reports a failure after k-1 iterations.
        *_,ref,_,_=_solve(15); k=ref.iterations
        *_,rep,_,tol=_solve(k-1)
        self.assertFalse(rep.converged); self.assertEqual(rep.iterations,k-1); self.assertGreater(rep.residual_inf,tol)
    def test_no_jacobian_built_only_to_detect_convergence(self):
        # The residual of the accepted line-search point is bitwise the f0 that a
        # Jacobian call at that point returns, so a solve converged in k updates
        # builds k Jacobians; before the fix it built one more, only to see ||F||.
        *_,ref,calls,_=_solve(15)
        self.assertTrue(ref.converged); self.assertEqual(calls,ref.iterations)
    def test_converged_start_returns_at_once(self):
        # A start that already meets the tolerance returns unchanged with 0 iterations
        # and no Jacobian.  advance() relies on it: in the BHP fallback the 'shut'
        # branch of an unchanged state converges in 0 iterations (DEBT-030 probe).
        *_,z_ref,ref,_,_=_solve(15)
        *_,z0,z,rep,calls,tol=_solve(15,z0=z_ref.copy())
        self.assertLessEqual(ref.residual_inf,tol)   # precondition: the converged point is a converged start
        self.assertTrue(rep.converged); self.assertEqual(rep.iterations,0); self.assertEqual(calls,0)
        self.assertTrue(np.array_equal(z,z0))

if __name__=='__main__': unittest.main()
```

Текст совпадает с `$P\planned_tests\test_newton_last_iteration.py`, проверенным на копиях прототипа.

**Проверка после шага** (из `Prototype_1.0.3`): `& $PY -m pytest tests/test_newton_last_iteration.py -q` → **3 failed, 1 passed**:
- `test_converged_on_last_allowed_update` — `rep.converged` False;
- `test_no_jacobian_built_only_to_detect_convergence` — `3 != 2`;
- `test_converged_start_returns_at_once` — якобианов 1, а не 0;
- `test_one_update_short_still_fails` проходит: лимит и сейчас не ослаблен.

**Регресс:** — (тесты GPN не менялись; тесты прототипа целиком — в шаге 3).
**Подводные камни:** если $k$ < 2 (предусловие первого теста) — сценарий изменился: подобрать $\Delta t$ так, чтобы $k \ge 2$, не ослаблять проверку.
**Зависимости:** требует шаг 1; блокирует шаг 3.
**Оценка:** ~45 строк, ~10 мин.

### Шаг 3: Проверка сходимости на каждом новом приближении

**Цель:** вариант 2 в `_newton_fixed_active_set`.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` — docstring модуля, метод `_newton_fixed_active_set` (после DEBT-030 `:294-317`; искать по `def _newton_fixed_active_set`).

**Контекст:** §1.2, §3. Комментарии BUG-016 сохраняются дословно. Стиль прототипа — компактный, `;` в строке допустим. Комментарии в прототипе — английские.

**Что сделать:**

**3.1. Docstring модуля** — последней строкой перед закрывающими `"""`. При влитом DEBT-030 docstring кончается его строкой.
- было:
```python
fields of the original algorithm, not those of the last fallback attempt.
"""
```
- стало:
```python
fields of the original algorithm, not those of the last fallback attempt.
BUG-021: _newton_fixed_active_set tests convergence on every new iterate, the
last one included, on the residual its line search has evaluated; no Jacobian
is built only to detect convergence.
"""
```
**3.2. Метод целиком.** Заменить текст от `    def _newton_fixed_active_set(` до строки перед `    def advance(`.
- было:
```python
    def _newton_fixed_active_set(self,z0,state_old,dt_s,gas_active,max_iter=15,rtol=1e-8,atol_sm3s=1e-11):
        z=np.asarray(z0,float).copy(); f_initial=self.residual(z,state_old,dt_s,gas_active); scale=max(np.linalg.norm(f_initial,np.inf),1e-9)
        # BUG-016: norm of the line search; the convergence test stays on ||F||_inf.
        # With defaults the comparison is norm(ft,inf)<nrm, bitwise as before.
        merit=(lambda v: np.linalg.norm(v)) if self._line_search_l2 else (lambda v: np.linalg.norm(v,np.inf))
        for it in range(1,max_iter+1):
            J,f=self.finite_difference_jacobian(z,state_old,dt_s,gas_active); nrm=np.linalg.norm(f,np.inf)
            if nrm<=atol_sm3s+rtol*scale: return z,BlackOilNewtonReport(True,it-1,float(nrm))
            try: dz=self._linear_solve(J,-f)
            except Exception: return z,BlackOilNewtonReport(False,it,float(nrm))
            if self._sg_step_max is not None:
                # BUG-016: scale the whole update (p and Sg together, the Newton
                # direction is kept) so that |dSg| of two-phase cells <= limit
                dsg=np.abs(dz[self.grid.n:][gas_active])
                if dsg.size and dsg.max()>self._sg_step_max: dz=dz*(self._sg_step_max/dsg.max())
            mf=merit(f); alpha=1.0; accepted=False
            for _ in range(12):
                trial=z+alpha*dz
                if self._trial_is_reasonable(trial,gas_active):
                    ft=self.residual(trial,state_old,dt_s,gas_active)
                    if merit(ft)<mf: z=trial; accepted=True; break
                alpha*=0.5
            if not accepted: return z,BlackOilNewtonReport(False,it,float(nrm))
        f=self.residual(z,state_old,dt_s,gas_active); return z,BlackOilNewtonReport(False,max_iter,float(np.linalg.norm(f,np.inf)))
```
- стало:
```python
    def _newton_fixed_active_set(self,z0,state_old,dt_s,gas_active,max_iter=15,rtol=1e-8,atol_sm3s=1e-11):
        z=np.asarray(z0,float).copy(); f=self.residual(z,state_old,dt_s,gas_active); nrm=np.linalg.norm(f,np.inf)
        scale=max(nrm,1e-9); tol=atol_sm3s+rtol*scale
        # BUG-016: norm of the line search; the convergence test stays on ||F||_inf.
        # With defaults the comparison is norm(ft,inf)<nrm, bitwise as before.
        merit=(lambda v: np.linalg.norm(v)) if self._line_search_l2 else (lambda v: np.linalg.norm(v,np.inf))
        # BUG-021: convergence is tested on every new iterate, the last one included.
        # It used to be tested at the top of the next iteration only, so a solve that
        # converged on update max_iter was reported as failed.  f is residual(z),
        # bitwise the f0 that the Jacobian call returns at the same z: wherever the
        # solve converged before, iterates and reports are unchanged, and the
        # Jacobian that was built only to detect convergence is no longer built.
        if nrm<=tol: return z,BlackOilNewtonReport(True,0,float(nrm))
        for it in range(1,max_iter+1):
            J,f=self.finite_difference_jacobian(z,state_old,dt_s,gas_active)
            try: dz=self._linear_solve(J,-f)
            except Exception: return z,BlackOilNewtonReport(False,it,float(nrm))
            if self._sg_step_max is not None:
                # BUG-016: scale the whole update (p and Sg together, the Newton
                # direction is kept) so that |dSg| of two-phase cells <= limit
                dsg=np.abs(dz[self.grid.n:][gas_active])
                if dsg.size and dsg.max()>self._sg_step_max: dz=dz*(self._sg_step_max/dsg.max())
            mf=merit(f); alpha=1.0; accepted=False
            for _ in range(12):
                trial=z+alpha*dz
                if self._trial_is_reasonable(trial,gas_active):
                    ft=self.residual(trial,state_old,dt_s,gas_active)
                    if merit(ft)<mf: z=trial; f=ft; accepted=True; break
                alpha*=0.5
            if not accepted: return z,BlackOilNewtonReport(False,it,float(nrm))
            nrm=np.linalg.norm(f,np.inf)
            if nrm<=tol: return z,BlackOilNewtonReport(True,it,float(nrm))
        return z,BlackOilNewtonReport(False,max_iter,float(nrm))
```

Блок «стало» совпадает с `NEW_V2` в `$P\planned_code.py` — тем, что прошёл все замеры §1.4.

Что изменилось по строкам:
- `f_initial` → `f`, `nrm` — до цикла;
- `tol` считается один раз — то же выражение `atol_sm3s+rtol*scale`, побитно;
- проверка нулевого числа обновлений — до цикла;
- в цикле якобиан больше не даёт `nrm`, `nrm` берётся у предыдущего приближения — та же невязка того же `z`;
- принятая точка поиска приносит свою невязку `f=ft`;
- проверка — после обновления;
- после цикла `nrm` последнего приближения, без повторного `residual`.

**Проверка после шага:**
- Из `Prototype_1.0.3`: `& $PY -m pytest tests/test_newton_last_iteration.py -q` → 4 passed; `& $PY -m pytest tests -q` → **97 passed**.
- `& $PY regression\run_regression.py --quick` → **11/11 PASS** (на копии с вариантом 2 — PASS побитно; событий BUG-021 в T00–T11 нет). Удалить `OUTPUT\REGRESSION_*`.
- Регресс прототипа: полная регрессия — в шаге 5.
- Регресс GPN: быстрый → все passed (полный прогон на варианте 2 при планировании — 1267 passed).

**Подводные камни:** §4 «Побочные эффекты», «Граничные случаи». Если `--quick` не 11/11 — правка не та, что в плане: сверить с `NEW_V2` (`$P\planned_code.py`), не переснимать эталон.
**Зависимости:** требует шаг 2; блокирует шаги 4–6.
**Оценка:** ~20 строк, ~10 мин (+ ~3 мин `--quick`).

### Шаг 4: Тесты GPN, перехватывающие якобиан как итерацию Ньютона

**Цель:** вернуть тесту третьей ступени проверку последнего обновления и поправить комментарий.

**Файлы:**
- `numerical_solver/tests/test_prototype_globalization.py` (`test_sg_step_limited_in_third_stage`, `:101-145`);
- `numerical_solver/tests/test_prototype_well_branch.py` (`:234-235`).

**Контекст:** оба теста собирают приближения Ньютона по вызовам `finite_difference_jacobian`. С правкой шага 3 в сошедшемся приближении якобиан не строится.
- Тест третьей ступени проверяет $|\Delta S_g| \le 0.2$ между соседними точками. Последнее обновление каждого сошедшегося вызова выпадает: 16 → 13 пар (`planned_gpn_test_check.txt`).
- Возвращённое вызовом приближение возвращает покрытие: снова 16 пар, max 0.200000.
- Отказ линейного поиска возвращает последнюю точку якобиана — пара с нулевым шагом, безвредно.

**Что сделать:**

**4.1.** `test_prototype_globalization.py`, docstring `test_sg_step_limited_in_third_stage`:
- было:
```python
        прямо на модели прототипа: исходный путь и запасной отказывают, решает
        третья ступень. Точки, где считается якобиан, — итерации Ньютона; они
        собираются по вызовам _newton_fixed_active_set (набор фаз внутри вызова
        фиксирован) и только при включённом ограничителе, то есть в третьей ступени.
        """
```
- стало:
```python
        прямо на модели прототипа: исходный путь и запасной отказывают, решает
        третья ступень. Приближения Ньютона — точки, где считается якобиан, и
        приближение, которое возвращает вызов (BUG-021: в сошедшемся приближении
        якобиан не строится). Они собираются по вызовам _newton_fixed_active_set
        (набор фаз внутри вызова фиксирован) и только при включённом ограничителе,
        то есть в третьей ступени. Замер плана BUG-021: 16 пар соседних
        приближений, без возвращённого — 13.
        """
```

**4.2.** Там же, перехват Ньютона:
- было:
```python
        def newton(z0, state_old, dt_s, gas_active, **kw):
            calls.append([])
            return orig_newton(z0, state_old, dt_s, gas_active, **kw)
```
- стало:
```python
        def newton(z0, state_old, dt_s, gas_active, **kw):
            calls.append([])
            z, rep = orig_newton(z0, state_old, dt_s, gas_active, **kw)
            # Возвращённое приближение: якобиан в нём не строится (BUG-021), без
            # него последнее обновление каждого вызова выпало бы из проверки
            if model._sg_step_max is not None:
                calls[-1].append((z.copy(), gas_active.copy()))
            return z, rep
```

**4.3.** `test_prototype_well_branch.py`, `test_negative_iterates_not_accepted`:
- было:
```python
        # Итерации перехватываются на экземпляре: finite_difference_jacobian
        # вызывается на каждой итерации Ньютона с текущей точкой z.
```
- стало:
```python
        # Итерации перехватываются на экземпляре: finite_difference_jacobian
        # вызывается в начале каждой итерации Ньютона с текущей точкой z.
        # Возвращённое приближение сюда не попадает (BUG-021: якобиан в нём не
        # строится) — тесту нужны промежуточные, уходящие за границу −0.05.
```

**Проверка после шага** (из `numerical_solver`): `& $PY -m pytest tests/test_prototype_globalization.py tests/test_prototype_well_branch.py tests/test_prototype_activation_cap.py -q` → все passed (на варианте 2 до правки шага 4 — 40 passed; с DEBT-030 — 43).
**Регресс:** быстрый.
**Подводные камни:** перехват на экземпляре ставится до `advance`; `gas_active` в перехвате Ньютона — аргумент вызова (маска фиксирована внутри вызова).
**Зависимости:** требует шаг 3.
**Оценка:** ~12 строк, ~10 мин.

### Шаг 5: Полная регрессия прототипа, пересъём T05S_N200_DT5m, CHANGELOG

**Цель:** 17/17 PASS с переснятым эталоном одного расчёта; запись в `CHANGELOG_1.0.3.md`.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/regression/golden/T05/T05S_N200_DT5m/{profiles.csv,rates.csv,material_balance.csv,run_summary.json,step_log.csv}`;
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`;
- вывод разбора — `$P\compare_golden_T05S_N200_impl.txt`.

**Контекст:** §1.4. Эталон T05S_N200_DT5m — выход сборки авторов, на нём отказ BUG-021 записан как норма. Решение 2 — переснять все 5 файлов, как шесть расчётов DEBT-029. Сравнение регрессии почти побитовое (abs 2e-7 / rel 2e-10): любая смена шагов — FAIL.

**Что сделать:**
1. Закоммитить шаги 2–4. Зафиксировать HEAD (каждый кейс регрессии — отдельный процесс, код импортируется заново).
2. Из `Prototype_1.0.3`: `& $PY regression\run_regression.py` (~20 мин: `--quick` ~3 мин + T05 ~14 мин при планировании) → **16/17 PASS**. FAIL — только `T05S_N200_DT5m`, сообщение: `profiles.csv: row 202 col 4: 102.01582136024327 != golden 102.0031879315949`.
3. Разбор: `& $PY $P\compare_golden.py OUTPUT\REGRESSION_<время> regression\golden T05S_N200_DT5m > $P\compare_golden_T05S_N200_impl.txt`. Ожидание — числа §1.4:
   - шаги 8689/5 → 8675/4;
   - последовательность расходится со строки 6: 3.75 с принят, 19 итераций;
   - $\max|\Delta p|$ = 0.232 бар на 1 мин, 1.35e-4 бар на 1 сут, 2.6e-6 бар на 30 сут.

   Отклонённые строки `step_log.csv` при влитом DEBT-030 несут поля Ньютона исходного алгоритма; целые колонки 60–7.5 с совпадут с эталоном авторов (`15,2,42` … `15,2,26`). Если числа другие или FAIL у других расчётов — остановиться и разобрать, эталон не переснимать.
4. Переснять: скопировать 5 файлов из `OUTPUT\REGRESSION_<время>\T05\T05S_N200_DT5m\` в `regression\golden\T05\T05S_N200_DT5m\` (решение 2). Другие файлы `golden/` не трогать.
5. `& $PY regression\run_regression.py --case T05S_N200_DT5m` (~3 мин) → PASS. Удалить `OUTPUT\REGRESSION_*`.
6. `CHANGELOG_1.0.3.md` — раздел в конец файла, после раздела DEBT-030 (`## Local changes — GPN project (DEBT-030): report of a rejected step`):

```markdown
## Local changes — GPN project (BUG-021): Newton convergence tested on every new iterate
- Problem: `_newton_fixed_active_set()` tested ||F||_inf against the tolerance only at the top of an iteration, before the update. After the update of iteration `max_iter` (15) the loop ended; the residual of the new iterate was computed but not compared, so a solve that converged on its last allowed update was reported as failed and the step was rejected and halved (T05S_N200_DT5m: dt = 3.75 s, 15 iterations, ||F||_inf = 4.2e-16).
- Convergence is now tested right after each accepted line-search point, on the residual the line search has already evaluated, the last update included; a start that already meets the tolerance returns before the loop with 0 iterations. That residual is bitwise the `f0` the Jacobian call returns at the same point, so wherever the solve converged before, iterates, iteration counts and residuals are bitwise unchanged, and the Jacobian that was built only to detect convergence is no longer built (one per converged solve: 30-48 % of the Jacobians of the regression jobs).
- Regression: 16 of 17 jobs reproduce the golden outputs bitwise. T05S_N200_DT5m now accepts its 3.75 s step (19 iterations) instead of rejecting it: accepted/rejected steps 8689/5 -> 8675/4; against the former golden, max |dp| is 0.23 bar at 1 min, 1.4e-4 bar at 1 day and 2.6e-6 bar at 30 days. There is no IMEX reference for T05; the spatial convergence metric `spatial_100_200` (p_max 0.060 bar) moves by at most 0.2 %. All five golden files of T05S_N200_DT5m are refrozen from the run on the fixed code, so the statements in `README.md`, `docs/TESTING.md` and `regression/README.md` that `golden/` is the output of the externally validated build now hold for 10 of the 17 jobs (11 after DEBT-029).
- Effect on the GPN examples: 19 of 21 bitwise; 14 differs at round-off (its second step is accepted by the original algorithm, no longer by the third stage); 13b no longer splits the first hour of day 2 into 2 x 1800 s (max |dp| 392 Pa at 1.5 days, about 1 Pa at 30 days). Run time without other load: the 21 GPN examples 128.4 -> 98.4 s, the quick regression 174.7 -> 129.4 s.
- Tests: `tests/test_newton_last_iteration.py` (4 new: convergence on the last allowed update, the limit not relaxed, no Jacobian only for the convergence test, a converged start). Physics, residual equations, tolerances and active-set logic are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/64; plan: `vault/plans/bug-021 newton-final-iterate-check.md` of the GPN project.
```

Время в разделе — замер при планировании; заменить, если замер шага 6 п. 5 отличается больше чем на 10 % (раздел дописывается до шага 6 — вернуться к нему после).

**Проверка после шага:** `--case T05S_N200_DT5m` PASS; `git status` — в `golden/` изменены ровно 5 файлов T05S_N200_DT5m.
**Регресс:** документ-уровень (`--collect-only -q`) — тесты GPN не менялись.
**Регресс прототипа:** полная регрессия (п. 2) и повтор одного расчёта (п. 5).
**Подводные камни:** не переснимать при FAIL других расчётов — это означает, что правка не та (§4 «Прототип»). `run_summary.json` эталона содержит пути и время машины авторов; в новом будут свои — `compare_summary` их не сверяет (как в DEBT-029).
**Зависимости:** требует шаги 3–4; блокирует шаг 7.
**Оценка:** ~40 мин (регрессия ~20 мин + повтор ~3 мин).

### Шаг 6: Примеры GPN — истории, README 13b и 05, комментарий теста

**Цель:** подтвердить замер §1.4 на коде ветки и привести README в соответствие.

**Файлы:**
- `numerical_solver/examples/13b_pwf_alternating/README.md`;
- `numerical_solver/examples/05_standing_table_rp/README.md`;
- `numerical_solver/tests/test_energy_matrix_examples.py` (`:761-767`).

**Контекст:** §1.4. В 13b шаг первого часа вторых суток (третья ступень, ветка «открыта») сходился на 15-й итерации и дробился на 2 × 1800 с; теперь он принимается целиком, и 13b не дробится вовсе. Первый шаг 05 при 4 МПа — то же. Фраза README 05 о 2 МПа устарела ещё до BUG-021 (решение 4).

**Что сделать:**
1. Из `numerical_solver`: `& $PY $P\history_snapshot.py save new_impl`, затем `& $PY $P\history_snapshot.py compare base_impl new_impl > $P\history_compare_impl.txt`. Ожидание: 19 побитно; 14 и 13b различаются с величинами §1.4.
2. `& $PY $P\readme_13b.py base_impl new_impl > $P\readme_13b_impl.txt`. Ожидание:
   - 1.5 сут: $q_o$ 1.6985 → 1.6984e-3, GOR 41.30 → 41.28;
   - 2 сут: GOR 42.97 → 42.98;
   - прочее без изменений, «недонас.» тоже.
3. `& $PY $P\run_13b.py impl > $P\run_13b_impl.txt` — баланс энергии. Ожидание (вариант 2 при планировании, `run_13b_v2.txt`):
   - конвекция −2.6235e+09 (было −2.6230e+09);
   - Джоуль–Томсон +3.2059e+10 (было +3.2060e+10);
   - скрытая теплота −3.0036e+10 (было −3.0037e+10);
   - невязка 3.51e-11 (было 3.95e-11);
   - остальные члены прежние.

   Тег `impl` в `run_13b.py` — без подмены: считает код ветки.
4. Фраза README 13b «к концу первого часа давление у забоя уже 10.78–10.79 МПа» проверена при планировании (`hour1_13b.txt`: 10.7884 → 10.7842 МПа) и не меняется. Повторять не нужно: на коде ветки обе половины пробы считают исправленный код.
5. Время: строка «итого» `history_compare_impl.txt` (п. 1). Сравнивать только если пп. 1 и «до» шли без другой нагрузки на машине; при планировании — 128.4 → 98.4 с. Если замер отличается от этого больше чем на 10 %, в CHANGELOG (шаг 5) и реестр ставить свой, с пометкой о нагрузке.
6. README 13b — правки ниже (числа — из пп. 2–4; если они отличаются от ожиданий, ставить свои и разобраться, почему).
7. README 05 — правка ниже. Проверить `& $PY $P\audit_checks.py` (вывод `05, p_wf = …`: 5 МПа — 2 подшага, 8, 7, 6, 4, 3, 2 МПа — 1). На коде ветки обе половины пробы считают исправленный код, поэтому сверять правую часть «→».
8. `test_energy_matrix_examples.py:761-767` — комментарий ниже.

**6.1. README 13b, таблица «Ожидаемое поведение»:**
- было: `| 1.5 | 10.75 | $1.6985\cdot10^{-3}$ | 41.30 | 350.046 | 0.0164 | 10.8014 | 46 | 0 |`
- стало: `| 1.5 | 10.75 | $1.6984\cdot10^{-3}$ | 41.28 | 350.046 | 0.0164 | 10.8014 | 46 | 0 |`
- было: `| 2 | 10.75 | $1.7463\cdot10^{-3}$ | 42.97 | 350.046 | 0.0175 | 10.8030 | 45 | 0 |`
- стало: `| 2 | 10.75 | $1.7463\cdot10^{-3}$ | 42.98 | 350.046 | 0.0175 | 10.8030 | 45 | 0 |`

**6.2. README 13b, абзац о дроблении:**
- было:
```markdown
Гидравлический шаг дробится один раз: первый час вторых суток — на 2
подшага по 1800 с (первый скачок вверх). Первый час расчёта (начальный
отбор при 6 МПа) сходится целиком — третья ступень `advance` (BUG-016); до
неё он дробился на 128 подшагов по 28.1 с. Остальные 719 подшагов — по
3600 с. Баланс энергии замыкается с относительной невязкой
$3.9\cdot10^{-11}$. Члены баланса за 30 сут, Дж:
```
- стало:
```markdown
Гидравлический шаг не дробится: 720 подшагов по 3600 с. Первый час
расчёта (начальный отбор при 6 МПа) сходится целиком — третья ступень
`advance` (BUG-016); до неё он дробился на 128 подшагов по 28.1 с. Первый
час вторых суток (первый скачок вверх) до BUG-021 дробился на 2 подшага по
1800 с: Ньютон третьей ступени сходился на последней, 15-й итерации, а
записывался отказом. Баланс энергии замыкается с относительной невязкой
$3.5\cdot10^{-11}$. Члены баланса за 30 сут, Дж:
```

**6.3. README 13b, таблица баланса:**
- было: `| $-3.0636\cdot10^{10}$ | $-3.0045\cdot10^{10}$ | $-2.6230\cdot10^{9}$ | $+3.2060\cdot10^{10}$ | $-3.0037\cdot10^{10}$ | $+9.17\cdot10^{6}$ |`
- стало: `| $-3.0636\cdot10^{10}$ | $-3.0045\cdot10^{10}$ | $-2.6235\cdot10^{9}$ | $+3.2059\cdot10^{10}$ | $-3.0036\cdot10^{10}$ | $+9.17\cdot10^{6}$ |`

**6.4. README 05, «Что требует осторожности — $p_{wf}$»:**
- было:
```markdown
**Снизу:** до 6 МПа расчёт идёт без дробления шага; при 5, 4 и 2 МПа
первый шаг дробится на 2 подшага (замер 2026-10-02). При отказе
```
- стало:
```markdown
**Снизу:** до 6 МПа расчёт идёт без дробления шага; ниже первый шаг
дробится на 2 подшага только при 5 МПа, при 4, 3 и 2 МПа сходится
целиком (замер 2026-10-06, $p_{wf}$ = 8…2 МПа через 1 МПа). При 4 МПа до
BUG-021 было 2 подшага: Ньютон сходился на последней, 15-й итерации, а
записывался отказом. При отказе
```
Замер аудита (`audit_checks.txt`, текущий код → вариант 2): 8, 7, 6 МПа — 1 → 1 подшаг; 5 — 2 → 2; 4 — 2 → 1; 3 — 1 → 1; 2 — 1 → 1.

**6.5. `test_energy_matrix_examples.py`:**
- было:
```python
# 13b_pwf_alternating дробится — 2 × 1800 с на первом скачке p_wf вверх
# (128 × 28.125 с в первом часу сняты BUG-016), — но в список не входит
# (решение пользователя 2026-09-30): инвариант «сумма dt = интервал» не
# зависит от причины дробления, а прогон стоит ~60 с.
# 16_well_shut_in дробится — 2 × 1800 с на третьем часу останова, — но в
# список не входит по той же причине, что 13b. На остальных конфигах
# дробления нет и проверять нечего.
```
- стало:
```python
# 13b_pwf_alternating не дробится: 2 × 1800 с на первом скачке p_wf вверх
# сняты BUG-021 (Ньютон сходился на 15-й итерации, а записывался отказом),
# 128 × 28.125 с в первом часу — BUG-016.
# 16_well_shut_in дробится — 2 × 1800 с на третьем часу останова, — но в
# список не входит (решение пользователя 2026-09-30, принятое для 13b):
# инвариант «сумма dt = интервал» не зависит от причины дробления. На
# остальных конфигах дробления нет и проверять нечего.
```

**Проверка после шага:**
- `& $PY -m pytest tests/test_examples.py -k "13b or Alternating" -q` → passed (тесты 13b — неравенства; на варианте 2 при планировании полный прогон 1267 passed).
- Регресс: быстрый.
- Рисунки 13b (`examples/13b_pwf_alternating/output/`, в `.gitignore`) — пересоздать в **основном каталоге после влития**: `& $PY examples\13b_pwf_alternating\main.py`. В worktree `main.py` возьмёт пакет основного каталога (память проекта «Worktree и PYTHONPATH»), и рисунки будут от старого кода.

**Подводные камни:** BUG-020 к этому шагу не влит (решение 5, «Как начать» п. 3). Тот же абзац README 13b и тот же комментарий теста правит и план BUG-020; после BUG-021 он их не трогает (его раздел «Порядок с BUG-021»).
**Зависимости:** требует шаг 3 (числа) и шаг 1 (истории до правки).
**Оценка:** ~20 строк текста, ~25 мин (пробы ~6 мин).

### Шаг 7: Итог — полный прогон, vault, issue

**Цель:** зелёный полный прогон, записи в vault, комментарий в issue.

**Файлы:**
- `vault/roadmap/известные баги и технический долг.md` (BUG-021);
- `vault/knowledge/decisions/hydro-prototype-анализ.md` (`:91`);
- `vault/00-home/index.md`;
- `vault/issues/bug-021/05-comment-done.md`.

**Что сделать:**
1. Из `numerical_solver`: `& $PY -m pytest tests/ -q` (~6–10 мин) → все passed, число — как в шаге 1 (1270 на `3cdb43f`). Из `Prototype_1.0.3`: `& $PY -m pytest tests -q` → 97 passed.
2. BUG-021 в реестре:
   - поле «Результат»: коммиты, числа тестов, регрессия 16/17 → пересъём → 17/17, примеры 19 побитно, время;
   - поле «Масштаб» — по §1.4 (в том числе лестница BUG-020: 130/127 → 118/115);
   - статус ✅.
3. `hydro-prototype-анализ.md:91` — к описанию `_newton_fixed_active_set` добавить: «Сходимость по $\|F\|_\infty$ проверяется на каждом новом приближении — по невязке, которую уже посчитал линейный поиск, включая последнее (BUG-021; до него — только в начале следующей итерации, и сошедшийся на 15-м обновлении вызов записывался отказом)».
4. `index.md` — статус плана.
5. Комментарий в issue #64 (`/implement`).
6. Удалить из `$P` каталоги историй (`history_*`), копии прототипа (`applied_v*`, `applied_plan`), вывод примера (`out_13b_*`); они в `.gitignore` и пересоздаются пробами.

**Регресс:** полный (п. 1) — конец реализации.
**Зависимости:** требует шаги 1–6.
**Оценка:** ~20 мин + полный прогон.

## 7. Тестовая стратегия

**Тест:** `test_converged_on_last_allowed_update`
**Файл:** `Prototype_1.0.3/tests/test_newton_last_iteration.py` (новый)
**Сценарий:** вызов Ньютона, сходящийся за $k$ обновлений, повторён с `max_iter = k`.
**Setup:** `model_and_state(n=8)`, только нефть, BHP 100 / $p_0$ 200 бар, $\Delta t$ = 3600 с; $k$ = 2.
**Ожидание:** `converged`, `iterations = k`, `residual_inf` ≤ допуска и равна эталонной, `z` побитно.
**Предотвращает:** возврат проверки «только в начале итерации».

**Тест:** `test_one_update_short_still_fails`
**Файл:** там же
**Сценарий:** `max_iter = k − 1`.
**Ожидание:** отказ, `iterations = k − 1`, невязка выше допуска.
**Предотвращает:** ослабление лимита или допуска при исправлении.

**Тест:** `test_no_jacobian_built_only_to_detect_convergence`
**Файл:** там же
**Сценарий:** число вызовов `finite_difference_jacobian` у сошедшегося вызова.
**Ожидание:** ровно `iterations`.
**Предотвращает:** возврат лишней сборки якобиана (вариант 1).

**Тест:** `test_converged_start_returns_at_once`
**Файл:** там же
**Сценарий:** старт из сошедшегося приближения.
**Ожидание:** `converged`, 0 итераций, 0 якобианов, `z` = `z0`.
**Предотвращает:** потерю проверки до цикла — на неё опирается ветка «закрыта» запасного пути (сходится за 0 итераций на неизменном состоянии).

**Тест:** `test_sg_step_limited_in_third_stage` (изменён)
**Файл:** `numerical_solver/tests/test_prototype_globalization.py`
**Сценарий:** как был; пары приближений включают возвращённое.
**Ожидание:** $\max|\Delta S_g| \le 0.2$; пар 16 (замер).
**Предотвращает:** непроверенное последнее обновление третьей ступени.

**Регрессия прототипа** — 17/17 после пересъёма T05S_N200_DT5m; **истории примеров GPN** — 19 побитно, 13b и 14 с величинами §1.4.

## 8. Критерии завершения

- [ ] Тест-воспроизводитель (4 теста) — на текущем коде 3 failed, после правки 4 passed.
- [ ] Тесты прототипа: 97 passed.
- [ ] Тесты GPN: полный прогон — все passed, число как в шаге 1 (1270 на `3cdb43f`).
- [ ] Регрессия прототипа: `--quick` 11/11 после шага 3; полная 16/17 с разобранным FAIL T05S_N200_DT5m (`compare_golden_T05S_N200_impl.txt` = §1.4); эталон T05S_N200_DT5m переснят (5 файлов), `--case T05S_N200_DT5m` PASS; запись в `CHANGELOG_1.0.3.md`.
- [ ] Примеры GPN: 19 побитно; 13b, 14 — как в §1.4; README 13b (2 строки таблицы, абзац, баланс) и 05 обновлены; комментарий `test_energy_matrix_examples.py` обновлён.
- [ ] Время замерено и записано (CHANGELOG, реестр).
- [ ] Vault: реестр, `hydro-prototype-анализ.md`, индекс; issue #64 прокомментирован.

## 9. Новые проблемы

| ID | Суть | Блокирует | Действие |
|---|---|---|---|
| DEBT-041 | README 03, таблица минимального `max_retries` при $N$ = 150: при $p_{wf}$ = 0.5 МПа первый шаг на `5ce2168` — 16 подшагов (`max_retries` 4), в README 9 (замер 2026-10-01). Остальные точки (8…2 МПа) не перемерялись; 4 и 2 МПа совпадают (`first_step.txt`). Причина расхождения не искалась | нет | зарегистрирован (решение 4) |
| — | Issue #64: третья ступень на шаге 3.75 с T05S_N200_DT5m (5.16e-10) не ниже допуска (2.68e-11), а в issue — «скорее всего, тоже» | нет | исправлено комментарием «План готов» |

## Связанные заметки

- [[известные баги и технический долг]] — BUG-021, DEBT-030, BUG-020, BUG-016, DEBT-029, DEBT-033, DEBT-036, DEBT-040, DEBT-041
- [[debt-030 rejected-step-report]] — отчёт отклонённого шага (влить раньше)
- [[bug-020 shutin-phase-switching-newton]] — ступень 4 (флаг), порядок влития
- [[hydro-prototype-анализ]] — описание Ньютона прототипа
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` — разделы BUG-014, BUG-016, DEBT-029 (пересъём эталона)
