---
tags:
  - план
  - рефакторинг
date: 2026-10-10
issue: DEBT-060
github: 96
branch: refactor/debt-060/cell-center-name
status: отменён — поглощён DEBT-063 (2026-10-10)
---

# DEBT-060: центр ячейки — «среднее геометрическое радиуса по площади слоя», не «центр масс»

> ⛔ **План отменён 2026-10-10, не реализовывать.** Решение пользователя: по [[DEBT-063]] выбран вариант A — GPN переходит на центры прототипа $\sqrt{r_{j-1/2}r_{j+1/2}}$, формула $\exp\langle\ln r\rangle$ уходит вместе с названием «центр масс». DEBT-060 поглощена DEBT-063. Из этого плана в DEBT-063 переходят: замеры раздела 1 (вхождения, проба `val001_centers.py`, сборка `.tex`), находки по тестам (`test_val001`, `test_flux_exact_for_any_N`, `TestMassBalance` — раздел 7) и проба `ast_same_renamed.py` как образец. Шаги 1–5 ниже описывают $\exp\langle\ln r\rangle$ и к DEBT-063 неприменимы.

## Кратко

- **Дефект.** Центр ячейки радиальной сетки называют «центром масс кольцевого слоя» в постановке `numerical_solver/doc/problem_statement.tex`, в докстрингах `grid/log_radial.py`, в тестах и в пяти заметках vault. Формула `eq:cell_center` даёт другую точку: $\ln r_j = \langle\ln r\rangle$ по площади слоя, то есть $r_j = \exp\langle\ln r\rangle$ — **среднее геометрическое радиуса по площади слоя**. Центр масс $\langle r\rangle$ — другая величина: кольцо 1–2 м — 1.528 против 1.556. Сама формула выбрана правильно (в $r_j$ логарифмический профиль равен своему среднему по ячейке); неверно только название.
- **Попутно** (решения пользователя, раздел 0):
  - докстринг `test_flux_exact_for_any_N` приписывает центру свойство, которое от выбора центра не зависит;
  - `tests/test_val001.py::TestDupuitPressure::test_pressure_log_profile` сравнивает давление прототипа с эталоном **в центрах `LogRadialGrid`**, хотя прототип считает давление в своих центрах $\sqrt{r_{j-1/2}r_{j+1/2}}$. Расхождение 8.5e-4 целиком из-за разницы точек, а комментарий теста объясняет его «нестационарностью»; допуск 1e-2 при заявленной в шапке файла метрике 1e-12. В центрах прототипа совпадение — до округления (проба `val001_centers.py`, раздел 1).
- **Что делается:** название в `.tex` (+ формула определения `eq:cell_center_def` и смысл), докстринги и два имени в коде (`_cell_centers_mass` → `_cell_centers_log_average`, `TestCenterMassVerification` → `TestCellCenterLogAverage`), комментарии тестов, 11 строк в 5 заметках vault; `test_val001` — эталон в центрах прототипа, `rtol=1e-12`.
- **Расчёт не меняется.** В `log_radial.py`, `test_grid.py`, `test_prototype_adapter.py` логика та же с точностью до переименования — это доказывает проба `ast_same_renamed.py` (AST без докстрингов с возвратом старых имён совпадает с базой). Меняется логика одного теста (`test_val001.py`), и это намеренно.
- **Шагов:** 7 (0 — подготовка, 6 — итог). Файлов: 1 `.tex`, 1 модуль ядра, 3 теста, 5 заметок vault. Число тестов не меняется.
- **Оценка:** ~1.5 ч, из них ~10 мин — полный прогон и ~3 мин — сборка PDF.

## 0. Решения пользователя (2026-10-10)

1. **Название:** «среднее геометрическое радиуса по площади (кольцевого) слоя»; физический смысл — отдельной фразой. Не «среднелогарифмический»: так называют $(b-a)/\ln(b/a)$, другую величину. Не «радиус среднего давления»: свойство у любой величины, линейной по $\ln r$.
2. **Имена в коде:** переименовать оба — `_cell_centers_mass` → `_cell_centers_log_average`, `TestCenterMassVerification` → `TestCellCenterLogAverage`.
3. **Заметки vault:** все 5 (11 строк). В этих же строках «eq. 12» → `eq:cell_center`. Прочие номера уравнений в этих заметках **не трогать** — по решению DEBT-010 заметки времени до реализации исторические.
4. **Постановка:** вывод + смысл. Формула определения $\ln r_j = \int r\ln r\,dr / \int r\,dr$ с меткой, фраза о смысле, отличие от центра масс и от $\sqrt{r_{j-1/2}r_{j+1/2}}$. Неточное «логарифмически взвешенное среднее граней» убрать.
5. **`test_val001`:** исправление включить в DEBT-060 (те же строки): эталон в центрах прототипа, `rtol=1e-12`, комментарий по факту.

## Как начать работу по этому плану

1. Прочитай этот файл целиком, затем запись DEBT-060 в [[известные баги и технический долг]] и issue #96 (`gh issue view 96 --repo ArturSalamatin/Oil_Gas`).
2. Материалы задачи, которые `/implement` коммитит в базовую ветку до создания worktree: этот план, `vault/issues/debt-060/` (тело issue, комментарии, пробы), реестр техдолга и `vault/knowledge/decisions/модули-grid-сетка.md`. В последний `/issue` добавил строку `> ⚠️ Название неверно … DEBT-060 …` — шаг 5 её убирает; без коммита в базу её в worktree не будет, а при влитии в основном каталоге останется незакоммиченная правка того же файла.
3. Ветка от базовой — в worktree:
   ```powershell
   git worktree add .worktrees/debt-060 -b refactor/debt-060/cell-center-name numerical_scheme/implementation
   ```
4. Переменные (PowerShell). В worktree `.venv` нет — берётся интерпретатор основного каталога. pytest из worktree берёт пакет worktree; пробы печатают путь к пакету (`SOLVER = Path.cwd()`), запускать их из каталога worktree (`reference_worktree_pythonpath`):
   ```powershell
   $PY   = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   $P    = "D:\Lessons\Grants\2026\GPN\Oil_Gas\vault\issues\debt-060\probes"   # скрипты и выходы проб — в основном каталоге
   $ROOT = "D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\debt-060"             # корень worktree (git и проба AST)
   $WT   = "$ROOT\numerical_solver"                                            # отсюда pytest
   $BASE = git -C $ROOT merge-base refactor/debt-060/cell-center-name numerical_scheme/implementation
   ```
5. **Прототип `HydroSolverPrototype/` план не трогает** — тесты и регрессия прототипа не нужны.
6. Точки коммитов (на ветке задачи; формат — CLAUDE.md, «Коммиты»; stage по имени файла; vault — отдельно от кода):
   - после шага 1 — `docs: problem_statement — центр ячейки как среднее геометрическое радиуса по площади слоя (DEBT-060)`: `numerical_solver/doc/problem_statement.tex`;
   - после шага 3 — `refactor: центр ячейки — имена и докстринги без «центра масс» (DEBT-060)`: `gpn_multiphase_solver/grid/log_radial.py`, `tests/test_grid.py`, `tests/test_prototype_adapter.py`;
   - после шага 4 — `test: VAL-001 — давление прототипа сверяется в его центрах, rtol 1e-12 (DEBT-060)`: `tests/test_val001.py`;
   - после шага 5 — `vault: центр ячейки — среднее геометрическое по площади слоя в заметках (DEBT-060)`: 5 заметок;
   - шаг 6 — vault задачи (реестр, план, пробы), как требует `/implement`.

   До шага 1 не коммитить шаги 2–3: новый докстринг ссылается на метку `eq:cell_center_def`, и без неё тест-сторож DEBT-010 красный.

## Порядок влития

План написан на `7309f67` (после влития DEBT-010 и начала VAL-004): тестов 1679, в быстром уровне 1417. Номера строк ниже — на `7309f67`; после чужих влитий они сдвинутся — **править по тексту (`Edit` по уникальной подстроке), не по номеру**.

| Задача | Состояние на 2026-10-10 | Пересечение |
|---|---|---|
| **VAL-004** (#90) — сходимость по $\Delta t$ на останове | реализуется (`.worktrees/val-004`) | Новый `tests/test_val004.py`; затрагиваемых здесь файлов не трогает. Число тестов после её влития вырастет — записывать фактическую базу шага 0. |
| **DEBT-008** (#89) — мёртвые поля конфига | план готов | Правит `P8-формат-ввода-json.md` (§ про поля конфига, `dt_min`/`dt_max`, `p_ref`) — другие разделы, не «Центры ячеек» (`:281–303`). Конфликт возможен только по соседству строк; разрешать по тексту. |
| **DEBT-048**, **BUG-024** — прототип, ступень 4 | планы готовы | Файлы не пересекаются. |
| **DEBT-059** (#94) — прототип устанавливаемым пакетом | план готов | Может изменить подключение прототипа в `tests/conftest.py`; ссылка на `radial_blackoil/grid.py` в новом комментарии `test_val001.py` останется верной (имя модуля прототипа не меняется). |

## 1. Замеры при планировании (`7309f67`)

- **Тесты:** 1679 собрано, быстрый уровень 1417 (`-m "not slow"`). Затрагиваемые тесты все в быстром уровне: `test_val001.py::TestDupuitPressure::test_pressure_log_profile`, `test_grid.py::TestCenterMassVerification::test_log_average_property`, `test_grid.py::TestStationaryRate::test_flux_exact_for_any_N`, `test_prototype_adapter.py::TestMassBalance::test_oil_balance`.
- **Вхождения «центр масс»** (grep `[Цц]ентр\w*.{0,20}масс`):
  - `numerical_solver/` — 8: `doc/problem_statement.tex:938`; `gpn_multiphase_solver/grid/log_radial.py:12, 26, 29`; `tests/test_grid.py:76, 191, 306`; `tests/test_prototype_adapter.py:578`; `tests/test_val001.py:89`. Плюс идентификаторы: `_cell_centers_mass` (`log_radial.py:11`, единственный вызов `:64`), `TestCenterMassVerification` (`test_grid.py:308`). Вне этих строк имена нигде не встречаются (grep по репозиторию без `.venv`: только реестр и материалы issue). `HydroSolverPrototype/`, `examples/`, README — без вхождений.
  - `vault/knowledge/decisions/` — 11 строк: `словарь-код-физика.md:30`; `модули-grid-сетка.md:96, 165, 167`; `hydro-prototype-анализ.md:210, 223, 225`; `P8-формат-ввода-json.md:283, 285, 301`; `порядок-реализации-модулей.md:170`. Плюс строка-предупреждение `модули-grid-сетка.md:98`, добавленная `/issue`. Ещё одно совпадение — `literature/Mitchell Myers 2010 — HBIM и RIM для задач Стефана.md:83` («центр масс» распределения) — о другом, не трогать. Исторические планы (`vault/plans/feat-012-…:303`, `debt-010 …`) и записи реестра — документы своего времени, не правятся.
- **Проверка формулы** (численно, `_cell_centers_mass` на `b3ffaac`): кольцо 1–2 м — $\exp\langle\ln r\rangle$ = 1.528361, $\langle r\rangle$ = 1.555556, $\sqrt{1\cdot 2}$ = 1.414214. Сетка $r_w = 0.1$, $R = 500$, $N = 10$: центр масс больше на 2.54 % во всех ячейках.
- **Вывод `eq:cell_center` из определения.** $\int_a^b r\ln r\,dr = \bigl[\tfrac{r^2}{2}\ln r - \tfrac{r^2}{4}\bigr]_a^b$, $\int_a^b r\,dr = \tfrac{b^2-a^2}{2}$, откуда $\ln r_j = \dfrac{b^2\ln b - a^2\ln a}{b^2-a^2} - \dfrac12$. С $x = a^2/b^2$: $\ln r_j = \ln b + \tfrac12\bigl(-\tfrac{x\ln x}{1-x} - 1\bigr)$ — это `eq:cell_center`. Численно то же проверяет `TestCenterMassVerification::test_log_average_property` (rel 1e-12).
- **`test_flux_exact_for_any_N` от центра не зависит.** При $p = A + B\ln r$ и $T_w = 2\pi kh/\ln(r_0/r_w)$ поток $T_w(p_0 - p_{wf})/\mu = 2\pi kh B/\mu$ при любом $r_0 > r_w$. Тест проверяет проводимость грани, а не центр.
- **Проба `val001_centers.py`** (`vault/issues/debt-060/probes/`, выход `val001_centers.out.txt`, VAL-001: $N = 20$, $r_w = 0.1$, $R = 50$, 24 шага по 1 ч):

  | Сравнение | max отн. отклонение |
  |---|---|
  | $p$ прототипа против эталона в центрах `LogRadialGrid` (как в тесте сейчас) | 8.498e-4 |
  | $p$ прототипа против эталона в центрах прототипа $\sqrt{r_{j-1/2}r_{j+1/2}}$ | 0 |
  | эталон в одних центрах против эталона в других | 8.505e-4 |

  При $c_o = 0$ (шапка `test_val001.py`) течение несжимаемое — профиль стационарный на каждом шаге, а двухточечная схема с логарифмической проводимостью грани воспроизводит его в своих центрах точно. Комментарий теста («нестационарное решение за один шаг dt=86400 с») неверен дважды: шаги — 3600 с, нестационарности нет.
- **Масштаб разницы двух сеток.** На логарифмической сетке с шагом $h = \ln(R/r_w)/N$: $\ln(r_j^{\text{GPN}}/r_j^{\text{прот}}) = \tfrac12\bigl(\tfrac{2h}{e^{2h}-1} - 1\bigr) + \tfrac h2 \approx h^2/6$. VAL-001 ($N = 20$) — 1.60 % по $r$; `configs/baseline.json` ($N = 100$, $R/r_w = 500$) — 0.064 %. Внутренние проводимости у обеих сеток совпадают (отношение соседних центров одно и то же), различаются только граничные и логарифмические веса интерполяции.
- **Сборка PDF** (чистая, 3 прохода, `7309f67`): 0 ошибок, 0 неопределённых ссылок, 18 `Overfull \hbox`, 37 страниц. **С правкой шага 1** (проба `tex_check.py` — блоки «До»/«После» берёт из этого плана, собирает копию; выход `tex_check.out.txt`): те же 0 / 0 / 18, 37 страниц; `eq:log_grid` — (37), `eq:cell_center_def` — (38), `eq:cell_center` — (39), все на с. 14; страница просмотрена глазами. Вариант с `\mbox{$p = A + B\ln r$}` (против переноса после «=») дал 19-й Overfull — отклонён, перенос после знака отношения штатен для TeX.
- **Строки кода плана** (проба `plan_lines_check.py`, выход `plan_lines_check.out.txt`): 79 строк в ```python-блоках, максимум 93 символа; запрещённых форм ссылок нет; все метки (`eq:cell_center`, `eq:cell_center_def`) объявлены в `.tex` или в блоке шага 1; все 7 блоков «До» найдены в файлах дословно, каждый ровно один раз. ⚠️ Сборка с `-output-directory` из `numerical_solver/doc/` основного каталога читает устаревший `problem_statement.aux` от 22.09 и даёт 7 ложных «undefined» (`eq:c_ot`, `eq:bc_rate_pwf`, `eq:bc_pwf_shutin`, `eq:newton_cell_tol` — метки моложе того `.aux`). В worktree `.aux` нет (он в `.gitignore`), сборка там чистая.

## 2. Целевое состояние

- Ни одного «центр масс» о центре ячейки в `numerical_solver/` и `vault/knowledge/decisions/`; имена `_cell_centers_mass`, `TestCenterMassVerification` нигде не встречаются.
- `problem_statement.tex`: определение $\ln r_j = \int r\ln r\,dr/\int r\,dr$ (`eq:cell_center_def`), смысл, замкнутая форма `eq:cell_center` без изменений, отличие от $\langle r\rangle$ и $\sqrt{r_{j-1/2}r_{j+1/2}}$. PDF собирается: 0 ошибок, 0 неопределённых ссылок.
- `log_radial.py`, `test_grid.py`, `test_prototype_adapter.py` — AST без докстрингов совпадает с базой с точностью до двух переименований.
- `test_val001::test_pressure_log_profile` — эталон в центрах прототипа, `rtol=1e-12`, комментарий по факту.
- Число тестов то же; быстрый уровень и полный прогон зелёные.

### Связь формула → код

| Формула (`problem_statement.tex`) | Код | Тест |
|---|---|---|
| `eq:cell_center_def` (новая): $\ln r_j = \int r\ln r\,dr/\int r\,dr$ | `grid/log_radial.py::_cell_centers_log_average` (докстринг) | `test_grid.py::TestCellCenterLogAverage::test_log_average_property` |
| `eq:cell_center`: $r_j = r_{j+1/2}\sqrt{\exp(-x\ln x/(1-x) - 1)}$ | `_cell_centers_log_average` (тело без изменений) | `test_grid.py::TestSmallGridValues::test_centers` |

## 3. Варианты

1. **Только тексты** (A из issue #96): название в `.tex`, докстрингах, комментариях и заметках; имена `_cell_centers_mass`, `TestCenterMassVerification` остаются. Риск нулевой, но имя `mass` в коде продолжает противоречить формуле.
2. **Тексты + два имени** (B, выбран): плюс переименование приватной функции (один вызов) и класса тестов. Идентификаторы pytest для одного теста меняются (`--lf` после переименования его не найдёт — безвредно); внешних ссылок на имена нет (grep).
3. **Сменить формулу на центр масс** — отклонён: `eq:cell_center` — верный выбор для метода конечных объёмов на логарифмическом профиле; центр масс сломал бы `test_log_average_property` и изменил бы все истории. Задача — о названии.

`test_val001` (решение 5) не зависит от выбора: давление считает прототип, его центры — $\sqrt{r_{j-1/2}r_{j+1/2}}$ при любом названии наших.

## 4. Подводные камни

- ✅ **Все места вызова:** `_cell_centers_mass` — единственный вызов `log_radial.py:64`; `TestCenterMassVerification` — только определение. Grep по репозиторию (без `.venv`) — больше нигде, кроме реестра и материалов issue.
- ✅ **Обратная совместимость API:** обе сущности приватные (функция модуля с `_`, класс тестов). `LogRadialGrid` и его свойства не меняются.
- ✅ **Расчёт не меняется:** тело функции не правится; проба `ast_same_renamed.py` доказывает это для всех трёх `.py`, кроме `test_val001.py`, где логика меняется намеренно.
- ⚠️ **Тест-сторож DEBT-010** (`tests/test_eq_references.py`): (а) запрещает ссылки номером («eq. 12», «ур. N», «.tex:N») в `.py` ядра, тестов и примеров — в новых текстах только `eq:<метка>`; (б) каждая метка из `.py` должна быть объявлена в `.tex`. Новый докстринг ссылается на `eq:cell_center_def` — **шаг 1 (метка в `.tex`) раньше шагов 2–3**, иначе сторож красный.
- ⚠️ **Нумерация уравнений сдвинется** на +1 после `eq:cell_center_def`. Код и тесты ссылаются метками (сторож DEBT-010), заметки vault с номерами — исторические и уже неверны. Внутри документа — только `\eqref`.
- ⚠️ **Длина строк `.py`** ≤ 100 символов в новых строках (в пакете так принято, DEBT-010 §4). Проверка — шаг 6, п. 4.
- ⚠️ **Устаревший `.aux` в основном каталоге** даёт ложные «undefined» при `-output-directory`. Собирать в `$WT\doc` (там `.aux` нет), три прохода; выходы сборки (`*.aux`, `*.log`, `*.pdf`, `*.toc`, `*.out`) в `.gitignore`, но удалить после проверки, чтобы `git worktree remove` при влитии не споткнулся.
- ⚠️ **`--lf` после переименования:** если `test_log_average_property` падал в прошлом прогоне, `--lf` его под новым именем не найдёт — прогонять файл целиком.
- ⚠️ **Строка-предупреждение `модули-grid-сетка.md:98`** (от `/issue`) — удалить в шаге 5; см. «Как начать», п. 2.
- ⚠️ **Строгий допуск `test_val001`:** `rtol=1e-12` при фактическом 0. Запас — четыре порядка над округлением double (~1e-16 отн.). Если на другой машине выйдет ~1e-15, допуск всё равно проходит.
- ✅ **Конфиги, циклы импортов, состояние при ошибке, производительность:** неприменимо (конфиги и импорты не меняются).
- ✅ **Прототип:** не трогается.
- ✅ **Связь с другими задачами:** раздел «Порядок влития».

## Шаг 0. Подготовка

**Цель:** worktree, базовое состояние, пробы на базе.

**Файлы:** пробы уже лежат в `vault/issues/debt-060/probes/` основного каталога: `ast_same_renamed.py` (проверена на пустом diff — 4 OK; на имитации правок — переименования OK, смена допуска в `test_val001.py` — DIFF), `val001_centers.py` + `.out.txt`, `tex_check.py` + `.out.txt`, `plan_lines_check.py` + `.out.txt` (последние две — проверки плана при планировании, при реализации не нужны).

**Что сделать:**
1. Создать worktree и задать переменные («Как начать», п. 3–4).
2. Базовое состояние из `$WT`:
   ```powershell
   Set-Location $WT
   & $PY -m pytest tests/ --collect-only -q | Select-Object -Last 1
   & $PY -m pytest tests/ -m "not slow" -q | Select-Object -Last 3
   ```
   Ожидание: 1679 собрано, 1417 passed (~70 с), если база не уехала. Если уехала (VAL-004 и др.) — записать фактические числа; план число тестов не меняет.
3. Проба AST на пустом diff:
   ```powershell
   Set-Location $ROOT
   & $PY "$P\ast_same_renamed.py" $BASE numerical_solver/gpn_multiphase_solver/grid/log_radial.py numerical_solver/tests/test_grid.py numerical_solver/tests/test_prototype_adapter.py numerical_solver/tests/test_val001.py
   ```
   Ожидание: 4 OK, `с изменённой логикой: 0`.
4. Базовая сборка PDF в worktree (три прохода — оглавление и `longtable`):
   ```powershell
   Set-Location "$WT\doc"
   1..3 | ForEach-Object { pdflatex -interaction=nonstopmode -halt-on-error problem_statement.tex | Out-Null }
   $log = Get-Content problem_statement.log -Encoding UTF8
   "errors: "    + ($log | Select-String '^!').Count
   "undefined: " + ($log | Select-String 'undefined').Count
   "overfull: "  + ($log | Select-String 'Overfull').Count
   ($log | Select-String 'Output written').Line
   ```
   Ожидание: 0 / 0 / 18, 37 страниц.

**Проверка:** числа записаны. **Регресс:** — (кода нет).

**Оценка:** ~5 мин.

## Шаг 1. Постановка: определение, смысл, название

**Цель:** `problem_statement.tex` называет центр ячейки верно и выводит `eq:cell_center` из определения.

**Файлы:** `numerical_solver/doc/problem_statement.tex` (раздел `ssec:grid`, абзац «Центры ячеек», `:937–951` на `7309f67`).

**Контекст:** сейчас абзац называет $r_j$ «центром масс кольцевого слоя (логарифмически взвешенным средним граней)». Оба названия неверны: центр масс — $\langle r\rangle$, а $\ln r_j$ — не взвешенное среднее $\ln r_{j\pm1/2}$ (веса $b^2/(b^2-a^2)$ и $-a^2/(b^2-a^2)$, один отрицательный, плюс постоянная $-1/2$). Решения пользователя 1 и 4.

**Изменения (старый → новый текст):**

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
--- среднее геометрическое радиуса по~площади кольцевого слоя:
логарифм центра равен среднему значению~$\ln r$ по~площади слоя,
\begin{equation}\label{eq:cell_center_def}
  \ln r_j
  = \frac{\displaystyle\int_{r_{j-\half}}^{r_{j+\half}} r\ln r\,dr}
         {\displaystyle\int_{r_{j-\half}}^{r_{j+\half}} r\,dr}.
\end{equation}
Поэтому любая величина, линейная по~$\ln r$, --- стационарный
профиль давления $p = A + B\ln r$, температура при~чистой
теплопроводности --- в~точке~$r_j$ равна своему среднему
по~объёму ячейки: значения в~центрах, по~которым считаются
потоки, согласованы со~средними по~объёму в~членах накопления.
Интегралы берутся в~замкнутом виде; для всех ячеек
($j = 0, 1, \ldots, N-1$):
\begin{equation}\label{eq:cell_center}
  r_j = r_{j+\half}\,
  \sqrt{\exp\!\left(
    -\frac{x\ln x}{1 - x} - 1
  \right)},
  \qquad
  x = \left(\frac{r_{j-\half}}{r_{j+\half}}\right)^2.
\end{equation}
Это не~центр масс кольца
$\langle r\rangle = \tfrac{2}{3}\,
(r_{j+\half}^3 - r_{j-\half}^3)/(r_{j+\half}^2 - r_{j-\half}^2)$
и~не~среднее геометрическое граней
$\sqrt{r_{j-\half}\,r_{j+\half}}$: для кольца $1 \le r \le 2$~м
эти три точки~--- $1{,}528$, $1{,}556$ и~$1{,}414$~м.
Центры граничных ячеек ($j = 0$ и~$j = N{-}1$) определяются
```

Тело `eq:cell_center` не меняется. Остаток абзаца («…по~той же формуле, что и~внутренние…») — без изменений.

**Проверка после шага:**
1. Сборка — команда шага 0, п. 4. Ожидание (проба `tex_check.py`): 0 ошибок, 0 неопределённых ссылок, 18 `Overfull`, 37 страниц.
2. Глазами: прочитать с. 14 PDF (`Read` по `$WT\doc\problem_statement.pdf`, `pages: "14"`). Уравнения (37) `eq:log_grid`, (38) `eq:cell_center_def`, (39) `eq:cell_center` подряд; числа 1,528 / 1,556 / 1,414 в абзаце после (39). Перенос строки после «=» в $p = A + B\ln r$ допустим.
3. `& $PY -m pytest tests/test_eq_references.py -q` из `$WT` — 2 passed (метки целы).
4. Удалить выходы сборки: `Remove-Item "$WT\doc\problem_statement.aux","$WT\doc\problem_statement.log","$WT\doc\problem_statement.pdf","$WT\doc\problem_statement.toc","$WT\doc\problem_statement.out" -ErrorAction SilentlyContinue` (перед этим п. 2).
- **Регресс:** `--collect-only -q` (только документ) — 1679.

**Зависимости:** блокирует шаги 2–3 (метка `eq:cell_center_def`).

**Оценка:** ~20 строк, ~15 мин.

## Шаг 2. `log_radial.py`: имя функции и докстринги

**Цель:** в ядре нет «центра масс», функция названа по формуле.

**Файлы:** `numerical_solver/gpn_multiphase_solver/grid/log_radial.py` (`:11–15`, `:25–29`, `:64`).

**Контекст:** `_cell_centers_mass` — приватная функция модуля, единственный вызов в конструкторе `LogRadialGrid`. Тело не меняется (решение 2).

**Изменения:**

До (`:11–15`):
```python
def _cell_centers_mass(r_left: np.ndarray, r_right: np.ndarray) -> np.ndarray:
    """Центры масс кольцевых слоёв (vectorized). Ур. (eq:cell_center) problem_statement.tex.

    r_j = r_right * sqrt(exp(-x*ln(x)/(1-x) - 1)),  x = (r_left/r_right)^2
    """
```
После:
```python
def _cell_centers_log_average(r_left: np.ndarray, r_right: np.ndarray) -> np.ndarray:
    """Центры ячеек — среднее геометрическое радиуса по площади слоя (vectorized).

    ln r_j = ∫ r·ln r dr / ∫ r dr — Ур. (eq:cell_center_def) problem_statement.tex;
    в замкнутом виде, Ур. (eq:cell_center):
    r_j = r_right * sqrt(exp(-x*ln(x)/(1-x) - 1)),  x = (r_left/r_right)^2
    """
```

До (`:25–29`):
```python
    """Логарифмическая радиальная сетка с центрами масс.

    Грани: geomspace(r_well, R_ext, N+1).
    Центры: центр масс кольцевого слоя (eq:cell_center).
```
После:
```python
    """Логарифмическая радиальная сетка.

    Грани: geomspace(r_well, R_ext, N+1).
    Центры: среднее геометрическое радиуса по площади слоя (eq:cell_center).
```

До (`:64`): `        self._r_centers = _cell_centers_mass(`
После: `        self._r_centers = _cell_centers_log_average(`

**Проверка после шага:**
1. `& $PY -m pytest tests/test_grid.py tests/test_eq_references.py -q` из `$WT` — все passed (в `test_grid.py` 78 тестов + 2 сторожа).
2. `Set-Location $ROOT; & $PY "$P\ast_same_renamed.py" $BASE numerical_solver/gpn_multiphase_solver/grid/log_radial.py` — OK.
- **Регресс:** быстрый (меняется имя в коде ядра).

**Зависимости:** требует шаг 1.

**Оценка:** ~10 строк, ~5 мин.

## Шаг 3. Тесты сетки и адаптера: тексты, имя класса

**Цель:** тесты не называют центр «центром масс» и не приписывают ему чужих свойств.

**Файлы:** `numerical_solver/tests/test_grid.py` (`:76–81`, `:190–191`, `:306–309`), `numerical_solver/tests/test_prototype_adapter.py` (`:577–579`).

**Контекст:** (1) комментарий к эталону $N = 3$ называет формулу «центром масс», и два промежуточных числа в нём неточны: $e^{-0.5379} = 0.58397$ (в комментарии 0.58388), $\sqrt{\cdot} = 0.76418$ (0.76413) — тест считает эталон кодом (`_factor`, `:89`), комментарий на него не влияет. (2) `test_flux_exact_for_any_N` — точность от центра не зависит (раздел 1). (3) Класс `TestCenterMassVerification` проверяет как раз определение `eq:cell_center_def` — верно по сути, неверно по имени.

> ⚠️ **Не применять правку `test_prototype_adapter.py` ниже до решения пользователя** (раздел 7, п. 4): докстринг `TestMassBalance` объясняет допуск разницей центров, а фактическая невязка — 5.5e-12, центры в баланс не входят.

**Изменения:**

`test_grid.py`, до (`:76–81`):
```python
# Центр масс: r_j = r_R · sqrt(exp(-0.25·ln(0.25)/(1-0.25) - 1))
#           = r_R · sqrt(exp(-0.25·(-1.3863)/0.75 - 1))
#           = r_R · sqrt(exp(0.4621 - 1))
#           = r_R · sqrt(exp(-0.5379))
#           = r_R · sqrt(0.58388)
#           = r_R · 0.76413
```
после:
```python
# Центр ячейки — среднее геометрическое радиуса по площади слоя (eq:cell_center):
# r_j = r_R · sqrt(exp(-0.25·ln(0.25)/(1-0.25) - 1))
#     = r_R · sqrt(exp(-0.25·(-1.3863)/0.75 - 1))
#     = r_R · sqrt(exp(0.4621 - 1))
#     = r_R · sqrt(exp(-0.5379))
#     = r_R · sqrt(0.58397)
#     = r_R · 0.76418
```

`test_grid.py`, до (`:190–191`):
```python
    def test_flux_exact_for_any_N(self):
        """Центр масс кольца точен для логарифмического профиля при любом N."""
```
после:
```python
    def test_flux_exact_for_any_N(self):
        """Забойный поток на логарифмическом профиле точен при любом N."""
        # Точность — свойство проводимости грани 2πkh/ln(r_0/r_w), а не выбора
        # центра: при p = A + B·ln r поток T·(p_0 − p_wf)/μ = 2πkh·B/μ не зависит
        # от r_0. Сам центр ячейки проверяет TestCellCenterLogAverage.
```

`test_grid.py`, до (`:306–309`):
```python
# ── Центр масс: независимая верификация ───────────────────────

class TestCenterMassVerification:
    """Проверка: r_center — точка, где <ln(r)>_volume = ln(r_center)."""
```
после (разделитель — 64 символа, как соседние):
```python
# ── Центр ячейки: независимая верификация ─────────────────────

class TestCellCenterLogAverage:
    """Проверка: r_center — точка, где <ln(r)>_volume = ln(r_center) (eq:cell_center_def)."""
```

`test_prototype_adapter.py`, до (`:577–579`):
```python
    Допуск ~2% из-за разных центров ячеек:
    наш Grid — центр масс кольца (eq:cell_center), прототип — √(r_i·r_{i+1}).
    Проводимости расходятся → потоки немного разные.
```
после:
```python
    Допуск ~2% из-за разных центров ячеек:
    наш Grid — среднее геометрическое радиуса по площади слоя (eq:cell_center),
    прототип — среднее геометрическое граней √(r_i·r_{i+1}).
    Проводимости расходятся → потоки немного разные.
```

**Проверка после шага:**
1. `& $PY -m pytest tests/test_grid.py tests/test_prototype_adapter.py tests/test_eq_references.py -q` из `$WT` — все passed.
2. `& $PY -m pytest tests/ --collect-only -q | Select-Object -Last 1` — число как в шаге 0.
3. `& $PY -m pytest "tests/test_grid.py::TestCellCenterLogAverage" -q` — 1 passed (новое имя собирается).
4. `Set-Location $ROOT; & $PY "$P\ast_same_renamed.py" $BASE numerical_solver/gpn_multiphase_solver/grid/log_radial.py numerical_solver/tests/test_grid.py numerical_solver/tests/test_prototype_adapter.py` — 3 OK.
- **Регресс:** по п. 1–2 (меняются только тексты и имя класса тестов; быстрый уровень — в шаге 4).

**Зависимости:** требует шаг 1 (метки в комментариях).

**Оценка:** ~20 строк, ~10 мин.

## Шаг 4. VAL-001: давление прототипа — в его центрах

**Цель:** тест давления VAL-001 сверяет решение там, где его считает прототип, с заявленной в шапке точностью.

**Файлы:** `numerical_solver/tests/test_val001.py` (`:88–95`).

**Контекст:** решение 5; проба `val001_centers.py` (раздел 1). Грани у `LogRadialGrid` и у `RadialGrid` прототипа совпадают (обе — `np.geomspace(r_w, R_ext, N+1)`: `log_radial.py:57`, `radial_blackoil/grid.py:9`), центры прототипа — `np.sqrt(faces[:-1]*faces[1:])` (`radial_blackoil/grid.py:10`). Тест строит эталон из граней нашей сетки — так он не зависит от приватных полей адаптера.

**Изменения:**

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
        """p(r_j) = p_wf + Δp·ln(r_j/rw)/ln(R/rw) в центрах ячеек прототипа."""
        sim, history = _run_val001()
        # Давление считает прототип — в своих центрах, среднем геометрическом
        # граней √(r_{j-1/2}·r_{j+1/2}) (radial_blackoil/grid.py, centers_m).
        # Грани у него и у LogRadialGrid общие (geomspace с теми же r_w, R_ext,
        # N), центры разные: в центрах LogRadialGrid (eq:cell_center) эталон
        # отличался бы на 8.5e-4 — разница точек при N = 20, не ошибка решения
        # (DEBT-060, проба vault/issues/debt-060/probes/val001_centers.py).
        # При c_o = 0 течение несжимаемое: профиль стационарный на каждом шаге,
        # и двухточечная схема с проводимостью 2πkh/ln(r_{j+1}/r_j)
        # воспроизводит его в своих центрах до округления.
        faces = sim._grid.r_faces
        r = np.sqrt(faces[:-1] * faces[1:])
        p_exact = P_WF + (P_EXT - P_WF) * np.log(r / R_WELL) / np.log(R_EXT / R_WELL)
        np.testing.assert_allclose(history.states[-1].p, p_exact, rtol=1e-12)
```

**Проверка после шага:**
1. `& $PY -m pytest tests/test_val001.py -q` из `$WT` — все passed.
2. Проба из worktree (берёт пакет worktree, печатает путь): `Set-Location $WT; & $PY "$P\val001_centers.py"` — `solver:` указывает на `$WT`; числа как в `val001_centers.out.txt` (8.498e-04 / 0 / 8.505e-04). Подтверждает, что новый тест различает точки: при старом эталоне `rtol=1e-12` упал бы на 8.5e-4.
3. `Set-Location $ROOT; & $PY "$P\ast_same_renamed.py" $BASE numerical_solver/tests/test_val001.py` — **DIFF** (логика теста изменена намеренно).
- **Регресс:** быстрый — `& $PY -m pytest tests/ -m "not slow" -q`, ожидание — как в шаге 0, все passed.

**Зависимости:** требует шаг 0.

**Оценка:** ~15 строк, ~10 мин.

## Шаг 5. Заметки vault

**Цель:** действующие и исторические заметки называют центр верно (решение 3).

**Файлы** (`vault/knowledge/decisions/`, правки в worktree): `словарь-код-физика.md`, `модули-grid-сетка.md`, `hydro-prototype-анализ.md`, `P8-формат-ввода-json.md`, `порядок-реализации-модулей.md`.

**Что сделать** (замены по тексту; «eq. 12» меняется только в этих строках):

| Файл | Строка (`7309f67`) | До | После |
|---|---|---|---|
| `словарь-код-физика.md` | 30 | `` | `r_centers[j]` \| r_j (центр масс кольца) \| `eq:cell_center` \| [N] \| `` | `` | `r_centers[j]` \| r_j — среднее геометрическое радиуса по площади слоя, ln r_j = ⟨ln r⟩ \| `eq:cell_center_def`, `eq:cell_center` \| [N] \| `` |
| `модули-grid-сетка.md` | 96 | `Это центр масс кольцевого слоя — точка, в которой давление при логарифмическом профиле совпадает со средним по объёму.` | `Это среднее геометрическое радиуса по площади кольцевого слоя: ln r_j = ∫ r·ln r dr / ∫ r dr (`eq:cell_center_def`) — точка, в которой давление при логарифмическом профиле совпадает со средним по объёму. Не центр масс ⟨r⟩: кольцо 1–2 м — 1.528 против 1.556 (DEBT-060, [#96](https://github.com/ArturSalamatin/Oil_Gas/issues/96)).` |
| `модули-grid-сетка.md` | 97–98 | пустая строка и `> ⚠️ Название неверно: … — DEBT-060. **GitHub issue:** [#96](…)` (добавлена `/issue`) | удалить обе строки |
| `модули-grid-сетка.md` | 165 | `… Наша формула — центр масс кольца (eq. 12). Зарегистрированы задачи:` | `… Наша формула — среднее геометрическое радиуса по площади слоя (`eq:cell_center`). Зарегистрированы задачи:` |
| `модули-grid-сетка.md` | 167 | `1. Изменить формулу центров в прототипе (√ → центр масс) — приоритет средний` | `1. Изменить формулу центров в прототипе (√ → среднее геометрическое по площади слоя) — приоритет средний` |
| `модули-grid-сетка.md` | 170 | `Временное решение: два Grid (наш + прототипа) с одинаковыми rw, re, N. Faces совпадают, centers расходятся.` | та же строка + ` Расхождение — второго порядка по шагу h = ln(R_ext/r_w)/N: ln(r_j/r_j^прот) ≈ h²/6 — 1.6 % по r при N = 20 (VAL-001), 0.064 % при N = 100; внутренние проводимости совпадают, различаются граничные и веса интерполяции. Давление прототипа в выводе отнесено к центрам LogRadialGrid (DEBT-060, проба `vault/issues/debt-060/probes/val001_centers.py`; согласование сеток — DEBT-063).` |
| `hydro-prototype-анализ.md` | 210 | `(√ vs наш центр масс)` | `(√ vs наше среднее геометрическое по площади слоя)` |
| `hydro-prototype-анализ.md` | 223 | `Наша постановка (problem_statement.tex, eq. 12): центр масс кольца — более сложная формула.` | `Наша постановка (problem_statement.tex, `eq:cell_center`): среднее геометрическое радиуса по площади кольцевого слоя — более сложная формула.` |
| `hydro-prototype-анализ.md` | 225 | `… использовать сетку прототипа (геометрическое среднее) или нашу (центр масс)?` | `… использовать сетку прототипа (среднее геометрическое граней) или нашу (среднее геометрическое по площади слоя)?` |
| `P8-формат-ввода-json.md` | 283 | `Используем формулу центра масс кольца из problem_statement.tex (eq. 12).` | `Используем среднее геометрическое радиуса по площади кольцевого слоя из problem_statement.tex (`eq:cell_center`).` |
| `P8-формат-ввода-json.md` | 285 | `**Задача:** изменить формулу центров в прототипе на центр масс кольца.` | `**Задача:** изменить формулу центров в прототипе на среднее геометрическое радиуса по площади слоя.` |
| `P8-формат-ввода-json.md` | 301 | `Нужно: заменить на центр масс кольца (problem_statement.tex eq. 12).` | `Нужно: заменить на среднее геометрическое радиуса по площади слоя (problem_statement.tex, `eq:cell_center`).` |
| `порядок-реализации-модулей.md` | 170 | `(√ → центр масс кольца eq. 12)` | `(√ → среднее геометрическое радиуса по площади слоя, `eq:cell_center`)` |

В ячейках таблицы `\|` — экранированная для markdown вертикальная черта: в файл пишется `|`. Остаток строк (текст до и после замены) — без изменений. Заголовок `### Центры ячеек (eq. 12)` (`модули-grid-сетка.md:90`) и прочие номера в этих заметках не трогать (решение 3).

**Проверка после шага:**
```powershell
Set-Location $ROOT
git grep -n -E "[Цц]ентр\w*.{0,20}масс|_cell_centers_mass|TestCenterMassVerification" -- numerical_solver vault/knowledge/decisions
```
Ожидание: пусто. (`literature/Mitchell Myers 2010 …` вне пути поиска — там «центр масс» распределения, о другом.)
- **Регресс:** — (только vault).

**Оценка:** 13 строк, ~15 мин.

## Шаг 6. Итог

**Цель:** полный прогон, итоговые проверки, vault задачи.

**Что сделать:**
1. Полный прогон: `Set-Location $WT; & $PY -m pytest tests/ -q` — все passed, число — как в шаге 0 (~10 мин).
2. Проба AST по всем изменённым `.py`:
   ```powershell
   Set-Location $ROOT
   & $PY "$P\ast_same_renamed.py" $BASE numerical_solver/gpn_multiphase_solver/grid/log_radial.py numerical_solver/tests/test_grid.py numerical_solver/tests/test_prototype_adapter.py numerical_solver/tests/test_val001.py
   ```
   Ожидание: 3 OK, `test_val001.py` — DIFF (`с изменённой логикой: 1`). Выход сохранить в `$P\ast_same_renamed.out.txt`.
3. `git -C $ROOT diff --stat $BASE` — изменены ровно 10 файлов: `problem_statement.tex`, `log_radial.py`, `test_grid.py`, `test_prototype_adapter.py`, `test_val001.py`, 5 заметок vault (плюс vault задачи шага 6).
4. Длина новых строк `.py`:
   ```powershell
   Set-Location $ROOT
   git diff -U0 $BASE -- "*.py" | Select-String '^\+[^+]' | Where-Object { $_.Line.Length -gt 101 }
   ```
   Ожидание: пусто (101 — с ведущим `+`).
5. Grep шага 5 — пусто.
6. Vault задачи: реестр (статус DEBT-060, итоги), frontmatter плана (`status: реализован`), `vault/issues/debt-060/05-comment-done.md` + комментарий в issue #96 — как требует `/implement`.

**Регресс:** полный (п. 1).

## 5. Тестовая стратегия

| Тест | Файл | Что проверяет | Ожидание |
|---|---|---|---|
| `TestCellCenterLogAverage::test_log_average_property` (переименован) | `tests/test_grid.py` | $\ln r_j$ = среднее $\ln r$ по площади — определение `eq:cell_center_def` | rel 1e-12, как было |
| `TestSmallGridValues::test_centers` | `tests/test_grid.py` | эталон `eq:cell_center` для $N = 3$ | rtol 1e-12, как было |
| `TestDupuitPressure::test_pressure_log_profile` (изменён) | `tests/test_val001.py` | давление прототипа на VAL-001 — профиль Дюпюи в центрах прототипа | `rtol=1e-12` (было `1e-2`); факт — 0 |
| `test_no_numeric_equation_or_line_references`, `test_label_references_exist_in_problem_statement` | `tests/test_eq_references.py` | новые ссылки — метками; `eq:cell_center_def` объявлена | 2 passed |
| остальные | все | поведение не изменилось | быстрый уровень и полный прогон зелёные |

Новых тестов нет: задача о названии; переименованный тест уже проверяет определение, которое теперь записано в `.tex`. **Предотвращает:** возврат «центра масс» не ловится тестом (это текст), но `test_val001` с `rtol=1e-12` ловит любую будущую подмену точек сравнения (например, обратный переход на `r_centers` нашей сетки).

## 6. Критерии завершения

- [ ] Шаги 0–6 выполнены, коммиты по точкам «Как начать», п. 6.
- [ ] Быстрый уровень и полный прогон зелёные; число тестов не изменилось.
- [ ] `ast_same_renamed.py`: `log_radial.py`, `test_grid.py`, `test_prototype_adapter.py` — OK; `test_val001.py` — DIFF.
- [ ] `test_val001::test_pressure_log_profile` — `rtol=1e-12`, эталон в центрах прототипа.
- [ ] PDF: 0 ошибок, 0 неопределённых ссылок; раздел «Радиальная сетка» проверен глазами; выходы сборки удалены.
- [ ] Grep шага 5 пуст.
- [ ] Vault: реестр, план, заметки; issue #96 прокомментирован, закрывается при влитии.

## 7. Обнаруженные проблемы

1. **`test_val001::test_pressure_log_profile` — не та точка сравнения и допуск 1e-2** — включено в задачу (решение 5, шаг 4).
2. **Неточные числа в комментарии `test_grid.py:80–81`** (0.58388, 0.76413 вместо 0.58397, 0.76418) — исправляются в шаге 3.
3. **Две сетки: давление прототипа в выводе и энергия — на центрах `LogRadialGrid`** — зарегистрировано как [[DEBT-063]] (решение пользователя 2026-10-10). Проба DEBT-063 `center_accuracy.py`: ни один центр не точнее равномерно (дебит в нестационаре точнее у $\sqrt{\cdot}$, среднее по ячейке — у $\exp\langle\ln r\rangle$, оба второго порядка). ⚠️ Если DEBT-063 выберет вариант A (GPN на центры прототипа), абзац шага 1 о среднем геометрическом по площади и `eq:cell_center_def` будут заменены — направление DEBT-063 лучше решить до `/implement` этого плана. В строке шага 5 для `модули-grid-сетка.md:170` сослаться также на DEBT-063.
4. **`TestMassBalance` (`test_prototype_adapter.py:575–580`): объяснение допуска неверно** (проба DEBT-063 `adapter_balance.py`). Баланс в тесте собран из объёмов ячеек (у двух сеток совпадают) и потоков $G_o$ прототипа — центры в него не входят; фактическая невязка — 5.5e-12 при `atol=0.02`. Шаг 3 сейчас переписывает этот докстринг, сохраняя неверное «Допуск ~2% из-за разных центров… Проводимости расходятся». **Решение пользователя ждёт:** по аналогии с `test_val001` (решение 5) — исправить докстринг по факту и ужесточить допуск в шаге 3; либо только убрать «центр масс», а исправление вынести отдельно.
5. **Устаревший `numerical_solver/doc/problem_statement.aux` в основном каталоге** (22.09) даёт ложные «undefined» при сборке с `-output-directory`. Не дефект документа; учтено в подводных камнях.

## Связанные заметки

- [[известные баги и технический долг]] — DEBT-060
- [[модули-grid-сетка]], [[словарь-код-физика]], [[P8-формат-ввода-json]], [[hydro-prototype-анализ]], [[порядок-реализации-модулей]]
- [[debt-010 docstring-eq-labels]] — где обнаружено; тест-сторож меток
- Issue: [#96](https://github.com/ArturSalamatin/Oil_Gas/issues/96)
