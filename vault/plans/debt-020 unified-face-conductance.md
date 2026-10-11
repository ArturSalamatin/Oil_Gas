---
tags:
  - план
  - рефакторинг
date: 2026-10-11
issue: DEBT-020
github: 99
branch: refactor/debt-020/unified-face-conductance
status: реализован
worktree: .worktrees/debt-020
audit:
  date: 2026-10-11
  found: 6
  auto-fixed: 6
  manual-required: 0
---

# План DEBT-020: проводимость грани $\mathcal{Q}_T$ — единый массив $[N+1]$ по номеру грани, сборка СЛАУ по формулам постановки на всех строках

**Задача:** [[известные баги и технический долг#DEBT-020: Кондуктивные проводимости граней хранятся в трёх разных видах — сдвинутая индексация рядом с прямой в одной строке сборки|DEBT-020]] · GitHub [#99](https://github.com/ArturSalamatin/Oil_Gas/issues/99) · ветка `refactor/debt-020/unified-face-conductance` · база `numerical_scheme/implementation` (план — на `d7528d4`, аудит 1 — на `123247a` после влития DEBT-059; файлы плана между ними не менялись)

**Подтип:** рефакторинг (внутренний интерфейс модуля `energy/tridiag.py`; численный результат — побитово прежний).

## Решения пользователя (2026-10-11)

Заданы вопросом при планировании, ответы — прямые:

1. **Сборка — вариант 2:** единый массив `Q_T` $[N+1]$ **и** сборка операциями над массивами по `eq:tridiag_a`…`eq:tridiag_c` на всех строках; цикл по ячейкам и ветвь `if N == 1` уходят.
2. **Эталон DEBT-016 не трогать:** `_ref_conductive` и `_ref_assemble` (`tests/test_energy_matrix_examples.py`) остаются с парой `(Q_T_internal, Q_T_ext)` и циклом. Правится только самопроверка, которая зовёт решатель (`test_ref_conductive_matches_annulus_solution`).
3. **Накопитель баланса:** `solve` передаёт `add_substep(Q_T_ext=Q_T[N])`; `energy/balance.py` не меняется.
4. **Проверка побитовости — новая проба** `vault/issues/debt-020/probes/bits_capture.py` (хеши $a, b, c, d$ на каждом вызове `solve` + все записи $T$ + синтетика $N = 1, 2, 3, 10$), а не утилита `tests/baseline_vectorization_check.py`.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-020 в `vault/roadmap/известные баги и технический долг.md` (с абзацем «Актуализация 2026-10-11») и тело issue `vault/issues/debt-020/01-issue-body.md`.
3. Реализация — только в отдельном worktree (`/implement` делает это сам; основной каталог занят параллельными сессиями):
   ```powershell
   git worktree add .worktrees/debt-020 -b refactor/debt-020/unified-face-conductance numerical_scheme/implementation
   ```
   Перед этим `/implement` коммитит в базу материалы задачи — этот план и `vault/issues/debt-020/` (пробы нужны в worktree).
4. Интерпретатор — основного каталога по абсолютному пути (в worktree `.venv` нет):
   `D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python`. Ниже он обозначен `<py>`.
   `pytest` из `.worktrees\debt-020\numerical_solver` берёт код worktree (пакет — каталог запуска первым в `sys.path`, прототип — `pythonpath` в `[tool.pytest.ini_options]` `numerical_solver/pyproject.toml`, DEBT-059). Проба `bits_capture.py` берёт код **текущего каталога** и печатает путь первой строкой (`Код: …\.worktrees\debt-020\numerical_solver\…`) — проверять каждый раз ([[reference_worktree_pythonpath]]: иначе сверка «до/после» молча сравнит неизменённый основной каталог).
   Почему проба видит worktree без `PYTHONPATH`: с DEBT-059 оба пакета (`gpn_multiphase_solver`, `radial_blackoil`) установлены в общий venv в редактируемом режиме и указывают на **основной** каталог, но через поисковики `_EditableFinder`, которые стоят в `sys.meta_path` **после** `PathFinder` (проверено при аудите: `['BuiltinImporter', 'FrozenImporter', 'PathFinder', '_EditableFinder', '_EditableFinder']`). Проба вставляет `Path.cwd()` и путь прототипа в начало `sys.path` — `PathFinder` находит код worktree раньше. `PYTHONPATH` из правила 3 `/implement` нужен скриптам примеров; в этом плане они не запускаются.
5. Baseline (из `.worktrees\debt-020\numerical_solver`):
   ```powershell
   <py> -m pytest tests/ --collect-only -q                # ожидается 1699 (на 123247a)
   <py> -m pytest tests/ -m "not slow" -q                 # ожидается 1428 passed, ~75 с
   <py> ..\vault\issues\debt-020\probes\bits_capture.py capture base   # ~31 с
   ```
   Запомни число тестов, число в быстром уровне и время быстрого уровня.
6. Начни с шага 1. После каждого шага — регресс по полю «Регресс» и (для шагов кода) `compare base <шаг>`.

## Контекст

### Что сейчас

Кондуктивная проводимость грани $\mathcal{Q}_T$ (`eq:heat_cond_disc`) в `numerical_solver/gpn_multiphase_solver/energy/tridiag.py` хранится тремя способами:

| грань | где лежит | тип |
|---|---|---|
| $f = 0$ (забой) | нигде | — |
| $f = 1 \ldots N-1$ | `Q_T_internal[f-1]` | массив $[N-1]$, **индексация со сдвигом** |
| $f = N$ (контур) | `Q_T_ext` | скаляр, отдельный аргумент |

Все прочие величины на гранях (`Phi_plus`, `Phi_minus`, `Phi_o`, `Phi_g`) — массивы $[N+1]$ с индексом = номер грани. Грань $f$ разделяет ячейки $f-1$ и $f$; ячейка $j$ ограничена гранями $j$ (слева, ближе к скважине) и $j+1$ (справа). В строке сборки (`assemble_tridiag`, стр. 543-554) две конвенции стоят в одном выражении:

```python
Q_T_L = Q_T_internal[j - 1]     # грань j   — со сдвигом
Q_T_R = Q_T_internal[j]         # грань j+1 — со сдвигом
b[j] = cap[j] + Q_T_L + Q_T_R + Phi_plus[j] - Phi_minus[j + 1]   # Φ — без сдвига
```

Ошибка в этом члене уже была (BUG-002 — двойной $\ln$; BUG-027 — то же в постановке). Пара `(Q_T_internal, Q_T_ext)` порождает ещё ветвь `if N > 1 … else np.empty(0)` в `compute_conductive_transmissibility` и ветвь `if N == 1` в `assemble_tridiag` (при $N = 1$ блоки «забой» и «контур» присваивают строку 0 целиком, и второй затирал бы первый — так было до BUG-012).

### Что хотим

`Q_T` — массив $[N+1]$ по номеру грани: `Q_T[0] = 0.0` (ГУ Неймана у забоя, `ssec:bc_disc`: кондуктивного потока в скважину нет при любой $T$ за гранью), `Q_T[1..N-1]` — внутренние, `Q_T[N]` — контур. Тогда формулы постановки `eq:tridiag_a`…`eq:tridiag_c` с $Q^T_{\lambda,1/2} = 0$ верны на **всех** строках, включая $j = 0$ и $N = 1$, — ровно так их и пишет `problem_statement.tex`.

**Соответствие индексов граней.** В `eq:tridiag_a`…`eq:tridiag_d` ячейка $j$ ($j = 0 \ldots N-1$) лежит между гранями $j-\tfrac12$ и $j+\tfrac12$: грань кода `f = j` ↔ грань $j-\tfrac12$ формул. Подраздел ГУ `ssec:bc_disc` и `eq:log_grid` нумеруют грани со сдвигом на единицу: забойная — $\tfrac12$ ($r_{1/2} = r_w$), контурная — $N+\tfrac12$. Это известная нестыковка `.tex` (вопрос из аудита BUG-027, в реестр не записана), к DEBT-020 не относится: код и план следуют индексу грани кода, `Q_T[0]` — забой, `Q_T[N]` — контур, как у `Phi_plus`/`Phi_minus`. Новые комментарии кода пишутся в индексах кода и метках; перенесённый без изменений комментарий BUG-012 о $D_j = \Phi_{j+1/2} - \Phi_{j-1/2}$ (шаг 3) — в записи формул постановки, его не трогать. Граничные условия остаются точечными поправками:

- `a[0] = 0` — связи слева нет;
- $\Phi^+$ забойной грани (индекс 0) в `b[0]` не входит — забойная грань конвективного вклада не даёт (ГУ забоя, BUG-012);
- `c[N-1] = 0` — справа $T_{ext}$ известна;
- `d[N-1]` получает $(\mathcal{Q}_T[N] - \Phi^-_N)\,T_{ext}$ — вклад Дирихле.

Поправки применяются к массивам, собранным целиком, и при $N = 1$ складываются, а не затирают друг друга, — ветвь $N = 1$ исчезает.

### Почему результат побитово прежний (проверено)

Порядок сложений сохраняется: `b = cap + Q_T[:-1]; b += Q_T[1:]; b[1:] += Phi_plus[1:N]; b -= Phi_minus[1:]` даёт для $j \ge 1$ ту же последовательность `((cap + Q_L) + Q_R) + Φ⁺) − Φ⁻`, что цикл; для $j = 0$ — `((cap + 0.0) + Q_T[1]) − Φ⁻[1]`, а прибавление точного нуля не меняет ни бита. `d[N-1]` собирается заново полной формулой в прежнем порядке слагаемых. numpy не сливает отдельные операции в FMA.

**Проба плана** `vault/issues/debt-020/probes/plan_vector_assembly.py` (вывод — `plan_vector_assembly.out.txt`): нынешний код не тронут, обёртка на **каждом** вызове сборки сравнивает по байтам нынешнюю сборку с кандидатной (код шага 3 этого плана):

- синтетика — 800 случаев, $N = 1, 2, 3, 10$, $T_{ext} \ne 0$, $\Phi^+_0 > 0$, $\lambda = 0$ в каждом десятом: **побитово**;
- все 23 конфига `examples/*/config.json` целиком (от 30 до 864 вызовов сборки на пример, $N$ = 50…350): **побитово**.

**Отрицательный контроль** (`plan_negative_control.py`, вывод — `.out.txt`): сдвиг `b[N-1]` на 1 ULP проба `bits_capture.py` видит на первом же вызове во всех частях, **а поля $T$ при этом побитово прежние на всех пяти примерах**. Отсюда критерий плана: хеши матрицы, а не только $T$. Сверка одного поля $T$ (утилита DEBT-018 `tests/baseline_vectorization_check.py`) такую правку пропустила бы.

## Baseline (2026-10-11, `123247a`; аудит 1)

| Что | Значение |
|---|---|
| Тестов всего | 1699 (на `d7528d4` было 1691; +8 — `tests/test_packaging.py` из DEBT-059) |
| Быстрый уровень (`-m "not slow"`) | 1428 (271 deselected), ~75 с |
| Тестов в `test_energy.py`, `test_val002.py`, `test_energy_matrix_examples.py` | 90 (быстрых 67) |
| Снимок `bits_capture.py` | ~31 с: synth 800; 07 — 72 вызова `solve`, 10 — 73, 11 — 72, 14 — 361, 16 — 720 |

После плана: тестов **1702** (+3), быстрый уровень **1431**. Если до начала реализации в базу влита другая задача, считать от фактического baseline шага 0: +2 после шага 1, +3 после шага 2.

## Затронутые файлы

| Файл | Место (на `123247a` = на `d7528d4`) | Что меняется | Шаг |
|---|---|---|---|
| `numerical_solver/gpn_multiphase_solver/energy/tridiag.py` | `solve` 114-116, 159-170 | `Q_T` в сборку, `Q_T[N]` в накопитель | 2 |
| то же | `compute_conductive_transmissibility` 329-358 | возврат `Q_T` $[N+1]$, без ветви `if N > 1` | 2 |
| то же | `assemble_tridiag` 515-591 | сигнатура (шаг 2), тело — операции над массивами (шаг 3) | 2, 3 |
| то же | докстринг модуля 37-41 | `Q_T[0] = 0` в описании ГУ забоя | 3 |
| `numerical_solver/tests/test_energy.py` | 705, 711, 723-727, 740-744, 1027-1037, 1071-1081, 1097-1106, 1227-1237, 1346-1361, 1378-1402 | распаковка пары → массив, индексы | 2 |
| то же | `TestAssembleTridiag` (после 1109), `TestComputeConductiveTransmissibility` (после 744) | +3 теста | 1, 2 |
| `numerical_solver/tests/test_val002.py` | 167-168, 189-192, 319-329 | то же; `Q_T_internal[0]` → `Q_T[1]` | 2 |
| `numerical_solver/tests/test_energy_matrix_examples.py` | 358-363 (самопроверка эталона) | `Q_solver[1:N]` | 2 |
| `numerical_solver/tests/test_examples.py` | 751-752 | устаревшая ссылка `tridiag.py:179` | 4 |
| `numerical_solver/examples/02_single_phase_jt/main.py` | 143 | устаревшая ссылка `tridiag.py:223` | 4 |
| `vault/knowledge/decisions/словарь-код-физика.md` | 302, 326, 360-374 | обозначения `Q_T[f]` | 5 |

**Зона неприкосновенности:**
- `numerical_solver/gpn_multiphase_solver/energy/balance.py` — без изменений (решение 3); `add_substep(…, Q_T_ext: float, …)` принимает `Q_T[N]` (тип тот же — `numpy.float64`);
- `_ref_conductive`, `_ref_assemble`, `_ref_d_scale`, `build_reference` в `tests/test_energy_matrix_examples.py` — без изменений (решение 2);
- `tests/baseline_vectorization_check.py` — не трогать (решение 4);
- пробы прошлых задач в `vault/issues/*/probes/` (12 скриптов зовут `compute_conductive_transmissibility`/`assemble_tridiag`/`build_reference` со старой сигнатурой) — архив разовых замеров, не правятся;
- прототип `HydroSolverPrototype/` — не затрагивается.

## Шаги

### Шаг 0: Подготовка — worktree, baseline, снимок `base`

**Цель:** зафиксировать число тестов и побитовый снимок матрицы и $T$ до правки.

**Файлы:** нет изменений.

**Что сделать:** пункты 3–5 раздела «Как начать работу». Снимок `base` снимать в worktree **до** любой правки кода; первая строка вывода должна указывать на `.worktrees\debt-020\numerical_solver`.

**Проверка:** 1699 тестов, быстрый уровень 1428 passed (или фактические числа базы, если она ушла вперёд — тогда они и есть baseline); `bits_base.npz` создан в `.worktrees\debt-020\vault\issues\debt-020\probes\` (файл `*.npz` в `.gitignore` — в коммит не идёт).

**Оценка:** ~3 мин.

---

### Шаг 1: Тесты граничных строк на текущем API — до правки

**Цель:** закрепить поведение, которое векторная сборка может нарушить незаметно для примеров, тестами, зелёными на **нынешнем** коде.

**Файлы:** `numerical_solver/tests/test_energy.py` (класс `TestAssembleTridiag`, после `test_boundary_conditions_a0_cN`, стр. 1087-1109).

**Контекст:** два пробела покрытия.
1. На рабочем пути $\Phi^+_0 = 0$: добыча ($\Phi < 0$), втекание через забой исключено (FEAT-020/FEAT-023, `eq:bc_pwf_shutin`). Поэтому сборка, прибавившая бы $\Phi^+$ всех левых граней и к строке 0 (`b += Phi_plus[:-1]` вместо `b[1:] += Phi_plus[1:N]`), прошла бы все примеры и сверку матрицы (эталон тоже не видит $\Phi^+_0 > 0$ — в примерах его нет). Существующий `TestAdvectiveFormDetectors::test_outflow_branch_assembles_correctly` проверяет только $j = 1..N-2$.
2. $N = 2$: внутренних ячеек нет, обе строки граничные, цикл пуст — случай, на котором срезы `[1:N]`, `[:-1]`, `[1:]` легко сдвинуть на единицу. $N = 1$ уже покрыт `test_single_cell_boundary_contribution_counted_once`.

Тесты пишутся **до** правки (запись DEBT-020: иначе неизвестно, фиксирует тест верное поведение или то, что получилось).

**Что сделать:** добавить в `TestAssembleTridiag` два теста:

```python
    def test_wellbore_face_phi_plus_not_in_matrix(self):
        """Φ⁺ забойной грани (индекс 0) в матрицу и правую часть не входит.

        ГУ забоя (ssec:bc_disc): забойная грань конвективного вклада не
        даёт — слева ячейки нет, перепада T через грань нет. На рабочем
        пути Φ⁺[0] = 0 (добыча, Φ < 0; втекание через забой исключено,
        eq:bc_pwf_shutin), поэтому ни один пример и ни сверка матрицы с
        эталоном не заметят, если сборка начнёт прибавлять Φ⁺[0] к b[0]
        (DEBT-020: сборка операциями над массивами граней). Сценарий:
        Φ⁺[0] = 500 Вт/К против 0, прочие входы одинаковы; N = 1, 2, 5 —
        с ячейкой, где забой и контур совпадают, и без неё.
        Ожидание: a, b, c, d совпадают побитово.
        """
        for N_cells in (1, 2, 5):
            grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
            solver = TridiagEnergySolver(grid, _make_pvt(), _rock())
            props = solver.compute_cell_properties(
                np.full(N_cells, P0), np.zeros(N_cells),
                np.full(N_cells, RS0), np.ones(N_cells),
                np.full(N_cells, T0))
            Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(
                props['lambda_eff'], N_cells)
            # Φ⁻ < 0 на всех гранях (приток к скважине), значения различны
            Phi_minus = np.linspace(-500.0, -100.0, N_cells + 1)
            z = np.zeros(N_cells)

            def assemble(phi_plus_0):
                Phi_plus = np.zeros(N_cells + 1)
                Phi_plus[0] = phi_plus_0
                return solver.assemble_tridiag(
                    N_cells, DT, np.full(N_cells, T0), T_EXT,
                    props['rho_cp_eff'], Q_T_int, Q_T_ext,
                    Phi_plus, Phi_minus, z, z, z)

            for name, x, y in zip("abcd", assemble(0.0), assemble(500.0)):
                assert np.array_equal(x, y), (
                    f"N = {N_cells}, {name}: Φ⁺ забойной грани вошёл в "
                    f"сборку (ГУ забоя, ssec:bc_disc)")

    def test_two_cells_rows_by_formulas(self):
        """N = 2: обе строки граничные — коэффициенты по формулам постановки.

        eq:tridiag_a…eq:tridiag_d с ГУ ssec:bc_disc. Ячейка 0: левая грань 0
        (забой) — Q_T = 0, Φ± грани 0 не входят, a[0] = 0. Ячейка 1: правая
        грань 2 (контур) — c[1] = 0, T_ext уходит в d[1] с весом
        (Q_T грани 2 − Φ⁻[2]). Внутренних ячеек нет: цикл прежней сборки
        пуст, срезы массивов граней в новой (DEBT-020) — на краю.
        Ожидание собрано здесь по формулам, не из ядра. Потоки на гранях
        различны и ненулевы на ВСЕХ гранях, включая Φ⁻[0] и Φ⁺[2], которые
        в строки входить не должны: подмена грани на соседнюю дала бы
        другое число.
        """
        N_cells = 2
        grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
        solver = TridiagEnergySolver(grid, _make_pvt(), _rock())
        props = solver.compute_cell_properties(
            np.full(N_cells, P0), np.zeros(N_cells),
            np.full(N_cells, RS0), np.ones(N_cells), np.full(N_cells, T0))
        Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(
            props['lambda_eff'], N_cells)
        Q1, Q2 = Q_T_int[0], Q_T_ext       # проводимости граней 1 и 2

        Phi_plus = np.array([0.0, 120.0, 70.0])
        Phi_minus = np.array([-300.0, -500.0, -40.0])
        T_old = np.array([T0 - 3.0, T0 + 1.0])
        J_jt = np.array([7.0, -2.0])
        Q_ad = np.array([0.5, -0.1])
        Q_deg = np.array([-0.3, 0.2])

        a, b, c, d = solver.assemble_tridiag(
            N_cells, DT, T_old, T_EXT, props['rho_cp_eff'],
            Q_T_int, Q_T_ext, Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)

        V = grid.volumes
        cap = V * props['rho_cp_eff'] / DT
        # Ячейка 0: грань 0 — забой (Нейман), грань 1 — внутренняя
        assert a[0] == 0.0
        assert c[0] == pytest.approx(-Q1 + Phi_minus[1], rel=1e-12)
        assert b[0] == pytest.approx(cap[0] + Q1 - Phi_minus[1], rel=1e-12)
        assert d[0] == pytest.approx(
            cap[0] * T_old[0] + J_jt[0] + V[0] * (Q_ad[0] + Q_deg[0]),
            rel=1e-12)
        # Ячейка 1: грань 1 — внутренняя, грань 2 — контур (Дирихле)
        assert a[1] == pytest.approx(-Q1 - Phi_plus[1], rel=1e-12)
        assert c[1] == 0.0
        assert b[1] == pytest.approx(
            cap[1] + Q1 + Q2 + Phi_plus[1] - Phi_minus[2], rel=1e-12)
        assert d[1] == pytest.approx(
            cap[1] * T_old[1] + (Q2 - Phi_minus[2]) * T_EXT
            + J_jt[1] + V[1] * (Q_ad[1] + Q_deg[1]), rel=1e-12)
```

Имена `LogRadialGrid`, `TridiagEnergySolver`, `_make_pvt`, `_rock`, `R_WELL`, `R_EXT`, `H`, `K_PERM`, `P0`, `RS0`, `T0`, `T_EXT`, `DT` уже определены/импортированы в `test_energy.py` (используются в `test_boundary_conditions_a0_cN`).

Тексты тестов проверены при планировании (`vault/issues/debt-020/probes/plan_step_tests.py`, 4 passed; повторено аудитом на `123247a`): оба теста шага 1 — на нынешнем коде; `test_face_indexed_array` шага 2 — на кандидатной `compute_conductive_transmissibility`; отрицательный контроль — сборка с `b[0] += Phi_plus[0]` даёт разные `b` при $\Phi^+_0 = 0$ и 500, то есть `test_wellbore_face_phi_plus_not_in_matrix` её ловит.

**Проверка после шага:**
- `<py> -m pytest tests/test_energy.py -q -k "wellbore_face_phi_plus or two_cells_rows"` — 2 passed **на нынешнем коде**. Если падает — остановиться: тест фиксирует не то поведение (сверить с `assemble_tridiag` и `ssec:bc_disc`), правку ядра не начинать.
- Регресс: быстрый — 1430 passed.

**Подводные камни:** `rel=1e-12` в `test_two_cells_rows_by_formulas`, а не точное равенство: формула теста не обязана повторять порядок сложений ядра.

**Зависимости:** требует шаг 0; блокирует шаги 2, 3.

**Оценка:** ~90 строк, ~15 мин.

---

### Шаг 2: Хранение — `Q_T` $[N+1]$; сборка пока прежним циклом с новыми индексами

**Цель:** сменить хранение и сигнатуры (`compute_conductive_transmissibility` → массив, `assemble_tridiag(…, Q_T, …)`), не трогая структуру сборки, — чтобы правка индексов и правка тела сборки проверялись по отдельности.

**Файлы:** `numerical_solver/gpn_multiphase_solver/energy/tridiag.py`; `numerical_solver/tests/test_energy.py`; `numerical_solver/tests/test_val002.py`; `numerical_solver/tests/test_energy_matrix_examples.py`.

**Контекст:** промежуточное состояние ради бисекции: если шаг 3 разойдётся с `base`, будет видно, что хранение уже было верным. Тело `assemble_tridiag` на этом шаге меняется **только в индексах**.

**Что сделать:**

2.1. `compute_conductive_transmissibility` (`tridiag.py:329-358`).

До:
```python
    def compute_conductive_transmissibility(self, lambda_eff, N):
        """Теплопроводность: Q_T = 2πh / (w_L/λ_L + w_R/λ_R).

        Последовательные кольцевые сопротивления R_α = ln(r_face/r_center_α) / (2πh·λ_α).
        Возвращает Q_T_internal [N-1] и Q_T_ext (скаляр).
        """
        grid = self._grid

        # Внутренние грани
        if N > 1:
            w_L = grid.log_weights_left    # ln(r_face / r_center_left)
            w_R = grid.log_weights_right   # ln(r_center_right / r_face)
            lam_L = lambda_eff[:-1]
            lam_R = lambda_eff[1:]
            # Последовательные кольцевые сопротивления: R = w/λ, Q_T = 2πh / ΣR.
            # При λ = 0 (конфиг без теплопроводности) сопротивление бесконечно,
            # а проводимость — ноль. Считаем через errstate, чтобы промежуточные
            # inf не печатали предупреждение: 2πh/inf = 0 — верный ответ.
            with np.errstate(divide='ignore'):
                R_series = w_L / lam_L + w_R / lam_R
                Q_T_internal = 2.0 * np.pi * grid.h / R_series
        else:
            Q_T_internal = np.empty(0)

        # Контур: λ_face = λ_eff[N-1] (нет ячейки за контуром)
        geom_ext = 2.0 * np.pi * grid.h / np.log(
            grid.R_ext / grid.r_centers[-1])
        Q_T_ext = geom_ext * lambda_eff[-1]

        return Q_T_internal, Q_T_ext
```

После:
```python
    def compute_conductive_transmissibility(self, lambda_eff, N):
        """Проводимости граней Q_T [N+1], Вт/К. Ур. (eq:heat_cond_disc) problem_statement.tex."""
        grid = self._grid

        # Индекс — номер грани, как у Phi_plus/Phi_minus (DEBT-020): грань f
        # разделяет ячейки f-1 и f.
        #   Q_T[0] = 0       — забой, ГУ Неймана (ssec:bc_disc): кондуктивного
        #                      потока в скважину нет при любой T за гранью;
        #   Q_T[1..N-1]      — внутренние грани;
        #   Q_T[N]           — контур.
        Q_T = np.zeros(N + 1)

        # Внутренние грани. При N = 1 их нет: веса сетки и срезы λ пустые,
        # срез Q_T[1:1] тоже — отдельная ветвь не нужна.
        w_L = grid.log_weights_left    # ln(r_face / r_center_left)
        w_R = grid.log_weights_right   # ln(r_center_right / r_face)
        lam_L = lambda_eff[:-1]
        lam_R = lambda_eff[1:]
        # Последовательные кольцевые сопротивления: R = w/λ, Q_T = 2πh / ΣR.
        # При λ = 0 (конфиг без теплопроводности) сопротивление бесконечно,
        # а проводимость — ноль. Считаем через errstate, чтобы промежуточные
        # inf не печатали предупреждение: 2πh/inf = 0 — верный ответ.
        with np.errstate(divide='ignore'):
            R_series = w_L / lam_L + w_R / lam_R
            Q_T[1:N] = 2.0 * np.pi * grid.h / R_series

        # Контур: λ_face = λ_eff[N-1] (нет ячейки за контуром)
        geom_ext = 2.0 * np.pi * grid.h / np.log(
            grid.R_ext / grid.r_centers[-1])
        Q_T[N] = geom_ext * lambda_eff[-1]

        return Q_T
```

Почему без `if N > 1`: `LogRadialGrid` при $N = 1$ отдаёт пустые `log_weights_left/right` (`grid/log_radial.py:100-102`); других реализаций `Grid` нет (grep `class .*\(Grid\)` — только `LogRadialGrid`). Пустые срезы дают пустой `R_series`, присваивание в `Q_T[1:1]` — пустое.

2.2. `solve` (`tridiag.py:114-116`, `159-170`).

До:
```python
        # Подшаг 4: кондуктивная проводимость
        Q_T_internal, Q_T_ext = self.compute_conductive_transmissibility(
            props['lambda_eff'], N)
```
После:
```python
        # Подшаг 4: кондуктивная проводимость граней, Q_T [N+1]
        Q_T = self.compute_conductive_transmissibility(props['lambda_eff'], N)
```

До (в вызове `collect.add_substep`):
```python
                Q_T_ext=Q_T_ext, J_jt=J_jt, Q_ad=Q_ad, Q_deg=Q_deg,
```
После:
```python
                # Накопителю нужна только контурная грань: внутренние
                # телескопируются, забойная равна нулю (balance.py,
                # add_accumulation).
                Q_T_ext=Q_T[N], J_jt=J_jt, Q_ad=Q_ad, Q_deg=Q_deg,
```

До (вызов сборки):
```python
            props['rho_cp_eff'], Q_T_internal, Q_T_ext,
```
После:
```python
            props['rho_cp_eff'], Q_T,
```

2.3. `assemble_tridiag` — сигнатура и индексы (`tridiag.py:515-591`); структура (ветвь $N = 1$, цикл, блоки) — прежняя.

- сигнатура: `rho_cp_eff, Q_T_internal, Q_T_ext,` → `rho_cp_eff, Q_T,`;
- ветвь $N = 1$: `Q_T_ext` → `Q_T[1]` (две строки, 534 и 536);
- цикл: `Q_T_L = Q_T_internal[j - 1]` → `Q_T_L = Q_T[j]          # грань j (левая)`; `Q_T_R = Q_T_internal[j]` → `Q_T_R = Q_T[j + 1]      # грань j+1 (правая)`;
- забой: `Q_T_R0 = Q_T_internal[0]` → `Q_T_R0 = Q_T[1]`;
- контур: `Q_T_LN = Q_T_internal[-1]` → `Q_T_LN = Q_T[N - 1]`; в `b[N - 1]` и `d[N - 1]` `Q_T_ext` → `Q_T[N]`.

2.4. Тесты-вызовы. Везде `Q_T_int, Q_T_ext = solver.compute_conductive_transmissibility(...)` → `Q_T = solver.compute_conductive_transmissibility(...)` и в `assemble_tridiag` вместо пары — `Q_T`. Индексы:

| Файл:строка (на `123247a` = на `d7528d4`; после шага 1 строки `test_energy.py` ниже 1109 сдвинутся на длину вставки — искать по коду) | До | После |
|---|---|---|
| `test_energy.py:705, 711` | `Q_T_int, _ = …`; `assert_allclose(Q_T_int, expected, …)` | `Q_T = …`; `assert_allclose(Q_T[1:N_cells], expected, …)` |
| `test_energy.py:713-714, 723, 727` (`test_Q_T_ext`; имя теста не менять) | докстринг `Q_T_ext = (2*pi*h / ln(R_ext/r_c[-1])) * lambda_eff[-1].`; `_, Q_T_ext = …`; `assert Q_T_ext == approx(…)` | докстринг `Контурная грань: Q_T[N] = (2*pi*h / ln(R_ext/r_c[-1])) * lambda_eff[-1].`; `Q_T = …`; `assert Q_T[N_cells] == approx(…)` |
| `test_energy.py:740-744` | пара; `assert_allclose(Q_T_int, 0.0, …)`, `assert Q_T_ext == approx(0.0, …)` | `Q_T = …`; `np.testing.assert_allclose(Q_T, 0.0, atol=1e-30)` — все грани, включая забой и контур |
| `test_energy.py:1027-1037`, `1071-1081`, `1097-1106` | пара → `assemble_tridiag(…, Q_T_int, Q_T_ext, …)` | `Q_T` → `assemble_tridiag(…, Q_T, …)` |
| `test_energy.py:1227-1232` | `args = (N, DT, s['T_old'], T_EXT, s['props']['rho_cp_eff'], Q_T_int, Q_T_ext)` | `args = (N, DT, s['T_old'], T_EXT, s['props']['rho_cp_eff'], Q_T)` |
| `test_energy.py:1346-1361` | `-Q_T_int[j - 1] - Phi_plus[j]`; `Q_T_int[j - 1] + Q_T_int[j]` | `-Q_T[j] - Phi_plus[j]`; `Q_T[j] + Q_T[j + 1]` |
| `test_energy.py:1378-1402` | `Q_T_int, Q_T_ext = …(…, 1)`; `assemble_tridiag(1, …, Q_T_int, Q_T_ext, …)`; в проверках `Q_T_ext` | `Q_T = …(…, 1)`; `assemble_tridiag(1, …, Q_T, …)`; в проверках `Q_T[1]` |
| тесты шага 1 | `Q_T_int, Q_T_ext = …`; `Q1, Q2 = Q_T_int[0], Q_T_ext`; в `assemble` — пара | `Q_T = …`; `Q1, Q2 = Q_T[1], Q_T[2]`; в `assemble` — `Q_T` |
| `test_val002.py:167-168, 191` (`check_energy_balance`) | `Q_T_internal, Q_T_ext = …`; `assemble_tridiag(…, Q_T_internal, Q_T_ext, …)` | `Q_T = …`; `assemble_tridiag(…, Q_T, …)` |
| `test_val002.py:319-329` (`TestCaseD_PureConduction::test_conductive_transmissibility_single_ln`) | `Q_T_internal, Q_T_ext = …`; комментарий `Q_T_internal[0] / …`; `ratio = Q_T_internal[0] / Q_analyt_0` | `Q_T = …`; комментарий `Q_T[1] / …` (грань 1 — между центрами 0 и 1); `ratio = Q_T[1] / Q_analyt_0` |
| `test_energy_matrix_examples.py:358-363` | `Q_solver, _ = …compute_conductive_transmissibility(lam_cells, N)`; `assert_allclose(Q_solver, …)` | `Q_solver = …`; `assert_allclose(Q_solver[1:N], …)`; комментарий: «массив по граням [N+1] (DEBT-020), внутренние — Q_solver[1:N]» |

Остальное в `test_energy_matrix_examples.py` — не трогать (решение 2): эталон считает `Q_T_internal, Q_T_ext` своей функцией `_ref_conductive` и собирает своей `_ref_assemble`; с ядром он сравнивается только через `a, b, c, d` (проба `matrix_probe`).

2.5. Добавить в `TestComputeConductiveTransmissibility` (после `test_zero_lambda_gives_zero_Q_T`, стр. 729-744):

```python
    def test_face_indexed_array(self):
        """Q_T — массив по граням [N+1], как Φ±: Q_T[0] = 0, Q_T[N] — контур.

        DEBT-020: проводимость хранилась парой (внутренние [N-1] со сдвигом
        индекса и контур отдельным числом). Индекс — номер грани: грань f
        разделяет ячейки f-1 и f. Q_T[0] равно нулю ТОЧНО — не малое число,
        а ГУ Неймана у забоя (ssec:bc_disc); на этом нуле держится сборка
        строки 0 по общей формуле. N = 1: внутренних граней нет, массив из
        двух элементов. λ различны по ячейкам, контурная грань берёт λ
        ячейки N-1.
        """
        for N_cells in (1, 5):
            grid = LogRadialGrid(R_WELL, R_EXT, H, N_cells, K_PERM)
            solver = TridiagEnergySolver(grid, _make_pvt(), _rock())
            lam = np.linspace(0.8, 1.6, N_cells)

            Q_T = solver.compute_conductive_transmissibility(lam, N_cells)

            assert Q_T.shape == (N_cells + 1,)
            assert Q_T[0] == 0.0, "забойная грань: ГУ Неймана, Q_T[0] = 0"
            geom_ext = 2.0 * np.pi * grid.h / np.log(
                grid.R_ext / grid.r_centers[-1])
            assert Q_T[N_cells] == pytest.approx(geom_ext * lam[-1], rel=1e-12)
            assert np.all(Q_T[1:N_cells] > 0.0)
```

**Проверка после шага:**
- `<py> -m pytest tests/test_energy.py tests/test_val002.py tests/test_energy_matrix_examples.py -m "not slow" -q` — 70 passed (67 + 3).
- `grep -rn "Q_T_internal\|Q_T_int\b" numerical_solver/gpn_multiphase_solver numerical_solver/tests/test_energy.py numerical_solver/tests/test_val002.py` — пусто; в `test_energy_matrix_examples.py` `Q_T_internal` остаётся **только** в эталоне (`_ref_conductive`, `_ref_assemble`, `build_reference`).
- `<py> ..\vault\issues\debt-020\probes\bits_capture.py capture step2` и `compare base step2` — ИТОГ: OK (вызовов столько же, матрица и $T$ побитово). Код в первой строке — worktree.
- Регресс: быстрый — 1431 passed.

**Подводные камни:**
- ⚠️ Механическая замена `Q_T_int` → `Q_T` без сдвига индекса: `test_val002.py:329` с `Q_T[0]` дал бы `ratio = 0` (тест упадёт — хорошо), `test_energy.py:1355` с `Q_T[j - 1]` — неверную грань (упадёт). Сдвиг — по таблице 2.4, не по поиску-замене.
- ⚠️ `Q_T[N]` в `add_substep` — `numpy.float64`, как и прежний `Q_T_ext = geom_ext * lambda_eff[-1]`: тип для `balance.py` не меняется.
- ✅ `matrix_probe` получает `a, b, c, d` — контракт DEBT-016 не меняется.

**Зависимости:** требует шаг 1; блокирует шаг 3.

**Оценка:** ~60 строк в `tridiag.py` и тестах, ~30 мин.

---

### Шаг 3: Сборка по формулам постановки на всех строках — без цикла и ветви $N = 1$

**Цель:** тело `assemble_tridiag` — операции над массивами граней по `eq:tridiag_a`…`eq:tridiag_d`; граничные условия — точечные поправки.

**Файлы:** `numerical_solver/gpn_multiphase_solver/energy/tridiag.py` (`assemble_tridiag`; докстринг модуля, стр. 37-41).

**Контекст:** при `Q_T[0] = 0` общие формулы верны для всех $j$; особыми остаются ГУ, а не хранение (раздел «Что хотим»). Порядок сложений повторяет прежний цикл — побитовость доказана пробой плана на всех 23 примерах (раздел «Почему результат побитово прежний»). Код ниже — ровно тот, что проверен (`new_assemble` в `plan_vector_assembly.py`), плюс комментарии.

**Что сделать:**

3.1. Заменить тело `assemble_tridiag` целиком (после шага 2 сигнатура уже `(self, N, dt, T_old, T_ext, rho_cp_eff, Q_T, Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)`).

До (после шага 2; ветвь $N = 1$, цикл и два граничных блока, `tridiag.py:518-591` на `d7528d4`): см. файл.

После:
```python
    def assemble_tridiag(self, N, dt, T_old, T_ext,
                         rho_cp_eff, Q_T,
                         Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg):
        """Коэффициенты a, b, c, d с ГУ. Ур. (eq:tridiag_a)–(eq:tridiag_d) problem_statement.tex."""
        V = self._grid.volumes

        cap = V * rho_cp_eff / dt  # [N], Вт/К — накопительный член

        # ── Все строки по eq:tridiag_a … eq:tridiag_c ──
        # Ячейка j ограничена гранями j (слева) и j+1 (справа). Q_T и Φ±
        # индексируются номером грани [N+1], поэтому срез [:-1] — левые
        # грани ячеек, [1:] — правые. Q_T[0] = 0 (Нейман на забое), и общие
        # формулы верны на всех строках, включая j = 0 и N = 1: отдельной
        # ветви для одной ячейки нет (DEBT-020). Граничные условия ниже —
        # точечные поправки к собранным массивам; при N = 1 они относятся к
        # одной строке и складываются, а не затирают друг друга.
        #
        # Порядок сложения в b тот же, что в прежнем цикле по ячейкам, а в
        # строку 0 прибавляется точный ноль Q_T[0]: результат побитово
        # прежний (проба vault/issues/debt-020/probes, все 23 примера).
        a = -Q_T[:-1] - Phi_plus[:-1]
        c = -Q_T[1:] + Phi_minus[1:]

        # Адвективная форма (BUG-012, eq:tridiag_b): Φ⁺ с ЛЕВОЙ грани j,
        # Φ⁻ с ПРАВОЙ грани j+1 — те же грани, что в a[j] и c[j].
        # Дивергентная версия брала противоположные (Φ⁺ справа, Φ⁻
        # слева), и разность двух версий b[j] равна ровно
        # D_j = Φ_{j+1/2} − Φ_{j−1/2} — паразитному члену T_j·D_j,
        # дублирующему работу расширения газа (она уже в Q_ad и J_jt).
        b = cap + Q_T[:-1]
        b += Q_T[1:]
        # Φ⁺ забойной грани (индекс 0) в b[0] не входит — см. ГУ забоя
        b[1:] += Phi_plus[1:N]
        b -= Phi_minus[1:]

        d = cap * T_old + J_jt + V * (Q_ad + Q_deg)

        # ── ГУ забой (j=0): ∂T/∂r = 0 (Нейман, кондуктивный поток = 0) ──
        # Кондуктивный вклад грани 0 уже нулевой: Q_T[0] = 0.
        # Конвективного вклада забойная грань (индекс 0) не даёт вовсе:
        # слева ячейки нет, а условие Неймана означает отсутствие перепада
        # T через эту грань. В адвективной форме каждое слагаемое
        # пропорционально разности T соседей, поэтому член грани 0
        # тождественно нулевой — Φ⁺[0] не входит ни в a[0], ни в b[0]
        # (выше: b[1:]). Физически: вынос флюида с T_0 не создаёт члена при
        # неизвестных — перенос без градиента. Втекание через забой
        # (Phi_plus[0] > 0) для данной постановки не определено — см. DEBT-019.
        a[0] = 0.0

        # ── ГУ контур (j=N-1): T = T_ext (Дирихле) ──
        # Вклад контурной грани: (Q_T[N] − Phi_minus[N])·(T_ext − T_{N-1}).
        # Множитель при T_{N-1} уже в b[N-1] (общая формула), известная
        # T_ext уходит в правую часть, связи справа нет.
        # d[N-1] пересобирается целиком, а не дополняется: порядок
        # слагаемых — прежний (побитово).
        c[N - 1] = 0.0
        d[N - 1] = (cap[N - 1] * T_old[N - 1]
                    + Q_T[N] * T_ext
                    + (-Phi_minus[N]) * T_ext
                    + J_jt[N - 1]
                    + V[N - 1] * (Q_ad[N - 1] + Q_deg[N - 1]))

        return a, b, c, d
```

3.2. Докстринг модуля (`tridiag.py:37-41`).

До:
```
ГУ:
  - Забой (f=0): ∂T/∂r = 0 (Нейман) — кондуктивный поток = 0, и
    конвективного вклада забойная грань не даёт (нет перепада T).
    Но JT-вклад там НЕ нулевой: давление p_wf задано на грани.
  - Контур (f=N): T = T_ext (Дирихле)
```
После:
```
ГУ:
  - Забой (f=0): ∂T/∂r = 0 (Нейман) — кондуктивный поток = 0 (Q_T[0] = 0),
    и конвективного вклада забойная грань не даёт (нет перепада T).
    Но JT-вклад там НЕ нулевой: давление p_wf задано на грани.
  - Контур (f=N): T = T_ext (Дирихле)

Величины на гранях — массивы [N+1] по номеру грани f (грань f разделяет
ячейки f-1 и f): Φ±, Φ_α, Q_T (DEBT-020).
```

**Проверка после шага:**
- `grep -n "N == 1\|for j in range\|if N" numerical_solver/gpn_multiphase_solver/energy/tridiag.py` — пусто (на `d7528d4` все три совпадения — `:338` `if N > 1`, `:533` `if N == 1`, `:542` цикл — в двух методах этой задачи).
- `<py> -m pytest tests/test_energy.py -q` — зелёный, в том числе тесты шага 1 и `test_single_cell_boundary_contribution_counted_once`.
- `bits_capture.py capture step3`, `compare base step3` — ИТОГ: OK.
- Регресс: **полный** — шаг меняет сборку матрицы энергии; сверку с эталоном на всех 23 примерах (`test_matrix_matches_reference`) несёт только медленный уровень. Ожидание: 1702 passed. Если после шагов 4–5 код не менялся, этот прогон засчитывается итоговым (`/implement` §3.1).

**Подводные камни:**
- ⚠️ `b[1:] += Phi_plus[1:N]`, а **не** `b += Phi_plus[:-1]`: на примерах разницы нет ($\Phi^+_0 = 0$), ловит только `test_wellbore_face_phi_plus_not_in_matrix` (шаг 1) и синтетика пробы.
- ⚠️ Не менять входные массивы: `a[0] = 0.0`, `c[N-1] = 0.0` пишутся в новые массивы (`-Q_T[:-1] - …` создаёт копию); `Phi_plus` и `Q_T` используются только срезами справа от `=` и в `+=` к новым `b`. Прямая запись в `Phi_plus[0]` или `Q_T[...]` испортила бы `Phi_plus`, который `solve` передаёт дальше (`collect` получает `Phi_o`, `Phi_g` — отдельные массивы, но всё равно не трогать).
- ⚠️ `a[0] = 0.0` и `c[N-1] = 0.0` — положительный ноль: `test_matrix_matches_reference` требует `a[0] == 0.0` (верно и для `-0.0`), но проба сравнивает байты; без явного присваивания `a[0]` было бы `-0.0 - Φ⁺[0]`.
- ⚠️ `d[N-1]` — присваивание полной формулой, не `+=`: `+=` к общей `d` изменил бы порядок слагаемых (побитовость держалась бы только при $T_{ext} - T_{ref} = 0$, то есть на рабочем пути, но не в тестах и синтетике).
- ✅ При $N = 1$: `b[1:]` и `Phi_plus[1:1]` пустые; `a[0] = 0`, `c[0] = 0`, `d[0]` — формула контура; совпадает с прежней ветвью (синтетика пробы, $N = 1$, 200 случаев).

**Зависимости:** требует шаг 2; блокирует шаг 5 (словарь описывает итог).

**Оценка:** −45/+40 строк, ~30 мин + полный прогон ~10 мин.

---

### Шаг 4: Устаревшие ссылки на номера строк `tridiag.py`

**Цель:** заменить две ссылки вида `tridiag.py:NNN`, указывающие не туда, ссылками по имени метода.

**Файлы:** `numerical_solver/tests/test_examples.py`; `numerical_solver/examples/02_single_phase_jt/main.py`.

**Контекст:** DEBT-010 перевёл ссылки в `balance.py` на имена методов; эти две остались. `tridiag.py:179` сейчас — вызов `matrix_probe`, `tridiag.py:223` — `compute_cell_properties`; правка DEBT-020 сдвигает номера ещё раз.

**Что сделать:**

`test_examples.py:751-752`. До:
```python
                # Q_T_ext = geom * lambda_eff[-1] при lambda = 0 даёт ровно
                # 0.0, без NaN и inf (tridiag.py:179).
```
После:
```python
                # Q_T[N] = geom * lambda_eff[-1] при lambda = 0 даёт ровно
                # 0.0, без NaN и inf (compute_conductive_transmissibility).
```

`examples/02_single_phase_jt/main.py:143`. До:
```python
    # Множитель адиабатики с учётом JT: (1 + ρ·cp·μ_JT), см. tridiag.py:223
```
После:
```python
    # Множитель адиабатики с учётом JT: (1 + ρ·cp·μ_JT), см. TridiagEnergySolver.compute_adiabatic
```

**Проверка после шага:**
- `grep -rn "tridiag\.py:[0-9]" numerical_solver --include=*.py --include=*.md` — пусто.
- Регресс: быстрый (`test_examples.py` — комментарий; проверки скриптов `examples/` DEBT-037/DEBT-046 — в быстром уровне) — 1431 passed.

**Зависимости:** требует шаг 2 (имя `Q_T[N]`).

**Оценка:** 3 строки, ~5 мин.

---

### Шаг 5: Словарь «код — физика»

**Цель:** обозначения проводимости в словаре — как в коде после правки.

**Файлы:** `vault/knowledge/decisions/словарь-код-физика.md`.

**Что сделать:**

- стр. 302, таблица §5.2. До: ``| `Q_T_internal[f−1]`, `Q_T_ext` (`compute_conductive_transmissibility`) | Q^T_f | Вт/К | `eq:heat_cond_disc` | Кондуктивная проводимость грани |``. После: ``| `Q_T[f]` (`compute_conductive_transmissibility`) | Q^T_f | Вт/К | `eq:heat_cond_disc` | Кондуктивная проводимость грани; [N+1], `Q_T[0] = 0` (Нейман), `Q_T[N]` — контур (DEBT-020) |``;
- стр. 326, §5.4: «Контур: `Q_T_ext = 2πh·λ_eff[N−1] / ln(R_ext/r_centers[N−1])`. Забой: `Q_λ[0] = 0` (Нейман).» → «Контур: `Q_T[N] = 2πh·λ_eff[N−1] / ln(R_ext/r_centers[N−1])`. Забой: `Q_T[0] = 0` (Нейман).»;
- стр. 360: «Внутренние ячейки j = 1..N−2 (`assemble_tridiag`); …» → «Все ячейки j = 0..N−1 (`assemble_tridiag`, операции над массивами граней; срез `[:-1]` — левые грани, `[1:]` — правые); …»;
- стр. 364-366, столбец «Формула»: `−Q_T_internal[j−1] − Phi_plus[j]` → `−Q_T[j] − Phi_plus[j]`; `−Q_T_internal[j] + Phi_minus[j+1]` → `−Q_T[j+1] + Phi_minus[j+1]`; `cap[j] + Q_T_internal[j−1] + Q_T_internal[j] + Phi_plus[j] − Phi_minus[j+1]` → `cap[j] + Q_T[j] + Q_T[j+1] + Phi_plus[j] − Phi_minus[j+1]`;
- стр. 371-374, «Граничные ячейки» — заменить на:
  ```
  Граничные условия — поправки к общим формулам:
  - **j = 0** (забой, Нейман): `Q_T[0] = 0`; `a[0] = 0`; `Phi_plus[0]` в `b[0]` не входит (грань 0 конвективного вклада не даёт). Итог: `c[0] = −Q_T[1] + Phi_minus[1]`, `b[0] = cap[0] + Q_T[1] − Phi_minus[1]`.
  - **j = N−1** (контур, Дирихле `T = T_ext`): `c[N−1] = 0`; `b[N−1]` — по общей формуле (`cap + Q_T[N−1] + Q_T[N] + Phi_plus[N−1] − Phi_minus[N]`); к `d[N−1]` добавляется `(Q_T[N] − Phi_minus[N])·T_ext`.
  - **N = 1** — отдельной ветви нет (DEBT-020): обе поправки относятся к строке 0 и не затирают друг друга.
  ```

**Проверка:** Регресс: `--collect-only -q` (только документ) — 1702.

**Зависимости:** требует шаг 3.

**Оценка:** ~10 строк, ~10 мин.

---

### Итог реализации (`/implement`)

1. `bits_capture.py compare base step3` — ИТОГ: OK (если после шага 3 код менялся — снять `step_final` и сравнить с `base`).
2. Полный прогон (если не засчитан на шаге 3): 1702 passed.
3. Vault: статус DEBT-020 в реестре, комментарий `05-comment-done.md` в issue #99 — делает `/implement`.

## Тестовая стратегия

**Неизменность поведения:**
- `bits_capture.py` — хеши $a, b, c, d$ на каждом вызове `solve` (07 — 72, 10 — 73, 11 — 72, 14 — 361, 16 — 720 вызовов) и все записи $T$; синтетика 800 случаев ($N = 1, 2, 3, 10$; $T_{ext} \ne 0$; $\Phi^+_0 > 0$; $\lambda = 0$). Чувствительность — 1 ULP в одном элементе (отрицательный контроль).
- Существующие тесты, покрывающие затронутый код: `TestComputeConductiveTransmissibility` (3), `TestAssembleTridiag` (3), `TestAdvectiveFormDetectors` (в т. ч. `test_outflow_branch_assembles_correctly`, `test_single_cell_boundary_contribution_counted_once`), `test_val002.py` (функция `check_energy_balance` — пересобирает СЛАУ и проверяет невязку решения; её зовут `test_energy_balance` классов `TestCaseD_PureConduction`, `TestCaseB_PureJT`, `TestCaseA_ConvectionConduction`; `TestCaseD_PureConduction::test_conductive_transmissibility_single_ln` — проверка BUG-002), `test_energy_matrix_examples.py::test_ref_conductive_matches_annulus_solution` (быстрый), `::test_matrix_matches_reference` (slow, 23 примера, rtol 1e-12), балансы энергии в `test_examples.py` (slow).

**Новые тесты (+3):**

**Тест:** `test_wellbore_face_phi_plus_not_in_matrix`
**Файл:** `numerical_solver/tests/test_energy.py` (`TestAssembleTridiag`, существующий)
**Сценарий:** $\Phi^+_0 = 500$ Вт/К против 0 при прочих равных; $N = 1, 2, 5$
**Ожидание:** `a, b, c, d` побитово равны
**Baseline:** проходит на нынешнем коде (`d7528d4`, `123247a`; шаг 1)
**Предотвращает:** прибавление $\Phi^+$ забойной грани к `b[0]` в векторной сборке — на примерах невидимо ($\Phi^+_0 = 0$)

**Тест:** `test_two_cells_rows_by_formulas`
**Файл:** `numerical_solver/tests/test_energy.py` (`TestAssembleTridiag`)
**Сценарий:** $N = 2$, различные ненулевые $\Phi^\pm$ на всех трёх гранях (включая $\Phi^-_0$ и $\Phi^+_2$, которые входить не должны), $T^n \ne T_{ext}$, ненулевые источники
**Ожидание:** 8 коэффициентов по формулам `eq:tridiag_a`…`eq:tridiag_d` + `ssec:bc_disc`, rel 1e-12; `a[0] = c[1] = 0` точно
**Baseline:** проходит на нынешнем коде (`d7528d4`, `123247a`; шаг 1)
**Предотвращает:** сдвиг срезов граней на единицу в случае без внутренних ячеек

**Тест:** `test_face_indexed_array`
**Файл:** `numerical_solver/tests/test_energy.py` (`TestComputeConductiveTransmissibility`)
**Сценарий:** $N = 1, 5$, неоднородная $\lambda$
**Ожидание:** форма $(N+1,)$; `Q_T[0] == 0.0` точно; `Q_T[N]` — формула контура (rel 1e-12); внутренние $> 0$
**Baseline:** новый контракт (шаг 2)
**Предотвращает:** возврат к сдвинутой индексации; ненулевой забойный элемент, на котором держится общая формула строки 0

## Чеклист подводных камней

| Пункт | Оценка |
|---|---|
| Все call sites найдены | ✅ `compute_conductive_transmissibility`: `tridiag.py` (1), `test_energy.py` (9), `test_val002.py` (2), `test_energy_matrix_examples.py` (1, самопроверка); `assemble_tridiag`: `tridiag.py` (1), `test_energy.py` (6 + 2 новых), `test_val002.py` (1). Эталон DEBT-016 своей функцией — не call site. Пробы `vault/issues/*/probes/` — архив, вне задачи |
| Зависимости пакетов | ✅ нет |
| Обратная совместимость API | ⚠️ меняются сигнатуры двух методов `TridiagEnergySolver` — внутренний API модуля; внешних вызовов, кроме тестов, нет; ABC `EnergySolver` и `solve` не меняются |
| Состояние при ошибке | ✅ методы без состояния; `matrix_probe` и `collect` получают то же |
| Тесты | ✅ правка вызовов — шаг 2, в одном шаге с ядром (иначе красные) |
| Циклические импорты | ✅ импорты не меняются |
| Ссылки на уравнения | ✅ докстринги `compute_conductive_transmissibility` и `assemble_tridiag` — метками (`eq:heat_cond_disc`, `eq:tridiag_a`…`eq:tridiag_d`), страж `tests/test_eq_references.py` |
| Конфиги | ✅ не меняются |
| Связь с другими задачами | ⚠️ **DEBT-063** (две сетки, план готов 2026-10-11): кода `tridiag.py` не правит, но меняет сетку — значения $\mathcal{Q}_T$ и $T$ сдвинутся. Если DEBT-063 влита в базу во время реализации DEBT-020, побитовая сверка сравнивает только `base` и ветку **от одной базы**: после слияния базы в ветку снять `base` заново на новой базе (во временном worktree или на коммите базы) и сравнить с веткой. Текстовых пересечений нет (DEBT-063 в `test_val002.py` и `test_energy*.py` не правит). **DEBT-016** — эталон не трогаем (решение 2). **BUG-012** — тест $N = 1$ и ветвь $N = 1$ оттуда; тест сохраняется, ветвь уходит |
| Связь с другими задачами (аудит 1) | ⚠️ **DEBT-059** влита в базу между планом и аудитом (`29a1ffa`): +8 тестов (`test_packaging.py`), прототип из `pythonpath` pytest и из редактируемой установки; файлы плана не менялись, пробы на `123247a` повторены — побитово. ⚠️ **DEBT-023** (issue открыт, плана нет): правит `tests/test_examples.py:735-754` (ветки `cum_cond`) — там же комментарий шага 4 (`:751-752`); конфликт при слиянии — в одной строке комментария, разрешать по смыслу обеих правок. Она же даёт $\lambda \ne 0$ примерам 03–09: комментарий `bits_capture.py` «07 — λ = 0» устареет; сверка `base`/ветка от одной базы от этого не зависит. ⚠️ **DEBT-063** (план готов, baseline 1699 → 1703): правит `словарь-код-физика.md:30` и 2 комментария `test_examples.py` — с правками DEBT-020 (`:302-374`, `:751-752`) по известным строкам не пересекается |
| Производительность | ✅ цикл Python по $N$ ячейкам заменён операциями numpy — не медленнее |
| Прототип | ✅ не затрагивается; регрессия прототипа не нужна |

## Критерии завершения

- [ ] Шаги 0–5 выполнены
- [ ] `bits_capture.py compare base step3` — ИТОГ: OK (матрица и $T$ побитово на 07, 10, 11, 14, 16 и синтетике)
- [ ] Полный прогон: 1702 passed; быстрый уровень 1431 passed
- [ ] В `gpn_multiphase_solver/` нет `Q_T_internal`; в `assemble_tridiag` нет ветви `N == 1` и цикла по ячейкам; в `compute_conductive_transmissibility` нет `if N > 1`
- [ ] `grep -rn "tridiag\.py:[0-9]" numerical_solver` — пусто
- [ ] `balance.py`, эталон DEBT-016, `baseline_vectorization_check.py` — без изменений (`git diff --stat` базы и ветки)
- [ ] Словарь обновлён; реестр, issue #99 — `/implement`

## Обнаруженные проблемы

1. **Проектная заметка `vault/knowledge/decisions/модули-energy-tridiag.md` описывает сборку до BUG-012.** `b[j]` — в дивергентной форме ($\Phi^+_{j+1/2} - \Phi^-_{j-1/2}$, стр. 188); JT и дегазация — разностью потоков граней (`J_cell = J[j+1/2] − J[j−1/2]`, стр. 143; `mdot_conv`, стр. 167); на забое `b[0] += Phi_well_plus` (стр. 224), хотя грань 0 из `b[0]` исключена; `Q_ad` с множителем `V[j]` (стр. 151) при `V[j]·(Q_ad + Q_deg)` в `d` (стр. 189) — объём дважды; ссылки — номерами уравнений (`eq. 5-7`, `eq. 33-36` …), а не метками; на заметку ссылаются 14 заметок `vault/knowledge/`. Не блокирует DEBT-020 (код и словарь — источник истины); в шаге 5 не правится, чтобы не смешивать задачи. → зарегистрировано **DEBT-064**.
2. **Утилита `tests/baseline_vectorization_check.py` (DEBT-018) сверяет только последнее поле $T$** — отрицательный контроль этого плана показал, что сдвиг матрицы на 1 ULP записанных $T$ не меняет. Шапка утилиты утверждает, что «любое отличие в последнем бите означает изменение смысла», — но отличие до $T$ не доходит. Для DEBT-020 не используется (решение 4). Регистрировать ли — вопрос пользователю (не регистрировалось).
3. **Пробел покрытия: $\Phi^+_0 > 0$ в сборке не проверялся ни одним тестом** — закрывается тестом шага 1 в рамках задачи.

## Связь формула → код

| Формула (`numerical_solver/doc/problem_statement.tex`) | Код после правки |
|---|---|
| `eq:heat_cond_disc` (+ `eq:face_interp`) — $\mathcal{Q}^T$ внутренней грани | `compute_conductive_transmissibility`: `Q_T[1:N]` |
| `ssec:bc_disc` — Нейман у забоя, $Q^T_{\lambda,1/2} = 0$ | `Q_T[0] = 0`; `a[0] = 0`; `b[1:] += Phi_plus[1:N]` |
| `ssec:bc_disc` — контур, $\lambda$ ячейки $N-1$ | `Q_T[N]` |
| `eq:tridiag_a` | `a = -Q_T[:-1] - Phi_plus[:-1]` |
| `eq:tridiag_c` | `c = -Q_T[1:] + Phi_minus[1:]` |
| `eq:tridiag_b` | `b = cap + Q_T[:-1] + Q_T[1:] + Phi_plus[:-1]` (без грани 0) `- Phi_minus[1:]` |
| `eq:tridiag_d` + Дирихле на контуре | `d = cap*T_old + J_jt + V*(Q_ad + Q_deg)`; `d[N-1]` — с `(Q_T[N] − Phi_minus[N])·T_ext` |

## Связанные заметки

- Запись реестра DEBT-020; [[BUG-002]], [[BUG-012]], [[BUG-027]] — ошибки в этом члене и ветвь $N = 1$; [[DEBT-016]] — эталон матрицы; [[DEBT-018]] — образец побитовой проверки; [[DEBT-010]] — ссылки по меткам; [[DEBT-063]] — сетка
- [[словарь-код-физика]] — §5.2, §5.4, §6
- [[reference_worktree_pythonpath]] — проба в worktree
- Пробы: `vault/issues/debt-020/probes/` — `plan_vector_assembly.py` (+ `.out.txt`), `plan_negative_control.py` (+ `.out.txt`), `plan_step_tests.py`, `bits_capture.py`
