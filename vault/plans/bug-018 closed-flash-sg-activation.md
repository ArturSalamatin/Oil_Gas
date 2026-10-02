---
tags:
  - план
  - баг
date: 2026-10-02
issue: BUG-018
github: 48
branch: fix/bug-018/closed-flash-sg-activation
status: готов к реализации
---

# BUG-018: начальное приближение $S_g$ «закрытого сосуда» выше $1 - S_{or}$ — ограничить по таблице ОФП

**Реестр:** [[известные баги и технический долг]] → BUG-018. **Issue:** [#48](https://github.com/ArturSalamatin/Oil_Gas/issues/48). **Ветка:** `fix/bug-018/closed-flash-sg-activation` от `numerical_scheme/implementation`.

## Цель

Первый шаг с высоким $R_{s,0}$ и глубокой депрессией перестаёт падать: начальное $S_g$ ячейки, переходящей в двухфазный режим, ограничивается сверху наибольшим узлом таблицы ОФП, где $k_{ro} > 0$. Меняется только стартовая точка Ньютона — уравнения, критерий сходимости и решение прежние. Попутно сообщение адаптера об отказе перестаёт называть непроверенную причину и советовать `max_retries` как единственный выход.

## 0. Решения пользователя (2026-10-02)

| № | Вопрос | Решение |
|---|---|---|
| 1 | Правило границы | **наибольший узел таблицы ОФП, где $k_{ro} > 0$** (нефть ещё подвижна); без свободных констант. Кори на 101 узле, $S_{or} = 0.2$ → 0.79; таблица примера 04 (узлы …, 0.6, 0.8) → 0.6 |
| 2 | Где применять | **во всех ступенях** `advance` — одна правка в `_advance_phases` |
| 3 | Сообщение адаптера | **исправить сейчас**: не называть «обе фазы малоподвижны», не обещать, что поможет `max_retries` |

Отвергнутая альтернатива к решению 1: «первый узел с $k_{ro} = 0$ минус 0.05» — не зависит от шага таблицы, но требует константы. На всех замерах (§2.3) даёт тот же результат.

## 1. Предусловия

- **База:** `numerical_scheme/implementation`, HEAD на момент плана — `4bd1e8c` (после `5a8ef08`: тесты примера 14 исправлены, `RTOL = 1e-12`). **1035 passed** (замер плана с правкой в памяти, 584 с — см. §2.4; без правки пользователь сообщил «тесты зелёные»).
- **Рабочее дерево:** перед созданием ветки `git status --short -uno -- numerical_solver` — пусто. Иначе остановиться и спросить пользователя.
- **Параллельные задачи:** ветка `fix/bug-017/rs0-table-range-check` (worktree) — правит `factory.py`, `io/config.py`, тесты фабрики; `blackoil.py` и `prototype_adapter.py` не трогает (план BUG-017, §5). FEAT-026 — `examples/figure_io.py`. Пересечений по файлам нет.
- **Тесты прототипа** (`HydroSolverPrototype/Prototype_1.0.3/tests`): **70 passed, 10 failed** — до и после правки одинаково; 10 падений — [[DEBT-024]] (нет `xlsxwriter`).
- **Пробы** — `vault/issues/bug-018/probes/` (в `.gitignore`; в коде и README на них не ссылаться). Запуск из `numerical_solver`:

  | скрипт | что даёт |
  |---|---|
  | `which_step_fails.py [ключ=значение]` | номер отказавшего интервала, журнал Ньютона всех ступеней при 1 сут и 169 с |
  | `first_step_trace.py` | один шаг с журналом Ньютона |
  | `cap_initial_sg.py cap=… [save=имя]` | опыт «обрезать $S_g$ начального приближения» — доказательство причины |
  | `compare_solutions.py эталон имя…` | сверка сохранённых решений |
  | `patch_cap.py rule=node cases` / `examples` | **правка плана в памяти**: отказные конфиги 30 сут; 17 примеров — срабатывания и побитовость |
  | `cap_plugin.py` | pytest-плагин: правка на уровне класса для всего прогона; срабатывания — в `cap_plugin_hits.txt` |
  | `plan_impl_plugin.py` + `test_prototype_activation_cap.py` | **код шагов 2–3 и тесты шага 4 до реализации** (с `data/bug018_rs500/config.json`) |
  | `freeze_case.py` | пишет замороженный сценарий `frozen/bug018_rs500/config.json` и числа первого шага |

## 2. Физика и замеры

### 2.1 Причина (установлена опытом)

На шаге прототип (`RadialBlackOilModel._advance_phases`, `blackoil.py:298-316`):
1. решает шаг при всех ячейках однофазных — давление у забоя падает почти до $p_{wf}$;
2. ячейки с $R_s > R_s^{sat}(p) + 10^{-5}$ переводит в двухфазный режим; начальное $S_g$ — «закрытый сосуд»: весь газ, выделившийся при падении давления, остаётся в ячейке,
   $$S_g^{закр} = \frac{d\,B_g}{B_o + d\,B_g},\qquad d = R_{s,0} - R_s^{sat}(p)$$
   (`blackoil.py:312-313`); перетоки за шаг это приближение не учитывает;
3. запускает Ньютон из этого состояния.

При $R_{s,0} = 500$, $p_{wf} = 5$ МПа $S_g^{закр}$ у забоя 0.905–0.912, решение шага — 0.41–0.42. Нефти в начальном приближении меньше остаточной ($S_o < S_{or} = 0.2$). Из области $S_g > 1 - S_{or}$ Ньютон до решения не доходит.

**Доказательство** (`cap_initial_sg.py`, $S_{or} = 0.2$, 5 сут): начальное $S_g$ обрезается сверху значением cap, остальное не меняется.

| cap | $R_{s,0} = 500$, $N = 50$, $k$ = 100 мД, $p_{wf} = 5$ МПа | $R_{s,0} = 150$, $N = 350$, $k$ = 10 мД, $p_{wf} = 3$ МПа |
|---|---|---|
| без ограничения | отказ | отказ |
| 0.85, 0.81 | отказ | — |
| **0.79** | **сходится**, без дробления | — |
| 0.75, 0.50 | сходится, без дробления | сходится, без дробления |

Порог — ровно $1 - S_{or} = 0.80$.

**Почему Ньютон не выходит из этой области** — объяснение, по итерациям не проверенное: при $S_g \ge 1 - S_{or}$ обе ОФП Кори на полках ($k_{ro} = 0$, $k_{rg} = k_{rg}^{max}$), производные потоков по $S_g$ нулевые; на границе — излом $k_{rg}$ (наклон 3.4 → 0). В трассировке третья ступень останавливается на $\max S_g = 0.802$. Для исправления механизм не нужен: опыт показывает, что достаточно не стартовать за границей.

### 2.2 Ограничение не меняет решение

Уравнения $F(z) = 0$ и критерий сходимости ($\|F\|_\infty \le 10^{-11} + 10^{-8}\cdot$масштаб) не меняются — принятое состояние остаётся решением тех же дискретных уравнений. Тот же ли это корень — сверка полей $p$, $S_g$, $R_s$, $T$ на всех записях (`compare_solutions.py`):

| опыт | эталон | сравнение | $\max\lvert\Delta p\rvert$, Па | $\max\lvert\Delta S_g\rvert$ | $\max\lvert\Delta T\rvert$, К |
|---|---|---|---|---|---|
| $R_{s,0} = 500$, $S_{or} = 0.2$, $p_{wf} = 12$ МПа, 5 сут — сходится и без ограничения | без ограничения | cap = 0.5 / 0.3 | $1.5\cdot10^{-8}$ / $7.7\cdot10^{-5}$ | $9\cdot10^{-15}$ / $1.2\cdot10^{-10}$ | $3\cdot10^{-13}$ / $1.6\cdot10^{-10}$ |
| $R_{s,0} = 150$, $S_{or} = 0.05$ (конфиг FEAT-025), 5 сут — сходится и без ограничения | без ограничения | cap = 0.5 / 0.3 | $7.5\cdot10^{-9}$ / $1.9\cdot10^{-4}$ | $4\cdot10^{-15}$ / $6.4\cdot10^{-10}$ | $1.6\cdot10^{-12}$ / $1.6\cdot10^{-10}$ |
| отказной: $R_{s,0} = 500$, $p_{wf} = 5$ МПа, 5 сут | cap = 0.79 | cap = 0.5 / 0.3 / 0.15 | до $2.9\cdot10^{-5}$ | до $7.5\cdot10^{-12}$ | до $1.0\cdot10^{-10}$ |
| отказной, первый шаг ($N = 50$) | cap = 0.79 | cap = 0.5 / 0.3 | $8.2\cdot10^{-7}$ / $6.0\cdot10^{-6}$ | $2.0\cdot10^{-13}$ / $9.9\cdot10^{-13}$ | — |

Единственность корня в общем виде не доказана — показана на этих случаях.

### 2.3 Правка плана в памяти: отказные конфиги (`patch_cap.py rule=node cases`, 30 сут)

| конфиг | граница | срабатываний | вызовов `advance` на 30 интервалов | $T(r_w)$ / $S_g(r_w)$ на 30 сут |
|---|---|---|---|---|
| $R_{s,0} = 500$, $S_{or} = 0.2$, $N = 50$, $k$ = 100 мД, $p_{wf} = 5$ МПа | 0.79 | 7 | 30 (без дробления) | 371.426 К / 0.4223 |
| то же, $p_{wf} = 8$ МПа | 0.79 | 4 | 30 | 373.138 К / 0.4018 |
| $R_{s,0} = 500$, $S_{or} = 0.2$, $N = 350$, $k$ = 30 мД, $p_{wf} = 5$ МПа | 0.79 | 147 | 30 | 371.243 К / 0.4258 |
| $R_{s,0} = 150$, $S_{or} = 0.2$, $N = 350$, $k$ = 10 мД, $p_{wf} = 3$ МПа | 0.79 | 20 | 30 | 396.344 К / 0.3831 |
| $R_{s,0} = 100$, $S_{or} = 0.2$, $N = 350$, $k$ = 10 мД, $p_{wf} = 3$ МПа | 0.79 | 0 | 30 | 397.508 К / 0.3544 |
| $R_{s,0} = 500$, $S_{or} = 0.1$, $N = 50$, $k$ = 100 мД, $p_{wf} = 5$ МПа | 0.89 | 1 | 30 | 371.521 К / 0.4680 |

Все шесть сходятся без дробления; до правки первые четыре и последний не сходились. Правило «узел с $k_{ro} = 0$ минус 0.05» даёт те же $T(r_w)$ и $S_g(r_w)$ до печатаемого знака.

Первый шаг замороженного сценария (`freeze_case.py`; $R_{s,0} = 500$, $S_{or} = 0.2$, $k$ = 100 мД, $p_{wf} = 5$ МПа, одни сутки):

| $N$ | без правки | с правкой | $S_g[0]$ | $p[0]$, МПа | кто решил шаг |
|---|---|---|---|---|---|
| 50 | отказ (512 × 169 с) | 1 подшаг | 0.410017 | 5.925090 | исходный алгоритм (9 итераций Ньютона, 2 обхода active set) |
| 350 | отказ (512 × 169 с) | 1 подшаг | 0.417217 | 5.140841 | третья ступень [[BUG-016]] (16 итераций, 4 обхода) |

При $N = 350$ ограничения мало — шаг решает только третья ступень. Поэтому правка — во всех ступенях (решение 2), иначе при применении только в первой ступени $N = 350$ не сошёлся бы.

### 2.4 Регрессия: правка не меняет ни одного существующего расчёта

`np.minimum(x, cap)` возвращает $x$ побитово при $x \le$ cap. Значит, где ограничение не срабатывает, результат побитово прежний. Замеры:

- **17 примеров** (`patch_cap.py rule=node examples`): срабатываний **0** во всех. Наибольшее $S_g^{закр}$ — 0.6526 у 14 (граница 0.79); у табличных 04, 07–13, 15 — до 0.32 при границе 0.6; у 04a — 0.36 при 0.99.
- **Весь `tests/`** с правкой на уровне класса (`cap_plugin.py`): **1035 passed**, 584 с, срабатываний **0** (`cap_plugin_hits.txt` пуст).
- **Тесты прототипа** с правкой: 70 passed, 10 failed — как без правки; срабатываний 0.

Следствие: числа README всех примеров, пороги `max_retries` README 03/04 и тесты не меняются.

### 2.5 Граница по таблице

Прототип знает ОФП только таблицей (`TabulatedRelPerm`: `sg`, `kro_tab`, `krg_tab`; `relperm.py`). Для `CoreyRP` фабрика табулирует ОФП на 101 узле (`factory.py:225-238`), для табличной ОФП берёт CSV как есть.

- граница = `sg[j - 1]`, где `j` — первый узел с `kro_tab <= 0`;
- нет узла с $k_{ro} = 0$ → ограничения нет (`None`);
- $k_{ro} = 0$ уже в первом узле (`j = 0`) → ограничения нет: нефть неподвижна всегда, граница не определена.

Значения на конфигах проекта: Кори $S_{or} = 0.2$ → 0.79; $S_{or} = 0.1$ → 0.89; таблица примеров 04, 07–13, 15 → 0.6; 04a → 0.99.

### 2.6 Сообщение адаптера

Сейчас (`prototype_adapter.py:134-143`) при отказе после всех удвоений:

```
HydroSolver не сошёлся после 512 подшагов (dt_sub=1.69e+02 s). Увеличьте numerics.max_retries
(сейчас 9). Более мелкие подшаги требуются при корреляционном PVT (нелинейность B_g) и при
высокой газонасыщенности (обе фазы малоподвижны одновременно).
```

Совет верен, когда отказ вызван величиной шага ([[DEBT-007]]: README 03 и 10 приводят пороги `max_retries`), и неверен, когда шаг не сходится при любом дроблении (BUG-018 до исправления, [[BUG-017]], [[BUG-019]]). Причину адаптер не диагностирует. Новый текст сообщает факты — шаг, подшаги, время, число двухфазных ячеек, $\max S_g$ — и оба исхода дробления, без догадки о причине. Начало «HydroSolver не сошёлся после N подшагов» сохраняется: его цитируют README 03 (строка 416), 06 (105), 07 (133), 10 (105). Тестов на текст сообщения сейчас нет (`grep "raises(RuntimeError" tests/` — только без `match`).

## 3. Затронутые файлы

| файл | что | строки (на `4bd1e8c`) |
|---|---|---|
| `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` | докстринг модуля; функция `_sg_activation_cap`; атрибут `sg_activation_cap` в `__init__`; ограничение в `_advance_phases` | 1-9, перед 30 (после `BlackOilNewtonReport`), 53, 312-313 |
| `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py` | текст `RuntimeError` и комментарий над ним | 134-143 |
| `numerical_solver/tests/test_prototype_activation_cap.py` | **новый** — 10 тестов | — |
| `numerical_solver/tests/data/bug018_rs500/config.json` | **новый** — замороженный сценарий | — |
| `vault/roadmap/известные баги и технический долг.md`, `vault/00-home/index.md`, issue #48 | шаг 7 | |

Не меняются: `factory.py`, `pvt/relperm.py` (`CoreyRP`), примеры и их README, прочие тесты.

## 4. Варианты

| вариант | суть | + | − |
|---|---|---|---|
| **1. Ограничение $S_g$ активации по таблице ОФП, во всех ступенях (принят)** | `_advance_phases`: `min(S_g^закр, cap)` | устраняет причину; одна правка; доказано опытом; 17 примеров побитово | граница зависит от шага таблицы (решение 1) |
| 2. То же только в запасном пути и третьей ступени | флаг, как у BUG-014/016 | — | лишний флаг; побитовость и так сохраняется (§2.4); $N = 50$ решался бы позже |
| 3. Гашение цикла active set | не переключать ячейку повторно за шаг | убирает зацикливание при 169 с | при варианте 1 до 169 с не доходит; меняет логику прототипа |
| 4. Лимит итераций Ньютона 15 → 25–30 в третьей ступени | — | тривиально | причину не устраняет: при крупном шаге Ньютон стоит на границе при любом лимите |
| 5. Передать $S_{or}$ из `CoreyRP` в прототип | точная $1 - S_{or}$ | не зависит от табуляции | у табличной ОФП $S_{or}$ нет; новый интерфейс фабрика → прототип |

## 5. Подводные камни

- ✅ **Побочные эффекты:** `_advance_phases` вызывают `advance` и `_fallback` (все ступени) — это и нужно; срабатываний на существующих расчётах 0 (§2.4).
- ✅ **Граничные случаи таблицы:** нет узла с $k_{ro} = 0$; $k_{ro} = 0$ в первом узле; пустая таблица / объект без `sg`, `kro_tab` (через `getattr`) — `None`, правка отключена. Тесты A.2–A.4.
- ✅ **Граница ниже $S_{gc}$:** только если $k_{ro} = 0$ начинается ниже порога подвижности газа — у реальных ОФП не бывает ($S_{gc} < 1 - S_{or}$). Опыт с cap = 0.15 < $S_{gc}$ дал то же решение (§2.2).
- ✅ **Нижняя граница `1e-8`** у $S_g^{закр}$ сохраняется: ограничение сверху применяется после неё.
- ✅ **Решение не меняется** — §2.2, тест B.4.
- ⚠️ **Тест-воспроизводитель может «протухнуть»:** если прототип изменится и сценарий начнёт сходиться и без ограничения, тест B.2 (`test_without_cap_fails`) упадёт — это сигнал заменить сценарий, а не ослабить тест (комментарий в тесте).
- ⚠️ **BUG-019 не исправляется:** пример 20 при $k$ = 10 мД падает на вторых сутках по другой причине (активаций нет). После правки сообщение об этом отказе станет честнее, но сам отказ останется.
- ✅ **Производительность:** одно `np.minimum` на активацию — ничтожно.
- ✅ **Import-цепочки:** новая функция в модуле `blackoil.py`, импорт в тесте `from radial_blackoil.blackoil import _sg_activation_cap`.
- ✅ **Соответствие постановке:** уравнения не меняются; `problem_statement.tex` не затрагивается.
- 🔵 **Связь с FEAT-025:** после вливания примеры 19–21 могут вернуть $S_{or} = 0.2$ вместо обхода 0.05 — это решение FEAT-025 (числа его плана тогда перемерить), в эту задачу не входит.

## 6. Шаги реализации

### Шаг 1: Подготовка

```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas
git status --short -uno -- numerical_solver          # пусто, иначе стоп и вопрос пользователю
git checkout numerical_scheme/implementation
git log -1 --oneline                                 # записать HEAD
git checkout -b fix/bug-018/closed-flash-sg-activation
cd numerical_solver
.venv\Scripts\python -m pytest tests/ -q                                      # baseline: ожидание 1035 passed
.venv\Scripts\python -m pytest HydroSolverPrototype/Prototype_1.0.3/tests -q  # ожидание 70 passed, 10 failed (DEBT-024)
```

Воспроизведение бага (до правки):

```powershell
.venv\Scripts\python ..\vault\issues\bug-018\probes\freeze_case.py
```

Ожидание: «N = 50, без правки: ОТКАЗ», «N = 350, без правки: ОТКАЗ».

### Шаг 2: Ограничение в прототипе

**Файл:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (прототип править разрешено; стиль файла — английские комментарии, плотный код).

**2.1. Докстринг модуля** (строки 6-8), было:

```python
Local changes (GPN project, BUG-014): when the original step fails, advance()
retries with the BHP well branch as an outer active constraint and no lower
bound on Sg of two-phase cells.
"""
```

стало:

```python
Local changes (GPN project, BUG-014): when the original step fails, advance()
retries with the BHP well branch as an outer active constraint and no lower
bound on Sg of two-phase cells.
BUG-018: the closed-flash Sg guess of a cell switching to two-phase is capped
at the largest relperm-table Sg where kro > 0 (sg_activation_cap).
"""
```

**2.2. Функция** — после класса `BlackOilNewtonReport`, перед `class RadialBlackOilModel:` (строка 30):

```python
def _sg_activation_cap(relperm):
    """BUG-018: upper bound of the closed-flash Sg guess -- the largest Sg node of
    the relperm table where kro > 0 (oil still mobile).  None when kro never
    reaches zero or is zero from the first node: then no cap applies."""
    sg=np.asarray(getattr(relperm,'sg',()),float); kro=np.asarray(getattr(relperm,'kro_tab',()),float)
    zero=np.flatnonzero(kro<=0.0)
    if sg.size==0 or zero.size==0 or zero[0]==0: return None
    return float(sg[zero[0]-1])
```

**2.3. Атрибут** — в `__init__` после строки 53 (`self._line_search_l2=False; self._sg_step_max=None`):

```python
        # BUG-018: a cell switching to two-phase starts Newton from the closed-
        # flash Sg (all released gas stays in the cell).  With high Rs0 and a deep
        # drawdown it exceeds 1 - S_or (0.91 at Rs0 = 500, p_wf = 5 MPa against
        # 0.41 in the solution) and Newton never gets back below the kro = 0
        # plateau; the cap only moves the starting point, the equations and the
        # converged state are unchanged (plan BUG-018, 2.2).
        self.sg_activation_cap=_sg_activation_cap(relperm)
```

**2.4. Ограничение** — `_advance_phases`, строки 311-313, было:

```python
            if np.any(activate):
                pa=guess.pressure_bar[activate]; rtot=guess.rs_sm3_sm3[activate].copy(); rsat=self.pvt.rs_sat(pa); bo=self.pvt.bo(pa,rsat); bg=self.pvt.bg(pa); d=np.maximum(rtot-rsat,0.0)
                guess.sg[activate]=np.maximum(d*bg/(bo+d*bg),1e-8); guess.rs_sm3_sm3[activate]=rsat
```

стало:

```python
            if np.any(activate):
                pa=guess.pressure_bar[activate]; rtot=guess.rs_sm3_sm3[activate].copy(); rsat=self.pvt.rs_sat(pa); bo=self.pvt.bo(pa,rsat); bg=self.pvt.bg(pa); d=np.maximum(rtot-rsat,0.0)
                sg0=np.maximum(d*bg/(bo+d*bg),1e-8)
                # BUG-018: keep the guess where oil is still mobile; np.minimum
                # returns sg0 bitwise wherever it is below the cap
                if self.sg_activation_cap is not None: sg0=np.minimum(sg0,self.sg_activation_cap)
                guess.sg[activate]=sg0; guess.rs_sm3_sm3[activate]=rsat
```

**Проверка** (`cap=nan` — проба ничего не подставляет, работает код из файла):

```powershell
.venv\Scripts\python ..\vault\issues\bug-018\probes\cap_initial_sg.py cap=nan ex=20 S_or=0.2 N=50 k=1e-13 days=1
.venv\Scripts\python -m pytest tests/test_prototype_globalization.py tests/test_prototype_well_branch.py -q
```

Ожидание: «СОШЁЛСЯ, вызовов advance 1 на 1 интервалов, …» (до правки — «ОТКАЗ»); тесты ступеней `advance` зелёные.

### Шаг 3: Сообщение адаптера

**Файл:** `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`, строки 134-143, было:

```python
        # Подсказка называет обе известные первопричины (DEBT-007, BUG-003).
        # Про dt_integration намеренно не пишем: при высокой Sg уменьшение dt
        # не помогает — A-retry уже дробит шаг внутри с тем же лимитом.
        raise RuntimeError(
            f"HydroSolver не сошёлся после {2**self._max_retries} подшагов "
            f"(dt_sub={dt / 2**self._max_retries:.2e} s). "
            f"Увеличьте numerics.max_retries (сейчас {self._max_retries}). "
            f"Более мелкие подшаги требуются при корреляционном PVT "
            f"(нелинейность B_g) и при высокой газонасыщенности "
            f"(обе фазы малоподвижны одновременно).")
```

стало:

```python
        # Сообщение — факты, а не догадка о причине. Отказ бывает из-за
        # величины шага (DEBT-007: тогда помогает дробление глубже) и при любом
        # шаге (BUG-017, BUG-018 до исправления, BUG-019) — адаптер их не
        # различает. Начало «HydroSolver не сошёлся после N подшагов» цитируют
        # README примеров 03, 06, 07, 10 — не менять. Про dt_integration не
        # пишем: A-retry уже дробит шаг внутри с тем же лимитом.
        n_two = int(np.count_nonzero(state.regime == 1))
        raise RuntimeError(
            f"HydroSolver не сошёлся после {2**self._max_retries} подшагов "
            f"(dt_sub={dt / 2**self._max_retries:.2e} s) на шаге с "
            f"t = {state.t / DAY_TO_S:.4f} сут: двухфазных ячеек {n_two} из "
            f"{state.p.size}, max S_g = {float(np.max(state.Sg)):.3f}. "
            f"Если отказ вызван величиной шага, поможет больший "
            f"numerics.max_retries (сейчас {self._max_retries}, допустимо "
            f"до 20); если шаг не сходится и при мелких подшагах, причина "
            f"не в его величине.")
```

`np` и `DAY_TO_S` уже импортированы (строки 23, 30). `state` — входное состояние интервала (`solve(self, state, dt, bc)`, строка 51), у `SimulationState` есть `t`, `regime`, `Sg`, `p`.

### Шаг 4: Тесты

**4.1.** Создать `numerical_solver/tests/data/bug018_rs500/config.json` — скопировать `vault/issues/bug-018/probes/frozen/bug018_rs500/config.json` без изменений (`Copy-Item`). Содержимое — генератор FEAT-025 (`make_configs.build("20", …, S_or=0.2, N=50, k=1e-13, days=1, log=INFO)`): PVT `standing` (800 / 1.014), Кори $S_{gc} = 0.1$, $S_{or} = 0.2$, $n_o = 2$, $n_g = 3$, $k_{rg}^{max} = 0.8$; $T_0 = 380$ К, $R_{s,0} = 500$, $p_0 = 46.9$ МПа; одна история 86 400 с при $p_{wf} = 5$ МПа; `max_retries = 9`.

**4.2.** Создать `numerical_solver/tests/test_prototype_activation_cap.py` — скопировать `vault/issues/bug-018/probes/test_prototype_activation_cap.py` без изменений. Состав (10 тестов):

| тест | что проверяет | ожидание (замер плана) |
|---|---|---|
| A.1 `test_corey_table_101_nodes` | граница модели на замороженном сценарии | 0.79 |
| A.2 `test_coarse_table` | таблица с узлами 0.6, 0.8 | 0.6 |
| A.3 `test_no_immobile_oil_no_cap` | $k_{ro} > 0$ везде | `None` |
| A.4 `test_oil_immobile_from_first_node_no_cap` | $k_{ro} = 0$ с первого узла | `None` |
| B.1 `test_first_step_converges[50]` | первые сутки одним шагом | `n_substeps = 1`, $S_g[0] = 0.410017 \pm 10^{-5}$, $p[0] = 5.925090$ МПа ± 100 Па |
| B.1 `test_first_step_converges[350]` | то же на $N = 350$ | 0.417217, 5.140841 МПа |
| B.2 `test_without_cap_fails` | `sg_activation_cap = None`, `max_retries = 0` | `RuntimeError` — сценарий воспроизводит баг |
| B.3 `test_guess_capped` | старт Ньютона по двухфазным ячейкам | $\max \le$ границы и $=$ границе |
| B.4 `test_solution_independent_of_cap` | граница 0.79 против 0.3 | $\max|\Delta p| < 10^{-3}$ Па, $\max|\Delta S_g| < 10^{-9}$, $\max|\Delta R_s| < 10^{-7}$ (замер $6\cdot10^{-6}$, $10^{-12}$, $7.5\cdot10^{-11}$) |
| C `test_failure_message_reports_state_not_guess` | текст `RuntimeError` при всегда отказывающем `advance`, `max_retries = 1` | начинается с «HydroSolver не сошёлся после 2 подшагов», содержит «t = 0.0000 сут», «двухфазных ячеек 0 из 50», не содержит «малоподвижны» |

Все 10 тестов проверены до реализации: `plan_impl_plugin.py` подставляет в память код шагов 2 и 3 (функцию, атрибут, ограничение и тот же f-string сообщения) — **10 passed** за 2.2 с. Команда: `$env:PYTHONPATH = "..\vault\issues\bug-018\probes"; .venv\Scripts\python -m pytest ..\vault\issues\bug-018\probes\test_prototype_activation_cap.py -p plan_impl_plugin -v`. Пример нового текста (тот же сценарий без ограничения, `max_retries = 0`):

```
HydroSolver не сошёлся после 1 подшагов (dt_sub=8.64e+04 s) на шаге с t = 0.0000 сут: двухфазных
ячеек 0 из 50, max S_g = 0.000. Если отказ вызван величиной шага, поможет больший
numerics.max_retries (сейчас 0, допустимо до 20); если шаг не сходится и при мелких подшагах,
причина не в его величине.
```

(«после 1 подшагов» при `max_retries = 0` — несогласование числительного, было и раньше; префикс не трогаем из-за цитат в README.)

**Проверка:**

```powershell
.venv\Scripts\python -m pytest tests/test_prototype_activation_cap.py -v       # 10 passed
```

### Шаг 5: Регрессия

```powershell
.venv\Scripts\python -m pytest tests/ -q                                       # 1035 + 10 = 1045 passed
.venv\Scripts\python -m pytest HydroSolverPrototype/Prototype_1.0.3/tests -q   # 70 passed, 10 failed — те же
```

Побитовость 17 примеров — по построению (§2.4); дополнительно `examples\run_all.py` не обязателен: тесты примеров сверяют числа README.

### Шаг 6: Проверка на отказных конфигах

```powershell
.venv\Scripts\python ..\vault\issues\bug-018\probes\cap_initial_sg.py cap=nan ex=20 S_or=0.2 N=50 k=1e-13 days=30
.venv\Scripts\python ..\vault\issues\bug-018\probes\cap_initial_sg.py cap=nan ex=19 S_or=0.2 days=30
```

`cap=nan` — проба ничего не подставляет, работает код из файла. Ожидание: «СОШЁЛСЯ, вызовов advance 30 на 30 интервалов»; на 30 сут $T(r_w) = 371.426$ К / $S_g(r_w) = 0.4223$ (20) и 396.344 К / 0.3831 (19) — как в §2.3.

### Шаг 7: Vault и issue

1. Реестр, BUG-018: «Результат» (тестов 1035 → 1045, время; числа шагов 5–6), «Отклонения от плана», статус ✅ ИСПРАВЛЕНО <дата>.
2. Реестр, [[BUG-019]]: в «Файл»/«Симптом» — новое сообщение адаптера (текст после шага 3).
3. `vault/00-home/index.md` — строка плана: «Реализовано <дата>».
4. Комментарий в #48: `vault/issues/bug-018/05-comment-done.md`.
5. Коммиты (`/implement`): код + тесты + данные — `fix:`; vault — отдельно `vault:`.

## 7. Тестовая стратегия

| категория | тест | предотвращает |
|---|---|---|
| Unit | A.1–A.4 | неверную границу по таблице; ограничение там, где оно не определено |
| Воспроизводитель | B.2 | «протухание» сценария: если он начнёт сходиться и без ограничения, тест покажет |
| Интеграционный | B.1 ($N$ = 50, 350) | возврат отказа первого шага; дробление шага |
| Инвариант | B.3 | неприменённое или превышенное ограничение |
| Инвариант | B.4 | ограничение, меняющее решение, а не стартовую точку |
| Сообщение | C | возврат догадки о причине в текст ошибки; потерю префикса, который цитируют README |
| Регрессия | весь `tests/`, тесты прототипа | изменение существующих расчётов (по замеру — срабатываний 0) |

## 8. Критерии завершения

- [ ] `test_prototype_activation_cap.py` — 10 passed.
- [ ] `tests/` — 1045 passed; тесты прототипа — 70 passed, 10 failed (те же).
- [ ] Отказные конфиги шага 6 сходятся без дробления, числа §2.3.
- [ ] Реестр (BUG-018, BUG-019), индекс vault, комментарий в #48.

## 9. Новые проблемы

Новых нет. Известные и не входящие в задачу: [[BUG-019]] (отказ на вторых сутках при 10 мД — другой механизм), зацикливание active set при мелком шаге из далёкого начального приближения (§4, вариант 3) — после правки не наблюдается, отдельной записи не требует.

## 10. Как начать работу по этому плану

1. Прочитать этот файл и запись BUG-018 в реестре.
2. Шаг 1: чистое дерево, зелёная база, ветка `fix/bug-018/closed-flash-sg-activation`.
3. Venv — `numerical_solver\.venv\Scripts\python` напрямую.
4. Шаги 2 → 3 → 4 → 5 → 6 → 7; после шагов 2, 3, 4 — `pytest tests/test_prototype_activation_cap.py` и `tests/test_prototype_globalization.py`.

## Связанные заметки

- [[известные баги и технический долг]] — BUG-018, BUG-019, BUG-016, BUG-014, DEBT-007, DEBT-024
- [[bug-016 newton-line-search-norm]] — третья ступень `advance`
- [[feat-025 standing-corey-cooling-examples]] — обход $S_{or} = 0.05$
