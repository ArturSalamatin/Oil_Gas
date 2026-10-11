---
tags:
  - план
  - рефакторинг
date: 2026-10-11
issue: DEBT-063
github: 98
branch: refactor/debt-063/unify-grid-prototype-centers
status: реализован
worktree: .worktrees/debt-063
audit:
  date: 2026-10-11
  round: 1
  base: 6cf8515
  found: 10
  auto-fixed: 10
  manual-required: 1   # допуск TestMassBalance — решён пользователем 2026-10-11: 1e-6
---

# DEBT-063: одна сетка — центры ячеек GPN как у прототипа, $\sqrt{r_{j-1/2}r_{j+1/2}}$

## Кратко

- **Дефект.** Гидродинамику считает прототип на `RadialGrid` с центрами $\sqrt{r_{j-1/2}r_{j+1/2}}$ (`radial_blackoil/grid.py:10`). GPN строит рядом `LogRadialGrid` с теми же гранями, но центрами $\exp\langle\ln r\rangle$ (`eq:cell_center`, `_cell_centers_mass`). По этим центрам выводятся профили прототипа, считаются веса $\lambda$ и контурная кондуктивная проводимость энергии и строится аналитика примеров. Расхождение $\approx h^2/6$ по $\ln r$, $h = \ln(R_{ext}/r_w)/N$; граничные проводимости различаются на $\approx h/3$. Сравнения с аналитикой получают ошибку, которой в решении нет (VAL-001: 8.5e-4 при точном совпадении в центрах прототипа).
- **Решения пользователя** (раздел 0): вариант A — GPN на центры прототипа, прототип не меняется; способ A1 — формула в `LogRadialGrid`; сторож — только тест; DEBT-060 поглощена.
- **Что меняется в расчёте.** Гидродинамика — побитово та же (прототип наших центров не видит). Температура — на $\le 2\cdot10^{-8}$ К у забоя и $\le 10^{-5}$ К по полю (проба `examples_shift.py`, 23 примера). Член теплопроводности в балансе энергии примеров 10–21 — на 1–5 % (контурная проводимость, множитель $\approx 1 - h/3$); $\Delta E$ — на $\le 10^{-4}$. Ломаются ровно 4 теста `test_grid.py` (эталон $N = 3$ и свойство $\exp\langle\ln r\rangle$; проба `sqrt_centers_plugin.py` — полный прогон с подменой формулы).
- **Что меняется в документах** (пробы — раздел 1; полный список правок — шаг 4, таблица 4.1: 104 замены в 21 README, 2 скриптах сходимости и 2 комментариях тестов + 13 строк сводной таблицы баланса энергии; согласованность с файлами проверяет `table41_check.py`). Тесты эти числа не проверяют. Группы:
  - сверка с замкнутым решением $\max|p_{ана}-p_{чис}|$ (13 примеров) — меньше на 1–34 %: из неё уходит разница точек;
  - численный фронт $r_b$ (интерполяция по $\ln r$ между центрами) — на множитель $e^{-\delta_N}$, $\delta_N \approx h^2/6$;
  - радиусы центров ячеек в тексте («центр 186.08 м», «$r_{N-1} = 47.11$ м», «0.9–75 м», «117.9 м»);
  - член теплопроводности и относительная невязка баланса энергии (README 10–21, сводная таблица);
  - таблицы сходимости 03, 04 и докстринги скриптов сходимости 04, 05; в 05 наблюдаемый порядок по давлению 1.160 → 0.926 — первый, как у схемы против потока: прежний «1.16» давала примесь разницы точек.
- **Тесты на решении прототипа ужесточаются:** `test_val001` и `test_factory_standing_hydro` — `rtol` 1e-2 → 1e-12 (в центрах прототипа отклонение 0 и 6.7e-16); `TestMassBalance` — `atol` 0.02 → 1e-6 по критерию сходимости Ньютона прототипа.
- **Шагов:** 7 (0 — подготовка, 6 — итог). Файлов: 1 модуль ядра, 1 `.tex`, 4 теста + `test_examples.py` (2 комментария), 21 README + 2 скрипта сходимости + `prototype_input.py` (комментарий), 5 заметок vault. Тестов +4 (1699 → 1703).
- **Оценка:** ~4 ч, из них ~10 мин полный прогон, ~1.5 ч правки README по таблице 4.1 и ~15 мин перезапуск скриптов для сверки.

## 0. Решения пользователя

1. **2026-10-10:** вариант A — GPN переходит на центры прототипа $\sqrt{r_{j-1/2}r_{j+1/2}}$; прототип и его эталон регрессии не меняются. Вариант B (прототип на $\exp\langle\ln r\rangle$) отклонён: пересъём эталона и сверка с IMEX без выигрыша в точности.
2. **2026-10-10:** DEBT-060 (#96) поглощена: название «центр масс» уходит вместе с формулой; находки её плана (тесты `test_val001`, `test_flux_exact_for_any_N`, `TestMassBalance`) — здесь. `TestMassBalance` — исправить докстринг и допуск («по замеру с запасом, порядка 1e-9 — уточнить при планировании»; уточнение — раздел 4, ⚠️ «Допуск `TestMassBalance`»).
3. **2026-10-11:** способ **A1** — формула $\sqrt{\cdot}$ в `LogRadialGrid`, без зависимости сетки от прототипа; совпадение с `RadialGrid` — новым тестом, побитово.
4. **2026-10-11:** сторож согласованности — **только тест**, без проверки в фабрике.
5. **2026-10-11 (после аудита 1):** допуск `TestMassBalance` — **1e-6** (не «порядка 1e-9»): выше гарантии критерия Ньютона прототипа на шаге теста (3.7e-7 в долях дебита) и не зависит от квадратичной сходимости последней итерации.

## Как начать работу по этому плану

1. Прочитай этот файл целиком, затем запись DEBT-063 в [[известные баги и технический долг]] и issue #98 (`gh issue view 98 --repo ArturSalamatin/Oil_Gas`).
2. Материалы задачи, которые `/implement` коммитит в базовую ветку до создания worktree: этот план, `vault/issues/debt-063/` (тело issue, комментарии, пробы и их выходы `*.out.txt`, каталог `probes/stdout/`), реестр техдолга. Отменённый план DEBT-060 и `vault/issues/debt-060/` — тоже (незакоммичены в основном каталоге).
3. Ветка от базовой — в worktree:
   ```powershell
   git worktree add .worktrees/debt-063 -b refactor/debt-063/unify-grid-prototype-centers numerical_scheme/implementation
   ```
4. Переменные (PowerShell; переменные не переживают отдельный вызов инструмента — задавать в той же команде, что и запуск). В worktree `.venv` нет — берётся интерпретатор основного каталога. pytest из `$WT` берёт код worktree (`pythonpath` в `pyproject.toml`, DEBT-059). **Скрипты вне pytest** (`main.py` примеров, скрипты сходимости, пробы) без подготовки берут пакеты `gpn_multiphase_solver` и `radial_blackoil` **основного** каталога — оба установлены в venv в редактируемом режиме (правило 3 `/implement`). Поэтому каждый запуск скриптов — с `PYTHONPATH` на worktree в той же команде; `run_with_centers.py` печатает пути обоих пакетов (строка `пакеты:`), пробы `vault/issues/debt-063/probes/*.py` вставляют `$WT` и прототип `$WT` в `sys.path` сами и печатают `solver:`:
   ```powershell
   $PY   = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   $P    = "D:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\debt-063\probes"   # пробы — в основном каталоге
   $ROOT = "D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\debt-063"
   $WT   = "$ROOT\numerical_solver"                                            # отсюда pytest и скрипты
   $BASE = git -C $ROOT merge-base refactor/debt-063/unify-grid-prototype-centers numerical_scheme/implementation
   $env:PYTHONPATH = "$WT;$WT\HydroSolverPrototype\Prototype_1.0.3"; $env:PYTHONIOENCODING = "utf-8"
   & $PY -c "import gpn_multiphase_solver as g, radial_blackoil as r; print(g.__file__, r.__file__)"   # оба — в $WT
   ```
5. **Прототип `HydroSolverPrototype/` план не трогает** — его тесты и регрессия не нужны.
6. Точки коммитов (на ветке задачи; формат — CLAUDE.md, «Коммиты»; stage по имени файла; vault — отдельно от кода):
   - после шага 1 — `docs: problem_statement — центр ячейки как среднее геометрическое граней, как у прототипа (DEBT-063)`;
   - после шага 2 — `refactor: LogRadialGrid — центры √(r_{j-1/2}·r_{j+1/2}), как у прототипа; тесты сетки и совпадения с RadialGrid (DEBT-063)`: `grid/log_radial.py`, `tests/test_grid.py`, `tests/test_prototype_adapter.py`;
   - после шага 3 — `test: решение прототипа сверяется в его центрах — VAL-001, baseline Дюпюи rtol 1e-12, баланс нефти atol 1e-6 (DEBT-063)`: `tests/test_val001.py`, `tests/test_factory_standing_hydro.py`, `tests/test_prototype_adapter.py`;
   - после шага 4 — `docs: числа сверки с аналитикой в README и скриптах сходимости после смены центров (DEBT-063)`;
   - после шага 5 — `vault: центры ячеек — одна сетка с прототипом в заметках (DEBT-063)`;
   - шаг 6 — vault задачи (реестр, план, пробы).

## Порядок влития

План написан на `123247a` (после влития BUG-027, BUG-024, DEBT-059): тестов 1699, в быстром уровне 1428. Пробы с числами шли на `6aaf9e9`…`d7528d4` — эти влития расчёт примеров, сеток и тестов из плана не меняют (BUG-024 — числа примера 17 по ступени 4, не по центрам; DEBT-059 — упаковка прототипа). Номера строк ниже — на `123247a`; после чужих влитий они сдвинутся — **править по тексту (`Edit` по уникальной подстроке), не по номеру**.

| Задача | Состояние на 2026-10-11 | Пересечение |
|---|---|---|
| **DEBT-059** (#94) — прототип устанавливаемым пакетом | влит (`29a1ffa`) | Импорт `radial_blackoil` в тестах — через установленный пакет; новый тест `test_prototype_adapter.py` импортирует его так же, как модуль сейчас. |
| **DEBT-020** — проводимости граней в одном массиве `Q_T` $[N+1]$ | **реализуется** (`.worktrees/debt-020`, с `6cf8515`) | Правит сборку теплопроводности `energy/tridiag.py` (`:330–358` — те строки, что берут `log_weights_*` и `r_centers[-1]`), тесты `test_energy.py`, `test_val002.py`, `test_energy_matrix_examples.py`, `test_examples.py` (ссылки на строки), `examples/02_single_phase_jt/main.py`, словарь `§5.4` (~`:326`). DEBT-063 эти строки не правит — меняет значения сетки, которые туда приходят; в словаре правит `:30`. Текстового конфликта нет. Числа: DEBT-020 обещает побитовость с базой своей ветки — на числа таблицы 4.1 влиять не должен. Если он влит раньше, сверка шага 4 (п. 1: `impl_energy_*.out.txt` против правого столбца планирования) это и проверит; расхождение — остановиться и разобрать, а не подгонять таблицу. |
| **DEBT-023** — физическая теплопроводность в примерах 03–09 | issue открыт, плана нет | Включит $\lambda \ne 0$ в 03–09: их баланс энергии и $T$ начнут зависеть от центров (сейчас в 03–09 теплопроводность нулевая, и таблица 4.1 строк баланса для них не содержит). **Рекомендуемый порядок — DEBT-063 раньше DEBT-023**: тогда DEBT-023 сразу считает на одной сетке. Если DEBT-023 влит раньше — до шага 4 перезапустить `energy_all.py` и `examples_stdout.py` (обе формулы) и дополнить таблицу 4.1 строками 03–09. |
| **DEBT-008** (#89) — мёртвые поля конфига | план готов | Правит `P8-формат-ввода-json.md` (поля конфига) — не раздел «Центры ячеек» и не «Зарегистрированные задачи» (`:281–309`). |
| **DEBT-048** — память ступени 4 | план готов | Добавляет тесты в `test_prototype_adapter.py` — другие классы; при мерже — соседние вставки. |

## 1. Замеры при планировании (`d7528d4`, пробы — `vault/issues/debt-063/probes/`)

- **Тесты** (`123247a`): 1699 собрано, быстрый уровень 1428 (`-m "not slow"`).
- **Полный прогон с центрами $\sqrt{\cdot}$** (`sqrt_centers_plugin.py` — подключаемый модуль pytest подменяет функцию центров в `log_radial`; код пакета не трогается; при планировании — на `6aaf9e9`: 4 failed, 1684 passed; **аудит 1 повторил на `6cf8515` (= `123247a` + vault): 4 failed, 1695 passed**, выход `sqrt_centers_full_audit.out.txt`) — только `test_grid.py`: `TestSmallGridValues::test_centers`, `::test_transmissibility_well`, `::test_transmissibility_ext` (эталон $N = 3$ строится старой формулой) и `TestCenterMassVerification::test_log_average_property` (свойство $\exp\langle\ln r\rangle$). Выход — `sqrt_centers_full.out.txt`. Примеры (фикстура `results`), сверка матрицы энергии, балансы энергии, VAL-002, VAL-004 — зелёные.
- **Сдвиг историй примеров** (`examples_shift.py`, каждый из 23 примеров считается с обеими формулами в одном процессе; выход `examples_shift.out.txt`):
  - $p$, $S_g$, $q_o$ — **побитово** во всех 23;
  - $T$ в 01–09 — побитово (теплопроводность в них нулевая — веса $\lambda$ и контур не участвуют);
  - $T$ в 10–21: $\max_t|\Delta T(r_w)| \le 2.1\cdot10^{-8}$ К (18), $\max_{t,j}|\Delta T| \le 9.9\cdot10^{-6}$ К (14) — на 6–7 порядков меньше изменения $T$ у забоя за расчёт (0.05–15.5 К).
- **Тесты, сверяющие решение прототипа с Дюпюи:**
  - `test_val001.py::TestDupuitPressure::test_pressure_log_profile` (`vault/issues/debt-060/probes/val001_centers.py`): отклонение в центрах `LogRadialGrid` 8.5e-4, в центрах прототипа — 0;
  - `test_factory_standing_hydro.py::…::test_standing_dupuit_pressure` (`baseline_dupuit.py`, `configs/baseline.json`, $N = 100$, 96 интервалов): 1.03e-4 и 6.7e-16. Оба допуска 1e-2 и объяснение «нестационарное решение» — неверны: расхождение целиком из-за точек сравнения.
- **`TestMassBalance`** (`adapter_balance.py`): невязка баланса нефти $\max|F|/|G_o[0]|$ = 5.5e-12 при `atol=0.02`; центры в баланс не входят (объёмы и потоки — общие с прототипом).
- **Вывод всех скриптов примеров** (`examples_stdout.py` + `run_with_centers.py`: 23 `main.py` и 5 скриптов сходимости, каждый с обеими формулами; выводы — `probes/stdout/{base,sqrt}/`; сравнение — `diff_stdout.py`, выход `diff_stdout.out.txt`): меняется вывод 23 из 28 скриптов. Не меняются: `01` (`main.py`, `spatial_convergence.py`), `02/check_slopes.py`, `04a/grid_convergence.py`, `18/main.py` (последний баланс энергии не печатает — его числа из `energy_all.py`). Группы изменений:
  - **E. сверка с замкнутым решением** $\max|p_{ана}-p_{чис}|$ — 03: 8.00 → 7.45 кПа; 04, 07, 08, 09: 27.95 → 23.58; 04a: 35.87 → 34.95; 05: 15.68 → 10.74; 06: 34.77 → 30.51; 10: 33.60 → 28.78; 11: 14.11 → 10.82; 12: 63.39 → 59.28; 13a: 59.00 → 54.76; 15: 463.97 → 458.12 (выход `closed_form_dp.out.txt` — тот же замер для шести примеров с этой строкой в README). Дебит замкнутого решения от точек не зависит; отклонение от Дюпюи в однофазной зоне (`dupuit_check`) — тоже, с точностью до шума округления: сдвиг $\ln r$ одинаков во всех ячейках, а профиль привязан к последней;
  - **C. численный фронт** $r_b$ (интерполяция $\ln r$ между центрами по $p = p_b$; `fronts.py`, выход `fronts.out.txt`): множитель $e^{-\delta_N}$ — 03: 0.19790487 → 0.19784826; 04, 07, 08, 09: 2.63707 → 2.63029; 04a: 1.50764 → 1.50721; 05: 0.20390 → 0.20337; 06: 2.48934 → 2.48294; 10: 3.57805 → 3.56886; 18: 15.717 → 15.705; ряд 03 по сетке ($N$ = 25…200) — там же;
  - **баланс энергии** (`energy_all.py`, `energy_windows.py`): член теплопроводности 10–21 — меньше на 0.6–5.1 % (10: $+1.3612\cdot10^6$ → $+1.3053\cdot10^6$; 12: $+6.1606\cdot10^6$ → $+5.8494\cdot10^6$; 14: $-9.9756\cdot10^8$ → $-9.9202\cdot10^8$; …); $\Delta E$ — $\le 10^{-4}$ отн.; относительная невязка — на уровне округления, $\le 4.9\cdot10^{-15}$ (было $\le 3.6\cdot10^{-15}$; порог DEBT-043 — $10^{-12}$); в 01–09 баланс побитово тот же;
  - **радиусы центров в тексте и таблицах** (`readme_radii.py`, выход `readme_radii.out.txt` — числа с «м» в тексте и в столбцах таблиц с «м» в заголовке, совпадающие с центром старой формулы и меняющиеся при $\sqrt{\cdot}$): «центр 186.08 м» (последняя ячейка сеток $N = 50$, $R = 200$ м) → 185.36; «$r_{N-1} = 47.11$ м» (11) → 46.99; «117.9 м» (12, 13a) → 117.5; «0.9–75 м» → 0.9–74; столбец «фронт, м» (центр последней ячейки с газом) во временных таблицах 12, 13a, 15 — 26 строк (87.0 → 86.7, 101.3 → 100.9, 117.9 → 117.5, …) и «газ до, м» в 18 — 4 строки (1.89 → 1.88, 3.06 → 3.05, 14.97 → 14.96); пары для правки — `table_radii_pairs.py` → `table_radii_pairs.out.txt` (аудит 1: первая версия плана табличные столбцы пропускала);
  - **02**: $\max|T_{num}-T_{ode}|$ (ОДУ-аналитика в центрах) 0.0036 / 0.0034 / 0.0032 → 0.0035 / 0.0033 / 0.0031 К;
  - **сходимость 04** (`grid_convergence.py`): столбец $\max|dp|$ 63.91 / 27.95 / 13.11 / 8.52 → 46.34 / 23.58 / 12.03 / 8.04 кПа (отношения 1.97, 1.96, 1.50 — первый порядок, как у дебита), $r_b$ 2.6936 / 2.6371 / 2.6136 / 2.6064 → 2.6662 / 2.6303 / 2.6119 / 2.6057;
  - **сходимость 05** (`closed_form_convergence.py`): отклонение $p$, % — 0.3199 / 0.1307 / 0.0573 / 0.0265 / 0.0127 → 0.1547 / 0.0895 / 0.0470 / 0.0239 / 0.0121; порядок по давлению 1.160 → 0.926, отношение по краям 25.1× → 12.8× (у дебита 13.2×) — прежний «сверхпервый» порядок давала разница точек, убывающая как $h^2$.
- **Не от DEBT-063** (замечено при сравнении): README 04, таблица «Сходимость по сетке» — $T(r_w)$ при $N$ = 100, 150 записаны 351.4888 / 351.4877, а скрипт и до, и после смены центров печатает 351.4884 / 351.4872 (отсюда и «приращения 0.0051 и 0.0027 К» вместо 0.0031); сводная таблица баланса энергии — у 06 невязка $1.2\cdot10^{-15}$, расчёт даёт $1.1\cdot10^{-15}$. Строки 04 переписываются из вывода скрипта целиком (шаг 4) — давнее расхождение уходит попутно; строку 06 не трогать.
- **Сборка `.tex`** (копии в каталоге пробы, три прохода; `tex_check.py` берёт блоки «До»/«После» шага 1 из этого плана; выход `tex_check.out.txt`): база и с правкой — 0 ошибок, 0 неопределённых ссылок, 18 Overfull, 37 страниц; `eq:cell_center` — (38), с. 14, `eq:face_interp` — (43); нумерация не сдвигается (уравнений не добавлено). Страница 14 с правкой просмотрена. ⚠️ В `numerical_solver/doc/` основного каталога лежит устаревший `problem_statement.aux` (22.09): сборка оттуда с `-output-directory` даёт ложные «undefined». В worktree `.aux` нет.

## 2. Целевое состояние

- `LogRadialGrid.r_centers` = $\sqrt{r_{j-1/2}r_{j+1/2}}$ — побитово как `RadialGrid.centers_m` прототипа при тех же $r_w$, $R_{ext}$, $N$; функция `_cell_centers_mass` (и её ветка «тонкого слоя») удалена.
- `eq:cell_center`: $\ln r_j = \tfrac12(\ln r_{j-1/2} + \ln r_{j+1/2})$, $r_j = \sqrt{r_{j-1/2}r_{j+1/2}}$; в тексте — почему (одна сетка с гидродинамикой; Дюпюи точен при любом центре) и следствие для весов `eq:face_interp` (равны).
- Слов «центр масс», «логарифмически взвешенное среднее» и имён `_cell_centers_mass`, `TestCenterMassVerification` нет в `numerical_solver/` и `vault/knowledge/decisions/`.
- Тесты, сверяющие решение прототипа с Дюпюи, — `rtol=1e-12`; баланс нефти адаптера — `atol=1e-6`.
- Числа README и скриптов сходимости, зависящие от точек сравнения, — по новому выводу скриптов.
- Заметки vault описывают одну сетку; «временное решение» FEAT-012 и незарегистрированные «задачи» P8 закрыты ссылкой на DEBT-063.

### Связь формула → код

| Формула (`problem_statement.tex`) | Код | Тест |
|---|---|---|
| `eq:cell_center`: $r_j = \sqrt{r_{j-1/2}r_{j+1/2}}$ | `grid/log_radial.py::LogRadialGrid.__init__` (центры) | `test_grid.py::TestCellCenterGeometricMean::test_log_midpoint_property`, `TestSmallGridValues::test_centers`; `test_prototype_adapter.py::TestGridsMatchPrototype::test_same_cells` |
| `eq:face_interp` (веса $w_L = w_R$ на сетке `eq:log_grid`) | `log_weights_left/right` | `test_grid.py::TestCellCenterGeometricMean::test_equal_log_weights` |
| `eq:transmissibility`, граничные проводимости под `eq:bc_flux_well` | `trans_internal`, `trans_well`, `trans_ext` | `test_grid.py::TestSmallGridValues::test_transmissibility_*` (эталон через `CENTERS_3`) |

## 3. Варианты (выбран A1 — раздел 0)

- **A1.** Формула $\sqrt{\cdot}$ в `LogRadialGrid`; совпадение с прототипом — тест. Минимальный diff (1 модуль), сетка не зависит от прототипа — её по-прежнему строят тесты и двойники без прототипа.
- **A2.** Фабрика передаёт центры `RadialGrid` в `LogRadialGrid`: единый источник, но новый параметр конструктора, сборка сетки после прототипа и всё равно формула внутри для путей без прототипа — два пути вместо одного.
- **B.** Прототип на $\exp\langle\ln r\rangle$ — отклонён (раздел 0, п. 1).
- **Точность выбора** (проба `center_accuracy.py`, однофазный упругий приток, точное по времени решение, эталон $N = 2000$): стационар Дюпюи точен у обоих центров до 1e-13; в нестационаре оба второго порядка, при $N = 100$ дебит точнее у $\sqrt{\cdot}$ вдвое (основной участок), среднее по ячейке давление — у $\exp\langle\ln r\rangle$ в 2–11 раз. Равномерно лучшего нет; решает согласованность с гидродинамикой.

## 4. Подводные камни

- ✅ **Места вызова:** `_cell_centers_mass` — единственный вызов `log_radial.py:64`; вне модуля имя не встречается (grep по репозиторию без `.venv`). `TestCenterMassVerification` — только определение.
- ✅ **API:** свойства `LogRadialGrid` те же; меняются значения `r_centers`, `trans_well`, `trans_ext`, `log_weights_*` ($\approx h^2/6$ и $\approx h/3$); `trans_internal` — с точностью до округления (отношение соседних центров у обеих формул $e^h$).
- ✅ **Гидродинамика:** прототип строит свою `RadialGrid` (`factory.py:407`) и наших центров не видит; адаптер берёт потоки прототипа. Проба: $p$, $S_g$, $q_o$ побитово.
- ⚠️ **Энергия:** веса `log_weights_*` (при неоднородной $\lambda$) и контурная проводимость `energy/tridiag.py:354–355` меняются; сверка матрицы энергии (`test_energy_matrix_examples.py`, эталон строит матрицу из той же сетки) и балансы — зелёные в пробе. Изменение $T$ — $\le 10^{-5}$ К.
- ⚠️ **Тест-сторож DEBT-010** (`tests/test_eq_references.py`): ссылки только меткой; новые тексты ссылаются на `eq:cell_center`, `eq:face_interp` — обе объявлены. Номер уравнения в скобках после метки («`eq:x (74)`») — DEBT-062, не писать.
- ⚠️ **Допуск `TestMassBalance`.** Решение пользователя — «порядка 1e-9, уточнить». Критерий сходимости Ньютона прототипа — $\|F\|_\infty \le 10^{-11} + 10^{-8}\|F_0\|_\infty$ м³ст/с (`radial_blackoil/blackoil.py:347`, `_newton_fixed_active_set`). Аудит 1 замерил $\|F_0\|_\infty$ этого шага (`adapter_balance.py`, перехват `_newton_fixed_active_set`): $1.1\cdot10^{-1}$ м³ст/с $\approx 37\,|G_o[0]|$ — в начальном приближении весь перепад $p_0 - p_{wf}$ приходится на забойную грань, а невязка включает и газовое уравнение. Гарантия критерия в долях дебита — **3.7e-7**; замер 5.5e-12 получен за счёт квадратичной сходимости последней итерации (итоговая $\|F\|_\infty = 1.6\cdot10^{-14}$). Допуск 1e-9 держался бы только на этом запасе и мог бы упасть при другой последовательности итераций (смена прототипа, BLAS); **1e-6** — выше гарантии в 2.7 раза и в 2·10⁴ раз строже нынешнего 0.02 (первая версия плана писала «гарантия ~1e-8, запас 100×» — неверно, исправлено аудитом 1). ✅ Пользователь подтвердил 1e-6 (раздел 0, п. 5).
- ⚠️ **Числа README и скриптов** — не проверяются тестами (полный прогон с подменой зелёный); правятся по таблице 4.1 и сверяются выводом скриптов (шаг 4). Скрипты вне pytest — из `$WT` с `PYTHONPATH` на worktree в той же команде (правило 3 `/implement`): без него `main.py` и скрипты сходимости возьмут пакеты основного каталога (оба установлены в venv в редактируемом режиме).
- ⚠️ **Пробы, подменяющие формулу** (`sqrt_centers_plugin.py`, `examples_shift.py`, `run_with_centers.py` в режиме `sqrt`), после шага 2 не запускаются: функции `_cell_centers_mass` больше нет. Для сверки после шага 2 — `examples_stdout.py impl`, `energy_all.py`, `energy_windows.py` (запасной путь — один расчёт текущим кодом), `fronts.py`, `closed_form_dp.py` (подмены не делают).
- ⚠️ **Графики примеров** в `examples/*/output/` (в `.gitignore`) после перезапуска скриптов шага 4 — новые; коммитить нечего.
- ⚠️ **`--lf` после переименования класса тестов** — упавший `test_log_average_property` под новым именем не найдётся; прогонять файл.
- ⚠️ **Устаревший `.aux`** в основном каталоге — собирать `.tex` в `$WT\doc` (три прохода), выходы удалить после проверки.
- ✅ **Конфиги, импорты, циклы, производительность:** не меняются ($\sqrt{\cdot}$ дешевле прежней формулы).
- ✅ **Прототип:** не трогается.

## Шаг 0. Подготовка

**Цель:** worktree, базовое состояние, сборка `.tex`.

**Что сделать:**
1. Worktree и переменные («Как начать», п. 3–4).
2. Из `$WT`:
   ```powershell
   Set-Location $WT
   & $PY -m pytest tests/ --collect-only -q | Select-Object -Last 1
   & $PY -m pytest tests/ -m "not slow" -q | Select-Object -Last 3
   ```
   Ожидание: 1699 собрано, 1428 passed (~70 с), если база не уехала; иначе записать фактические. План добавляет 4 теста.
3. Сборка `.tex` в worktree (три прохода — оглавление и `longtable`):
   ```powershell
   Set-Location "$WT\doc"
   1..3 | ForEach-Object { pdflatex -interaction=nonstopmode -halt-on-error problem_statement.tex | Out-Null }
   $log = Get-Content problem_statement.log -Encoding UTF8
   "errors: "    + ($log | Select-String '^!').Count
   "undefined: " + ($log | Select-String 'undefined').Count
   "overfull: "  + ($log | Select-String 'Overfull').Count
   ($log | Select-String 'Output written').Line
   ```
   Ожидание (`$P\tex_check.out.txt`, «base»): 0 / 0 / 18, 37 страниц.

**Регресс:** — (кода нет). **Оценка:** ~5 мин.

## Шаг 1. Постановка: `eq:cell_center`

**Цель:** постановка задаёт центры $\sqrt{r_{j-1/2}r_{j+1/2}}$ и объясняет выбор.

**Файлы:** `numerical_solver/doc/problem_statement.tex` (раздел `ssec:grid`, абзац «Центры ячеек», `:937–951`).

**Изменения:**

До:
```latex
\paragraph{Центры ячеек}
--- центр масс кольцевого слоя (логарифмически взвешенное
среднее граней). Для всех ячеек ($j = 0, 1, \ldots, N-1$):
\begin{equation}\label{eq:cell_center}
  r_j = r_{j+\half}\,
  \sqrt{\exp\!\left(
    -\frac{x\ln x}{1 - x} - 1
  \right)},
  \qquad
  x = \left(\frac{r_{j-\half}}{r_{j+\half}}\right)^2.
\end{equation}
Центры граничных ячеек ($j = 0$ и~$j = N{-}1$) определяются
```

После:
```latex
\paragraph{Центры ячеек}
--- середина ячейки по~$\ln r$, то~есть среднее геометрическое
граней. Для всех ячеек ($j = 0, 1, \ldots, N-1$):
\begin{equation}\label{eq:cell_center}
  \ln r_j = \tfrac{1}{2}\bigl(\ln r_{j-\half} + \ln r_{j+\half}\bigr),
  \qquad
  r_j = \sqrt{r_{j-\half}\,r_{j+\half}}.
\end{equation}
Те~же центры у~гидродинамического решателя (прототип
\texttt{radial\_blackoil}), поэтому балансы масс, уравнение энергии
и~вывод профилей относятся к~одним и~тем~же точкам. На~точность
стационарного однофазного притока выбор центра не~влияет: с~проводимостью
грани~\eqref{eq:transmissibility} профиль Дюпюи $p = A + B\ln r$
воспроизводится в~центрах точно при любом их положении внутри
ячейки. На~сетке~\eqref{eq:log_grid} центры делят расстояние между
гранями пополам по~$\ln r$, поэтому веса~\eqref{eq:face_interp}
равны: $\ln(r_{j+\half}/r_j) = \ln(r_{j+1}/r_{j+\half})$.
Центры граничных ячеек ($j = 0$ и~$j = N{-}1$) определяются
```

Остаток абзаца («…по~той же формуле, что и~внутренние…») — без изменений.

**Проверка после шага:**
1. Сборка — команда шага 0, п. 3. Ожидание (`$P\tex_check.out.txt`, «step1»): 0 / 0 / 18, 37 страниц.
2. Глазами: с. 14 (`Read` по `$WT\doc\problem_statement.pdf`, `pages: "14"`) — (38) в двух формах, абзац о прототипе и Дюпюи, ссылки (40), (37), (43) разрешены.
3. `& $PY -m pytest tests/test_eq_references.py -q` из `$WT` — 2 passed.
4. Удалить выходы сборки: `Remove-Item "$WT\doc\problem_statement.*" -Exclude problem_statement.tex`.
- **Регресс:** `--collect-only -q` (только документ).

**Оценка:** ~15 строк, ~15 мин.

## Шаг 2. `LogRadialGrid` на центры прототипа; тесты сетки

**Цель:** `r_centers` = $\sqrt{r_{j-1/2}r_{j+1/2}}$ побитово как у `RadialGrid`; тесты сетки — по новой формуле. Один коммит: после правки формулы четыре теста `test_grid.py` красные, пока не обновлены эталоны.

**Файлы:** `numerical_solver/gpn_multiphase_solver/grid/log_radial.py`, `numerical_solver/tests/test_grid.py`, `numerical_solver/tests/test_prototype_adapter.py`.

**Изменения — `log_radial.py`:**

До (`:7–32`, функция и докстринг класса):
```python
import numpy as np
from .base import Grid


def _cell_centers_mass(r_left: np.ndarray, r_right: np.ndarray) -> np.ndarray:
    """Центры масс кольцевых слоёв (vectorized). Ур. (eq:cell_center) problem_statement.tex.

    r_j = r_right * sqrt(exp(-x*ln(x)/(1-x) - 1)),  x = (r_left/r_right)^2
    """
    x = (r_left / r_right) ** 2
    thin = np.abs(x - 1.0) < 1e-12
    x_safe = np.where(thin, 0.5, x)
    arg = -x_safe * np.log(x_safe) / (1.0 - x_safe) - 1.0
    result = r_right * np.sqrt(np.exp(arg))
    result[thin] = 0.5 * (r_left[thin] + r_right[thin])
    return result


class LogRadialGrid(Grid):
    """Логарифмическая радиальная сетка с центрами масс.

    Грани: geomspace(r_well, R_ext, N+1).
    Центры: центр масс кольцевого слоя (eq:cell_center).
```
После:
```python
import numpy as np
from .base import Grid


class LogRadialGrid(Grid):
    """Логарифмическая радиальная сетка.

    Грани: geomspace(r_well, R_ext, N+1).
    Центры: среднее геометрическое граней √(r_{j-1/2}·r_{j+1/2}) (eq:cell_center).
```

До (`:63–66`):
```python
        # Центры (eq:cell_center)
        self._r_centers = _cell_centers_mass(
            self._r_faces[:-1], self._r_faces[1:]
        )
```
После:
```python
        # Центры (eq:cell_center): середина ячейки по ln r — среднее
        # геометрическое граней. Та же формула и тот же порядок операций,
        # что у RadialGrid прототипа (radial_blackoil/grid.py), — центры
        # совпадают побитово, и гидродинамика, энергия и вывод относятся к
        # одним точкам (DEBT-063). Совпадение проверяет
        # tests/test_prototype_adapter.py::TestGridsMatchPrototype.
        self._r_centers = np.sqrt(self._r_faces[:-1] * self._r_faces[1:])
```

**Изменения — `test_grid.py`:**

До (`:71–90`):
```python
# ── Эталонные значения для малой сетки ────────────────────────
#
# N=3, r_w=1, R_ext=8, h=1, k=1
# Грани (geomspace): r_f = 1 · (8/1)^{j/3} = 1, 2, 4, 8
# x = (r_L/r_R)^2 = (1/2)^2 = 0.25 — одинаков для всех ячеек
# Центр масс: r_j = r_R · sqrt(exp(-0.25·ln(0.25)/(1-0.25) - 1))
#           = r_R · sqrt(exp(-0.25·(-1.3863)/0.75 - 1))
#           = r_R · sqrt(exp(0.4621 - 1))
#           = r_R · sqrt(exp(-0.5379))
#           = r_R · sqrt(0.58388)
#           = r_R · 0.76413

R_W = 1.0
R_E = 8.0
FACES_3 = np.array([1.0, 2.0, 4.0, 8.0])

# Вычислим эталонные центры:
_x = 0.25
_factor = np.sqrt(np.exp(-_x * np.log(_x) / (1.0 - _x) - 1.0))
CENTERS_3 = FACES_3[1:] * _factor  # [2·f, 4·f, 8·f]
```
После:
```python
# ── Эталонные значения для малой сетки ────────────────────────
#
# N=3, r_w=1, R_ext=8, h=1, k=1
# Грани (geomspace): r_f = 1 · (8/1)^{j/3} = 1, 2, 4, 8
# r_L/r_R = 1/2 — одинаково для всех ячеек
# Центр ячейки — среднее геометрическое граней (eq:cell_center):
# r_j = √(r_L · r_R) = r_R · √(r_L/r_R) = r_R · √0.5 = r_R · 0.70711

R_W = 1.0
R_E = 8.0
FACES_3 = np.array([1.0, 2.0, 4.0, 8.0])

# Вычислим эталонные центры:
_factor = np.sqrt(0.5)
CENTERS_3 = FACES_3[1:] * _factor  # [2·f, 4·f, 8·f]
```

До (`:190–191`):
```python
    def test_flux_exact_for_any_N(self):
        """Центр масс кольца точен для логарифмического профиля при любом N."""
```
После:
```python
    def test_flux_exact_for_any_N(self):
        """Забойный поток на логарифмическом профиле точен при любом N."""
        # Точность — свойство проводимости грани 2πkh/ln(r_0/r_w), а не выбора
        # центра: при p = A + B·ln r поток T·(p_0 − p_wf)/μ = 2πkh·B/μ не зависит
        # от r_0. Сам центр ячейки проверяет TestCellCenterGeometricMean.
```

До (`:306–328`):
```python
# ── Центр масс: независимая верификация ───────────────────────

class TestCenterMassVerification:
    """Проверка: r_center — точка, где <ln(r)>_volume = ln(r_center)."""

    @pytest.fixture
    def grid(self):
        return LogRadialGrid(r_well=0.1, R_ext=500.0, h=10.0, N=50)

    def test_log_average_property(self, grid):
        """∫ ln(r)·r dr / ∫ r dr по кольцу [r_L, r_R] должен = ln(r_center)."""
        for j in range(grid.N):
            r_L = grid.r_faces[j]
            r_R = grid.r_faces[j + 1]
            # ∫_{r_L}^{r_R} r·ln(r) dr = [r²/2·ln(r) - r²/4]
            integral_num = (
                r_R**2 / 2 * np.log(r_R) - r_R**2 / 4
                - r_L**2 / 2 * np.log(r_L) + r_L**2 / 4
            )
            integral_den = (r_R**2 - r_L**2) / 2
            log_avg = integral_num / integral_den
            assert log_avg == pytest.approx(
                np.log(grid.r_centers[j]), rel=1e-12), f"cell {j}"
```
После (разделитель — 64 символа, как соседние):
```python
# ── Центр ячейки: независимая верификация ─────────────────────

class TestCellCenterGeometricMean:
    """Проверка eq:cell_center: центр — середина ячейки по ln r."""

    @pytest.fixture
    def grid(self):
        return LogRadialGrid(r_well=0.1, R_ext=500.0, h=10.0, N=50)

    def test_log_midpoint_property(self, grid):
        """ln r_j = (ln r_{j-1/2} + ln r_{j+1/2})/2 в каждой ячейке."""
        # Эталон — по граням, независимо от кода центров. Допуск абсолютный:
        # ln r проходит через ноль (r ≈ 1 м на этой сетке)
        mid = 0.5 * (np.log(grid.r_faces[:-1]) + np.log(grid.r_faces[1:]))
        np.testing.assert_allclose(np.log(grid.r_centers), mid, rtol=0, atol=1e-13)

    def test_equal_log_weights(self, grid):
        """Веса eq:face_interp равны: w_L = ln(r_{j+1/2}/r_j) = w_R = ln(r_{j+1}/r_{j+1/2})."""
        # На сетке eq:log_grid обе половины — по половине шага ln(r_{j+1}/r_j)
        np.testing.assert_allclose(grid.log_weights_left, grid.log_weights_right,
                                   rtol=1e-12)
```

**Изменения — `test_prototype_adapter.py`** (новый класс — сразу после фикстур, перед разделом «A. Шаг 1: set_bhp_control», после строки `return adapter.solve(initial_state, dt=DT, bc=bc)`):
```python


# ═══════════════════════════════════════════════════════════
# 0. Одна сетка с прототипом (DEBT-063)
# ═══════════════════════════════════════════════════════════

class TestGridsMatchPrototype:
    """LogRadialGrid и RadialGrid прототипа — одни и те же ячейки.

    Фабрика строит обе сетки из одних полей конфига (factory.py, сетка
    прототипа — в _create_prototype_hydro). Гидродинамику считает прототип на
    своей, энергию и вывод GPN — на LogRadialGrid. Расхождение центров
    отнесло бы решение прототипа к чужим точкам (до DEBT-063 — на h²/6 по
    ln r) — побитовое сравнение ловит любую правку формулы с одной стороны.
    """

    @pytest.mark.parametrize("r_w, R, n", [
        (0.1, 50.0, 20),      # VAL-001, этот модуль
        (0.1, 50.0, 100),     # configs/baseline.json
        (0.1, 200.0, 350),    # пример 19 (мелкая сетка)
    ])
    def test_same_cells(self, r_w, R, n):
        """Грани, центры, объёмы совпадают побитово."""
        ours = LogRadialGrid(r_well=r_w, R_ext=R, h=H, N=n, k=K_PERM)
        proto = RadialGrid(r_w, R, H, n, K_MD)
        np.testing.assert_array_equal(ours.r_faces, proto.faces_m)
        np.testing.assert_array_equal(ours.r_centers, proto.centers_m)
        np.testing.assert_array_equal(ours.volumes, proto.bulk_volumes_m3)
```

**Проверка после шага:**
1. `& $PY -m pytest tests/test_grid.py tests/test_prototype_adapter.py tests/test_eq_references.py -q` из `$WT` — все passed.
2. `& $PY -m pytest tests/ --collect-only -q | Select-Object -Last 1` — база + 4 (`test_grid.py`: −1 +2; `TestGridsMatchPrototype`: +3).
- **Регресс:** быстрый. Полный — в шаге 6 (проба `sqrt_centers_plugin.py` уже показала: вне `test_grid.py` полный прогон зелёный).

**Подводные камни:** ✅ места вызова; ⚠️ `--lf`; ⚠️ сторож DEBT-010 — новые комментарии ссылаются на `eq:cell_center`, `eq:face_interp`, `eq:log_grid`.

**Зависимости:** требует шаг 1 (метки упомянуты в тексте — объявлены и до шага 1, но смысл формулы должен совпадать).

**Оценка:** ~70 строк, ~25 мин.

## Шаг 3. Тесты на решении прототипа: точки и допуски

**Цель:** решение прототипа сверяется там, где оно посчитано, с допусками по замеру.

**Файлы:** `numerical_solver/tests/test_val001.py` (`:88–95`), `numerical_solver/tests/test_factory_standing_hydro.py` (`:81–95`), `numerical_solver/tests/test_prototype_adapter.py` (`:574–596`, `TestMassBalance`).

**Изменения — `test_val001.py`:**

До:
```python
    def test_pressure_log_profile(self):
        """p(r_j) = p_wf + Δp·ln(r_j/rw)/ln(R/rw) на центрах масс ячеек."""
        sim, history = _run_val001()
        r = sim._grid.r_centers
        p_exact = P_WF + (P_EXT - P_WF) * np.log(r / R_WELL) / np.log(R_EXT / R_WELL)
        # Newton-солвер (PrototypeHydroAdapter) даёт нестационарное решение
        # за один шаг dt=86400 с — не точный лог-профиль, фактическая ошибка ~8e-4
        np.testing.assert_allclose(history.states[-1].p, p_exact, rtol=1e-2)
```
После:
```python
    def test_pressure_log_profile(self):
        """p(r_j) = p_wf + Δp·ln(r_j/rw)/ln(R/rw) в центрах ячеек (eq:cell_center)."""
        sim, history = _run_val001()
        r = sim._grid.r_centers
        p_exact = P_WF + (P_EXT - P_WF) * np.log(r / R_WELL) / np.log(R_EXT / R_WELL)
        # Центры LogRadialGrid — те же, что у прототипа, который считает
        # давление (DEBT-063). При c_o = 0 течение несжимаемое: профиль
        # стационарный на каждом шаге, а двухточечная схема с проводимостью
        # 2πkh/ln(r_{j+1}/r_j) воспроизводит его в центрах до округления
        # (замер: отклонение 0). До DEBT-063 эталон строился в других точках
        # и расходился на 8.5e-4 — разница точек, а не ошибка решения.
        np.testing.assert_allclose(history.states[-1].p, p_exact, rtol=1e-12)
```

**Изменения — `test_factory_standing_hydro.py`:**

До:
```python
    def test_standing_dupuit_pressure(self):
        """Профиль давления ≈ лог-профиль Дюпюи (однофазный, Newton).

        baseline.json: 2 интервала, последний p_wf=10e6. Newton даёт
        нестационарное решение, rtol=1e-2.
        """
```
и
```python
        np.testing.assert_allclose(
            history.states[-1].p, p_exact, rtol=1e-2)
```
После:
```python
    def test_standing_dupuit_pressure(self):
        """Профиль давления = лог-профиль Дюпюи в центрах ячеек (однофазный).

        baseline.json, последний p_wf = 10e6. Центры LogRadialGrid — те же,
        что у прототипа (DEBT-063); в них отклонение от Дюпюи — до округления
        (замер DEBT-063: 6.7e-16). Прежние rtol=1e-2 и «нестационарное
        решение» объясняли расхождение 1.03e-4 — разницу точек сравнения.
        """
```
и
```python
        np.testing.assert_allclose(
            history.states[-1].p, p_exact, rtol=1e-12)
```

**Изменения — `test_prototype_adapter.py`, `TestMassBalance`:**

До:
```python
    """F_oil[j] = V·φ·Δ(So/Bo)/dt + G_o[j+1] - G_o[j] ≈ 0.

    Допуск ~2% из-за разных центров ячеек:
    наш Grid — центр масс кольца (eq:cell_center), прототип — √(r_i·r_{i+1}).
    Проводимости расходятся → потоки немного разные.
    """
```
и
```python
        np.testing.assert_allclose(residual / scale, 0.0, atol=0.02,
                                   err_msg="Баланс нефтяного компонента нарушен")
```
После:
```python
    """F_oil[j] = V·φ·Δ(So/Bo)/dt + G_o[j+1] - G_o[j] ≈ 0.

    Баланс собран из объёмов ячеек (общих с прототипом) и потоков G_o
    прототипа — центры ячеек в него не входят. Невязку ограничивает критерий
    Ньютона прототипа ||F||_inf <= 1e-11 + 1e-8·||F0||_inf м³ст/с
    (radial_blackoil/blackoil.py, _newton_fixed_active_set). На этом шаге
    ||F0||_inf ≈ 37·|G_o[0]| — гарантия 3.7e-7 в долях дебита, допуск 1e-6
    её покрывает. Замер DEBT-063 — 5.5e-12 (квадратичная сходимость).
    Прежний допуск 0.02 объяснялся «разными центрами» — неверно.
    """
```
и
```python
        np.testing.assert_allclose(residual / scale, 0.0, atol=1e-6,
                                   err_msg="Баланс нефтяного компонента нарушен")
```

**Проверка после шага:**
1. `& $PY -m pytest tests/test_val001.py tests/test_factory_standing_hydro.py tests/test_prototype_adapter.py -q` из `$WT` — все passed.
2. Пробы на коде worktree — из `$WT`, с переменными «Как начать», п. 4 в той же команде (пробы печатают `solver:` — должен быть `$WT`): `& $PY "D:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\debt-060\probes\val001_centers.py"` → все три строки 0 (центры совпали — эталоны в обеих точках одинаковы); `& $PY "$P\baseline_dupuit.py" 2>$null` → все три строки ~1e-16; `& $PY "$P\adapter_balance.py"` → невязка ~5e-12, строка «Ньютон 0: … ||F0||_inf ≈ 37·|G_o[0]| … гарантия 3.7e-07» (как в `adapter_balance.out.txt`).
- **Регресс:** быстрый.

**Зависимости:** требует шаг 2.

**Оценка:** ~30 строк, ~20 мин.

## Шаг 4. Числа примеров

**Цель:** опубликованные числа, зависящие от точек сравнения или от проводимостей энергии, — по расчёту на одной сетке.

**Файлы:** README 21 примера и сводный `examples/README.md`; `examples/04_table_table/grid_convergence.py`, `examples/05_standing_table_rp/closed_form_convergence.py`, `examples/18_prototype_input/prototype_input.py` (докстринги, комментарий); `tests/test_examples.py` (два комментария). Пути ниже — от `numerical_solver/examples/`, кроме оговорённых.

**Контекст:** числа таблицы 4.1 получены пробами при планировании с подменой формулы центров на $\sqrt{\cdot}$ (раздел 1) — тем же расчётом, что даст код после шага 2. Тесты эти числа не проверяют (полный прогон с подменой — зелёный), поэтому сверка — перезапуском скриптов (п. 1). Правка — по тексту: строка-«было» уникальна в своём файле; номер строки — ориентир на `123247a`.

**Что сделать:**
1. Сверка (код worktree после шагов 2–3; правый столбец «→» планирования = вывод нового кода):
   ```powershell
   # Переменные «Как начать», п. 4 — в той же команде ($PY, $P, $WT, PYTHONPATH на worktree)
   Set-Location $WT
   # все 28 скриптов примеров без подмены формулы → probes/stdout/impl/ (~25 мин; можно в фоне)
   & $PY -u "$P\examples_stdout.py" impl
   Select-String -Path "$P\stdout\impl\*.txt" -Pattern "пакеты:" | Select-Object -First 1   # оба пути — в $WT
   & $PY "$P\diff_stdout.py" sqrt impl > "$P\diff_stdout_impl.out.txt"
   # окна останова 16, 17; баланс всех примеров (в т. ч. 18); фронты и ряд 03 по сетке
   & $PY -u "$P\energy_windows.py" 2>$null > "$P\impl_energy_windows.out.txt"
   & $PY -u "$P\energy_all.py" 2>$null > "$P\impl_energy_all.out.txt"
   & $PY -u "$P\fronts.py" 2>$null > "$P\impl_fronts.out.txt"
   ```
   Ожидание: строка `пакеты:` — оба пути в `$WT` (иначе вывод недействителен — скрипты взяли код основного каталога, правило 3 `/implement`); `diff_stdout_impl.out.txt` — «sqrt → impl: скриптов с изменённым выводом: 0» (вывод нового кода побитово равен выводу с подменой при планировании; строки со временем счёта и путями `diff_stdout.py` пропускает); в трёх `impl_*.out.txt` оба столбца каждой строки равны правому столбцу выходов планирования (`energy_windows.out.txt`, `energy_all.out.txt`, `fronts.out.txt`). Пробы после шага 2 подменять нечего — `energy_*` считают один раз (запасной путь при отсутствии `_cell_centers_mass`), `fronts.py` строит обе сетки из граней. Каждая проба печатает `solver:` — путь `$WT`. Расхождение — остановиться и разобрать: значит, код шага 2 считает не то, что подмена.
2. Заменить числа по таблице 4.1.
3. `18_prototype_input/prototype_input.py:358`: комментарий `# все источники — по номеру ячейки, абсцисса — центры нашей сетки` → `# все источники — по номеру ячейки, абсцисса — центры ячеек (у нашей сетки и прототипа одни, DEBT-063)`.

### 4.1. Таблица правок

В ячейках `\|` — экранированная для markdown черта: в файл пишется `|`. «⚠️ смысл» — правка меняет толкование, а не только число (пункт после таблицы).

**Сверка с замкнутым решением (E) и численный фронт (C)**

| Файл | Строка | Было | Станет |
|---|---|---|---|
| `03_standing_corey/README.md` | 68 | `**0.1979 м**` | `**0.1978 м**` |
| ″ | 146 | `8.00 кПа (0.067 % депрессии)` | `7.45 кПа (0.062 % депрессии)` |
| ″ | 147 | `\| $S_g^{max}$ \| 0.08151 \|` | `\| $S_g^{max}$ \| 0.08152 \|` |
| ″ | 148 | `\| 0.1971 \| 0.1979 \| 0.4 % \|` | `\| 0.1971 \| 0.1978 \| 0.4 % \|` |
| ″ | 175 | `= 0.1979\ \text{м}` | `= 0.1978\ \text{м}` |
| ″ | 190 | `= 1.5\cdot10^{-8}\ \text{Па}` | `= 7.5\cdot10^{-9}\ \text{Па}` |
| ″ | 340 (N = 25) | `$1.3\cdot10^{-8}$ \| $2.3\cdot10^{-4}$ \| 0.20214` | `$9.3\cdot10^{-9}$ \| $2.3\cdot10^{-4}$ \| 0.20008` |
| ″ | 341 (N = 50) | `\| 0.19957 \|` | `\| 0.19905 \|` (Дюпюи $3.7\cdot10^{-9}$ — без изменений) |
| ″ | 342 (N = 100) | `$7.4\cdot10^{-9}$ \| $2.2\cdot10^{-3}$ \| 0.19824` | `$1.7\cdot10^{-8}$ \| $2.2\cdot10^{-3}$ \| 0.19811` |
| ″ | 343 (N = 150) | `$1.5\cdot10^{-8}$ \| $1.8\cdot10^{-3}$ \| 0.19790` | `$7.5\cdot10^{-9}$ \| $1.8\cdot10^{-3}$ \| 0.19785` |
| ″ | 344 (N = 200) | `$7.4\cdot10^{-9}$ \| $2.4\cdot10^{-3}$ \| 0.19772` | `$1.3\cdot10^{-8}$ \| $2.4\cdot10^{-3}$ \| 0.19769` |
| ″ | 346 | `$r_b$, $q_o$ и $T(r_w)$ сходятся монотонно, первым порядком:` | `$r_b$, $q_o$ и $T(r_w)$ сходятся монотонно, первым порядком (у $r_b$ — с $N = 50$: приращения 0.00094 и 0.00042 м при удвоениях; на паре 25 → 50 — 0.00103 м):` — ⚠️ смысл |
| `04_table_table/README.md` | 103 | `**2.637 м**` | `**2.630 м**` |
| ″ | 151 | `27.95 кПа (0.233 % депрессии)` | `23.58 кПа (0.197 % депрессии)` |
| ″ | 152 | `\| $S_g^{max}$ \| 0.01468 \|` | `\| $S_g^{max}$ \| 0.01470 \|` |
| ″ | 153 | `\| 2.594 \| 2.637 \| 1.7 % \|` | `\| 2.594 \| 2.630 \| 1.4 % \|` |
| ″ | 321 (N = 25) | `\| 63.9 \| 2.694 \| 351.4966 \|` | `\| 46.3 \| 2.666 \| 351.4966 \|` |
| ″ | 322 (N = 50) | `\| 28.0 \| 2.637 \| 351.4915 \|` | `\| 23.6 \| 2.630 \| 351.4915 \|` |
| ″ | 323 (N = 100) | `\| 13.1 \| 2.614 \| 351.4888 \|` | `\| 12.0 \| 2.612 \| 351.4884 \|` (T — давнее расхождение, раздел 1) |
| ″ | 324 (N = 150) | `\| 8.5 \| 2.606 \| 351.4877 \|` | `\| 8.0 \| 2.606 \| 351.4872 \|` (то же) |
| ″ | 328–329 | `0.0051 и 0.0027 К при удвоениях` | `0.0051 и 0.0031 К при удвоениях` |
| `04_table_table/grid_convergence.py` | 17–20 | столбец «макс\|dp\|»: `63.9`, `28.0`, `13.1`, `8.5` | `46.3`, `23.6`, `12.0`, `8.0` (выравнивание столбца сохранить) |
| ″ | 27–29 | `(2.694 -> 2.637 -> 2.614 ->` / `приращения 0.0051 и 0.0027 К при` / `замер 2026-09-29` | `(2.666 -> 2.630 -> 2.612 ->` / `приращения 0.0051 и 0.0031 К при` / `замер 2026-10-11, DEBT-063` |
| `04a_high_gas_saturation/README.md` | 176 | `1.508 м расчёт` | `1.507 м расчёт` |
| ″ | 215 | `35.9 кПа (0.224 % депрессии)` | `35.0 кПа (0.218 % депрессии)` |
| ″ | 217 | `\| 1.476 \| 1.508 \| 2.1 % \|` | `\| 1.476 \| 1.507 \| 2.1 % \|` |
| `05_standing_table_rp/README.md` | 60 | `\| 0.2039 м \|` | `\| 0.2034 м \|` |
| ″ | 103 | `0.20390 м vs 0.20390 м (0.00 %)` | `0.20337 м vs 0.20337 м (0.00 %)` |
| ″ | 105 | `= 3.7\times10^{-9}$ Па` | `= 1.3\times10^{-8}$ Па` |
| ″ | 106 | `отн. разность $2.3\times10^{-15}$` | `отн. разность $9.7\times10^{-16}$` |
| `05_standing_table_rp/closed_form_convergence.py` | 5–6 | `по давлению —` / `16 кПа.` | `по давлению —` / `11 кПа.` |
| `06_table_corey_rp/README.md` | 58 | `\| 2.49 м \|` | `\| 2.48 м \|` |
| `07_degassing_adiabatic_only/README.md` | 52 | `\| фронт $r_b$ \| 2.64 м \|` | `\| фронт $r_b$ \| 2.63 м \|` |
| `09_degassing_latent_heat/README.md` | 43 | `\| фронт $r_b$ \| 2.64 м \|` | `\| фронт $r_b$ \| 2.63 м \|` |
| ″ | 60 | `$r < r_b = 2.64$ м` | `$r < r_b = 2.63$ м` |
| `10_deep_degassing/README.md` | 52 | `\| $r_b$, м \| 3.58 \|` | `\| $r_b$, м \| 3.57 \|` |
| ″ | 60 | `$r_b = 3.58$ м` | `$r_b = 3.57$ м` |
| `12_large_drainage_radius/README.md` | 146 | `63 кПа (0.67 % депрессии)` | `59 кПа (0.62 % депрессии)` |
| `13a_pwf_ramp_down/README.md` | 160 | `59.00 кПа (0.621 % депрессии 9.5 МПа)` | `54.76 кПа (0.576 % депрессии 9.5 МПа)` |
| `15_oil_rate_ramp_up/README.md` | 223 | `463.97 кПа (5.21 % депрессии 8.9 МПа)` | `458.12 кПа (5.14 % депрессии 8.9 МПа)` |
| `README.md` (сводный) | ~425 | `464 кПа (5.2 % депрессии)` | `458 кПа (5.1 % депрессии)` |
| ″ | ~739 | `фронт — 0.20 против 2.64 м` | `фронт — 0.20 против 2.63 м` |
| `02_single_phase_jt/README.md` | 91 | `\| 0.0036 К \| 0.0034 К \| 0.0032 К \|` | `\| 0.0035 К \| 0.0033 К \| 0.0031 К \|` |

**Радиусы центров ячеек**

| Файл | Строка | Было | Станет |
|---|---|---|---|
| `11_degassing_at_boundary/README.md` | 7 | `$r_{N-1} = 47.11$ м` | `$r_{N-1} = 46.99$ м` |
| `12_large_drainage_radius/README.md`, `13a_pwf_ramp_down/README.md`, `13b_pwf_alternating/README.md`, `15_oil_rate_ramp_up/README.md`, `16_well_shut_in/README.md` | 52, 50, 54, 56, 58 | `центр 186.08 м` | `центр 185.36 м` |
| `12_large_drainage_radius/README.md` | 112 | `(117.9 м)` | `(117.5 м)` |
| ″ | 162 | `Ячейка с центром 117.9 м лежит сразу за стационарным фронтом (117.6 м).` | `Ячейка с центром 117.5 м лежит у стационарного фронта (117.6 м), в 0.1 м внутри него.` — ⚠️ смысл |
| `13a_pwf_ramp_down/README.md` | 118 | `до 117.9 м (14.5 сут)` | `до 117.5 м (14.5 сут)` |
| `13b_pwf_alternating/README.md` | 151 | `от 0.9 до 75 м` | `от 0.9 до 74 м` |
| ″ | 181 | `0.9–75 м` | `0.9–74 м` |
| `README.md` (сводный) | ~521 | `0.9–75 м нефть недонасыщена` | `0.9–74 м нефть недонасыщена` |
| `numerical_solver/tests/test_examples.py` | 1642 | `ячейки (186.08 м) лежит` | `ячейки (185.36 м) лежит` |
| ″ | 2230 | `30 ячеек на 0.9-75 м` | `30 ячеек на 0.9-74 м` |

**Радиусы центров в столбцах таблиц** (добавлено аудитом 1). Столбец «фронт, м» временных таблиц 12, 13a, 15 и «газ до, м» в 18 — центр последней ячейки с газом. Точные подстроки «было → станет» (соседняя ячейка слева или вся строка таблицы, каждая — уникальна в файле) — `vault/issues/debt-063/probes/table_radii_pairs.out.txt` (31 пара; столбцы: файл, строка, было, станет, число вхождений = 1):

| Файл | Таблица, строки | Строка таблицы (первый столбец «сут»): было → станет |
|---|---|---|
| `12_large_drainage_radius/README.md` | «Две стадии…» — по суткам, `:63–73`, столбец «фронт, м» | 1: 87.0 → 86.7; 2: 101.3 → 100.9; 3, 4, 5, 6, 7, 10, 12: 117.9 → 117.5; 13, 15: 101.3 → 100.9 |
| `13a_pwf_ramp_down/README.md` | по суткам, `:83–90`, «фронт, м» | 3: 35.0 → 34.8; 5: 55.1 → 54.9; 7: 74.7 → 74.5; 10: 87.0 → 86.7; 12, 14: 101.3 → 100.9; 14.5, 15: 117.9 → 117.5 |
| `15_oil_rate_ramp_up/README.md` | по суткам, `:103–110`, «фронт, м» | 3: 12.1 → 12.0; 5: 35.0 → 34.8; 7: 55.1 → 54.9; 9: 74.7 → 74.5; 10: 87.0 → 86.7; 12, 14, 15: 101.3 → 100.9 |
| `18_prototype_input/README.md` | «Ожидаемое поведение», `:143–150`, «газ до, м» | 1 сут: 1.89 → 1.88; 5 сут и 5 сут + 1 мин: 3.06 → 3.05; 30 сут: 14.97 → 14.96 |

Остальные строки этих столбцов (0.24, 1.89 в 13a и т. п.) при печатаемой точности не меняются.

**Баланс энергии**

| Файл | Строка | Было | Станет |
|---|---|---|---|
| `12_large_drainage_radius/README.md` | 101–102 | `$7.6\cdot10^{-16}$; кондуктивный член` / `$E_{конд} = +6.16\cdot10^{6}$ Дж.` | `$4.5\cdot10^{-17}$; кондуктивный член` / `$E_{конд} = +5.85\cdot10^{6}$ Дж.` |
| `13a_pwf_ramp_down/README.md` | 112 | `$4.1\cdot10^{-16}$; кондуктивный член $E_{конд} = +3.63\cdot10^{6}$ Дж.` | `$1.0\cdot10^{-16}$; кондуктивный член $E_{конд} = +3.45\cdot10^{6}$ Дж.` |
| `13b_pwf_alternating/README.md` | 116 | `\| $-3.0636\cdot10^{10}$ \| $-3.0045` … `\| $+9.17\cdot10^{6}$ \|` | `\| $-3.0637\cdot10^{10}$ \| $-3.0045` … `\| $+8.70\cdot10^{6}$ \|` (остальные столбцы — без изменений) |
| `14_high_gor_cooling/README.md` | 98 | `$1.8\cdot10^{-17}$` | `$2.9\cdot10^{-16}$` |
| ″ | 136 | `$-9.98\cdot10^{8}$` | `$-9.92\cdot10^{8}$` |
| `15_oil_rate_ramp_up/README.md` | 133 | `$5.4\cdot10^{-16}$` | `$1.6\cdot10^{-16}$` |
| `16_well_shut_in/README.md` | 144 | `\| $+2.0\cdot10^{5}$ \| $-6.3\cdot10^{5}$ \|` | `\| $+1.9\cdot10^{5}$ \| $-6.0\cdot10^{5}$ \|` |
| `17_shut_in_strong_cooling/README.md` | 157 | `\| $+5.7\cdot10^{5}$ \| $-6.1\cdot10^{6}$ \|` | `\| $+5.7\cdot10^{5}$ \| $-6.0\cdot10^{6}$ \|` |
| `18_prototype_input/README.md` | 166 | `$+5.1\cdot10^{6}$ Дж; невязка $3.6\cdot10^{-15}$` | `$+5.0\cdot10^{6}$ Дж; невязка $4.9\cdot10^{-15}$` |
| `19_rs150_cooling/README.md` | 137 | `$+8.68\cdot10^{6}$` | `$+8.62\cdot10^{6}$` |
| `20_rs300_cooling/README.md` | 153 | `$+8.7806\cdot10^{6}$` | `$+8.7306\cdot10^{6}$` |
| `21_rs100_cooling/README.md` | 137 | `$+7.28\cdot10^{6}$` | `$+7.23\cdot10^{6}$` |
| `README.md` (сводный), таблица баланса энергии (~570–582) | строки **10**…**21**, столбцы «невязка» и «теплопроводность» | 10: `$5.7\cdot10^{-16}$ \| $+1.36\cdot10^{6}$`; 11: `$4.6\cdot10^{-17}$ \| $+1.53\cdot10^{6}$`; 12: `$7.6\cdot10^{-16}$ \| $+6.16\cdot10^{6}$`; 13a: `$4.1\cdot10^{-16}$ \| $+3.63\cdot10^{6}$`; 13b: `$1.4\cdot10^{-15}$ \| $+9.17\cdot10^{6}$`; 14: `$1.8\cdot10^{-17}$ \| $-9.98\cdot10^{8}$`; 15: `$5.4\cdot10^{-16}$ \| $+3.03\cdot10^{6}$`; 16: `$1.8\cdot10^{-15}$ \| $+5.53\cdot10^{6}$`; 17: `$3.4\cdot10^{-15}$ \| $+6.86\cdot10^{6}$`; 18: `$3.6\cdot10^{-15}$ \| $+5.14\cdot10^{6}$`; 19: `$5.0\cdot10^{-17}$ \| $+8.68\cdot10^{6}$`; 20: `$5.6\cdot10^{-17}$ \| $+8.78\cdot10^{6}$`; 21: `$4.5\cdot10^{-17}$ \| $+7.28\cdot10^{6}$` | 10: `$4.1\cdot10^{-16}$ \| $+1.31\cdot10^{6}$`; 11: `$9.1\cdot10^{-17}$ \| $+1.47\cdot10^{6}$`; 12: `$4.5\cdot10^{-17}$ \| $+5.85\cdot10^{6}$`; 13a: `$1.0\cdot10^{-16}$ \| $+3.45\cdot10^{6}$`; 13b: `$1.8\cdot10^{-15}$ \| $+8.70\cdot10^{6}$`; 14: `$2.9\cdot10^{-16}$ \| $-9.92\cdot10^{8}$`; 15: `$1.6\cdot10^{-16}$ \| $+2.88\cdot10^{6}$`; 16: `$4.4\cdot10^{-15}$ \| $+5.25\cdot10^{6}$`; 17: `$2.5\cdot10^{-15}$ \| $+6.78\cdot10^{6}$`; 18: `$4.9\cdot10^{-15}$ \| $+5.02\cdot10^{6}$`; 19: `0` \| `$+8.62\cdot10^{6}$`; 20: невязка без изменений \| `$+8.73\cdot10^{6}$`; 21: `$9.0\cdot10^{-17}$ \| $+7.23\cdot10^{6}$` |

**⚠️ Правки со сменой смысла:**
- **README 12, абзац «Недонасыщенная нефть у фронта»** (`:162`). Прежде ячейка (центр 117.9 м) лежала «сразу за» стационарным фронтом (117.58 м). На самом деле прототип считает её давление в точке 117.5 м — **в 0.08 м внутри** фронта. Расчёт не меняется (гидродинамика побитово та же): на 3–12 сут ячейка двухфазна, с 13 сут $S_g = 0$ при $p < p_b$ — недонасыщенная нефть. Меняется только толкование положения ячейки; остальной текст абзаца (`:163–174`) верен и правки не требует. Слово «за фронтом» в `:171` («ячейка за фронтом попадает в строку…») заменить на «ячейка у фронта».
- **README 03, `:346`** — первый порядок у $r_b$ на новых данных виден с $N = 50$; на грубой паре 25 → 50 приращение почти то же, что на 50 → 100. Прежнюю «правильную» картину давала добавка разницы центров ($\propto h^2$).

**Проверка после шага:**
1. Все замены сделаны, и только они (из `$WT`, переменные «Как начать», п. 4):
   ```powershell
   Set-Location $WT
   & $PY "$P\table41_check.py" after      # ожидание: «пар: 104 + строк сводной таблицы: 13; нарушений: 0 (после шага 4)»
   & $PY "$P\readme_radii.py"             # ожидание: пусто — в README нет радиусов центров прежней формулы
   git -C $ROOT diff --stat -- numerical_solver/examples numerical_solver/tests/test_examples.py
   ```
   `table41_check.py` до шага 4 (основной каталог, аудит 1) — «нарушений: 0 (до шага 4)»: каждое «было» встречается ровно один раз, «станет» — ни разу. `readme_radii.py` сравнивает числа README с центрами **прежней** формулы (вычисляет её сам, от кода сетки не зависит), поэтому после правок — пусто.
2. `& $PY -m pytest tests/test_examples.py -m "not slow" -q` — проверки README (разделы, имена) зелёные.
- **Регресс:** быстрый.

**Оценка:** 104 замены + 13 строк сводной таблицы, ~2 ч (из них ~25 мин — перезапуск скриптов для сверки).

## Шаг 5. Заметки vault

**Цель:** заметки описывают одну сетку.

**Файлы** (`vault/knowledge/decisions/`, в worktree): `словарь-код-физика.md`, `модули-grid-сетка.md`, `hydro-prototype-анализ.md`, `P8-формат-ввода-json.md`, `порядок-реализации-модулей.md`.

**Что сделать** (по тексту):

| Файл | Место (`d7528d4`) | Правка |
|---|---|---|
| `словарь-код-физика.md` | `:30` | `` | `r_centers[j]` \| r_j (центр масс кольца) \| `eq:cell_center` \| [N] \| `` → `` | `r_centers[j]` \| r_j = √(r_{j-1/2}·r_{j+1/2}) — середина ячейки по ln r, как у прототипа \| `eq:cell_center` \| [N] \| `` |
| `модули-grid-сетка.md` | раздел «Центры ячеек» `:90–102` | Заголовок → `### Центры ячеек (`eq:cell_center`)`; формула → `r_j = √(r_{j-1/2} · r_{j+1/2})` (середина по ln r); абзац смысла → «Те же центры у RadialGrid прототипа (DEBT-063): одна сетка для гидродинамики, энергии и вывода. Профиль Дюпюи воспроизводится в центрах точно при любом центре (логарифмическая проводимость грани). До DEBT-063 — exp⟨ln r⟩ по площади слоя (в заметках ошибочно «центр масс», DEBT-060); замер точности обоих центров — `vault/issues/debt-063/probes/center_accuracy.py`.»; плашку ⚠️ DEBT-060/063 и абзац «Численная особенность» (ветка x → 1 — её больше нет) удалить; фразу «x = const … вычислить один раз» удалить. |
| `модули-grid-сетка.md` | раздел «Задача: согласование с прототипом» `:163–172` | Заменить на: «**Решено DEBT-063** (2026-10-11, [#98](https://github.com/ArturSalamatin/Oil_Gas/issues/98)): `LogRadialGrid` берёт центры прототипа √ (вариант A1), сетки совпадают побитово — `test_prototype_adapter.py::TestGridsMatchPrototype`. Задача 1 (√ → другая формула в прототипе) отменена; задача 2 (передать единый Grid в прототип) не нужна. Подробности: [[P8-формат-ввода-json]].» |
| `hydro-prototype-анализ.md` | `:210` | `(√ vs наш центр масс)` → `(с DEBT-063 центры совпадают, √)`; «**частично** — те же формулы, но центры ячеек отличаются» → «**да** — формулы и центры совпадают (DEBT-063)» |
| `hydro-prototype-анализ.md` | `:223–227` | `:223` → «Наша постановка до DEBT-063 (`eq:cell_center`): exp⟨ln r⟩ по площади слоя (ошибочно названная «центр масс», DEBT-060).»; после `:227` добавить «**Принято DEBT-063** (2026-10-11): сетка прототипа (√) — для GPN тоже.» |
| `P8-формат-ввода-json.md` | `:283–285` | → «Центры ячеек — среднее геометрическое граней √(r_{j-1/2}·r_{j+1/2}), как у прототипа (problem_statement.tex, `eq:cell_center`; DEBT-063). До DEBT-063 GPN брал exp⟨ln r⟩ по площади слоя.» Строку «**Задача:** изменить формулу центров в прототипе…» удалить. |
| `P8-формат-ввода-json.md` | `:293` | «Centers расходятся (формулы разные). Задача по согласованию зарегистрирована.» → «Centers совпадают побитово (DEBT-063, тест `TestGridsMatchPrototype`).» |
| `P8-формат-ввода-json.md` | `:297–309` («Зарегистрированные задачи») | Под заголовком каждой TASK — строка: первой «**Отменена DEBT-063:** формулы согласованы в обратную сторону — GPN на √ прототипа.»; второй «**Не нужна (DEBT-063):** две сетки с одинаковыми гранями и центрами, совпадение проверяет тест.» Текст задач не удалять (история). |
| `порядок-реализации-модулей.md` | `:170–171` | `:170` → «- ~~Изменить формулу центров ячеек в прототипе~~ — решено обратным путём: GPN на центры прототипа √ (DEBT-063)»; `:171` → «- ~~Передача единого Grid в прототип~~ — не нужна (DEBT-063: сетки совпадают побитово)» |

В ячейках таблицы `\|` — экранированная для markdown черта: в файл пишется `|`.

**Проверка после шага:**
```powershell
Set-Location $ROOT
git grep -n -E "[Цц]ентр\w*.{0,20}масс|_cell_centers_mass|TestCenterMassVerification|взвешенное" -- numerical_solver vault/knowledge/decisions
```
Ожидание: в `numerical_solver/` — пусто; в `vault/knowledge/decisions/` — три строки-«история»: по одной в `модули-grid-сетка.md` и `hydro-prototype-анализ.md` (новый текст с пометкой DEBT-060) и `P8-формат-ввода-json.md` — текст отменённой TASK («Нужно: заменить на центр масс кольца…», сохраняется как история, см. таблицу выше).
- **Регресс:** — (только vault).

**Оценка:** ~20 строк, ~20 мин.

## Шаг 6. Итог

1. Полный прогон: `Set-Location $WT; & $PY -m pytest tests/ -q` — все passed, база + 4 (~10 мин).
2. `git -C $ROOT diff --stat $BASE` — файлы шагов 1–5 и vault задачи; кода прототипа нет.
3. Длина новых строк `.py` ≤ 100: `git -C $ROOT diff -U0 $BASE -- "*.py" | Select-String '^\+[^+]' | Where-Object { $_.Line.Length -gt 101 }` — пусто.
4. Grep шага 5.
5. Vault задачи: реестр (статус DEBT-063; DEBT-060 уже закрыта), frontmatter плана, `vault/issues/debt-063/05-comment-done.md` + комментарий в #98.

**Регресс:** полный.

## 5. Тестовая стратегия

| Тест | Файл | Что проверяет | Ожидание |
|---|---|---|---|
| `TestGridsMatchPrototype::test_same_cells` ×3 (новый) | `test_prototype_adapter.py` | грани, центры, объёмы `LogRadialGrid` и `RadialGrid` — одни ячейки | побитово; **предотвращает** возврат двух сеток при правке любой из формул |
| `TestCellCenterGeometricMean::test_log_midpoint_property` (заменяет `test_log_average_property`) | `test_grid.py` | `eq:cell_center` по граням, независимо от кода | atol 1e-13 по $\ln r$ |
| `TestCellCenterGeometricMean::test_equal_log_weights` (новый) | `test_grid.py` | следствие для `eq:face_interp` | rtol 1e-12 |
| `TestSmallGridValues::*` (эталон $N = 3$ — $\sqrt{0.5}$) | `test_grid.py` | центры и проводимости малой сетки | rtol 1e-12, как было |
| `test_pressure_log_profile` | `test_val001.py` | решение прототипа = Дюпюи в общих центрах | rtol 1e-12 (было 1e-2) |
| `test_standing_dupuit_pressure` | `test_factory_standing_hydro.py` | то же на `baseline.json` | rtol 1e-12 (было 1e-2) |
| `TestMassBalance::test_oil_balance` | `test_prototype_adapter.py` | баланс нефти адаптера | atol 1e-6 (было 0.02) |
| остальные | все | гидродинамика побитово, $T$ — на $\le 10^{-5}$ К | быстрый уровень и полный прогон зелёные (проба: вне `test_grid.py` — зелёные) |

## 6. Критерии завершения

- [ ] Шаги 0–6, коммиты по точкам «Как начать», п. 6.
- [ ] Полный прогон зелёный; тестов база + 4.
- [ ] `LogRadialGrid.r_centers` побитово = `RadialGrid.centers_m` (тест).
- [ ] PDF: ошибок и неопределённых ссылок как в базе; раздел «Радиальная сетка» просмотрен; выходы сборки удалены.
- [ ] Числа таблицы 4.1 заменены: `table41_check.py after` — 0 нарушений, `readme_radii.py` — пусто; вывод нового кода совпадает с выводом подмены при планировании: `diff_stdout.py sqrt impl` — 0 скриптов с изменённым выводом, `impl_energy_*.out.txt`, `impl_fronts.out.txt` — равны правому столбцу выходов планирования.
- [ ] Grep шага 5 — по ожиданию.
- [ ] Vault, issue #98 — комментарий; закрывается при влитии.

## 7. Обнаруженные проблемы

1. **Ложные объяснения допусков в трёх тестах** (`test_val001`, `test_factory_standing_hydro`, `TestMassBalance`) — включены (шаг 3).
2. **Опубликованные числа примеров** (сверки с аналитикой, фронты, радиусы центров, член теплопроводности, таблицы сходимости) содержали систематическую составляющую от разницы точек или от граничной проводимости энергии — исправляются в шаге 4 (таблица 4.1). Наблюдаемый порядок по давлению в 05 — 0.926 вместо 1.160: прежнее значение — артефакт.
3. **Давние расхождения README с выводом, не от DEBT-063** (раздел 1): $T(r_w)$ при $N$ = 100, 150 в таблице сходимости 04 (исправляются попутно — строки переписываются из вывода целиком) и невязка 06 в сводной таблице баланса энергии ($1.2\cdot10^{-15}$ против $1.1\cdot10^{-15}$ — не трогать). README примеров тестами на числа не проверяются — числа устаревают незаметно; регистрировать ли задачу — решение пользователя.
4. **Предупреждение pytest** `PytestRemovedIn10Warning` в `test_val002.py::TestCaseC_MeshConvergence` (фикстура класса — метод экземпляра) — вне задачи; при следующем обновлении pytest станет ошибкой. Регистрировать — решение пользователя.

## Связанные заметки

- [[известные баги и технический долг]] — DEBT-063, DEBT-060
- [[debt-060 cell-center-name]] — отменённый план (замеры раздела 1 на `7309f67`)
- [[модули-grid-сетка]], [[словарь-код-физика]], [[P8-формат-ввода-json]], [[hydro-prototype-анализ]], [[порядок-реализации-модулей]]
- Issue: [#98](https://github.com/ArturSalamatin/Oil_Gas/issues/98), [#96](https://github.com/ArturSalamatin/Oil_Gas/issues/96)
