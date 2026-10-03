---
tags:
  - план
  - рефакторинг
date: 2026-10-03
issue: DEBT-028
github: 60
branch: refactor/debt-028/compute-fluxes-shutin-upwind
status: в процессе
audit:
  date: 2026-10-03
  found: 8
  auto-fixed: 8
  manual-required: 0
---

# DEBT-028: общий шаг «Q, u, m из G» для обоих гидро-путей и закрытие скважины в `compute_fluxes` — план

## Кратко

Потоки через грани считаются в два шага: (1) потоки компонентов $G^o, G^g, G^{св.газ}$ (м³ст/с), (2) производные величины для энергии — объёмные расходы фаз $\mathcal{Q}_\alpha$, скорости $u_\alpha$, массовые расходы $m_\alpha$, $Gm_\alpha$. Шаг 2 сейчас написан **дважды**: в рабочем пути (`PrototypeHydroAdapter._build_result`) и в пути тестов (`compute_fluxes`), и копии расходятся в трёх местах. План:

1. выносит шаг 2 в одну функцию `fluxes.phase_fluxes_from_components`, которую вызывают оба пути — тесты энергии, `Simulator`, VAL-001/002 начинают проверять **рабочий** код шага 2;
2. делает выбор ячейки выше по потоку в адаптере таким же, как в прототипе (по перепаду давления, а не по знаку $G^o$) — устраняет **подтверждённое замером** расхождение при $k_{ro} = 0$;
3. закрывает скважину в `compute_fluxes` при $p[0] \le p_{wf}$ по `eq:bc_pwf_shutin` вместо закачки через забой;
4. попутно закрывает [[DEBT-021]]: $\rho_g$ на контуре при притоке — $\rho_g(p_{ext})$ в обоих путях.

- Подтип: рефакторинг (устранение дублирования) + исправление тестового пути на забое.
- Решения пользователя (2026-10-03): забой — закрытие скважины (не `ValueError`); вариант А — общий шаг «$Q, u, m$ из $G$» (не одна строка в адаптере и не только общая функция выбора ячейки); DEBT-021 закрывается этой задачей.
- Шагов: 7 (подготовка, фикстура, закрытие скважины, общий шаг, адаптер, документация, vault).
- Код: `fluxes.py` — переписывается (~180 → ~200 строк, из них ~95 — общая функция, перенесённая из адаптера); `prototype_adapter.py` — минус ~75 строк; тесты — ~150 строк новых, ~15 изменённых.
- Прототип (`HydroSolverPrototype/`) **не меняется** — его тесты и регрессия не нужны.
- **Код шагов 3–5 проверен при планировании** подменой в памяти (пробы в `vault/issues/debt-028/probes/`, см. раздел «Проверка при планировании»): новые тесты на текущем коде падают ровно там, где должны (16 шт.), на коде плана проходят все; быстрый уровень с кодом плана — 976 passed, 11 failed (ровно тесты грани 0 старой фикстуры, которую меняет шаг 2); истории всех 20 примеров с кодом плана — **побитово** прежние (включая $T$, $\mathcal{Q}_\alpha$, $u_\alpha$, $m_\alpha$).

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай: запись DEBT-028 и DEBT-021 в `vault/roadmap/известные баги и технический долг.md`; issue #60 (`gh issue view 60 --repo ArturSalamatin/Oil_Gas`); `vault/knowledge/decisions/свойства-фаз-на-контурной-грани-берутся-из-ГУ-при-притоке.md`; `vault/knowledge/decisions/конвенции-знаков.md`.
3. Ветка от базовой `numerical_scheme/implementation` (проверка: `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`): `git checkout -b refactor/debt-028/compute-fluxes-shutin-upwind` (или worktree `.worktrees/debt-028` — так делает `/implement`).
4. Venv: `numerical_solver\.venv\Scripts\python` основного каталога (в worktree своего `.venv` может не быть — тогда полный путь `d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python`).
5. Baseline (шаг 1 расписывает подробно), из `numerical_solver`:
   - `.venv\Scripts\python -m pytest tests/ --collect-only -q` → **1223** (после влития DEBT-026, `4136f3c`; если влито что-то ещё — взять фактическое число и пересчитать ожидания шагов: +14, +3, +1);
   - `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` → **999 passed** (~70–90 с);
   - снимок историй примеров `save base_impl` (~4–8 мин; метка `base` занята снимком планирования).
6. Запомни числа тестов и время быстрого уровня — это baseline.
7. Начни с шага 1. После каждого шага: тесты шага и регресс по полю «Регресс»; полный прогон `tests/` — в конце (`/implement` §3.1).

⚠️ **Пробы лежат только в основном каталоге.** `vault/issues/` — в `.gitignore`, в worktree каталога `vault/issues/debt-028/probes/` нет. Скрипт снимка историй запускается по абсолютному пути основного каталога **из каталога `numerical_solver` того дерева, чей код проверяется**: он берёт код из каталога запуска (`Path.cwd()`) и первой строкой stdout печатает `код: <путь radial_blackoil> | <путь gpn_multiphase_solver>`. Если в строке не путь worktree — сравнение недействительно. stdout буферизуется: строка `код:` и строки `<пример>: N записей` появляются в файле вывода в конце прогона, лог `[INFO]` (stderr) — по ходу.

```powershell
# из <дерево>\numerical_solver
$P = "d:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\debt-028\probes"
d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python $P\history_snapshot.py save base_impl *> $P\save_base_impl.txt
```

## Контекст для читателя без контекста

### Два гидро-пути

Гидродинамику (давление $p$, газонасыщенность $S_g$, газосодержание $R_s$) в рабочем расчёте решает прототип `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/` (код коллеги, единицы — бар). Обёртка `PrototypeHydroAdapter` (`numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`) переводит единицы и собирает `HydroResult` — потоки через все $N+1$ граней, которые дальше берёт решатель энергии (`energy/tridiag.py`).

`compute_fluxes` (`numerical_solver/gpn_multiphase_solver/fluxes.py`) — **второй** путь: по заданному состоянию считает $G$ по закону Дарси и затем $\mathcal{Q}, u, m$. В рабочем расчёте не вызывается. Его вызывают тесты (`test_fluxes.py`, `test_energy.py`, `test_hydro.py`, `test_val002.py`) и тестовый двойник `tests/_doubles.py::LogProfileHydroStub` (на нём — `test_simulator.py`, `test_output.py`, `test_val001.py`, `test_hydro.py`).

### Шаг «Q, u, m из G» и его две копии

Из потоков компонентов (м³ст/с) энергии нужны:
- $\mathcal{Q}_o = G^o \cdot B_o^{up}$, $\mathcal{Q}_g = G^{св.газ} \cdot B_g^{up}$ — объёмные расходы фаз при пластовых условиях, м³/с (`eq:phase_flux`: $G^o = \mathcal{T}\,\frac{k_{ro}}{\mu_o B_o}\Delta p$, поэтому $G^o B_o = \mathcal{T}\frac{k_{ro}}{\mu_o}\Delta p$);
- $u_\alpha = \mathcal{Q}_\alpha / (2\pi h r_f)$ — скорость фильтрации на грани;
- $m_\alpha = \rho_\alpha^{up}\,\mathcal{Q}_\alpha$ — массовый расход фазы, $Gm_\alpha = \rho_{\alpha,ст}\,G$ — компонента.

Индекс $up$ — ячейка **выше по потоку** (откуда течёт флюид): её свойства $B_\alpha, \rho_\alpha$ берутся для грани.

| | Кто вызывает | $\mathcal{Q}$ | Ячейка выше по потоку на внутренней грани | $\rho_g$ на контуре при притоке |
|---|---|---|---|---|
| адаптер, `prototype_adapter.py:184-241` | рабочий расчёт | $G \cdot B_{up}$ | **по знаку $G^o$**: `up = f if G_o[f] < 0 else f - 1` (стр. 204) | $\rho_g(p_{ext})$ (стр. 228) |
| `compute_fluxes`, `fluxes.py:77-164` | тесты | $\mathcal{T}\frac{k_r}{\mu}\Delta p$ | по знаку $\Delta p$: `dp >= 0 → f-1` (стр. 86-90) | `0.0` (стр. 151) |
| прототип, `blackoil.py:160` | — (считает $G$) | — | по знаку $\Delta p$: `left = dp >= 0` | — |

**Расхождение 1 — выбор ячейки при $k_{ro} = 0$.** Если в ячейке выше по потоку $k_{ro} = 0$ ($S_g \ge 1 - S_{or}$), прототип отдаёт $G^o = 0$ (точнее `-0.0`). Условие адаптера `G_o[f] < 0` ложно, и он берёт ячейку $f-1$ — **ниже** по потоку: $\mathcal{Q}_g, u_g$ получают $B_g$ не той ячейки. $m_g$ не страдает: $\rho_g B_g = \rho_{g,ст}$ (`pvt/base.py:74`), так что $m_g = \rho_{g,ст} G^{св.газ}$ при любом выборе. **Подтверждено замером**: тест `TestUpstreamWithZeroKro` (шаг 5) на текущем коде падает (проба `test_planned_debt028.py`). В рабочих примерах не проявляется: во всех 20 историях $k_{ro} > 0$ с большим запасом — максимум $S_g$ 0.70 при пороге 1.0 (04a), 0.45 при пороге 0.95 (19–21), остальные ≤ 0.26 при пороге 0.8 (проба `kro_zero_in_histories.py`, вывод `.txt`; видны только сохранённые записи, не каждый шаг).

**Расхождение 2 — $\rho_g$ на контуре при притоке** ([[DEBT-021]]): `0.0` против $\rho_g(p_{ext})$. Ненаблюдаемо: на контуре $S_g = 0$, $G^{св.газ}[N] = 0$, $\mathcal{Q}_g[N] = 0$, и $m_g[N] = 0$ при любом $\rho_g$. Целевое значение — $\rho_g(p_{ext})$: так рекомендует сама запись DEBT-021 (вариант 2), так решено для энергии в [[DEBT-017]] (решение Р-1, `tridiag.py:276-284`), так делает адаптер.

**Расхождение 3 — забой.** Постановка `eq:bc_pwf_shutin` (`numerical_solver/doc/problem_statement.tex:689-705`; дискретно — стр. 1736-1747, абзац «Закрытие скважины»): скважина только добывающая; при $p_0 \le p_{wf}$ ($p_0$ — давление в ячейке 0) она закрыта — потоки через забой нулевые, фактическое $p_{wf}$ шага равно $p_0$. Прототип делает ровно это (`blackoil.py:116-131`, ветвь `'shut'`: `bhp=p0; qow=0.0; qgfw=0.0`), адаптер берёт фактическое $p_{wf}$ из `well_rates` (`prototype_adapter.py:252`). `compute_fluxes` (`fluxes.py:112-129`) знак `dp_w` не проверяет: при $p_{wf} > p[0]$ считает **закачку** ($G^o_{1/2} > 0$) со свойствами ячейки 0 (это ячейка ниже по потоку) и возвращает `p_wf` = уставке. `HydroResult.p_wf` берёт энергия (`energy/tridiag.py:120`).

На закачке построена двухфазная фикстура `tests/test_fluxes.py:326-355`: `state_2ph` с $p = (8, 10, 13, 16, 19)$ МПа и `bc_2ph` с `PressureControl(P_WF)`, `P_WF = 10e6` → $\Delta p_w = +2$ МПа. На ней 82 теста: `TestTwoPhaseAllFields` (66 = 11 полей × 6 граней), `TestTwoPhaseConcreteValues` (7, грань 1), `TestTwoPhaseGDecomposition` (6), `TestTwoPhaseExtBoundary` (3). Остальные вызовы `compute_fluxes` идут при $p[0] \ge p_{wf}$ (проверено по всем фикстурам: логарифмический профиль от $p_{wf}$ к $p_{ext} > p_{wf}$ или $p[0] \in \{10, 12, 15\}$ МПа при `P_WF = 10e6`; в `TestUniformPressure` и `TestMaxGasSaturation` $p[0] = p_{wf}$ — потоки нулевые и до, и после правки).

### Почему DEBT-019 упомянут в тестах

[[DEBT-019]] планировал запретить втекание через забой (`ValueError`), но закрыт 2026-10-01 без реализации: дефект энергии устранён [[BUG-012]], ограничение «только добыча» дали [[FEAT-020]]/[[FEAT-023]]; `compute_fluxes` вынесен в DEBT-028. Два места в тестах ссылаются на неисполненный план DEBT-019 — их правит шаг 3.

## Baseline

| Что | Значение | Как получено |
|---|---|---|
| Число тестов | 1223 | `pytest tests/ --collect-only -q`, 2026-10-03, HEAD `4136f3c` (аудит; при планировании на `c51e137` было 1210 — затем влит DEBT-026, +13 тестов) |
| Быстрый уровень | 999 (224 отобраны меткой `slow`) | `pytest tests/ --collect-only -q -m "not slow"` |
| Время быстрого уровня | ~70–90 с | CLAUDE.md; с подменой при планировании — 88.7 с (параллельно шли два снимка историй) |
| Пакет `gpn_multiphase_solver` с влития DEBT-033 | не менялся | `git log f4cb6a8..4136f3c -- numerical_solver/gpn_multiphase_solver` пуст; DEBT-026 менял только `examples/` (README, `main.py` 03, 05, `rs_analytics.py`, `pvt_plot.py`) и тесты `test_examples.py`, `test_rs_analytics.py` — ни одного файла этого плана, номера строк плана в силе (проверено аудитом); `config.json` примеров не менялись — снимок планирования действителен (аудит: пример 01 на `4136f3c` побитово равен `base`) |

## Целевое состояние

- `fluxes.py`:
  - новая `phase_fluxes_from_components(G_o, G_g, G_free_gas, state, grid, pvt, bc, p_wf, n_substeps=1) -> HydroResult` — шаг «$\mathcal{Q}, u, m, Gm$ из $G$»: выбор ячейки выше по потоку (внутренние грани — по $\Delta p$; забой — ячейка 0; контур — контур при притоке, ячейка $N-1$ при оттоке), формулы, сборка `HydroResult`. Код — перенос из адаптера (`prototype_adapter.py:184-263`) с одной правкой: условие выбора ячейки по $\Delta p$ вместо знака $G^o$, на внутренних гранях и на контуре;
  - `compute_fluxes` — только $G$ по Дарси (eq:flux_oil, eq:flux_gas, eq:bc_flux_well, eq:bc_flux_ext) + закрытие скважины + вызов общей функции. Массивы `Q_o, Q_g, u_o, u_g, m_o, m_g` и подвижности `lam_o, lam_g`, плотности `rho_o, rho_g` из него уходят.
- `hydro/prototype_adapter.py::_build_result` — $G$ от прототипа (инверсия знака забоя), фактическое $p_{wf}$, вызов общей функции. Импорт `from ..fluxes import phase_fluxes_from_components`.
- Граф импортов: `hydro/prototype_adapter.py → fluxes.py → state, bc, grid.base, pvt.base`. Цикла нет: `fluxes.py` и его зависимости `hydro` не импортируют (проверено: `state.py` импортирует только `bc` под `TYPE_CHECKING`, `__init__.py` пакетов `pvt`, `grid` — только свои модули).
- Внешний API не меняется: сигнатура `compute_fluxes`, `HydroResult`, `PrototypeHydroAdapter.solve` — прежние. Новая функция — добавление.
- Поведение:
  - рабочий расчёт — **побитово прежний** на всех 20 примерах (расхождение 1 в них не проявляется; формулы и порядок операций перенесены без изменений);
  - `compute_fluxes` — $\mathcal{Q}, u, m$ меняются на округление (≤ 4.4e-16 относительно, проба `q_from_g_roundoff.py`), что на 1.5 порядка ниже самого жёсткого допуска тестов (`rel=1e-14`, `TestOnePhasePerFace`); на забое при $p[0] \le p_{wf}$ — нули и `p_wf = p[0]`.

## Варианты и выбор

Подробный анализ — issue #60 и обсуждение с пользователем 2026-10-03.

| Вариант | Что снимает | Почему не выбран / выбран |
|---|---|---|
| А. Общий шаг «$Q, u, m$ из $G$» | расхождения 1, 2, 3 (+3 — правкой забоя); тесты начинают проверять рабочий код шага 2 | **выбран** (решение пользователя): единственный, убирающий само дублирование |
| Б. Общая функция выбора ячейки | только 1 | формулы $Q, u, m$ остаются в двух копиях, DEBT-021 остаётся |
| В. Одна строка в адаптере | только 1 | дублирование не трогается |
| Забой: `ValueError` вместо закрытия | 3 | отклонён пользователем: закрытая скважина — штатный режим постановки (FEAT-023, пример 13б), путь тестов перестал бы его покрывать |

`compute_fluxes` по-прежнему сам считает $G$ по Дарси — это копия **прототипа**, а не адаптера. Объединить её с прототипом нельзя: прототип — отдельный пакет в барах со своей невязкой и якобианом; путь тестов нужен именно затем, чтобы по заданному профилю $p(r)$ получить потоки без решения уравнения фильтрации.

## Подводные камни (чеклист)

| Пункт | Статус | Комментарий |
|---|---|---|
| Все места вызова найдены | ✅ | `compute_fluxes`: `fluxes.py`, `tests/test_fluxes.py` (13), `test_energy.py` (12), `test_hydro.py` (8), `test_val002.py` (3), `_doubles.py` (4), упоминание в docstring `bc.py:4`. `_build_result`: только `prototype_adapter.py:131`. Новая функция — новые вызовы в двух местах |
| Зависимости пакетов | ✅ | `pyproject.toml` не меняется |
| Обратная совместимость API | ✅ | сигнатуры прежние; `n_substeps` проходит через новую функцию (тест `test_pwf_and_substeps_passed_through`) |
| Состояние при ошибке | ✅ | новая функция чистая (без побочных эффектов); `NotImplementedError` для `RateControl` в `compute_fluxes` остаётся до вычислений |
| Тесты | ⚠️ | 11 тестов `TestTwoPhaseAllFields[*-0]` упадут, если шаг 3 сделать до шага 2 (замер с кодом плана) — порядок шагов 2 → 3 обязателен. 4 места в `test_prototype_adapter.py` повторяют старое правило выбора ячейки — проходят и после правки (в фикстуре $k_{ro} > 0$), но правятся на новое правило (шаг 5) |
| Циклические импорты | ✅ | см. «Целевое состояние» |
| Docstrings / `\eqref` | ✅ | `eq:phase_flux`, `eq:flux_oil`, `eq:flux_gas`, `eq:bc_pwf_shutin`, `eq:bc_flux_ext` существуют (`problem_statement.tex:1302, 999, 1005, 697, 1784`) |
| Ссылки на строки `fluxes.py` | ⚠️ | `energy/tridiag.py:215` («как в fluxes.py:47-52», уже неверно) и `:268` («fluxes.py:143-145») — после шага 4 номера бессмысленны; шаг 4 заменяет их ссылками на функции. Это комментарии: матрица энергии не меняется, `test_matrix_matches_reference` не затронут |
| Configs | ✅ | имена параметров не меняются |
| Связь с другими задачами | ✅ | DEBT-021 закрывается здесь (решение пользователя). [[DEBT-036]] (#59, ускорение невязки прототипа на табличном PVT) меняет прототип (`radial_blackoil`), его план сам отмечает, что с DEBT-028 не пересекается; он обещает побитовость историй. Если DEBT-036 вольют раньше — снимок `base_impl` всё равно снимается на ветке этой задачи (шаг 1), сравнение остаётся корректным |
| Производительность | ✅ | адаптер выполняет те же операции в том же порядке (цикл по граням перенесён как есть); `compute_fluxes` — на 2 PVT-вызова и 2 массива меньше |
| Прототип | ✅ | не меняется — регрессия прототипа не нужна |
| Побитовость рабочего пути | ⚠️ | правило выбора ячейки теперь по $\Delta p$ в Па (`new_state.p`), прототип — в барах. Умножение на $10^5$ монотонно, знаки могут разойтись только при $|\Delta p|$ в 1 ULP — тогда $G \approx 0$, и вклад грани пренебрежим. Проверяет снимок историй (шаг 5): ожидание — 20/20 побитово |
| Тестовый двойник `LogProfileHydroStub` | ✅ | строит профиль от $p_{wf}$ к $p_{ext}$ и зовёт `compute_fluxes`; все его вызовы (`test_hydro.py`, `test_simulator.py`, `test_output.py`, `test_val001.py`) — с $p_{ext} > p_{wf}$, т. е. добыча. При $p_{ext} < p_{wf}$ двойник после шага 3 дал бы закрытый забой при потоке внутри — профиль несогласован; таких вызовов нет, правка двойника не нужна (аудит) |
| Отрицательный ноль | ✅ | при закрытии $G = \mathcal{T}\cdot\lambda\cdot 0.0 = +0.0$; у адаптера при закрытии `-0.0` (инверсия знака) — `-0.0 == 0.0` истинно, тесты сравнивают с `0.0` |

## Шаги

### Шаг 1: Подготовка — ветка, baseline, снимок историй

**Цель:** зафиксировать исходное состояние тестов и историй примеров до правок.

**Файлы:** нет изменений в коде.

**Что сделать:**
1. Ветка/worktree от `numerical_scheme/implementation` (см. «Как начать работу»).
2. Из `numerical_solver` дерева задачи:
   - `.venv\Scripts\python -m pytest tests/ --collect-only -q` → ожидание **1223**;
   - `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` → ожидание **999 passed**; записать время.
3. Снимок историй всех 20 примеров **текущим** кодом:
   ```powershell
   $P = "d:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\debt-028\probes"
   d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python $P\history_snapshot.py save base_impl *> $P\save_base_impl.txt
   ```
   Проверить в `save_base_impl.txt`: строка `код:` указывает на дерево задачи; 20 строк `<пример>: N записей`. Метка `base_impl` — чтобы не перезаписать снимок `base` планирования. Скрипт сохраняет $p, S_g, R_s, T$, regime, $t$ и $G_o, G_g, \mathcal{Q}_o, \mathcal{Q}_g, u_o, u_g, m_o, m_g$ каждой записи истории (копия скрипта DEBT-033 с добавленными $\mathcal{Q}, u, m$ — именно их меняет правка адаптера).

**Проверка после этого шага:**
- Регресс: быстрый (это и есть baseline).

**Зависимости:** блокирует все шаги.

**Оценка:** 0 строк, ~10 мин (снимок 4–8 мин можно запустить в фоне и продолжать шаги 2–4: рабочий путь `fluxes.py` не импортирует, а `prototype_adapter.py` процесс снимка загрузил при старте. **До шага 5 снимок должен завершиться** — проверить 20 строк `записей` в `save_base_impl.txt`).

---

### Шаг 2: Двухфазная фикстура — на добычу ($p_{wf} = 6$ МПа)

**Цель:** 82 теста двухфазной фикстуры проверяют формулы при добыче, а не при закачке, которую постановка исключает.

**Файлы:** `numerical_solver/tests/test_fluxes.py`

**Контекст:** `bc_2ph` берёт `P_WF = 10e6` > $p[0]$ = 8 МПа. После шага 3 забой закроется, и `TestTwoPhaseAllFields[*-0]` (11 тестов) сверят нули с формулой эталона — замер с кодом плана: ровно эти 11 падают. Новая уставка 6 МПа < 8 МПа — добыча; на гранях 1..N значения от $p_{wf}$ не зависят, `TestTwoPhaseConcreteValues` (грань 1) не меняется (проверено пробой DEBT-019 `vault/issues/debt-019/probes/test_round2_fixture_2ph_fix.py`). `P_WF` нельзя просто поменять: на нём построен однофазный профиль `state_1ph` и аналитические числа `TestOnePhaseAnalyticalRate`.

**Что сделать:**
1. После `P_WF = 10e6` (стр. 40) добавить константу с комментарием.
2. `bc_2ph` (стр. 346-350) — на `P_WF_2PH`.
3. Docstring `TestTwoPhaseAllFields` (стр. 359): «72 проверки» → «66 проверок: 11 полей × 6 граней».

**Изменения:**

До (стр. 39-41):
```python
P_EXT = 20e6
P_WF = 10e6
T0 = 350.0
```
После:
```python
P_EXT = 20e6
P_WF = 10e6
# Забойное давление двухфазной фикстуры: ниже p[0] = 8 МПа — добыча.
# При P_WF = 10 МПа > p[0] скважина закрыта (eq:bc_pwf_shutin), и тесты
# грани 0 проверяли бы нули вместо формулы притока (DEBT-028).
P_WF_2PH = 6e6
T0 = 350.0
```

До (стр. 346-350):
```python
@pytest.fixture
def bc_2ph():
    return BoundaryConditions(
        well=PressureControl(P_WF), p_ext=P_EXT,
        T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)
```
После:
```python
@pytest.fixture
def bc_2ph():
    return BoundaryConditions(
        well=PressureControl(P_WF_2PH), p_ext=P_EXT,
        T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)
```

До (стр. 359): `"""Формула на каждой грани × каждое поле (72 проверки)."""`
После: `"""Формула на каждой грани × каждое поле (66 проверок: 11 полей × 6 граней)."""`

**Проверка после этого шага:**
- `.venv\Scripts\python -m pytest tests/test_fluxes.py -q` — все зелёные (число не меняется).
- Регресс: быстрый — 999 passed.

**Подводные камни:** грань 0 теперь с $\Delta p_w = -2$ МПа — эталон `_compute_reference_face` её считает той же формулой, что ядро (проверено пробой DEBT-019: все поля на всех гранях совпадают с `rel=1e-12`).

**Зависимости:** требует шаг 1; блокирует шаг 3.

**Оценка:** ~6 строк, ~5 мин.

---

### Шаг 3: Закрытие скважины в `compute_fluxes` (eq:bc_pwf_shutin)

**Цель:** при $p[0] \le p_{wf}$ путь тестов закрывает скважину, как постановка и прототип: потоки через забой нулевые, `HydroResult.p_wf = p[0]`.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/fluxes.py`
- `numerical_solver/tests/test_fluxes.py`
- `numerical_solver/tests/test_energy.py`
- `numerical_solver/tests/test_energy_matrix_examples.py`

**Контекст:** см. «Расхождение 3». Закрытие выражено нулевым перепадом: при `dp_w = 0.0` существующие формулы забоя дают $G = \mathcal{Q} = u = m = Gm = 0$ (все — произведения на `dp_w`), отдельная ветка с присвоением нулей не нужна. Граница $p[0] = p_{wf}$ — в ветке закрытия, как в прототипе (`'shut' if p0 <= target`) и в постановке («при $p_0 \le p_{wf}$ скважина закрыта»); при равенстве результат тот же, что и раньше (`TestUniformPressure`, `TestMaxGasSaturation` не меняются).

**Что сделать — сначала тесты (красные), потом код:**

⚠️ Номера строк `test_fluxes.py` в шагах 3–4 — по исходному файлу; шаг 2 вставил 4 строки после стр. 40, шаг 3 (п. 4) — ещё одну в эталоне. Править по тексту (`Edit` ищет `old_string`), номера — ориентир.

1. В `test_fluxes.py` после класса `TestTwoPhaseExtBoundary` (исходно заканчивается на стр. 425, после шага 2 — на 429; перед `def _get_Rs_up`) добавить класс:

```python
class TestWellShutIn:
    """Закрытие скважины при p_wf >= p[0] (eq:bc_pwf_shutin, DEBT-028).

    Скважина только добывающая: если заданное p_wf не ниже давления в
    ячейке 0, закачки нет — потоки через забой нулевые, а фактическое
    давление на забое равно p[0] (problem_statement.tex, «Закрытие
    скважины»). Так же поступает прототип (blackoil.py, _well_fluxes,
    ветвь 'shut'). Профиль — state_2ph, p[0] = 8 МПа; уставка 10 МПа > p[0].
    """

    @pytest.fixture
    def shut(self, state_2ph, grid_2ph, pvt, relperm):
        bc_shut = BoundaryConditions(
            well=PressureControl(10e6), p_ext=P_EXT,
            T_ext=T0, Rs_ext=RS0, Sg_ext=0.0)
        return compute_fluxes(state_2ph, grid_2ph, pvt, relperm, bc_shut)

    @pytest.mark.parametrize("field", TestTwoPhaseAllFields.FIELDS)
    def test_well_face_zero(self, shut, field):
        """Все 11 полей на грани 0 — нули.

        Ловит: закачку через забой (до DEBT-028 G_o[0] > 0 при p_wf > p[0]).
        """
        assert getattr(shut, field)[0] == 0.0

    def test_pwf_equals_p0(self, shut, state_2ph):
        """Фактическое p_wf = p[0] = 8 МПа, а не уставка 10 МПа.

        Ловит: возврат уставки — энергия берёт давление на забойной грани
        из HydroResult.p_wf (energy/tridiag.py), а не из управления.
        """
        assert shut.p_wf == state_2ph.p[0]

    def test_other_faces_unchanged(self, shut, result_2ph):
        """Грани 1..N побитово те же, что при добыче (p_wf = 6 МПа).

        Условие на забое входит только в поток грани 0. Ловит: закрытие,
        задевающее другие грани.
        """
        for field in TestTwoPhaseAllFields.FIELDS:
            np.testing.assert_array_equal(getattr(shut, field)[1:],
                                          getattr(result_2ph, field)[1:])

    def test_producing_pwf_is_setpoint(self, result_2ph):
        """При добыче (p_wf = 6 МПа < p[0]) фактическое p_wf = уставке."""
        assert result_2ph.p_wf == P_WF_2PH
```

2. Запустить `.venv\Scripts\python -m pytest tests/test_fluxes.py -q -k TestWellShutIn` — ожидание: **12 failed, 2 passed** (11 × `test_well_face_zero` и `test_pwf_equals_p0` падают на текущем коде; `test_other_faces_unchanged`, `test_producing_pwf_is_setpoint` проходят). Замер пробы: так и есть.

3. `fluxes.py`, блок забоя (стр. 112-116):

До:
```python
    # ── Забой (f = 0) ────────────────────────────────────────
    # Upstream: всегда ячейка 0 (ближайшая к забою).
    # При типичной добыче p_wf < p[0] → dp < 0 → G < 0 (к скважине).
    dp_w = p_wf - p[0]
    up_w = 0
```
После:
```python
    # ── Забой (f = 0) ────────────────────────────────────────
    # Скважина только добывающая (eq:bc_pwf_shutin): при p[0] <= p_wf она
    # закрыта — потоки через забой нулевые, фактическое давление на забое
    # равно p[0] (problem_statement.tex, «Закрытие скважины»). Так же
    # поступает прототип (blackoil.py, _well_fluxes, ветвь 'shut').
    # Закрытие выражено нулевым перепадом: формулы ниже дают G = 0.
    # При добыче p_wf < p[0] → dp_w < 0 → G < 0 (к скважине); выше по
    # потоку — ячейка 0.
    dp_w = p_wf - p[0]
    if dp_w >= 0:
        p_wf = float(p[0])
        dp_w = 0.0
    up_w = 0
```
Остальное (стр. 118-129 — формулы $G, \mathcal{Q}, u, m$ забоя, стр. 177 `p_wf=p_wf`) не меняется: возвращается уже исправленное `p_wf`.

4. Эталон `_compute_reference_face` (`test_fluxes.py:71-74`, после шага 2 — 75-78) — тоже закрытие, иначе эталон и ядро разойдутся на любом будущем вызове с $p_{wf} > p[0]$:

До:
```python
    if f == 0:
        p_wf = bc.well.p_wf    # эталон: только PressureControl
        dp = p_wf - p[0]
        T_f = grid.trans_well
```
После:
```python
    if f == 0:
        p_wf = bc.well.p_wf    # эталон: только PressureControl
        # Закрытая скважина (eq:bc_pwf_shutin): при p[0] <= p_wf потоков нет
        dp = min(p_wf - p[0], 0.0)
        T_f = grid.trans_well
```

5. `test_energy.py:1392-1394`, docstring `test_inflow_temperature_depends_on_hydro_pwf`:

До:
```
        HydroResult строится подменой потока на забойной грани, а не через
        compute_fluxes с p_wf > p[0]: план DEBT-019 запрещает там приток.
        Энергия приток не запрещает, её путь с Φ⁺_{1/2} > 0 проверяем.
```
После:
```
        HydroResult строится подменой потока на забойной грани: compute_fluxes
        при p_wf > p[0] закрывает скважину (eq:bc_pwf_shutin, DEBT-028), и
        притока через забой гидродинамика не даёт. Энергия приток не
        запрещает, её путь с Φ⁺_{1/2} > 0 проверяем.
```

6. `test_energy_matrix_examples.py:211-212`:

До:
```python
    # Ноль допустим: при p_wf = p[0] потока нет и вклад нулевой.
    # Та же строгость, что в DEBT-019 (отказ при dp_w > 0, не >=).
```
После:
```python
    # Ноль допустим: при p_wf = p[0] потока нет и вклад нулевой; при
    # p_wf > p[0] скважина закрыта, и потоки тоже нулевые
    # (eq:bc_pwf_shutin) — закачки гидродинамика не даёт ни на одном пути.
```

**Проверка после этого шага:**
- `pytest tests/test_fluxes.py -q -k TestWellShutIn` → 14 passed.
- `pytest tests/test_fluxes.py -q` — все зелёные.
- Регресс: быстрый — **1013 passed** (999 + 14).

**Подводные камни:** `test_other_faces_unchanged` сравнивает побитово — на этом шаге верно (грани 1..N не зависят от `p_wf`), после шага 4 тоже (общая функция на гранях 1..N получает те же $G$ и то же состояние).

**Зависимости:** требует шаг 2; блокирует шаг 4.

**Оценка:** ~60 строк тестов, ~8 строк кода, ~15 мин.

---

### Шаг 4: Общий шаг `phase_fluxes_from_components`; `compute_fluxes` через него

**Цель:** шаг «$\mathcal{Q}, u, m, Gm$ из $G$» — в одной функции; `compute_fluxes` считает только $G$.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/fluxes.py`
- `numerical_solver/tests/test_fluxes.py`
- `numerical_solver/gpn_multiphase_solver/energy/tridiag.py` (только комментарии)

**Контекст:** тело функции — перенос `prototype_adapter.py:184-263` (PVT в центрах, цикл по внутренним граням, забой, контур, $Gm$, сборка `HydroResult`) с двумя правками условий: выбор ячейки по $\Delta p$ вместо знака $G^o$ — на внутренних гранях (`up = f - 1 if p[f - 1] - p[f] >= 0 else f` вместо `up = f if G_o[f] < 0 else f - 1`) и на контуре (`if p[N - 1] - bc.p_ext < 0` вместо `if G_o[N] < 0`). Порядок арифметических операций сохранён — это условие побитовости рабочего пути на шаге 5. `compute_fluxes` теряет вычисление $\mathcal{Q}, u, m$ (оно было через $\mathcal{T}\lambda\Delta p$) — теперь $\mathcal{Q} = G \cdot B$; разница — округление ≤ 4.4e-16 (проба `q_from_g_roundoff.py`).

На контуре при притоке $\rho_g$ = $\rho_g(p_{ext})$ (было `0.0` в `compute_fluxes`) — закрывает [[DEBT-021]]. Для эталона теста — то же.

**Что сделать:**

1. Тесты (красные — функции ещё нет). В `test_fluxes.py`: импорт (стр. 27):

```python
from gpn_multiphase_solver.fluxes import compute_fluxes, phase_fluxes_from_components
```

После класса `TestWellShutIn` добавить:

```python
class TestPhaseFluxesFromComponents:
    """Общий шаг «Q, u, m, Gm из G» (phase_fluxes_from_components, DEBT-028).

    Функцию вызывают оба гидро-пути: compute_fluxes (тесты, двойники) и
    PrototypeHydroAdapter (рабочий расчёт). G задаются вручную — так
    получаются ситуации, которых compute_fluxes на штатных профилях не даёт.
    Профиль state_2ph: p растёт от скважины (8 → 19 МПа), Δp < 0 на всех
    внутренних гранях, на контуре p[N-1] = 19 < p_ext = 20 МПа — приток.
    """

    @staticmethod
    def _zeros(n):
        return np.zeros(n + 1), np.zeros(n + 1), np.zeros(n + 1)

    def test_upstream_by_pressure_when_G_o_zero(self, state_2ph, grid_2ph,
                                                pvt, bc_2ph):
        """G_o = 0, свободный газ течёт к скважине: выше по потоку — ячейка f.

        Так бывает при k_ro = 0 (S_g >= 1 - S_or) в ячейке выше по потоку.
        Ячейка выбирается по перепаду давления (как в прототипе), а не по
        знаку G_o: на грани 1 Δp = 8 - 10 МПа < 0 → ячейка 1.
        Ожидание: Q_g[1] = G_free_gas[1] · B_g[1]. Ловит: правило «по знаку
        G_o», которое при G_o = 0 брало ячейку 0 (ниже по потоку).
        """
        N = grid_2ph.N
        G_o, G_g, G_free_gas = self._zeros(N)
        G_free_gas[1] = -1.0          # к скважине: знак «−» по конвенции
        G_g[1] = -1.0
        Bg = pvt.Bg(state_2ph.p)
        rho_g = pvt.rho_g(state_2ph.p)
        # Контроль невырожденности: при равных B_g тест не различит ячейки
        assert not np.isclose(Bg[0], Bg[1], rtol=1e-6)
        r = phase_fluxes_from_components(G_o, G_g, G_free_gas, state_2ph,
                                         grid_2ph, pvt, bc_2ph, P_WF_2PH)
        area = 2.0 * np.pi * grid_2ph.h * grid_2ph.r_faces[1]
        assert r.Q_g[1] == pytest.approx(-Bg[1], rel=1e-14)
        assert r.u_g[1] == pytest.approx(-Bg[1] / area, rel=1e-14)
        assert r.m_g[1] == pytest.approx(rho_g[1] * r.Q_g[1], rel=1e-14)

    def test_outer_inflow_gas_density_from_ext(self, state_2ph, grid_2ph,
                                               pvt, bc_2ph):
        """Приток через контур: B_g и ρ_g — при p_ext (DEBT-021).

        Свободного газа на контуре нет (S_g,ext = 0), и в расчёте
        G_free_gas[N] = 0 — здесь он задан вручную, как при S_g,ext > 0.
        Ожидание: Q_g[N] = G_free_gas[N]·B_g(p_ext), m_g[N] = ρ_g(p_ext)·Q_g[N] ≠ 0.
        Ловит: ρ_g = 0 на контуре (прежний compute_fluxes) — расхождение
        двух гидро-путей, скрытое умножением на ноль.
        """
        N = grid_2ph.N
        G_o, G_g, G_free_gas = self._zeros(N)
        G_free_gas[N] = -1.0          # приток: к скважине, знак «−»
        G_g[N] = -1.0
        p_ext_a = np.array([bc_2ph.p_ext])
        Bg_ext = pvt.Bg(p_ext_a)[0]
        rho_g_ext = pvt.rho_g(p_ext_a)[0]
        assert state_2ph.p[N - 1] < bc_2ph.p_ext          # действительно приток
        # Контроль невырожденности: ρ_g контура ≠ ρ_g ячейки N-1
        assert not np.isclose(rho_g_ext, pvt.rho_g(state_2ph.p)[N - 1], rtol=1e-6)
        r = phase_fluxes_from_components(G_o, G_g, G_free_gas, state_2ph,
                                         grid_2ph, pvt, bc_2ph, P_WF_2PH)
        assert r.Q_g[N] == pytest.approx(-Bg_ext, rel=1e-14)
        assert r.m_g[N] == pytest.approx(rho_g_ext * r.Q_g[N], rel=1e-14)
        assert r.m_g[N] != 0.0

    def test_pwf_and_substeps_passed_through(self, state_2ph, grid_2ph,
                                             pvt, bc_2ph):
        """p_wf, n_substeps и state уходят в HydroResult без изменений.

        Адаптер передаёт фактическое p_wf прототипа и число подшагов
        A-retry (BUG-010). Ловит: потерю или подмену этих полей.
        """
        N = grid_2ph.N
        G_o, G_g, G_free_gas = self._zeros(N)
        r = phase_fluxes_from_components(G_o, G_g, G_free_gas, state_2ph,
                                         grid_2ph, pvt, bc_2ph, 7.5e6,
                                         n_substeps=4)
        assert r.p_wf == 7.5e6
        assert r.n_substeps == 4
        assert r.state is state_2ph
```

Запуск `pytest tests/test_fluxes.py -q` — ожидание: ошибка импорта (`phase_fluxes_from_components` нет) — весь модуль красный. Это ожидаемо, переходить к п. 2.

2. Эталон `_compute_reference_face`, контур при притоке (исходно стр. 107, после шагов 2–3 — 112):

До: `            rho_g_up = 0.0`
После: `            rho_g_up = pvt.rho_g(p_ext_a)[0]   # при p_ext, как ρ_o (DEBT-021)`

(Численно ничего не меняет: `lam_g_up = 0.0` → $\mathcal{Q}_g = 0$, $m_g = 0$ — но эталон описывает целевое правило.)

3. `fluxes.py` — заменить файл целиком на код ниже (он же — `vault/issues/debt-028/probes/planned_code.py`, проверенный подменой; здесь добавлены аннотации типов и модульный docstring, docstring функций укорочены до ≤ 100 символов в строке — аудит):

```python
"""Вычисление потоков через грани: G, Q, u, m, Gm + upstream.

Eq. 8, 9, 24 problem_statement.tex. Конвенция: >0 = от скважины (рост r).

phase_fluxes_from_components — шаг «Q, u, m, Gm из G», общий для обоих
гидро-путей: compute_fluxes (путь тестов и двойников, G по Дарси) и
PrototypeHydroAdapter (рабочий расчёт, G от прототипа). Одна копия правила
выбора ячейки выше по потоку и формул (DEBT-028).
"""

import numpy as np

from .state import SimulationState, HydroResult, BoundaryConditions
from .bc import PressureControl
from .grid.base import Grid
from .pvt.base import HydroPVT, RelPermModel


def phase_fluxes_from_components(G_o: np.ndarray, G_g: np.ndarray,
                                 G_free_gas: np.ndarray,
                                 state: SimulationState, grid: Grid,
                                 pvt: HydroPVT, bc: BoundaryConditions,
                                 p_wf: float,
                                 n_substeps: int = 1) -> HydroResult:
    """Q, u, m, Gm из потоков компонентов G — общий шаг обоих гидро-путей. Ур. (eq:phase_flux)."""
    N = grid.N
    p = state.p
    Rs = state.Rs

    # PVT в центрах ячеек
    Bo = pvt.Bo(p, Rs)
    Bg = pvt.Bg(p)
    rho_o = pvt.rho_o(p, Rs)
    rho_g = pvt.rho_g(p)

    face_area = 2.0 * np.pi * grid.h * grid.r_faces

    Q_o = np.empty(N + 1)
    Q_g = np.empty(N + 1)
    u_o = np.empty(N + 1)
    u_g = np.empty(N + 1)
    m_o = np.empty(N + 1)
    m_g = np.empty(N + 1)

    # ── Внутренние грани (f = 1..N-1) ────────────────────────
    # Q_α = G·B_α ячейки выше по потоку: G^o = T·k_ro/(μ_o·B_o)·Δp, поэтому
    # G^o·B_o = T·(k_ro/μ_o)·Δp — это eq:phase_flux; для газа так же с G^св.газ.
    # Ячейка выше по потоку — по перепаду давления, как в прототипе
    # (blackoil.py, face_component_fluxes_sm3s: left = dp >= 0):
    #   dp = p[f-1] - p[f] >= 0 → ячейка f-1 (поток от скважины, нетипично)
    #   dp < 0                 → ячейка f   (поток к скважине, типично)
    # Не по знаку G^o: при k_ro = 0 в ячейке выше по потоку G^o = 0, и знак
    # не различает направление (DEBT-028).
    for f in range(1, N):
        up = f - 1 if p[f - 1] - p[f] >= 0 else f
        Q_o[f] = G_o[f] * Bo[up]
        Q_g[f] = G_free_gas[f] * Bg[up]
        u_o[f] = Q_o[f] / face_area[f]
        u_g[f] = Q_g[f] / face_area[f]
        m_o[f] = rho_o[up] * Q_o[f]
        m_g[f] = rho_g[up] * Q_g[f]

    # ── Забой (f = 0) ────────────────────────────────────────
    # Выше по потоку — ячейка 0: втекания через забой нет (eq:bc_pwf_shutin),
    # при закрытой скважине G = 0 и Q = 0. Знаки: добыча → G < 0 → Q < 0.
    Q_o[0] = G_o[0] * Bo[0]
    Q_g[0] = G_free_gas[0] * Bg[0]
    u_o[0] = Q_o[0] / face_area[0]
    u_g[0] = Q_g[0] / face_area[0]
    m_o[0] = rho_o[0] * Q_o[0]
    m_g[0] = rho_g[0] * Q_g[0]

    # ── Контур (f = N) ── eq:bc_flux_ext ─────────────────────
    if p[N - 1] - bc.p_ext < 0:
        # Приток с контура (типично): выше по потоку контур, свойства при
        # p_ext, Rs_ext. ρ_g — тоже при p_ext, а не ноль: свободного газа на
        # контуре нет и G^св.газ[N] = 0, но ветвь остаётся верной при
        # S_g,ext > 0 (DEBT-021, решение Р-1 DEBT-017).
        p_ext_a = np.array([bc.p_ext])
        Rs_ext_a = np.array([bc.Rs_ext])
        Bo_up_N = pvt.Bo(p_ext_a, Rs_ext_a)[0]
        Bg_up_N = pvt.Bg(p_ext_a)[0]
        rho_o_up_N = pvt.rho_o(p_ext_a, Rs_ext_a)[0]
        rho_g_up_N = pvt.rho_g(p_ext_a)[0]
    else:
        # Отток через контур (нетипично): выше по потоку ячейка N-1
        Bo_up_N = Bo[N - 1]
        Bg_up_N = Bg[N - 1]
        rho_o_up_N = rho_o[N - 1]
        rho_g_up_N = rho_g[N - 1]

    Q_o[N] = G_o[N] * Bo_up_N
    Q_g[N] = G_free_gas[N] * Bg_up_N
    u_o[N] = Q_o[N] / face_area[N]
    u_g[N] = Q_g[N] / face_area[N]
    m_o[N] = rho_o_up_N * Q_o[N]
    m_g[N] = rho_g_up_N * Q_g[N]

    # ── Покомпонентные массовые расходы ──────────────────────
    Gm_o = pvt.rho_o_std * G_o
    Gm_g = pvt.rho_g_std * G_g

    return HydroResult(
        state=state,
        G_o=G_o, G_g=G_g, G_free_gas=G_free_gas,
        Q_o=Q_o, Q_g=Q_g,
        u_o=u_o, u_g=u_g,
        m_o=m_o, m_g=m_g,
        Gm_o=Gm_o, Gm_g=Gm_g,
        p_wf=p_wf,
        n_substeps=n_substeps,
    )


def compute_fluxes(state: SimulationState, grid: Grid,
                   pvt: HydroPVT, relperm: RelPermModel,
                   bc: BoundaryConditions) -> HydroResult:
    """Потоки через все грани: G по Дарси + общий шаг Q, u, m, Gm.

    Ур. (eq:flux_oil), (eq:flux_gas), (eq:bc_pwf_shutin) problem_statement.tex.
    """
    # Путь тестов и тестовых двойников: рабочий расчёт получает G от
    # прототипа (PrototypeHydroAdapter). state не меняется, HydroResult.state = state.
    N = grid.N
    p = state.p
    Sg = state.Sg
    Rs = state.Rs

    # PVT в центрах ячеек
    Bo = pvt.Bo(p, Rs)
    Bg = pvt.Bg(p)
    mu_o = pvt.mu_o(p, Rs)
    mu_g = pvt.mu_g(p)

    kro = relperm.kro(Sg)
    krg = relperm.krg(Sg)

    # Подвижности потоков компонентов
    mob_o = kro / (mu_o * Bo)       # kro/(μo·Bo) — для G_o
    mob_g = krg / (mu_g * Bg)       # krg/(μg·Bg) — для G_free_gas

    # Забойное давление. compute_fluxes — гидродинамический путь тестов
    # и дублёров и сам читает управление (FEAT-020). Заданный дебит здесь
    # не поддержан: p_wf пришлось бы искать итерациями.
    if not isinstance(bc.well, PressureControl):
        raise NotImplementedError(
            f"compute_fluxes поддерживает только PressureControl, "
            f"получено {type(bc.well).__name__}")
    p_wf = bc.well.p_wf

    # PVT на контуре (однофазная зона: Sg=0)
    p_ext_arr = np.array([bc.p_ext])
    Rs_ext_arr = np.array([bc.Rs_ext])
    Bo_ext = pvt.Bo(p_ext_arr, Rs_ext_arr)[0]
    mu_o_ext = pvt.mu_o(p_ext_arr, Rs_ext_arr)[0]
    kro_ext = relperm.kro(np.array([bc.Sg_ext]))[0]

    mob_o_ext = kro_ext / (mu_o_ext * Bo_ext)

    # Потоки компонентов, м³ст/с
    G_o = np.empty(N + 1)
    G_g = np.empty(N + 1)
    G_free_gas = np.empty(N + 1)

    # ── Внутренние грани (f = 1..N-1) ────────────────────────
    # Грань f расположена между ячейками f-1 (левая) и f (правая).
    # dp = p[f-1] - p[f]:
    #   dp > 0 → поток от скважины (нетипично), upstream = f-1
    #   dp < 0 → поток к скважине (типично), upstream = f
    for f in range(1, N):
        dp = p[f - 1] - p[f]
        T_f = grid.trans_internal[f - 1]

        # Upstream = ячейка с бо́льшим давлением
        if dp >= 0:
            up = f - 1
        else:
            up = f

        # G_o = T * (kro/(μo·Bo))_up * dp — поток нефтяного компонента, м³ст/с (eq. 8)
        G_o[f] = T_f * mob_o[up] * dp
        # G_free_gas = T * (krg/(μg·Bg))_up * dp — свободный газ, м³ст/с
        G_free_gas[f] = T_f * mob_g[up] * dp
        # G_g = (Rs_up * mob_o_up + mob_g_up) * T * dp — полный газовый компонент (eq. 9)
        G_g[f] = T_f * (Rs[up] * mob_o[up] + mob_g[up]) * dp

    # ── Забой (f = 0) ────────────────────────────────────────
    # Скважина только добывающая (eq:bc_pwf_shutin): при p[0] <= p_wf она
    # закрыта — потоки через забой нулевые, фактическое давление на забое
    # равно p[0] (problem_statement.tex, «Закрытие скважины»). Так же
    # поступает прототип (blackoil.py, _well_fluxes, ветвь 'shut').
    # Закрытие выражено нулевым перепадом: формулы ниже дают G = 0.
    # При добыче p_wf < p[0] → dp_w < 0 → G < 0 (к скважине); выше по
    # потоку — ячейка 0.
    dp_w = p_wf - p[0]
    if dp_w >= 0:
        p_wf = float(p[0])
        dp_w = 0.0
    up_w = 0

    G_o[0] = grid.trans_well * mob_o[up_w] * dp_w
    G_free_gas[0] = grid.trans_well * mob_g[up_w] * dp_w
    G_g[0] = grid.trans_well * (Rs[up_w] * mob_o[up_w] + mob_g[up_w]) * dp_w

    # ── Контур (f = N) ───────────────────────────────────────
    dp_e = p[N - 1] - bc.p_ext

    if dp_e >= 0:
        # Поток от скважины (нетипично): upstream = ячейка N-1
        mob_o_up_e = mob_o[N - 1]
        mob_g_up_e = mob_g[N - 1]
        Rs_up_e = Rs[N - 1]
    else:
        # Приток из контура (типично): upstream = контур
        mob_o_up_e = mob_o_ext
        mob_g_up_e = 0.0       # krg=0 на контуре (Sg=0)
        Rs_up_e = bc.Rs_ext

    G_o[N] = grid.trans_ext * mob_o_up_e * dp_e
    G_free_gas[N] = grid.trans_ext * mob_g_up_e * dp_e
    G_g[N] = grid.trans_ext * (Rs_up_e * mob_o_up_e + mob_g_up_e) * dp_e

    # ── Q, u, m, Gm — общий шаг с рабочим путём (адаптер прототипа) ──
    return phase_fluxes_from_components(G_o, G_g, G_free_gas,
                                        state, grid, pvt, bc, p_wf)
```

Что ушло из `compute_fluxes` по сравнению с текущим: `rho_o`, `rho_g` в центрах; `lam_o`, `lam_g`; на контуре `rho_o_ext`, `lam_o_ext`, `lam_o_up_e`, `lam_g_up_e`, `rho_o_up_e`, `rho_g_up_e`; массивы `Q_o, Q_g, u_o, u_g, m_o, m_g`, `face_area`, вычисление `Gm_*` и сборка `HydroResult` — всё это теперь в общей функции. Комментарии к оставшимся строкам сохранены дословно.

4. `energy/tridiag.py` — две ссылки на строки `fluxes.py` (номера после шага бессмысленны; уже сейчас `:47-52` неверно — фактически 53-58). Замены подстрок, остальной текст строк не трогать:
   - стр. 215 (docstring `_ext_properties`): `fluxes.py:47-52` → `fluxes.py (свойства контура)`;
   - стр. 268 (комментарий в `compute_convective_coefficients`): `(fluxes.py:143-145)` → `(fluxes.py, phase_fluxes_from_components)`.

**Проверка после этого шага:**
- `pytest tests/test_fluxes.py -q` — все зелёные, включая 3 новых.
- Регресс: быстрый — **1016 passed** (1013 + 3). Тесты энергии, `Simulator`, VAL-001/002, `test_hydro.py` теперь идут через общую функцию: при планировании с кодом плана все зелёные (кроме 11 тестов старой фикстуры, которую поменял шаг 2).
- Если какой-то тест разошёлся на уровне $10^{-15}$–$10^{-13}$ относительно — это округление $\mathcal{Q} = G\cdot B$ против $\mathcal{T}\lambda\Delta p$ (замер ≤ 4.4e-16); разобрать, а не ослаблять допуск вслепую.

**Подводные камни:** `tridiag.py` — только комментарии, `test_matrix_matches_reference` (slow) не затронут.

**Зависимости:** требует шаг 3; блокирует шаг 5.

**Оценка:** fluxes.py ~200 строк (переписан), тесты ~85 строк, ~30 мин.

---

### Шаг 5: Адаптер через общий шаг; выбор ячейки по перепаду давления

**Цель:** рабочий путь использует тот же код шага «$\mathcal{Q}, u, m$ из $G$», что и путь тестов; расхождение с прототипом при $k_{ro} = 0$ устранено.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`
- `numerical_solver/tests/test_prototype_adapter.py`

**Контекст:** см. «Расхождение 1». `_build_result` вызывается напрямую в тесте: через `solve` состояние с $S_g = 0.8$ не задать — прототип за шаг его изменит; `_build_result` считает потоки на заданном состоянии без шага по времени.

**Что сделать — сначала тест (красный), потом код:**

1. `test_prototype_adapter.py`: после класса `TestGgDecomposition` (заканчивается на стр. 515, перед секцией «G. Баланс масс», стр. 518) добавить:

```python
# ═══════════════════════════════════════════════════════════
# F2. Выбор ячейки выше по потоку при k_ro = 0 (DEBT-028)
# ═══════════════════════════════════════════════════════════

class TestUpstreamWithZeroKro:
    """Ячейка выше по потоку — по перепаду давления, как в прототипе.

    При S_g = 0.8 табличная k_ro = 0 (KRO_TAB), и прототип отдаёт G_o = 0
    (точнее −0.0) на грани, хотя Δp < 0 и свободный газ течёт к скважине.
    Прототип выбирает ячейку по перепаду (blackoil.py,
    face_component_fluxes_sm3s: left = dp >= 0) — ячейку f. Правило «по
    знаку G_o» (до DEBT-028) брало f-1, ячейку ниже по потоку, и Q_g, u_g
    получали B_g не той ячейки. m_g верен при любом выборе: ρ_g·B_g = ρ_g,ст.

    _build_result вызывается напрямую: через solve состояние с S_g = 0.8
    не задать — прототип за шаг его изменит.
    """

    def test_Q_g_uses_upstream_cell_by_pressure(self, adapter, our_pvt,
                                                our_grid, bc):
        """Грани 1, 2: G_o = 0, Q_g = G_free_gas · B_g[f] (ячейка f).

        Условия: p растёт от 160 до 200 бар (Δp < 0 на всех гранях),
        S_g = 0.8 в ячейках 0–2 (k_ro = 0, k_rg = 0.8), дальше S_g = 0.
        Ловит: выбор ячейки ниже по потоку при G_o = 0 (до DEBT-028
        Q_g[1] брал B_g[0], расхождение ~0.7 %).
        """
        p = np.linspace(160e5, 200e5, N)          # Δp < 0 на всех внутренних гранях
        Sg = np.zeros(N)
        Sg[:3] = 0.8                              # k_ro = 0 в ячейках 0–2
        Rs = np.where(Sg > 0, our_pvt.Rs_eq(p), RS0)
        state = SimulationState(p=p, Sg=Sg, Rs=Rs, T=np.full(N, T0),
                                regime=np.where(Sg > 0, 1, 2), t=0.0)
        proto = BlackOilState(pressure_bar=p / BAR_TO_PA, rs_sm3_sm3=Rs.copy(),
                              sg=Sg.copy(), gas_active=(Sg > 0))
        r = adapter._build_result(state, proto, bc)
        Bg = our_pvt.Bg(p)
        area = 2.0 * np.pi * our_grid.h * our_grid.r_faces
        for f in (1, 2):
            assert r.G_o[f] == 0.0                # k_ro(S_g = 0.8) = 0
            assert r.G_free_gas[f] < 0.0          # газ течёт к скважине
            # Контроль невырожденности: при равных B_g тест не различит ячейки
            assert not np.isclose(Bg[f], Bg[f - 1], rtol=1e-6)
            assert r.Q_g[f] == pytest.approx(r.G_free_gas[f] * Bg[f], rel=1e-14)
            assert r.u_g[f] == pytest.approx(r.Q_g[f] / area[f], rel=1e-14)
            # m_g от выбора ячейки не зависит: ρ_g·B_g = ρ_g,ст (pvt/base.py)
            assert r.m_g[f] == pytest.approx(
                our_pvt.rho_g_std * r.G_free_gas[f], rel=1e-12)
```

2. `pytest tests/test_prototype_adapter.py -q -k TestUpstreamWithZeroKro` — ожидание **1 failed** (`Q_g` на грани 1: `comparison failed`). Замер пробы: так и есть. Записать сообщение в отчёт — это подтверждение расхождения.

3. `prototype_adapter.py`:
   - импорт (после стр. 30 `from ..units import BAR_TO_PA, DAY_TO_S`): `from ..fluxes import phase_fluxes_from_components`;
   - метод `_build_result` (стр. 152-263) заменить на:

```python
    def _build_result(self, new_state: SimulationState,
                      new_proto, bc: BoundaryConditions,
                      n_substeps: int = 1) -> HydroResult:
        """Шаги 5–9: потоки компонентов из прототипа, Q, u, m, Gm — общим шагом fluxes.py.

        n_substeps — фактическое дробление A-retry, уходит в HydroResult
        для синхронного дробления шага энергии (BUG-010).
        """
        N = self._grid.N

        # ── Шаг 5+6: потоки + согласование знаков ──
        fluxes = self._model.face_component_fluxes_sm3s(new_proto)

        # G_o: нефтяной компонент, м³ст/с
        # Инверсия ТОЛЬКО well (прототип: outflow+ = к скважине, мы: outflow− = к скважине)
        G_o = np.empty(N + 1)
        G_o[0] = -fluxes['oil_well']
        G_o[1:N] = fluxes['oil_internal']
        G_o[N] = fluxes['oil_outer']

        # G_g: полный газовый компонент (растворённый + свободный), м³ст/с
        G_g = np.empty(N + 1)
        G_g[0] = -fluxes['gas_component_well']
        G_g[1:N] = fluxes['gas_component_internal']
        G_g[N] = fluxes['gas_component_outer']

        # G_free_gas: только свободный газ, м³ст/с
        G_free_gas = np.empty(N + 1)
        G_free_gas[0] = -fluxes['free_gas_well']
        G_free_gas[1:N] = fluxes['free_gas_internal']
        G_free_gas[N] = fluxes['free_gas_outer']

        # ── Шаг 9: фактическое забойное давление ──
        # Результат шага при любом управлении: при OIL_RATE прототип
        # выражает p_bhp из уравнения притока (blackoil.py, _well_fluxes),
        # при BHP и p[0] <= уставки скважина закрыта и p_bhp = p[0].
        # well_rates считает на том же new_proto, что и потоки выше.
        p_wf = self._model.well_rates(new_proto)['bhp_bar'] * BAR_TO_PA

        # ── Шаги 7–8: Q, u, m, Gm — общий шаг с путём тестов (DEBT-028) ──
        # Тот же код, что у compute_fluxes: правило выбора ячейки выше по
        # потоку и формулы записаны в одном месте (fluxes.py).
        return phase_fluxes_from_components(G_o, G_g, G_free_gas,
                                            new_state, self._grid, self._pvt, bc,
                                            p_wf, n_substeps=n_substeps)
```

   Ушли: блок «Шаг 7» (стр. 184-241: PVT, `face_area`, массивы, три цикла/блока граней), «Шаг 8» (стр. 243-245), сборка `HydroResult` (стр. 254-263). Комментарии шагов 5-6 и 9 — дословно.
   - модульный docstring (стр. 1-21): после строки 8 «- забойное давление: bhp_bar прототипа → HydroResult.p_wf (Па)» добавить абзац перед «НЕ конвертирует»:
     ```
     Q, u, m, Gm из потоков компонентов — общий шаг
     fluxes.phase_fluxes_from_components, тот же, что у compute_fluxes
     (DEBT-028): выбор ячейки выше по потоку — по перепаду давления, как
     в прототипе.
     ```

4. `test_prototype_adapter.py` — правило выбора ячейки в тестах, воспроизводящих адаптер, — на новое (4 места):
   - стр. 432-433 (`test_Q_o_from_G_o_Bo`): `# Upstream по знаку G_o` / `up = f if result.G_o[f] < 0 else f - 1` → `# Выше по потоку — по перепаду давления, как прототип (DEBT-028)` / `up = f - 1 if p[f - 1] - p[f] >= 0 else f`;
   - стр. 444 (`test_Q_g_from_G_free_gas_Bg`): то же; в начале теста уже есть `p = result.state.p` (стр. 440);
   - стр. 473 (`test_m_o_from_rho_Q`): то же; `p = result.state.p` есть (стр. 468);
   - стр. 512 (`test_decomposition_internal`): то же; добавить `p = result.state.p` после `Rs = result.state.Rs` (стр. 510).
   - docstring модуля, стр. 12: «7. Q, u, m из G через upstream PVT» → «7. Q, u, m из G через upstream PVT (общий шаг fluxes.phase_fluxes_from_components)».

5. Снимок историй новым кодом и сравнение:
   ```powershell
   $P = "d:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\debt-028\probes"
   d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python $P\history_snapshot.py save new_impl *> $P\save_new_impl.txt
   d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python $P\history_snapshot.py compare base_impl new_impl
   ```
   Ожидание: **20 × «побитово», «итого: различий 0»** — по всем массивам, включая $T$, $\mathcal{Q}_\alpha$, $u_\alpha$, $m_\alpha$. Так получилось при планировании с кодом плана (раздел «Проверка при планировании»).

**Проверка после этого шага:**
- `pytest tests/test_prototype_adapter.py -q` — все зелёные, включая новый.
- Регресс: быстрый — **1017 passed** (1016 + 1).
- Снимок: 20/20 побитово. **Любое различие — остановиться и разобрать** (с какой записи, в каком массиве; не расходится ли выбор ячейки в Па и барах при $|\Delta p|$ ~ 1 ULP — см. чеклист), не переходить к шагу 6.

**Подводные камни:** побитовость рабочего пути (чеклист); `-0.0` от прототипа на забое закрытой скважины (`test_short_upstep_well_shut` сравнивает с `0.0` — проходит).

**Зависимости:** требует шаг 4; блокирует шаг 6.

**Оценка:** адаптер −75 строк, тесты ~45 строк, снимок ~10 мин.

---

### Шаг 6: Документация

**Цель:** документы проекта описывают новое устройство.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/bc.py` — без изменений: docstring (стр. 3-6) говорит, что `compute_fluxes` «возвращает фактическое p_wf в HydroResult» — после шага 3 это верно.
- `numerical_solver/tests/_doubles.py:67` — комментарий «Потоки — через compute_fluxes (единая логика upstream, знаков, формул)» верен, не трогать.
- `numerical_solver/tests/test_hydro.py:208-209` — docstring `test_all_fields_match_compute_fluxes` верен, не трогать.

Код на этом шаге не меняется — шаг фактически пустой, если шаги 3–5 выполнены с указанными docstring и комментариями. Оставлен как контрольная точка: grep `fluxes.py:\d` и `prototype_adapter.py:\d` по `numerical_solver/` должен давать пусто:
```powershell
# из numerical_solver
Select-String -Path gpn_multiphase_solver\*.py, gpn_multiphase_solver\*\*.py, tests\*.py -Pattern "fluxes\.py:\d|prototype_adapter\.py:\d"
```

**Проверка после этого шага:**
- Регресс: `--collect-only -q` → **1241**.

**Зависимости:** требует шаг 5.

**Оценка:** ~2 мин.

---

### Шаг 7: Vault и issue

**Цель:** реестр, заметки и issue отражают результат.

**Файлы:**
- `vault/roadmap/известные баги и технический долг.md`
- `vault/knowledge/decisions/свойства-фаз-на-контурной-грани-берутся-из-ГУ-при-притоке.md`
- `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md`
- `vault/knowledge/decisions/P1-адаптер-единицы.md`
- `vault/issues/debt-028/05-comment-done.md` (новый)

**Что сделать:**
1. Реестр, DEBT-028: поле **Статус** → `✅ ЗАКРЫТ (<дата>)` с одной строкой итога (общий шаг, закрытие скважины, расхождение при $k_{ro}=0$ подтверждено и устранено, истории 20/20 побитово, число тестов); **Затронутые модули** — добавить `tests/test_prototype_adapter.py`, `energy/tridiag.py` (комментарии).
2. Реестр, DEBT-021: **Статус** → `✅ ЗАКРЫТ (<дата>) — устранено [[DEBT-028]]: общий шаг phase_fluxes_from_components берёт ρ_g(p_ext) при притоке в обоих гидро-путях (вариант 2 записи)`; **GitHub:** — issue не создавался.
3. Заметка `свойства-фаз-на-контурной-грани-…`:
   - стр. 38: «(`fluxes.py:143-145` берёт `rho_o_ext`, подвижность при $S_g = 0$)» → «(`compute_fluxes` — подвижность при $S_g = 0$; свойства контура для $\mathcal{Q}, m$ — `phase_fluxes_from_components`)»;
   - таблица, стр. 50-51: строки `fluxes.py:124-145` и `hydro/prototype_adapter.py:204-218` заменить одной: `| fluxes.py, phase_fluxes_from_components (оба гидро-пути, DEBT-028) | при притоке берёт rho_o(p_ext), rho_g(p_ext) |`;
   - стр. 70-71 (⚠️ про `rho_g_up_e = 0.0`): заменить на «Расхождение `fluxes.py` с адаптером ([[DEBT-021]]) устранено [[DEBT-028]]: оба пути вызывают одну функцию.»
4. Заметка `архитектура библиотеки numerical_solver.md`, стр. 75: `fluxes.py # Вычисление потоков: G, Q, u, m, Gm + upstream` → `fluxes.py # G по Дарси (путь тестов) + общий шаг Q, u, m, Gm обоих гидро-путей (DEBT-028)`.
5. Заметка `vault/knowledge/decisions/P1-адаптер-единицы.md` (на неё ссылается docstring адаптера, `prototype_adapter.py:20`): раздел «Метод solve: пошаговый алгоритм» (стр. 169) приводит код шага 7 адаптера с правилом «по знаку $G^o$» (стр. 321-345, контур — стр. 364). Код не переписывать (заметка — история проектирования); перед блоком шага 7 (около стр. 310) вставить:
   ```markdown
   > ⚠️ **DEBT-028 (<дата>):** шаг 7 (Q, u, m, Gm из G) вынесен в
   > `fluxes.phase_fluxes_from_components` — общий для адаптера и `compute_fluxes`.
   > Ячейка выше по потоку выбирается по перепаду давления (как в прототипе,
   > `blackoil.py`: `left = dp >= 0`), а не по знаку `G_o`: при $k_{ro} = 0$
   > в ячейке выше по потоку $G^o = 0$, и правило ниже брало ячейку ниже по потоку.
   ```
   и в «Замечания и ловушки» (стр. 412) — пункт «7. Выбор ячейки выше по потоку — по $\Delta p$, не по знаку $G^o$ (DEBT-028)» с одной фразой и ссылкой на [[debt-028 compute-fluxes-shutin-upwind]]. `грабли-реализации.md:21` уже требует «upstream по знаку dp» — не трогать.
6. Комментарий в issue #60 (`05-comment-done.md`, через `gh issue comment 60 --body-file`).

**Проверка после этого шага:**
- Регресс: `--collect-only -q` (только документы) → 1241.

**Зависимости:** требует шаг 6.

**Оценка:** ~15 мин.

## Тестовая стратегия

**Регрессия (существующие тесты, должны остаться зелёными после каждого шага):**
- `tests/test_fluxes.py` — формулы `compute_fluxes` на всех гранях (эталон `_compute_reference_face` считает $\mathcal{Q}$ через $\mathcal{T}\lambda\Delta p$ — независимо от общей функции, через $G\cdot B$: это проверка общей функции другой формулой);
- `tests/test_prototype_adapter.py` — адаптер против прототипа, $\mathcal{Q}, u, m$ по формулам, закрытие скважины (`test_pwf_floats_to_p0_when_shut`, `test_short_upstep_well_shut`);
- `tests/test_hydro.py` (`TestDelegationToFluxes` — двойник делегирует `compute_fluxes`), `test_energy.py`, `test_val001.py`, `test_val002.py`, `test_simulator.py`, `test_output.py` — потребители `HydroResult` пути тестов;
- снимок историй 20 примеров (шаг 5) — потребители рабочего пути, побитово.

**Новые тесты (18):**

| Тест | Файл | Сценарий | Ожидание | Ловит |
|---|---|---|---|---|
| `TestWellShutIn::test_well_face_zero[×11]` | `test_fluxes.py` | `state_2ph`, уставка 10 МПа > p[0] = 8 | 11 полей грани 0 == 0.0 | закачку через забой |
| `TestWellShutIn::test_pwf_equals_p0` | то же | то же | `p_wf == p[0]` | возврат уставки |
| `TestWellShutIn::test_other_faces_unchanged` | то же | закрыто vs добыча 6 МПа | грани 1..N побитово равны | закрытие, задевающее другие грани |
| `TestWellShutIn::test_producing_pwf_is_setpoint` | то же | добыча 6 МПа | `p_wf == 6e6` | подмену p_wf при добыче |
| `TestPhaseFluxesFromComponents::test_upstream_by_pressure_when_G_o_zero` | то же | G_o = 0, G_free_gas[1] = −1, Δp < 0 | $\mathcal{Q}_g[1] = -B_g[1]$ | выбор по знаку G_o |
| `TestPhaseFluxesFromComponents::test_outer_inflow_gas_density_from_ext` | то же | G_free_gas[N] = −1, приток | $m_g[N] = \rho_g(p_{ext})\mathcal{Q}_g[N] \ne 0$ | $\rho_g = 0$ на контуре (DEBT-021) |
| `TestPhaseFluxesFromComponents::test_pwf_and_substeps_passed_through` | то же | p_wf = 7.5 МПа, n_substeps = 4 | поля как переданы | потерю p_wf/n_substeps |
| `TestUpstreamWithZeroKro::test_Q_g_uses_upstream_cell_by_pressure` | `test_prototype_adapter.py` | S_g = 0.8 в ячейках 0–2, p 160→200 бар | $\mathcal{Q}_g[f] = G^{св.газ}[f]B_g[f]$, f = 1, 2 | расхождение адаптера с прототипом при $k_{ro}=0$ |

**Инвариант:** истории 20 примеров побитово (шаг 5, `history_snapshot.py compare base_impl new_impl`).

**Числа:** 1223 → 1237 (шаг 3) → 1240 (шаг 4) → 1241 (шаг 5); быстрый уровень 999 → 1013 → 1016 → 1017 (новые тесты быстрые).

## Критерии завершения

- [ ] Шаги 1–7 выполнены.
- [ ] Быстрый уровень: 1017 passed; полный прогон (`/implement` §3.1): все зелёные, 1241.
- [ ] `TestWellShutIn` (14), `TestPhaseFluxesFromComponents` (3), `TestUpstreamWithZeroKro` (1) — зелёные; падение новых тестов на исходном коде зафиксировано (шаги 3, 4, 5 — сначала красные).
- [ ] Снимок историй: `compare base_impl new_impl` → 20 × «побитово», «итого: различий 0».
- [ ] В `compute_fluxes` нет вычисления $\mathcal{Q}, u, m$; в `_build_result` нет цикла по граням — оба вызывают `phase_fluxes_from_components`.
- [ ] grep `fluxes\.py:\d|prototype_adapter\.py:\d` по `numerical_solver/gpn_multiphase_solver`, `tests` — пусто.
- [ ] Прототип (`HydroSolverPrototype/`) не менялся: `git diff --stat numerical_scheme/implementation -- numerical_solver/HydroSolverPrototype` пуст.
- [ ] Vault: DEBT-028 и DEBT-021 закрыты, заметки обновлены; комментарий в issue #60.

## Обнаруженные проблемы

1. **Расхождение адаптера с прототипом при $k_{ro} = 0$** — подтверждено замером при планировании (тест падает на текущем коде), устраняется шагом 5. Отдельной записи не требует — часть DEBT-028.
2. **`compute_fluxes` на контуре:** $k_{ro}$ берётся при `bc.Sg_ext`, а $k_{rg}$ — всегда 0 (`mob_g_up_e = 0.0`); прототип на контуре всегда $S_g = 0$ для обеих фаз. При `Sg_ext > 0` путь тестов разошёлся бы с прототипом. Не регистрируется: фабрика всегда задаёт `Sg_ext=0.0` (`factory.py:464`), постановка — $S_g|_{ext} = 0$ (`eq:bc_flux_ext`); если появится конфиг с газом на контуре — это часть той задачи (меняется и прототип).
3. **Устаревшие номера строк и описание старого правила в vault** (`свойства-фаз-на-контурной-грани-…`, `P1-адаптер-единицы.md`, запись DEBT-021) — правит шаг 7.

## Связь формула → код

| Уравнение (`problem_statement.tex`) | Код после плана |
|---|---|
| `eq:flux_oil` (999), `eq:flux_gas` (1005) — $G$ на внутренних гранях | `fluxes.compute_fluxes`, цикл внутренних граней (путь тестов); прототип `face_component_fluxes_sm3s` (рабочий) |
| `eq:bc_flux_well` (1718), `eq:bc_flux_well_gas` (1723) — $G$ на забое | `compute_fluxes`, блок забоя |
| `eq:bc_pwf_shutin` (697), абзац «Закрытие скважины» (1736-1747) | `compute_fluxes`: `dp_w >= 0 → p_wf = p[0], dp_w = 0`; прототип `_well_fluxes`, ветвь `'shut'` |
| `eq:bc_flux_ext` (1784), `eq:bc_flux_ext_gas` (1788) — $G$ на контуре | `compute_fluxes`, блок контура |
| `eq:phase_flux` (1302) — $\mathcal{Q}_\alpha$ | `fluxes.phase_fluxes_from_components`: $\mathcal{Q} = G\cdot B_{up}$ (оба пути) |

## Проверка при планировании

Пробы — `vault/issues/debt-028/probes/` (только основной каталог, `.gitignore`):

| Проба | Что проверяет | Результат |
|---|---|---|
| `kro_zero_in_histories.py` (+ `.txt`) | есть ли $k_{ro} = 0$ в историях 20 примеров (снимок DEBT-033) | нет ни в одном; запас — см. «Расхождение 1» |
| `q_from_g_roundoff.py` (+ `.txt`) | $\mathcal{Q} = G\cdot B$ против $\mathcal{T}\lambda\Delta p$ на фикстурах `test_fluxes` | ≤ 4.36e-16 (1ph), ≤ 2.71e-16 (2ph) |
| `planned_code.py` | код шагов 3–5 (функции плана) + `apply()` — подмена в памяти | — |
| `planned_plugin.py` | pytest-плагин: `apply()` до сбора тестов | — |
| `test_planned_debt028.py` | новые тесты плана | текущий код: 16 failed (11 + 1 `TestWellShutIn`, 3 `TestPhaseFluxesFromComponents`, 1 `TestUpstreamWithZeroKro`); код плана: все прошли |
| быстрый уровень с `-p planned_plugin` (`planned_fast_tests.txt`) | весь быстрый уровень с кодом плана, фикстура **старая** | 976 passed, 11 failed — ровно `TestTwoPhaseAllFields[*-0]` (обоснование порядка шагов 2 → 3) |
| `history_snapshot.py save base` / `save planned --planned` / `compare base planned` (`save_base.txt`, `save_planned.txt`, `compare_base_planned.txt`) | истории 20 примеров: текущий код против кода плана (в `save_planned.txt` перед расчётом — строка `код подменён: planned_code.apply()`) | **20 × «побитово», «итого: различий 0»** — по $p, S_g, R_s, T$, regime, $t$, $G_o, G_g, \mathcal{Q}_\alpha, u_\alpha, m_\alpha$ |

Снимок `planned` снят с первой редакцией `planned_code.compute_fluxes` (закрытие скважины явными нулями вместо `dp_w = 0.0`); на рабочий путь это не влияет — адаптер `compute_fluxes` не вызывает. Текущая редакция проверена тестами пробы и быстрыми модулями (`test_planned_debt028.py`, `test_fluxes.py`, `test_hydro.py`, `test_energy.py`, `test_val002.py` с плагином: 281 passed, 11 failed — те же тесты старой фикстуры).

Запуск проб — в docstring каждой. Плагин и тесты пробы — из `numerical_solver` с `$env:PYTHONPATH = "..\vault\issues\debt-028\probes"`.
