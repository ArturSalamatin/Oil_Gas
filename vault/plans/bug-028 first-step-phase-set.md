---
tags:
  - план
  - исправление
date: 2026-10-14
issue: BUG-028
github: 117
branch: fix/bug-028/first-step-phase-set
status: в процессе
worktree: .worktrees/bug-028
audit:
  date: 2026-10-14
  round: 1
  base: 6adea25
  found: 11
  auto-fixed: 11
  manual-required: 0
---

# План BUG-028: первый шаг добычи из равновесия — цикл набора фаз упирается в 12 проходов

**Задача:** запись BUG-028 в [[известные баги и технический долг]] · issue [#117](https://github.com/ArturSalamatin/Oil_Gas/issues/117) · ветка `fix/bug-028/first-step-phase-set` · база `6d27358` (код = `209326d`)

## Как начать работу по этому плану

1. Прочитай этот файл целиком. Тело issue — `vault/issues/bug-028/01-issue-body.md`. Пробы и их выходы — `vault/issues/bug-028/probes/`.
2. Связанные заметки:
   - [[нарастающий шаг после смены управления — от 0.11 с, удвоение вчетверо уменьшает ошибку температуры у забоя за первый час]] — FEAT-032, исключение первого интервала;
   - [[на коротком шаге невязка Ньютона стоит на пределе округления запасов — допуск не ниже 4ε·M_max на Δt]] — BUG-025;
   - [[запасной путь с отрицательной насыщенностью и веткой скважины снимает порог шага на скачке p_wf вверх]] — ступени 2–3 и цикл набора фаз, BUG-014;
   - [[останов из развитой газовой зоны — забойная ячейка без потока и дребезг ячейки выше по потоку]] — ступень 4, BUG-020;
   - [[Ben Gharbia Jaffré 2014 — полугладкий Ньютон для появления и исчезновения газовой фазы]] — переключение фаз внутри Ньютона, вариант В6;
   - план DEBT-054 `vault/plans/debt-054 newton-failure-diagnostics.md` — текст отказа.
3. Worktree (правило `/implement`): `git worktree add .worktrees/bug-028 -b fix/bug-028/first-step-phase-set numerical_scheme/implementation`. Базовая ветка — `numerical_scheme/implementation`, не `master`.
4. Python — venv основного каталога, в worktree его нет: `$PY = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"`. Во всех командах плана `.venv\Scripts\python` и `..\..\.venv\Scripts\python` читать как `& $PY`.
   - Скрипты вне pytest в worktree берут пакет основного каталога: перед пробами задать `$env:PYTHONPATH = "<worktree>\numerical_solver;<worktree>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"` и проверить первую строку вывода проб («код: …» — путь worktree).
   - pytest берёт код из своего дерева сам.
   - Пробы `vault/issues/bug-028/probes/` попадают в worktree с коммитом материалов задачи (`/implement`, шаг 0).
5. Baseline из `<worktree>\numerical_solver`:
   - `.venv\Scripts\python -m pytest tests/ --collect-only -q` → **1932** теста;
   - `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` → **1656 passed, 276 deselected**.

   Из `<worktree>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3`:
   - `..\..\.venv\Scripts\python -m pytest tests -q` → **101 passed**;
   - `..\..\.venv\Scripts\python regression\run_regression.py --quick` → **11/11 PASS**. Выходы `OUTPUT\REGRESSION_*` удалить после проверки.
6. Воспроизвести баг (из `<worktree>\numerical_solver`, ~1 с): `.venv\Scripts\python ..\vault\issues\bug-028\probes\first_step_probe.py single 19_rs150_cooling 1` → «ОТКАЗ … выход: набор фаз не установился; числа — Ньютона ступени 1».
7. Шаги 1–5 по порядку. После каждого — проверка из поля «Проверка». Полный прогон — в конце (шаг 4).
8. Если база ушла вперёд (параллельно готовы планы DEBT-068 — +6 тестов, DEBT-062 — +8 тестов), baseline — по факту. Правка плана касается только `_advance_phases` и текстов §3 шага 3: сверить их строки с базой перед правкой.

## 1. Суть

Первый шаг добычи из равновесия не сходится, если он короче порога: в примере 19 ($R_{s,0}$ = 150, $p_0$ = 24.7 МПа, $p_{wf}$ = 3 МПа) — при $\Delta t \le 120$ с, в примере 21 ($R_{s,0}$ = 100, $p_0$ = 17.7 МПа) — при $\Delta t \le 5.27$ с. Причина — лимит 12 проходов цикла набора фаз `_advance_phases` прототипа: решение существует, но цикл до него не доходит.

**Исправление:** проход, который только снимает газ, в лимит `max_active_iter` не считается. Такой проход строго сужает набор фаз, поэтому подряд их не больше $N$. Общее число проходов ограничено $\text{max\_active\_iter} + N$. Где цикл кончается за ≤ 12 проходов, он идёт как прежде, побитово.

Замер на варианте (копия метода в пробе):
- все 23 конфига примеров побитово;
- регрессия прототипа 11/11 и T05 6/6 PASS;
- тесты прототипа 101 passed; GPN — быстрый уровень 1656 passed, медленный 276 passed;
- ни в одном из этих прогонов проходов не стало больше 12;
- первый шаг 19 и 21 сходится при всех $\Delta t$ от 0.01 с.

## 2. Анализ

### 2.1. Воспроизведение

Теста-воспроизводителя нет: штатные расчёты начинают добычу шагом 1 сут, он сходится. Проба `vault/issues/bug-028/probes/first_step_probe.py`, режимы:

| режим | что делает | выход |
|---|---|---|
| `single <пример> <dt…>` | конфиг примера, сокращённый до одного шага $\Delta t$ от $t = 0$, `max_retries = 0` (без дробления) | `single.out.txt` |
| `stages <пример> <dt…>` | ступени 1–4 `advance` по отдельности; ход набора фаз ступени 1 по проходам; ветка «открыта» ступеней 2–4 | `stages.out.txt` |
| `passes <пример> <K> <dt…>` | ступень 1 при лимите K проходов: сколько проходов нужно | `passes400.out.txt` |
| `aset`, `co` | обход через конфиг: `max_active_set_iter` = 400; $c_o$ = 3.3e-9 1/Па | `aset400.out.txt`, `co33e-10.out.txt` |
| `v1 <пример> <N|0> <dt…>` | `single` с вариантом 1 (`variant1.py`) | `first_step_v1.out.txt` |

Один шаг без дробления на базе (`single.out.txt`):

| $\Delta t$, с | 0.01 | 0.1 | 1 | 5.27 | 30 | 120 | 600 | 3600 | 86400 |
|---|---|---|---|---|---|---|---|---|---|
| 19 | отказ | отказ | отказ | отказ | отказ | отказ | сошёлся | сошёлся | сошёлся |
| 21 | отказ | отказ | отказ | отказ | сошёлся | сошёлся | сошёлся | сошёлся | сошёлся |
| 20 | сошёлся | сошёлся | сошёлся | сошёлся | сошёлся | сошёлся | сошёлся | сошёлся | сошёлся |

Подшаги дробления те же, что одиночный шаг: Simulator делит подшаг пополам и повторяет из того же состояния. При штатном `max_retries = 9` шаг 1 с в 19 тоже отказывает: за 8 с, на наименьшем подшаге 1.95e-3 с, «набор фаз не установился» (`split_19_1s.out.txt`, замер аудита на `6adea25`; до BUG-025 — `vault/issues/feat-032/probes/diag_19_first1.out.txt`). Эмуляция нарастания FEAT-032 на первом интервале после BUG-025 шла подшагами до 6.4e-4 с больше 35 мин (`vault/issues/bug-025/probes/ramp_with_floor_19.out.txt`).

### 2.2. Причинная цепочка

1. **Вход.**
   - Пример 19: $c_o = 0$ (Стендинг, `pvt.co_undersaturated` по умолчанию 0, `config.py:68`), $c_r = 0$ (`rock.compressibility` по умолчанию 0, `config.py:56`). Запас над давлением насыщения $(p_0 - p_b)/(p_0 - p_{wf}) = 0.024$, $p_b$ = 241.85 бар.
   - Пример 21: то же, запас 0.032, $p_b$ = 172.23 бар.
   - Пример 20 для сравнения: $c_o$ = 3.3e-9 1/Па, запас 0.097.
2. **Проход 1 ступени 1** (`blackoil.py:585-595`). Набор фаз начального состояния — все ячейки однофазные. Однофазная зона при $c_o = c_r = 0$ несжимаема: Ньютон за 1–2 итерации даёт стационарный профиль давления при любом $\Delta t$. Замер: $p(r_w)$ = 30.31 бар и 342 включаемые ячейки при 0.01, 1, 120, 600 и 86400 с. $R_s > R_{s,\text{sat}}(p) + 10^{-5}$ выходит в 342 из 350 ячеек (21 — в 339). Все они включаются двухфазными, $S_g$ — по «закрытому сосуду» (`:596-602`).
3. **Проходы 2…** Двухфазная зона сжимаема (газ), и решение — узкая зона у забоя. $S_g < -10^{-9}$ получается только на внешнем краю набора. Каждый проход снимает газ с 1–24 крайних ячеек, новых включений нет (`stages.out.txt`):

   | пример, $\Delta t$ | включено проходом 1 | двухфазных в решении | снято за проход | проходов нужно (`passes400`) |
   |---|---|---|---|---|
   | 19, 0.01 с | 342 | 30 | — | 182 |
   | 19, 1 с | 342 | 98 | 2 (проходы 2–12) | 62 |
   | 19, 120 с | 342 | 190 | 6–24 | 16 |
   | 19, 600 с | 342 | 222 | 14–26 | 11 |
   | 19, 86400 с | 342 | 309 | — | 5 |
   | 21, 0.01 с | 339 | 23 | — | 194 |
   | 21, 1 с | 339 | 82 | 1 | 78 |
   | 21, 30 с | 339 | 145 | 3–4 | 29 |

   Набор сужается монотонно, не колеблется: гипотеза реестра о колебании не подтвердилась.
4. **Исчерпание.** Лимит `max_active_iter` = 12 (`:586`; `numerics.max_active_set_iter`, `config.py:159`) кончается раньше, выход `'active_set'` (`:605-610`). Для ступени 1 порог по $\Delta t$ — там, где проходов нужно больше 12. В 19 это и порог шага (120 с отказ, 600 с — 11 проходов). В 21 шаг 30 с (29 проходов) спасает ступень 4, отказывают шаги ≤ 5.27 с.
5. **Ступени 2–4** (`advance` `:481-503`, `_fallback` `:538-579`).
   - Ветка «открыта» в ступенях 2 и 3 кончается тем же исчерпанием 12 проходов или 15 итерациями Ньютона.
   - Ступень 4 (`_newton_switching`, `:629`) упирается в предел 40 итераций при 399–497 переключениях. Исключение — 21 при 30 с: там она сходится за 31 итерацию, и шаг принимается.
   - Затем пробуется ветка «закрыта». Она «сходится» за 0 итераций на неизменном состоянии, но отвергается как несогласованная ($p_0 > p_{wf}$, `:569`).
6. **Проявление.**
   - `advance` возвращает отказ с числами ступени 1 (подмена DEBT-030, `:504-519`).
   - Адаптер бросает `HydroConvergenceError` («набор фаз не установился; числа — Ньютона ступени 1», `prototype_adapter.py:246-251`).
   - Simulator дробит шаг. Подшаги до ~0.01 с отказывают так же; после BUG-025 ~0.01 с сходится, и расчёт ползёт мелкими подшагами.

**Почему решение существует:** при `max_active_set_iter` = 400 первый шаг сходится при всех $\Delta t$ (`aset400.out.txt`). Тот же результат даёт вариант 1 (`first_step_v1.out.txt`). При $c_o$ = 3.3e-9 1/Па шаг сходится и без этого (`co33e-10.out.txt`).

**Связь с теорией.** Цикл `_advance_phases` — метод активных множеств для условия дополнительности $S_g \ge 0$, $R_{s,\text{sat}}(p) - R_s \ge 0$, $S_g\,(R_{s,\text{sat}} - R_s) = 0$ ([[Jaffré Sboui 2010 — закон Генри и исчезновение газовой фазы]]). Метод активных множеств как полугладкий Ньютон — [[Hintermüller Ito Kunisch 2003 — метод активного множества как полугладкий Ньютон]] (SIAM J. Optim. 13, 865–888; заметка краткая, из контекста цитирования).

Утверждение «при матрице типа M итерации сходятся монотонно, и проходов тем больше, чем дальше начальное множество от решения» — по памяти, в заметке его нет, не сверено. Замер выше с ним согласуется: после перелёта на проходе 1 — монотонное сужение по краю. Правка на этом утверждении не держится, конечность — в §2.5.

### 2.3. Целевое состояние

- Первый шаг добычи из равновесия в 19 и 21 сходится ступенью 1 при любом $\Delta t$ от 0.01 с. Числа — в §3.3, тест A.
- Цикл набора фаз конечен с явной оценкой: проходов с включением газа ≤ `max_active_iter`, всего ≤ `max_active_iter` + $N$.
- Где цикл кончался за ≤ `max_active_iter` проходов — побитово то же: все 23 конфига примеров, регрессия прототипа (11 + 6 расчётов T05), тесты прототипа и GPN без изменений ожидаемых чисел.
- Смысл `numerics.max_active_set_iter` в текстах — «проходов набора фаз с включением газа». Умолчание 12 не меняется.
- Исключение первого интервала из нарастания FEAT-032 **не снимается** — это решение пользователя (2026-10-11). После исправления его причина устраняется: замер к решению — в §2.7.

### 2.4. Варианты

**В1. Не считать проходы, которые только снимают газ.** Счётчик `counted` растёт только на проходе, где газ включился хотя бы в одной ячейке. Проход без включений строго сужает набор (`newmask = mask − deactivate`), подряд таких не больше числа двухфазных ячеек ≤ $N$.
- Изменения: `_advance_phases` (`blackoil.py:580-610`): `for` → `while`, счётчик, отчёт исчерпания пишет `aset`.
- Плюсы: общий для любого входа; побитово там, где цикл кончался за ≤ 12 проходов; ~5 строк.
- Минусы: оценка числа проходов в худшем случае — $(\text{max\_active\_iter}+1)(N+1)$ при чередовании «включение — длинная серия снятий». Не замерено, но при $N$ = 350 это до ~4.6 тыс. проходов, ~26 с на вызов, ×3 ступени, ×10 уровней дробления.
- Трудоёмкость: 1 файл, ~10 строк.

**В1б (выбран). В1 + общий предел $\text{max\_active\_iter} + N$ проходов.** Условие цикла `counted < max_active_iter and aset < max_active_iter + n`.
- Плюсы: худший случай линеен по $N$, того же порядка, что замеренный успех. Предел нигде не достигается: наибольшее число проходов 194 при $N$ = 350 (предел 362) и 334 при $N$ = 800 (предел 812). Значит, всё замеренное для В1 верно и для В1б.
- Минусы: ещё одно условие и тест на него (подменный Ньютон, §3.3 тест C3).
- Трудоёмкость: +1 строка.

**В2. Поднять умолчание `numerics.max_active_set_iter`** (12 → 400). Работает и как обход сейчас (`aset400.out.txt`).
- Плюсы: без правки прототипа.
- Минусы:
  - зацикленный набор (включение ↔ снятие) тоже сожжёт до 400 проходов, прежде чем передать шаг ступени 2: цена неудачного шага растёт в ~30 раз;
  - лимит теряет смысл ограничителя: 400 — подгонка под $N$ = 350; при $N$ = 800 и 0.01 с нужно 334, при $N$ = 1600 — больше 400 (оценка, не замерено);
  - тест `test_defaults_match_prototype` (`test_config.py:1181`) требует равенства умолчаний конфига и `advance` — правка в двух местах.

**В3. Начальный набор фаз делением пополам по положению фронта.** При добыче из однородного состояния двухфазная зона связна от забоя: ~$\log_2 N$ ≈ 9 решений Ньютона находят фронт, дальше штатный цикл.
- Плюсы: $O(\log N)$ проходов вместо $O(N)$.
- Минусы:
  - эвристика со своим допущением (связность неверна после останова и растворения газа, при чередовании режимов);
  - нужен критерий включения;
  - ~40 строк в прототипе и отдельные тесты.

  Выигрыш — секунды на одном первом шаге: 1.7 с при $N$ = 350 и 0.01 с, 5.7 с при $N$ = 800. Отложить до замера, где это станет узким местом.

**В4. Поднять предел ступени 4** (40 итераций).
- Минусы: ступень 4 — для останова (BUG-020). На старте добычи она запасная и тоже снимает газ по краю (399–497 переключений). Те же минусы, что у В2.

**В5. $c_o > 0$ в примерах 19 и 21** (`pvt.co_undersaturated` = 3.3e-9 1/Па, Васкес–Беггс, как в 20 по DEBT-034).
- Замер: первый шаг сходится при всех $\Delta t$ за 0.1–0.2 с.
- Не исправление: $c_o = 0$ — умолчание конфига и допустимый вход. Меняет физику, истории, README и тесты 19 и 21. Вне этого плана — вопрос пользователю (§2.7).

**В6. Заменить внешний цикл набора фаз переключением внутри Ньютона.** Варианты:
- полугладкий Ньютон для условий дополнительности (Newton-min) — [[Ben Gharbia Jaffré 2014 — полугладкий Ньютон для появления и исчезновения газовой фазы]];
- сквозные переменные $(p, X)$ с обрезкой $S_g = \max(0, \cdot)$ — [[Bourgeat Jurak Smaï 2009 — двухфазная фильтрация с растворением газа в хранилище отходов]].

Ни один на нашей задаче не проверялся ([[запасной путь с отрицательной насыщенностью и веткой скважины снимает порог шага на скачке p_wf вверх]]). Ближайший аналог в проекте — ступень 4 (`_newton_switching`, BUG-020): переключения после каждой итерации, ограничения приращений. Здесь она отказывает так же: 399–497 переключений и предел 40 итераций, газ снимается по краю (§2.2 п. 5). Метод S плана BUG-014 (переключение на каждой итерации, полный шаг) на первом шаге из начального состояния зацикливался на ячейке фронта.
- Минусы: переделка решателя фаз прототипа с новой глобализацией; нужен свой план и проверка против эталона IMEX. Для счёта проходов это непропорционально.
- Если потребуется, то отдельной задачей.

### 2.5. Выбор

**В1б.** Он устраняет причину — счёт проходов, а не симптом — лимит или вход примера. Конечность и худший случай — из простого рассуждения:
- проход без включений строго уменьшает $|\text{mask}|$;
- проходов с включением ≤ `max_active_iter`;
- всего проходов < `max_active_iter` + $N$ + 1.

Побитовость там, где цикл кончался за ≤ `max_active_iter` проходов. Проход $k \le$ `max_active_iter` выполняется и в старом, и в новом цикле: перед ним `counted` ≤ $k-1$ < `max_active_iter` и `aset` = $k-1$ < `max_active_iter` + $N$. Тело прохода не меняется, значит те же приближения и тот же отчёт.

Исчерпание без проходов «только снятие» тоже прежнее: после прохода `max_active_iter` с включением на каждом проходе `counted` = `max_active_iter`, `aset` = `max_active_iter`, и отчёт несёт то же `active_set_iterations`.

В2–В4 отвергнуты (§2.4). В5 — не исправление решателя. В6 — переделка решателя фаз, вне масштаба бага.

### 2.6. Подводные камни

| # | Проверка | Итог |
|---|---|---|
| 1 | **Побочные эффекты.** `_advance_phases` вызывают `advance` (`:470`), `_fallback` (`:546`, `:564`); ступень 4 уходит из него в `_newton_switching` до цикла (`:584`) — не затронута. Подмены метода на экземпляре в тестах (`test_prototype_open_branch_skip.py:148`, `test_prototype_globalization.py`, `test_prototype_phase_switching.py`, `test_prototype_well_branch.py`) идут в обход тела | ✅ |
| 2 | **Граничные случаи.** `max_active_iter` = 1 (`test_active_set_exit`, `test_prototype_failure_diagnostics.py:134-146`): проход 1 включает газ → `counted` = 1 → выход, `(active_set_iterations, phase_switches)` = (1, 5) как прежде. Пустой набор после снятий: проход без переключений → сходимость. $N$ = 1: предел `max_active_iter` + 1 | ✅ |
| 3 | **Производительность.** Расходится с прежним только там, где прежний цикл исчерпывался, — замер: на всех примерах таких вызовов 0, время примеров то же (`examples_v1.out.txt`). Первый шаг 0.01 с: 182 прохода, 1.7 с ($N$ = 350); 334 прохода, 5.7 с ($N$ = 800) (`first_step_v1.out.txt`); худший случай ограничен `max_active_iter` + $N$ проходами | ✅ |
| 4 | **Обратная совместимость.** 23 конфига примеров побитово (отпечатки `examples_v1.out.txt`); регрессия прототипа 11/11 PASS (`regression_v1.out.txt`); регрессия T05 6/6 PASS (`regression_t05_v1.out.txt`); тесты прототипа 101 passed; GPN быстрый 1656 passed, медленный 276 passed (`gpn_slow_v1.out.txt`); событий (проходов > 12) 0 во всех; метки `*.mark.txt` подтверждают, что подмена стояла в каждом дочернем процессе | ✅ |
| 5 | **Смысл отчёта.** `active_set_iterations` может стать больше `max_active_iter`. Потребители: журнал шагов прототипа (`simulation.py:83`, `:99`; `runner.py:32`), `runner.py:90` — только печать; `_grow_dt` (`simulation.py:23-26`) читает `iterations` — в прежних сценариях без изменений; GPN `_failure_details` проходы не печатает | ✅ |
| 6 | **Состояние при ошибке.** Цикл не меняет атрибуты модели; возвраты те же, что прежде | ✅ |
| 7 | **Численная устойчивость.** Допуски и критерии сходимости не меняются; условие снятия ($S_g < -10^{-9}$) и включения ($R_s > R_{s,\text{sat}} + 10^{-5}$) — прежние | ✅ |
| 8 | **Смысл параметра конфига.** `numerics.max_active_set_iter` теперь ограничивает проходы с включением газа. Умолчание 12, проверки (`config.py:659`) и равенство умолчаний (`test_config.py:1181`) не меняются; тексты — шаг 3 | ⚠️ адресован шагом 3 |
| 9 | **Связь с задачами.** FEAT-032: `simulator.py:91-95` и `test_simulator.py:158` называют BUG-028 причиной исключения первого интервала — тексты уточнить, поведение не трогать (шаг 3). DEBT-054 (#102): отказ всех ступеней показывает числа ступени 1 — вне плана, новая DEBT (§2.7). DEBT-048 (память ступени 4) — не затронута: ступень 4 не идёт через цикл | ⚠️ адресован |
| 10 | **Импорты.** Не меняются | ✅ |
| 11 | **Прототип.** Меняет `HydroSolverPrototype/`. Ожидание по замеру варианта (`sitecustomize` в `probes/site_v1/`, база `6d27358`, прототип = `209326d`): тесты прототипа 101 passed; регрессия полная 17/17 PASS (`--quick` 11/11 + T05 6/6), ни одного вызова с проходами > 12 — побитово. Запись в `CHANGELOG_1.0.3.md` — шаг 3 | ✅ |
| 12 | **Соответствие постановке.** `problem_statement.tex` внешний цикл набора фаз не описывает (переключения — `sssec:switching_disc`, внутри Ньютона); формулы не меняются, `.tex` не трогать | ✅ |
| 13 | **Параллельные сессии.** Другая сессия может влить ветку с правкой `blackoil.py` посреди реализации: замеры дадут ложные расхождения, база уедет. Сверять `git log` базы до и после замеров и регрессии. На 2026-10-14 в реализации DEBT-068 (`.worktrees/debt-068`): `config.py` `:53-56` и `_validate` `:523+`, `P8-формат-ввода-json.md` `:216-227`, `json-config-schema.md` `:47-55` — с правками BUG-028 (`config.py:159`, P8 `:202`, схема `:177`) строки не пересекаются; номера после неё сдвинутся только ниже `:523` и `:225`. Планы BUG-015, DEBT-062 файлов BUG-028 не трогают. `CHANGELOG_1.0.3.md` дописывается в конец — при параллельной правке прототипа (DEBT-067, #113) конфликт в конце файла разрешать сохранением обоих разделов | ⚠️ |
| 14 | **Тесты набора прототипа.** Новых тестов в `Prototype_1.0.3/tests/` нет, как у DEBT-055: логику проверяют тесты GPN, побитовость — регрессия прототипа. В поставке прототипа (FEAT-031) правку покрывает только регрессия. Если нужно, C1–C3 переносятся в набор прототипа без изменений, кроме модели (`_build` использует книгу Nabor_1b) | ✅ решено так |

### 2.7. Новые проблемы и вопросы

1. **[[DEBT-069]] (зарегистрирована при планировании):** при отказе всех ступеней `advance` текст показывает числа ступени 1. Причина отказа ветки «открыта» ступеней 2–4 скрыта отчётом последней ветки «закрыта» (0 итераций, отвергнута как несогласованная) — в BUG-028 её нашла только отдельная проба (`stages.out.txt`). Продолжение DEBT-054 (#102). Не блокирует.
2. **Вопрос пользователю (не задача):** снимать ли исключение первого интервала из нарастания FEAT-032 (`first_substep_depth`, `interval_idx == 0`). Замер с вариантом 1, $h_0$ = 0.11 с (`ramp_first_v1.out.txt`):

   | пример | время расчёта | max $\lvert\Delta T(r_w)\rvert$ | первая запись (1 сут) |
   |---|---|---|---|
   | 19 | 5.4 с против 1.4 с | 0.047 К | $\Delta T$ = +0.005 К, $\Delta R_s$ = −0.020, $\Delta p$ = −0.041 бар |
   | 21 | 6.5 с против 1.3 с | 0.025 К | $\Delta T$ = −0.004 К, $\Delta R_s$ = −0.014, $\Delta p$ = −0.028 бар |

   В каждом прогоне один вызов выходит за 12 проходов: 130 и 143 прохода. Снятие исключения меняет истории всех примеров (нарастание на первом интервале) — отдельная задача по решению пользователя.
3. **Вопрос пользователю (не задача):** $c_o = 0$ — умолчание `pvt.co_undersaturated`. Это вырожденный предел: давление в однофазной зоне устанавливается мгновенно по всей области. Нужен ли $c_o > 0$ в 19 и 21 (В5) — решение о физике примеров, вне этого бага.

## 3. Шаги

### Шаг 1: Тесты-воспроизводители (красные)

**Цель:** зафиксировать отказ и целевое поведение до правки.
**Файлы:** `numerical_solver/tests/test_prototype_phase_set_passes.py` (новый).

**Контекст.** Отказ виден на модели фабрики примеров 19 и 21 (`max_active_iter` = 12, `cell_tol` = 1e-8 — как в расчёте). Логику счёта проходов (снятие не считается, предел `max_active_iter` + $N$) на настоящей модели не проверить: предел в замерах не достигается. Для неё — подменный Ньютон на модели Nabor_1b из 12 ячеек (`_build` из `test_prototype_cell_tolerance.py:42`).

**Что сделать:** создать файл с тестами §3.3: A1–A4, B1, C1–C3, D1. Шапка модуля:

```python
"""BUG-028: цикл набора фаз прототипа не считает в лимит проходы, которые только снимают газ.

Первый шаг добычи из равновесия в примерах 19 и 21 (c_o = c_r = 0) короче 120 с / 5 с не
сходился: первый, однофазный проход стационарен и включает газ в 342 из 350 ячеек, дальше
газ снимается только с внешнего края набора, 1-24 ячейки за проход, а лимит
max_active_iter = 12 проходов кончался раньше (при 1 с нужно 62 прохода, при 0.01 с — 182).
Теперь лимит — на проходы с включением газа; всего проходов не больше max_active_iter + N.

План: vault/plans/bug-028 first-step-phase-set.md; замеры — vault/issues/bug-028/probes/.
"""
```

**Проверка после шага.**
- Тест: `.venv\Scripts\python -m pytest tests/test_prototype_phase_set_passes.py -q`.
- Ожидание: падают A1–A4, C1, C3, D1 (7). Проходят B1 ×2, C2 (3). Если падает B1 или C2 — тест неверен, разобрать до шага 2.
- Замер аудита: те же тесты, записанные функциями, на исходном коде дают ровно этот итог (`vault/issues/bug-028/probes/plan_tests_check.py orig`, `plan_tests_check.out.txt`):
  - A1–A4: `converged=False`, `passes=12`, `exit=active_set`;
  - C1: отказ после 2 проходов;
  - C3: отказ после 3 проходов;
  - D1: `RuntimeError` «набор фаз не установился».
- D1 задаёт `max_retries = 0` ради скорости и однозначности: при штатных 9 шаг тоже отказывает, но за 8 с дробления (`split_19_1s.out.txt`).
- Регресс: быстрый — **1659 passed, 7 failed** (ровно семь новых красных), 276 deselected. Коммит шага с красными тестами — по контракту `/implement` («тест до реализации»).

**Подводные камни:** §2.6 п. 1 (подмена на экземпляре: `model._newton_fixed_active_set = fake`, вернуть `del model._newton_fixed_active_set`, если модель общая).
**Зависимости:** блокирует шаг 2.
**Оценка:** ~170 строк, ~60 мин.

### Шаг 2: Исправление `_advance_phases` (В1б)

**Цель:** проходы без включения газа не расходуют `max_active_iter`; всего проходов ≤ `max_active_iter` + $N$.
**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` — docstring модуля (после абзаца DEBT-055, `:41-43`), метод `_advance_phases` (`:580-610`).

**Контекст:** §2.2, §2.5.

**Что сделать:**

1. Docstring модуля — дописать после абзаца DEBT-055:

```
BUG-028: _advance_phases limits by max_active_iter only the passes that switch gas on; a pass
that only switches gas off shrinks the two-phase set and is not counted, all passes together
stay below max_active_iter + N.  Production from equilibrium with incompressible
undersaturated oil (GPN examples 19, 21) failed every stage at steps up to 120 s and 5.27 s.
```

Правку метода (п. 2 ниже) вносить **четырьмя заменами**, а не одной: блоки «До» и «После» п. 2 опускают строки 597-602, и целиком как `old_string` они не годятся.

| # | Где (на `209326d`) | Что |
|---|---|---|
| 1 | `:581` | docstring метода |
| 2 | `:585-586` | после строки `state_old=…total_newton=0` — комментарий BUG-028 и `aset=counted=0; max_passes=…`; `for aset in range(…)` → `while …:` и первой строкой тела `aset+=1` |
| 3 | перед `:595` (`newmask=…`) | строка `if np.any(activate): counted+=1   # …` |
| 4 | `:605-608` | комментарий отчёта исчерпания и `max_active_iter` → `aset` в `BlackOilNewtonReport(…)` |

Остальные строки тела цикла не трогать. Результат сверить с блоком «После».

2. Метод `_advance_phases`.

До (`:580-610`):

```python
    def _advance_phases(self,state_old,dt_s,max_active_iter=12,max_newton=15):
        """Phase active-set loop (unchanged Prototype 1 logic)."""
        # BUG-020: inside the fourth stage of advance the BUG-014 fallback (well branches)
        # runs the Newton with phase switches inside it instead of this loop
        if self._phase_switching: return self._newton_switching(state_old,dt_s)
        state_old=state_old.copy(); mask=state_old.gas_active.copy(); guess=state_old.copy(); total_switches=total_newton=0
        for aset in range(1,max_active_iter+1):
            z,report=self._newton_fixed_active_set(self.pack(guess,mask),state_old,dt_s,mask,max_iter=max_newton); total_newton+=report.iterations
            if not report.converged:
                report.active_set_iterations=aset; report.phase_switches=total_switches; return guess,report
            trial=self.unpack(z,mask); rs_sat=self.pvt.rs_sat(trial.pressure_bar)
            activate=(~mask)&(trial.rs_sm3_sm3>rs_sat+self.rs_switch_tol); deactivate=mask&(trial.sg<-self.sg_switch_tol)
            ns=int(np.count_nonzero(activate)+np.count_nonzero(deactivate)); total_switches+=ns
            if ns==0:
                tiny=mask&(trial.sg<0)&(trial.sg>=-self.sg_switch_tol); trial.sg[tiny]=0.0; trial.gas_active=mask.copy(); report.iterations=total_newton; report.active_set_iterations=aset; report.phase_switches=total_switches; return trial,report
            newmask=mask.copy(); newmask[activate]=True; newmask[deactivate]=False; guess=trial.copy(); guess.gas_active=newmask.copy()
            if np.any(activate):
                ...  (строки 597-602 без изменений)
            if np.any(deactivate): guess.sg[deactivate]=0.0; guess.rs_sm3_sm3[deactivate]=self.pvt.rs_sat(guess.pressure_bar[deactivate])
            mask=newmask
        # DEBT-054: the phase loop ran out; r is the residual of the guess with the new phase set,
        # which no Newton solved -- no absolute tolerance, the per-cell measure of r
        r=self.residual(self.pack(guess,mask),state_old,dt_s,mask)
        return guess,BlackOilNewtonReport(False,total_newton,float(np.linalg.norm(r,np.inf)),max_active_iter,total_switches,
                                          cell_measure=self._cell_measure(r,self._cell_weights(state_old,dt_s)),
                                          exit_reason='active_set')
```

После (меняются docstring, строки перед циклом, заголовок цикла, одна строка после `if ns==0`, отчёт исчерпания; тело прохода — без изменений):

```python
    def _advance_phases(self,state_old,dt_s,max_active_iter=12,max_newton=15):
        """Phase active-set loop (Prototype 1 logic); max_active_iter counts the passes that switch gas on (BUG-028)."""
        # BUG-020: inside the fourth stage of advance the BUG-014 fallback (well branches)
        # runs the Newton with phase switches inside it instead of this loop
        if self._phase_switching: return self._newton_switching(state_old,dt_s)
        state_old=state_old.copy(); mask=state_old.gas_active.copy(); guess=state_old.copy(); total_switches=total_newton=0
        # BUG-028: max_active_iter limits the passes that switch gas on in some cell.  A pass that
        # only switches gas off shrinks the two-phase set, so at most N such passes follow in a
        # row; all passes together stay below max_active_iter + N.  Production from equilibrium
        # with incompressible undersaturated oil (c_o = c_r = 0, GPN examples 19, 21): the first,
        # single-phase pass is steady at any dt and switches gas on in 342 of 350 cells; every pass
        # after it switches gas off only at the outer edge of the set, 1-24 cells, and a step of
        # 1 s needs 62 passes (0.01 s: 182) -- steps up to 120 s (19) and 5.27 s (21) failed
        # every stage.  A loop that
        # ends within max_active_iter passes runs the same passes as before, bitwise: before pass
        # k <= max_active_iter, counted <= k-1 and aset = k-1.
        aset=counted=0; max_passes=max_active_iter+self.grid.n
        while counted<max_active_iter and aset<max_passes:
            aset+=1
            z,report=self._newton_fixed_active_set(self.pack(guess,mask),state_old,dt_s,mask,max_iter=max_newton); total_newton+=report.iterations
            if not report.converged:
                report.active_set_iterations=aset; report.phase_switches=total_switches; return guess,report
            trial=self.unpack(z,mask); rs_sat=self.pvt.rs_sat(trial.pressure_bar)
            activate=(~mask)&(trial.rs_sm3_sm3>rs_sat+self.rs_switch_tol); deactivate=mask&(trial.sg<-self.sg_switch_tol)
            ns=int(np.count_nonzero(activate)+np.count_nonzero(deactivate)); total_switches+=ns
            if ns==0:
                tiny=mask&(trial.sg<0)&(trial.sg>=-self.sg_switch_tol); trial.sg[tiny]=0.0; trial.gas_active=mask.copy(); report.iterations=total_newton; report.active_set_iterations=aset; report.phase_switches=total_switches; return trial,report
            if np.any(activate): counted+=1   # BUG-028: only a pass that switches gas on is counted
            newmask=mask.copy(); newmask[activate]=True; newmask[deactivate]=False; guess=trial.copy(); guess.gas_active=newmask.copy()
            if np.any(activate):
                ...  (строки 597-602 без изменений)
            if np.any(deactivate): guess.sg[deactivate]=0.0; guess.rs_sm3_sm3[deactivate]=self.pvt.rs_sat(guess.pressure_bar[deactivate])
            mask=newmask
        # DEBT-054: the phase loop ran out; r is the residual of the guess with the new phase set,
        # which no Newton solved -- no absolute tolerance, the per-cell measure of r.  BUG-028: aset
        # passes, max_active_iter of them switched gas on (or max_active_iter + N passes in all);
        # aset = max_active_iter where every pass switched gas on, as before
        r=self.residual(self.pack(guess,mask),state_old,dt_s,mask)
        return guess,BlackOilNewtonReport(False,total_newton,float(np.linalg.norm(r,np.inf)),aset,total_switches,
                                          cell_measure=self._cell_measure(r,self._cell_weights(state_old,dt_s)),
                                          exit_reason='active_set')
```

Копия этого кода без предела `max_passes` — `vault/issues/bug-028/probes/variant1.py`, `advance_phases_v1`; на ней сняты все замеры плана. Предел нигде не достигается (§2.4 В1б), поэтому замеры верны и для кода выше.

Код блока «После» с пределом дословно, без комментариев, — `vault/issues/bug-028/probes/plan_tests_check.py`, `_advance_phases_plan`. На нём тесты §3.3 зелёные все 10 (`plan_tests_check.out.txt`, режим `plan`). Сверка аудита: каждая строка кода блока есть в пробе, каждая строка блока «До» — в `blackoil.py`.

**Проверка после шага.**
- Тест: `.venv\Scripts\python -m pytest tests/test_prototype_phase_set_passes.py -q` — все зелёные.
- Регресс: быстрый — 1656 + новые passed, прежние тесты без правок.
- Регресс прототипа (из `Prototype_1.0.3`): `..\..\.venv\Scripts\python -m pytest tests -q` → 101 passed; `..\..\.venv\Scripts\python regression\run_regression.py --quick` → 11/11 PASS (ожидание — побитово, как на варианте в пробе). Выходы `OUTPUT\REGRESSION_*` удалить.
- Проба (`PYTHONPATH` на worktree, «Как начать», п. 4): `.venv\Scripts\python ..\vault\issues\bug-028\probes\first_step_probe.py single 19_rs150_cooling 0.01 1 5.27 120 600 86400` и то же для `21_rs100_cooling 0.01 1 5.27 30`. Ожидание — «сошёлся», числа $p(r_w)$ и двухфазных ячеек как в `first_step_v1.out.txt` (19: 78.13 / 30, 38.38 / 98, 34.84 / 129, 32.24 / 190, 31.70 / 222, 30.96 / 309; 21: 69.14 / 23, 36.28 / 82, 33.48 / 112, 32.07 / 145).

**Подводные камни:** §2.6 пп. 2, 4, 5, 11.
**Зависимости:** требует шаг 1. Блокирует шаги 3, 4.
**Оценка:** ~20 строк, ~30 мин (из них ~10 мин регрессия).

### Шаг 3: Тексты GPN и журнал изменений прототипа

**Цель:** смысл `max_active_set_iter`, причина исключения первого интервала и запись прототипа соответствуют коду.
**Файлы:**
- `numerical_solver/gpn_multiphase_solver/io/config.py:159`
- `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py:143`
- `numerical_solver/gpn_multiphase_solver/simulator.py:91-95`
- `numerical_solver/tests/test_simulator.py:158`
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` (в конец)

**Что сделать:**

1. `config.py:159`. До:
   ```python
       max_active_set_iter: int = 12          # проходов уточнения набора фаз (газ есть / нет)
   ```
   После:
   ```python
       # Проходов набора фаз с включением газа; проходы, где газ только снимается, не
       # считаются (BUG-028), всего проходов не больше max_active_set_iter + N
       max_active_set_iter: int = 12
   ```
2. `prototype_adapter.py:143`. До: `max_active_iter — проходов уточнения набора фаз (numerics.max_active_set_iter)`. После: `max_active_iter — проходов набора фаз с включением газа (numerics.max_active_set_iter, BUG-028)`.
3. `simulator.py:91-95`. До:
   ```python
           # Смена — граничные условия интервала не равны предыдущим; управление
           # сравнивается по значению (bc.py). Первый интервал сменой не считается
           # (решение пользователя): мелкий первый шаг добычи из равновесия в
           # примерах 19 и 21 не сходится (BUG-028). m — наименьшее, при котором
   ```
   После:
   ```python
           # Смена — граничные условия интервала не равны предыдущим; управление
           # сравнивается по значению (bc.py). Первый интервал сменой не считается
           # (решение пользователя 2026-10-11, когда мелкий первый шаг добычи из
           # равновесия в примерах 19 и 21 не сходился — BUG-028, исправлен в
           # прототипе; снятие исключения меняет истории всех примеров и решается
           # отдельно). m — наименьшее, при котором
   ```
   Поведение не меняется.
4. `test_simulator.py:158`. До: `"""Интервал 0 — не смена (BUG-028: мелкий первый шаг добычи из равновесия не сходится)."""`. После: `"""Интервал 0 — не смена (решение пользователя 2026-10-11; причина — BUG-028, исправлен)."""`.
5. `CHANGELOG_1.0.3.md` — раздел в конец:

```markdown
## Local changes — GPN project (BUG-028): passes that only switch gas off are not counted
- Problem: `_advance_phases` gave up after `max_active_iter` (12) passes of the phase active-set loop. In GPN production from equilibrium with incompressible undersaturated oil (c_o = c_r = 0; GPN examples 19, 21: (p0 - pb)/(p0 - p_wf) = 0.024 and 0.032, N = 350) the first, single-phase pass is steady at any dt and switches gas on in 342 of 350 cells. Every later pass switches gas off only at the outer edge of the two-phase set, 1-24 cells, with no new switch-ons: a step of 1 s needs 62 passes, 0.01 s -- 182, 120 s -- 16, 600 s -- 11. Steps up to 120 s (example 19) and 5.27 s (example 21) failed every stage of advance; the 'open' branch of stages 2-3 ran out of the same 12 passes, the fourth stage out of its 40 iterations.
- `_advance_phases` counts against `max_active_iter` only the passes that switch gas on in some cell; a pass that only switches gas off shrinks the set, so at most N of them follow in a row, and all passes together stay below `max_active_iter + N`. The report of an exhausted loop carries the number of passes run (`active_set_iterations`), equal to `max_active_iter` where every pass switched gas on, as before.
- A loop that ended within `max_active_iter` passes runs the same passes, bitwise: tests ⟨101⟩ passed, regression 11/11 PASS quick and ⟨17/17⟩ PASS full. In GPN all 23 example configurations are bitwise. The first production step of examples 19 and 21 converges with the first stage at every dt down to 0.01 s (182 passes, 1.7 s at N = 350; 334 passes, 5.7 s at N = 800).
- Physics, residual equations, convergence tests, switching thresholds, the other stages and well semantics are unchanged. The distribution version stays `1.0.3+gpn.1`. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
- Tests: `numerical_solver/tests/test_prototype_phase_set_passes.py` of the GPN project (⟨число⟩).
- Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/117; plan: `vault/plans/bug-028 first-step-phase-set.md` of the GPN project.
```

Числа в ⟨⟩ — по фактическому прогону шагов 2 и 4.

**Проверка после шага.**
- Тест: `.venv\Scripts\python -m pytest tests/test_simulator.py tests/test_config.py -q`; `tests/test_eq_references.py` — ссылки в комментариях метками, номеров уравнений нет.
- Регресс: быстрый.

**Зависимости:** требует шаг 2.
**Оценка:** ~25 строк, ~20 мин.

### Шаг 4: Верификация

**Цель:** доказать «побитово, где сходилось» и «сходится, где отказывало» на полном объёме.
**Файлы:** — (только прогоны; выходы проб — в `vault/issues/bug-028/probes/`, суффикс `_impl`).

**Что сделать** (из `<worktree>\numerical_solver`, `PYTHONPATH` на worktree):

1. Примеры: `& $PY ..\vault\issues\bug-028\probes\examples_v1.py | Out-File -Encoding utf8 ..\vault\issues\bug-028\probes\examples_impl.out.txt` (~6 мин). Столбец «штатный» теперь — исправленный код. Каждый отпечаток сверить с «штатным» отпечатком той же строки `examples_v1.out.txt` (база `209326d`). Ожидание — все 23 совпадают, событий 0.
2. Первый шаг: `first_step_probe.py single` (как в шаге 2) для 19 и 21 по всем $\Delta t$ из §2.1 → `first_step_impl.out.txt`. Ожидание — все «сошёлся»; числа равны `first_step_v1.out.txt`. На $N$ = 800: `first_step_probe.py v1 19_rs150_cooling 800 0.01 1` — вариант в пробе, для сравнения времени.
3. Полный прогон GPN: `.venv\Scripts\python -m pytest tests/ -q` → 1932 + новые passed.
4. Полная регрессия прототипа (зафиксировать HEAD базы до старта, §2.6 п. 13): `..\..\.venv\Scripts\python regression\run_regression.py` → 17/17 PASS (ожидание по замеру: 11 + T05 — §2.6 п. 11). Выходы удалить.

**Проверка:** все четыре пункта — как ожидается. Любое расхождение отпечатка или FAIL регрессии — стоп и разбор: с какого шага расходится; есть ли в журнале шагов прототипа (`step_log.csv`, столбец `active_set_iterations`) вызовы с проходами > 12 — только там правка меняет ход расчёта. Эталон не переснимать; решение о пересъёме — за пользователем (шапка `/plan-fix`, «Правка прототипа»).
**Регресс:** полный — это и есть итоговый прогон `/implement`.
**Зависимости:** требует шаги 2, 3.
**Оценка:** ~60 мин (45 — полная регрессия, в фоне).

### Шаг 5: Vault и issue

**Цель:** знание о механизме — в vault, задача закрыта по порядку.
**Файлы:**
- `vault/knowledge/debugging/при c_o = 0 первый проход набора фаз включает газ почти во всей области.md` (новая; имя короче предела пути Windows с worktree)
- `vault/roadmap/известные баги и технический долг.md` (BUG-028: **Статус**; **План** заполнен при планировании, DEBT-069 зарегистрирована)
- `vault/knowledge/decisions/нарастающий шаг после смены управления — от 0.11 с, удвоение вчетверо уменьшает ошибку температуры у забоя за первый час.md:43`
- `vault/knowledge/decisions/P8-формат-ввода-json.md:202`
- `vault/knowledge/decisions/json-config-schema.md:177`
- `vault/00-home/index.md`
- `vault/issues/bug-028/05-comment-done.md`

**Что сделать:**
1. Заметка debugging. Frontmatter (`name`, `description`, `metadata: type: debugging`), разделы:
   - симптом — таблица §2.1;
   - цепочка — §2.2;
   - почему проход 1 стационарен ($c_o = c_r = 0$);
   - почему снятие идёт по краю;
   - исправление и его оценка (§2.5);
   - что не сделано: В3, вопросы §2.7.

   Ссылки: [[BUG-028]], [[FEAT-032]], [[BUG-025]], [[DEBT-054]].
2. Заметка FEAT-032, строка 43: «мелкий первый шаг … не сходится ни при каком $h_0$ — [[BUG-028]]» → «не сходился ([[BUG-028]], исправлен 2026-10-xx); исключение первого интервала осталось решением пользователя; с исправлением нарастание на первом интервале 19 и 21 сходится (5.4 и 6.5 с счёта, max $\lvert\Delta T(r_w)\rvert$ 0.047 и 0.025 К, `vault/issues/bug-028/probes/ramp_first_v1.out.txt`)».
3. `P8-формат-ввода-json.md:202`, `json-config-schema.md:177`: «проходов уточнения набора фаз» → «проходов набора фаз с включением газа; проходы, где газ только снимается, не считаются, всего не больше `max_active_set_iter` + $N$ (BUG-028)».
4. Реестр: **Статус** — «✅ ГОТОВО (дата)» с веткой, коммитами и числами тестов, по контракту `/implement` и образцу соседних записей; ссылка на заметку debugging.
5. `index.md`: заметка debugging — в раздел отладки (план уже добавлен при планировании).
6. `05-comment-done.md` по образцу `vault/issues/bug-026/05-comment-done.md`: что сделано, замеры шага 4, тесты; затем `gh issue comment 117 --repo ArturSalamatin/Oil_Gas --body-file vault/issues/bug-028/05-comment-done.md`.

**Проверка:** `--collect-only -q` (только документы).
**Зависимости:** требует шаг 4.
**Оценка:** ~40 мин.

## 3.3. Тестовая стратегия

Файл `numerical_solver/tests/test_prototype_phase_set_passes.py`. Модели:

- **Фабрика примеров 19, 21.** `load_config(EXAMPLES / name / "config.json")`, `SimulatorFactory.from_config(cfg)` → `sim, init`; `model = sim._hydro._model`; `model.set_bhp_control(cfg.time.history[0].p_wf / BAR_TO_PA)`; `ps = BlackOilState(pressure_bar=init.p / BAR_TO_PA, rs_sm3_sm3=init.Rs.copy(), sg=init.Sg.copy(), gas_active=(init.regime == 1))`. Фикстура `scope="module"` на пример. Модель между тестами не меняется: `advance` восстанавливает атрибуты в `finally`.
- **Nabor_1b, $N$ = 12** — `_build(12)` из `tests/test_prototype_cell_tolerance.py:42`: начальное состояние 200 бар, без газа.

**Тест A1–A4: `test_first_production_step_converges[19-0.01]`, `[19-1]`, `[19-5.27]`, `[21-1]`**
- Сценарий: первый шаг добычи из равновесия при $c_o = c_r = 0$, глубокая депрессия ниже $p_b$ (§2.2).
- Setup: `new, rep = model.advance(ps, dt)` с умолчаниями (12 проходов, 15 итераций) — как адаптер.
- Ожидание:
  - `rep.converged` и `not rep.fallback` — решила ступень 1;
  - `rep.active_set_iterations` = 182 / 62 / 41 / 78;
  - `int(new.gas_active.sum())` = 30 / 98 / 129 / 82;
  - `new.pressure_bar[0]` = 78.13 / 38.38 / 34.84 / 36.28 бар (`approx`, abs 0.01);
  - $0 \le S_g \le 1$.

  Числа — `first_step_v1.out.txt`, `passes400.out.txt`.
- Предотвращает: возврат лимита на проходы снятия; подмену исправления подъёмом умолчания (при 400 проходах A1 прошёл бы, но B1 и C1 — нет).
- Время: ~4 с всего (1.7 + 0.8 + 0.5 + 0.9).

**Тест B1: `test_first_pass_steady_switches_gas_on_almost_everywhere[0.01, 86400]`**
- Сценарий: механизм §2.2 п. 2 — при $c_o = c_r = 0$ проход 1 стационарен.
- Setup: пример 19, `model._advance_phases(ps, dt, max_active_iter=1)`.
- Ожидание: `exit_reason == "active_set"`, `active_set_iterations == 1`, `phase_switches == 342` при обоих $\Delta t$ (проход 1 включает газ, `counted` = 1 — выход как прежде).
- Предотвращает: молчаливую смену входа примера 19 (кто-то задаст $c_o > 0$ — тест A тогда не про BUG-028).
- Зелёный и до правки.

**Подменный Ньютон для C1–C3.** Функция в тесте `_scripted(model, script)` ставит `model._newton_fixed_active_set = fake`. `fake(z0, state_old, dt_s, gas_active, max_iter=15)` берёт следующий элемент `script` и строит `x` на `n = model.grid.n` ячейках:
- двухфазные ячейки (`gas_active`): $S_g$ = 0.1, кроме снимаемых — `-1e-3`;
- однофазные: $R_s = R_{s,\text{sat}}(p) - 1$, кроме включаемых — $R_{s,\text{sat}}(p) + 1$, где $p$ — `state_old.pressure_bar`.

Возврат: `np.concatenate([state_old.pressure_bar, x])` и `BlackOilNewtonReport(True, 1, 0.0)`. Элемент `script`:
- `("on", idx)` — включить ячейки `idx`;
- `("off_edge",)` — снять наибольшую по индексу двухфазную ячейку; при пустом наборе — без переключений;
- `("none",)` — без переключений.

Раскладка `z` — `pack` (`blackoil.py:222-225`): `[p, x]`, `x` = $S_g$ у двухфазных, $R_s$ у однофазных. Включение по `R_s > rs_sat + rs_switch_tol` (1e-5), снятие по `S_g < -sg_switch_tol` (1e-9). После теста — `del model._newton_fixed_active_set`.

**Тест C1: `test_switch_off_passes_not_counted`**
- Script: `("on", range(6))`, пять раз `("off_edge",)`, `("none",)`; `max_active_iter=2`.
- Ожидание: `converged`, `active_set_iterations == 7`, `phase_switches == 11`, `gas_active` — только ячейка 0.
- До правки: отказ `active_set` после 2 проходов.
- Предотвращает: счёт проходов снятия.

**Тест C2: `test_switch_on_passes_limited`**
- Script: `("on", [k])` для k = 0…11 (каждый проход включает новую ячейку); `max_active_iter=3`.
- Ожидание: `not converged`, `exit_reason == "active_set"`, `active_set_iterations == 3`, `phase_switches == 3`.
- Зелёный и до правки.
- Предотвращает: снятие лимита с включений (зацикливание включение ↔ снятие).

**Тест C3: `test_total_passes_capped_at_limit_plus_n`**
- Script: `("on", range(12))`, 12 × `("off_edge",)`, `("on", range(12))`, далее `("off_edge",)` без конца; `max_active_iter=3`, $N$ = 12.
- Ожидание: `not converged`, `exit_reason == "active_set"`, `active_set_iterations == 15` (= 3 + 12), `phase_switches == 12 + 12 + 12 + 1` = 37. Включений два (`counted` = 2 < 3), выход — по общему пределу.
- До правки: отказ после 3 проходов.
- Предотвращает: потерю общего предела (худший случай $(\text{max\_active\_iter}+1)(N+1)$ проходов).

**Тест D1: `test_simulator_first_step_one_second`**
- Сценарий: путь пользователя — Simulator + адаптер.
- Setup: конфиг 19; `history = [первый интервал с dt = 1 с]`, `dt_integration = 1`, `numerics.max_retries = 0`, `output.log_level = "ERROR"`; `sim.run(init)`.
- Ожидание: без исключения; `hist.states[-1].p[0] / BAR_TO_PA` = 38.38 бар (abs 0.01); двухфазных 98.
- До правки: `RuntimeError` («набор фаз не установился»).
- Предотвращает: расхождение пути адаптера с прямым вызовом `advance` (лимиты из конфига).

Прочие проверки — прогоны, не тесты:
- побитовость 23 конфигов (шаг 4 п. 1);
- регрессия прототипа;
- тесты прототипа и GPN без правки ожидаемых чисел.

Тест «побитово, где ≤ 12 проходов» в pytest не пишется: старого кода после правки нет, а копия в тесте устареет. Это доказывают регрессия (почти побитовое сравнение с эталоном) и отпечатки примеров.

Число тестов: 1932 → 1932 + 10 (A1–A4, B1 ×2, C1–C3, D1).

## 3.4. Критерии завершения

- [ ] A1–A4, C1, C3, D1 — красные до шага 2, зелёные после.
- [ ] B1, C2 — зелёные до и после.
- [ ] GPN: полный прогон 1942 passed (шаг 4 п. 3).
- [ ] Прототип: тесты 101 passed; регрессия полная 17/17 PASS.
- [ ] 23 конфига примеров — отпечатки равны базе `209326d` (шаг 4 п. 1).
- [ ] Первый шаг 19 и 21 сходится при всех $\Delta t$ из §2.1 (шаг 4 п. 2).
- [ ] Тексты (шаг 3) и CHANGELOG с фактическими числами.
- [ ] Vault: заметка debugging, реестр, FEAT-032, P8, json-config-schema, index (шаг 5).
- [ ] Issue #117 прокомментирован (`05-comment-done.md`).
- [ ] Обходов нет: `numerics.max_active_set_iter` в конфигах примеров не задан.

## 4. Связь формула → код

Формулы не меняются. Внешний цикл набора фаз в `problem_statement.tex` не описан: переключения — `sssec:switching_disc`, внутри Ньютона. Ссылок на уравнения в новых комментариях нет; `tests/test_eq_references.py` проверяет только метки.

## 5. Проверка плана

**Раунд 1 — полнота.**
- Файлы: `blackoil.py` (шаг 2), `CHANGELOG_1.0.3.md`, `config.py`, `prototype_adapter.py`, `simulator.py`, `test_simulator.py` (шаг 3), новый тест (шаг 1), vault (шаг 5).
- Проверка есть у каждого шага; зависимости 1 → 2 → 3 → 4 → 5, циклов нет.
- §2.6 адресован: п. 8 — шаг 3; п. 9 — шаги 3, 5; п. 13 — шаг 4.

**Раунд 2 — корректность** (проверено на `6d27358`).
- `_advance_phases` `:580-610`, `_newton_fixed_active_set` `:419`, `pack`/`unpack` `:222-230`, `_cell_measure`/`_cell_weights` `:287-295` — есть.
- `self.grid.n` используется в `:449`.
- `BlackOilNewtonReport` — 4-й позиционный `active_set_iterations` (`:63`).
- `_build` — `test_prototype_cell_tolerance.py:42`.
- `config.py:159`, `prototype_adapter.py:143`, `simulator.py:91-95`, `test_simulator.py:158` — тексты в плане дословно по файлам.

**Раунд 3 — автономность.**
- Пути от корня; команды с каталогами; «почему» — в §2.2, §2.5 и комментарии кода.
- Числа ожиданий — из файлов проб с именами.
- Baseline зафиксирован: 1932 / 1656 / 101 / 11 PASS.
