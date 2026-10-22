---
tags:
  - план
  - баг
date: 2026-10-10
issue: BUG-027
github: 97
branch: fix/bug-027/tex-conductive-face-mean
status: реализован
worktree: .worktrees/bug-027; удалён после влития
merged: 6aaf9e9 (2026-10-11)
audit:
  date: 2026-10-10
  found: 11
  auto-fixed: 9
  manual-required: 2
---

# BUG-027: в постановке остался двойной ln BUG-002 — нормировать веса гармонического среднего

## Кратко

- **Дефект.** `numerical_solver/doc/problem_statement.tex` записывает гармоническое среднее на грани с **ненормированными** логарифмическими весами: `eq:face_interp` $A_{j+1/2} = (w_L/A_j + w_R/A_{j+1})^{-1}$ и такое же $\lambda^{j+1/2}$ под `eq:heat_cond_disc`. При однородном $\lambda$ это «среднее» равно $\lambda/\ln(r_{j+1}/r_j)$, а не $\lambda$. Поток `eq:heat_cond_disc` делит его ещё раз на $\ln(r_{j+1}/r_j)$, и логарифм оказывается в знаменателе дважды. Поток документа в $1/\ln(r_{j+1}/r_j)$ раз больше верного: на сетке примера 14 — в **46** раз (замер, раздел 1). Код решателя верен: BUG-002 (2026-09-01) исправил его, а документ — нет.
- **Что делается** (вариант 3 issue #97):
  - `eq:face_interp` и среднее под `eq:heat_cond_disc` — с множителем $\ln(r_{j+1}/r_j)$, то есть с нормированными весами;
  - под `eq:heat_cond_disc` — тождество с последовательными сопротивлениями двух кольцевых слоёв (форма кода) и проверка однородным $\lambda$;
  - попутно: под `eq:tridiag_d` знаменатель $\ln(r_{j\pm1}/r_j)$ для левой грани отрицателен, хотя проводимость объявлена положительной — исправляется; фраза о знаке $Q_\lambda$ стоит до «где» — переставляется;
  - тесты, записавшие ту же ошибку: `TestHarmonicInterpolation` (`tests/test_grid.py`) утверждает «$\lambda_{face} = \lambda/\ln$» и в комментарии повторяет двойной ln — переписывается на нормированное среднее с проверкой свойства среднего; новый быстрый тест-самопроверка эталона `_ref_conductive` против точного решения в кольце;
  - докстринги и комментарии: `_ref_conductive`, `test_energy.py`, `test_val002.py`; заметки vault.
- **Код решателя не меняется.** Правки — в `.tex`, в тестах (две проверки переписаны, одна добавлена) и в vault. Числа, истории, графики — те же.
- **Шагов:** 6 (0 — подготовка, 5 — итог). Тестов +1 (1688 → 1689 на базе `b94e7d3` — после влития VAL-004; на `a020f64` было 1679 → 1680; быстрый уровень 1417 → 1418).
- **Оценка:** ~1 ч 15 мин, из них ~10 мин — полный прогон.

## Как начать работу по этому плану

1. Прочитай этот файл целиком, затем запись BUG-027 в [[известные баги и технический долг]] и issue #97 (`gh issue view 97 --repo ArturSalamatin/Oil_Gas`).
2. Ветка от базовой — в worktree, как делает `/implement`:
   ```powershell
   git worktree add .worktrees/bug-027 -b fix/bug-027/tex-conductive-face-mean numerical_scheme/implementation
   ```
3. Переменные (PowerShell). В worktree `.venv` нет — берётся интерпретатор основного каталога. pytest из `$WT` берёт пакет worktree (память проекта `reference_worktree_pythonpath`). Пробы считают пути от текущего каталога (`SOLVER = Path.cwd()`) и печатают первой строкой `Код: …` — запускать **из `$WT`**:
   ```powershell
   $PY   = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   $ROOT = "D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\bug-027"     # корень worktree
   $WT   = "$ROOT\numerical_solver"                                    # отсюда pytest и пробы
   $P    = "$ROOT\vault\issues\bug-027\probes"                         # пробы — в worktree (их коммитит /implement до ветвления)
   ```
4. Базовое состояние — шаг 0. **Прототип `HydroSolverPrototype/` план не трогает** — тесты и регрессия прототипа не нужны.
5. После каждого шага — проверка шага и регресс по полю «Регресс». Полный прогон — шаг 5.
6. Точки коммитов (на ветке задачи; формат — CLAUDE.md, «Коммиты»; stage по имени файла; vault — отдельно от кода):
   - после шага 2 — `docs: problem_statement — нормированные веса гармонического среднего, один ln в кондуктивном потоке (BUG-027)`: `numerical_solver/doc/problem_statement.tex`;
   - после шага 4 — `test: кондуктивная проводимость — нормированное среднее, самопроверка эталона (BUG-027)`: `numerical_solver/tests/test_grid.py`, `numerical_solver/tests/test_energy_matrix_examples.py`, `numerical_solver/tests/test_energy.py`, `numerical_solver/tests/test_val002.py`;
   - после шага 5 — `vault: двойной ln снят из постановки и заметок (BUG-027)`: заметки `vault/knowledge/` из шага 5;
   - реестр, план, пробы — как требует `/implement`.

## Порядок влития

План написан на `a020f64` (после влития DEBT-010): тестов 1679, быстрый уровень 1417 passed (94 с). К концу планирования база ушла на `7309f67` (VAL-004 — начало реализации, только vault). **Аудит 1 (2026-10-10) — на `b94e7d3`:** влит VAL-004 (`11ea42d`, +9 slow-тестов `tests/test_val004.py`) — тестов 1688, быстрый уровень 1417; файлы плана с `a020f64` не менялись (`git diff --stat a020f64 b94e7d3` — только `test_val004.py` и заметка VAL-004). Номера строк ниже — на `a020f64`; после чужих влитий они сдвинутся — **правки по тексту, не по номерам** (проба `tex_apply.py` ищет «до» по тексту и требует единственности).

| Задача | Состояние на 2026-10-10 | Пересечение с BUG-027 |
|---|---|---|
| **VAL-004** (#90) | влит (`11ea42d`) | Добавил `tests/test_val004.py` (9 slow) — база 1688. Файлов BUG-027 не трогал. |
| **DEBT-059** (#94) | реализуется (`.worktrees/debt-059`) | Правит `pyproject.toml`, `tests/conftest.py` (подключение прототипа), скрипты примеров, добавляет `tests/test_packaging.py`. Файлов BUG-027 не трогает; пробы BUG-027 прототип не импортируют (фабрика импортирует его лениво). После влития число тестов больше — прирост от BUG-027 по-прежнему +1. |
| **DEBT-014** (#95) | план готов | Конфиги, README, −1 тест. Пересечений нет. |
| **BUG-024** (#93), **DEBT-048** (#78) | планы готовы | Правят комментарии `test_energy_matrix_examples.py` у `SUBDIVIDING_EXAMPLES` (~`:764`, `:854-872`). BUG-027 вставляет тест после `_ref_conductive` (~`:303`) — их строки сдвинутся на ~55, правки по тексту не пересекаются. |
| **DEBT-060** (#96) | план готов (на `7309f67`) | `.tex`: добавляет **нумерованное** `eq:cell_center_def` у `:938` — номера всех уравнений ниже, в том числе `eq:face_interp` (43 → 44) и `eq:heat_cond_disc` (60 → 61), сдвигаются на +1, страницы — возможно. Блоки BUG-027 от этого не меняются (ссылки — `\eqref`), но ожидания шага 2в «(43) на с. 15, (60) на с. 19–20» — сверять по метке, а сравнение номеров с базой — с той базой, от которой ветвится worktree. `tests/test_grid.py`: DEBT-060 правит `:76-81`, `:190-191`, `:306-309` и переименовывает `TestCenterMassVerification` → `TestCellCenterLogAverage`; BUG-027 — `TestHarmonicInterpolation` (`:331-388`), соседние, но разные участки. Vault: DEBT-060 правит `модули-grid-сетка.md:96` и строку 30 словаря, BUG-027 — `:142` и `:328`. Конфликтов по строкам нет; кто вливается вторым — проверяет сборку `.tex` и `test_grid.py` на слитом дереве. |
| **DEBT-062** (новая, раздел 7) | зарегистрирована | Убирает «(74)» в `test_energy_matrix_examples.py:238, 306, 716`; `:306` — первая строка после вставки BUG-027. Конфликт возможен, разрешается тривиально (обе правки). |

## 1. Замеры при планировании (`a020f64`)

**Проба формы проводимости** `vault/issues/bug-027/probes/conductive_forms.py` (вывод — `conductive_forms_before.txt`): три формы $Q^T_{j+1/2}$ против кода на двух сетках.

| Сетка | $\ln(r_{j+1}/r_j)$ | старая запись / код | новая запись / код − 1 | среднее новой формы в $[\lambda_{\min}, \lambda_{\max}]$ | старое «среднее» |
|---|---|---|---|---|---|
| пример 14 ($r_w = 0.1$, $R_{ext} = 200$, $N = 350$) | 0.02172 | **46.047** | $\le 2.2\cdot10^{-16}$ | да, выход $\le 1.2\cdot10^{-14}$ | больше $\lambda_{\max}$ на 17…45 |
| `test_grid` ($R_{ext} = 500$, $N = 50$) | 0.1703 | 5.870 | $\le 2.2\cdot10^{-16}$ | да, выход $\le 9\cdot10^{-16}$ | больше $\lambda_{\max}$ на 1.2…4.9 |

Однородная $\lambda = 1.228$ и ступенька $1.228 \mid 0.3$ дают одинаковые отношения. Анализ размерностей ошибку не ловит: веса безразмерны, и $(w_L/\lambda_L + w_R/\lambda_R)^{-1}$ имеет размерность $\lambda$.

**Допуск свойства «среднее между соседями» — $10^{-12}$, не $10^{-15}$.** $\ln(r_{j+1}/r_j)$ из центров и $w_L + w_R$ из граней расходятся на $\sim 10^{-16}$ абсолютно, при $\ln = 0.02$ это $\sim 10^{-14}$ относительно. Первый прогон пробы с допуском $10^{-15}$ на сетке примера 14 дал ложное «нет».

**Проба кода тестов** `plan_tests_check.py` (вывод — `plan_tests_check.out.txt`): копии тестов шага 3 — 4 зелёных на текущем коде; те же проверки против записи документа до BUG-027 — все 4 краснеют (8 passed, из них 4 — `pytest.raises(AssertionError)`).

**Проба правок `.tex`** `tex_apply.py`: блоки шагов 1–2 применены к копии `problem_statement.tex` и собраны тремя проходами `pdflatex`:
- каждое «до» найдено ровно 1 раз;
- сборка без ошибок и предупреждений, 37 страниц, как у базы (локальный `doc/problem_statement.pdf` устарел: 35 страниц, PDF не в git);
- номера всех 144 меток `eq:`/`sec:`/`ssec:` совпадают с базой — выключные формулы добавлены без номера (`\[…\]`);
- новых переполнений строк (Overfull) нет; первые варианты текста давали 8.9 pt и 0.8 pt — переписаны, итоговые блоки ниже;
- страницы 15 (`eq:face_interp`, (43)), 19–20 (`eq:heat_cond_disc`, (60)) и 23 (`eq:tridiag_d`) просмотрены.

**Тесты:** `pytest tests/ --collect-only -q` — 1679; `-m "not slow"` — 1417 passed, 262 deselected, 94 с. На `b94e7d3` (аудит 1): 1688 собрано, 1417 в быстром уровне.

**Проба текста плана** `plan_apply_check.py` (аудит 1, на `b94e7d3`; запуск из `numerical_solver/`): блоки «До/После» шагов 3–4 берутся **из этого файла как есть** и применяются к копии `tests/` (`probes/tree/`, удаляется в конце), `.tex` — пробой `tex_apply.py`. Итог: 8 пар «до/после» и вставка нового теста легли на свои строки (`test_grid.py:354, 371, 381`, `test_energy_matrix_examples.py:54, 257, 293`, вставка после `:302`, `test_energy.py:688`, `test_val002.py:322`); на копии зелёные `TestHarmonicInterpolation` (3), новый тест и самопроверка JT (2), `TestComputeConductiveTransmissibility` (3), `single_ln` (1), сторож DEBT-010 против исправленного `.tex` (2); тестов в четырёх файлах 78/26/45/18 → 78/27/45/18; негатив (эталон без множителя $w_L + w_R$) — новый тест красный. При реализации пробу можно прогнать до шага 3 — она покажет, легли ли блоки на дерево worktree.

## 2. Причинно-следственная цепочка

1. **Запись** (`d9a33ab1`, 2026-08-20): `eq:face_interp` — гармоническое среднее с весами $w_L = \ln(r_{j+1/2}/r_j)$, $w_R = \ln(r_{j+1}/r_{j+1/2})$ без деления на их сумму. Для «интерполяции» это не среднее: среднее однородного поля обязано равняться самому полю.
2. **Перенос в поток** (`97aeefd0`, `d95dc9a6`, 2026-08-24): под `eq:heat_cond_disc` то же среднее, а сам поток содержит геометрический множитель $2\pi h/\ln(r_{j+1}/r_j)$. Вместе: $Q = 2\pi h\lambda\Delta T/\ln^2$.
3. **Код** (до 2026-09-01) реализовал документ буквально — BUG-002: порядок сходимости VAL-002 0.5 (после исправления — 1.28). Исправление `129d90a` перевело код на последовательные сопротивления $2\pi h/(w_L/\lambda_L + w_R/\lambda_R)$ и затронуло только `energy/tridiag.py`, `tests/test_energy.py`, `tests/test_val002.py`. **План BUG-002 правку документа предусматривал** — шаг 4 [[bug-002 double-ln-conductive]] («Обновить problem_statement.tex»: форма последовательных сопротивлений, то есть вариант 2 этого плана). Шаг выпал при реализации: `.tex` в коммите нет, пункт критериев «`problem_statement.tex` компилируется» остался неотмеченным. Там же (`:57`) записано прочтение, на котором стоит этот план: `eq:heat_cond_disc` подразумевает **нормированное** среднее.
4. **Следы в тестах и заметках.** `TestHarmonicInterpolation` (`tests/test_grid.py:331-388`, написан до BUG-002) утверждает $\lambda_{face} = \lambda/\ln(r_{j+1}/r_j)$ и в комментарии `:354-356` повторяет двойной ln. `test_energy.py:693` называет ненормированное среднее «lambda_face». `test_val002.py:324` описывает код до BUG-002 как текущий. Заметки `модули-energy-tridiag.md:116-128`, `модули-grid-сетка.md:138-142` — та же запись. Эталон `_ref_conductive` (DEBT-016) считает верно, но объявляет, что следует «форме документа», которой в `.tex` нет.
5. **Проявление.** В расчётах — нигде. В документе-постановке для заказчика — формула, повторяющая BUG-002 у любого, кто реализует схему по ней. Документ противоречит сам себе: поток через контур (`:1912-1917`) записан верно, с одним ln.

## 3. Целевое состояние

- `eq:face_interp`: $A_{j+1/2} = \ln(r_{j+1}/r_j)\big/\bigl(w_L/A_j + w_R/A_{j+1}\bigr)$. В тексте — $w_L$, $w_R$ и их нормировка; среднее однородного поля равно ему самому и в общем случае лежит между $A_j$ и $A_{j+1}$.
- Под `eq:heat_cond_disc`: то же среднее со ссылкой на `eq:face_interp`; подстановка даёт $Q = 2\pi h\,\Delta T/(w_L/\lambda_j + w_R/\lambda_{j+1})$ — последовательные сопротивления (форма кода); при однородной $\lambda$ — $2\pi h\lambda\Delta T/\ln(r_{j+1}/r_j)$, согласовано с потоком через контур.
- Под `eq:tridiag_d`: проводимость правой грани с $\ln(r_{j+1}/r_j)$, левой — с $\ln(r_j/r_{j-1}) > 0$.
- Метки и номера уравнений не меняются (на них ссылаются код и тест-сторож DEBT-010).
- Тесты фиксируют: среднее по `eq:face_interp` при однородной $\lambda$ равно $\lambda$, при неоднородной лежит между соседями; эталон `_ref_conductive` и решатель дают точное решение в кольце (однородная $\lambda$ и два слоя). Ни один тест и комментарий не называет $\lambda/\ln$ средним.
- Вывод решателя побитово прежний (код решателя не меняется).

## 4. Варианты (выбран 3 — issue #97)

| Вариант | Суть | Почему нет / да |
|---|---|---|
| 1 | Нормировать веса в `eq:face_interp` и в среднем под `eq:heat_cond_disc` | Минимальная правка, `:1638` для правой грани верна; но связь с формой кода остаётся неочевидной. |
| 2 | Убрать $1/\ln$ из потока: $Q = 2\pi h\,\Delta T/(w_L/\lambda_j + w_R/\lambda_{j+1})$ | Документ = код буквально, но `eq:face_interp` всё равно нужно нормировать (текст называет её средним), `:1638` переписывать, эталон DEBT-016 переводить на форму кода — сверка теряет независимость формы. Отклонён. Этот вариант предлагал невыполненный шаг 4 плана BUG-002 (до DEBT-016, когда требования «эталон — в форме документа» ещё не было). |
| **3** | **1 + строка о последовательных сопротивлениях и проверка однородной $\lambda$; попутные правки `:1378`, `:1638`** | **Выбран.** Плюсы 1 + явная связь с кодом и записанная в тексте проверка предельного случая. |
| — | Тест, читающий `.tex` и проверяющий числитель `eq:face_interp` | Хрупок к форматированию LaTeX; защита от повтора — эталон `_ref_conductive`, который следует документу, и его самопроверка (шаг 3). Отклонён. |

## 5. Подводные камни

- ✅ **Побочные эффекты.** Код решателя не меняется. `compute_conductive_transmissibility` (`gpn_multiphase_solver/energy/tridiag.py:329`) — только читается тестами.
- ✅ **Метки.** `eq:face_interp`, `eq:heat_cond_disc`, `ssec:bc_disc` сохраняются; `tests/test_eq_references.py::test_label_references_exist_in_problem_statement` проверяет это на шаге 2.
- ✅ **Номера уравнений.** Новые выключные формулы — `\[…\]` без номера; замер: 144 метки, номера совпадают с базой.
- ⚠️ **Тест-сторож DEBT-010 по докстрингам.** Запрещены «eq. N», «ур. N», «.tex:N», «.tex, строки…». Новые докстринги ссылаются только метками (`eq:face_interp`, `eq:heat_cond_disc`, `ssec:bc_disc`) — шаг 4 проверяет сторож.
- ⚠️ **Допуск в тестах.** $10^{-12}$, не меньше (раздел 1).
- ✅ **Граничные случаи.** $\lambda = 0$ (примеры 01–09): эталон считает по маске $\lambda > 0$, в тест не входит (это отдельная ветка `_ref_conductive`, её покрывает сверка матрицы). $N = 1$: внутренних граней нет — тест строит $N = 20$.
- ✅ **Производительность.** Новый тест — без фикстуры `results`, < 0.1 с, уровень быстрый.
- ✅ **Обратная совместимость.** Вывод решателя, истории, графики — без изменений.
- ⚠️ **PDF.** `doc/problem_statement.pdf` не в git. В worktree собирается заново (шаг 2); основной каталог после влития хранит старый PDF (35 страниц, до DEBT-056 и BUG-022) — пересобрать там после `/merge` (шаг 5, п. 6).
- ⚠️ **Параллельные задачи.** Раздел «Порядок влития».
- ✅ **Прототип** не меняется.
- ✅ **Соответствие формулам.** После правки документ, эталон и код совпадают по значению (проба: $2.2\cdot10^{-16}$).

## Шаг 0. Подготовка

**Цель:** worktree, базовое состояние, пробы «до».
**Файлы:** — (пробы уже лежат в `vault/issues/bug-027/probes/`).

**Что сделать:**
1. Создать worktree и переменные («Как начать», пп. 2–3).
2. Базовое состояние:
   ```powershell
   Set-Location $WT
   & $PY -m pytest tests/ --collect-only -q | Select-Object -Last 1
   & $PY -m pytest tests/ -m "not slow" -q | Select-Object -Last 2
   ```
   Ожидание на `b94e7d3`: 1688 тестов, 1417 passed (~95 с). Если база ушла (DEBT-059, DEBT-014, DEBT-060 и др.) — записать фактические числа; ожидаемый прирост от плана +1 в обоих.
3. Пробы «до» — из `$WT`:
   ```powershell
   & $PY "$P\conductive_forms.py"
   & $PY -m pytest "$P\plan_tests_check.py" -q -s -p no:cacheprovider -W ignore::pytest.PytestUnknownMarkWarning
   & $PY "$P\tex_apply.py" doc\problem_statement.tex
   & $PY "$P\plan_apply_check.py"
   ```
   Ключ `-s` нужен, чтобы pytest не перехватил строку `Код: …` пробы.
   Ожидание: первая строка `Код: …\.worktrees\bug-027\numerical_solver\gpn_multiphase_solver\__init__.py`; числа — как в `conductive_forms_before.txt` (старая/код 46.0472 и 5.87048); `8 passed`; `plan_apply_check.py` — как в разделе 1 (8 пар, все проверки ✓, негатив красный, «копия удалена»); `tex_apply.py` — три строки ««до» найдено 1 раз» (A — строка 1034, B — 1381, C — 1663: номера B и C считаются в тексте **после** предыдущих замен; на исходном файле B — 1374, C — 1638).

**Проверка:** числа записаны; все три «до» единственны.
**Регресс:** быстрый (это и есть базовый вариант).
**Оценка:** ~5 мин.

## Шаг 1. `eq:face_interp` — нормированные веса (минимальный фикс)

**Цель:** среднее на грани — настоящее среднее.
**Файлы:** `numerical_solver/doc/problem_statement.tex`, абзац «Интерполяция скалярных свойств» (`:1030-1039`).

**Контекст:** при $A_j = A_{j+1} = A$ текущая формула даёт $A/(w_L + w_R) = A/\ln(r_{j+1}/r_j)$. На неё ссылается `eq:heat_cond_disc`. Метка остаётся, номер (43) — тоже.

**Изменения** (блок A пробы `tex_apply.py`; строки 1030–1033 — заголовок абзаца и «…логарифмическими весами:» — не меняются):

До:
```latex
\begin{equation}\label{eq:face_interp}
  A_{j+\half} = \frac{1}{\dfrac{\ln(r_{j+\half}/r_j)}{A_j}
    + \dfrac{\ln(r_{j+1}/r_{j+\half})}{A_{j+1}}}.
\end{equation}
Логарифмические веса корректны для радиальной геометрии
(аналогия с~последовательными сопротивлениями в~кольцевых слоях).
```
После:
```latex
% BUG-027: до исправления в числителе стояла единица — веса не нормированы,
% при A_j = A_{j+1} = A «среднее» равнялось A/ln(r_{j+1}/r_j), и поток
% eq:heat_cond_disc получал ln^2 в знаменателе (дефект BUG-002 в постановке).
\begin{equation}\label{eq:face_interp}
  A_{j+\half} = \frac{\ln(r_{j+1}/r_j)}{\dfrac{\ln(r_{j+\half}/r_j)}{A_j}
    + \dfrac{\ln(r_{j+1}/r_{j+\half})}{A_{j+1}}}.
\end{equation}
Логарифмы $w_L = \ln(r_{j+\half}/r_j)$ и~$w_R = \ln(r_{j+1}/r_{j+\half})$
в~сумме дают $\ln(r_{j+1}/r_j)$, поэтому веса $w_L/(w_L + w_R)$
и~$w_R/(w_L + w_R)$ нормированы на~единицу: при~$A_j = A_{j+1} = A$
среднее равно~$A$, в~общем случае оно лежит между~$A_j$ и~$A_{j+1}$.
Логарифмические веса корректны для радиальной геометрии
(аналогия с~последовательными сопротивлениями в~кольцевых слоях).
```

Обозначения $w_L$, $w_R$ совпадают с кодом (`grid.log_weights_left`, `grid.log_weights_right`) и словарём vault (раздел 5.4). Комментарий `% BUG-027` — по образцу `% BUG-015` (`:1782`).

**Что сделать:** применить вручную (Edit) или пробой: из `$WT` — `& $PY "$P\tex_apply.py" doc\problem_statement.tex doc\problem_statement.tex` применяет **все три** блока (A, B, C) сразу; тогда шаг 2 сводится к проверке и сборке. Проба отказывается писать, если хоть одно «до» не единственно.

**Проверка после шага:**
- `Select-String -Path doc\problem_statement.tex -Pattern 'frac\{1\}\{\\dfrac\{\\ln\(r_\{j\+\\half\}/r_j\)\}\{A_j\}'` — пусто (старого числителя нет).
- Регресс: `--collect-only -q` (меняется только документ) — число тестов прежнее.

**Подводные камни:** «Метки», «Номера уравнений».
**Зависимости:** требует шаг 0. Блокирует: шаг 2.
**Оценка:** ~10 строк, ~5 мин.

## Шаг 2. `eq:heat_cond_disc` и проводимость под `eq:tridiag_d`; сборка PDF

**Цель:** поток с одним ln, связь с формой кода, верный знак знаменателя левой грани.
**Файлы:** `numerical_solver/doc/problem_statement.tex` — абзац «Кондуктивный поток через грань» (`:1371-1384`) и фраза под `eq:tridiag_d` (`:1638-1639`).

### 2а. Кондуктивный поток (блок B)

До (`:1374-1384`):
```latex
\begin{equation}\label{eq:heat_cond_disc}
  Q_{\lambda,j+\half} = \frac{2\pi\,h}{\ln(r_{j+1}/r_j)}\,
    {\leff}^{j+\half}\,(T_j - T_{j+1}),
\end{equation}
$Q_\lambda > 0$~--- поток тепла от~скважины (в~сторону роста~$r$).
где~${\leff}^{j+\half}$~--- гармоническое среднее
с~логарифмическими весами (ср.~\eqref{eq:face_interp}):
\[
  {\leff}^{j+\half} =\left( \dfrac{\ln(r_{j+\half}/r_j)}{{\leff}_j}
    + \dfrac{\ln(r_{j+1}/r_{j+\half})}{{\leff}_{j+1}}\right)^{-1}.
\]
```
После:
```latex
\begin{equation}\label{eq:heat_cond_disc}
  Q_{\lambda,j+\half} = \frac{2\pi\,h}{\ln(r_{j+1}/r_j)}\,
    {\leff}^{j+\half}\,(T_j - T_{j+1}),
\end{equation}
где~${\leff}^{j+\half}$~--- гармоническое среднее
с~логарифмическими весами~\eqref{eq:face_interp}:
\[
  {\leff}^{j+\half} = \ln(r_{j+1}/r_j)
    \left( \dfrac{\ln(r_{j+\half}/r_j)}{{\leff}_j}
    + \dfrac{\ln(r_{j+1}/r_{j+\half})}{{\leff}_{j+1}}\right)^{-1};
\]
$Q_\lambda > 0$~--- поток тепла от~скважины (в~сторону роста~$r$).
Подстановка среднего в~\eqref{eq:heat_cond_disc} сокращает
$\ln(r_{j+1}/r_j)$:
\[
  Q_{\lambda,j+\half}
  = \frac{2\pi h\,(T_j - T_{j+1})}
    {\ln(r_{j+\half}/r_j)/{\leff}_j + \ln(r_{j+1}/r_{j+\half})/{\leff}_{j+1}},
\]
то~есть тепловые сопротивления двух кольцевых слоёв
$[r_j, r_{j+\half}]$ и~$[r_{j+\half}, r_{j+1}]$ складываются
последовательно. При~однородной теплопроводности поток совпадает
с~потоком стационарного решения $T = C_1\ln r + C_2$ в~кольце
$[r_j, r_{j+1}]$:
\[
  Q_{\lambda,j+\half} = \frac{2\pi h\,\leff\,(T_j - T_{j+1})}{\ln(r_{j+1}/r_j)};
\]
так~же, с~одним логарифмом, записан поток через контур
(раздел~\ref{ssec:bc_disc}).
```

Почему так:
- фраза «$Q_\lambda > 0$ …» стояла между формулой и «где» — теперь после определения среднего;
- «ср.~\eqref» → прямая ссылка: это то же среднее, а не сравнимое;
- $C_1$, $C_2$ вместо $A$, $B$ — $A$ занята в `eq:face_interp`;
- форма раздела `ssec:bc_disc` — «(раздел~\ref{…})», как в `:951`.

### 2б. Проводимость под `eq:tridiag_d` (блок C)

До (`:1638-1639`):
```latex
Здесь $Q_{\lambda,j\pm\half}^T = 2\pi h\,{\leff}^{j\pm\half}/
\ln(r_{j\pm 1}/r_j)$~--- кондуктивная проводимость ($>0$);
```
После:
```latex
Здесь $Q_{\lambda,j+\half}^T = 2\pi h\,{\leff}^{j+\half}/
\ln(r_{j+1}/r_j)$~--- кондуктивная проводимость грани~$j{+}\half$ (\mbox{$>0$});
для~грани~$j{-}\half$~--- то~же с~заменой $j \to j-1$, знаменатель
$\ln(r_j/r_{j-1})$ тоже положителен;
```

Почему: при знаке «−» $\ln(r_{j-1}/r_j) < 0$ — проводимость по записи отрицательна, а текст и $a_j \le 0$ требуют $> 0$. `\mbox{$>0$}` — иначе TeX переносит строку между «>» и «0» (видно на с. 23 при сборке пробы). Следующая строка (`$\Phi_{j+\half}^{+} = …$`) не меняется.

### 2в. Сборка

```powershell
Set-Location "$WT\doc"
1..3 | ForEach-Object { pdflatex -interaction=nonstopmode problem_statement.tex | Out-Null }
Select-String -Path problem_statement.log -Pattern "^!|Warning|undefined|Output written" | ForEach-Object { $_.Line }
Set-Location $WT
```
Три прохода: после первого `longtable` и метки просят повтор (замер). Ожидание: только `Output written on problem_statement.pdf (37 pages, …)`. Overfull — те же 18 строк, что у базы (`Select-String -Pattern Overfull` — 5 у `alignment` 75.08 pt и 13 у абзацев; новых нет). `.aux`, `.log`, `.pdf` — в `.gitignore`.

Просмотр (Read по PDF): с. 15 — (43) с $\ln(r_{j+1}/r_j)$ в числителе, абзац про $w_L$, $w_R$; с. 19–20 — (60), среднее с множителем, формула последовательных сопротивлений, выключная формула однородного случая; с. 23 — текст под (72).

**Проверка после шага:**
- `& $PY "$P\tex_apply.py" doc\problem_statement.tex` — **все три «до» найдено 0 раз** и отказ «не единственно»: старых блоков в файле нет (ожидаемо после правки).
- `& $PY -m pytest tests/test_eq_references.py -q` — 2 passed (метки на месте).
- Регресс: `--collect-only -q` — число тестов прежнее.

**Подводные камни:** «Метки», «Номера уравнений», «PDF».
**Зависимости:** требует шаг 1. Блокирует: шаг 3 (тесты ссылаются на исправленный текст документа).
**Оценка:** ~35 строк `.tex`, ~15 мин (с тремя проходами LaTeX по ~30 с).

**Коммит** (после шага 2): `docs: problem_statement — нормированные веса гармонического среднего, один ln в кондуктивном потоке (BUG-027)`.

## Шаг 3. Тесты: среднее по `eq:face_interp` и самопроверка эталона

**Цель:** тесты проверяют свойства среднего и точное решение в кольце, а не записывают двойной ln.
**Файлы:** `numerical_solver/tests/test_grid.py` (`TestHarmonicInterpolation`, `:331-388`), `numerical_solver/tests/test_energy_matrix_examples.py` (импорт `:54-56`, новый тест после `_ref_conductive`, `:302`).

### 3а. `test_grid.py`, `test_heat_flux_analytic` (`:354-369`)

**Контекст.** Тест вычисляет `lam_face = lam / (w_L + w_R) * (w_L + w_R)` и не использует; поток берёт как `2πhλ/log_ratio` — веса сетки вообще не проверяются, хотя класс называется «Проверка log_weights». Комментарий `:354-356` записывает двойной ln. Комментарий `:345-352` (вывод аналитики) верен — не меняется.

До:
```python
        # Через log_weights: λ_face = 1 / (w_L/λ + w_R/λ) = λ / (w_L + w_R)
        # Кондуктивная проводимость: Q_T_f = 2πh / ln(r_c[j+1]/r_c[j]) · λ_face
        # Q_face = Q_T_f · (T[j+1] - T[j])

        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        lam_face = lam / (w_L + w_R) * (w_L + w_R)  # = λ для постоянного λ

        for f in range(grid.N - 1):
            log_ratio = np.log(grid.r_centers[f + 1] / grid.r_centers[f])
            Q_T = 2 * np.pi * grid.h * lam / log_ratio
            dT = T_centers[f + 1] - T_centers[f]
            Q_face = Q_T * dT
            # dT = ln(r[f+1]) - ln(r[f]) = log_ratio → Q_face = 2πhλ
            assert Q_face == pytest.approx(
                2 * np.pi * grid.h * lam, rel=1e-10), f"face {f}"
```
После:
```python
        # Через log_weights (BUG-027): сопротивления двух кольцевых слоёв
        # [r_j, r_{j+1/2}] и [r_{j+1/2}, r_{j+1}] складываются,
        # Q_T_f = 2πh / (w_L/λ + w_R/λ) = 2πhλ / (w_L + w_R), и
        # w_L + w_R = ln(r_c[j+1]/r_c[j]) — в знаменателе один ln. Запись
        # «2πh/ln · 1/(w_L/λ + w_R/λ)» (ненормированное «среднее» λ/ln под
        # вторым ln) — дефект BUG-002; до BUG-027 она стояла и в этом
        # комментарии, и в постановке.
        # Q_face = Q_T_f · (T[j+1] - T[j])

        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        Q_T = 2 * np.pi * grid.h / (w_L / lam + w_R / lam)    # [N-1], Вт/К

        for f in range(grid.N - 1):
            dT = T_centers[f + 1] - T_centers[f]
            Q_face = Q_T[f] * dT
            # dT = ln(r[f+1]) - ln(r[f]) = w_L + w_R → Q_face = 2πhλ
            assert Q_face == pytest.approx(
                2 * np.pi * grid.h * lam, rel=1e-10), f"face {f}"
```

### 3б. `test_grid.py`, `test_harmonic_mean_nontrivial` (`:371-379`)

**Контекст.** Проверяет только «положительно и конечно» — этому удовлетворяет и ненормированная форма. Свойство, отличающее среднее, — оно лежит между соседями. Старая форма его нарушает в 5.9 раза (проба `plan_tests_check.py`, `test_mean_between_red_on_old_doc`).

До:
```python
    def test_harmonic_mean_nontrivial(self, grid):
        """Гармоническое среднее с log_weights для неоднородного λ: положительное, конечное."""
        lam_cells = 1.0 + np.arange(grid.N, dtype=float)
        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        lam_face = 1.0 / (w_L / lam_cells[:-1] + w_R / lam_cells[1:])

        assert np.all(lam_face > 0)
        assert np.all(np.isfinite(lam_face))
```
После:
```python
    def test_harmonic_mean_nontrivial(self, grid):
        """Среднее eq:face_interp при неоднородном λ лежит между λ_j и λ_{j+1}.

        Проверяется свойство среднего, а не только знак. Ненормированная форма
        1/(w_L/λ_j + w_R/λ_{j+1}) — запись постановки до BUG-027 — в
        1/ln(r_{j+1}/r_j) ≈ 5.9 раза больше верного среднего на этой сетке и
        выходит за max(λ_j, λ_{j+1}).
        """
        lam_cells = 1.0 + np.arange(grid.N, dtype=float)    # растёт: λ_j < λ_{j+1}
        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        lam_face = (w_L + w_R) / (w_L / lam_cells[:-1] + w_R / lam_cells[1:])

        assert np.all(np.isfinite(lam_face))
        # Допуск 1e-12 — запас на округление: среднее строго между λ_j и λ_{j+1},
        # ошибка его счёта — несколько ULP
        assert np.all(lam_face >= lam_cells[:-1] * (1 - 1e-12))
        assert np.all(lam_face <= lam_cells[1:] * (1 + 1e-12))
```

### 3в. `test_grid.py`, `test_uniform_lambda_face_value` (`:381-388`)

**Контекст.** Утверждает $\lambda_{face} = \lambda/\ln(r_{j+1}/r_j)$ — закрепляет ненормированную величину под именем среднего. Проверяемое тождество ($w_L + w_R = \ln$ между центрами) сохраняется в новой форме.

До:
```python
    def test_uniform_lambda_face_value(self, grid):
        """При однородном λ: λ_face = λ / (w_L + w_R) = λ / ln(r_{j+1}/r_j)."""
        lam_val = 2.5
        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        lam_face = 1.0 / (w_L / lam_val + w_R / lam_val)
        log_ratio_centers = np.log(grid.r_centers[1:] / grid.r_centers[:-1])
        np.testing.assert_allclose(lam_face, lam_val / log_ratio_centers, rtol=1e-12)
```
После:
```python
    def test_uniform_lambda_face_value(self, grid):
        """При однородном λ среднее eq:face_interp равно λ.

        Нормировка весов eq:face_interp: w_L + w_R = ln(r_{j+1}/r_j) между
        центрами ячеек — та же проверка, что до BUG-027, но величина
        называется средним, только если равна λ.
        """
        lam_val = 2.5
        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        log_ratio_centers = np.log(grid.r_centers[1:] / grid.r_centers[:-1])
        lam_face = log_ratio_centers / (w_L / lam_val + w_R / lam_val)
        np.testing.assert_allclose(lam_face, lam_val, rtol=1e-12)
```

### 3г. `test_energy_matrix_examples.py` — импорт и новый тест

До (импорт, `:54-56`):
```python
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
```
После:
```python
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.io.config import load_config
```

Новый тест — сразу после `_ref_conductive` (после строки `    return Q_T_internal, Q_T_ext`, `:302`, перед `def _ref_ext_properties`; две пустые строки до и после), по образцу `test_ref_jt_outflow_matches_hand_formula`:
```python
# ── Самопроверка _ref_conductive: точное решение в кольце ──

def test_ref_conductive_matches_annulus_solution():
    """Проводимость граней в форме документа против точного решения в кольце.

    Зачем. Эталон следует форме документа: eq:heat_cond_disc со средним
    eq:face_interp. До BUG-027 документ записывал среднее без нормировки
    весов — при однородной λ оно равнялось λ/ln(r_{j+1}/r_j), и поток получал
    ln² в знаменателе: дефект BUG-002, перенесённый в постановку. Эталон,
    переписанный буквально по такому документу, завысил бы проводимость в
    1/ln(r_{j+1}/r_j) раз (на сетке примера 14 — в 46 раз), а сверка
    test_matrix_matches_reference увидела бы это только в медленном прогоне.

    Ожидание — стационарная теплопроводность, а не код решателя:
      однородная λ: Q_T = 2πhλ / ln(r_{j+1}/r_j)  (T = C1·ln r + C2);
      λ_L в слое [r_j, r_{j+1/2}], λ_R в слое [r_{j+1/2}, r_{j+1}]:
        сопротивления складываются,
        Q_T = 2πh / (ln(r_{j+1/2}/r_j)/λ_L + ln(r_{j+1}/r_{j+1/2})/λ_R);
      контур: Q_T_ext = 2πh·λ_{N-1} / ln(R_ext/r_{N-1})  (ssec:bc_disc).
    Сетка — r_w, R_ext примера 14, но N = 20: ln(r_{j+1}/r_j) ≈ 0.38, двойной
    ln дал бы расхождение в 2.6 раза. Чередование λ по ячейкам — на каждой
    грани два слоя с разной λ. Решатель проверяется той же формулой.
    """
    grid = LogRadialGrid(0.1, 200.0, 10.0, 20, 1e-13)
    N = grid.N
    r_c = grid.r_centers
    r_f = grid.r_faces[1:-1]          # внутренние грани [N-1]
    two_pi_h = 2.0 * np.pi * grid.h

    # Однородная λ: в знаменателе один ln
    lam = 1.228
    Q_int, Q_ext = _ref_conductive(grid, np.full(N, lam))
    np.testing.assert_allclose(
        Q_int, two_pi_h * lam / np.log(r_c[1:] / r_c[:-1]), rtol=1e-12,
        err_msg="однородная λ: в знаменателе один ln (BUG-002, BUG-027)")
    np.testing.assert_allclose(
        Q_ext, two_pi_h * lam / np.log(grid.R_ext / r_c[-1]), rtol=1e-12,
        err_msg="контур: ssec:bc_disc")

    # Два слоя кольца с разной λ: сопротивления складываются
    lam_cells = np.where(np.arange(N) % 2 == 0, 1.228, 0.3)
    R_layers = (np.log(r_f / r_c[:-1]) / lam_cells[:-1]
                + np.log(r_c[1:] / r_f) / lam_cells[1:])
    Q_int, _ = _ref_conductive(grid, lam_cells)
    np.testing.assert_allclose(
        Q_int, two_pi_h / R_layers, rtol=1e-12,
        err_msg="эталон: сопротивления двух слоёв кольца складываются")

    # compute_conductive_transmissibility читает только сетку
    Q_solver, _ = TridiagEnergySolver(grid, None, None) \
        .compute_conductive_transmissibility(lam_cells, N)
    np.testing.assert_allclose(
        Q_solver, two_pi_h / R_layers, rtol=1e-12,
        err_msg="решатель compute_conductive_transmissibility")
```

Замер (раздел 1, `plan_tests_check.py`): расхождения эталона $1.1\cdot10^{-16}$ (однородная), $6.7\cdot10^{-16}$ (два слоя), решателя — 0; эталон в старой форме документа — `AssertionError` с «один ln». `TridiagEnergySolver(grid, None, None)` — так же, как в `test_ref_jt_outflow_matches_hand_formula` (`:490`): метод читает только `self._grid`.

**Проверка после шага:**
- `& $PY -m pytest tests/test_grid.py -k TestHarmonicInterpolation -q` — 3 passed.
- `& $PY -m pytest tests/test_energy_matrix_examples.py -k annulus -q` — 1 passed (тест быстрый: фикстуры `results` нет, метку `slow` хук не ставит; `-m "not slow"` его выбирает).
- Регресс: быстрый — ожидание 1418 passed (на `a020f64` и `b94e7d3`).

**Подводные камни:** «Допуск в тестах», «Тест-сторож DEBT-010».
**Зависимости:** требует шаг 2. Блокирует: шаг 5.
**Оценка:** ~90 строк, ~15 мин.

## Шаг 4. Докстринги и комментарии: эталон, `test_energy.py`, `test_val002.py`

**Цель:** ни один текст в тестах не описывает документ до BUG-027 как действующий и не называет $\lambda/\ln$ средним.
**Файлы:** `numerical_solver/tests/test_energy_matrix_examples.py` (`:256-276`, `:293-295`), `numerical_solver/tests/test_energy.py` (`:688-695`), `numerical_solver/tests/test_val002.py` (`:322-325`). Логика не меняется.

### 4а. `_ref_conductive`, докстринг (`:257-268`)

До:
```python
    """Кондуктивная проводимость граней. eq:heat_cond_disc.

    ФОРМА ДОКУМЕНТА:
        Q_T = 2πh · λ^{j+1/2} / ln(r_{j+1}/r_j),
        λ^{j+1/2} = (w_L/λ_L + w_R/λ_R)^{-1} · (w_L + w_R)   [гармоническое
        среднее с логарифмическими весами]

    Ядро считает это иначе — как последовательные кольцевые сопротивления
    Q_T = 2πh / (w_L/λ_L + w_R/λ_R). Формы алгебраически тождественны, так
    как w_L + w_R = ln(r_{j+1}/r_j).
    Здесь намеренно записана форма документа: именно ошибка в этом месте
    (двойной ln) была содержанием BUG-002.
```
После:
```python
    """Кондуктивная проводимость граней. eq:heat_cond_disc.

    ФОРМА ДОКУМЕНТА (eq:heat_cond_disc со средним eq:face_interp):
        Q_T = 2πh · λ^{j+1/2} / ln(r_{j+1}/r_j),
        λ^{j+1/2} = (w_L + w_R) · (w_L/λ_L + w_R/λ_R)^{-1}   [гармоническое
        среднее с нормированными логарифмическими весами]

    Ядро считает это иначе — как последовательные кольцевые сопротивления
    Q_T = 2πh / (w_L/λ_L + w_R/λ_R). Формы алгебраически тождественны, так
    как w_L + w_R = ln(r_{j+1}/r_j).
    Здесь намеренно записана форма документа: именно ошибка в этом месте
    (двойной ln) была содержанием BUG-002. До BUG-027 сам документ записывал
    среднее без множителя (w_L + w_R); эталон буквально по такому документу
    завысил бы проводимость в 1/ln(r_{j+1}/r_j) раз. Самопроверка —
    test_ref_conductive_matches_annulus_solution.
```
Строки `:269-276` (λ = 0, контур, «Возвращает …») не меняются.

### 4б. `_ref_conductive`, комментарий (`:293-295`)

До:
```python
    # Форма документа: делим на ln(r_{j+1}/r_j) ещё раз. Этот ln тождественен
    # числителю (w_L + w_R), но сокращать его НЕЛЬЗЯ — двойной ln здесь и был
    # содержанием BUG-002, эталон воспроизводит запись документа буквально.
```
После:
```python
    # Форма документа: делим на ln(r_{j+1}/r_j). Он сокращается с множителем
    # (w_L + w_R) среднего, но сокращать его здесь НЕЛЬЗЯ — эталон
    # воспроизводит запись документа буквально. Без множителя (w_L + w_R)
    # ln остался бы в знаменателе дважды: BUG-002 в коде, BUG-027 в документе.
```

### 4в. `test_energy.py`, `TestComputeConductiveTransmissibility` (`:688-695`)

До:
```python
class TestComputeConductiveTransmissibility:
    """compute_conductive_transmissibility: Q_T = geom * lambda_face."""

    def test_uniform_lambda(self):
        """При однородном lambda_eff:
        lambda_face = lam / (w_L + w_R) (гармоническое среднее с ненормированными весами).
        Q_T = geom * lambda_face.
        """
```
После:
```python
class TestComputeConductiveTransmissibility:
    """compute_conductive_transmissibility: Q_T = 2πh / (w_L/λ_L + w_R/λ_R)."""

    def test_uniform_lambda(self):
        """При однородном lambda_eff: Q_T = 2πhλ / (w_L + w_R) = 2πhλ / ln(r_{j+1}/r_j).

        Один ln в знаменателе (BUG-002). В записи документа — eq:heat_cond_disc
        со средним eq:face_interp — среднее грани при однородной λ равно λ (BUG-027).
        """
```
Комментарий `:706` («Последовательные сопротивления: …») и проверка не меняются.

### 4г. `test_val002.py`, `test_conductive_transmissibility_single_ln` (`:322-325`)

До:
```python
        # Аналитический Q для потока от центра j к центру j+1:
        # Q = 2πhλ / ln(r_{j+1}/r_j) · ΔT   (один ln)
        # Код вычисляет: geom * lambda_face = (2πh/ln) * (λ/ln) = 2πhλ/ln²
        # Сравним: Q_T_internal[0] / (2πhλ/ln(r_c[1]/r_c[0]))
```
После:
```python
        # Аналитический Q для потока от центра j к центру j+1:
        # Q = 2πhλ / ln(r_{j+1}/r_j) · ΔT   (один ln)
        # До BUG-002 код вычислял geom · lambda_face = (2πh/ln) · (λ/ln) = 2πhλ/ln²;
        # сейчас — последовательные сопротивления 2πh/(w_L/λ + w_R/λ) = 2πhλ/ln.
        # Сравним: Q_T_internal[0] / (2πhλ/ln(r_c[1]/r_c[0]))
```
Допуск `rtol=0.05` (`:331`) не меняется: на этой сетке ($N = 50$, $R_{ext} = 50$) $1/\ln \approx 8$ — двойной ln ловится с запасом.

**Проверка после шага:**
- `& $PY -m pytest tests/test_eq_references.py tests/test_energy.py tests/test_val002.py tests/test_grid.py tests/test_energy_matrix_examples.py -m "not slow" -q` — все passed (сторож DEBT-010: в новых текстах только метки).
- Регресс: быстрый — 1418 passed.

**Подводные камни:** «Тест-сторож DEBT-010».
**Зависимости:** требует шаг 3 (докстринг эталона ссылается на новый тест).
**Оценка:** ~25 строк, ~10 мин.

**Коммит** (после шага 4): `test: кондуктивная проводимость — нормированное среднее, самопроверка эталона (BUG-027)`.

## Шаг 5. Vault и итог

**Цель:** заметки не повторяют двойной ln; полный прогон; результат в реестре и issue.
**Файлы:** `vault/knowledge/decisions/словарь-код-физика.md` (`:326-328`), `vault/knowledge/decisions/вопрос-кондуктивная-проводимость.md`, `vault/knowledge/decisions/модули-energy-tridiag.md` (`:116-128`), `vault/knowledge/decisions/модули-grid-сетка.md` (`:72`, `:136-142`), `vault/knowledge/validation/матрица температурной задачи сверена с постановкой поэлементно.md` (`:65-66`); реестр — `/implement`.

**Что сделать:**
1. **Словарь**, раздел 5.4: абзац `:328` «⚠️ В `problem_statement.tex` среднее … BUG-027.» заменить на:
   > Документ после [[BUG-027]]: `eq:heat_cond_disc` со средним `eq:face_interp` — $\lambda^{j+1/2} = (w_L + w_R)/(w_L/\lambda_L + w_R/\lambda_R)$, веса нормированы; подстановка даёт ту же формулу последовательных сопротивлений. До BUG-027 `.tex` записывал среднее без множителя $(w_L + w_R)$ — двойной ln BUG-002 в постановке.

   (План DEBT-010 `:71` оговаривал именно эту правку.)
2. **`вопрос-кондуктивная-проводимость.md`**:
   - frontmatter `description:` → «Двойной ln в кондуктивной проводимости: код исправлен BUG-002, постановка — BUG-027»;
   - перед «## Связанные заметки» — раздел:
     > ## Решение
     >
     > - Код — [[BUG-002]] (2026-09-01): последовательные кольцевые сопротивления $Q_T = 2\pi h/(w_L/\lambda_L + w_R/\lambda_R)$.
     > - Постановка — [[BUG-027]] (<дата>): объяснение 2 этой заметки — веса `eq:face_interp` нормированы, $\lambda^{j+1/2} = \lambda$ при однородной $\lambda$; поток `eq:heat_cond_disc` с одним ln, под ним — тождество с последовательными сопротивлениями.
     > - Направление ошибки: поток по старой записи **завышен** в $1/\ln(r_{j+1}/r_j)$ раз (на всех рабочих сетках $\ln < 1$; пример 14 — в 46 раз).
3. **`модули-energy-tridiag.md`** `:116-128` — три блока кода заменить:
   ```python
   Q_lambda[j+1/2] = (2*pi*h / ln(r_{j+1}/r_j)) * lambda_eff_face * (T_j - T_{j+1})   # > 0 — от скважины
   ```
   lambda_eff_face — гармоническое среднее с нормированными логарифмическими весами (`eq:face_interp`):
   ```python
   lambda_eff_face = (w_left + w_right) / (w_left/lambda_eff[j] + w_right/lambda_eff[j+1])   # w_left + w_right = ln(r_{j+1}/r_j)
   ```
   Обозначим кондуктивную проводимость:
   ```python
   Q_T[j+1/2] = (2*pi*h / ln(r_{j+1}/r_j)) * lambda_eff_face == 2*pi*h / (w_left/lambda_eff[j] + w_right/lambda_eff[j+1])
   ```
   и строкой ниже: «До [[BUG-027]] здесь, как в `.tex`, среднее было без множителя `(w_left + w_right)` — двойной ln [[BUG-002]]; знак потока был обратным конвенции (`T_{j+1} − T_j`)». Ссылка «(eq. 21)» заменяется меткой `eq:face_interp` (словарь DEBT-010 — метки, не номера).
4. **`модули-grid-сетка.md`** `:142` — «где λ_{eff}^{j+1/2} = 1 / (w_left[j]/λ_j + w_right[j]/λ_{j+1}) — гармоническое среднее.» заменить на «где λ_{eff}^{j+1/2} = (w_left[j] + w_right[j]) / (w_left[j]/λ_j + w_right[j]/λ_{j+1}) — гармоническое среднее с нормированными весами (`eq:face_interp`; w_left + w_right = ln(r_{j+1}/r_j)). Без множителя в числителе — двойной ln ([[BUG-002]], [[BUG-027]]).» Там же `:72` (докстринг `log_weights` в наброске ABC проектного этапа): «A_{j+1/2} = 1 / (w_left[j]/A_j + w_right[j]/A_{j+1})» → «A_{j+1/2} = (w_left[j] + w_right[j]) / (w_left[j]/A_j + w_right[j]/A_{j+1})». Правка — по тексту: в основном каталоге в эту заметку уже внесена чужая незакоммиченная строка (`/issue` DEBT-060, после `:96`), номера ниже неё могут сдвинуться на +2.
5. **`матрица температурной задачи сверена с постановкой поэлементно.md`** — после `:66` («Ошибка именно в этом месте (двойной `ln`) была содержанием [[BUG-002]].») добавить: «До [[BUG-027]] `.tex` записывал $\lambda^{j+1/2}$ без множителя $(w_L + w_R)$: эталон следовал документу в исправленном прочтении. Теперь документ совпадает с эталоном буквально; самопроверка эталона — `test_ref_conductive_matches_annulus_solution`.»
6. **Полный прогон и пробы «после»** (из `$WT`):
   ```powershell
   & $PY -m pytest tests/ -q | Select-Object -Last 2
   & $PY "$P\conductive_forms.py"
   & $PY -m pytest "$P\plan_tests_check.py" -q -s -p no:cacheprovider -W ignore::pytest.PytestUnknownMarkWarning
   ```
   Ожидание: 1689 passed (на `b94e7d3`; иначе — база + 1); вывод `conductive_forms.py` совпадает с `conductive_forms_before.txt`, кроме пути в первой строке: код решателя не менялся; `plan_tests_check.py` — 8 passed.
7. Реестр и issue — по контракту `/implement`. В запись BUG-027 — итог, в запись BUG-002 — строку «**Уточнение ([[BUG-027]], <дата>):** поток по документу был не занижен, а завышен в $1/\ln(r_{j+1}/r_j)$ раз (воспроизведение «в ~ln раз меньше» — наоборот); документ исправлен только в BUG-027». В запись DEBT-016 (строка «Формы записи кода и документа различаются…», «расхождение 3.4e-16») — «(тождество — для документа после [[BUG-027]]; до него `.tex` записывал среднее без множителя $(w_L + w_R)$)».
8. **После `/merge`** — пересобрать `doc/problem_statement.pdf` в основном каталоге (три прохода, как в 2в): PDF не в git, локальный устарел (35 страниц против 37).

**Проверка:** полный прогон зелёный; пробы как в п. 6; `Select-String -Path vault\knowledge\decisions\*.md -Pattern '(= 1|1\.0) / \(w_left'` — пусто (до шага — 3 строки: `модули-energy-tridiag.md:122`, `модули-grid-сетка.md:72`, `:142`; замер аудита).
**Регресс:** полный (конец реализации, `/implement` §3.1).
**Зависимости:** требует шаги 1–4.
**Оценка:** ~30 строк vault, ~20 мин (из них ~10 — полный прогон).

**Коммит:** `vault: двойной ln снят из постановки и заметок (BUG-027)` — заметки `vault/knowledge/` пп. 1–5.

## Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_ref_conductive_matches_annulus_solution` (новый) | `tests/test_energy_matrix_examples.py` | Сетка $r_w = 0.1$, $R_{ext} = 200$, $h = 10$, $N = 20$; однородная $\lambda = 1.228$ и чередование $1.228 \mid 0.3$ | Эталон: $2\pi h\lambda/\ln$, контур $2\pi h\lambda/\ln(R_{ext}/r_{N-1})$, два слоя $2\pi h/\sum R$ при `rtol=1e-12`; решатель — то же | Эталон «по документу» с двойным ln (в быстром уровне, а не только в сверке матрицы) |
| `test_heat_flux_analytic` (переписан) | `tests/test_grid.py` | $T = \ln r$, $\lambda = 2$, $N = 50$, $R_{ext} = 500$ | $Q_T$ через `log_weights` даёт $Q_{face} = 2\pi h\lambda$ на всех гранях, `rel=1e-10` | Веса сетки не проверялись вовсе; комментарий с двойным ln |
| `test_harmonic_mean_nontrivial` (усилен) | `tests/test_grid.py` | $\lambda_j = 1 + j$ | Среднее `eq:face_interp` в $[\lambda_j, \lambda_{j+1}]$ с допуском $10^{-12}$ | Ненормированное «среднее» (выходит за $\lambda_{\max}$) |
| `test_uniform_lambda_face_value` (переписан) | `tests/test_grid.py` | $\lambda = 2.5$ | Среднее `eq:face_interp` $= \lambda$, `rtol=1e-12` | Закрепление $\lambda/\ln$ под именем среднего |
| `test_label_references_exist_in_problem_statement` (есть) | `tests/test_eq_references.py` | Метки после правки `.tex` | 2 passed | Удаление или переименование меток |

Каждый новый и переписанный тест проверен на копии: зелёный на текущем коде, красный на записи документа до BUG-027 (`plan_tests_check.py`, раздел 1).

## Критерии завершения

- [ ] `eq:face_interp` и среднее под `eq:heat_cond_disc` — с множителем $\ln(r_{j+1}/r_j)$; тождество с последовательными сопротивлениями и однородный случай — в тексте; знаменатель левой грани под `eq:tridiag_d` положителен.
- [ ] PDF собирается без предупреждений, 37 страниц, номера уравнений прежние, новых переполнений строк нет.
- [ ] Новый тест и переписанные тесты зелёные; число тестов +1.
- [ ] Быстрый уровень и полный прогон зелёные.
- [ ] Вывод `conductive_forms.py` прежний (код не менялся).
- [ ] Заметки vault (5 файлов) без двойного ln; словарь без ⚠️.
- [ ] Реестр (BUG-027, BUG-002, DEBT-016), issue #97 — по `/implement`.
- [ ] После `/merge` — PDF в основном каталоге пересобран.

## 7. Обнаруженные при планировании проблемы

| Проблема | Решение |
|---|---|
| `TestHarmonicInterpolation` (`tests/test_grid.py`) закрепляет $\lambda/\ln$ как «$\lambda_{face}$» и повторяет двойной ln в комментарии; `test_heat_flux_analytic` не использует веса сетки | В план, шаг 3 |
| Под `eq:tridiag_d` (`:1638`) $\ln(r_{j\pm1}/r_j)$ при «−» отрицателен, а проводимость объявлена $> 0$ (в issue ошибочно названо «верным после правки») | В план, шаг 2б |
| Заметки `модули-energy-tridiag.md`, `модули-grid-сетка.md` повторяют двойной ln; первая — ещё и с обратным знаком потока | В план, шаг 5 |
| Запись BUG-002: «поток занижен в ln раз» — направление обратное (завышен в $1/\ln$) | В план, шаг 5 п. 7 |
| Локальный `doc/problem_statement.pdf` устарел (35 страниц, текущий `.tex` — 37) | В план, шаг 5 п. 8 |
| Ссылка «`eq:bc_props_ext (74)`» в `tests/test_energy_matrix_examples.py:238, 306, 716` — номер устарел (сейчас 75), сторож DEBT-010 форму «метка (N)» не ловит | Новая запись [[DEBT-062]], не в этом плане. ⚠️ Аудит 1: в `vault/issues/debt-062/probes/center_accuracy.py` параллельная сессия готовит **другую** задачу под тем же номером (точность центра ячейки, к DEBT-060), в реестр она не записана — номер занят этой записью, решение — за пользователем. **Снято до реализации:** та сессия записала свою задачу как [[DEBT-063]] (каталог `vault/issues/debt-063/`) |
| `модули-grid-сетка.md:72` (докстринг `log_weights` в наброске ABC) — та же ненормированная формула; планом пропущена (аудит 1) | В план, шаг 5 п. 4 |
| План BUG-002 предусматривал правку `.tex` (шаг 4), шаг выпал при реализации (аудит 1) | В причинную цепочку, раздел 2 п. 3 |
| Нумерация граней в `.tex` сдвинута на единицу: `eq:log_grid` и `:935` дают $r_{1/2} = r_w$, $r_{N+1/2} = R_{ext}$, граничный раздел — $Q_{\lambda,1/2} = 0$, $\Phi_{1/2}$ на забое, $\mathcal{T}_{N+1/2}$, $Q_{\lambda,N+1/2}$ на контуре; а внутренние формулы (`eq:heat_cond_disc`, потоки компонентов) ставят грань $j+1/2$ между ячейками $j$ и $j+1$ при ячейках $0…N-1$ — забой тогда $r_{-1/2}$, контур $r_{N-1/2}$ (аудит 1) | Вне задачи (в BUG-027 текст на граничные грани не ссылается); регистрация — по решению пользователя |

## Связанные заметки

- [[известные баги и технический долг]] — BUG-027, BUG-002, DEBT-016, DEBT-010, DEBT-062
- [[вопрос-кондуктивная-проводимость]] — исходный вопрос о двойном ln, оба варианта исправления
- [[словарь-код-физика]] — раздел 5.4
- [[матрица температурной задачи сверена с постановкой поэлементно]] — формы записи $Q_T$
- [[модули-energy-tridiag]], [[модули-grid-сетка]] — проектные заметки с той же записью
- [[bug-002 double-ln-conductive]] — исправление в коде
- [[debt-016 energy-matrix-verification]] — эталон в форме документа (находка 4)
- [[debt-010 docstring-eq-labels]] — обнаружение (раздел 7), тест-сторож меток
- Пробы: `vault/issues/bug-027/probes/` — `conductive_forms.py` (+ `_before.txt`), `plan_tests_check.py` (+ `.out.txt`), `tex_apply.py`, `plan_apply_check.py` (аудит 1: текст плана на копии дерева)
