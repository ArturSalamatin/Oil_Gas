---
tags:
  - план
  - рефакторинг
date: 2026-10-03
issue: DEBT-033
github: 52
branch: refactor/debt-033/vectorize-grouped-jacobian
status: реализован
audit:
  date: 2026-10-03
  found: 7
  auto-fixed: 7
  manual-required: 0
---

# DEBT-033: векторизация группового якобиана прототипа — план

## Кратко

Конечно-разностный якобиан прототипа гидродинамики (`radial_blackoil/blackoil.py`) занимает 72–81 % времени расчёта примеров. При $N = 350$ половина всего времени уходит не на вычисление невязок, а на учёт вокруг них: цикл Python по ячейкам при раскраске столбцов и перевод плотной матрицы $2N \times 2N$ в разреженную. План убирает этот учёт, **не меняя численного метода**: те же шаги возмущения, те же вычисления невязки в том же порядке, те же элементы $\Delta F / h$. Якобиан собирается сразу в разреженном виде — CSC (сжатые столбцы, `scipy.sparse.csc_matrix`; этот формат принимает разреженный LU-решатель SuperLU, `splu`) — и побитово равен прежнему; шаги Ньютона, истории примеров и регрессия прототипа — побитово прежние.

- Подтип: рефакторинг (ускорение без изменения поведения).
- Шагов: 6 (подготовка, шаги возмущения, разреженный якобиан, документация, верификация, vault).
- Код: ~45 строк в `blackoil.py`, ~45 строк тестов прототипа.
- **Код шагов 2–3 проверен при планировании** подменой методов в памяти (проба `planned_code_check.py`, вывод — `.txt`): тесты плана проходят, истории пяти примеров побитово равны исходному коду. Ускорение (замер): пример 20 ($N = 350$) — 15.90 → 6.60 с (×2.41), 14 ($N = 350$, таблица) — 63.88 → 43.91 с (×1.45); на $N = 50$ выигрыша нет: 04 — ×0.98, 15 — ×1.12, 13b — ×1.09 (учёт там и так мал, основное — невязки).

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай: запись DEBT-033 в `vault/roadmap/известные баги и технический долг.md`, issue #52 (`gh issue view 52 --repo ArturSalamatin/Oil_Gas`), `vault/knowledge/decisions/hydro-prototype-анализ.md` (§6 «Якобиан»).
3. Ветка от базовой `numerical_scheme/implementation` (проверка: `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`): `git checkout -b refactor/debt-033/vectorize-grouped-jacobian` (или worktree `.worktrees/debt-033` — так делает `/implement`).
4. Venv: `numerical_solver\.venv\Scripts\python` основного каталога (в worktree своего `.venv` может не быть — тогда полный путь `d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python`).
5. Baseline (до правок, шаг 1 расписывает подробно):
   - из `numerical_solver`: `.venv\Scripts\python -m pytest tests/ --collect-only -q` → **1210**; `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` → **987 passed** (~73 с);
   - из `numerical_solver\HydroSolverPrototype\Prototype_1.0.3`: `..\..\.venv\Scripts\python -m pytest tests -q` → **80 passed**; `..\..\.venv\Scripts\python regression\run_regression.py --quick` → **11/11 PASS** (~8 мин);
   - снимок историй примеров `save base` и замер времени (шаг 1).
6. Запомни числа тестов, время быстрого уровня и замер — это baseline.
7. Начни с шага 1. После каждого шага: тест шага и регресс по полю «Регресс»; полный прогон `tests/` — в конце (`/implement` §3.1).

⚠️ **Пробы лежат только в основном каталоге.** `vault/issues/` — в `.gitignore`, в worktree каталога `vault/issues/debt-033/probes/` нет. Пробы запускаются по абсолютному пути основного каталога **из каталога `numerical_solver` того дерева, чей код проверяется**: они берут код из каталога запуска (`Path.cwd()`) и первой строкой печатают `код: <путь radial_blackoil> | <путь gpn_multiphase_solver>`. Если в строке не путь worktree — замер и сравнение недействительны.

```powershell
# из <дерево>\numerical_solver
$P = "d:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\debt-033\probes"
d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python $P\time_jacobian.py 20_rs300_cooling 14_high_gor_cooling 03_standing_corey 04_table_table
d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python $P\history_snapshot.py save base
```

## Контекст для читателя без контекста

### Что такое прототип и где якобиан

Гидродинамику (давление $p$, насыщенность $S_g$, газосодержание $R_s$) решает прототип `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/` (код коллеги, «Sergey solver»; править разрешено). Неявный шаг — метод Ньютона по $2N$ неизвестным: на ячейку $p$ и $X$, где $X = S_g$ в двухфазной ячейке и $X = R_s$ в однофазной. Вектор $z = [p_0 \dots p_{N-1}, X_0 \dots X_{N-1}]$, невязка $F(z)$ — баланс нефтяного и газового компонентов по ячейкам (`residual`, `blackoil.py:177-178`; строки газа делятся на `gas_residual_scale`).

На каждой итерации Ньютона (`_newton_fixed_active_set`, `blackoil.py:236-259`) строится якобиан `finite_difference_jacobian` (`:217-218`, `:242`) и решается система `_linear_solve` (`:219-221`, `:244`).

### Раскраска столбцов (метод Кертиса — Пауэлла — Рида, 1974)

Столбец $j$ якобиана — реакция всех невязок на возмущение одной неизвестной: $J_{:,j} = (F(z + h_j e_j) - F(z))/h_j$. Невязки ячейки $i$ зависят только от ячеек $i-1, i, i+1$ (трёхточечный шаблон: потоки через две грани ячейки, выбор ячейки выше по потоку — из пары соседей). Возмущение ячейки $i$ меняет строки $i-1 \dots i+1$, возмущение ячейки $i+3$ — строки $i+2 \dots i+4$: наборы не пересекаются. Значит, ячейки $i, i+3, i+6, \dots$ («цвет» $i \bmod 3$) возмущаются одновременно, невязка считается один раз, а изменения раскладываются по своим столбцам. $p$ и $X$ одной ячейки меняют одни и те же строки и в один цвет не совмещаются: 2 блока × 3 цвета = **6 вычислений невязки** на якобиан (+ базовое $F(z)$), вместо $2N$ у поколонного режима `reference`.

### Что медленно сейчас

`finite_difference_jacobian_grouped` (`blackoil.py:204-216`):

```python
    def finite_difference_jacobian_grouped(self,z,state_old,dt_s,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
        z=np.asarray(z,float); f0=self.residual(z,state_old,dt_s,gas_active); n=self.grid.n; J=np.zeros((2*n,2*n),float)
        for block in (0,1):
            for color in range(3):
                zp=z.copy(); cols=[]
                for i in range(color,n,3):
                    j=i if block==0 else n+i
                    h=self._pressure_fd_step(z[j],bool(gas_active[i]),p_rel_step,p_abs_step) if block==0 else (sg_abs_step if gas_active[i] else max(rs_abs_step,1e-6*max(abs(z[j]),1.0)))
                    zp[j]+=h; cols.append((i,j,h))
                df=self.residual(zp,state_old,dt_s,gas_active)-f0
                for i,j,h in cols:
                    rows=np.arange(max(0,i-1),min(n,i+2)); J[rows,j]=df[rows]/h; J[n+rows,j]=df[n+rows]/h
        return J,f0
```

Шесть вычислений невязки векторизованы, учёт вокруг них — нет: два цикла Python по ячейкам на каждый цвет (шаг `_pressure_fd_step` по скаляру с `np.searchsorted`, `np.arange`, запись строк в плотную матрицу) — $4N$ итераций на якобиан. Затем `_linear_solve` (`:219-221`) делает `splu(csc_matrix(J))`: `csc_matrix` от плотной матрицы просматривает все $4N^2$ элементов.

### Замер baseline (2026-10-03, HEAD `a342a85`, без профилировщика)

Проба `time_jacobian.py` (обёртки `perf_counter` вокруг методов в памяти):

| пример | $N$ | PVT | всего | якобиан | невязки в якобиане | учёт раскраски | перевод в разреженную | якобианов |
|---|---|---|---|---|---|---|---|---|
| 20_rs300_cooling | 350 | Стендинг | 15.57 с | 11.92 с (77 %) | 3.98 с | **7.94 с (51 %)** | 1.57 с (10 %) | 604 |
| 14_high_gor_cooling | 350 | таблица | 62.61 с | 50.54 с (81 %) | 32.54 с | **18.01 с (29 %)** | 2.96 с (5 %) | 1335 |
| 03_standing_corey | 150 | Стендинг | 1.13 с | 0.86 с (76 %) | 0.39 с | 0.47 с (42 %) | 0.02 с | 100 |
| 04_table_table | 50 | таблица | 1.34 с | 0.96 с (72 %) | 0.77 с | 0.19 с (14 %) | 0.01 с | 111 |

«Учёт раскраски» = время якобиана минус время невязок внутри него. Ожидание после правки: учёт + перевод ≈ 0.3–0.5 мс на якобиан (≈ 0.3 с на пример 20 вместо 9.5 с).

⚠️ Пример 20 после DEBT-034 — `20_rs300_cooling` ($R_{s,0} = 300$, $k$ = 10 мД, 604 якобиана). Таблица в записи реестра и в issue #52 снята на `00af963` для прежнего `20_rs500_cooling` — верна для того коммита; baseline этого плана — таблица выше.

### Проверено при планировании (пробы в `vault/issues/debt-033/probes/`)

1. **`grouped` побитово равен `reference`.** `grouped_vs_reference.py` (вывод — `grouped_vs_reference.txt`): 488 состояний Ньютона пяти примеров — 04 (таблица, $N = 50$), 20 и 14 ($N = 350$), 15 (управление по дебиту), 13b (ветви скважины open и shut); в том числе 114 состояний третьей ступени `advance` (BUG-016). `np.array_equal(Jg, Jr)` — **488/488**. Причина: невязка строки $k$ при возмущении нескольких ячеек одного цвета вычисляется той же арифметикой, что при возмущении одной — соседи по шаблону не возмущены. Следствие: побитовый эталон для нового кода — режим `reference`, замороженная копия старого цикла не нужна.
2. **Разреженная сборка полосы = `csc_matrix(dense)`.** Сборка `coo_matrix((значения, (строки, столбцы))).tocsc()` + `eliminate_zeros()` из трёх диагоналей четырёх блоков даёт те же `indptr`, `indices`, `data`, что `csc_matrix(J)` от плотной матрицы — **488/488** (scipy 1.18.1, numpy 2.5.2). SuperLU получает тот же вход → тот же шаг Ньютона.
3. **Вне полосы плотная $J$ — нули** (`np.count_nonzero(Jg) == csc_matrix(Jg).nnz` на всех 488 состояниях) — раскраска не теряет связей.
4. **В полосе есть точные нули.** На фикстуре `Nabor_1b` при $N = 7$: ненулевых 45–48 из 76 мест полосы $4(3N-2)$ (нули — элементы ниже по потоку, $\partial k_{rg}/\partial S_g = 0$ при $S_g$ ниже $S_{gc}$). Без `eliminate_zeros()` шаблон разреженности другой.
5. **Тесты плана выполнимы** на фикстурах прототипа: на трёх состояниях (`Nabor_1b`, $N = 7$) `grouped == reference` побитово; `advance` при $\Delta t$ = 60 и 3600 с с переключениями фаз (2 и 3) — состояние и число итераций побитово равны у `grouped` и `reference`.
6. **Детерминизм.** `history_snapshot.py`: два прогона одного кода (примеры 04, 15) — истории побитово равны. Побитовый критерий приёмки применим.
7. **Настройки.** Все 17 входов регрессии прототипа и все примеры GPN (`numerics.jacobian_mode = "grouped"`, `linear_solver = "sparse"` по умолчанию, `io/config.py:147-148`) идут ровно по изменяемому пути. `linear_solver='dense'` используется только в тесте `test_sparse_dense_same_step`.
8. **Код плана работает.** `planned_code_check.py` подменяет `_fd_steps`, `finite_difference_jacobian_grouped`, `_linear_solve` кодом шагов 2–3 дословно и выполняет: утверждения трёх новых тестов (в `test_fd_steps_equal_scalar_rule` — 70 давлений, 20 отрицательных шагов у узлов), `test_sparse_dense_same_step` с разреженной $J$ в плотном пути — всё OK; истории примеров 04, 15, 13b, 20, 14 исходным и новым кодом в одном процессе — **побитово**; время — в «Кратко».
9. **Аудит (2026-10-03, `b054acc`): код и тесты взяты из файла плана дословно** (`audit_plan_literal.py`): блоки «До» совпадают с `blackoil.py:194-198`, `:204-216`, `:217-221`; с подменой кода шагов 2–3 тесты прототипа — 76 passed (без `test_grouped_jacobian.py`) + 7 passed в `test_grouped_jacobian.py` по плану (2 правки `.toarray()`, 3 новых теста) = **83**; быстрый уровень `numerical_solver` — **987 passed**. Пробы в worktree берут код дерева запуска: editable-установка `gpn_multiphase_solver` ставит свой поиск модулей в конец `sys.meta_path`, `sys.path[0]` пробы проверяется раньше.

### Решение об аналитическом якобиане (не входит)

Обсуждено 2026-10-03 (issue #52, вариант 4). Точность конечных разностей (~$10^{-6}$ относительной) сходимость не ограничивает; BUG-019 проверил это тестом Тейлора: якобиан согласован с невязкой (поэлементно ≤ 5.8e-5), невязка гладкая вдоль направления Ньютона ($e \propto \varepsilon$ на 5 декадах). На табличном PVT невязки — основная часть якобиана (пример 14: 32.5 из 50.5 с), но их стоимость — цикл интерполяции PVTO, это отдельная задача (см. «Обнаруженные проблемы»).

## Текущее состояние (baseline)

- Тесты `numerical_solver/tests/`: 1210 (быстрый уровень — 987, ~73 с) на `b054acc` (аудит 2026-10-03; после планирования влит FEAT-028, +9 тестов), база зелёная (правило мёржа).
- Тесты прототипа: 80 passed (37 с). Регрессия: `--quick` — **11/11 PASS на `b054acc`** (аудит 2026-10-03, ~8 мин); полная — 17/17 PASS против переснятого `regression/golden/` по записи DEBT-029. Последняя правка `radial_blackoil/` — `408c77e` (BUG-018); эталон переснят в `373bcd3`.
- API: `finite_difference_jacobian_grouped(z, state_old, dt_s, gas_active, ...) -> (np.ndarray (2n, 2n), f0)`; `finite_difference_jacobian` — диспетчер по `jacobian_mode`; единственный потребитель матрицы — `_linear_solve` в `_newton_fixed_active_set`.

## Целевое состояние

- `_fd_steps(z, gas_active, ...)` — новый метод: шаги всех $2N$ неизвестных одним массивом, поэлементно та же арифметика, что `_pressure_fd_step` и правило шага по $R_s$/$S_g$.
- `finite_difference_jacobian_grouped` — без циклов по ячейкам; возвращает `scipy.sparse.csc_matrix` (был `np.ndarray`), побитово равную `csc_matrix(reference)`.
- `_linear_solve` — принимает разреженную и плотную $J$.
- `finite_difference_jacobian_reference`, `_pressure_fd_step`, невязка, Ньютон, набор фаз — без изменений.
- Import graph: в `blackoil.py` добавляются `coo_matrix`, `issparse` из `scipy.sparse` (зависимость уже есть).

## Варианты и выбор

Подробно — issue #52. Кратко:

| вариант | суть | итог |
|---|---|---|
| 1 | векторизация учёта, плотная матрица остаётся | снимает учёт, остаётся $O(N^2)$ перевода и памяти (при $N = 2000$ — 128 МБ на итерацию) |
| **2** | **1 + сборка сразу в CSC** | **выбран**: $O(N)$ по времени и памяти; меняется тип результата `grouped` — правка двух тестов прототипа |
| 3 | 1 + быстрый перевод внутри `_linear_solve` | половинчатый: плотная матрица остаётся, шаблон описан в двух местах |
| 4 | аналитический якобиан | не входит (см. выше) |
| 5 | JIT (numba) | новая зависимость ради цикла, который векторизуется numpy |
| 6 | `scipy.optimize._numdiff.approx_derivative(..., sparsity=(шаблон, группы))` — готовая раскраска CPR в scipy | отвергнут: закрытый API (`_numdiff`); свои правила шага — без одностороннего шага у узлов PVTO (`_pressure_fd_step`, исправление T05) и без правил $h$ прототипа → якобиан не побитово прежний, регрессия FAIL |

Отличие от issue: там вариант 2 шёл двумя шагами (сначала плотная векторизация, потом CSC). Здесь — один шаг: побитовый эталон — режим `reference` (проверено, п. 1–2 выше), он проверяет и значения, и структуру CSC сразу; промежуточная плотная версия ничего не добавляет к проверке.

## Подводные камни (чеклист)

- ✅ **Все места вызова найдены.** `finite_difference_jacobian` — `blackoil.py:242` (Ньютон); матрица уходит только в `_linear_solve` (`:244`). Прямые вызовы `finite_difference_jacobian_grouped` — только `Prototype_1.0.3/tests/test_grouped_jacobian.py:6,8`. Подмены на экземпляре в `numerical_solver/tests/test_prototype_globalization.py:117-132` и `test_prototype_well_branch.py:234-247` пропускают $J$ насквозь — тип не важен. `gpn_multiphase_solver/` якобиан не трогает (`grep finite_difference_jacobian` — только прототип и эти тесты).
- ✅ **Зависимости пакетов.** `scipy.sparse` уже импортируется (`blackoil.py:15-16`).
- ⚠️ **Обратная совместимость API.** `grouped` возвращает `csc_matrix` вместо `ndarray`. Адресовано: `_linear_solve` принимает оба типа; два теста `test_grouped_jacobian.py` (`abs(Jg-Jr)`) переводятся на `Jg.toarray()`. Исторические пробы в `vault/issues/bug-016/`, `bug-018/`, `bug-019/`, читающие $J$ как `ndarray`, не поддерживаются (как и проба `debt-033/probes/grouped_vs_reference.py` — она для кода до правки).
- ⚠️ **Явные нули и порядок столбцов SuperLU.** `csc_matrix(dense)` отбрасывает нули (в том числе `-0.0`); сборка из полосы их сохраняет. Иной шаблон → иная перестановка COLAMD → шаг Ньютона расходится на уровне округления → регрессия FAIL. Адресовано: `J.eliminate_zeros()` (удаляет и `-0.0`); тест сверяет массивы `indptr`, `indices`, `data` с `csc_matrix(Jr)`.
- ✅ **Порядок вычислений невязки.** `_well_fluxes` пишет `_last_effective_bhp_bar`, `_last_constraint_active` (побочный эффект невязки). Порядок вычислений сохраняется: базовое, затем блок $p$ цвета 0–2, затем блок $X$ цвета 0–2 — последнее вычисление то же. К тому же `well_rates()` (`blackoil.py:339-343`) пересчитывает потоки от состояния.
- ✅ **Пустые цвета при $N < 3$.** Старый цикл считает невязку и для пустого цвета; новый — тоже (`np.arange(color, n, 3)` пуст, `zp == z`, `df = 0`, элементов нет).
- ✅ **Состояние при ошибке.** Метод чистый: новых атрибутов модели нет.
- ✅ **Тесты.** `numerical_solver/tests/` — без правок; прототип — 2 правки + 3 новых теста (80 → 83).
- ✅ **Циклические import-ы.** Нет: правка внутри одного модуля.
- ✅ **Docstrings.** Ссылок `\eqref{}` в этих методах нет; docstring модуля и CHANGELOG — шаг 4.
- ✅ **Конфиги.** Не меняются (`jacobian_mode`, `linear_solver` — те же значения).
- ✅ **Связь с другими задачами.** BUG-019 влит (`cdb00d0`), `blackoil.py` не трогал. FEAT-028 (план готов) только читает `radial_blackoil/pvt.py`. DEBT-036 (обнаружена здесь — стоимость невязки на табличном PVT) — другой файл и другие методы; порядок не важен.
- ⚠️ **Знак нуля в плотном пути.** При `linear_solver='dense'` $J$ = `J.toarray()`: там, где прежняя плотная матрица держала `-0.0`, будет `+0.0`. На значения решения это не влияет (выбор ведущего элемента по $|a|$); путь используется только в `test_sparse_dense_same_step` (допуск 1e-8).
- ✅ **Производительность.** Цель задачи; замер до и после — шаги 1 и 5.
- ⚠️ **Прототип меняется** → тесты прототипа после шагов 2 и 3, регрессия `--quick` после шага 3, полная — в шаге 5. Ожидание: **побитово, 17/17 PASS** (тот же якобиан, тот же вход SuperLU → те же шаги по времени). Любой FAIL — дефект реализации, а не повод переснимать эталон.

## Шаги

### Шаг 1: Подготовка — ветка и baseline

**Цель:** зафиксировать числа и эталонные истории до правки кода.

**Файлы:** — (только запуски); снимки — `vault/issues/debt-033/probes/history_base/*.npz` основного каталога.

**Контекст:** побитовый критерий приёмки требует эталона на том же коде, что и база ветки. Снимок историй — главный эталон для примеров GPN (тесты `tests/` сравнивают числа с допусками и мелкое расхождение не поймают).

**Что сделать:**
1. Ветка/worktree `refactor/debt-033/vectorize-grouped-jacobian` от `numerical_scheme/implementation`; записать короткий SHA базы.
2. Из `numerical_solver` дерева ветки: `--collect-only -q` (ожидается 1210), быстрый уровень (987 passed, записать время).
3. Из `Prototype_1.0.3` дерева ветки: тесты прототипа (80 passed), `regression\run_regression.py --quick` (11/11 PASS). Выходы `OUTPUT/REGRESSION_*` после разбора удалить.
4. Из `numerical_solver` дерева ветки (команды — раздел «Как начать»): `history_snapshot.py save base` (все 20 примеров, ~4 мин; первая строка вывода — пути кода, должны быть пути дерева ветки) и `time_jacobian.py 20_rs300_cooling 14_high_gor_cooling 03_standing_corey 04_table_table` (~80 с). Если замер заметно отличается от таблицы baseline выше (> 20 %) — записать новые числа: машина загружена или база сдвинулась.

**Проверка после этого шага:**
- Регресс: быстрый (это и есть baseline).
- Регресс прототипа: тесты + `--quick` — baseline.

**Подводные камни:** пробы — по абсолютному пути основного каталога, запуск из `numerical_solver` дерева ветки (см. ⚠️ в «Как начать»).

**Зависимости:** блокирует все шаги.

**Оценка:** 0 строк, ~15 мин (из них 8 — регрессия).

### Шаг 2: `_fd_steps` — шаги возмущения всех неизвестных одним массивом

**Цель:** векторный аналог шагов, побитово равный прежним.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (новый метод после `_pressure_fd_step`, `:196`)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_grouped_jacobian.py` (новый тест)

**Контекст:** шаг по давлению (`_pressure_fd_step`, `blackoil.py:179-196`) — $h = \max(10^{-4}, 10^{-6}\max(|p|, 1))$ бар; в двухфазной ячейке ($R_s = R_s^{sat}(p)$, кусочно-линейна по узлам `pvt.pb`) шаг берётся вниз, если вверх он пересёк бы узел (`room_plus <= 1.25h` и `room_minus > h`) — иначе якобиан портится ровно при пересечении ячейкой границы фаз (исправление T05 в CHANGELOG 1.0.3). Шаг по $X$: $10^{-7}$ для $S_g$, $\max(10^{-5}, 10^{-6}\max(|R_s|, 1))$ для $R_s$. Второе условие `_pressure_fd_step` (`room_minus <= 1.25h and room_plus > h → +h`) совпадает с умолчанием и в векторной версии не нужно. Скалярный `_pressure_fd_step` **остаётся**: им пользуются `reference` и тесты `test_pvt_kink_jacobian.py:17-33`; новый тест держит обе реализации согласованными.

**Что сделать:**
1. Добавить метод после `_pressure_fd_step` (после строки 196, перед пустой строкой 197).
2. Добавить в `test_grouped_jacobian.py` класс `GroupedJacobianSparseTests` с тестом `test_fd_steps_equal_scalar_rule` (код — раздел «Тестовая стратегия»; `_jacobian_states` и импорт `scipy.sparse` — в шаге 3, где они нужны).

**Изменения:**

До (`blackoil.py:194-198`):
```python
        if room_plus <= 1.25*h and room_minus > h: return -h
        if room_minus <= 1.25*h and room_plus > h: return h
        return h

    def finite_difference_jacobian_reference(self,z,state_old,dt_s,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
```
После:
```python
        if room_plus <= 1.25*h and room_minus > h: return -h
        if room_minus <= 1.25*h and room_plus > h: return h
        return h
    def _fd_steps(self,z,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
        """DEBT-033: finite-difference steps of all 2n unknowns at once (pressure block, then Rs/Sg)."""
        # Elementwise the same float64 arithmetic as _pressure_fd_step and the Rs/Sg
        # step rule of the column loop, hence bitwise the same steps.
        z=np.asarray(z,float); mask=np.asarray(gas_active,dtype=bool); n=self.grid.n
        p,x=z[:n],z[n:]
        h=np.maximum(p_abs_step,p_rel_step*np.maximum(np.abs(p),1.0))
        knots=np.asarray(self.pvt.pb,float)
        if knots.size:
            # Gas-active cells: step down where the step up would straddle the next
            # Rs_sat(p) knot (see _pressure_fd_step); its second rule returns +h,
            # the default, and needs no counterpart here.
            idx=np.searchsorted(knots,p,side='left')
            lower=np.where(idx>0,knots[np.maximum(idx-1,0)],-np.inf)
            upper=np.where(idx<knots.size,knots[np.minimum(idx,knots.size-1)],np.inf)
            down=mask&(upper-p<=1.25*h)&(p-lower>h)
            h=np.where(down,-h,h)
        hx=np.where(mask,sg_abs_step,np.maximum(rs_abs_step,1e-6*np.maximum(np.abs(x),1.0)))
        return np.concatenate([h,hx])

    def finite_difference_jacobian_reference(self,z,state_old,dt_s,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
```

Почему побитово: Python `max(a, b)` и `np.maximum` на конечных положительных float64 дают одно и то же значение; `p_rel_step*...`, `upper-p`, `p-lower`, `1.25*h` — те же операции float64 поэлементно; `p - (-inf) = inf` как в скалярной версии.

**Проверка после этого шага:**
- Тест шага: из `Prototype_1.0.3` — `..\..\.venv\Scripts\python -m pytest tests/test_grouped_jacobian.py -q` (5 passed).
- Регресс прототипа: тесты прототипа — 81 passed. Регрессия не нужна: метод пока не вызывается.
- Регресс: быстрый — поведение не меняется (987 passed).

**Подводные камни:** знак шага у узлов (чеклист — «Обратная совместимость», шаг сохраняет `_pressure_fd_step`).

**Зависимости:** требует шаг 1; блокирует шаг 3.

**Оценка:** ~20 строк кода, ~20 строк теста, ~20 мин.

### Шаг 3: Групповой якобиан — векторно и сразу в CSC; `_linear_solve` для обоих типов

**Цель:** убрать цикл по ячейкам и плотную матрицу; результат побитово равен `csc_matrix(reference)`.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (`:15` импорт, `:204-221`)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_grouped_jacobian.py` (`:6`, `:8` — `.toarray()`; 2 новых теста)

**Контекст:** для каждого из 6 цветов массив ячеек `cells = arange(color, n, 3)`, их столбцы `j = cells + block*n`, шаги `h[j]`. После `df = F(zp) - f0` элементы столбца ячейки $i$ — строки $i+d$, $d \in \{-1, 0, 1\}$ (нефть) и $n+i+d$ (газ), значение `df[строка] / h` — та же операция, что `J[rows,j]=df[rows]/h` в старом цикле (деление, не умножение на `1/h`). Пары (строка, столбец) не повторяются, `tocsc()` даёт канонический CSC (индексы отсортированы), `eliminate_zeros()` — тот же шаблон, что `csc_matrix(dense)` (проверено, п. 2 «Проверено при планировании»).

**Что сделать:**
1. Импорт (`blackoil.py:15`): `from scipy.sparse import csc_matrix` → `from scipy.sparse import coo_matrix, csc_matrix, issparse`.
2. Заменить тело `finite_difference_jacobian_grouped` (`:204-216`), добавить комментарий в диспетчер (`:217-218`), заменить `_linear_solve` (`:219-221`).
3. В `test_grouped_jacobian.py:6` и `:8`: `abs(Jg-Jr)` → `abs(Jg.toarray()-Jr)` (допуски 1e-8 и 2e-7 не трогать — это прежние тесты эквивалентности режимов; побитовую проверку делают новые тесты).
4. Добавить импорт `from scipy.sparse import csc_matrix, issparse` в начало `test_grouped_jacobian.py`, функцию `_jacobian_states()` перед классом `GroupedJacobianSparseTests`, тесты `test_grouped_is_csc_bitwise_reference` и `test_step_bitwise_grouped_vs_reference` (код — «Тестовая стратегия»).

**Изменения:**

До (`blackoil.py:204-221`): см. «Что медленно сейчас» + 
```python
    def finite_difference_jacobian(self,*args,**kwargs):
        return self.finite_difference_jacobian_reference(*args,**kwargs) if self.jacobian_mode=='reference' else self.finite_difference_jacobian_grouped(*args,**kwargs)
    def _linear_solve(self,J,b):
        if self.linear_solver=='sparse': return splu(csc_matrix(J)).solve(b)
        return dense_solve(J,b,assume_a='gen',check_finite=True)
```
После:
```python
    def finite_difference_jacobian_grouped(self,z,state_old,dt_s,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
        """Coloured finite-difference Jacobian as a CSC matrix, bitwise csc_matrix() of the reference one (DEBT-033)."""
        # The residual of cell i depends on cells i-1, i, i+1 only, so cells i, i+3,
        # i+6, ... are perturbed together: 2 blocks x 3 colours = 6 residual
        # evaluations.  Steps, residual evaluations and their order, and the entries
        # df/h are those of the former per-cell loop (DEBT-033 probe: bitwise equal
        # to the reference on 488 Newton states of five GPN examples).
        z=np.asarray(z,float); f0=self.residual(z,state_old,dt_s,gas_active); n=self.grid.n
        h=self._fd_steps(z,gas_active,p_rel_step,p_abs_step,rs_abs_step,sg_abs_step)
        rows=[]; cols=[]; vals=[]
        for block in (0,1):
            for color in range(3):
                cells=np.arange(color,n,3); j=cells+block*n; hj=h[j]
                zp=z.copy(); zp[j]+=hj
                df=self.residual(zp,state_old,dt_s,gas_active)-f0
                for d in (-1,0,1):
                    # oil (row r) and gas (row n+r) residuals of the neighbour r=i+d
                    ok=(cells+d>=0)&(cells+d<n); r=cells[ok]+d; c=j[ok]; hc=hj[ok]
                    rows+=[r,n+r]; cols+=[c,c]; vals+=[df[r]/hc,df[n+r]/hc]
        J=coo_matrix((np.concatenate(vals),(np.concatenate(rows),np.concatenate(cols))),shape=(2*n,2*n)).tocsc()
        # csc_matrix(dense) of the former loop dropped exact zeros (downstream
        # entries, dkrg/dSg = 0 below Sgc).  Explicit zeros would change the sparsity
        # pattern, SuperLU's column ordering and the Newton step at round-off level.
        J.eliminate_zeros()
        return J,f0
    def finite_difference_jacobian(self,*args,**kwargs):
        # DEBT-033: grouped returns a CSC matrix, reference a dense array; _linear_solve takes both
        return self.finite_difference_jacobian_reference(*args,**kwargs) if self.jacobian_mode=='reference' else self.finite_difference_jacobian_grouped(*args,**kwargs)
    def _linear_solve(self,J,b):
        if self.linear_solver=='sparse': return splu(J if issparse(J) else csc_matrix(J)).solve(b)
        return dense_solve(J.toarray() if issparse(J) else J,b,assume_a='gen',check_finite=True)
```

Замечания к коду:
- `zp[j]+=hj` поэлементно равно прежнему `zp[j]+=h` по одной ячейке (индексы `j` различны).
- Цикл `for d` — 3 итерации на цвет, не по ячейкам: 18 срезов на якобиан вместо $4N$ итераций.
- `splu(J)` для канонического CSC не копирует и не меняет $J$; прежний путь `splu(csc_matrix(J))` остаётся для плотной $J$ режима `reference`.

**Проверка после этого шага:**
- Тест шага: `..\..\.venv\Scripts\python -m pytest tests/test_grouped_jacobian.py -q` (7 passed).
- Регресс прототипа: тесты прототипа — **83 passed**; `regression\run_regression.py --quick` — **11/11 PASS** (ожидание — побитово: тот же якобиан, тот же вход SuperLU).
- Регресс: быстрый — 987 passed (примеры в быстрый уровень не входят; их побитовую проверку делает шаг 5).
- Быстрая проверка эффекта: `time_jacobian.py 20_rs300_cooling` — «учёт» должен упасть с ~7.9 с до ~0.5 с.

**Подводные камни:** явные нули и SuperLU; тип результата; порядок вычислений невязки; пустые цвета (чеклист).

**Зависимости:** требует шаг 2; блокирует шаги 4, 5.

**Оценка:** ~25 строк кода (взамен ~15), ~25 строк тестов, ~40 мин (из них 8 — регрессия).

### Шаг 4: Документация прототипа и заметка о прототипе

**Цель:** записать локальное изменение там, где их записывают для прототипа.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (docstring модуля, `:1-11`)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` (новый раздел в конце)
- `vault/knowledge/decisions/hydro-prototype-анализ.md` (§6, `:79-83`) — **отдельным коммитом `vault:`** (CLAUDE.md: изменения vault — отдельно от кода)

`docs/UNIT_TEST_AUDIT.md` прототипа не трогать: это аудит тестов релиза 1.0.3, локальные изменения BUG-014/016/018 в нём не записывались — журнал локальных правок ведёт только CHANGELOG.

**Что сделать:**
1. Docstring модуля — строка после BUG-018 (`:9-10`):
   ```
   DEBT-033: the grouped Jacobian is assembled vectorized, directly as a CSC matrix
   (bitwise the former dense one); _linear_solve takes sparse or dense J.
   ```
2. CHANGELOG — раздел по образцу BUG-014/016 (английский, как весь файл):
   ```
   ## Local changes — GPN project (DEBT-033): vectorized grouped Jacobian
   - Problem: the grouped finite-difference Jacobian took 72-81 % of the run time of the GPN examples; at N = 350 half of the run time was bookkeeping around its six residual evaluations: a Python loop over cells per colour (`_pressure_fd_step` per cell, `np.arange`, row writes into a dense 2N x 2N matrix) and `csc_matrix(J)` scanning all 4N^2 entries in `_linear_solve()`.
   - `_fd_steps()`: perturbation steps of all 2N unknowns at once, elementwise the same arithmetic as `_pressure_fd_step()` and the Rs/Sg step rule.
   - `finite_difference_jacobian_grouped()`: entries written by array slicing per colour, the matrix assembled directly as CSC (`coo_matrix(...).tocsc()`, `eliminate_zeros()`); it returns a `scipy.sparse.csc_matrix` instead of a dense array. Same steps, the same residual evaluations in the same order, the same entries `df/h`: bitwise the former matrix and the same CSC arrays as `csc_matrix(dense)`, so SuperLU gets the same input. `reference` mode still returns a dense array.
   - `_linear_solve()` accepts sparse or dense J (`linear_solver='dense'` uses `J.toarray()`).
   - Effect: <числа шага 5: пример 20, 14 — было/стало>; prototype tests 83 passed; regression 17/17 PASS.
   - Physics, residual equations, tolerances and Newton/active-set logic are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
   - Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/52; plan: `vault/plans/debt-033 vectorize-grouped-jacobian.md` of the GPN project.
   ```
3. `hydro-prototype-анализ.md` §6: строку «Два режима: `grouped` (3-цветная раскраска, O(N) вычислений невязки)…» уточнить — `grouped`: 6 вычислений невязки (+1 базовое) независимо от $N$, стоимость якобиана $O(N)$; `reference`: $2N$ вычислений, $O(N^2)$. Добавить абзац: DEBT-033 — `grouped` собирается векторно сразу в CSC, побитово равен `reference` (488 состояний); BUG-019 — тест Тейлора: якобиан согласован с невязкой; аналитический якобиан не нужен (DEBT-033, вариант 4). П. P7 («ОФП без производных») не меняется.

**Проверка после этого шага:**
- Регресс: `--collect-only -q` (только документы и docstring).

**Зависимости:** требует шаг 3 (числа эффекта — шаг 5: вписать в CHANGELOG после шага 5).

**Оценка:** ~25 строк текста, ~15 мин.

### Шаг 5: Верификация — истории примеров, полная регрессия, замер

**Цель:** доказать побитовую неизменность на всех примерах GPN и всех кейсах прототипа и измерить эффект.

**Файлы:** — (запуски); снимки — `vault/issues/debt-033/probes/history_new/`.

**Что сделать:**
1. Зафиксировать HEAD ветки (полная регрессия — отдельные процессы на каждый кейс; не вливать ничего в дерево во время прогона).
2. Из `numerical_solver` дерева ветки: `history_snapshot.py save new`, затем `history_snapshot.py compare base new` → ожидание: **20 строк «побитово», «итого: различий 0»**.
3. Из `Prototype_1.0.3` дерева ветки: `..\..\.venv\Scripts\python regression\run_regression.py` (полная, с T05; было ~45 мин, после правки ожидается меньше) → **17/17 PASS**. Выходы `OUTPUT/REGRESSION_*` после разбора удалить.
4. `time_jacobian.py 20_rs300_cooling 14_high_gor_cooling 03_standing_corey 04_table_table` — таблица «было/стало» (было — шаг 1).
5. Вписать числа в CHANGELOG (шаг 4, п. 2).

**Если `compare` или регрессия показали различие:** не переснимать эталоны. Найти первое расхождение: истории — с какой записи; регрессия — `step_log.csv` (с какого шага по времени). Проверить на этом состоянии `np.array_equal(Jg.toarray(), Jr)` и массивы CSC против `csc_matrix(Jr)` — тесты шага 3 должны были это поймать; если не поймали — дописать тест на это состояние.

**Проверка после этого шага:**
- Регресс: полный — `pytest tests/ -q` (1210 passed, ~10 мин) делает `/implement` в §3.1; отдельно здесь не нужен.
- Регресс прототипа: полная регрессия (п. 3).

**Критерии:**
- истории 20 примеров — побитово;
- регрессия прототипа — 17/17 PASS;
- «учёт раскраски + перевод в разреженную» у примера 20 — не больше 1 с (было 9.5 с); если больше 2 с — разобрать, что осталось в цикле.

**Зависимости:** требует шаги 3–4; блокирует шаг 6.

**Оценка:** 0 строк, ~60 мин (регрессия ≤ 45 мин, снимок 4 мин).

### Шаг 6: Vault и issue

**Цель:** закрыть запись и оставить результат в issue.

**Файлы:**
- `vault/roadmap/известные баги и технический долг.md` (запись DEBT-033)
- `vault/issues/debt-033/05-comment-done.md` (новый)
- `vault/00-home/index.md` (строка плана)

**Что сделать:**
1. DEBT-033: поле «Результат» (замер было/стало, 83 теста прототипа, 17/17 PASS, истории 20 примеров побитово), статус `✅ ИСПРАВЛЕНО (дата)`. В поле «Воспроизведение» — пример `20_rs300_cooling` вместо `20_rs500_cooling`.
2. Комментарий в #52 (`gh issue comment 52 --repo ArturSalamatin/Oil_Gas --body-file vault/issues/debt-033/05-comment-done.md`).
3. Строка в `index.md` — отметить «реализовано».

**Проверка после этого шага:** `--collect-only -q`.

**Зависимости:** требует шаг 5.

**Оценка:** ~15 строк текста, ~10 мин.

## Тестовая стратегия

Все новые тесты — в `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_grouped_jacobian.py` (стиль прототипа: `unittest`, компактные строки; комментарии — по правилам проекта). Запуск — из `Prototype_1.0.3`: `..\..\.venv\Scripts\python -m pytest tests/test_grouped_jacobian.py -q`.

Код (добавляется после класса `GroupedJacobianTests`, перед `if __name__=='__main__'`; импорт `from scipy.sparse import csc_matrix, issparse` — в начало файла):

```python
# DEBT-033: the grouped Jacobian is assembled vectorized, directly as a CSC matrix.
# It must stay bitwise the former matrix: the Newton steps and the prototype
# regression against golden/ (abs 2e-7 / rel 2e-10) depend on it.  The bitwise
# reference is the column-by-column mode: the former dense grouped matrix equalled
# it bitwise on 488 Newton states of five GPN examples (DEBT-033 probe).
def _jacobian_states():
    """Oil-only, mixed (Sg = 0.02 and 0), mixed with two-phase cells just below a PVTO knot."""
    # Oil-only: downstream band entries are exact zeros.  Sg = 0: krg = 0 at the first
    # relperm-table row.  Below a knot: the pressure step of those cells is negative
    # (_pressure_fd_step steps down instead of straddling the Rs_sat(p) kink).
    _,m,s=model_and_state(n=7); yield m,s,s.gas_active.copy()
    for sg in (0.02,0.0):
        _,m,s=model_and_state(n=7,p0=160); mask=np.zeros(7,bool); mask[:3]=True
        s.gas_active=mask; s.sg[:3]=sg; s.rs_sm3_sm3[:3]=m.pvt.rs_sat(s.pressure_bar[:3]); yield m,s,mask
    _,m,s=model_and_state(n=7,p0=160); mask=np.zeros(7,bool); mask[:3]=True
    k=float(m.pvt.pb[-2]); s.pressure_bar[:3]=k-0.5*max(1e-4,1e-6*k)
    s.gas_active=mask; s.sg[:3]=0.02; s.rs_sm3_sm3[:3]=m.pvt.rs_sat(s.pressure_bar[:3]); yield m,s,mask

class GroupedJacobianSparseTests(unittest.TestCase):
    def test_fd_steps_equal_scalar_rule(self):
        # _fd_steps gives bitwise the steps of _pressure_fd_step (one-sided step at the
        # Rs_sat(p) knots) and of the Rs/Sg rule of the column loop.  Pressures straddle
        # every PVTO knot at 0.5...2 steps, where the step direction flips; Rs below
        # and above 1 hits both branches of max(|Rs|, 1).
        _,m0,_=model_and_state(n=3); knots=np.asarray(m0.pvt.pb,float)
        hk=np.maximum(1e-4,1e-6*np.maximum(np.abs(knots),1.0))
        offs=np.array([-2,-1.3,-1.25,-1,-0.5,0,0.5,1,1.25,1.3,2])
        p=np.concatenate([(knots[:,None]+offs*hk[:,None]).ravel(),[0.5,1.0,knots[-1]+10.0,300.0]])
        n=p.size; _,m,_=model_and_state(n=n); flipped=[]
        for mask in (np.ones(n,bool),np.arange(n)%2==0):
            x=np.where(mask,0.02,np.resize([0.5,30.0,120.0],n)); h=m._fd_steps(np.concatenate([p,x]),mask)
            hp=np.array([m._pressure_fd_step(pi,bool(gi)) for pi,gi in zip(p,mask)])
            hx=np.array([1e-7 if gi else max(1e-5,1e-6*max(abs(xi),1.0)) for xi,gi in zip(x,mask)])
            self.assertTrue(np.array_equal(h,np.concatenate([hp,hx]))); flipped.append(np.any(hp<0))
        self.assertTrue(flipped[0])   # the knot rule was exercised, not only the default +h
    def test_grouped_is_csc_bitwise_reference(self):
        # Values: bitwise the column-by-column reference.  Structure: the same CSC arrays
        # as csc_matrix(dense), which the former _linear_solve passed to splu -- explicit
        # zeros would change SuperLU's column ordering and the step at round-off level.
        negative=False
        for m,s,mask in _jacobian_states():
            z=m.pack(s,mask); n=m.grid.n
            Jg,_=m.finite_difference_jacobian_grouped(z,s,60,mask); Jr,_=m.finite_difference_jacobian_reference(z,s,60,mask)
            self.assertTrue(issparse(Jg) and Jg.format=='csc')
            self.assertTrue(np.array_equal(Jg.toarray(),Jr))
            R=csc_matrix(Jr)
            for a in ('indptr','indices','data'): self.assertTrue(np.array_equal(getattr(Jg,a),getattr(R,a)),a)
            self.assertLess(Jg.nnz,4*(3*n-2))   # the band holds exact zeros: eliminate_zeros is exercised
            negative|=bool(np.any(m._fd_steps(z,mask)[:n]<0))
        self.assertTrue(negative)   # some state used negative pressure steps (below a PVTO knot)
    def test_step_bitwise_grouped_vs_reference(self):
        # Whole implicit steps with phase switches: the grouped path (CSC straight to
        # splu) and the reference path (dense, csc_matrix in _linear_solve) must give
        # bitwise the same state and the same Newton iteration count.
        for dt in (60.0,3600.0):
            _,mg,s=model_and_state(n=8,jacobian='grouped'); _,mr,_=model_and_state(n=8,jacobian='reference')
            a,ra=mg.advance(s,dt); b,rb=mr.advance(s,dt)
            self.assertTrue(ra.converged and rb.converged); self.assertEqual(ra.iterations,rb.iterations)
            self.assertGreater(ra.phase_switches,0)   # the active-set loop ran, not one plain Newton solve
            for f in ('pressure_bar','rs_sm3_sm3','sg','gas_active'): self.assertTrue(np.array_equal(getattr(a,f),getattr(b,f)),f)
```

Паспорт тестов:

**Тест:** `test_fd_steps_equal_scalar_rule`
**Файл:** `Prototype_1.0.3/tests/test_grouped_jacobian.py` (существующий)
**Сценарий:** давления вокруг каждого узла `pvt.pb` фикстуры `Nabor_1b` (6 узлов: 24.5…180 бар) на $\{-2, -1.3, -1.25, -1, -0.5, 0, 0.5, 1, 1.25, 1.3, 2\}$ шагах, плюс 0.5, 1, $p_{b,max}+10$, 300 бар; маски «все двухфазные» и «через одну».
**Ожидание:** `np.array_equal` с поэлементным скалярным правилом; в маске «все двухфазные» есть отрицательный шаг.
**Предотвращает:** расхождение векторного и скалярного правил шага (в том числе при будущей правке одного из них).

**Тест:** `test_grouped_is_csc_bitwise_reference`
**Сценарий:** три состояния $N = 7$ — однофазное, смешанное с $S_g = 0.02$ и с $S_g = 0$.
**Ожидание:** CSC; `toarray()` побитово равна `reference`; `indptr`, `indices`, `data` равны `csc_matrix(Jr)`; `nnz < 4(3N-2)` (на планировании: 45 и 48 из 76).
**Baseline:** проба на 488 состояниях примеров.
**Предотвращает:** ошибку индексов при раскладке столбцов, потерю `eliminate_zeros()`, смену шаблона разреженности.

**Тест:** `test_step_bitwise_grouped_vs_reference`
**Сценарий:** `advance` $N = 8$, $p_0 = 200$, BHP 100 бар, $\Delta t$ = 60 и 3600 с (на планировании: 7 и 6 итераций, 2 и 3 переключения фаз).
**Ожидание:** оба сходятся, число итераций равно, $p$, $R_s$, $S_g$, набор фаз побитово равны.
**Предотвращает:** расхождение пути «CSC прямо в `splu`» и прежнего пути через `csc_matrix(dense)`.

Правки существующих тестов: `test_grouped_jacobian.py:6`, `:8` — `Jg.toarray()`. `test_sparse_dense_same_step` (`:11-12`) без правки — теперь проверяет плотный путь `_linear_solve` с разреженной $J$.

Неизменность поведения (без новых тестов):
- `numerical_solver/tests/` — быстрый уровень после шагов 2–3, полный в конце;
- тесты прототипа (80 → 83);
- регрессия прототипа `--quick` (шаг 3), полная (шаг 5) — побитово против `golden/`;
- истории 20 примеров GPN — побитово (`history_snapshot.py compare base new`, шаг 5).

## Критерии завершения

- [ ] Шаги 1–6 выполнены.
- [ ] `numerical_solver/tests/` — 1210 passed (полный прогон в конце).
- [ ] Тесты прототипа — 83 passed; полная регрессия `run_regression.py` — 17/17 PASS.
- [ ] Истории 20 примеров — побитово (`compare base new`: различий 0).
- [ ] Учёт раскраски + перевод в разреженную у примера 20 ≤ 1 с (было 9.5 с); таблица «было/стало» в CHANGELOG и в записи DEBT-033.
- [ ] Import graph: `coo_matrix`, `issparse` используются; лишних импортов нет.
- [ ] CHANGELOG, docstring модуля, `hydro-prototype-анализ.md` обновлены.
- [ ] Vault: DEBT-033 — результат и статус; комментарий в #52 (закрывается при merge).

## Обнаруженные проблемы

1. **Невязка на табличном PVT дорогая — DEBT-036** (зарегистрирована при планировании). На состоянии примера 14 ($N = 350$, 334 двухфазные ячейки, 14 сегментов PVTO из 19 ветвей) невязка — 2.65 мс против ~0.9 мс на Стендинге: `bo` и `mu_o` по 0.48 мс за вызов (`BlackOilPVT._oil_prop`, `radial_blackoil/pvt.py:43-64` — цикл Python по сегментам $R_s$); `component_inventories` берёт `oil_properties` и `gas_properties` и считает $\mu_o$, $\mu_g$ впустую (`blackoil.py`, запасы — только $B_o$, $B_g$); `physical_residual` пересчитывает запасы старого состояния на каждом вызове, хотя в пределах шага они постоянны. Невязки — 52 % времени примера 14 (32.5 из 62.6 с). Текущую задачу не блокирует.
2. **Номера примера 20 в записи DEBT-033 и issue #52** — замер на `00af963` для `20_rs500_cooling` (переименован в DEBT-034). Не ошибка — исторический замер; актуальный baseline — в этом плане; поле «Воспроизведение» обновить в шаге 6.
3. **`hydro-prototype-анализ.md` §6** — «O(N) вычислений невязки» у `grouped` неточно (их 6 при любом $N$); исправляется в шаге 4.

## Оценка

- Файлов: 2 кода/тестов прототипа (`blackoil.py`, `test_grouped_jacobian.py`), 1 документ прототипа (`CHANGELOG_1.0.3.md`), 4 файла vault (заметка о прототипе, реестр, индекс, комментарий issue).
- Строк: ~45 кода (из них ~15 заменяются), ~45 тестов, ~40 текста.
- Время: ~2.5 ч, из них ~1.2 ч — прогоны (регрессия `--quick` × 2, полная × 1, снимки историй × 2, полный `tests/`).

## Связанные заметки

- `vault/roadmap/известные баги и технический долг.md` — DEBT-033, DEBT-036, BUG-019, DEBT-029, DEBT-032
- `vault/knowledge/decisions/hydro-prototype-анализ.md`
- `vault/issues/debt-033/` — тело issue, пробы: `time_jacobian.py` (замер), `grouped_vs_reference.py` (+ `.txt`; только для кода до правки), `history_snapshot.py` (побитовое сравнение историй), `planned_code_check.py` (+ `.txt`; код шагов 2–3 подменой в памяти — после реализации не нужна), `audit_plan_literal.py` (аудит: код и тесты из файла плана дословно; после реализации не нужна)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` — разделы локальных изменений BUG-014, BUG-016, DEBT-029
- Issue: [#52](https://github.com/ArturSalamatin/Oil_Gas/issues/52)
