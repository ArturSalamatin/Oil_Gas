---
tags:
  - план
  - рефакторинг
date: 2026-10-14
issue: DEBT-070
github: 119
branch: refactor/debt-070/statement-boundary-notation
status: реализован
worktree: .worktrees/debt-070; удалён после влития
merged: e0b7fe0 (2026-10-15)
audit:
  date: 2026-10-15
  found: 7
  auto-fixed: 7
  manual-required: 0
---

# DEBT-070: обозначения на границах в постановке — $p_0$, $T_0$ и индексы граней

## Кратко

- **Дефект.** В `numerical_solver/doc/problem_statement.tex` два конфликта обозначений на границах области:
  1. макросы `\ppl`, `\Tpl` (начальные и контурные давление и температура) печатаются как $p_0$, $T_0$ — теми же символами, что значения **ячейки 0** в `ssec:bc_disc`. В PDF рядом стоят «$p|_{R_{ext}} = p_0$» (контур) и «$p_0 \ge p_{wf}$» (ячейка 0);
  2. индексы граней — в трёх соглашениях. В балансах, `eq:cell_center`, `eq:volume`, `eq:energy_conv_face`, `eq:QJT_disc`, `eq:tridiag_*` ячейка $j$ лежит между гранями $j \mp \tfrac12$, забой — грань $-\tfrac12$. В `eq:log_grid` и `ssec:bc_disc` забой — грань $\tfrac12$, контур — $N + \tfrac12$. Отсюда два настоящих противоречия: `eq:cell_center` при $j = 0$ требует неопределённую $r_{-1/2}$, а $\mathcal{T}_{1/2}$ — это и проводимость грани между ячейками 0 и 1 (`eq:transmissibility`), и забойной грани (`ssec:bc_disc`).
- **Что делается** (решения пользователя 2026-10-14, раздел 0):
  - **одно соглашение по граням:** ячейки $j = 0, \ldots, N-1$, ячейка $j$ — между гранями $j - \tfrac12$ и $j + \tfrac12$; забой — грань $-\tfrac12$, контур — грань $N - \tfrac12$; в коде грань $j - \tfrac12$ имеет номер $f = j$;
  - **начальные и контурные значения — $p_{\text{пл}}$, $T_{\text{пл}}$** (правка двух макросов); $p_0$, $T_0$ остаются за ячейкой 0, как любые $p_j$, $T_j$;
  - словарь CLAUDE.md дополняется строкой про $p_{\text{пл}}$ в постановке.
- **Логика решателя не меняется.** В `.py` меняются только комментарии и докстринги (3 теста, 2 модуля ядра). Метки `\label{}` и номера уравнений не меняются. Числа, истории и графики те же. Прототип `HydroSolverPrototype/` не затрагивается.
- **Объём:** `problem_statement.tex` — 44 правки (T1–T44), код/тесты/README — 13 (C1–C13), vault и CLAUDE.md — 17 (V1–V17). Число тестов не меняется: **1987**, быстрый уровень **1711**. PDF: 40 страниц, `Overfull` 19 → **17** (два переполнения `ssec:bc_disc` уходят попутно, T32/T33/T38).
- **Шагов:** 8 (0 — подготовка, 7 — итог). **Оценка:** ~1.5 ч, из них ~10 мин — итоговый полный прогон, ~20 мин — вычитка PDF.

## 0. Решения пользователя (2026-10-14)

1. **Нумерация граней — ячейки с 0, грани $j \mp \tfrac12$.** Отклонены:
   - именованные граничные грани («заб», «конт») поверх индексов — у каждой величины было бы два имени;
   - ячейки с 1 (учебная запись $\tfrac12 \ldots N + \tfrac12$) — сдвиг на единицу между постановкой и кодом во всём словаре, «ячейка 0» кода = «ячейка 1» текста.
2. **Начальные и контурные значения — $p_{\text{пл}}$, $T_{\text{пл}}$** через макросы `\ppl`, `\Tpl`. Отклонены: $p_{\text{конт}}$/$T_{\text{конт}}$ при начальных $p_0$/$T_0$ (символ $p_0$ сохранил бы два смысла в документе) и пометка ячейки 0 ($p_{(0)}$; ломает единообразие $p_j$).
3. **Словарь CLAUDE.md дополнить:** строка $p_0$ получает пояснение «в `problem_statement.tex` — $p_{\text{пл}}$; там $p_0$, $T_0$ — ячейка 0». README примеров не трогаются: там $p_0$, $T_0$ — начальные значения, это согласуется со словарём.

## 1. Текущее состояние (замер на `8c045d7`)

База — `numerical_scheme/implementation` на `8c045d7` (влит DEBT-067). Issue открывался на `24689d0`; между ними `problem_statement.tex` изменён только DEBT-067 (новый абзац около стр. 2296–2320, `sec:time`) — все строки этого плана (15–2083) не сдвинулись, сверено grep.

**Аудит 1 (2026-10-15):** база ушла на `a7b0dc0` — влит DEBT-062 (`aecd1e4`): он поменял `test_energy_matrix_examples.py` (строки 254, 383, 799 — «`eq:bc_props_ext (74)`» без номера, число строк то же), `CLAUDE.md` (раздел «Связь формула → код», строка 262) и добавил 8 тестов в `test_eq_references.py`. Проба плана на `a7b0dc0`: все 74 «До» найдены ровно один раз, итоги те же (ниже), сторож — `10 passed`. Числа baseline ниже — на `a7b0dc0`.

**Baseline:**
- тесты: **1987** (`--collect-only -q`), быстрый уровень **1711** (`-m "not slow" --collect-only -q`: `1711/1987 tests collected (276 deselected)`); `tests/test_eq_references.py` — `10 passed` (на `8c045d7` было 1979 / 1703 / 2 passed);
- PDF (`pdflatex` в `numerical_solver/doc/` основного каталога, где `.aux` уже есть): **40 страниц**, неопределённых ссылок **0**, `LaTeX Warning` **0**, `Overfull \hbox` **19**: 5 — таблица обозначений (75 pt, колонки `lll`, ширина = сумма максимумов по колонкам; задают её строки «сжимаемость насыщенной нефти…» и «коэфф. объёмного теплового расширения нефти…», замер `probes/table_widths.py`), 2 — в `ssec:bc_disc` (3.4 pt в `eq:bc_props_ext`, 6.5 pt на «$Q_{\lambda,1/2} =~0$»), остальные — вне правок.

⚠️ **Сборка:**
- с `-output-directory` в другую папку — ложные неопределённые ссылки: pdflatex читает устаревший `problem_statement.aux` из текущего каталога `numerical_solver/doc/` (проверено при планировании). Собирать в самом `numerical_solver/doc/`: `.aux`, `.log`, `.pdf`, `.toc` в git не попадают (`.gitignore`);
- **на чистом дереве (новый worktree, `.aux` нет) — три прохода.** После второго в логе «Label(s) may have changed», а ширины колонок `longtable` ещё не сошлись: таблица обозначений даёт ложные Overfull 104 pt. После третьего — как в базе.

**Проба плана** (`vault/issues/debt-070/probes/plan_apply.py 8c045d7`, выход `plan_apply.out.txt`): 74 правки, каждая «До» найдена ровно один раз; PDF — 40 страниц, undefined 0, LaTeX Warning 0, Overfull **17** (два переполнения `ssec:bc_disc` ушли); запрещённых шаблонов в `.tex` и заметках vault — 0; `ast` пяти `.py` без докстрингов совпадает с базой, новых строк длиннее 79 нет; сторож меток `2 passed` (на `a7b0dc0` — `10 passed`, остальное то же). Страницы 4–5 (таблица), 14 (`ssec:grid`), 24–28 (`ssec:bc_disc`) просмотрены: $p_{\text{пл}}$, $T_{\text{пл}}$, индексы $-\tfrac12$, $N-\tfrac12$ печатаются верно, неудачных переносов нет (два найденных пробой — «$j +$ / $\tfrac12$» и «$= $ / 0» — устранены в T7 и T38).

### 1.1. Символы $p_0$, $T_0$

- `problem_statement.tex:15, 18`: `\newcommand{\ppl}{p_0}`, `\newcommand{\Tpl}{T_0}`; 47 вхождений `\ppl`/`\Tpl` без определений (таблица обозначений, НУ/ГУ, `eq:porosity`, гидродинамика при $T = \Tpl$, `eq:bc_flux_ext`, `eq:bc_props_ext`, ГУ по температуре, алгоритм).
- Буквально, без макроса: стр. 120 ($R_s^{\text{eq}}(p_0, T_0)$ — начальные), 152 ($\phi_0 = \phi(p_0)$ — начальное), 621 ($R_{s,0} = 500$ — **начальное** газосодержание, записанное как значение ячейки 0).
- Значения ячейки 0 ($p_0$, $T_0$, $S_{g,0}$, $R_{s,0}$, $(\cdot)_0$) — ~26 строк `ssec:bc_disc` (1833–2084). После правки макросов они однозначны и **не меняются**.
- Абзац BUG-015 (1949–1971) обходит коллизию символами $p_{\text{конт}}$, $T_{\text{конт}}$ — третье имя той же величины; после правки макросов заменяется на `\ppl`, `\Tpl`.
- **Не трогаем:** $\phi_0$ — опорная пористость при $p_{\text{пл}}$ (`eq:porosity`, 27 вхождений, в коде `rock.porosity`); пористость ячейки 0 в документе явно нигде не пишется. $R_s^0$ — начальное газосодержание (верхний индекс), $R_{s,0}$ — ячейка 0 (стр. 1876): различимы, оставляем.

### 1.2. Индексы граней

| Где (строки на `8c045d7`) | Забойная грань | Правая грань ячейки 0 | Контурная грань |
|---|---|---|---|
| `eq:log_grid`, 950–954 | $r_{1/2} = r_w$ | — | $r_{N+1/2} = R_{ext}$ |
| `eq:cell_center`, `eq:volume`, балансы, `eq:energy_conv_face`, `eq:QJT_disc`, `eq:tridiag_*` | $-\tfrac12$ (неявно, $j = 0$) | $\tfrac12$ | $N - \tfrac12$ (неявно) |
| `eq:transmissibility`, 1012–1016 | — | $\mathcal{T}_{1/2} = 2\pi hk/\ln(r_1/r_0)$ | — |
| диаг. преобладание, 1778 | — | — | $Q^T_{\lambda,N+1/2}$ и $\Phi^-_N$ в одной скобке |
| `ssec:bc_disc`, 1811–2068 | $\mathcal{T}_{1/2} = 2\pi hk/\ln(r_0/r_w)$, $G_{1/2}$, $\Phi_{1/2}$, $Q_{\lambda,1/2}$ | $G_{3/2}$ (1846), $\Phi^-_{1/2+1}$ (2051) | $\mathcal{T}_{N+1/2}$, $G_{N+1/2}$, $\mathcal{Q}_{N+1/2}$; $\Phi^-_N$ (2026–2030); левая грань ячейки $N-1$ — «$N - \tfrac12$» (2033) |
| случай $N = 1$, 2078–2083 | — | — | $Q^T_{\lambda,1+1/2}$ и $\Phi^-_1$ |
| код, словарь `словарь-код-физика.md` §1, §6 | $f = 0$ | $f = 1$ | $f = N$; $a_j \leftrightarrow$ `−Q_T[j] − Phi_plus[j]`, то есть $j - \tfrac12 \leftrightarrow f = j$ |

Соглашение `ssec:bc_disc` ($\tfrac12$ для забоя) скопировано в комментарии кода, тестов, README и заметки vault:

| Файл | Строки | Что |
|---|---|---|
| `numerical_solver/gpn_multiphase_solver/energy/tridiag.py` | 427–431 | докстринг `compute_jt`: «μ·Φ⁺_{1/2}·(p[0] − p_wf)», «Φ_{1/2} < 0» |
| `numerical_solver/gpn_multiphase_solver/energy/balance.py` | 272 | комментарий «-Φ⁻_N·T_ext» (индекс без скобок — читается как грань постановки) |
| `numerical_solver/tests/test_energy.py` | 1537, 1538, 1575, 1594 | `TestWellPressureSource`: «Φ⁺_{1/2}» для забойной грани |
| `numerical_solver/tests/test_energy_matrix_examples.py` | 256 | «при условиях контура (p_0, T_0, Rs^0)» — $p_0$ в смысле контура |
| то же | 689, 693 | «Q_λ,1/2 = 0», «член грани 1/2» для забоя |
| `numerical_solver/tests/test_rate_control.py` | 12 | «T_{1/2}» в формуле `eq:bc_rate_pwf` |
| `numerical_solver/examples/15_oil_rate_ramp_up/README.md` | 138, 142, 145, 168 | $G^o_{1/2}$, $\mathcal{T}_{1/2}$, $\Phi^+_{1/2}$; **и** $p_0$ = давление ячейки 0 (142, 145), тогда как в том же README $p_0 = 15.5$ МПа — начальное (14, 51, 283) |
| `vault/knowledge/decisions/словарь-код-физика.md` | 29, 32–34, 42 | `r_faces[f]` = «r_{f+1/2} при нумерации ячеек с 1», `trans_well` = T_{1/2}, `trans_ext` = T_{N+1/2}, `trans_internal[f]` = T_{f+1} |
| `vault/knowledge/decisions/модули-grid-сетка.md` | 54, 60, 84–86, 117–118 | то же в архитектурной заметке |
| `vault/knowledge/decisions/свойства-фаз-на-контурной-грани-берутся-из-ГУ-при-притоке.md` | 22–25 | `eq:bc_props_ext` с индексом $N + 1/2$ и $(p_0, T_0, R_s^0)$ |
| `vault/knowledge/numerics/температура ячейки 0 — центр, не забой.md` | 21, 36 | $\Phi^\pm_{1/2}$ для забойной грани |

Остальные `j∓1/2` в коде и тестах (`tridiag.py:23, 416–417, 510–517, 606`, `balance.py:283`, `grid/log_radial.py:15`, `test_energy.py:1245`, `test_grid.py`, `test_energy_matrix_examples.py:276–677`) — относительные индексы ячейки $j$, верны при любом соглашении; **не трогаем**. Код-индексы в квадратных скобках (`Φ⁻[N]`, `Q_T[0]`, `p[0]`) — тоже.

## 2. Целевое состояние

**Правило обозначений после DEBT-070** (одно на постановку, словарь, комментарии):
- ячейки $j = 0, \ldots, N-1$; ячейка $j$ лежит между гранями $j - \tfrac12$ (ближе к скважине) и $j + \tfrac12$;
- забой — грань $-\tfrac12$ ($r_{-1/2} = r_w$), контур — грань $N - \tfrac12$ ($r_{N-1/2} = R_{ext}$);
- в коде грань $j - \tfrac12$ — индекс $f = j$ (массивы граней длины $N + 1$); внутренняя грань между ячейками $f$ и $f+1$ — `trans_internal[f]` = $\mathcal{T}_{f+1/2}$;
- $p_{\text{пл}}$, $T_{\text{пл}}$ — начальные (они же контурные) давление и температура, в коде `InitialConfig.p0`, `.T0` и `BoundaryConditions.p_ext`, `.T_ext`; $R_s^0$ — начальное газосодержание и состав притока (`Rs0`, `Rs_ext`);
- $p_0$, $T_0$, $S_{g,0}$, $R_{s,0}$ — значения в ячейке 0 у забоя.

**Не меняется (зона неприкосновенности):**
- метки `\label{}` и `\ref`/`\eqref`; нумерация уравнений; содержание формул (только индексы и имена величин);
- логика кода, числа, истории, графики, README примеров кроме 15;
- `HydroSolverPrototype/`;
- исторические записи `vault/plans/`, `vault/issues/`, записи реестра других задач (в том числе BUG-029 с $\mathcal{T}_{1/2}$) — это снимки на свою дату.

## 3. Варианты и выбор

Разобраны в issue [#119](https://github.com/ArturSalamatin/Oil_Gas/issues/119) и решены пользователем (раздел 0). Порядок реализации — один: сначала текст постановки (шаги 1–3) и его сборка (шаг 4), затем копии соглашения в коде (шаг 5) и vault (шаг 6). Каждый шаг оставляет дерево согласованным: тесты от текста не зависят, кроме сторожа меток (метки не меняются).

## 4. Подводные камни

| Пункт | Статус | Комментарий |
|---|---|---|
| Все вхождения найдены | ⚠️ | grep по `_{\half}`, `N+\half`, `\half+1`, `1+\half`, `3/2`, `\Phi_{N}`, `\Phi_{1}`, `p_0`, `T_0`, `\text{конт}` в `.tex`; `1/2`, `p_0`, `T_0` в `.py`/`.md` пакета, тестов, примеров, `vault/knowledge`. Проверка после правки — шаг 4 (список запрещённых шаблонов) |
| Зависимости пакетов, import-ы | ✅ | не меняются |
| Обратная совместимость API | ✅ | только тексты |
| Тесты | ✅ | меняются комментарии и докстринги; `ast` модулей без докстрингов совпадает с базой (проба, раздел 5) |
| Сторож ссылок `test_eq_references.py` | ✅ | метки не меняются; новые тексты не содержат «eq. N», «.tex:N», «eq:x (N)» |
| Docstrings: ссылки `eq:` | ✅ | в C1 ссылка `ssec:bc_disc` остаётся |
| Configs | ✅ | имена параметров не меняются (`p0`, `T0` в конфиге остаются) |
| `\text{пл}` в макросе | ✅ | `amsmath` загружен; `\text{ст}`, `\text{конт}` уже используются в формулах документа. Макрос нигде не стоит перед `_`/`^`/`'` (grep `\\(ppl\|Tpl)\s*[_^']` — пусто), двойного индекса не будет |
| Ширина таблицы обозначений (`lll`) | ✅ | уже 75 pt за полем; новые ячейки (T2, T3, T5) уже самых широких — проба: после плана сумма максимумов по колонкам та же, 495.3 pt (`probes/table_widths.py <путь к .tex>`) |
| Переполнения строк в правленых абзацах | ✅ | индекс $N-\tfrac12$ и $p_{\text{пл}}$ шире прежних; без мер `eq:bc_props_ext` давал 12.3 pt, строка с $Q_{\lambda,-1/2}$ — 13.1 pt. T32/T33 сокращают пояснения «(отток наружу)» → «(отток)», «(приток с~контура)» → «(приток)» (знак $\mathcal{Q}$ рядом говорит то же), T38 переформулирована — оба переполнения уходят совсем |
| Связь с другими задачами | ⚠️ | **DEBT-062** влит (`aecd1e4`, 2026-10-15): правил `test_energy_matrix_examples.py:254` и `CLAUDE.md:262`; «До» C6 (строка 256) и V17 (строка 53) на `a7b0dc0` найдены (проба аудита 1). **DEBT-071** (план готов, не начат) правит прототип, адаптер, фабрику и `test_table_range_warnings.py` — файлов этого плана не касается. **BUG-029** (не начат) будет править тот же абзац о скин-факторе в `ssec:bc_disc`: его запись в реестре использует $\mathcal{T}_{1/2}$ — при планировании BUG-029 читать по новому соглашению ($\mathcal{T}_{-1/2}$) |
| Производительность | ✅ | не затрагивается |
| Прототип | ✅ | не меняется |

## 5. Как начать работу по этому плану

1. Прочитай этот файл целиком; заметки — раздел «Связанные заметки».
2. Worktree от базовой ветки (это делает `/implement`): `git worktree add .worktrees/debt-070 -b refactor/debt-070/statement-boundary-notation numerical_scheme/implementation`.
3. Python — `numerical_solver\.venv\Scripts\python` основного каталога; pytest из `.worktrees\debt-070\numerical_solver` берёт пакет и прототип своего дерева (`pythonpath` в `pyproject.toml`). Скрипты примеров не запускаются.
4. **Проба плана:** из корня репозитория (основного каталога или worktree)
   `numerical_solver\.venv\Scripts\python vault\issues\debt-070\probes\plan_apply.py <коммит>`
   Берёт блоки «До/После» правок T, C, V **из текста этого плана**, применяет их к копии дерева `<коммит>` (`git archive` → `probes/tree`, удаляется в конце; `--keep` — оставить для просмотра PDF), собирает PDF трижды, проверяет запрещённые шаблоны, сравнивает `ast` изменённых `.py` без докстрингов с базой и прогоняет сторож меток. Выход — `probes/plan_apply.out.txt`. Ожидание на `a7b0dc0`: 74 правки, каждая найдена ровно один раз; PDF 40 страниц, undefined 0, LaTeX Warning 0, Overfull 17; запрещённых шаблонов 0; `ast` совпадает; сторож `10 passed`.
5. Baseline в worktree: `.venv\Scripts\python -m pytest tests/ --collect-only -q` (1987), `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` (1711 passed, ~70 с), PDF — шаг 0.
6. Правки делаются **инструментом Edit по блокам «До/После» ниже**, по одной правке на вызов (или группой в одном файле). «До» каждой правки уникален в файле на момент применения (проба это проверяет).

## 6. Шаги

### Шаг 0: Подготовка и baseline

**Цель:** зафиксировать исходное состояние и убедиться, что правки плана применимы к базе реализации.

**Файлы:** —

**Что сделать:**
1. `git log --oneline -3` в базе; если база ушла от `a7b0dc0` — `git diff --stat a7b0dc0 HEAD -- numerical_solver/doc numerical_solver/gpn_multiphase_solver/energy numerical_solver/tests/test_energy.py numerical_solver/tests/test_energy_matrix_examples.py numerical_solver/tests/test_rate_control.py numerical_solver/examples/15_oil_rate_ramp_up vault/knowledge CLAUDE.md`.
2. Проба плана на базе реализации (раздел 5, п. 4). Если какая-то правка «не найдена» или «найдена N раз» — база ушла: обновить «До» этой правки по текущему тексту (смысл правки не менять) и повторить.
3. Тесты: `--collect-only -q` → 1987 (или новое число базы), `-m "not slow" -q` → все passed, время.
4. PDF в `.worktrees\debt-070\numerical_solver\doc`: `pdflatex -interaction=nonstopmode problem_statement.tex` **три раза** (в новом worktree `.aux` нет — раздел 1); из `problem_statement.log` — страницы (`Output written … (N pages`), число `undefined`, `LaTeX Warning`, `Overfull`. Ожидание: 40, 0, 0, 19.

**Проверка:** числа записаны в отчёт шага.

**Оценка:** ~5 мин.

### Шаг 1: Начальные значения — $p_{\text{пл}}$, $T_{\text{пл}}$; блок «Сетка» в таблице обозначений

**Цель:** символы $p_0$, $T_0$ освобождаются для ячейки 0; таблица обозначений прямо говорит, что значит $p_0$ и как нумеруются грани.

**Файлы:** `numerical_solver/doc/problem_statement.tex`

**Контекст:** макросы `\ppl`, `\Tpl` — 47 вхождений; правка двух определений меняет их все. Три места набраны буквально (120, 152, 621) — на 621 начальное газосодержание ошибочно записано $R_{s,0}$ (символ ячейки 0); правильно $R_s^0$, как в таблице обозначений (стр. 120). В таблице `lll` — строки короткие, чтобы не расширять её (раздел 4).

#### Правка T1 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
\newcommand{\ppl}{p_0}
\newcommand{\pwf}{p_{\mathrm{wf}}}
\newcommand{\pb}{p_b}
\newcommand{\Tpl}{T_0}
````

После:
````latex
\newcommand{\ppl}{p_{\text{пл}}}
\newcommand{\pwf}{p_{\mathrm{wf}}}
\newcommand{\pb}{p_b}
\newcommand{\Tpl}{T_{\text{пл}}}
````

#### Правка T2 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
$\ppl$        & начальное пластовое давление              & Па \\
$\Tpl$        & начальная пластовая температура            & К \\
````

После:
````latex
$\ppl$        & начальное пластовое давление (оно~же на~контуре) & Па \\
$\Tpl$        & начальная пластовая температура (она~же на~контуре) & К \\
````

#### Правка T3 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
$R_s^0$       & начальное газосодержание ($R_s^0 \leqslant R_s^{\text{eq}}(p_0, T_0)$) & м$^3$ст/м$^3$ст \\
````

После:
````latex
$R_s^0$       & начальное газосодержание ($R_s^0 \leqslant R_s^{\text{eq}}(\ppl, \Tpl)$) & м$^3$ст/м$^3$ст \\
````

#### Правка T4 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
$\phi$        & пористость, $\phi(p)$~\eqref{eq:porosity}; $\phi_0 = \phi(p_0)$ & --- \\
````

После:
````latex
$\phi$        & пористость, $\phi(p)$~\eqref{eq:porosity}; $\phi_0 = \phi(\ppl)$ & --- \\
````

#### Правка T5 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
$h$           & мощность (толщина) пласта                  & м \\

\end{longtable}
````

После:
````latex
$h$           & мощность (толщина) пласта                  & м \\

\multicolumn{3}{l}{\textbf{Сетка}} \\
$N$           & число ячеек                                & --- \\
$j$           & номер ячейки, $j = 0, \ldots, N-1$; ячейка~0 у~забоя & --- \\
$j \pm \half$ & грани ячейки~$j$; забой~--- $-\half$, контур~--- $N-\half$ & --- \\
$p_j$, $T_j$  & давление и~температура ячейки~$j$ ($p_0$, $T_0$~--- у~забоя) & Па, К \\

\end{longtable}
````

#### Правка T6 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
с~$R_{s,0} = 500$~м$^3$ст/м$^3$ст расчёт не~сходится или зависит от~шага
````

После:
````latex
с~$R_s^0 = 500$~м$^3$ст/м$^3$ст расчёт не~сходится или зависит от~шага
````

**Проверка после шага:**
- Регресс: `--collect-only -q` (только документ) — 1987.
- `.venv\Scripts\python -m pytest tests/test_eq_references.py -q` — `10 passed`.
- Сборка PDF без ошибок (полная проверка — шаг 4).

**Подводные камни:** ширина таблицы (раздел 4); `\text{пл}` (раздел 4).

**Зависимости:** требует шаг 0; блокирует шаг 3 (абзац BUG-015 переходит на `\ppl`, `\Tpl`).

**Оценка:** 6 правок, ~10 мин.

### Шаг 2: Сетка — грани $j - \tfrac12$, забой $-\tfrac12$, контур $N - \tfrac12$

**Цель:** `ssec:grid` определяет грани в том же соглашении, что `eq:cell_center`, `eq:volume` и балансы; проводимость `eq:transmissibility` явно относится к внутренним граням.

**Файлы:** `numerical_solver/doc/problem_statement.tex`

**Контекст:** сейчас `eq:log_grid` задаёт $r_{j+1/2} = r_w (R_{ext}/r_w)^{j/N}$, $j = 0 \ldots N$, то есть $r_{1/2} = r_w$; тогда `eq:cell_center` для $j = 0$ требует $r_{-1/2}$, которой нет. Сдвиг индекса в левой части ($r_{j-1/2}$ при той же правой части) даёт $r_{-1/2} = r_w$, $r_{N-1/2} = R_{ext}$ — и `eq:cell_center`, `eq:volume` определены для всех $j = 0 \ldots N-1$. Положение граней (числа) не меняется. Фраза про номер $f$ в коде — для читателя кода; та же связь — в словаре (шаг 6).

#### Правка T7 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
  r_{j+\half} = \rw \cdot \left(\frac{\Rext}{\rw}\right)^{j/N},
  \quad j = 0, 1, \ldots, N.
\end{equation}
Крайние грани совпадают с~границами области:
$r_{\half} = \rw$, $r_{N+\half} = \Rext$.
````

После:
````latex
  r_{j-\half} = \rw \cdot \left(\frac{\Rext}{\rw}\right)^{j/N},
  \quad j = 0, 1, \ldots, N.
\end{equation}
Ячейка~$j$ ($j = 0, \ldots, N-1$) лежит между гранями ${j-\half}$ (ближе
к~скважине) и~${j+\half}$. Крайние грани совпадают с~границами области:
$r_{-\half} = \rw$ (забой), $r_{N-\half} = \Rext$ (контур). В~коде грани
нумеруются $f = 0, \ldots, N$: грань ${j-\half}$ имеет номер $f = j$.
````

Фигурные скобки внутри `$…$` (`${j+\half}$`) делают выражение неразрывным: без них TeX переносит строку после «+» (проба: «$j +$» в конце строки, «$\tfrac12$» в начале следующей).

#### Правка T8 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
\paragraph{Геометрическая проводимость} грани~$j+\half$
в~логарифмической радиальной сетке:
````

После:
````latex
\paragraph{Геометрическая проводимость} внутренней грани~$j+\half$
($j = 0, \ldots, N-2$) в~логарифмической радиальной сетке
(граничные грани $-\half$ и~$N-\half$~--- в~разделе~\ref{ssec:bc_disc}):
````

**Проверка после шага:** `--collect-only -q` — 1987; `test_eq_references.py` — passed.

**Зависимости:** требует шаг 0.

**Оценка:** 2 правки, ~5 мин.

### Шаг 3: Граничные грани в `ssec:bc_disc` и в абзаце о диагональном преобладании

**Цель:** забойная грань везде $-\tfrac12$, контурная $N - \tfrac12$, правая грань ячейки 0 — $\tfrac12$; абзац BUG-015 пишет контурные значения через `\ppl`, `\Tpl`.

**Файлы:** `numerical_solver/doc/problem_statement.tex`

**Контекст:** таблица соответствий старое → новое:

| Было | Стало | Смысл |
|---|---|---|
| $\tfrac12$ (забойная грань): $r_{1/2}$, $\mathcal{T}_{1/2}$, $G_{1/2}$, $\Phi_{1/2}$, $Q_{\lambda,1/2}$ | $-\tfrac12$ | левая грань ячейки 0 |
| $\tfrac32$, $\tfrac12 + 1$ | $\tfrac12$ | правая грань ячейки 0 |
| $N + \tfrac12$, $N$ (у $\Phi^-$) | $N - \tfrac12$ | контурная грань (правая ячейки $N-1$) |
| $N - \tfrac12$ (левая грань ячейки $N-1$, стр. 2033) | $N - \tfrac32$ | левая грань ячейки $N-1$ |
| $1 + \tfrac12$, $1$ (случай $N = 1$) | $\tfrac12$ | контурная грань при $N = 1$ ($N - \tfrac12 = \tfrac12$) |
| $p_{\text{конт}}$, $T_{\text{конт}}$ | `\ppl`, `\Tpl` | значения на контуре |

$p_0$, $T_0$, $S_{g,0}$, $R_{s,0}$, $(\cdot)_0$, $a_0$, $b_0$, $V_0$ в `ssec:bc_disc` — ячейка 0, **не меняются**.

#### Правка T9 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
($Q_{\lambda,N+\half}^T$ и~$-\Phi_{N}^{-}$ при~$j = N{-}1$) остаются
````

После:
````latex
($Q_{\lambda,N-\half}^T$ и~$-\Phi_{N-\half}^{-}$ при~$j = N{-}1$) остаются
````

#### Правка T10 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
  \mathcal{T}_{\half} = \frac{2\pi\,h\,k}{\ln(r_0/\rw)},
  \qquad
  \mathcal{T}_{N+\half} = \frac{2\pi\,h\,k}{\ln(\Rext/r_{N-1})}.
````

После:
````latex
  \mathcal{T}_{-\half} = \frac{2\pi\,h\,k}{\ln(r_0/\rw)},
  \qquad
  \mathcal{T}_{N-\half} = \frac{2\pi\,h\,k}{\ln(\Rext/r_{N-1})}.
````

#### Правка T11 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
$\mathcal{T}_{\half} = 2\pi h k / \bigl(\ln(r_0/\rw) + s\bigr)$.
````

После:
````latex
$\mathcal{T}_{-\half} = 2\pi h k / \bigl(\ln(r_0/\rw) + s\bigr)$.
````

#### Правка T12 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
\paragraph{Забой ($r = \rw$, левая грань ячейки $j = 0$).}
Давление на~грани $r_{\half} = \rw$ задано: $p\big|_{r_w} = \pwf$.
````

После:
````latex
\paragraph{Забой ($r = \rw$, левая грань $-\half$ ячейки $j = 0$).}
Давление на~грани $r_{-\half} = \rw$ задано: $p\big|_{r_w} = \pwf$.
````

#### Правка T13 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
  G_{\half}^{o} &= \mathcal{T}_{\half}\,
````

После:
````latex
  G_{-\half}^{o} &= \mathcal{T}_{-\half}\,
````

#### Правка T14 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
  G_{\half}^{g} &= \mathcal{T}_{\half}\!\left[
````

После:
````latex
  G_{-\half}^{g} &= \mathcal{T}_{-\half}\!\left[
````

#### Правка T15 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
Потоки $G_{\half}^{o}$, $G_{\half}^{g}$ входят в~невязки
ячейки~$j = 0$ наравне с~потоками через правую грань~$G_{3/2}$.
````

После:
````latex
Потоки $G_{-\half}^{o}$, $G_{-\half}^{g}$ входят в~невязки
ячейки~$j = 0$ наравне с~потоками через правую грань~$G_{\half}$.
````

#### Правка T16 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
$q_{o,\text{ст}} = -G_{\half}^o > 0$.
````

После:
````latex
$q_{o,\text{ст}} = -G_{-\half}^o > 0$.
````

#### Правка T17 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
$G_{\half} > 0$~--- закачку через~забой, которую
````

После:
````latex
$G_{-\half} > 0$~--- закачку через~забой, которую
````

#### Правка T18 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
$G_{\half}^{o} = G_{\half}^{g} = 0$, а~фактическое $\pwf$ шага
````

После:
````latex
$G_{-\half}^{o} = G_{-\half}^{g} = 0$, а~фактическое $\pwf$ шага
````

#### Правка T19 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
Поток нефти через~забойную грань задан, $G_{\half}^{o} = -q_{o,\text{ст}}$,
````

После:
````latex
Поток нефти через~забойную грань задан, $G_{-\half}^{o} = -q_{o,\text{ст}}$,
````

#### Правка T20 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
    {\mathcal{T}_{\half}\,\bigl(k_{ro}/(\mu_o B_o)\bigr)_0}
````

После:
````latex
    {\mathcal{T}_{-\half}\,\bigl(k_{ro}/(\mu_o B_o)\bigr)_0}
````

#### Правка T21 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
входит с~весом~$\Phi^{+}_{\half}$ и~при~добыче ($\Phi_{\half} < 0$)
````

После:
````latex
входит с~весом~$\Phi^{+}_{-\half}$ и~при~добыче ($\Phi_{-\half} < 0$)
````

#### Правка T22 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
\paragraph{Контур питания ($r = \Rext$, правая грань ячейки
$j = N{-}1$).}
Давление на~грани $r_{N+\half} = \Rext$ задано:
````

После:
````latex
\paragraph{Контур питания ($r = \Rext$, правая грань $N-\half$ ячейки
$j = N{-}1$).}
Давление на~грани $r_{N-\half} = \Rext$ задано:
````

#### Правка T23 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
  G_{N+\half}^{o} &= \mathcal{T}_{N+\half}\,
````

После:
````latex
  G_{N-\half}^{o} &= \mathcal{T}_{N-\half}\,
````

#### Правка T24 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
  G_{N+\half}^{g} &= \mathcal{T}_{N+\half}\,
````

После:
````latex
  G_{N-\half}^{g} &= \mathcal{T}_{N-\half}\,
````

#### Правка T25 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
  \item на~забое (левая грань ячейки~$j = 0$):
````

После:
````latex
  \item на~забое (левая грань $-\half$ ячейки~$j = 0$):
````

#### Правка T26 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
    $\sum_\alpha \mu_{\mathrm{JT},\alpha}\,\Phi_{\alpha,\half}^{+}
    (p_0 - \pwf)$~--- с~весом~$\Phi^{+}$ левой грани, как у~любой
    ячейки. При~добыче $\Phi_{\alpha,\half} \le 0$, поэтому
    $\Phi^{+}_{\alpha,\half} = 0$ и~слагаемое \textbf{тождественно
````

После:
````latex
    $\sum_\alpha \mu_{\mathrm{JT},\alpha}\,\Phi_{\alpha,-\half}^{+}
    (p_0 - \pwf)$~--- с~весом~$\Phi^{+}$ левой грани, как у~любой
    ячейки. При~добыче $\Phi_{\alpha,-\half} \le 0$, поэтому
    $\Phi^{+}_{\alpha,-\half} = 0$ и~слагаемое \textbf{тождественно
````

#### Правка T27 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
      T_j = T_{\text{конт}} + \mu_{\mathrm{JT}}\,(p_j - p_{\text{конт}})
    \]
    \textbf{точно в~центрах} ячеек ($p_{\text{конт}}$, $T_{\text{конт}}$~---
    значения на~контуре). Поэтому температура ячейки~$j = 0$~---
````

После:
````latex
      T_j = \Tpl + \mu_{\mathrm{JT}}\,(p_j - \ppl)
    \]
    \textbf{точно в~центрах} ячеек ($\ppl$, $\Tpl$~---
    значения на~контуре). Поэтому температура ячейки~$j = 0$~---
````

#### Правка T28 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
    перепад от~$\pwf$ до~$p_{\text{конт}}$, и~в~стационаре
````

После:
````latex
    перепад от~$\pwf$ до~$\ppl$, и~в~стационаре
````

#### Правка T29 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
  \item на~контуре (правая грань ячейки~$j = N{-}1$):
    давление~$p_{\text{конт}} = \ppl$,
````

После:
````latex
  \item на~контуре (правая грань $N-\half$ ячейки~$j = N{-}1$):
    давление~$\ppl$,
````

#### Правка T30 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
вычисляется с~граничной проводимостью $\mathcal{T}_{\half}$
или~$\mathcal{T}_{N+\half}$. Далее
````

После:
````latex
вычисляется с~граничной проводимостью $\mathcal{T}_{-\half}$
или~$\mathcal{T}_{N-\half}$. Далее
````

#### Правка T31 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
  \bigr)_{N+\half}
````

После:
````latex
  \bigr)_{N-\half}
````

#### Правка T32 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
      & \mathcal{Q}_{\alpha,N+\half} \geqslant 0
        \quad\text{(отток наружу)},\\[6pt]
````

После:
````latex
      & \mathcal{Q}_{\alpha,N-\half} \geqslant 0
        \;\text{(отток)},\\[6pt]
````

#### Правка T33 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
      & \mathcal{Q}_{\alpha,N+\half} < 0
        \quad\text{(приток с~контура)}.
````

После:
````latex
      & \mathcal{Q}_{\alpha,N-\half} < 0
        \;\text{(приток)}.
````

T32, T33 сокращают подписи ветвей `eq:bc_props_ext` по ширине: с $N-\tfrac12$ и $(p_{\text{пл}}, T_{\text{пл}}, R_s^0)$ в индексе формула в рамке выходила за поле на 12.3 pt (в базе — 3.4 pt). Смысл тот же: направление задаёт знак $\mathcal{Q}$ в той же строке, а «наружу» и «с контура» на контурной грани — единственные варианты.

#### Правка T34 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
$\mathcal{Q}_{g,N+\half} = 0$, и~газовая составляющая~$\Phi_g$
````

После:
````latex
$\mathcal{Q}_{g,N-\half} = 0$, и~газовая составляющая~$\Phi_g$
````

#### Правка T35 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
      \Phi_{N}^{-}\,\bigl(\Tpl - T_{N-1}\bigr)
      \;\Longrightarrow\;
      b_{N-1} \mathrel{+}= -\Phi_{N}^{-},
      \qquad
      d_{N-1} \mathrel{+}= -\Phi_{N}^{-}\,\Tpl ,
````

После:
````latex
      \Phi_{N-\half}^{-}\,\bigl(\Tpl - T_{N-1}\bigr)
      \;\Longrightarrow\;
      b_{N-1} \mathrel{+}= -\Phi_{N-\half}^{-},
      \qquad
      d_{N-1} \mathrel{+}= -\Phi_{N-\half}^{-}\,\Tpl ,
````

#### Правка T36 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
    справа нет: $c_{N-1} = 0$. Вклад левой грани $N{-}\half$~---
````

После:
````latex
    справа нет: $c_{N-1} = 0$. Вклад левой грани $N{-}\tfrac{3}{2}$~---
````

#### Правка T37 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
    $Q_{\lambda,N+\half}
    = \dfrac{2\pi\,h}{\ln(\Rext/r_{N-1})}\,
````

После:
````latex
    $Q_{\lambda,N-\half}
    = \dfrac{2\pi\,h}{\ln(\Rext/r_{N-1})}\,
````

#### Правка T38 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
    Кондуктивный поток через левую грань обнуляется:
    $Q_{\lambda,\half} =~0$.
````

После:
````latex
    Кондуктивный поток через левую грань $Q_{\lambda,-\half}$
    равен нулю.
````

Формулировка без «$= 0$» в конце: с ней TeX переносил строку после «=», и «0.» оказывался один на следующей строке (проба); исходная `=~0` давала Overfull 6.5 pt в базе и 13 pt с индексом $-\tfrac12$.

#### Правка T39 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
    отвечающий грани~$\half$, тождественно равен нулю:
    $b_0^{\text{конв}} = -\Phi_{\half+1}^{-}$, и~$a_0 = 0$.
````

После:
````latex
    отвечающий грани~$-\half$, тождественно равен нулю:
    $b_0^{\text{конв}} = -\Phi_{\half}^{-}$, и~$a_0 = 0$.
````

#### Правка T40 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
    нулевой: он входит в~\eqref{eq:QJT_disc} с~весом~$\Phi^{+}_{\half}$,
````

После:
````latex
    нулевой: он входит в~\eqref{eq:QJT_disc} с~весом~$\Phi^{+}_{-\half}$,
````

#### Правка T41 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
    \textbf{Важно.} При \emph{втекании} через забой ($\Phi_{\half}^{+} > 0$,
````

После:
````latex
    \textbf{Важно.} При \emph{втекании} через забой ($\Phi_{-\half}^{+} > 0$,
````

#### Правка T42 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
    обе её грани граничные. Левая (забой) вклада не~даёт, правая
    (контур) даёт его \emph{один} раз:
````

После:
````latex
    обе её грани граничные. Левая ($-\half$, забой) вклада не~даёт, правая
    ($\half = N-\half$, контур) даёт его \emph{один} раз:
````

#### Правка T43 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
            + Q_{\lambda,1+\half}^T - \Phi_{1}^{-},
````

После:
````latex
            + Q_{\lambda,\half}^T - \Phi_{\half}^{-},
````

#### Правка T44 — `numerical_solver/doc/problem_statement.tex`

До:
````latex
            + Q_{\lambda,1+\half}^T\,\Tpl
            - \Phi_{1}^{-}\,\Tpl
````

После:
````latex
            + Q_{\lambda,\half}^T\,\Tpl
            - \Phi_{\half}^{-}\,\Tpl
````

**Проверка после шага:** `--collect-only -q` — 1987; `test_eq_references.py` — passed.

**Подводные камни:** порядок правок T1 → T27: «После» T27 использует `\ppl`, `\Tpl`, которые печатаются как $p_{\text{пл}}$, $T_{\text{пл}}$ только после T1. Правые грани ячейки 0 и случая $N = 1$ остаются с индексом $\tfrac12$ (T15, T39, T43, T44) — это верно, не «забытые».

**Зависимости:** требует шаг 1.

**Оценка:** 36 правок, ~30 мин.

### Шаг 4: Сборка PDF, проверка шаблонов, вычитка

**Цель:** убедиться, что документ собирается, в тексте не осталось старого соглашения, а формулы на страницах граничных условий читаются верно.

**Файлы:** `numerical_solver/doc/problem_statement.tex` (только чтение), `problem_statement.log`, `.aux`, `.pdf` (не в git).

**Что сделать:**
1. В `.worktrees\debt-070\numerical_solver\doc`: `pdflatex -interaction=nonstopmode problem_statement.tex` — повторять, пока в логе есть «Label(s) may have changed» или «Rerun» (обычно хватает двух проходов после шага 0).
2. Из `problem_statement.log`: страниц — **40**, `undefined` — **0**, `LaTeX Warning` — **0**, `Overfull` — **17** (как в пробе: 5 строк таблицы по 75 pt и 12 вне правок; двух переполнений `ssec:bc_disc` базы нет). Больше 17 или Overfull в правленых абзацах — переформулировать фразу (без смены обозначений) и проверить переносы глазами.
3. Запрещённые шаблоны в `.tex` (grep, все должны дать **0**):
   - `N+\half`, `\half+1`, `1+\half`, `G_{3/2}`, `\Phi_{N}^`, `\Phi_{1}^`;
   - `\text{конт}`;
   - `r_{\half} = \rw`, `(p_0, T_0)`, `\phi(p_0)`, `R_{s,0} = 500`;
   - `\newcommand{\ppl}{p_0}`, `\newcommand{\Tpl}{T_0}`.
4. Оставшиеся `_{\half}` и `,\half}` (без минуса) — только правая грань ячейки 0 и случай $N = 1$: $G_{\half}$ (T15), $\Phi^-_{\half}$ (T39, T43, T44), $Q_{\lambda,\half}$ (T43, T44), плюс общие `j\pm\half` (`j+\half`, `j-\half`). Вывести список grep-ом и просмотреть.
5. **Вычитка PDF** (инструмент Read, параметр `pages`). Страницы `ssec:bc_disc` и `ssec:grid` — по `problem_statement.aux`: `\newlabel{ssec:bc_disc}{{…}{<стр.>}…}`, `\newlabel{ssec:grid}{…}`. В пробе: таблица обозначений — с. 4–5 (блок «Сетка» — внизу с. 5), `ssec:grid` — с. 14, `ssec:bc_disc` — с. 24–28. Проверить глазами:
   - $p_{\text{пл}}$, $T_{\text{пл}}$ печатаются кириллицей прямым шрифтом в индексе;
   - индексы $-\tfrac12$, $N-\tfrac12$ не сливаются с соседними символами;
   - нет переносов внутри «$j \pm \tfrac12$» и одинокого «0.» в начале строки (оба были в первой версии правок, устранены T7, T38);
   - нигде рядом не стоят $p_0$ в двух смыслах.

**Проверка после шага:** все пункты выполнены; числа записаны в отчёт шага.

**Зависимости:** требует шаги 1–3.

**Оценка:** ~20 мин.

### Шаг 5: Копии соглашения в коде, тестах и README примера 15

**Цель:** комментарии и докстринги, где забойная грань названа $\tfrac12$, а контурные значения — $p_0$, $T_0$, говорят то же, что постановка.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/energy/tridiag.py`
- `numerical_solver/gpn_multiphase_solver/energy/balance.py`
- `numerical_solver/tests/test_energy.py`
- `numerical_solver/tests/test_energy_matrix_examples.py`
- `numerical_solver/tests/test_rate_control.py`
- `numerical_solver/examples/15_oil_rate_ramp_up/README.md`

**Контекст:** меняются только комментарии и докстринги — `ast` модулей без докстрингов совпадает с базой (проба). В комментариях `.py` индексы граней постановки пишутся `-1/2` ASCII-дефисом, как `j-1/2` в соседних строках (`tridiag.py:416`). Код-индексы в квадратных скобках (`p[0]`, `Φ⁻[N]`) — номера массивов. В README 15 символ $p_0$ уже означает начальное давление (15.5 МПа, стр. 14, 51, 283), поэтому давление ячейки 0 в формуле `eq:bc_rate_pwf` пишется $p[0]$ — как в том же README на стр. 153.

#### Правка C1 — `numerical_solver/gpn_multiphase_solver/energy/tridiag.py`

До:
````python
        p_wf — давление на забойной грани (HydroResult.p_wf), значение «за
        гранью» для грани 0. Её слагаемое μ·Φ⁺_{1/2}·(p[0] − p_wf) при
        добыче (Φ_{1/2} < 0) нулевое: перепад p[0] − p_wf не получает ни
        одна ячейка, и T[0] — температура в центре ячейки 0, а не на забое
        (BUG-015, ssec:bc_disc).
````

После:
````python
        p_wf — давление на забойной грани (HydroResult.p_wf), значение «за
        гранью» для грани 0 (в постановке — грань -1/2). Её слагаемое
        μ·Φ⁺_{-1/2}·(p[0] − p_wf) при добыче (Φ_{-1/2} < 0) нулевое: перепад
        p[0] − p_wf не получает ни одна ячейка, и T[0] — температура в центре
        ячейки 0, а не на забое (BUG-015, ssec:bc_disc).
````

#### Правка C2 — `numerical_solver/gpn_multiphase_solver/energy/balance.py`

До:
````python
        # -Φ⁻_N·T_ext уходит в правую часть d[N-1], потому что T_ext
````

После:
````python
        # -Φ⁻[N]·T_ext уходит в правую часть d[N-1], потому что T_ext
````

#### Правка C3 — `numerical_solver/tests/test_energy.py`

До:
````python
    μ_JT·Φ⁺_{1/2}·(p[0] − p_wf): схема против потока берёт левую грань с Φ⁺.
    При добыче Φ_{1/2} < 0, Φ⁺ = 0, и p_wf на T не влияет (BUG-015); при
````

После:
````python
    μ_JT·Φ⁺_{-1/2}·(p[0] − p_wf): схема против потока берёт левую грань с Φ⁺.
    При добыче Φ_{-1/2} < 0, Φ⁺ = 0, и p_wf на T не влияет (BUG-015); при
````

#### Правка C4 — `numerical_solver/tests/test_energy.py`

До:
````python
        запрещает, её путь с Φ⁺_{1/2} > 0 проверяем.
````

После:
````python
        запрещает, её путь с Φ⁺_{-1/2} > 0 проверяем.
````

#### Правка C5 — `numerical_solver/tests/test_energy.py`

До:
````python
        """Добыча: T побитово не зависит от p_wf (Φ⁺_{1/2} = 0).
````

После:
````python
        """Добыча: T побитово не зависит от p_wf (Φ⁺_{-1/2} = 0).
````

#### Правка C6 — `numerical_solver/tests/test_energy_matrix_examples.py`

До:
````python
    # из ячейки N-1, приток — при условиях контура (p_0, T_0, Rs^0).
````

После:
````python
    # из ячейки N-1, приток — при условиях контура (p_ext, T_ext, Rs_ext).
````

#### Правка C7 — `numerical_solver/tests/test_energy_matrix_examples.py`

До:
````python
        обнуляется (Q_λ,1/2 = 0), связи слева нет → a[0] = 0.
````

После:
````python
        обнуляется (Q_λ,-1/2 = 0), связи слева нет → a[0] = 0.
````

#### Правка C8 — `numerical_solver/tests/test_energy_matrix_examples.py`

До:
````python
        разности T соседей, поэтому член грани 1/2 тождественно нулевой.
````

После:
````python
        разности T соседей, поэтому член грани -1/2 тождественно нулевой.
````

#### Правка C9 — `numerical_solver/tests/test_rate_control.py`

До:
````python
p_wf = p_0 − q_o,ст / (T_{1/2}·λ_o,0), с нижней границей min_bhp. Дебит
````

После:
````python
p_wf = p[0] − q_o,ст / (T_{-1/2}·λ_o[0]), с нижней границей min_bhp. Дебит
````

В этом же файле `p0` — начальное давление 15.5 МПа (строки 31, 114), поэтому давление и подвижность ячейки 0 — кодовыми индексами `p[0]`, `λ_o[0]`, как в соседнем `q = −G_o[0]`. В `test_energy_matrix_examples.py` так не делается: там `p0` — поле конфига, а `p_0` уже везде означает ячейку 0 (строки 417, 468, 541); после C6 исключений нет.

#### Правка C10 — `numerical_solver/examples/15_oil_rate_ramp_up/README.md`

До:
````markdown
$G^o_{1/2} = -q_{o,\text{ст}}$, и забойное давление выражается из уравнения
````

После:
````markdown
$G^o_{-1/2} = -q_{o,\text{ст}}$, и забойное давление выражается из уравнения
````

#### Правка C11 — `numerical_solver/examples/15_oil_rate_ramp_up/README.md`

До:
````markdown
p_{wf} = p_0 - \frac{q_{o,\text{ст}}}{\mathcal{T}_{1/2}\,\bigl(k_{ro}/(\mu_o B_o)\bigr)_0},
````

После:
````markdown
p_{wf} = p[0] - \frac{q_{o,\text{ст}}}{\mathcal{T}_{-1/2}\,\bigl(k_{ro}/(\mu_o B_o)\bigr)[0]},
````

#### Правка C12 — `numerical_solver/examples/15_oil_rate_ramp_up/README.md`

До:
````markdown
где $p_0$ — давление в ячейке у забоя, $\mathcal{T}_{1/2}$ — проводимость
забойной грани. Подвижность нефти берётся на новом слое, поэтому $p_{wf}$
````

После:
````markdown
где $p[0]$ — давление в ячейке 0 у забоя (не начальное $p_0$),
$\mathcal{T}_{-1/2}$ — проводимость забойной грани (грань 0 в коде).
Подвижность нефти берётся на новом слое, поэтому $p_{wf}$
````

#### Правка C13 — `numerical_solver/examples/15_oil_rate_ramp_up/README.md`

До:
````markdown
забойной грани с весом $\Phi^+_{1/2}$, а при потоке к скважине он нулевой
````

После:
````markdown
забойной грани с весом $\Phi^+_{-1/2}$, а при потоке к скважине он нулевой
````

**Проверка после шага:**
- Регресс: **быстрый** — `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` (изменены `.py`; все passed, число как в шаге 0).
- Отдельно: `.venv\Scripts\python -m pytest tests/test_eq_references.py tests/test_rate_control.py tests/test_energy.py::TestWellPressureSource -q` — passed.
- Grep по шести файлам шага (`tridiag.py`, `balance.py`, `test_energy.py`, `test_energy_matrix_examples.py`, `test_rate_control.py`, README 15): шаблоны `_{1/2}`, `,1/2 `, `грани 1/2`, `Φ⁻_N`, `(p_0, T_0` — 0 вхождений (проба проверяет только `.tex` и заметки vault).
- `ast` без докстрингов: `tridiag.py`, `balance.py`, три теста — как в базе (проба плана делает это на копии дерева; в worktree можно повторить пробой на коммите шага).

**Подводные камни:** C6 — через строку от правки DEBT-062 (строка 254, влит в `aecd1e4`); «До» C6 сверено на `a7b0dc0`. Длина изменённых строк ≤ 79 символов.

**Зависимости:** требует шаг 0 (от шагов 1–4 не зависит по коду, но формулировки ссылаются на новое соглашение — делать после них).

**Оценка:** 13 правок, ~15 мин.

### Шаг 6: Vault и словарь CLAUDE.md

**Цель:** словарь код ↔ физика и заметки, описывающие сетку и граничные грани, говорят на языке постановки после DEBT-070; словарь CLAUDE.md объясняет $p_{\text{пл}}$.

**Файлы:**
- `vault/knowledge/decisions/словарь-код-физика.md`
- `vault/knowledge/decisions/модули-grid-сетка.md`
- `vault/knowledge/decisions/свойства-фаз-на-контурной-грани-берутся-из-ГУ-при-притоке.md`
- `vault/knowledge/numerics/температура ячейки 0 — центр, не забой.md`
- `CLAUDE.md`

**Контекст:** словарь — «единственный источник истины при реализации» (его строка 10). Сейчас он сам смешивает соглашения: `r_faces[f]` = «r_{f+1/2} при нумерации ячеек с 1», `trans_well` = $T_{1/2}$, а коэффициенты СЛАУ (§6) — $j - \tfrac12 \leftrightarrow f = j$. **Попутно** (V7): формулы контурной грани в §3.1 берут подвижность из ячейки $N-1$ безусловно, а код (`fluxes.py:204–220`) и постановка (`eq:bc_flux_ext`) — против потока: при притоке из условий контура. Это устаревшая запись словаря, исправляется в той же правке, что и индексы рядом. CLAUDE.md правится только в строке, согласованной пользователем (раздел 0, п. 3).

#### Правка V1 — `vault/knowledge/decisions/словарь-код-физика.md`

До:
````markdown
Ячейки нумеруются j = 0, 1, ..., N-1. Грани нумеруются f = 0, 1, ..., N.
````

После:
````markdown
Ячейки нумеруются j = 0, 1, ..., N-1. Грани нумеруются f = 0, 1, ..., N.

В `problem_statement.tex` (после [[DEBT-070]]) ячейка j лежит между гранями j − 1/2 и j + 1/2; грань j − 1/2 постановки — это грань f = j кода. Забой — грань −1/2 (f = 0), контур — грань N − 1/2 (f = N). Значения ячейки 0 — p_0, T_0; начальные (они же контурные) — p_пл, T_пл (конфиг `p0`, `T0`; граничные условия `p_ext`, `T_ext`).
````

#### Правка V2 — `vault/knowledge/decisions/словарь-код-физика.md`

До:
````markdown
| `r_faces[f]` | r_{f+1/2} при нумерации ячеек с 1; r_faces[0]=r_w, r_faces[N]=R_ext | `eq:log_grid` | [N+1] |
````

После:
````markdown
| `r_faces[f]` | r_{f-1/2}; r_faces[0] = r_{-1/2} = r_w, r_faces[N] = r_{N-1/2} = R_ext | `eq:log_grid` | [N+1] |
````

#### Правка V3 — `vault/knowledge/decisions/словарь-код-физика.md`

До:
````markdown
| `trans_internal[f]` | T_{f+1} = 2πhk / ln(r_centers[f+1]/r_centers[f]), f=0..N-2 | `eq:transmissibility` | [N-1] |
| `trans_well` | T_{1/2} = 2πhk / ln(r_centers[0]/r_w) | формула без номера над `eq:bc_flux_well` | скаляр |
| `trans_ext` | T_{N+1/2} = 2πhk / ln(R_ext/r_centers[N-1]) | формула без номера над `eq:bc_flux_well` | скаляр |
````

После:
````markdown
| `trans_internal[f]` | T_{f+1/2} = 2πhk / ln(r_centers[f+1]/r_centers[f]), f=0..N-2 (грань f+1 кода) | `eq:transmissibility` | [N-1] |
| `trans_well` | T_{-1/2} = 2πhk / ln(r_centers[0]/r_w) | формула без номера над `eq:bc_flux_well` | скаляр |
| `trans_ext` | T_{N-1/2} = 2πhk / ln(R_ext/r_centers[N-1]) | формула без номера над `eq:bc_flux_well` | скаляр |
````

#### Правка V4 — `vault/knowledge/decisions/словарь-код-физика.md`

До:
````markdown
Проводимость `trans_internal[f]` соответствует грани f+1 (между ячейками f и f+1), f=0..N-2. Альтернативная интерпретация: проводимость грани между ячейками f и f+1.
````

После:
````markdown
Проводимость `trans_internal[f]` — грани между ячейками f и f+1, f = 0..N-2: в коде это грань f+1, в постановке — грань f + 1/2.
````

#### Правка V5 — `vault/knowledge/decisions/словарь-код-физика.md`

До:
````markdown
G_o[N] = trans_ext · (kro/(μo·Bo))_{N-1} · (p[N-1] - p_ext)
G_g[N] = trans_ext · Rs0·(kro/(μo·Bo))_{N-1} · (p[N-1] - p_ext)
         // krg=0 на контуре (Sg=0)
````

После:
````markdown
G_o[N] = trans_ext · (kro/(μo·Bo))_up · (p[N-1] - p_ext)
G_g[N] = trans_ext · [Rs_up·(kro/(μo·Bo))_up + (krg/(μg·Bg))_up] · (p[N-1] - p_ext)
         // up — против потока (fluxes.py, eq:bc_flux_ext):
         //   p[N-1] < p_ext (приток, типично) — условия контура:
         //     kro(Sg_ext), μo и Bo при (p_ext, Rs_ext), krg = 0, Rs_up = Rs_ext;
         //   иначе (отток) — ячейка N-1.
````

#### Правка V6 — `vault/knowledge/decisions/словарь-код-физика.md`

До:
````markdown
$p_b(R_{s,0})$, недонасыщенная нефть с $R_s = R_{s,0}$ — до $p_0$.
````

После:
````markdown
$p_b(R_s^0)$, недонасыщенная нефть с $R_s = R_s^0$ — до $p_{\text{пл}}$.
````

#### Правка V7 — `vault/knowledge/decisions/словарь-код-физика.md`

До:
````markdown
| `rock.porosity` | φ0 = φ(p0) | — |
````

После:
````markdown
| `rock.porosity` | φ_0 = φ(p_пл) | — |
````

#### Правка V8 — `vault/knowledge/decisions/словарь-код-физика.md`

До:
````markdown
| `TridiagEnergySolver.porosity(p)` | φ(p) = φ0·exp(c_r·(p − p0)), `eq:porosity` | — |
````

После:
````markdown
| `TridiagEnergySolver.porosity(p)` | φ(p) = φ_0·exp(c_r·(p − p_пл)), `eq:porosity` | — |
````

#### Правка V9 — `vault/knowledge/decisions/словарь-код-физика.md`

До:
````markdown
| `geom.h` | h | м |
````

После:
````markdown
| `geom.h` | h | м |
| `InitialConfig.p0`, `.T0`, `.Rs0` | p_пл, T_пл, R_s^0 — начальные значения | Па, К, м³ст/м³ст |
| `BoundaryConditions.p_ext`, `.T_ext`, `.Rs_ext` | p_пл, T_пл, R_s^0 — значения на контуре (фабрика: `p_ext = ic.p0` и т. д.) | Па, К, м³ст/м³ст |
````

#### Правка V10 — `vault/knowledge/decisions/модули-grid-сетка.md`

До:
````python
        """Проводимость левой граничной грани T_{1/2}."""
````

После:
````python
        """Проводимость левой граничной грани T_{-1/2}."""
````

#### Правка V11 — `vault/knowledge/decisions/модули-grid-сетка.md`

До:
````python
        """Проводимость правой граничной грани T_{N+1/2}."""
````

После:
````python
        """Проводимость правой граничной грани T_{N-1/2}."""
````

#### Правка V12 — `vault/knowledge/decisions/модули-grid-сетка.md`

До:
````markdown
r_{j+1/2} = r_w · (R_ext / r_w)^{j/N},   j = 0, 1, ..., N
```
r_faces[0] = r_w, r_faces[N] = R_ext.
````

После:
````markdown
r_{j-1/2} = r_w · (R_ext / r_w)^{j/N},   j = 0, 1, ..., N
```
r_faces[f] = r_{f-1/2}: r_faces[0] = r_{-1/2} = r_w, r_faces[N] = r_{N-1/2} = R_ext ([[DEBT-070]]).
````

#### Правка V13 — `vault/knowledge/decisions/модули-grid-сетка.md`

До:
````markdown
T_{1/2} = 2π · h · k / ln(r_0 / r_w)
T_{N+1/2} = 2π · h · k / ln(R_ext / r_{N-1})
````

После:
````markdown
T_{-1/2} = 2π · h · k / ln(r_0 / r_w)
T_{N-1/2} = 2π · h · k / ln(R_ext / r_{N-1})
````

#### Правка V14 — `vault/knowledge/decisions/свойства-фаз-на-контурной-грани-берутся-из-ГУ-при-притоке.md`

До:
````markdown
$$\bigl(\rho_\alpha, c_{p,\alpha}, \mu_{\mathrm{JT},\alpha}\bigr)_{N+1/2} =
\begin{cases}
\text{из ячейки } N-1, & \mathcal{Q}_{\alpha,N+1/2} \geqslant 0 \ \text{(отток)},\\
\text{при } (p_0, T_0, R_s^0), & \mathcal{Q}_{\alpha,N+1/2} < 0 \ \text{(приток)}.
\end{cases}$$
````

После:
````markdown
$$\bigl(\rho_\alpha, c_{p,\alpha}, \mu_{\mathrm{JT},\alpha}\bigr)_{N-1/2} =
\begin{cases}
\text{из ячейки } N-1, & \mathcal{Q}_{\alpha,N-1/2} \geqslant 0 \ \text{(отток)},\\
\text{при } (p_{\text{пл}}, T_{\text{пл}}, R_s^0), & \mathcal{Q}_{\alpha,N-1/2} < 0 \ \text{(приток)}.
\end{cases}$$

Обозначения — по постановке после [[DEBT-070]]: контурная грань $N - 1/2$, контурные значения $p_{\text{пл}}$, $T_{\text{пл}}$.
````

#### Правка V15 — `vault/knowledge/numerics/температура ячейки 0 — центр, не забой.md`

До:
````markdown
вклад забойной грани в $\mathcal J_0$ входит с весом $\Phi^+_{1/2} = 0$
````

После:
````markdown
вклад забойной грани в $\mathcal J_0$ входит с весом $\Phi^+_{-1/2} = 0$
````

#### Правка V16 — `vault/knowledge/numerics/температура ячейки 0 — центр, не забой.md`

До:
````markdown
К `J[0]` добавлено $\mu\Phi^-_{1/2}(p[0] - p_{wf})$:
````

После:
````markdown
К `J[0]` добавлено $\mu\Phi^-_{-1/2}(p[0] - p_{wf})$:
````

#### Правка V17 — `CLAUDE.md`

До:
````markdown
| $p_0$ | начальное пластовое давление |
````

После:
````markdown
| $p_0$ | начальное пластовое давление; в `numerical_solver/doc/problem_statement.tex` — $p_{\text{пл}}$, там $p_0$, $T_0$ — значения в ячейке 0 у забоя (DEBT-070) |
````

**Проверка после шага:** `--collect-only -q` — 1987 (документы). Grep в `vault/knowledge`: `T_{1/2}`, `T_{N+1/2}`, `N+1/2`, `Φ^±_{1/2}` для забоя — 0 (кроме `ΔT_{1/2}` — «JT полуячейки» в заметке BUG-015, это не индекс грани).

**Подводные камни:** V5 и V12 содержат строки с ``` внутри — в плане они в блоках ```` (четыре обратные кавычки); при Edit переносить содержимое без внешних кавычек. V17 — в CLAUDE.md другие строки не трогать (DEBT-062 правит раздел «Связь формула → код» — другой участок файла).

**Зависимости:** требует шаги 1–5 (описывает уже сделанное).

**Оценка:** 17 правок, ~15 мин.

### Шаг 7: Итог

**Цель:** полная проверка и запись результата.

**Что сделать:**
1. Полный прогон `.venv\Scripts\python -m pytest tests/ -q` (контракт `/implement`, ~10 мин): все passed, число — как в шаге 0.
2. Повторная сборка PDF (шаг 4, п. 1–3) на итоговом дереве.
3. Vault (делает `/implement`): статус DEBT-070, «План», комментарий `vault/issues/debt-070/05-comment-done.md` в issue #119 — что изменено (таблица соответствий старое → новое из шага 3), числа PDF, тесты.

**Оценка:** ~15 мин.

## 7. Тестовая стратегия

Новых тестов нет: задача меняет обозначения в тексте, а не поведение. Обоснование — сторожа, которые уже есть, плюс проверки шага 4:

**Тест:** `test_no_numeric_equation_or_line_references`, `test_label_references_exist_in_problem_statement`
**Файл:** `numerical_solver/tests/test_eq_references.py` (существующий)
**Сценарий:** изменённые комментарии `.py` и README 15 не вводят номеров уравнений/строк; метки, на которые ссылаются код и примеры, по-прежнему объявлены в `.tex`.
**Ожидание:** passed.
**Предотвращает:** случайное удаление или переименование `\label` при правке абзацев `ssec:bc_disc`.

**Тест:** быстрый уровень целиком
**Сценарий:** правки C1–C9 — только комментарии и докстринги.
**Ожидание:** все passed, число тестов 1987 / 1711 как в базе.
**Предотвращает:** синтаксическую ошибку в правленых строках (например, сломанная кавычка докстринга).

**Проверка без pytest** (проба плана и шаг 4): PDF собирается, неопределённых ссылок 0, запрещённых шаблонов 0, `ast` без докстрингов совпадает с базой.

Тест «в `.tex` нет старых индексов» в набор **не добавляется**: шаблоны вроде `_{\half}` законно встречаются для правой грани ячейки 0, и сторож с исключениями хрупок. Проверка — однократная, шагом 4.

## 8. Критерии завершения

- [ ] Правки T1–T44, C1–C13, V1–V17 применены (V-нумерация: 17 правок, включая CLAUDE.md)
- [ ] PDF: 40 страниц, 0 неопределённых ссылок, 0 `LaTeX Warning`, `Overfull` 17 (база 19)
- [ ] Запрещённые шаблоны шага 4 — 0
- [ ] Вычитка страниц таблицы обозначений, `ssec:grid`, `ssec:bc_disc` выполнена
- [ ] `test_eq_references.py` passed; быстрый уровень и итоговый полный — passed, число тестов не изменилось
- [ ] `ast` изменённых `.py` без докстрингов совпадает с базой
- [ ] Vault обновлён: словарь, заметки; статус DEBT-070
- [ ] Issue #119 прокомментирован с результатом; закрывается при `/merge`

## 9. Обнаруженные проблемы

1. **Словарь код ↔ физика, §3.1, формулы контурной грани:** подвижность — из ячейки $N-1$ безусловно, а код и постановка берут её против потока (при притоке — при условиях контура). Не блокирует; исправляется попутно правкой V5 (та же область заметки).
2. **Номера уравнений и параграфов в заметках `vault/knowledge/`:** 24 вхождения в 9 заметках — «(eq. 10)», «(eq. 13)», «уравнение 74», «§4.1» и т. п. (в том числе `модули-grid-сетка.md`, `свойства-фаз-на-контурной-грани-…md`, которые правит этот план). Сторож DEBT-010 проверяет только `numerical_solver/`, vault — нет; номера уже разошлись с документом. Не блокирует; в этом плане **не трогаем** (правки V не задевают эти строки). Зарегистрирована отдельной задачей **DEBT-074** (реестр, 2026-10-14; без issue).

## 10. Связь с другими задачами

- [[BUG-015]] — источник находки; его абзац о забойной грани (1935–1969) правится T26–T28.
- [[DEBT-062]] — влит (`aecd1e4`); соседние строки в `test_energy_matrix_examples.py` и другой раздел `CLAUDE.md` (раздел 4).
- [[BUG-029]] — запись реестра пишет $\mathcal{T}_{1/2}$; читать как $\mathcal{T}_{-1/2}$ после DEBT-070; правка записи не нужна (снимок на дату).
- [[DEBT-062]], [[DEBT-010]] — сторож ссылок; метки этот план не меняет.

## Связанные заметки

- `vault/knowledge/decisions/словарь-код-физика.md` — индексация, §1, §3.1, §6, §9
- `vault/knowledge/decisions/модули-grid-сетка.md`
- `vault/knowledge/decisions/конвенции-знаков.md` — знаки потоков (не меняются)
- `vault/knowledge/numerics/температура ячейки 0 — центр, не забой.md`
- Issue: [#119](https://github.com/ArturSalamatin/Oil_Gas/issues/119), тело — `vault/issues/debt-070/01-issue-body.md`
