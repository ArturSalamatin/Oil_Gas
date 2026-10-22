---
tags:
  - план
  - рефакторинг
date: 2026-10-03
issue: DEBT-036
github: 59
branch: refactor/debt-036/table-pvt-residual-speedup
status: реализован
worktree: .worktrees/debt-036 (ветка от 38df988; vault задачи — в основном каталоге, не в ветке)
audit:
  date: 2026-10-03
  round: 2
  found: 5
  auto-fixed: 5
  manual-required: 0
---

# DEBT-036: ускорение невязки прототипа на табличном PVT — план

## Кратко

Невязка прототипа гидродинамики (`RadialBlackOilModel.residual`, `radial_blackoil/blackoil.py`) на табличном PVT (PVTO) стоит 3.5 мс при $N = 350$ против 0.9 мс на Стендинге. После [[DEBT-033]] вычисление невязок — основная статья времени расчёта: 30.7 из 40.0 с у примера 14. План убирает три источника лишней работы, **не меняя численного метода**:

1. запасы компонентов считают и выбрасывают вязкости $\mu_o$, $\mu_g$;
2. запасы старого состояния пересчитываются при каждом вызове невязки, хотя в пределах шага старое состояние одно;
3. интерполяция PVTO идёт циклом Python по сегментам $R_s$, и $B_o$, $\mu_o$ одних и тех же ячеек ищутся дважды.

Все изменения дают **побитово прежние** $B_o$, $\mu_o$, невязку, шаги Ньютона и истории примеров.

- Подтип: рефакторинг (ускорение без изменения поведения).
- Шагов: 8 (подготовка; запасы без вязкостей; запасы старого состояния один раз на шаг; PVTO массивами; $B_o$ и $\mu_o$ за один проход; документация; верификация; vault).
- Код: ~45 строк в `pvt.py`, ~20 строк в `blackoil.py`; два новых файла тестов прототипа (9 тестов, ~140 строк).
- **Код и тесты плана проверены при планировании** подменой методов в памяти: проба `vault/issues/debt-036/probes/planned_code_check.py`, база `67d2d23`.
  - $B_o$, $\mu_o$ побитово равны прежнему циклу на 30 таблицах (все таблицы проекта и две синтетические), 4.1 млн точек, включая узлы, точки на 1 ulp от узлов, NaN и $\pm\infty$.
  - Истории всех 20 примеров побитово равны исходным.
  - Тесты прототипа: 83 из 83 зелёные. Тесты плана: 9 из 9 на коде плана; на исходном коде падают 5 тестов нового поведения.
- Ускорение (замер):

| | невязка, пример 14 ($N = 350$, 19 ветвей) | невязка, пример 04 ($N = 50$, таблица 2×2) | невязка, пример 20 (Стендинг) | расчёт примера 14 | расчёт остальных примеров |
|---|---|---|---|---|---|
| было | 3.49 мс | 1.09 мс | 0.88 мс | 41.5 с | — |
| стало | 0.74 мс (×4.7) | 0.62 мс (×1.76) | 0.57 мс (×1.56) | 11.5 с (×3.6) | ×1.3–1.6 (05: в пределах шума) |

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай:
   - запись DEBT-036 в `vault/roadmap/известные баги и технический долг.md`;
   - issue #59: `gh issue view 59 --repo ArturSalamatin/Oil_Gas`;
   - `vault/knowledge/decisions/hydro-prototype-анализ.md`: §2 «PVT», §6 «Якобиан».
3. Ветка от базовой `numerical_scheme/implementation`.
   - Проверка: `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`.
   - DEBT-033 уже влит (`f4cb6a8`); проверка: `git merge-base --is-ancestor f4cb6a8 numerical_scheme/implementation; $?` → `True`.
   - Команда: `git checkout -b refactor/debt-036/table-pvt-residual-speedup` или worktree `.worktrees/debt-036` (так делает `/implement`).
4. Venv — `numerical_solver\.venv\Scripts\python` основного каталога. В worktree своего `.venv` нет: полный путь `d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python`.
5. Baseline до правок (шаг 1 расписывает подробно):
   - из `numerical_solver`:
     - `.venv\Scripts\python -m pytest tests/ --collect-only -q` → **1223** (на `4136f3c`, после влития DEBT-026; было 1210);
     - `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` → **999 passed** (время записать; на `67d2d23` было 82 с при 987);
   - из `numerical_solver\HydroSolverPrototype\Prototype_1.0.3`:
     - `..\..\.venv\Scripts\python -m pytest tests -q` → **83 passed**;
     - `..\..\.venv\Scripts\python regression\run_regression.py --quick` → **11/11 PASS** (~8 мин);
   - снимок историй примеров `save base` (шаг 1).
6. Запомни числа тестов, время быстрого уровня и снимок — это baseline.
7. Начни с шага 1. После каждого шага — тест шага и регресс по полю «Регресс». Полный прогон `tests/` — в конце (`/implement` §3.1).

⚠️ **Пробы лежат только в основном каталоге.** `vault/issues` — в `.gitignore` (строка 48), поэтому в worktree каталога `vault/issues/debt-036/probes/` нет. Пробы запускаются по абсолютному пути основного каталога, **из каталога `numerical_solver` того дерева, чей код проверяется**: они берут код из каталога запуска (`Path.cwd()`) и первой строкой печатают `код: <путь radial_blackoil> | <путь gpn_multiphase_solver>`. Если в этой строке не путь worktree, замер и сравнение недействительны.

⚠️ Переменная окружения `DEBT036_PROTO` (пробы `planned_code_check.py`, `history_snapshot.py`) подменяет каталог прототипа копией, к которой при планировании применялся план. При реализации она должна быть **пуста**; строка `код:` покажет, если это не так. `planned_code_check.py unit` берёт 11 таблиц кейсов регрессии из `regression/inputs/` проверяемого прототипа: в дереве ветки — `таблиц 30`.

```powershell
# из <дерево>\numerical_solver
$PY = "d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python"
$P  = "d:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\debt-036\probes"
& $PY $P\history_snapshot.py save base          # снимок историй 20 примеров, ~4 мин
& $PY $P\time_jacobian.py 14_high_gor_cooling 04_table_table 06_table_corey_rp 20_rs300_cooling 03_standing_corey
& $PY $P\planned_code_check.py unit             # B_o, mu_o кода файлов против прежнего цикла, 30 таблиц
```

## Контекст для читателя без контекста

### Прототип, невязка и где в ней PVT

Гидродинамику (давление $p$, газонасыщенность $S_g$, газосодержание $R_s$) решает прототип `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/` (код коллеги, «Sergey solver»; править разрешено, см. память проекта). Неявный шаг по времени решается методом Ньютона по $2N$ неизвестным. Невязка $F(z)$ — баланс нефтяного и газового компонентов по ячейкам, `physical_residual` (`blackoil.py:176-178`):

$$F = \frac{M(z) - M(\text{state\_old})}{\Delta t} + \text{(сток через грани)},$$

где $M$ — запасы компонентов в ячейке, `component_inventories` (`:147-151`): нефть $V_p S_o / B_o$, газ $V_p (R_s S_o / B_o + S_g / B_g)$, $V_p$ — поровый объём. Потоки через грани — `face_component_fluxes_sm3s` (`:156-169`). Подвижности фаз ячейки выше по потоку `_phase_mobilities_surface` (`:152-155`) вызываются трижды: на грани скважины (`_well_fluxes`, `:89-91`, скаляры), на $N-1$ внутренних гранях (массивы) и на внешней границе (скаляры). Каждый вызов берёт `bo` и `mu_o` по отдельности.

Итог: одна невязка — **10 вызовов** интерполяции нефти `_oil_prop`:

| где | вызовов | на чём |
|---|---|---|
| запасы нового состояния (`bo` и ненужный `mu_o`) | 2 | массив длины $N$ |
| запасы старого состояния (`bo`, `mu_o`) | 2 | массив длины $N$ |
| внутренние грани | 2 | массив длины $N-1$ |
| грань скважины, внешняя граница | 4 | скаляры |

Невязка вычисляется 7 раз на якобиан (базовая $F(z)$ и 6 цветов раскраски, [[DEBT-033]]) и от 1 до 12 раз в линейном поиске. Все эти вызовы в пределах шага получают один и тот же `state_old`: его копию делает `_advance_phases` (`:352`).

### PVTO и нынешняя интерполяция

Таблица нефти — формат ECLIPSE PVTO (`radial_blackoil/pvt.py`, класс `BlackOilPVT`). Строки группируются в «ветви» с постоянным $R_s$. Первая строка ветви — точка насыщения $p_b(R_s)$, следующие — недонасыщенная нефть при $p > p_b$. Внутри ветви берётся координата $x = p - p_b$ (`_branch_arrays`, `pvt.py:19-23`). Свойство в точке $(p, R_s)$ вычисляет `_oil_prop` (`pvt.py:43-64`):

1. Находит сегмент $[R_{s,j}, R_{s,j+1}]$, в котором лежит $R_s$. Вне таблицы берутся концевые ветви, экстраполяции нет.
2. Считает вес $w = (R_s - R_{s,j})/(R_{s,j+1} - R_{s,j})$, давление насыщения $p_b = p_{b,j} + w(p_{b,j+1} - p_{b,j})$ и $\Delta p = \max(p - p_b, 0)$.
3. Интерполирует по каждой из двух ветвей `np.interp(dp, x, y)`; на верхнем узле и выше берётся последнее значение ветви.
4. Результат: $v_0 + w(v_1 - v_0)$.

Пункты 1–4 выполняются циклом Python по сегментам (`for jj in np.unique(j)`). На каждый сегмент строятся булева маска по всем ячейкам и два вызова `np.interp`.

Таблицы проекта:
- у 12 из 13 табличных примеров — 2 ветви по 2 строки (один сегмент);
- у примера 14 — 19 ветвей по 4–31 строке (313 строк), ячейки занимают 14 сегментов;
- у кейсов регрессии T00–T11 и фикстур прототипа — 6 ветвей по 5 строк (T08c: 7 ветвей по 4–5).

### Тот же объект PVT считает свойства для уравнения энергии

`PrototypePVTAdapter` (`numerical_solver/gpn_multiphase_solver/pvt/prototype_adapter.py:34-41`) оборачивает **тот же** `BlackOilPVT` для `TableFullPVT` нашей библиотеки (фабрика, `factory.py:122-146`). Изменение `bo`/`mu_o` меняет и гидродинамику, и температуру, поэтому побитовость нужна на всех вызовах, а не только в невязке. Стендинг идёт в прототип через `HydroPVTtoBlackOilAdapter` (`gpn_multiphase_solver/pvt/hydro_to_blackoil_adapter.py`) и интерполяцию PVTO не использует.

### Почему побитовость достижима

«Побитово» — равенство байтов float64 (`a.tobytes() == b.tobytes()`), строже `np.array_equal`: различаются и $-0.0$ и $+0.0$. «1 ulp» — соседнее представимое число float64 (`np.nextafter`): точки на 1 ulp от узла таблицы проверяют, что выбор интервала не ошибается на границе.

- **Пункты 1–2** (запасы) вызывают тот же `bo`, `bg` с теми же аргументами.
- **Кеш запасов** возвращает ровно те массивы, что вернул бы пересчёт: ключ — байты $p$, $R_s$, $S_g$, а запасы — детерминированная функция этих значений, сетки, породы и PVT. Сетка, порода и PVT в течение жизни модели не меняются: в прототипе и библиотеке `grid`, `rock`, `pvt` модели присваиваются только в `__init__` (`blackoil.py:46`). Тесты плана подменяют `m.pvt` временно, и вызовы невязки на это время не попадают.
- **Векторная интерполяция** повторяет формулу `np.interp` (numpy `compiled_base.c`, `arr_interp`): `slope*(x - xp[j]) + fp[j]` с `slope = (fp[j+1]-fp[j])/(xp[j+1]-xp[j])`; при $x \ge xp_{\text{посл}}$ — `fp[-1]`; при NaN — NaN. Наклоны заранее считаются тем же выражением. Веса по $R_s$ — те же поэлементные операции float64 над теми же числами (разности $R_{s,j+1}-R_{s,j}$ и $p_{b,j+1}-p_{b,j}$ заранее вычисляются тем же вычитанием). Сложение, умножение и деление IEEE 754 детерминированы поэлементно. Проверено пробой на 4.1 млн точек: numpy 2.5.2, MSVC.

### Замер (2026-10-03, HEAD `67d2d23`, проба `planned_code_check.py bench`)

Невязка на состоянии Ньютона: вызов 8000 примера 14 (320 двухфазных ячеек из 350), вызов 600 примера 04, вызов 3000 примера 20. Медиана 300 повторов, этапы накопительно:

| этап | пример 14 | пример 04 | пример 20 (Стендинг) |
|---|---|---|---|
| исходный код | 3.49 мс | 1.09 мс | 0.88 мс |
| + шаг 2 (запасы без $\mu$) | 2.53 | 0.88 | 0.68 |
| + шаг 3 (запасы старого состояния) | 1.97 | 0.76 | 0.57 |
| + шаг 4 (PVTO массивами) | 1.07 | **0.90** | 0.57 |
| + шаг 5 ($B_o$ и $\mu_o$ за проход) | **0.74** | **0.62** | 0.57 |

`bo` на массиве $N = 350$ (пример 14): 504 → 133 мкс; `bo_mu_o` — 153 мкс. На таблице 2×2 векторная версия **медленнее** цикла: $N = 50$ — 85 → 99 мкс, скаляр — 78–83 → 91 мкс. Цикл из одного сегмента дешевле примерно 35 операций numpy по ~2.8 мкс каждая. Поэтому шаг 4 без шага 5 на маленьких таблицах ухудшает невязку (0.76 → 0.90 мс у примера 04), а шаг 5 возвращает выигрыш (0.62 мс). **Шаги 4 и 5 реализуются подряд**, замер после шага 5.

Расчёт примеров, все этапы (проба `planned_code_check.py history`, истории побитово у всех 20):

| пример | было, с | стало, с | × |
|---|---|---|---|
| 14_high_gor_cooling | 41.51 | 11.54 | 3.60 |
| 13b_pwf_alternating | 46.96 | 31.62 | 1.49 |
| 04a_high_gas_saturation | 27.64 | 19.54 | 1.41 |
| 12_large_drainage_radius | 12.62 | 8.27 | 1.53 |
| 13a_pwf_ramp_down | 12.02 | 8.52 | 1.41 |
| 15_oil_rate_ramp_up | 11.74 | 8.13 | 1.44 |
| 20_rs300_cooling | 6.21 | 4.69 | 1.32 |
| 04, 06–11 | 1.2–2.8 | 0.9–2.0 | 1.39–1.58 |
| 01, 02, 03, 19, 21 | 0.6–2.0 | 0.5–1.4 | 1.10–1.44 |
| 05_standing_table_rp | 0.52 | 0.55 | 0.93 (шум: расчёт 0.5 с) |

### Проверено при планировании (пробы в `vault/issues/debt-036/probes/`)

| проба | что | результат |
|---|---|---|
| `planned_code_check.py unit --planned` | `bo`, `mu_o`, `bo_mu_o` кода плана против дословной копии прежнего цикла: 13 таблиц примеров, 11 кейсов регрессии, 4 фикстуры, таблица с ветвью из одной строки, таблица с ветвями 2–8 строк; сетка через узлы и ±1 ulp, $p < p_b$, выше верха ветвей, $R_s$ вне таблицы; 100 000 случайных пар; NaN, $+\infty$, $10^{300}$; скаляр, 0-d, 2-D, разные формы, пустой массив | побитово, 30 таблиц, 4.1 млн точек |
| `planned_code_check.py cache --planned` | невязка с кешем против исходной; число вызовов `component_inventories`; изменение `state_old` на месте | побитово; 3 вызова вместо 6; после изменения на месте — пересчёт |
| `planned_code_check.py history` (этапы 1234) | истории 20 примеров (p, Sg, Rs, T, regime, t, G_o, G_g) исходного кода и кода плана | все 20 побитово |
| `planned_code_check.py proto_tests` | 83 теста прототипа на коде плана | 83 OK |
| `planned_code_check.py planned_tests [--planned]` | 9 тестов плана (`probes/planned_tests/` — дословно файлы шагов 2–5) | код плана: 9 OK; исходный код: 4 OK, 5 упали (тесты нового поведения — так и должно быть) |
| `apply_plan.py` | **текст плана**: блоки «До/После» шагов 2–5 и код тестов применены к копии прототипа (`probes/applied/`) | каждый «До» найден ровно 1 раз; тесты прототипа в копии — 92 passed |
| `history_snapshot.py` с `DEBT036_PROTO=<копия>` | истории 20 примеров на копии с применённым планом против исходного кода (`save plan_base`, `save plan_applied`, `compare`) | различий 0; пример 14 — 44.2 → 12.8 с |
| `run_regression.py --quick` в копии с применённым планом (`probes/applied/Prototype_1.0.3`, каталог `regression/` скопирован; аудит) | эталон `golden/` на коде плана | **11/11 PASS** |
| `planned_code_check.py bench` | таблица замера выше | — |

Рассмотрены и отклонены при планировании (замер той же пробой):
- **поиск интервала сравнением с узлами своей ветви** (матрица $N \times m$): побитово, но 265 мкс против 133 мкс;
- **кеш по ссылке на объект `state_old`**: при изменении состояния на месте возвращает устаревшие запасы (проба `cache`);
- **кеш по `np.array_equal`**: 11 мкс на ключ против 1.8 мкс у байтов.

## Текущее состояние (baseline)

- Тесты `numerical_solver`: 1223, быстрый уровень 999 (на `4136f3c`, после влития DEBT-026; при планировании на `67d2d23` — 1210 и 987 passed за 82 с). Тесты прототипа: 83 passed. Регрессия прототипа: 17/17 PASS на влитом DEBT-033 (CHANGELOG, раздел DEBT-033).
- API, которым пользуются другие модули:
  - `BlackOilPVT.bo(p, rs)`, `mu_o(p, rs)`: массивы или скаляры, результат — массив формы broadcast, у скаляров 0-d;
  - атрибуты `rs_values`, `pb`, `branches`, `bo_sat`, `mu_sat`, `max_rs`, `bubble_point_max_rs_bar`, `gp`, `gbg`, `gmu`, методы `rs_sat`, `pb_of_rs`, `max_pressure_of_rs`, `bg`, `mu_g`. Пользователи: `blackoil.py`, `diagnostics.py`, `runner.py`, `factory.py`, `PrototypePVTAdapter`, `examples/pvt_plot.py` (`branches`), тесты.
- `RadialBlackOilModel.component_inventories(state)`: пользователи — `physical_residual`, `step_global_balance` (`:378-380`), `simulation.py:35` (через `oil_properties`), `tests/test_prototype_well_branch.py:223`, `Prototype_1.0.3/tests/test_physics.py:13,23`.
- `oil_properties`/`gas_properties` (`:145-146`) остаются для `simulation.py:35`.

## Целевое состояние

- `component_inventories` берёт `self.pvt.bo`, `self.pvt.bg` напрямую.
- `physical_residual` берёт запасы старого состояния из `_old_inventories(state_old)`: кеш одной записи по байтам $p$, $R_s$, $S_g$. Сигнатуры `residual`/`physical_residual` не меняются, и с кодом якобиана DEBT-033 правка не пересекается.
- `BlackOilPVT`:
  - `_branch_prop_delta` и `_oil_prop` заменены на `_oil_props(p, rs, columns)`, считающий все ячейки массивами по таблицам `_build_interp_tables` (строится в `__init__`);
  - `bo`, `mu_o` сохраняют сигнатуру и значения;
  - новый `bo_mu_o(p, rs)` — обе величины за один поиск сегмента и строки;
  - таблица с одной ветвью $R_s$ отклоняется при построении (`ValueError`). Раньше в такой таблице все $B_o$, $\mu_o$ были NaN.
- `_phase_mobilities_surface` вызывает `bo_mu_o`, если он есть у PVT (у `BlackOilPVT` есть, у адаптера Стендинга нет — там прежние `bo`, `mu_o`).
- Побитово прежние: $B_o$, $\mu_o$ во всех точках, невязка, якобиан, шаги, истории примеров, регрессия прототипа 17/17 PASS.

## Варианты и выбор

Варианты — из issue #59, выбор подтверждён замером (см. «Замер» и «Проверено при планировании»).

| вариант | суть | выбор и почему |
|---|---|---|
| 1 | запасы без вязкостей | **да**; побитово, одна строка |
| 2а | запасы старого состояния явным аргументом `residual(..., inv_old)` | нет: аргумент тянется через `_newton_fixed_active_set`, оба якобиана, линейный поиск, `_advance_phases:372` |
| 2б | кеш по ссылке на `state_old` | нет: при изменении состояния на месте — устаревшие запасы |
| 2б′ | **кеш по байтам $p$, $R_s$, $S_g$** | **да**: чистая мемоизация, ключ 1.8 мкс против 0.1–0.6 мс запасов (замер шага 3) |
| 2в | атрибут, выставляемый `_advance_phases` | нет: прямые вызовы `residual` вне шага (тесты, `reference`) требуют ключа — сводится к 2б′ |
| 3а | цикл по ветвям вместо сегментов | нет: цикл остаётся, ~×1.7 только у примера 14 (оценка по числу вызовов `np.interp`, не замер) |
| 3б | **массивами: таблица строк ветвей + карта интервалов по объединённой сетке узлов** | **да**: 504 → 133 мкс, побитово |
| 3б-сравнение | номер интервала сравнением с узлами ветви ($N \times m$) | нет: 265 мкс |
| 3в | сдвиг ветвей на $kS$ и один `np.interp` | нет: $(x+kS)-(x_j+kS) \ne x - x_j$, побитовость теряется |
| 4 | **`bo_mu_o` за один проход**, вызов через `getattr` | **да**: −0.33 мс у примера 14, на таблицах 2×2 снимает проигрыш шага 4 |
| 4′ | `bo_mu_o` и в `HydroPVTtoBlackOilAdapter` (без `getattr`) | нет: правка библиотеки ради прототипа, Стендинг не ускоряется (там `bo`, `mu_o` — отдельные корреляции) |

### Не рассмотрено при планировании (найдено аудитом, в план не включено)

**Вариант 5 — PVT ячеек один раз на невязку, грани берут его выборкой.**

Подвижности на гранях считаются по ячейке выше по потоку: $(p, R_s)$ грани — это ровно значения ячейки $i$ или $i+1$ (`face_component_fluxes_sm3s`, `np.where(left, p[:-1], p[1:])`), на грани скважины — ячейки 0. Те же $(p, R_s)$ уже проходят интерполяцию в запасах нового состояния. Отсюда вариант:
- один `bo_mu_o` на $N$ ячеек нового состояния;
- запасы берут из него $B_o$;
- внутренние грани и грань скважины — выборку по номеру ячейки выше по потоку;
- внешняя граница при притоке из контура — постоянные $(p_{\text{контур}}, R_{s,\text{контур}}, S_g = 0)$, значения можно запомнить один раз на модель.

Поэлементные операции не зависят от соседних элементов массива, поэтому вариант тоже побитовый.

Оценка по замерам отдельных вызовов (`bo` 133 мкс, `bo_mu_o` 153 мкс при $N = 350$; скалярный вызов ~91 мкс): уходят `bo` запасов и два скалярных вызова — около −0.3 мс из 0.74 мс у примера 14. Не замер. Цена — правка кода потоков: сигнатуры `face_component_fluxes_sm3s` и `_well_fluxes`, которые также вызывают `well_rates` и `step_global_balance`. Это уже не «невязка без лишней работы», а перестройка потоков. **Решение пользователя:** включить сюда шагом 5б или оформить отдельной задачей DEBT после влития DEBT-036 (рекомендация аудита: отдельная задача — нынешний план проверен целиком и побитово, расширение снова требует проб).

### Как устроена векторная интерполяция (вариант 3б)

Таблицы строятся один раз в `__init__` (`_build_interp_tables`):

- **`_rows[k, i]`** = $(x_i, B_{o,i}, s^{B}_i, \mu_{o,i}, s^{\mu}_i)$ — узел $i$ ветви $k$ и наклоны на $[x_i, x_{i+1}]$. Последняя строка ветви и дополнение коротких ветвей до общей длины $m$ — «верх»: $(x_{\text{посл}}, B_{o,\text{посл}}, 0, \mu_{o,\text{посл}}, 0)$.
- **`_x_union`** = $U$ — объединение узлов $x$ всех ветвей (отсортировано, $U_0 = 0$).
- **`_row_of[k, u]`** = (число узлов ветви $k$, не превышающих $U_u$) $- 1$. Внутри $[U_u, U_{u+1})$ нет ни одного узла **ни одной** ветви, поэтому строка ветви $k$ для любого $\Delta p$ из этого интервала постоянна. Номер $u$ даёт один точный `searchsorted` по $U$, общий для ветвей $j$ и $j+1$.
- **`_segments[j]`** = $(R_{s,j}, R_{s,j+1}-R_{s,j}, p_{b,j}, p_{b,j+1}-p_{b,j})$.

На вызов: сегмент $j$ (как раньше), вес $w$ и $\Delta p$ (как раньше), $u$, затем для $k \in \{j, j+1\}$ — строка `_rows[k, _row_of[k, u]]` и `np.where(Δp >= x_top_k, y_посл, slope*(Δp - x_i) + y_i)`.

- NaN в $\Delta p$: `searchsorted` ставит его в конец, сравнение с верхом даёт `False`, формула даёт NaN, как `np.interp`.
- $+\infty$: верх ветви, как `np.interp`. В отброшенной ветви `np.where` получается $0 \cdot \infty$, numpy выдаёт `RuntimeWarning: invalid value`. Прототип никогда не вызывает PVT при бесконечном давлении: `_trial_is_reasonable` отбрасывает неконечные пробные точки.

Память: `_rows` — $K \times m \times 5$ чисел (пример 14: 19×31×5 — 24 КБ), `_row_of` — $K \times |U|$ (19×313 — 48 КБ).

## Подводные камни (чеклист)

- ✅ **Все места вызова найдены.**
  - `_oil_prop` и `_branch_prop_delta` вызываются только внутри `pvt.py` (`grep` по `numerical_solver`); тесты их не вызывают.
  - `component_inventories`: 4 места (см. baseline), все получают прежние значения.
  - `physical_residual`/`residual`: сигнатуры не меняются.
  - `_phase_mobilities_surface`: только `_well_fluxes` и `face_component_fluxes_sm3s`.
- ✅ **Зависимости пакетов:** новых нет (numpy).
- ✅ **Обратная совместимость API:**
  - `bo`, `mu_o` — прежние сигнатуры, формы (0-d для скаляров, broadcast для разных форм — `two_phase_analytics.py:251` зовёт со скалярным $p$, 2-D) и значения;
  - публичные атрибуты `BlackOilPVT` не меняются, новые — с подчёркиванием;
  - `bo_mu_o` — новый метод.
- ⚠️ **Поведение на некорректных таблицах** (решение пользователя на аудите — см. «Обнаруженные проблемы»).
  - Одна ветвь $R_s$: было NaN во всех $B_o$, $\mu_o$ с `RuntimeWarning` (проверено), без шага 4 стало бы `IndexError` при первом вызове. План: `ValueError` при построении с понятным текстом. Ни один рабочий конфиг этим не ломается — с одной ветвью расчёт и раньше падал на NaN.
  - Ветвь из одной строки (CSV-путь фабрики её не запрещает): побитово как раньше. Единственное отличие — NaN на входе: `np.interp` с одной точкой даёт её значение, новый код — NaN. NaN на вход прототипа не попадает.
  - Повторяющиеся давления внутри ветви (CSV-путь их тоже не запрещает): строка нулевой длины никогда не выбирается, значения прежние. При построении её наклон $0/0$ даёт `RuntimeWarning`.
- ⚠️ **$p = \pm\infty$:** значения прежние, но появляется `RuntimeWarning` от $0 \cdot \infty$ в отброшенной ветви `np.where`. В расчёте не встречается; в тесте подавляется `np.errstate`.
- ⚠️ **Побитовость привязана к сборке numpy** (найдено аудитом). Совпадение с `np.interp` установлено пробой (numpy 2.5.2, MSVC, x86-64), исходник `arr_interp` не сверялся. Если сборка numpy вычисляет `slope*(x - xp[j]) + fp[j]` слитным умножением-сложением (FMA — возможно, например, в сборках для aarch64), прежний и новый код разойдутся в последнем разряде. Тогда `test_bo_mu_bitwise_former_loop` упадёт, хотя ошибки в коде нет. На машине проекта (venv `numerical_solver\.venv`) этого нет. При переносе на другую платформу падение этого теста при расхождении ≤ 1 ulp — повод перейти на допуск `rtol = 1e-15`, а не искать дефект.
- ✅ **Состояние при ошибке:** `_build_interp_tables` вызывается последней строкой `__init__`, после проверки газовой таблицы. При `ValueError` объект не создаётся. Кеш запасов заполняется только после успешного `component_inventories`.
- ✅ **Тесты:**
  - тесты прототипа на PVT и невязке: `test_pvt_clamp.py`, `test_physics.py`, `test_grouped_jacobian.py`, `test_pvt_kink_jacobian.py`, `test_input_contract.py`, `test_input_validation_extra.py`;
  - тесты `numerical_solver`: `test_prototype_adapter.py`, `test_prototype_well_branch.py`, `test_hydro_to_blackoil_adapter.py`, примеры. На коде плана зелёные (83 теста прототипа проверены).
- ✅ **Циклические импорты:** новых импортов нет.
- ✅ **Docstrings:** ссылки на уравнения не затрагиваются; новые методы — однострочные docstring с DEBT-036.
- ✅ **Конфиги:** не меняются.
- ✅ **Связь с другими задачами:**
  - [[DEBT-033]] влит; правка не трогает его код;
  - [[DEBT-026]] (параллельная работа: `examples/rs_analytics.py`, `tests/`) и [[DEBT-037]] (`tests/test_examples.py`) — другие файлы;
  - [[BUG-017]] (`_check_rs0_in_table`, `diagnostics.pvt_range_warnings` — `max_pressure_of_rs`, `gp`) и [[FEAT-028]] (`branches`) — атрибуты не меняются;
  - [[BUG-019]] (`gpn_multiphase_solver/pvt/consistency.py`) работает через адаптеры с прежним API и получает те же $B_o$, поэтому предупреждения прежние;
  - [[DEBT-028]] (#60, выбор ячейки выше по потоку в адаптере `gpn_multiphase_solver/hydro/prototype_adapter.py`) — файл библиотеки, свойства берёт через `PrototypePVTAdapter` с прежними значениями; не пересекается. На момент аудита раунда 2 реализуется параллельно (worktree `.worktrees/debt-028`, ветка `refactor/debt-028/compute-fluxes-shutin-upwind`; пока правит `tests/test_fluxes.py`, прототип не трогает). Если её влить раньше, сдвинется только число тестов `numerical_solver` (шаг 1 берёт фактическое).
- ✅ **Производительность:** см. «Замер». На маленьких таблицах векторный `bo` медленнее цикла, но вместе с шагом 5 невязка быстрее исходной на всех примерах.
- ✅ **Прототип:** правка меняет `HydroSolverPrototype/`. Тесты прототипа и регрессия — в шагах 2–5 и 7. **Ожидаемый исход регрессии: побитово, 11/11 PASS (`--quick`) после шагов 2–5 и 17/17 PASS (полная) в шаге 7.** Любой FAIL — дефект реализации: разбирать, эталон не переснимать.

## Шаги

Номера строк в блоках «До» — по базе `67d2d23`; прототип с тех пор не менялся (на `4136f3c` строки те же). После правок предыдущих шагов они сдвигаются, поэтому блоки искать по тексту. Проверено пробой `apply_plan.py --stepwise` (аудит, раунд 2): шаги 2–5 применены по одному к копии прототипа, каждый блок «До» нашёлся ровно один раз на своём шаге. После каждого шага в копии лежат только тесты этого и предыдущих шагов; тесты прототипа — 84, 87, 90, 92 passed, как в полях «Проверка».

⚠️ **Команды шагов записаны для основного каталога.** В worktree `.venv` нет (каталог в `.gitignore`), поэтому `.venv\Scripts\python` (из `numerical_solver`) и `..\..\.venv\Scripts\python` (из `Prototype_1.0.3`) там не найдутся. Вместо них — `$PY` из «Как начать», полный путь к venv основного каталога. Код при этом берётся из worktree: `python -m pytest` и `regression\run_regression.py` ставят первым в `sys.path` каталог запуска, `run_prototype.py` — свой каталог, пробы — `Path.cwd()`. Пример: `& $PY -m pytest tests/test_inventories_cache.py -q`.

### Шаг 1: Подготовка — ветка и baseline

**Цель:** зафиксировать числа и эталонные истории до правки кода.

**Файлы:** нет (только запуски). Снимки ложатся в `vault/issues/debt-036/probes/history_base/*.npz` основного каталога.

**Контекст:** побитовый критерий приёмки требует эталона на том же коде, что и база ветки. Снимок историй — главный эталон для примеров GPN: тесты `tests/` сравнивают числа с допусками и мелкое расхождение не поймают.

**Что сделать:**
1. Ветка/worktree `refactor/debt-036/table-pvt-residual-speedup` от `numerical_scheme/implementation`. Записать короткий SHA базы. История: планирование — `67d2d23`, аудит раунда 1 — `c51e137`, раунда 2 — `4136f3c` (влит [[DEBT-026]]: примеры, `rs_analytics.py`, тесты; прототип не тронут, блоки «До» верны).
2. Из `numerical_solver` дерева ветки: `--collect-only -q` (ожидается 1223), быстрый уровень (999 passed, записать время). Если база снова сдвинулась — брать фактические числа. Числа прототипа (83) и ожидания по прототипу меняются, только если сдвиг затронул `HydroSolverPrototype/`: проверить `git diff --stat 4136f3c HEAD -- numerical_solver/HydroSolverPrototype`.
3. Из `Prototype_1.0.3` дерева ветки: тесты прототипа (83 passed), `regression\run_regression.py --quick` (11/11 PASS). Выходы `OUTPUT/REGRESSION_*` после разбора удалить.
4. Из `numerical_solver` дерева ветки (команды — раздел «Как начать»):
   - `history_snapshot.py save base`: все 20 примеров, ~4 мин; первая строка вывода — пути кода, это должны быть пути дерева ветки;
   - `time_jacobian.py 14_high_gor_cooling 04_table_table 06_table_corey_rp 20_rs300_cooling 03_standing_corey` (~70 с), записать столбец «невязка»;
   - `planned_code_check.py unit` → `unit: OK, таблиц 30` (код файлов совпадает с эталонной копией цикла).

**Проверка после этого шага:**
- Регресс: быстрый (это и есть baseline).
- Регресс прототипа: тесты и `--quick` — baseline.

**Подводные камни:** пробы — по абсолютному пути основного каталога, запуск из `numerical_solver` дерева ветки (⚠️ в «Как начать»). `history_snapshot.py` этой задачи пишет в `debt-036/probes/`, снимки DEBT-033 не затрагиваются.

**Зависимости:** блокирует все шаги.

**Оценка:** 0 строк, ~15 мин (из них 8 — регрессия).

### Шаг 2: Запасы без вязкостей (вариант 1)

**Цель:** `component_inventories` не вычисляет $\mu_o$, $\mu_g$.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (`:147-151`)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_inventories_cache.py` (новый)

**Контекст:** `oil_properties`/`gas_properties` (`:145-146`) возвращают пары $(B, \mu)$, вязкости отбрасываются. `self.pvt.bo`, `self.pvt.bg` — те же вызовы с теми же аргументами, результат побитово прежний. Оба PVT, которые передаются в модель (`BlackOilPVT` и `HydroPVTtoBlackOilAdapter`), имеют `bo` и `bg`. `oil_properties` остаётся: им пользуется `simulation.py:35`.

**Что сделать:**
1. Заменить строку 149.
2. Создать `tests/test_inventories_cache.py`: шапка, `_mixed_state`, `_NoViscosityPVT`, класс `InventoriesTests` с тестом `test_inventories_without_viscosities` (код — «Тестовая стратегия»; остальные три теста класса добавляются в шаге 3).

**Изменения:**

До (`blackoil.py:147-151`):
```python
    def component_inventories(self,state):
        p,sg=state.pressure_bar,state.sg; so=1.0-sg
        bo,_=self.oil_properties(state); bg,_=self.gas_properties(state)
        pv=self.rock.pore_volume_m3(self.grid.bulk_volumes_m3,p)
        return pv*so/bo, pv*(state.rs_sm3_sm3*so/bo+sg/bg)
```
После:
```python
    def component_inventories(self,state):
        p,sg=state.pressure_bar,state.sg; so=1.0-sg
        # DEBT-036: Bo and Bg only; oil_properties/gas_properties would evaluate mu_o, mu_g as well
        bo=self.pvt.bo(p,state.rs_sm3_sm3); bg=self.pvt.bg(p)
        pv=self.rock.pore_volume_m3(self.grid.bulk_volumes_m3,p)
        return pv*so/bo, pv*(state.rs_sm3_sm3*so/bo+sg/bg)
```

**Проверка после этого шага:**
- Тест шага: из `Prototype_1.0.3` — `..\..\.venv\Scripts\python -m pytest tests/test_inventories_cache.py -q` (1 passed; до правки он падает на `AssertionError: inventories called mu_o`).
- Регресс прототипа: тесты прототипа — 84 passed. Регрессия — после шага 5 (шаги 2–5 вместе, ожидание — побитово).
- Регресс: быстрый (999 passed).

**Подводные камни:** нет (чеклист — «Все места вызова»).

**Зависимости:** требует шаг 1.

**Оценка:** 1 строка кода, ~30 строк теста, ~15 мин.

### Шаг 3: Запасы старого состояния один раз на шаг (вариант 2б′)

**Цель:** `physical_residual` не пересчитывает запасы `state_old` при каждом вызове.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (`__init__` `:76`, новый метод после `component_inventories`, `physical_residual` `:176-178`)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_inventories_cache.py` (ещё три теста)

**Контекст:** в пределах шага по времени все вызовы невязки получают один и тот же `state_old`: копию из `_advance_phases:352`. Это 7 вызовов на якобиан плюс линейный поиск. Запасы старого состояния — одна и та же работа на каждом вызове. По замеру шага 3 («Замер») она стоит 0.56 мс у примера 14, 0.12 мс у 04 и 0.11 мс у 20. Это больше 0.23 мс из записи реестра: там замер на другом состоянии Ньютона (HEAD `a342a85`). Причина расхождения не разбиралась; на выбор варианта она не влияет.

Ключ кеша — **байты** $p$, $R_s$, $S_g$, а не ссылка на объект:
- состояние, изменённое на месте, получает новые запасы (так делают тесты `test_grouped_jacobian.py:_jacobian_states` до вызова; проба показала, что кеш по ссылке в таком случае возвращает устаревшие значения);
- равные байты дают побитово те же запасы;
- `tobytes` трёх массивов $N = 350$ и сравнение — 1.8 мкс; `np.array_equal` — 11 мкс.

Одна запись кеша: следующий шаг вытесняет предыдущий; `_fallback` повторяет `_advance_phases` с той же копией значений и попадает в кеш. Сетка, порода и PVT модели постоянны (только `__init__` их присваивает), поэтому в ключ они не входят. `step_global_balance` по-прежнему вызывает `component_inventories` напрямую.

**Что сделать:**
1. В конец `__init__` (после строки 76) — атрибут кеша.
2. После `component_inventories` (перед `_phase_mobilities_surface`) — метод `_old_inventories`.
3. В `physical_residual` — `self._old_inventories(state_old)` вместо `self.component_inventories(state_old)`.
4. В `test_inventories_cache.py` — тесты `test_old_inventories_once_per_state`, `test_residual_bitwise_fresh_model`, `test_old_inventories_follow_in_place_change`.

**Изменения:**

До (`blackoil.py:74-76`):
```python
        if jacobian_mode not in ('grouped','reference'): raise ValueError("jacobian_mode must be 'grouped' or 'reference'")
        if linear_solver not in ('sparse','dense'): raise ValueError("linear_solver must be 'sparse' or 'dense'")
        self.jacobian_mode=jacobian_mode; self.linear_solver=linear_solver
```
После:
```python
        if jacobian_mode not in ('grouped','reference'): raise ValueError("jacobian_mode must be 'grouped' or 'reference'")
        if linear_solver not in ('sparse','dense'): raise ValueError("linear_solver must be 'sparse' or 'dense'")
        self.jacobian_mode=jacobian_mode; self.linear_solver=linear_solver
        # DEBT-036: (key, oil, gas) inventories of the last state_old of physical_residual (_old_inventories)
        self._old_inventories_cache=None
```

До (`blackoil.py:151-152`, конец `component_inventories` и начало `_phase_mobilities_surface`; строка 149 уже изменена шагом 2):
```python
        return pv*so/bo, pv*(state.rs_sm3_sm3*so/bo+sg/bg)
    def _phase_mobilities_surface(self,p,rs,sg):
```
После:
```python
        return pv*so/bo, pv*(state.rs_sm3_sm3*so/bo+sg/bg)
    def _old_inventories(self,state_old):
        """Inventories of state_old, recomputed only when its p, Rs or Sg change (DEBT-036)."""
        # Within a step every residual (7 per Jacobian plus the line search) has the same state_old.
        # The key is the bytes of p, Rs, Sg, not the object: a state changed in place gets fresh
        # inventories, equal bytes give bitwise the same ones (key 1.8 us at N = 350 against
        # 0.1-0.6 ms for the inventories).  grid, rock and pvt are fixed for the model's life.
        # The returned arrays are the cached ones: callers must not modify them in place.
        key=(state_old.pressure_bar.tobytes(),state_old.rs_sm3_sm3.tobytes(),state_old.sg.tobytes())
        c=self._old_inventories_cache
        if c is None or c[0]!=key:
            c=self._old_inventories_cache=(key,)+tuple(self.component_inventories(state_old))
        return c[1],c[2]
    def _phase_mobilities_surface(self,p,rs,sg):
```

До (`blackoil.py:176-178`, номера — до вставок этого шага):
```python
    def physical_residual(self,z,state_old,dt_s,gas_active):
        new=self.unpack(z,gas_active); oi1,gi1=self.component_inventories(new); oi0,gi0=self.component_inventories(state_old); qo,qg=self.net_component_outflow(new)
        return np.concatenate([(oi1-oi0)/float(dt_s)+qo,(gi1-gi0)/float(dt_s)+qg])
```
После:
```python
    def physical_residual(self,z,state_old,dt_s,gas_active):
        new=self.unpack(z,gas_active); oi1,gi1=self.component_inventories(new); oi0,gi0=self._old_inventories(state_old); qo,qg=self.net_component_outflow(new)
        return np.concatenate([(oi1-oi0)/float(dt_s)+qo,(gi1-gi0)/float(dt_s)+qg])
```

**Проверка после этого шага:**
- Тест шага: `..\..\.venv\Scripts\python -m pytest tests/test_inventories_cache.py -q` (4 passed; до правки `test_old_inventories_once_per_state` падает: 6 вызовов вместо 4).
- Регресс прототипа: тесты прототипа — 87 passed.
- Регресс: быстрый (999 passed).

**Подводные камни:** чеклист — «Состояние при ошибке» (кеш пишется после успешного вычисления), «Связь с DEBT-033» (сигнатуры не меняются).

**Зависимости:** требует шаг 2 (тестовый файл); блокирует шаг 7.

**Оценка:** ~13 строк кода, ~25 строк теста, ~20 мин.

### Шаг 4: Интерполяция PVTO массивами (вариант 3б)

**Цель:** `bo`, `mu_o` без цикла Python по сегментам, побитово прежние.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/pvt.py` (конец `__init__` `:30`; `:40-66` — `_branch_prop_delta`, `_oil_prop`, `bo`, `mu_o`)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_pvto_vectorized.py` (новый)

**Контекст:** устройство таблиц — раздел «Как устроена векторная интерполяция»; почему побитово — «Почему побитовость достижима». Комментарий прежнего `_oil_prop` об ограничениях PVTO (`pvt.py:46-51`) переносится дословно. `_branch_prop_delta` больше никто не вызывает, поэтому он удаляется; его поведение повторяет эталонная копия в тесте. Проверка «не меньше двух ветвей $R_s$» стоит в начале `_build_interp_tables`: с одной ветвью `_segments` пуст, и без проверки первый вызов дал бы `IndexError` (раньше — NaN, см. чеклист).

**Что сделать:**
1. Последней строкой `__init__` — вызов `self._build_interp_tables()`.
2. Заменить строки 40-66 кодом «После».
3. Создать `tests/test_pvto_vectorized.py`: шапка, `_former_oil_prop`, `GAS`, `_irregular_table`, `_tables`, `_points`, класс `PvtoVectorizedTests` с тестами `test_bo_mu_bitwise_former_loop`, `test_shapes_as_before`, `test_single_rs_branch_rejected` (код — «Тестовая стратегия»; два теста шага 5 добавляются там).

**Изменения:**

До (`pvt.py:28-30`):
```python
        self.max_rs=float(self.rs_values[-1]); self.bubble_point_max_rs_bar=float(self.pb[-1])
        self.gp=np.array([float(r[0]) for r in gas_rows]); self.gbg=np.array([float(r[1]) for r in gas_rows]); self.gmu=np.array([float(r[2]) for r in gas_rows])
        if len(self.gp)<2 or np.any(np.diff(self.gp)<=0): raise ValueError('GAS_PVT pressure must be strictly increasing with >=2 rows')
```
После:
```python
        self.max_rs=float(self.rs_values[-1]); self.bubble_point_max_rs_bar=float(self.pb[-1])
        self.gp=np.array([float(r[0]) for r in gas_rows]); self.gbg=np.array([float(r[1]) for r in gas_rows]); self.gmu=np.array([float(r[2]) for r in gas_rows])
        if len(self.gp)<2 or np.any(np.diff(self.gp)<=0): raise ValueError('GAS_PVT pressure must be strictly increasing with >=2 rows')
        self._build_interp_tables()
```

До (`pvt.py:40-66`):
```python
    def _branch_prop_delta(self, rs_branch, delta_p, which):
        x,bo,mu=self._branch_arrays[float(rs_branch)]
        return np.interp(delta_p,x,bo if which=='bo' else mu)
    def _oil_prop(self,p,rs,which):
        p_arr,rs_arr=np.broadcast_arrays(np.asarray(p,float),np.asarray(rs,float))
        shape=p_arr.shape; pf=p_arr.ravel(); rf=rs_arr.ravel(); out=np.empty_like(pf,dtype=float)
        # PVTO is evaluated from fixed-Rs branches. At p below Pb(Rs), the
        # branch is clamped to its first (saturated) point. For a gas-active
        # state Rs=Rs_sat(p), this is exactly the saturated locus. This
        # extension is also important for a fixed-active-set Newton trial that
        # temporarily crosses the phase boundary before the active set switches.
        # Explicit endpoint clamp in Rs; no extrapolation between/above PVTO branches.
        rr=np.clip(rf,self.rs_values[0],self.rs_values[-1])
        j=np.searchsorted(self.rs_values,rr,side='right')-1
        j=np.clip(j,0,len(self.rs_values)-2)
        for jj in np.unique(j):
            loc=(j==jj); ids=np.nonzero(loc)[0]
            r0,r1=self.rs_values[jj],self.rs_values[jj+1]
            rrj=rr[loc]; ppj=pf[loc]
            w=(rrj-r0)/(r1-r0)
            pbq=self.pb[jj]+w*(self.pb[jj+1]-self.pb[jj])
            dp=np.maximum(ppj-pbq,0.0)
            v0=self._branch_prop_delta(r0,dp,which); v1=self._branch_prop_delta(r1,dp,which)
            out[ids]=v0+w*(v1-v0)
        return out.reshape(shape)
    def bo(self,p,rs): return self._oil_prop(p,rs,'bo')
    def mu_o(self,p,rs): return self._oil_prop(p,rs,'mu')
```
После:
```python
    def _build_interp_tables(self):
        """DEBT-036: tables of _oil_props, all cells at once (bitwise the former per-segment np.interp)."""
        # Bo, mu_o interpolate between two Rs branches; with one branch the former code divided 0/0
        if self.rs_values.size<2: raise ValueError(f'OIL_PVT needs >=2 Rs branches, got {self.rs_values.size}')
        # Row i of branch k: (x_i, Bo_i, Bo slope, mu_i, mu slope) on [x_i, x_i+1], x = p - Pb of the
        # branch; the slopes are np.interp's own (y[i+1]-y[i])/(x[i+1]-x[i]).  The last row of a branch
        # and the padding of shorter branches are its top: (x_last, Bo_last, 0, mu_last, 0).
        br=[self._branch_arrays[float(r)] for r in self.rs_values]
        m=max(x.size for x,_,_ in br); rows=np.zeros((len(br),m,5))
        for k,(x,bo,mu) in enumerate(br):
            L=x.size
            rows[k,:,0]=x[-1]; rows[k,:,1]=bo[-1]; rows[k,:,3]=mu[-1]
            rows[k,:L,0]=x; rows[k,:L,1]=bo; rows[k,:L,3]=mu
            rows[k,:L-1,2]=(bo[1:]-bo[:-1])/(x[1:]-x[:-1]); rows[k,:L-1,4]=(mu[1:]-mu[:-1])/(x[1:]-x[:-1])
        self._rows=rows; self._x_top=rows[:,-1,0]
        # Union U of the knots of all branches.  No knot of any branch lies inside [U_u, U_u+1), so
        # for dp there the row of branch k is fixed: _row_of[k,u] = count(x_k <= U_u) - 1.  One
        # exact searchsorted over U replaces a search per branch.
        self._x_union=np.unique(np.concatenate([x for x,_,_ in br]))
        self._row_of=np.array([np.searchsorted(x,self._x_union,side='right')-1 for x,_,_ in br])
        # Segment j = [Rs_j, Rs_j+1]: (Rs_j, Rs_j+1 - Rs_j, Pb_j, Pb_j+1 - Pb_j), the differences
        # the per-segment loop formed
        rs,pb=self.rs_values,self.pb
        self._segments=np.stack([rs[:-1],rs[1:]-rs[:-1],pb[:-1],pb[1:]-pb[:-1]],axis=1)
    _BO=(1,2); _MU=(3,4)   # (value, slope) columns of _rows for Bo and mu_o
    def _oil_props(self,p,rs,columns):
        """PVTO oil properties of all cells at once, one per (value, slope) column pair of _rows (DEBT-036)."""
        p_arr,rs_arr=np.broadcast_arrays(np.asarray(p,float),np.asarray(rs,float))
        shape=p_arr.shape; pf=p_arr.ravel(); rf=rs_arr.ravel()
        # PVTO is evaluated from fixed-Rs branches. At p below Pb(Rs), the
        # branch is clamped to its first (saturated) point. For a gas-active
        # state Rs=Rs_sat(p), this is exactly the saturated locus. This
        # extension is also important for a fixed-active-set Newton trial that
        # temporarily crosses the phase boundary before the active set switches.
        # Explicit endpoint clamp in Rs; no extrapolation between/above PVTO branches.
        rr=np.clip(rf,self.rs_values[0],self.rs_values[-1])
        j=np.searchsorted(self.rs_values,rr,side='right')-1
        j=np.clip(j,0,len(self.rs_values)-2)
        # Rs weight and Pb(Rs) on the segment of each cell, as the per-segment loop formed them
        seg=self._segments[j]
        w=(rr-seg[:,0])/seg[:,1]
        dp=np.maximum(pf-(seg[:,2]+w*seg[:,3]),0.0)
        # dp >= 0 = U_0, so u >= 0; NaN sorts last and stays NaN through the formula below
        u=np.searchsorted(self._x_union,dp,side='right')-1
        sides=[]
        for k in (j,j+1):
            row=self._rows[k,self._row_of[k,u]]; top=dp>=self._x_top[k]
            # np.interp: slope*(x - x_i) + y_i inside the branch, its last value at and above the top
            sides.append([np.where(top,row[:,cy],row[:,cs]*(dp-row[:,0])+row[:,cy]) for cy,cs in columns])
        return [(v0+w*(v1-v0)).reshape(shape) for v0,v1 in zip(*sides)]
    def bo(self,p,rs): return self._oil_props(p,rs,(self._BO,))[0]
    def mu_o(self,p,rs): return self._oil_props(p,rs,(self._MU,))[0]
```

Цикл `for k in (j,j+1)` — два прохода (ветви $j$ и $j+1$), а не цикл по ячейкам или сегментам. Список `columns` — одна пара для `bo`/`mu_o`, две для `bo_mu_o` (шаг 5).

**Проверка после этого шага:**
- Тест шага: `..\..\.venv\Scripts\python -m pytest tests/test_pvto_vectorized.py -q` (3 passed; до правки `test_single_rs_branch_rejected` падает, два других проходят — эталон совпадает с прежним кодом).
- Проба: из `numerical_solver` дерева ветки `& $PY $P\planned_code_check.py unit` → `unit: OK, таблиц 30` (код файлов против эталонной копии цикла на всех таблицах проекта).
- Регресс прототипа: тесты прототипа — 90 passed (`test_pvt_clamp.py` без изменений).
- Регресс: быстрый (999 passed).

**Подводные камни:** чеклист — «Поведение на некорректных таблицах», «$p = \pm\infty$». Невязка на таблицах 2×2 после этого шага медленнее исходной (0.90 против 0.76 мс у примера 04, см. «Замер»): это промежуточное состояние, шаг 5 его снимает. Замер — после шага 5.

**Зависимости:** требует шаг 1; блокирует шаг 5.

**Оценка:** ~40 строк кода, ~70 строк теста, ~40 мин.

### Шаг 5: $B_o$ и $\mu_o$ за один проход (вариант 4)

**Цель:** подвижности на гранях — один поиск сегмента и строки на обе величины.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/pvt.py` (новый метод после `mu_o`)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (`_phase_mobilities_surface`)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_pvto_vectorized.py` (ещё два теста)

**Контекст:** `_phase_mobilities_surface` вызывается трижды на невязку (грань скважины, внутренние грани, внешняя граница) и каждый раз зовёт `bo` и `mu_o` на одних и тех же $(p, R_s)$. С `bo_mu_o` вызовов интерполяции нефти на невязку становится 4 вместо 10 исходных: запасы нового состояния и три грани. У адаптера Стендинга `HydroPVTtoBlackOilAdapter` метода нет; `getattr` оставляет ему прежний путь, и его результаты не меняются. Добавлять метод в библиотеку `gpn_multiphase_solver` ради прототипа не нужно.

**Что сделать:**
1. В `pvt.py` после `mu_o` — `bo_mu_o`.
2. В `blackoil.py` — `_phase_mobilities_surface` по «После».
3. В `test_pvto_vectorized.py` — тесты `test_bo_mu_o_one_pass`, `test_mobilities_one_pvto_pass` (добавить импорт `from radial_blackoil.units import CP_TO_PA_S`).

**Изменения:**

До (`pvt.py`, конец `mu_o` из шага 4):
```python
    def mu_o(self,p,rs): return self._oil_props(p,rs,(self._MU,))[0]
```
После:
```python
    def mu_o(self,p,rs): return self._oil_props(p,rs,(self._MU,))[0]
    def bo_mu_o(self,p,rs):
        """Bo and mu_o in one pass: the segment and row search is shared (DEBT-036)."""
        bo,mu=self._oil_props(p,rs,(self._BO,self._MU)); return bo,mu
```

До (`blackoil.py`, `_phase_mobilities_surface`; до шага 3 — строки 152-155):
```python
    def _phase_mobilities_surface(self,p,rs,sg):
        p=np.asarray(p,float); rs=np.asarray(rs,float); sg=np.asarray(sg,float)
        bo=self.pvt.bo(p,rs); muo=self.pvt.mu_o(p,rs); bg=self.pvt.bg(p); mug=self.pvt.mu_g(p)
        return self.relperm.kro(sg)/(muo*CP_TO_PA_S)/bo, self.relperm.krg(sg)/(mug*CP_TO_PA_S)/bg
```
После:
```python
    def _phase_mobilities_surface(self,p,rs,sg):
        p=np.asarray(p,float); rs=np.asarray(rs,float); sg=np.asarray(sg,float)
        # DEBT-036: Bo and mu_o from one PVTO pass where the PVT has it (BlackOilPVT); the
        # Standing adapter (HydroPVTtoBlackOilAdapter) has bo and mu_o only
        bo_mu_o=getattr(self.pvt,'bo_mu_o',None)
        bo,muo=bo_mu_o(p,rs) if bo_mu_o is not None else (self.pvt.bo(p,rs),self.pvt.mu_o(p,rs))
        bg=self.pvt.bg(p); mug=self.pvt.mu_g(p)
        return self.relperm.kro(sg)/(muo*CP_TO_PA_S)/bo, self.relperm.krg(sg)/(mug*CP_TO_PA_S)/bg
```

**Проверка после этого шага:**
- Тест шага: `..\..\.venv\Scripts\python -m pytest tests/test_pvto_vectorized.py tests/test_inventories_cache.py -q` (9 passed).
- Регресс прототипа: тесты прототипа — **92 passed**; `regression\run_regression.py --quick` — **11/11 PASS** (шаги 2–5 вместе; ожидание — побитово, любой FAIL — дефект реализации).
- Регресс: быстрый (999 passed).
- Проба: `& $PY $P\history_snapshot.py save new` и `& $PY $P\history_snapshot.py compare base new` → `итого: различий 0` (20 примеров).

**Подводные камни:** чеклист — «Обратная совместимость API» (`bo_mu_o` — новый метод).

**Зависимости:** требует шаги 3 и 4.

**Оценка:** ~8 строк кода, ~25 строк теста, ~20 мин (и ~12 мин на регрессию и снимок).

### Шаг 6: Документация прототипа и заметка о прототипе

**Цель:** записать изменение там, где его будут искать.

**Файлы:**
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` (новый раздел в конце)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (docstring модуля, `:11-13`)
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/pvt.py` (docstring класса, `:4-10`)
- `vault/knowledge/decisions/hydro-prototype-анализ.md` (§2 «PVT»)

**Что сделать:**
1. CHANGELOG, в конец (после раздела DEBT-033), по образцу разделов BUG-014/016, DEBT-033 (английский, как весь файл):
   ```markdown
   ## Local changes — GPN project (DEBT-036): faster residual on tabular PVT
   - Problem: on a tabular PVTO one residual cost 3.5 ms at N = 350 against 0.9 ms with the Standing adapter: `_oil_prop` interpolated with a Python loop over Rs segments (a mask and two `np.interp` per segment, 14 segments in a 19-branch table), `component_inventories()` evaluated and dropped mu_o, mu_g, the inventories of the old state were recomputed on every residual of a step, and the faces evaluated Bo and mu_o in separate passes.
   - `BlackOilPVT`: `_oil_props()` evaluates all cells at once from tables built in `__init__` (`_build_interp_tables()`: branch rows with np.interp's own slopes, a map from the union of all branch knots to the row of each branch, segment differences); `bo()`, `mu_o()` keep their signature and values; new `bo_mu_o()` returns both from one segment and row search. `_branch_prop_delta()` removed. A table with a single Rs branch is rejected (`ValueError`): it used to give NaN Bo, mu_o everywhere.
   - `RadialBlackOilModel`: `component_inventories()` takes `pvt.bo`, `pvt.bg` only; `physical_residual()` takes the old-state inventories from `_old_inventories()`, a one-entry cache keyed by the bytes of p, Rs, Sg; `_phase_mobilities_surface()` calls `pvt.bo_mu_o` where the PVT has it.
   - Bitwise: Bo and mu_o equal the former loop on all project tables (4.1 million points incl. knots, one ulp off them, NaN, +inf); residuals, Newton steps, the 20 GPN examples and the regression are unchanged. The only difference: +inf pressure raises a RuntimeWarning (0*inf in a discarded `np.where` branch); the prototype never evaluates PVT there.
   - Effect: residual at N = 350 (19-branch table) 3.49 -> 0.74 ms, at N = 50 (2x2 table) 1.09 -> 0.62 ms, Standing 0.88 -> 0.57 ms; GPN example 14 41.5 -> 11.5 s, others x1.3-1.6. Prototype tests <N> passed (9 new); full regression 17/17 PASS.
   - Physics, residual equations, tolerances and Newton/active-set logic are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
   - Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/59; plan: `vault/plans/debt-036 table-pvt-residual-speedup.md` of the GPN project.
   ```
   Числа «Effect» и `<N>` — из замера и прогонов шага 7.
2. Docstring модуля `blackoil.py` — после строк DEBT-033 (`:11-12`), перед `"""`:
   ```
   DEBT-036: component_inventories uses Bo, Bg only; the old-state inventories are
   computed once per step (_old_inventories); faces take Bo, mu_o from pvt.bo_mu_o
   where the PVT has it.
   ```
3. Docstring класса `BlackOilPVT` — после «...implementation is vectorized only for speed.» (`:9`):
   ```
   DEBT-036: all cells at once from padded branch tables (_oil_props), bitwise the
   former per-segment np.interp; bo_mu_o gives Bo and mu_o from one pass.
   ```
4. `hydro-prototype-анализ.md`, §2 — абзац после первого:
   ```markdown
   Интерполяция — все ячейки сразу (`_oil_props`, [[DEBT-036]]): строки ветвей с наклонами `np.interp`, карта «интервал объединённой сетки узлов → строка ветви», побитово прежний цикл по сегментам; `bo_mu_o` — $B_o$ и $\mu_o$ за один проход. Запасы старого состояния считаются один раз на шаг (`_old_inventories`, ключ — байты $p$, $R_s$, $S_g$). Невязка при $N = 350$ на таблице из 19 ветвей — 0.74 мс (было 3.49).
   ```

**Проверка после этого шага:** `--collect-only -q` (только документы и docstring).

**Зависимости:** требует шаг 5; числа CHANGELOG — после шага 7.

**Оценка:** ~20 строк текста, ~15 мин.

### Шаг 7: Верификация — полная регрессия, тесты, истории, замер

**Цель:** подтвердить побитовость и ускорение на всём наборе.

**Файлы:** нет (запуски); числа — в CHANGELOG (шаг 6) и vault (шаг 8).

**Что сделать:**
1. Зафиксировать HEAD ветки (`git rev-parse --short HEAD`); во время полной регрессии в ветку ничего не вливать (каждый кейс — отдельный процесс, импортирует код заново).
2. Из `Prototype_1.0.3`: тесты прототипа (92 passed), `regression\run_regression.py` полная (~45 мин) → **17/17 PASS**. FAIL — дефект реализации: найти шаг, с которого расходится (`--case <имя>`), сравнить с пробой `unit`. Эталон не переснимать. Выходы `OUTPUT/REGRESSION_*` удалить.
3. Из `numerical_solver`:
   - полный уровень `.venv\Scripts\python -m pytest tests/ -q` → 1223 passed (~10 мин; или фактическое число шага 1);
   - `history_snapshot.py compare base new` → различий 0 (если шаг 5 снимал `new` до правок шага 6 — переснять: docstring на числа не влияет, но HEAD должен быть финальным);
   - `planned_code_check.py unit` → `таблиц 30`;
   - `time_jacobian.py` с теми же примерами, что в шаге 1 — записать «было → стало» по столбцам «всего» и «невязка».
4. Если замер примера 14 хуже 15 с или невязка в якобиане не уменьшилась хотя бы вдвое — разобрать (машина загружена? повторить), числа в отчёт как есть.

**Проверка после этого шага:** полная регрессия прототипа и полный уровень `tests/` — это и есть проверка.

**Зависимости:** требует шаги 5, 6.

**Оценка:** 0 строк, ~60 мин (45 — регрессия).

### Шаг 8: Vault и issue

**Цель:** закрыть запись и оставить результат в issue.

**Файлы:**
- `vault/roadmap/известные баги и технический долг.md` (запись DEBT-036)
- `vault/issues/debt-036/05-comment-done.md` (новый)
- `vault/00-home/index.md` (строка плана)

**Что сделать:**
1. DEBT-036: поле «Результат» (замер было/стало, число тестов прототипа, 17/17 PASS, истории 20 примеров побитово), статус `✅ ГОТОВО (дата)`.
2. Комментарий в #59: `gh issue comment 59 --repo ArturSalamatin/Oil_Gas --body-file vault/issues/debt-036/05-comment-done.md`.
3. Строка в `index.md` — отметить «реализовано».

**Проверка после этого шага:** `--collect-only -q`.

**Зависимости:** требует шаг 7.

**Оценка:** ~15 строк текста, ~10 мин.

## Тестовая стратегия

Новые тесты — два файла в `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/`: стиль прототипа (`unittest`, компактные строки), комментарии — по правилам проекта. Запуск — из `Prototype_1.0.3`: `..\..\.venv\Scripts\python -m pytest tests/test_inventories_cache.py tests/test_pvto_vectorized.py -q`. Тесты `numerical_solver/tests/` не добавляются: правка не меняет ни значений, ни API библиотеки. Побитовость на примерах GPN проверяют снимки историй (шаги 5, 7).

**Код тестов проверен при планировании:** файлы `vault/issues/debt-036/probes/planned_tests/*.py` дословно совпадают с кодом ниже (проба `planned_tests`). На коде плана 9 OK. На исходном коде падают `test_inventories_without_viscosities`, `test_old_inventories_once_per_state`, `test_bo_mu_o_one_pass`, `test_mobilities_one_pvto_pass`, `test_single_rs_branch_rejected`, а 4 теста побитовости проходят: их эталон — прежний код.

| тест | файл | шаг | сценарий | ожидание | предотвращает |
|---|---|---|---|---|---|
| `test_inventories_without_viscosities` | `test_inventories_cache.py` | 2 | PVT без `mu_o`, `mu_g`, `bo_mu_o` (обёртка падает на их вызове); смешанное состояние Nabor_1b | запасы считаются и побитово равны $V_p S_o/B_o$, $V_p(R_s S_o/B_o + S_g/B_g)$ | возврат вязкостей в запасы |
| `test_old_inventories_once_per_state` | то же | 3 | 3 невязки с одним `state_old` | `component_inventories` вызван 4 раза (3 новых + 1 старый), без кеша — 6 | потерю кеша |
| `test_residual_bitwise_fresh_model` | то же | 3 | невязка при заполненном кеше против свежей модели | побитово, 3 точки | расхождение кешированных запасов |
| `test_old_inventories_follow_in_place_change` | то же | 3 | `state_old` изменён на месте между вызовами | побитово как у свежей модели | устаревшие запасы (ключ по ссылке) |
| `test_bo_mu_bitwise_former_loop` | `test_pvto_vectorized.py` | 4 | Nabor_1b (6×5), ветви 2–8 строк с перемежающимися узлами, таблица с ветвью из одной строки; 7.4–14.4 тыс. точек на таблицу: узлы, ±1 ulp, $p < p_b$, выше верха, $R_s$ вне таблицы, случайные, NaN, $+\infty$ | `bo`, `mu_o` побитово (`tobytes`) равны дословной копии прежнего цикла | любое отклонение формулы или выбора строки |
| `test_shapes_as_before` | то же | 4 | скаляр, 0-d, скаляр $p$ с массивом $R_s$ и наоборот, 2-D, пустой массив | формы и байты как у прежнего | поломку граней (скаляры) и `two_phase_analytics.py` (разные формы) |
| `test_single_rs_branch_rejected` | то же | 4 | таблица с одной ветвью $R_s$ | `ValueError` с «Rs branches» | молчаливые NaN |
| `test_bo_mu_o_one_pass` | то же | 5 | все таблицы и точки первого теста | `bo_mu_o` побитово равен `bo`, `mu_o` | расхождение общего прохода |
| `test_mobilities_one_pvto_pass` | то же | 5 | `_phase_mobilities_surface` с наблюдателем за атрибутами PVT | вызван `bo_mu_o`, не вызван `mu_o`; подвижности побитово по формуле из `bo`, `mu_o`; PVT без `bo_mu_o` (как адаптер Стендинга) даёт те же подвижности | возврат к двум проходам; поломку ветки `getattr` для Стендинга |

Код `test_inventories_cache.py` (шаг 2 — шапка, `_mixed_state`, `_NoViscosityPVT`, первый тест; шаг 3 — остальные три):

```python
import unittest, numpy as np
from tests.helpers import model_and_state

# DEBT-036: component_inventories needs Bo and Bg only, and the inventories of the old state are
# computed once per step (_old_inventories).  Both must leave the residual bitwise unchanged: the
# Newton steps and the prototype regression against golden/ (abs 2e-7 / rel 2e-10) depend on it.
def _mixed_state(n=9):
    """Fixture Nabor_1b at p0 = 160 bar: cells 0-3 two-phase (Sg = 0.03, Rs = Rs_sat(p)), the rest oil only."""
    _,m,s=model_and_state(n=n,p0=160); mask=np.zeros(n,bool); mask[:4]=True
    s.gas_active=mask; s.sg[:4]=0.03; s.rs_sm3_sm3[:4]=m.pvt.rs_sat(s.pressure_bar[:4])
    return m,s,mask

class _NoViscosityPVT:
    """The model's PVT without viscosities: a call of mu_o, mu_g or bo_mu_o fails the test."""
    def __init__(self,pvt): self._pvt=pvt
    def __getattr__(self,name):
        if name in ('mu_o','mu_g','bo_mu_o'): raise AssertionError(f'inventories called {name}')
        return getattr(self._pvt,name)

class InventoriesTests(unittest.TestCase):
    def test_inventories_without_viscosities(self):
        # Bo and Bg only: with a PVT that has no viscosities the inventories are still computed and
        # equal bitwise pv*So/Bo, pv*(Rs*So/Bo + Sg/Bg) with the model's own Bo, Bg
        m,s,_=_mixed_state(); p,rs,sg=s.pressure_bar,s.rs_sm3_sm3,s.sg
        pv=m.rock.pore_volume_m3(m.grid.bulk_volumes_m3,p); bo=m.pvt.bo(p,rs); bg=m.pvt.bg(p)
        m.pvt=_NoViscosityPVT(m.pvt); oi,gi=m.component_inventories(s)
        self.assertEqual(oi.tobytes(),(pv*(1.0-sg)/bo).tobytes()); self.assertEqual(gi.tobytes(),(pv*(rs*(1.0-sg)/bo+sg/bg)).tobytes())
    def test_old_inventories_once_per_state(self):
        # Three residuals with one state_old, as inside a Jacobian: inventories of the new state every
        # time, of state_old once -> 3 + 1 = 4 calls of component_inventories (6 before DEBT-036)
        m,s,mask=_mixed_state(); z=m.pack(s,mask); calls=[]; inner=m.component_inventories
        m.component_inventories=lambda st: (calls.append(st),inner(st))[1]
        for d in (0.0,1e-3,-2e-3): m.residual(z+d,s,60.0,mask)
        self.assertEqual(len(calls),4)
    def test_residual_bitwise_fresh_model(self):
        # With the cache filled, every residual equals bitwise the one of a fresh model (empty cache)
        m,s,mask=_mixed_state(); z=m.pack(s,mask)
        for d in (0.0,1e-3,-2e-3):
            fresh,_,_=_mixed_state()
            self.assertEqual(m.residual(z+d,s,60.0,mask).tobytes(),fresh.residual(z+d,s,60.0,mask).tobytes())
    def test_old_inventories_follow_in_place_change(self):
        # state_old changed in place between residuals (the same object): fresh inventories are
        # used, not stale ones -- the key is the bytes of p, Rs, Sg, not the object
        m,s,mask=_mixed_state(); z=m.pack(s,mask); m.residual(z,s,60.0,mask)
        s.pressure_bar[2]+=0.7; s.sg[1]+=0.01
        fresh,_,_=_mixed_state()
        self.assertEqual(m.residual(z,s,60.0,mask).tobytes(),fresh.residual(z,s,60.0,mask).tobytes())

if __name__=='__main__': unittest.main()
```

Код `test_pvto_vectorized.py` (шаг 4 — всё, кроме двух последних тестов и импорта `CP_TO_PA_S`; шаг 5 — они):

```python
import unittest, numpy as np
from radial_blackoil.pvt import BlackOilPVT
from radial_blackoil.units import CP_TO_PA_S
from tests.helpers import model_and_state

# DEBT-036: BlackOilPVT interpolates PVTO for all cells at once (_oil_props).  Bo and mu_o enter
# every residual of the Newton solve and, through the GPN adapter, the energy equation: they must
# stay bitwise the former per-segment loop with np.interp per branch, reproduced below verbatim.
# The prototype regression against golden/ (abs 2e-7 / rel 2e-10) depends on it.
def _former_oil_prop(pvt,p,rs,which):
    """BlackOilPVT._oil_prop with _branch_prop_delta before DEBT-036, verbatim."""
    p_arr,rs_arr=np.broadcast_arrays(np.asarray(p,float),np.asarray(rs,float))
    shape=p_arr.shape; pf=p_arr.ravel(); rf=rs_arr.ravel(); out=np.empty_like(pf,dtype=float)
    rr=np.clip(rf,pvt.rs_values[0],pvt.rs_values[-1])
    j=np.searchsorted(pvt.rs_values,rr,side='right')-1
    j=np.clip(j,0,len(pvt.rs_values)-2)
    for jj in np.unique(j):
        loc=(j==jj); ids=np.nonzero(loc)[0]
        r0,r1=pvt.rs_values[jj],pvt.rs_values[jj+1]
        rrj=rr[loc]; ppj=pf[loc]
        w=(rrj-r0)/(r1-r0)
        pbq=pvt.pb[jj]+w*(pvt.pb[jj+1]-pvt.pb[jj])
        dp=np.maximum(ppj-pbq,0.0)
        def branch(rs_branch):
            x,bo,mu=pvt._branch_arrays[float(rs_branch)]
            return np.interp(dp,x,bo if which=='bo' else mu)
        v0=branch(r0); v1=branch(r1)
        out[ids]=v0+w*(v1-v0)
    return out.reshape(shape)

GAS=[(1.0,0.9,0.011),(400.0,0.003,0.03)]

def _irregular_table():
    """7 Rs branches of 2...8 rows with uneven pressure steps: knots of different branches interleave."""
    rng=np.random.default_rng(7); rows=[]
    for k,rs in enumerate((0.0,15.0,40.0,41.5,90.0,150.0,260.0)):
        pb=20.0+1.1*rs; d=np.concatenate([[0.0],np.cumsum(rng.uniform(3.0,40.0,k+1))])
        rows+=[(rs,pb+x,1.05+0.0012*rs-1e-4*x,2.0-0.004*rs+3e-3*x) for x in d]
    return BlackOilPVT(rows,GAS)

def _tables():
    """Fixture Nabor_1b (6 branches of 5 rows), the irregular table, a table with a one-row branch."""
    inp,_,_=model_and_state(n=3)
    # A one-row branch (Rs = 30): the GPN CSV reader does not forbid it; np.interp returns its only value
    one_row=BlackOilPVT([(0,20,1.05,3.0),(0,80,1.04,3.1),(30,120,1.2,1.5),(60,170,1.3,1.2),(60,260,1.28,1.4)],GAS)
    return (('Nabor_1b',inp.pvt),('irregular',_irregular_table()),('one-row branch',one_row))

def _points(pvt):
    """Grid p x Rs through the special points, random pairs, NaN and +inf."""
    # Rs: the branches exactly and one ulp off them, segment midpoints, outside the table (end
    # branches are used, no extrapolation).  p: every PVTO knot pressure exactly and one ulp off it
    # (at Rs of a branch dp then hits its knots exactly), 7.5 bar above the knots, p below Pb, far
    # above the branch tops.
    rng=np.random.default_rng(36); rs_v=pvt.rs_values; lo,hi=rs_v[0],rs_v[-1]
    rs_pts=np.concatenate([rs_v,np.nextafter(rs_v,np.inf),np.nextafter(rs_v,-np.inf),0.5*(rs_v[1:]+rs_v[:-1]),[lo-5.0,hi+5.0],rng.uniform(lo-5.0,hi+5.0,20)])
    knots=np.array([r[0] for k in rs_v for r in pvt.branches[float(k)]])
    p_pts=np.concatenate([knots,np.nextafter(knots,np.inf),np.nextafter(knots,-np.inf),knots+7.5,[1.0,knots.max()+100.0],rng.uniform(1.0,knots.max()+50.0,50)])
    P,R=np.meshgrid(p_pts,rs_pts)
    p=np.concatenate([P.ravel(),rng.uniform(1.0,knots.max()+50.0,5000),[np.nan,100.0,np.inf]])
    rs=np.concatenate([R.ravel(),rng.uniform(lo-5.0,hi+5.0,5000),[lo,np.nan,hi]])
    return p,rs

class PvtoVectorizedTests(unittest.TestCase):
    def test_bo_mu_bitwise_former_loop(self):
        # Bitwise the former loop on every point of _points, including NaN (NaN as before) and
        # p = +inf (the branch top, as np.interp).  At +inf the discarded branch of np.where computes
        # 0*inf: the RuntimeWarning is silenced, the value is not used.
        for name,pvt in _tables():
            p,rs=_points(pvt)
            with np.errstate(invalid='ignore'):
                for which,f in (('bo',pvt.bo),('mu',pvt.mu_o)):
                    self.assertEqual(f(p,rs).tobytes(),_former_oil_prop(pvt,p,rs,which).tobytes(),f'{name} {which}')
    def test_shapes_as_before(self):
        # The well and outer faces call with scalars (0-d result), two_phase_analytics.py with a scalar
        # p and an array Rs; 2-D input keeps its shape; empty input gives an empty result
        for name,pvt in _tables():
            p,rs=_points(pvt)
            for pp,rr in ((150.0,30.0),(np.float64(p[9]),np.array(rs[9])),(float(p[5]),rs[:20]),(p[:20],float(rs[3])),(p[:12].reshape(3,4),rs[:12].reshape(3,4))):
                a=pvt.mu_o(pp,rr); b=_former_oil_prop(pvt,pp,rr,'mu')
                self.assertEqual((a.shape,a.tobytes()),(b.shape,b.tobytes()),name)
            self.assertEqual(pvt.bo(np.empty(0),np.empty(0)).shape,(0,))
    def test_single_rs_branch_rejected(self):
        # One Rs branch: the former code divided 0/0 between the branch and itself (NaN Bo, mu_o in
        # every cell, the run failed later); now the table is rejected when built
        with self.assertRaisesRegex(ValueError,'Rs branches'):
            BlackOilPVT([(10,50,1.1,2.0),(10,100,1.09,2.1)],GAS)
    def test_bo_mu_o_one_pass(self):
        # bo_mu_o shares the segment and row search of Bo and mu_o: bitwise bo and mu_o called apart
        for name,pvt in _tables():
            p,rs=_points(pvt)
            with np.errstate(invalid='ignore'):
                bo,mu=pvt.bo_mu_o(p,rs)
                self.assertEqual(bo.tobytes(),pvt.bo(p,rs).tobytes(),name); self.assertEqual(mu.tobytes(),pvt.mu_o(p,rs).tobytes(),name)
    def test_mobilities_one_pvto_pass(self):
        # _phase_mobilities_surface takes Bo and mu_o from one bo_mu_o call where the PVT has it
        # (BlackOilPVT); the mobilities are bitwise those from bo and mu_o
        _,m,s=model_and_state(n=5,p0=160); p,rs,sg=s.pressure_bar,s.rs_sm3_sm3,np.full(5,0.05)
        calls=[]; real=m.pvt
        class Spy:
            def __getattr__(self,name):
                calls.append(name); return getattr(real,name)
        m.pvt=Spy(); lo,lg=m._phase_mobilities_surface(p,rs,sg); m.pvt=real
        self.assertIn('bo_mu_o',calls); self.assertNotIn('mu_o',calls)
        lo_ref=m.relperm.kro(sg)/(real.mu_o(p,rs)*CP_TO_PA_S)/real.bo(p,rs); lg_ref=m.relperm.krg(sg)/(real.mu_g(p)*CP_TO_PA_S)/real.bg(p)
        self.assertEqual(lo.tobytes(),lo_ref.tobytes()); self.assertEqual(lg.tobytes(),lg_ref.tobytes())
        # A PVT without bo_mu_o (as the Standing adapter): bo and mu_o apart, the same mobilities
        class NoOnePass:
            def __getattr__(self,name):
                if name=='bo_mu_o': raise AttributeError(name)
                return getattr(real,name)
        m.pvt=NoOnePass(); lo2,lg2=m._phase_mobilities_surface(p,rs,sg); m.pvt=real
        self.assertEqual(lo2.tobytes(),lo_ref.tobytes()); self.assertEqual(lg2.tobytes(),lg_ref.tobytes())

if __name__=='__main__': unittest.main()
```

Счёт тестов прототипа по шагам: 83 → 84 (шаг 2) → 87 (шаг 3) → 90 (шаг 4) → 92 (шаг 5). Тестов `numerical_solver`: без изменений (1223 на `4136f3c`).

**Регресс по существующим тестам**, покрывающим затронутый код:
- прототип — `test_pvt_clamp.py` (ограничения PVTO по $R_s$ и $p$), `test_physics.py` (баланс, положительность запасов), `test_grouped_jacobian.py` (побитовость якобиана — через невязку), `test_pvt_kink_jacobian.py`, `test_input_contract.py` (`bubble_point_max_rs_bar`), `test_input_validation_extra.py` (ошибка газовой таблицы раньше проверки ветвей);
- `numerical_solver` — `test_prototype_adapter.py`, `test_prototype_well_branch.py` (`component_inventories`), `test_hydro_to_blackoil_adapter.py`, `test_examples.py` (slow).

**Инвариант на примерах:** снимки историй `history_snapshot.py` (20 примеров: p, Sg, Rs, T, regime, t, G_o, G_g) — `compare base new` без различий.

## Критерии завершения

- [ ] Шаги 1–8 выполнены.
- [ ] Тесты `numerical_solver`: полный уровень — все passed (1223 на `4136f3c`, или число шага 1).
- [ ] Тесты прототипа: 92 passed; полная регрессия `run_regression.py` 17/17 PASS (побитово, эталон не переснимался).
- [ ] Истории 20 примеров побитово (`history_snapshot.py compare base new` → различий 0); `planned_code_check.py unit` → 30 таблиц.
- [ ] `_branch_prop_delta`, `_oil_prop` удалены из кода: `Select-String -Path numerical_solver\HydroSolverPrototype\Prototype_1.0.3\radial_blackoil\*.py -Pattern '_oil_prop\b|_branch_prop_delta'` — пусто. В тестах (эталон `_former_oil_prop`) и в CHANGELOG имена остаются — так и задумано.
- [ ] Замер: невязка примера 14 в якобиане уменьшилась не менее чем вдвое; числа «было → стало» в CHANGELOG и vault.
- [ ] CHANGELOG, docstring, `hydro-prototype-анализ.md` обновлены.
- [ ] Vault: статус DEBT-036, комментарий в #59 (закрывается при слиянии).

## Обнаруженные проблемы

1. **CSV-путь фабрики не проверяет ветви PVTO** (`gpn_multiphase_solver/factory.py:_read_oil_pvt_csv`, `:371-395`). XLSX-ридер прототипа проверяет «≥ 2 строки в ветви» и «давление растёт внутри ветви» (`radial_blackoil/input_reader.py:60-64`); CSV-путь — ничего. После шага 4 `BlackOilPVT` отклоняет таблицу с одной ветвью $R_s$ в обоих путях. Ветвь из одной строки и повторяющиеся давления по-прежнему проходят: значения прежние, при повторе — `RuntimeWarning` при построении. Задачу не блокирует; регистрируется как **DEBT-038**.
2. **Решение для пользователя (аудит):** таблица с одной ветвью $R_s$. Прежний код давал NaN без ошибки (деление $0/0$ между ветвью и ею же). Варианты:
   - **а) `ValueError` при построении** — рекомендуется. Ни один рабочий конфиг не ломается: с одной ветвью расчёт и раньше падал. В тексте ошибки стоит назвать причину.
   - **б) без проверки:** `IndexError` при первом вызове `bo` — непонятное сообщение.
   - **в) поддержать одну ветвь** как нефть без растворённого газа ($w = 0$, свойства по единственной ветви при любом $R_s$). Физически осмысленно, но это новая возможность, а не ускорение; в ECLIPSE такая нефть задаётся отдельным ключевым словом PVDO, а не PVTO. Если нужно — отдельная задача FEAT.
3. **Решение для пользователя (аудит):** вариант 5 — PVT ячеек один раз на невязку, грани берут выборкой (раздел «Не рассмотрено при планировании»). Оценка около −0.3 мс из 0.74 у примера 14, не замер; требует правки кода потоков. Рекомендация — отдельная задача DEBT после влития DEBT-036.

## Оценка

- Файлов: 2 кода (`pvt.py`, `blackoil.py`), 2 новых теста, CHANGELOG, заметка vault.
- Строк: ~65 кода, ~140 тестов, ~30 документации.
- Время: ~3 ч, из них ~1 ч — регрессия прототипа (быстрая и полная) и полный прогон `tests/`.

## Связанные заметки

- [[известные баги и технический долг]] — запись DEBT-036; [[DEBT-033]] (якобиан), [[DEBT-032]] (уровни тестов), [[DEBT-038]] (проверка ветвей PVTO в CSV-пути)
- [[hydro-prototype-анализ]] — §2 «PVT», §6 «Якобиан»
- [[P1-адаптер-единицы]] — единицы `component_inventories` (м³ст)
- [[debt-033 vectorize-grouped-jacobian]] — план-образец, пробы `history_snapshot.py`, `time_jacobian.py`
- Пробы: `vault/issues/debt-036/probes/` (в `.gitignore`)
