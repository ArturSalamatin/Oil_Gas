---
tags:
  - план
  - инфраструктура
date: 2026-10-13
issue: FEAT-030
github: 104
branch: feat/feat-030/run-command-from-config
model_level: null
status: в процессе
worktree: .worktrees/feat-030
audit:
  date: 2026-10-13
  round: 1
  found: 9
  auto-fixed: 9
  manual-required: 0
---

# FEAT-030: команда расчёта по конфигу из установленного пакета

## 0. Решения пользователя (2026-10-13, при планировании)

1. **Параметры примера — в секции `output` конфига**: `title`, `n_profiles`, `steady_state`, `closed_form_overlays`. Команда воспроизводит пример без флагов; флаги `--title`, `--profiles` их переопределяют.
2. **`steady_state` по умолчанию — `false`.** Замкнутое решение (GOR = $R_{s,0}$) и асимптотика $T$ — пределы $t \to \infty$ одного режима; в реалистичных сценариях (14, 19–21) стационар не достигнут. 15 примеров, где аналитика сейчас работает, получают явное `"steady_state": true`.
3. **Каталог вывода очищается целиком (`shutil.rmtree`), как сейчас.** Плюс узкая защита: отказ **до расчёта** с кодом 2, если внутри каталога вывода лежит конфиг или его CSV-таблицы (`--output .` из папки конфига).
4. **EMF — как сейчас**: включён по умолчанию, `GPN_EXAMPLES_EMF=0` выключает, `INKSCAPE` — путь к Inkscape; без Inkscape — предупреждение, SVG сохраняются. Флагов командной строки для EMF нет.
5. **Форма команды** — `python -m gpn_multiphase_solver run config.json [--output DIR] [--title T] [--profiles N]` и та же команда как `gpn-solver run …` (`[project.scripts]`); одна функция `cli.main`. `--output` по умолчанию — папка `output` рядом с конфигом.

Из регистрации (2026-10-10, модель «Б»): пример = конфиг + README + собственные скрипты, где они есть. Отсюда: `main.py` удаляются у 17 примеров, где они только вызывают `run_example`; остаются у 01, 02, 03, 04, 05, 18 (своя логика после штатного расчёта).

Открытые пункты реестра, решённые планом (не решения пользователя — оспорить на аудите):
- **дополнительные скрипты примеров частью команды не становятся**: асимптота и ОДУ-аналитика 01/02, `check_slopes.py` (02), `spatial_convergence.py` (01), `grid_convergence.py` (04, 04a), `plot_profiles_50k.py` (04a), `closed_form_convergence.py` (05), `energy_balance_convergence.py`, CLI `two_phase_analytics.py` — исследования отдельного сценария, у них свои прогоны (серии сеток, шагов). Меняются только их импорты;
- автономные запуски `energy_balance.py NN`, `mass_balance.py NN`, `temperature_asymptotics.py NN` удаляются — их вывод входит в штатный набор команды;
- `tests/test_energy_balance_examples.py`, `tests/test_mass_balance.py` (названы в реестре) правок не требуют: из `examples/` они читают только конфиги, ряды балансов берут из пакета (проверено при аудите).

## 1. Сводка

- **Подтип:** инфраструктура (команда, ввод/вывод, конфиг). Уровень модели — нет; новых формул нет.
- **Суть:** конвейер `examples/example_runner.run_example` и модули рисунков/печати `examples/` переезжают в пакет (`gpn_multiphase_solver/report/`, `io/figures.py`); появляется точка входа `python -m gpn_multiphase_solver run` / `gpn-solver run`; параметры примеров уходят из `main.py` в конфиг.
- **Критерий неизменности:** снимок вывода всех 23 примеров (печать + побайтно `output/`) до и после совпадает, кроме строки времени расчёта и файлов времени выполнения прототипа у 18.
- **Шагов:** 10 (0–9). **Файлов:** ≈ 75 (пакет 13, тесты 8, примеры: 23 конфига, 6 `main.py` + 17 удалённых, 7 скриптов, 24 README; документы). **Оценка:** ~7–8 ч, из них ~40 мин — три снимка примеров, ~10 мин — полный прогон, ~10 мин — приёмка в чистом окружении.
- **Тестов:** N0 → ≈ N0 − 25 (−61 параметр за удалённые скрипты `examples/`, +36 новых); точное число — по `--collect-only` после каждого шага (раздел 5). На `3f3df63` N0 = 1826; на базе после DEBT-065 и FEAT-032 — больше.

## 2. Контекст

### 2.1. Задача и зависимости

- Реестр: `vault/roadmap/планируемые фичи.md`, FEAT-030; issue [#104](https://github.com/ArturSalamatin/Oil_Gas/issues/104).
- **Зависит от** [[DEBT-059]] (влит `29a1ffa`) и [[DEBT-011]] (влит `7f8d879`, 2026-10-13): вычислительная часть проверок — в `gpn_multiphase_solver/diagnostics/`, рисунки — в `io/output.py`, объекты задачи — `Simulator.grid/pvt/relperm`, `create_pvt/create_relperm`. Оба условия выполнены.
- **Блокирует** [[FEAT-031]] (комплект поставки, приёмка в чистом окружении).
- **Параллельные задачи** (на 2026-10-13 в работе, worktree): [[DEBT-065]] (`.worktrees/debt-065`: `diagnostics/rs.py`, `two_phase.py`, `closed_form.py`, текст `examples/04_table_table/grid_convergence.py:109-110`, абзац `examples/README.md` о `rs_profiles.png`) и [[FEAT-032]] (`.worktrees/feat-032`: `simulator.py`, `io/config.py` — поле `numerics`, конфиги и README 16, 17, `examples/README.md`). Обе правят файлы, которые правит FEAT-030 (README, конфиги 16/17, `config.py`, `grid_convergence.py`). **Начинать FEAT-030 после влития обеих** (шаг 0.1): конфликты слияния не нужны, и снимки «до/после» снимаются на одной базе.
- Ещё [[BUG-025]] (`.worktrees/bug-025`, аудит FEAT-030): правит прототип `HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (пол невязки на коротком шаге) и свои тесты; файлов FEAT-030 не трогает, конфликта слияния нет, но может менять числа примеров. Поэтому снимки берут **прототип из дерева worktree** (`PYTHONPATH` с путём прототипа; проба `snapshot_examples.py` проверяет оба пути): влитая в базу посреди реализации правка прототипа не попадёт в один снимок и минует другой. Ждать BUG-025 не обязательно.

### 2.2. Текущее состояние (на `3f3df63`; DEBT-011 влита)

**Конвейер** — `numerical_solver/examples/example_runner.py` (325 строк):

| строки | что | проблема для пакета |
|---|---|---|
| 26–28 | `sys.stdout/stderr.reconfigure(utf-8)` **при импорте** | библиотека меняет потоки вызывающей программы |
| 41 | `matplotlib.use("Agg")` **при импорте** | библиотека меняет режим matplotlib (Jupyter) |
| 54–64 | импорт соседних модулей `examples/` по плоскому имени | вне репозитория не работает |
| 67–70 | `run_example(config_path, output_dir, title, overlays=None, n_profiles=None, steady_state=True)` | параметры — только аргументами Python |
| 101–102 | печать `=== {title} ===`, `Конфиг: {config_path}` | — |
| 111 | `grid = simulator.grid` | — |
| 122–124 | `shutil.rmtree(output_dir)` после расчёта | остаётся (решение 3) |
| 139–146 | наложения замкнутого решения: `two_phase and steady_state` | — |
| 189–190, 198, 208, 216 | `plot_relperm`, `plot_pvt`, `plot_energy_balance`, `plot_mass_balance` | — |
| 221 | `export_emf(output_dir)` | — |
| 231, 234, 241, 254 | `report_rs`, `report_closed`, `report_pvt`, `report_asymptotics` | — |
| 261 | `return elapsed, history, grid, config` | решатель не возвращается — 01–05 собирают второй `Simulator` |
| 264, 273, 292, 312 | `_pick_overlay`, `_profile_times`, `_plot_field`, `_print_summary` | — |

**Модули печати и рисунков в `examples/`** (остались после DEBT-011, переезжают):

| файл | строк | что в нём | кто зовёт |
|---|---|---|---|
| `figure_io.py` | 141 | `save_figure`, `export_emf`, `emf_enabled`, `find_inkscape`; переменные `GPN_EXAMPLES_EMF`, `INKSCAPE` | конвейер, 4 модуля ниже, `main.py` 01/02/05/18, 6 скриптов примеров |
| `relperm_plot.py` | 121 | `plot_relperm` (PNG), `report_relperm`; `matplotlib.use("Agg")` `:39` | конвейер, `main.py` 05, тесты |
| `pvt_plot.py` | 263 | `plot_pvt` (PNG), `report_pvt`, `_physical_rs`; `matplotlib.use` `:68` | конвейер, тесты |
| `rs_analytics.py` | 106 | `make_overlay_rs`, `_draw_rs`, `report_rs` | конвейер, тесты |
| `closed_form.py` | 104 | `make_overlay_pressure`, `make_overlay_saturation`, `report_closed` | конвейер, тесты |
| `energy_balance.py` | 147 | `plot_energy_balance`, `report_energy_balance` (нигде не вызывается), `_resolve_example`, CLI; `sys.path` `:50-55`, `matplotlib.use` `:47` | конвейер, `mass_balance.py` (`_resolve_example`) |
| `mass_balance.py` | 107 | `plot_mass_balance`, CLI; `sys.path` `:42-47` | конвейер |
| `temperature_asymptotics.py` | 76 | `report_asymptotics`, `SG_EPS`, CLI; `sys.path` в CLI | конвейер |

**Что остаётся в `examples/`:** `two_phase_analytics.py` (`report` — зовут `main.py` 03/04/05; CLI), `convergence.py`, `energy_balance_convergence.py` (исследования), `run_all.py`, `check_energy_balance_all.py`, `verify_balance_vs_solver.py`, `compare_script_copies.py` (средства разработки). `_resolve_example` сейчас в трёх копиях: `energy_balance.py:113`, `energy_balance_convergence.py:172`, `two_phase_analytics.py:111` (искать `def _resolve_example`).

**Параметры примеров** — только в `main.py` (сняты 2026-10-13, таблица — в пробе `vault/issues/feat-030/probes/add_output_fields.py`, `VALUES`):
- `steady_state=False`: 13b, 14, 16, 17, 18, 19, 20, 21 (обоснования — комментарии в их `main.py`: стационар не достигнут или режим меняется);
- `n_profiles`: 13a, 14, 15, 18 — 6; 13b, 16, 17 — 7;
- `overlays`: 13a — `{"Sg": None}`; 15 — `{"p": None, "Sg": None}`; 03 — `{"T": overlay_temperature}` (функция в `main.py`, остаётся Python-аргументом);
- `title` — у всех 23.

**Конфиги:** у всех 23 последняя секция — `"output": {"log_level": "INFO"}`, переводы строк CRLF. `OutputConfig` (`gpn_multiphase_solver/io/config.py:191-199`) — одно поле `log_level`; проверка — `_validate` `:633-639`. Секция `output` не входит в `_NUMERIC_SECTIONS` (`:426-427`): новые поля проверяются явно, как `log_level`.

**`main.py`:** 23 файла, 1193 строки. 17 — только вызов `run_example` (17–28 строк). Своя логика: 01 (Дюпюи, ОДУ-аналитика $T$, перерисовка двух PNG, второй `Simulator` в `_add_temperature_analytics`), 02 (то же + JT), 03 (наложение $T$, `tpa.report`, второй `Simulator`), 04 (`tpa.report`, второй `Simulator`), 05 (`report_relperm`, `tpa.report`, перерисовка $T$, второй `Simulator`), 18 (сверка с прототипом и IMEX, `prototype_input.report_and_plot`, второй `export_emf`).

**Проба `factory_warnings.py`** (`vault/issues/feat-030/probes/`, вывод `.out.txt`): `SimulatorFactory.from_config` на конфигах 01–05 и 18 пишет в журнал 0 предупреждений — отказ от второго `Simulator` печать этих примеров не меняет.

**Тесты, привязанные к `examples/`:**
- `tests/test_examples.py`: `test_pipeline_writes_output` (`:500`), `test_profile_times_default_and_uniform` (`:533`), `test_pick_overlay_none_disables_default` (`:558`), `test_steady_state_false_skips_steady_analytics` (`:578`), `SHARED_CHECK_MODULES` (`:634`), `SHARED_EXAMPLE_FILES` (`:657`), `test_shared_modules_exist` (`:806`), `test_energy_balance_reported_for_all_examples` (`:816`), `test_rs_check_all_two_phase_examples` (`:866`, `from rs_analytics import report_rs`), помощники `_pvt_module` (`:930`), `_relperm_module` (`:1364`), `_closed_form` (`:1809`), подмена `pvt_plot.save_figure` (`:1297`); проверки **текста `main.py`**: 13a (`:1790`, `:1800`), 15 (`:2018`, `:2029`), 14 (`:2162`), 13b (`:2285`, `:2290`), 16 (`:2444-2447`), 19–21 (`:2629`), 17 (`:2875-2878`), 18 (`:2982-2985`); структура `TestStructure` (`:148-168`: `main.py` обязателен, `example_runner.py` существует);
- `tests/test_rs_analytics.py:31-35` — `sys.path` + `import rs_analytics`;
- `tests/test_example_scripts.py` — 46 скриптов × 2 параметризованных теста; (д) `:190-206` — аргументы `run_example`; `BROKEN_SNIPPETS` `:224-247` ссылаются на `figure_io`, `closed_form`, `example_runner`;
- `tests/test_packaging.py:147-162` — страж вставок `sys.path` (`found > 10`; сейчас 73 вставки);
- `tests/conftest.py:15` — `GPN_EXAMPLES_EMF = "0"`; режим matplotlib задают отдельные тесты (`test_output.py:15`), не `conftest.py`.

**Прочие ссылки:** `examples/README.md` (843 строки: «Запуск» `:226-267`, EMF `:293-305`, `steady_state` `:436`, таблица общих модулей `:782-822`, тесты `:838-843`), README 23 примеров (раздел «Запуск», упоминания `main.py`/`n_profiles`/`steady_state`/`overlays`, ссылки на `../energy_balance.py`, `../pvt_plot.py`, `example_runner`), `.claude/commands/run.md:35-38`, заметки vault (раздел 4, шаг 9).

### 2.3. Целевое состояние

```
numerical_solver/gpn_multiphase_solver/
├── __main__.py          # python -m gpn_multiphase_solver → cli.main
├── cli.py               # main(argv, prog), configure_batch_run()
├── io/figures.py        # ← examples/figure_io.py
└── report/              # рисунки с записью PNG, печать проверок, конвейер
    ├── __init__.py
    ├── pipeline.py      # ← examples/example_runner.py: run_case, CaseResult, CaseConfigError, CaseRunError
    ├── relperm.py       # ← examples/relperm_plot.py
    ├── pvt.py           # ← examples/pvt_plot.py
    ├── rs.py            # ← examples/rs_analytics.py
    ├── closed_form.py   # ← examples/closed_form.py
    ├── energy_balance.py# ← examples/energy_balance.py (без CLI, _resolve_example, report_energy_balance)
    ├── mass_balance.py  # ← examples/mass_balance.py (без CLI)
    └── temperature.py   # ← examples/temperature_asymptotics.py (без CLI)
```

- `diagnostics/` — считает (без печати и рисунков); `report/` — рисует с записью файлов и печатает; `io/output.py` — рисует на осях без записи. Граница DEBT-011 сохраняется.
- Модули пакета **не** зовут `matplotlib.use` и не трогают `sys.stdout`/`sys.path` при импорте. Это делает `cli.configure_batch_run()` — команда и скрипты примеров зовут её явно.
- Пример = `config.json` (+ CSV) + `README.md`; `main.py` — только у 01, 02, 03, 04, 05, 18; они зовут `run_case` и получают решатель из `CaseResult`.

## 3. Как начать работу по этому плану

1. Прочитать этот план целиком; заметки [[архитектура библиотеки numerical_solver]] (раздел «Диагностика и граница пакет / examples»), [[рисунки примеров дублируются в SVG и EMF через Inkscape]], [[имена скриптов examples проверяются разбором AST — импорт файла не видит импорты в функциях и обращения к модулю через точку]], [[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]].
2. `/implement FEAT-030`: worktree `.worktrees/feat-030`, ветка `feat/feat-030/run-command-from-config` от `numerical_scheme/implementation` (проверка: `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`).
3. Обозначения: `<W>` — корень worktree; `<R>` — корень основного каталога; `$PY` = `<R>\numerical_solver\.venv\Scripts\python`. Команды pytest — из `<W>\numerical_solver` (pytest берёт пакет из каталога запуска, прототип — по `pythonpath` в `pyproject.toml`).
4. **Скрипты вне pytest в worktree** (`main.py`, пробы) — с `$env:PYTHONPATH = "<W>\numerical_solver;<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"` (правило 3 `/implement`, заметка reference_worktree_pythonpath): без неё и пакет, и прототип берутся из основного каталога. `python -m gpn_multiphase_solver` из `<W>\numerical_solver` берёт пакет worktree и без неё (каталог запуска — первый в `sys.path`; установщик `-e` ищет после него), но прототип — всё равно из основного каталога; из постороннего каталога — оба только с ней.
5. **Не ставить пакеты из worktree** (`pip install -e` в общий venv перенаправил бы установку основного каталога на worktree). `gpn-solver.exe` в общем venv появится после влития и переустановки в основном каталоге (раздел 9). В worktree точку входа проверяют тест разбора `pyproject.toml` (шаг 6) и приёмка в чистом окружении (шаг 9).
6. Исходные числа: `$PY -m pytest tests/ --collect-only -q` (N0) и `$PY -m pytest tests/ -m "not slow" -q` (F0) — записать в журнал.
7. Начать с шага 0.

## 4. Шаги

### Шаг 0: подготовка — предусловия, сверка строк, снимок «до»

**Цель:** база содержит DEBT-065 и FEAT-032; номера строк плана сверены; снят снимок вывода 23 примеров на базе.
**Файлы:** — (только проверки и снимок в `vault/issues/feat-030/probes/out/`).

**Что сделать:**
1. Предусловия:
   ```powershell
   git log --oneline numerical_scheme/implementation | Select-String "DEBT-065 влит|FEAT-032 влит"
   git worktree list
   ```
   Обе строки «влит» есть. Если нет — остановиться и спросить пользователя: начинать на текущей базе (тогда конфликты в README 16/17, `examples/README.md`, `config.py`, `grid_convergence.py` при слиянии разрешать вручную) или ждать.
2. Сверка строк (на базе FEAT-032 и DEBT-065 номера сдвинутся — искать по тексту):
   ```powershell
   cd <W>\numerical_solver
   git grep -n "reconfigure\|matplotlib.use\|def run_example\|shutil.rmtree\|return elapsed" -- examples/example_runner.py
   git grep -n "class OutputConfig\|log_level: str\|output.log_level" -- gpn_multiphase_solver/io/config.py
   git grep -n "def _resolve_example" -- examples
   git grep -n "main.py\").read_text" -- tests/test_examples.py
   git grep -n "run_example\|figure_io\|closed_form import" -- tests/test_example_scripts.py
   ```
   Ожидание: как в разделе 2.2; расхождение — записать в журнал, план не переписывать.
3. Исходные числа N0, F0 (раздел 3, п. 6).
4. Снимок «до» (~12 мин; все 23 примера через `main.py`):
   ```powershell
   cd <W>\numerical_solver
   $env:PYTHONPATH = "<W>\numerical_solver;<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"
   & $PY -X utf8 <W>\vault\issues\feat-030\probes\snapshot_examples.py snap --tree . --out <W>\vault\issues\feat-030\probes\out\snap_before.json
   ```
   Проба сама задаёт `PYTHONPATH` (пакет и прототип дерева) и проверяет оба пути (`пакет: <W>\...`, `прототип: <W>\...`); переменная из п. 4 нужна для ручных запусков. Ожидание: 23 строки «код 0». Каталог `probes/out/` — не коммитить (снимки — рабочие файлы, ~1 МБ).

**Проверка после шага:** снимок есть, у всех примеров код 0.
**Подводные камни:** если 18 печатает «эталона IMEX нет» или прототип пишет время выполнения — это `TIME_FILES` пробы, сравнение их пропускает.
**Зависимости:** блокирует всё.
**Оценка:** ~20 мин.

---

### Шаг 1: `io/figures.py` ← `examples/figure_io.py` + тесты поведения без Inkscape

**Цель:** запись PNG/SVG и экспорт EMF — в пакете; поведение без Inkscape проверено тестом (в реестре FEAT-030 это было открыто).
**Файлы:** `numerical_solver/examples/figure_io.py` → `numerical_solver/gpn_multiphase_solver/io/figures.py` (`git mv`); импортёры: `examples/example_runner.py`, `examples/relperm_plot.py`, `examples/pvt_plot.py`, `examples/energy_balance.py`, `examples/mass_balance.py`, `examples/energy_balance_convergence.py`, `examples/01_single_phase_no_jt/main.py`, `examples/01_single_phase_no_jt/spatial_convergence.py`, `examples/02_single_phase_jt/main.py`, `examples/02_single_phase_jt/check_slopes.py`, `examples/04a_high_gas_saturation/plot_profiles_50k.py`, `examples/05_standing_table_rp/main.py`, `examples/05_standing_table_rp/closed_form_convergence.py`, `examples/18_prototype_input/main.py`, `examples/18_prototype_input/prototype_input.py` (импорт внутри `plot_comparison`, `:357`); `numerical_solver/tests/test_example_scripts.py` (`BROKEN_SNIPPETS["a_top_level_import"]`); новый `numerical_solver/tests/test_figures.py`.

**Контекст:** `figure_io` (FEAT-026) не зависит от `examples/`: `os`, `shutil`, `subprocess`, `matplotlib`. Переменные окружения остаются прежними (решение 4) — имя `GPN_EXAMPLES_EMF` историческое, его читают `tests/conftest.py:15` и README.

**Что сделать:**
1. `git mv numerical_solver/examples/figure_io.py numerical_solver/gpn_multiphase_solver/io/figures.py`.
2. Докстринг модуля: первая строка — «Сохранение рисунков: PNG + SVG и EMF в `<каталог>/emf/` (FEAT-026; в пакете с FEAT-030).» Остальной текст сохранить; «рисунков примеров» → «рисунков».
3. Импортёры: `from figure_io import save_figure, export_emf` → `from gpn_multiphase_solver.io.figures import save_figure, export_emf` (в модулях `examples/` и скриптах примеров — абсолютный импорт пакета). Внутри пакета (с шага 2) — `from ..io.figures import save_figure`.
4. `tests/test_example_scripts.py`, `BROKEN_SNIPPETS["a_top_level_import"]`: `"from figure_io import no_such_name\n"` → `"from two_phase_analytics import no_such_name\n"` (общий модуль, который останется в `examples/`).
5. Новый `tests/test_figures.py` — три теста (раздел 5, «Шаг 1»).

**Проверка после шага:**
- Тест: `$PY -m pytest tests/test_figures.py tests/test_example_scripts.py -q`.
- Регресс: быстрый.

**Подводные камни:** `export_emf` печатает через `print` — тест читает `capsys`. Тест без Inkscape задаёт `INKSCAPE` на несуществующий файл: тогда `find_inkscape` других мест не проверяет (`figures.py`, `find_inkscape`, ветка `explicit`) — тест не зависит от того, стоит ли Inkscape на машине.
**Зависимости:** требует шаг 0; блокирует шаги 2, 5.
**Оценка:** ~60 строк тестов, ~25 мин.

---

### Шаг 2: модули печати и рисунков → `gpn_multiphase_solver/report/`

**Цель:** семь модулей `examples/` — в подпакете `report/`; без побочных эффектов импорта; `examples/example_runner.py` и тесты берут их из пакета.
**Файлы:** новый `numerical_solver/gpn_multiphase_solver/report/__init__.py`; `git mv`:

| из `numerical_solver/examples/` | в `numerical_solver/gpn_multiphase_solver/report/` |
|---|---|
| `relperm_plot.py` | `relperm.py` |
| `pvt_plot.py` | `pvt.py` |
| `rs_analytics.py` | `rs.py` |
| `closed_form.py` | `closed_form.py` |
| `energy_balance.py` | `energy_balance.py` |
| `mass_balance.py` | `mass_balance.py` |
| `temperature_asymptotics.py` | `temperature.py` |

Правка импортов: `examples/example_runner.py:54-64`, `examples/05_standing_table_rp/main.py:40`, `examples/energy_balance_convergence.py` (`_resolve_example`), `gpn_multiphase_solver/diagnostics/__init__.py` (докстринг); тесты `tests/test_examples.py` (`:885`, `_pvt_module`, `_relperm_module`, `_closed_form`, вставки `sys.path` в `TestSharedChecks`), `tests/test_rs_analytics.py:31-35`, `tests/test_example_scripts.py` (`BROKEN_SNIPPETS["b_import_in_main_block"]`).

**Что сделать:**
1. `report/__init__.py`:
   ```python
   """Рисунки с записью файлов и печать проверок расчёта; конвейер run_case (FEAT-030).

   diagnostics/ считает проверки, io/output.py рисует на переданных осях —
   здесь их оформление: PNG в каталог вывода, печать отчётов в консоль,
   наложения на профили. pipeline.run_case — весь штатный набор по конфигу.

   relperm         — кривые ОФП и рабочий диапазон (relperm.png), сводка ОФП;
   pvt             — PVT в стиле PVTO (pvt.png), сводка PVT;
   rs              — наложение R_s^eq(p) на rs_profiles.png, печать проверки R_s;
   closed_form     — наложения и сверка замкнутого решения стационара;
   energy_balance  — energy_balance.png и печать членов баланса энергии;
   mass_balance    — mass_balance.png и печать баланса массы компонентов;
   temperature     — печать однофазной асимптотики температуры;
   pipeline        — run_case: конфиг → расчёт → CSV + рисунки + проверки.
   """
   ```
   (строку `pipeline` дописать на шаге 5.)
2. В каждом перенесённом модуле:
   - удалить `import matplotlib` + `matplotlib.use("Agg")`; оставить `import matplotlib.pyplot as plt` на уровне модуля (импорт pyplot режим не выбирает — он выбирается при первой фигуре; это проверит тест шага 6 `test_report_import_has_no_side_effects`);
   - удалить вставки `sys.path` (`energy_balance.py:50-55`, `mass_balance.py:42-47`) и переменные `_EXAMPLES`, `_ROOT`;
   - импорты пакета — относительные: `from ..io.figures import save_figure`, `from ..io.output import ...`, `from ..diagnostics.rs import ...`, `from ..energy.balance import compute_energy_balance`, `from ..mass_balance import compute_mass_balance`, `from ..factory import create_relperm` (внутри функций — тоже относительный: `from ..factory import create_pvt`);
   - удалить блоки `if __name__ == "__main__":` (`energy_balance.py:131-147`, `mass_balance.py:91-107`, `temperature_asymptotics.py:55-76`) — автономный запуск части штатного набора заменяет команда (шаг 6); строки «Запуск для конкретного примера: …» в докстрингах — заменить на «Входит в штатный набор `run_case` (`report/pipeline.py`).»;
   - `energy_balance.py`: удалить `_resolve_example` (`:113-128`) и `report_energy_balance` (`:94-110`) — она нигде не вызывается (`git grep -n "report_energy_balance"` — только определение и докстринг модуля `:36`); строку докстринга `:36` удалить, `:33-36` переписать: «Здесь — `plot_energy_balance`: график и печать поверх `compute_energy_balance`.»;
   - `mass_balance.py`: удалить импорт `_resolve_example` (`:52-53`);
   - упоминания `example_runner`/`run_example` в докстрингах и комментариях → `run_case` (`report/pipeline.py`); «общий модуль для всех примеров» можно оставить — смысл тот же.
3. `examples/energy_balance_convergence.py`: своя копия `_resolve_example` (`:172-…`) → удалить; импорт `from two_phase_analytics import _resolve_example` (одна копия правила разбора имени примера — как было у `mass_balance.py`, импортировавшего её из `energy_balance.py`). Комментарий: `# Одна копия правила разбора имени примера («03» → 03_standing_corey) — two_phase_analytics.py`.
4. `examples/example_runner.py:54-64`: импорты из пакета — `from gpn_multiphase_solver.report.relperm import plot_relperm`, `...report.rs import make_overlay_rs, report_rs`, `...report.closed_form import (make_overlay_pressure, make_overlay_saturation, report_closed)`, `...report.energy_balance import plot_energy_balance`, `...report.mass_balance import plot_mass_balance`, `...report.temperature import report_asymptotics`, `...report.pvt import plot_pvt, report_pvt`, `...io.figures import save_figure, export_emf`. Комментарий `:54-55` («Модуль лежит рядом, в examples/…») удалить.
5. `examples/05_standing_table_rp/main.py:40`: `from relperm_plot import report_relperm` → `from gpn_multiphase_solver.report.relperm import report_relperm`.
6. `diagnostics/__init__.py`, последняя фраза докстринга: «Печать отчётов и рисунки примеров — examples/.» → «Печать отчётов и рисунки с записью файлов — report/ (FEAT-030).» Ещё три живые ссылки пакета на переезжающие модули (аудит; строки на `7b636eb`):
   - `gpn_multiphase_solver/diagnostics/rs.py:73` — «(examples/pvt_plot._physical_rs сверяется с ней побитово)» → «(report/pvt._physical_rs …)»;
   - `gpn_multiphase_solver/io/config.py:155` — «проверки R_s примеров (examples/rs_analytics.py, DEBT-026)» → «проверки R_s (report/rs.py, DEBT-026)»;
   - `gpn_multiphase_solver/mass_balance.py:21-22` — «график и печать — examples/mass_balance.py» → «— report/mass_balance.py».
   Первые строки докстрингов `diagnostics/*.py` («DEBT-011: из examples/…») — история происхождения, не трогать. Проверка: `git grep -n "examples/" -- gpn_multiphase_solver` — остаются только эти первые строки докстрингов `diagnostics/*.py`.
7. Тесты:
   - `tests/test_rs_analytics.py:31-35`: убрать вставку `sys.path`; `import rs_analytics` → `from gpn_multiphase_solver.report import rs as rs_analytics` (имя в тестах прежнее, правок ниже нет); `_EXAMPLES` оставить — по нему читаются конфиги; комментарий `:1` → «печать и наложение — gpn_multiphase_solver/report/rs.py».
   - `tests/test_examples.py`: `_pvt_module()` → `from gpn_multiphase_solver.report import pvt as pvt_plot; return pvt_plot`; `_relperm_module()` → `report.relperm`; `_closed_form()` → `report.closed_form`; `:885` `from rs_analytics import report_rs` → `from gpn_multiphase_solver.report.rs import report_rs`; вставки `sys.path.insert(0, str(EXAMPLES_DIR))` в тестах, которые после правки берут только пакет (`:691`, `:716`, `:742`, `:777`, `:884`, `:933`, `:1032`, `:1367`, `:1812`) — удалить; докстринги помощников — «модуль пакета report/…».
   - `tests/test_example_scripts.py`, `BROKEN_SNIPPETS["b_import_in_main_block"]`: `from closed_form import no_such_name` → `from convergence import no_such_name`.
   - `tests/test_examples.py`, `SHARED_CHECK_MODULES` (`:634-641`) → `["energy_balance_convergence.py", "two_phase_analytics.py"]`; комментарий над списком: «Модули проверок, оставшиеся в examples/ после FEAT-030: печать и рисунки общих проверок — в пакете, gpn_multiphase_solver/report/».

**Проверка после шага:**
- Тест: `$PY -m pytest tests/test_rs_analytics.py tests/test_example_scripts.py tests/test_public_api.py -q`; `$PY -m pytest tests/test_examples.py -m "not slow" -q`.
- Регресс: быстрый.
- Частичный снимок (~3 мин; примеры ещё идут через `main.py` → `run_example`):
  ```powershell
  $env:PYTHONPATH = "<W>\numerical_solver;<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"
  & $PY -X utf8 <W>\vault\issues\feat-030\probes\snapshot_examples.py snap --tree . --out <W>\vault\issues\feat-030\probes\out\snap_step2.json --only 01 05 10 13a 15 16
  & $PY -X utf8 <W>\vault\issues\feat-030\probes\snapshot_examples.py compare <W>\vault\issues\feat-030\probes\out\snap_before.json <W>\vault\issues\feat-030\probes\out\snap_step2.json
  ```
  Ожидание: 6 «совпадает»; остальные 17 — «есть только в до» (частичный снимок), это не расхождение.

**Подводные камни:** `test_public_api.py::test_package_does_not_depend_on_examples` ловит любой абсолютный импорт имени модуля `examples/` и любое `sys.path` в пакете — оставшаяся вставка из `energy_balance.py` его уронит. Относительные импорты (`from .closed_form`) страж не трогает. Имя `report/closed_form.py` совпадает с `diagnostics/closed_form.py` — внутри `report/closed_form.py` импорт `from ..diagnostics.closed_form import saturation_from_numeric, solve_closed`, не `from .closed_form`.
**Зависимости:** требует шаг 1; блокирует шаг 5.
**Оценка:** ~150 строк правок, ~60 мин.

---

### Шаг 3: поля `output`: `title`, `n_profiles`, `steady_state`, `closed_form_overlays`

**Цель:** конфиг задаёт состав штатного вывода; ошибки полей ловит `load_config`.
**Файлы:** `numerical_solver/gpn_multiphase_solver/io/config.py` (`OutputConfig` `:191-199`, `_validate` после `:639`); `numerical_solver/tests/test_config.py`.

**Что сделать:**
1. `OutputConfig` (после `log_level`):
   ```python
   # Состав штатного вывода run_case и команды (FEAT-030). Параметры
   # оформления, на расчёт не влияют.
   # Заголовок рисунков и печати; None — имя папки конфига.
   title: Optional[str] = None
   # Число моментов на профильных графиках, равномерно по времени (не меньше
   # двух); None — четыре опорных момента по номеру записи.
   n_profiles: Optional[int] = None
   # Стационарная аналитика: замкнутое решение (наложения на профили p и S_g,
   # сверка report_closed) и асимптотика температуры. Это пределы t -> inf при
   # одном режиме скважины; по умолчанию выключена — в сценарии, где
   # стационар не достигнут, сверка показала бы расхождение, не связанное
   # с точностью расчёта (решение пользователя 2026-10-13).
   steady_state: bool = False
   # На каких профилях рисовать замкнутое решение при steady_state = true:
   # подмножество ["p", "Sg"]. Сверка report_closed печатается при любом.
   closed_form_overlays: list[str] = field(default_factory=lambda: ["p", "Sg"])
   ```
2. `_validate`, после проверки `log_level` (`:639`):
   ```python
   # Поля состава вывода (FEAT-030). Тип — явно: секция output не входит в
   # _NUMERIC_SECTIONS, а bool — подкласс int (true в n_profiles — опечатка).
   oc = cfg.output
   if oc.title is not None and (not isinstance(oc.title, str) or not oc.title.strip()):
       raise ValueError(f"output.title должен быть непустой строкой или null, получено {oc.title!r}")
   n = oc.n_profiles
   if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 2):
       raise ValueError(f"output.n_profiles должен быть целым ≥ 2 или null, получено {n!r}")
   if not isinstance(oc.steady_state, bool):
       raise ValueError(f"output.steady_state должен быть true или false, получено {oc.steady_state!r}")
   ov = oc.closed_form_overlays
   if (not isinstance(ov, list) or any(f not in ("p", "Sg") for f in ov)
           or len(set(ov)) != len(ov)):
       raise ValueError(f'output.closed_form_overlays — список без повторов из "p", "Sg", получено {ov!r}')
   ```
   (Сравнение `f not in ("p", "Sg")` для нестрокового `f` даёт `True` — отказ, а не `TypeError`.)
3. Тесты — раздел 5, «Шаг 3».

**Проверка после шага:**
- Тест: `$PY -m pytest tests/test_config.py -q`.
- Регресс: быстрый (конфиги примеров полей ещё не имеют — умолчания; `run_example` их не читает).

**Подводные камни:** `test_config.py::test_field_list_covers_known_fields` и `_FLOAT_FIELDS` — по секциям `_NUMERIC_SECTIONS`, `output` в них нет — не затрагиваются. `field` уже импортирован в `config.py` (`SimulationConfig` использует `field(default_factory=...)`).
**Зависимости:** требует шаг 0; блокирует шаги 4, 5.
**Оценка:** ~40 строк кода, ~60 строк тестов, ~35 мин.

---

### Шаг 4: поля `output` в 23 конфигах; проверки текста `main.py` → проверки конфига

**Цель:** параметры примеров записаны в конфигах; тесты проверяют конфиг, а не текст `main.py`.
**Файлы:** `numerical_solver/examples/*/config.json` (23); `numerical_solver/tests/test_examples.py`.

**Что сделать:**
1. Конфиги — пробой (значения в `VALUES`, сняты с `main.py` 2026-10-13; проверены без записи — `add_output_fields.out.txt`, 23 «ОК»):
   ```powershell
   cd <W>\numerical_solver
   & $PY -X utf8 <W>\vault\issues\feat-030\probes\add_output_fields.py           # проверка
   & $PY -X utf8 <W>\vault\issues\feat-030\probes\add_output_fields.py --write   # запись
   git diff --stat -- examples/*/config.json    # 23 файла, по 2–4 строки
   ```
   Перед записью — сверить `VALUES` с `main.py` базы: `git grep -n "title=\|TITLE =\|title = \|n_profiles=\|steady_state=\|overlays=" -- "examples/*/main.py"`. FEAT-032 (если влит) меняет у 16/17 `numerics`, не `output` — пробу не задевает.
2. `tests/test_examples.py` — проверки текста `main.py` → конфиг. Помощник рядом с `_run` (`:86`):
   ```python
   def _output(name: str):
       """Секция output конфига примера (FEAT-030): состав штатного вывода."""
       return load_config(EXAMPLES_DIR / name / "config.json").output
   ```
   Замены (имена тестов — `test_main_*` → `test_config_*`, докстринги — «конфиг» вместо «main.py», смысл прежний):

   | тест (класс) | было | стало |
   |---|---|---|
   | 13a `test_main_plots_six_moments` | `"n_profiles=6" in text` | `_output(NAME).n_profiles == 6` |
   | 13a `test_main_disables_saturation_overlay` | `'overlays={"Sg": None}' in text` | `o.steady_state is True and o.closed_form_overlays == ["p"]` |
   | 15 `test_main_plots_six_moments` | `"n_profiles=6"` | `n_profiles == 6` |
   | 15 `test_main_disables_closed_form_overlays` | `'overlays={"p": None, "Sg": None}'` | `steady_state is True and closed_form_overlays == []` |
   | 14 `test_main_disables_steady_state` | `"steady_state=False"` | `steady_state is False` |
   | 13b `test_main_plots_seven_moments`, `test_main_disables_steady_state` | `n_profiles=7`, `steady_state=False` | `== 7`, `is False` |
   | 16 `test_main_settings` | `n_profiles=7`, `steady_state=False`, `"overlays=" not in text` | `== 7`, `is False`, `closed_form_overlays == ["p", "Sg"]` |
   | 19–21 `test_main_disables_steady_state` | `steady_state=False` | `is False` |
   | 17 `test_main_settings` | как 16 | как 16 |
   | 18 `test_main_settings` | `n_profiles=6`, `steady_state=False`, `"report_and_plot(" in text` | `== 6`, `is False`; `report_and_plot(` — по-прежнему в тексте `main.py` (он остаётся) |

3. Новый тест `TestConfigs.test_output_explicit` — раздел 5, «Шаг 4».

**Проверка после шага:**
- Тест: `$PY -m pytest tests/test_examples.py -m "not slow" -q -k "Config or main_ or config_"`; `$PY -m pytest tests/test_config.py -q`.
- Регресс: быстрый. Вывод примеров не меняется: `run_example` полей не читает.

**Подводные камни:** тесты 13a–18 (кроме проверок текста) стоят на фикстуре `results` (`slow`) — сами проверки конфига быстрые, без расчёта; проверить, что новые тесты не берут фикстуру `results`, иначе они уйдут в `slow`. README 13a, 13b, 14, 15, 16, 17 говорят «в `main.py`» — правятся на шаге 8.
**Зависимости:** требует шаг 3; блокирует шаг 5.
**Оценка:** ~80 строк тестов, ~35 мин.

---

### Шаг 5: `report/pipeline.py` — `run_case`, `CaseResult`; `run_example` — временная обёртка

**Цель:** конвейер — в пакете, с параметрами из конфига, защитой входных файлов и решателем в результате; все 23 `main.py` ещё работают через обёртку, и полный снимок проверяет, что `run_case` даёт тот же вывод.
**Файлы:** новый `numerical_solver/gpn_multiphase_solver/report/pipeline.py`; `numerical_solver/examples/example_runner.py` (сжимается до обёртки); `numerical_solver/gpn_multiphase_solver/report/__init__.py`; `numerical_solver/tests/test_examples.py` (раздел H).

**Контекст:** почему обёртка, а не сразу удаление: удаление `example_runner.py` требует сразу переделать 23 `main.py` и тесты, и проверить «`run_case` = `run_example`» отдельно было бы нечем. С обёрткой шаг 5 проверяется полным снимком через неизменённые `main.py`, а шаг 7 — снимком через команду. Обёртка живёт два шага и удаляется на шаге 7 (переходных псевдонимов в базе не остаётся).

**Что сделать:**
1. `report/pipeline.py` — из `examples/example_runner.py` (тело переносится; отличия перечислены):
   ```python
   """Конвейер расчёта по конфигу: расчёт → CSV + рисунки + печать проверок (FEAT-030).

   Перенесён из examples/example_runner.py: тот же штатный набор, что давал
   run_example каждому примеру. Отличия: состав вывода (заголовок, число
   профилей, стационарная аналитика, наложения замкнутого решения) берётся
   из секции output конфига, аргументы его переопределяют; результат —
   CaseResult с решателем; входные файлы внутри каталога вывода — отказ до
   расчёта. Режим matplotlib и кодировку консоли модуль не трогает —
   cli.configure_batch_run.
   """
   from __future__ import annotations

   import shutil
   import time
   from dataclasses import dataclass
   from pathlib import Path

   import numpy as np
   import matplotlib.pyplot as plt

   from ..factory import SimulatorFactory
   from ..grid.base import Grid
   from ..io.config import SimulationConfig, load_config
   from ..io.figures import export_emf, save_figure
   from ..io.output import (plot_profiles, plot_well_rate, plot_wellbore_dynamics,
                            save_csv, save_well_csv)
   from ..simulator import Simulator
   from ..state import SimulationHistory
   from .closed_form import make_overlay_pressure, make_overlay_saturation, report_closed
   from .energy_balance import plot_energy_balance
   from .mass_balance import plot_mass_balance
   from .pvt import plot_pvt, report_pvt
   from .relperm import plot_relperm
   from .rs import make_overlay_rs, report_rs
   from .temperature import report_asymptotics


   class CaseConfigError(ValueError):
       """Конфиг не читается, не проходит проверку или не собирается фабрикой; расчёт не начат. FEAT-030."""


   class CaseRunError(RuntimeError):
       """Решатель отказал на шаге по времени; результаты прошлого прогона не тронуты. FEAT-030."""


   @dataclass
   class CaseResult:
       """Итог run_case: решатель, история, сетка, конфиг, заголовок, каталог вывода, время расчёта, с. FEAT-030."""
       elapsed: float
       simulator: Simulator
       history: SimulationHistory
       grid: Grid
       config: SimulationConfig
       title: str
       output_dir: Path
   ```
   `run_case`:
   ```python
   def run_case(config_path: str | Path, output_dir: str | Path | None = None, *,
                title: str | None = None, n_profiles: int | None = None,
                steady_state: bool | None = None,
                overlays: dict | None = None) -> CaseResult:
       """Полный штатный расчёт по конфигу: решение → CSV + PNG + печать проверок. FEAT-030.

       ... (абзацы overlays / n_profiles / steady_state — из докстринга
       run_example, плюс: None у title, n_profiles, steady_state — значение из
       секции output конфига; output_dir=None — папка output рядом с конфигом;
       каталог вывода очищается целиком после успешного расчёта.)
       """
       config_path = Path(config_path)
       t_start = time.perf_counter()
       # Ошибки чтения и проверки конфига — до печати и до расчёта. TypeError —
       # лишний ключ секции (строгая распаковка dataclass), KeyError —
       # пропущенный ключ внутри секции (time.history).
       try:
           config = load_config(config_path)
       except (OSError, KeyError, TypeError, ValueError) as exc:
           raise CaseConfigError(f"{config_path}: {exc}") from exc

       out = config.output
       if title is None:
           title = out.title if out.title is not None else config_path.resolve().parent.name
       if n_profiles is None:
           n_profiles = out.n_profiles
       elif isinstance(n_profiles, bool) or not isinstance(n_profiles, int) or n_profiles < 2:
           # Явный аргумент проверяется здесь, а не после расчёта в _profile_times
           raise ValueError(f"n_profiles = {n_profiles!r}: нужно целое не меньше двух")
       if steady_state is None:
           steady_state = out.steady_state
       output_dir = (Path(output_dir) if output_dir is not None
                     else config_path.parent / "output")
       _check_inputs_outside(config_path, config, output_dir)

       print(f"=== {title} ===")
       print(f"Конфиг: {config_path}")

       try:
           simulator, initial_state = SimulatorFactory.from_config(config)
       except (OSError, ValueError) as exc:
           # Таблицы PVT/ОФП не читаются или несогласованы (factory.py) — та
           # же категория: расчёт не начат
           raise CaseConfigError(f"{config_path}: {exc}") from exc
       grid = simulator.grid
       try:
           history = simulator.run(initial_state)
       except RuntimeError as exc:
           # Отказ шага (Simulator._failure_message) или нефизичная T —
           # сообщения решателя написаны для пользователя. Каталог вывода не
           # тронут: очистка — после расчёта.
           raise CaseRunError(str(exc)) from exc
       elapsed = time.perf_counter() - t_start
       ...  # дальше — тело run_example со строки «Чистим output/» без изменений, кроме:
   ```
   - наложения замкнутого решения (было `:139-146`):
     ```python
     two_phase = config.initial_conditions.Rs0 > 0.0
     steady = two_phase and steady_state
     # На каких профилях рисовать замкнутое решение — output.closed_form_overlays
     # (13a: только p; 15: ни на одном). Явный overlay аргумента сильнее.
     fields = out.closed_form_overlays
     p_overlay = _pick_overlay(overlays, "p",
                               make_overlay_pressure(config) if steady and "p" in fields else None)
     sg_overlay = _pick_overlay(overlays, "Sg",
                                make_overlay_saturation(config) if steady and "Sg" in fields else None)
     ```
   - конец: `return CaseResult(elapsed=elapsed, simulator=simulator, history=history, grid=grid, config=config, title=title, output_dir=output_dir)`;
   - строка «Стационарная аналитика отключена (steady_state=False)…» (было `:256-257`) — текст сохранить побайтно: его сверяет снимок и `test_steady_state_false_skips_steady_analytics`;
   - `_pick_overlay`, `_profile_times`, `_plot_field`, `_print_summary` — без изменений.
   - Защита входных файлов (решение 3):
     ```python
     def _check_inputs_outside(config_path: Path, config, output_dir: Path) -> None:
         """Конфиг и его CSV не лежат внутри каталога вывода: его очистка их удалила бы. FEAT-030."""
         # Каталог вывода очищается целиком (shutil.rmtree) после расчёта —
         # решение пользователя 2026-10-13. Узкая защита — от самого опасного
         # случая: --output . из папки конфига стёр бы конфиг и таблицы.
         out = output_dir.resolve()
         names = (config.pvt.oil_pvt_file, config.pvt.gas_pvt_file, config.relperm.file)
         inputs = [config_path] + [config.config_dir / n for n in names if n]
         for f in inputs:
             f = f.resolve()
             if f == out or out in f.parents:
                 raise CaseConfigError(
                     f"каталог вывода {out} содержит входной файл {f}: после расчёта "
                     f"каталог очищается целиком, и файл был бы удалён. Укажите "
                     f"другой каталог вывода.")
     ```
2. `report/__init__.py` — строка `pipeline` в докстринге.
3. `examples/example_runner.py` — **временная обёртка** (весь прежний код удалить):
   ```python
   """Временная обёртка FEAT-030: run_example → gpn_multiphase_solver.report.pipeline.run_case.

   Живёт до шага 7 плана FEAT-030 (vault/plans/feat-030 run-command-from-config.md):
   main.py примеров ещё зовут run_example, и полный снимок их вывода
   проверяет, что run_case даёт тот же вывод. На шаге 7 файл удаляется.
   """
   import sys

   # Как прежде при импорте example_runner — консоль UTF-8 и matplotlib без
   # окна; теперь это делает команда (cli.configure_batch_run, шаг 6).
   for _stream in (sys.stdout, sys.stderr):
       if hasattr(_stream, "reconfigure"):
           _stream.reconfigure(encoding="utf-8", errors="replace")
   import matplotlib  # noqa: E402
   matplotlib.use("Agg")

   from gpn_multiphase_solver.report.pipeline import run_case  # noqa: E402


   def run_example(config_path, output_dir, title, overlays=None,
                   n_profiles=None, steady_state=True) -> tuple:
       """Прежняя сигнатура и умолчание steady_state=True; возврат (elapsed, history, grid, config)."""
       r = run_case(config_path, output_dir, title=title, overlays=overlays,
                    n_profiles=n_profiles, steady_state=steady_state)
       return r.elapsed, r.history, r.grid, r.config
   ```
   `steady_state=True` по умолчанию — как было: обёртка обязана повторять старое поведение `main.py` 01–12, 04a, 03, 05 (они флаг не передают).
4. Тесты `tests/test_examples.py`, раздел H — на `run_case` (раздел 5, «Шаг 5»): `test_pipeline_writes_output`, `test_profile_times_default_and_uniform`, `test_pick_overlay_none_disables_default`, `test_steady_state_false_skips_steady_analytics` (подмена — `monkeypatch.setattr(pipeline, name, spy(name))` для `import gpn_multiphase_solver.report.pipeline as pipeline`), `test_energy_balance_reported_for_all_examples` — без `sys.path` и `example_runner`; новые — четыре.

**Проверка после шага:**
- Тест: `$PY -m pytest tests/test_examples.py -m "not slow" -q -k "pipeline or profile_times or pick_overlay or steady_state or run_case or energy_balance_reported"`.
- Регресс: быстрый.
- **Полный снимок** (~12 мин; все 23 через `main.py` → обёртка → `run_case`):
  ```powershell
  $env:PYTHONPATH = "<W>\numerical_solver;<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"
  & $PY -X utf8 <W>\vault\issues\feat-030\probes\snapshot_examples.py snap --tree . --out <W>\vault\issues\feat-030\probes\out\snap_step5.json
  & $PY -X utf8 <W>\vault\issues\feat-030\probes\snapshot_examples.py compare <W>\vault\issues\feat-030\probes\out\snap_before.json <W>\vault\issues\feat-030\probes\out\snap_step5.json
  ```
  Ожидание: 23 «совпадает» (у 18 — без файлов с временем выполнения).

**Подводные камни:**
- Порядок печати: заголовок теперь — после `load_config` (заголовок берётся из конфига). stdout не меняется; предупреждения `load_config` (stderr: удалённые ключи, большой скин, закрытая скважина — `_warn_well_shut`) выходят раньше заголовка. Снимок сравнивает потоки по отдельности, порядок между ними не виден; у примеров удалённых ключей нет (`TestConfigs.test_no_removed_keys`), прочие предупреждения, если есть, совпадут текстом.
- `Конфиг: {config_path}` — путь как передан; `main.py` передают абсолютный (`Path(__file__).parent`, Python ≥ 3.9 даёт абсолютный `__file__`).
- `title` из конфига у 23 примеров совпадает с аргументом `main.py` (проба шага 4), но обёртка передаёт аргумент — снимок шага 5 конфиговый заголовок ещё не проверяет; проверит снимок шага 7.
- Импорт `Simulator`, `Grid`, `SimulationHistory` в `pipeline.py` — для аннотаций `CaseResult`; цикла нет: `factory` импортирует `simulator`, `report` никто из ядра не импортирует.
**Зависимости:** требует шаги 1–4; блокирует шаги 6, 7.
**Оценка:** ~200 строк (перенос) + ~120 строк тестов, ~90 мин + 12 мин снимок.

---

### Шаг 6: команда — `cli.py`, `__main__.py`, `[project.scripts]`

**Цель:** `python -m gpn_multiphase_solver run config.json` и `gpn-solver run config.json` работают из любого каталога; коды возврата 0/1/2.
**Файлы:** новые `numerical_solver/gpn_multiphase_solver/cli.py`, `numerical_solver/gpn_multiphase_solver/__main__.py`, `numerical_solver/tests/test_cli.py`; `numerical_solver/pyproject.toml`.

**Что сделать:**
1. `cli.py`:
   ```python
   """Команда расчёта по конфигу: python -m gpn_multiphase_solver run config.json (FEAT-030).

   Штатный набор — run_case (report/pipeline.py): CSV истории и профилей,
   рисунки, печать проверок. Коды возврата: 0 — расчёт завершён; 1 — решатель
   отказал на шаге по времени; 2 — ошибка аргументов или конфига (расчёт не
   начат).
   """
   from __future__ import annotations

   import argparse
   import sys
   from pathlib import Path


   def configure_batch_run() -> None:
       """Консоль UTF-8 и matplotlib без окна (Agg) — для расчёта из командной строки. FEAT-030."""
       # Консоль Windows по умолчанию cp1251, а печать проверок содержит
       # символы вне неё (м³ст/с, λ, μ, ≠, →): print упал бы с
       # UnicodeEncodeError уже после расчёта. Файлы (CSV, PNG) пишутся своими
       # кодировками и этим не затрагиваются. Прежде это делал импорт
       # examples/example_runner — модуль пакета так поступать не должен.
       for stream in (sys.stdout, sys.stderr):
           if hasattr(stream, "reconfigure"):
               stream.reconfigure(encoding="utf-8", errors="replace")
       # Agg — без окон: в консоли и на сервере без графики интерактивный
       # режим падает. Переключение после импорта pyplot допустимо — режим
       # выбирается при первой фигуре.
       import matplotlib
       matplotlib.use("Agg")


   def _profiles(text: str) -> int:
       """Аргумент --profiles: целое не меньше двух."""
       try:
           n = int(text)
       except ValueError:
           raise argparse.ArgumentTypeError(f"нужно целое число, получено {text!r}")
       if n < 2:
           raise argparse.ArgumentTypeError(f"нужно не меньше двух моментов, получено {n}")
       return n


   def _parser(prog: str | None) -> argparse.ArgumentParser:
       """Разбор аргументов: подкоманда run и её параметры."""
       p = argparse.ArgumentParser(prog=prog, description="Расчёт притока газированной нефти к скважине с температурой (gpn_multiphase_solver).")
       sub = p.add_subparsers(dest="command", required=True, metavar="команда")
       run = sub.add_parser("run", help="расчёт по конфигу: CSV, рисунки, печать проверок",
                            epilog="Коды возврата: 0 — расчёт завершён; 1 — решатель отказал; 2 — ошибка аргументов или конфига. Каталог вывода после расчёта очищается целиком.")
       run.add_argument("config", type=Path, help="JSON-конфиг расчёта")
       run.add_argument("--output", type=Path, default=None, help="каталог результатов (по умолчанию — output рядом с конфигом); очищается целиком")
       run.add_argument("--title", default=None, help="заголовок рисунков и печати (по умолчанию — output.title конфига или имя его папки)")
       run.add_argument("--profiles", type=_profiles, default=None, metavar="N", help="число моментов на профильных графиках (по умолчанию — output.n_profiles конфига)")
       return p


   def main(argv: list[str] | None = None, prog: str | None = None) -> int:
       """Точка входа команды: разбор аргументов → run_case → код возврата. FEAT-030."""
       configure_batch_run()
       args = _parser(prog).parse_args(argv)   # ошибка аргументов — SystemExit(2)
       # Импорт конвейера — после configure_batch_run и разбора: --help не
       # тянет scipy, решатель и прототип (matplotlib и numpy импортирует
       # configure_batch_run — режим Agg)
       from .report.pipeline import CaseConfigError, CaseRunError, run_case
       # Абсолютные пути: печать «Конфиг: …» однозначна при любом каталоге
       # запуска (и совпадает с прежней печатью main.py)
       config = args.config.resolve()
       output = args.output.resolve() if args.output is not None else None
       try:
           run_case(config, output, title=args.title, n_profiles=args.profiles)
       except CaseConfigError as exc:
           print(f"Ошибка конфига: {exc}", file=sys.stderr)
           return 2
       except CaseRunError as exc:
           print(f"Расчёт не завершён: {exc}", file=sys.stderr)
           return 1
       return 0
   ```
   Прочие исключения (ошибка кода) — с трассировкой, код 1 (поведение Python): трассировка нужна отделу разработки.
2. `__main__.py`:
   ```python
   """python -m gpn_multiphase_solver — команда расчёта по конфигу (FEAT-030)."""
   import sys

   from .cli import main

   if __name__ == "__main__":
       sys.exit(main(prog="python -m gpn_multiphase_solver"))
   ```
3. `pyproject.toml`, после `[project.optional-dependencies]`:
   ```toml
   [project.scripts]
   # Команда расчёта по конфигу (FEAT-030) — то же, что
   # python -m gpn_multiphase_solver run config.json. На Windows gpn-solver.exe
   # ложится в Scripts\ окружения: без активации venv её нет в PATH, тогда —
   # форма python -m.
   gpn-solver = "gpn_multiphase_solver.cli:main"
   ```
4. Тесты `tests/test_cli.py` — раздел 5, «Шаг 6» (13 тестов).

**Проверка после шага:**
- Тест: `$PY -m pytest tests/test_cli.py -q`.
- Вручную: `cd <W>\numerical_solver; & $PY -m gpn_multiphase_solver run examples\05_standing_table_rp\config.json --output <W>\vault\issues\feat-030\probes\out\cli05` — код 0, 12 файлов; печать как у `main.py` 05 до его собственной части.
- Регресс: быстрый.

**Подводные камни:** `configure_batch_run` в тестах в том же процессе перенастраивает поток захвата pytest (`capsys` — `TextIOWrapper`, `reconfigure` есть) — безвредно; режим matplotlib становится Agg на всю сессию — так и нужно тестам. В подпроцессах тестов — `PYTHONPATH` на `numerical_solver` этого дерева и прототип (раздел 5), иначе в worktree подпроцесс возьмёт пакет основного каталога.
**Зависимости:** требует шаг 5; блокирует шаг 7.
**Оценка:** ~110 строк кода, ~200 строк тестов, ~70 мин.

---

### Шаг 7: примеры на команду — удаление обёртки и 17 `main.py`, `main.py` 01–05/18 на `run_case`

**Цель:** пример = конфиг + README (+ свои скрипты); ни одного импорта `example_runner`; `run_all.py` запускает команду.
**Файлы:**
- удалить: `numerical_solver/examples/example_runner.py`; `main.py` у 04a, 06, 07, 08, 09, 10, 11, 12, 13a, 13b, 14, 15, 16, 17, 19, 20, 21 (17 файлов);
- правка: `main.py` 01, 02, 03, 04, 05, 18; `examples/04_table_table/grid_convergence.py`, `examples/04a_high_gas_saturation/grid_convergence.py`; `examples/run_all.py`;
- тесты: `numerical_solver/tests/test_examples.py` (`TestStructure`, `SHARED_EXAMPLE_FILES` — сам), `numerical_solver/tests/test_example_scripts.py` ((д), `BROKEN_SNIPPETS["d_run_example_keyword"]`, комментарии), `numerical_solver/tests/conftest.py`;
- проба: снимок «после».

**Что сделать:**
1. `git rm` обёртки и 17 `main.py`. Перед удалением `main.py` 04a — перенести его докстринг (суть сценария) в README 04a, если там этого нет (`git grep -n "k_rg^max = 0.0014\|ОБРАТНЫМ" -- examples/04a_high_gas_saturation/README.md`); у прочих 16 докстринг — одна строка, повторяющая README.
2. `main.py` 01, 02, 03, 04, 05, 18 — общий заголовок (вместо `sys.path`-вставки `examples/` для `example_runner`, `import matplotlib; matplotlib.use("Agg")` и импорта `figure_io`):
   ```python
   from gpn_multiphase_solver.cli import configure_batch_run
   # Консоль UTF-8 и matplotlib без окна — как у команды (FEAT-030)
   configure_batch_run()

   from gpn_multiphase_solver.io.figures import save_figure, export_emf  # noqa: E402  (01, 02, 05, 18)
   from gpn_multiphase_solver.report.pipeline import run_case  # noqa: E402
   ```
   - вставка `examples/` в `sys.path` остаётся только у 03, 04, 05 — для `import two_phase_analytics as tpa`; комментарий: `# examples/ в sys.path — для two_phase_analytics (печать проверок стационара 03–05)`. У 01, 02, 18 — удалить (папка самого скрипта в `sys.path` и так, её вставки `sys.path.insert(0, str(Path(__file__).resolve().parent))` в 01, 02, 03, 05 — удалить как лишние: Python кладёт папку запускаемого скрипта первой);
   - вызов: `r = run_case(here / "config.json", here / "output")` (+ `overlays={"T": overlay_temperature}` у 03); заголовок, `n_profiles`, `steady_state` — из конфига; там, где ниже нужен заголовок (`TITLE`, `title`), — `r.title`; `history, grid, config` → `r.history, r.grid, r.config`;
   - второй `Simulator` убрать: 03 (`:96-99`), 04 (`:32-34`), 05 (`:94-97`) — `pvt = r.simulator.pvt`, `relperm = r.simulator.relperm`; 01, 02 — `_add_temperature_analytics(history, grid, config, pvt, output_dir, title)`: новый аргумент `pvt` вместо `SimulatorFactory.from_config` внутри (01 `:73`, `:84-85`; 02 `:117`, `:129-130`), вызов с `r.simulator.pvt` (печать не меняется — проба `factory_warnings`, 0 предупреждений);
   - комментарии «считает run_example» → «считает run_case (штатный набор)»; «вторым пакетом: первый конвертировал run_example» → «… первый конвертировал run_case»;
   - 18: `_, history, grid, _ = run_example(...)` → `r = run_case(here / "config.json", output)`; `prototype_input.report_and_plot(r.history, r.grid, output, r.title)`.
3. `grid_convergence.py` 04 и 04a: `import example_runner  # noqa: E402,F401  (консоль в UTF-8…)` → `from gpn_multiphase_solver.cli import configure_batch_run` + вызов `configure_batch_run()` с комментарием `# консоль UTF-8: скрипт печатает м³ст/с`; вставку `HERE.parents[0]` (examples/) в `sys.path` оставить у 04a (там `from convergence import run_series`), у 04 — проверить, нужна ли (`git grep -n "^from\|^import" -- examples/04_table_table/grid_convergence.py`).
4. `run_all.py`:
   - `find_examples()` — папки `NN_имя` с `config.json` (докстринг: «с config.json; у примера со своим main.py запускается он, иначе — команда пакета»);
   - запуск: `cmd = [sys.executable, str(example / "main.py")] if (example / "main.py").is_file() else [sys.executable, "-m", "gpn_multiphase_solver", "run", str(example / "config.json")]`; `subprocess.run(cmd, cwd=EXAMPLES_DIR.parent, ...)` — каталог запуска `numerical_solver`: команда `-m` берёт пакет этого дерева;
   - докстринг модуля: «Каждый пример запускается отдельным процессом — командой пакета или своим main.py».
5. Тесты:
   - `TestStructure.test_required_files` → `config.json`, `README.md` у всех; новый `test_main_py_only_with_own_logic` (раздел 5); `test_runner_and_run_all_exist` → `test_run_all_and_readme_exist` (`run_all.py`, `README.md`; `example_runner.py` — **отсутствует**).
   - `test_example_scripts.py` (д) `:190-206`: искать вызовы `run_case`; сигнатура — `inspect.signature(gpn_multiphase_solver.report.pipeline.run_case)`; импорт модуля — `importlib.import_module("gpn_multiphase_solver.report.pipeline")`; комментарии «main.py 17 из 22 примеров — только вызов run_example» → «main.py 01–05, 18 зовут run_case; переименованный параметр ломал бы их TypeError при запуске»; докстринг модуля `:19` и `:130` — `run_case`. `BROKEN_SNIPPETS["d_run_example_keyword"]` → ключ `"d_run_case_keyword"`: `"from gpn_multiphase_solver.report.pipeline import run_case\nrun_case(config_path=1, output_dir=2, no_such_arg=4)\n"`.
   - устаревшие комментарии (аудит): докстринг `test_example_scripts.py::test_no_private_solver_access` — «Импорт приватных имён между модулями examples/ (_resolve_example) — их внутреннее дело до FEAT-030 и не ловится» → «… (_resolve_example из two_phase_analytics.py) — их внутреннее дело и не ловится»; комментарий над `SHARED_EXAMPLE_FILES` (`test_examples.py:643-656`) описывает порядок `sys.path` в `main.py` 01–05 и «остальных main.py» — переписать: `main.py` остались у 01–05, 18; 03–05 вставляют `examples/` (для `two_phase_analytics`), папку скрипта Python кладёт первой сам — копия общего модуля в папке примера перекрыла бы общий модуль; механизм BUG-004 тот же;
   - `conftest.py`: в начало (после докстринга) — `import matplotlib` + `matplotlib.use("Agg")` с комментарием: «Режим без окон на всю сессию: модули пакета (report/) больше не выбирают его при импорте (FEAT-030), а тесты рисуют — run_case, report.pvt». Сейчас его задают отдельные тестовые модули (`test_output.py:15`), и порядок сбора решает, кто первый.
6. Снимок «после» (~12 мин) и сравнение с «до»:
   ```powershell
   $env:PYTHONPATH = "<W>\numerical_solver;<W>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3"
   & $PY -X utf8 <W>\vault\issues\feat-030\probes\snapshot_examples.py snap --tree . --out <W>\vault\issues\feat-030\probes\out\snap_after.json
   & $PY -X utf8 <W>\vault\issues\feat-030\probes\snapshot_examples.py compare <W>\vault\issues\feat-030\probes\out\snap_before.json <W>\vault\issues\feat-030\probes\out\snap_after.json
   ```
   Ожидание: 17 примеров — `(command)`, 6 — `(main.py)`; 23 «совпадает». Совпадение stdout у командных — проверка заголовка из конфига и абсолютного пути.

**Проверка после шага:**
- Тест: `$PY -m pytest tests/test_examples.py tests/test_example_scripts.py tests/test_packaging.py tests/test_public_api.py -m "not slow" -q`.
- Регресс: **полный** — шаг меняет `tests/conftest.py`, удаляет обёртку, которой пользовались тяжёлые тесты, и меняет параметры фикстур; ошибки ловят тесты `slow`. `$PY -m pytest tests/ -q`, ~10 мин.

**Подводные камни:**
- `test_packaging.py::test_code_does_not_insert_prototype_path` требует `found > 10` вставок `sys.path` (сейчас 73; уйдут ≈ 40: 17 `main.py`, вставки у 01/02/18, модули шага 2, тестовые вставки `examples/`). Останется ≈ 30 — с запасом; число записать в журнал.
- `test_no_duplicate_helper_scripts` параметризован по `examples/*.py` с диска — 16 → 7 параметров, правок не требует.
- `EXAMPLE_SCRIPTS` в `test_example_scripts.py` — 46 → 20 скриптов (−52 параметра двух тестов) — ожидаемо.
- Удалённый `main.py` у 04a: README 04a (`:448-459`) называет его — правится на шаге 8.
**Зависимости:** требует шаги 5, 6; блокирует шаги 8, 9.
**Оценка:** −700 строк, ~150 строк правок, ~90 мин + 12 мин снимок + 10 мин полный прогон.

---

### Шаг 8: документы — README примеров, `examples/README.md`, `.claude/commands/run.md`, CLAUDE.md

**Цель:** инструкции запуска — команда; упоминания `main.py`/`example_runner`/модулей `examples/` соответствуют коду.
**Файлы:** `numerical_solver/examples/README.md`; `numerical_solver/examples/*/README.md` (23); `.claude/commands/run.md`; `CLAUDE.md` (раздел «numerical_solver (PDE-солвер)»).

**Что сделать:**
1. Найти все места:
   ```powershell
   cd <W>\numerical_solver
   git grep -n -E "main\.py|example_runner|run_example|energy_balance\.py|mass_balance\.py|pvt_plot|relperm_plot|rs_analytics|closed_form\.py|temperature_asymptotics|figure_io|n_profiles|steady_state|overlays=" -- examples/README.md "examples/*/README.md"
   ```
   Правила замены:
   - «Запуск» примера без своего `main.py`: `.venv\Scripts\python examples\NN_имя\main.py` → `.venv\Scripts\python -m gpn_multiphase_solver run examples\NN_имя\config.json` (из `numerical_solver`; результаты — `examples\NN_имя\output\`);
   - «Запуск» 01–05, 18: оставить `main.py` и дописать строку: «Штатный набор без собственной части примера — `python -m gpn_multiphase_solver run examples\NN_имя\config.json`.»;
   - `examples\energy_balance.py NN`, `mass_balance.py NN`, `temperature_asymptotics.py NN` (01 `:215`, 02 `:300`, 03 `:432`) — удалить: баланс печатает и рисует команда; ссылки `[../energy_balance.py](../energy_balance.py)` → `gpn_multiphase_solver/report/energy_balance.py` (ссылка `../../gpn_multiphase_solver/report/energy_balance.py`), аналогично `pvt_plot.py` → `report/pvt.py`, `rs_analytics.py` → `report/rs.py`, `closed_form.py` (печать/наложения) → `report/closed_form.py`;
   - «`n_profiles` в `main.py`», «`steady_state=False` в `main.py`», «`overlays={...}` в `main.py`» (13a `:153`, `:225`; 13b `:190`, `:249`, `:252`; 14 `:213`; 15 `:208`; 16 `:199`, `:279`; 17 `:204`, `:276`) → «`output.n_profiles` в конфиге», «`output.steady_state = false` в конфиге», «`output.closed_form_overlays = ["p"]` / `[]` в конфиге»;
   - «подключает `example_runner`» (03 `:339`, 04 `:369`, 04a `:469`, 05 `:153`) → «ставит штатный набор `run_case` (`gpn_multiphase_solver/report/`)»;
   - таблицы «Файлы примера» (`| main.py | … |`) у примеров без `main.py` — строку удалить, у 01–05/18 — оставить.
2. `examples/README.md`:
   - строка 4: «Каждая подпапка самодостаточна — конфиг, нужные CSV, `main.py` и README» → «… конфиг, нужные CSV и README; у 01–05 и 18 — ещё `main.py` с собственной частью примера»;
   - «Запуск» (`:226-247`): команда для одного примера, `run_all.py` для всех, `gpn-solver run …` как короткая форма (после установки, venv активирован); коды возврата; **предупреждение**: «каталог `--output` после расчёта очищается целиком — не указывайте папку с другими файлами; папку с конфигом или его таблицами команда отвергает»; поля `output` конфига (`title`, `n_profiles`, `steady_state`, `closed_form_overlays`) с умолчаниями и смыслом; что `steady_state` по умолчанию `false` и почему;
   - EMF (`:293-305`): «в конце скрипта» → «в конце расчёта»; остальное без изменений (решение 4);
   - `:436` «отключено флагом `run_example(steady_state=False)`» → «`output.steady_state = false` в конфиге»;
   - «Общие модули проверок» (`:782-822`): таблица — модули пакета `report/` (что рисует/печатает) и оставшиеся `examples/` (`run_all.py`, `two_phase_analytics.py`, `convergence.py`, `energy_balance_convergence.py`, `check_energy_balance_all.py`, `verify_balance_vs_solver.py`, `compare_script_copies.py`); строки «автономный запуск» для `energy_balance.py`, `mass_balance.py`, `temperature_asymptotics.py` — удалить (их заменяет команда);
   - «Автоматические тесты» (`:838-843`): «именованные аргументы `run_example`» → «`run_case`»; добавить `tests/test_cli.py` (команда) одной фразой.
3. `.claude/commands/run.md:35-38`: «Если в `examples/` есть готовый сценарий — предпочесть его» → команда `.venv\Scripts\python -m gpn_multiphase_solver run examples\<сценарий>\config.json`; для 01–05 и 18 — их `main.py`.
4. `CLAUDE.md`, раздел «numerical_solver (PDE-солвер)», после строки «Код: …»: «Расчёт по конфигу: `python -m gpn_multiphase_solver run <config.json>` (или `gpn-solver run …`), результаты — `output/` рядом с конфигом (FEAT-030).»

**Проверка после шага:** `$PY -m pytest tests/ --collect-only -q` (число как после шага 7); `$PY -m pytest tests/test_examples.py -q -k Readme` (обязательные разделы README на месте); `$PY -m pytest tests/test_eq_references.py -q` (ссылки на метки в README примеров).
**Подводные камни:** числа README не трогать — вывод не изменился (снимок шага 7). `TestReadme` требует «Как модифицировать», «увеличить газонасыщенность», `PrototypeHydroAdapter`, `TridiagEnergySolver` — при правке «Запуск» не задеть.
**Зависимости:** требует шаг 7.
**Оценка:** ~24 файла, ~120 строк, ~60 мин.

---

### Шаг 9: итог — приёмка в чистом окружении, полный прогон, vault

**Цель:** команда работает после установки из колёс в новом окружении, из постороннего каталога, и даёт тот же вывод; задача закрыта в vault.
**Файлы:** новая проба `vault/issues/feat-030/probes/clean_env_command.py`; vault (ниже).

**Что сделать:**
1. Проба `clean_env_command.py` — по образцу `vault/issues/debt-059/probes/clean_env_acceptance.py` (сборка колёс `pip wheel`, зависимости `pip download` с ограничениями версий общего venv, `venv_wheels` с `--no-index`). Каталог работы — `<solver>\build\feat030_acceptance\` (`build/` игнорируется git). Проверки (строка «ОК»/«ОШИБКА» на каждую):
   1. колесо `gpn-multiphase-solver` содержит `gpn_multiphase_solver/report/` (8 модулей), `io/figures.py`, `cli.py`, `__main__.py`, а `entry_points.txt` в `*.dist-info` — `gpn-solver = gpn_multiphase_solver.cli:main`;
   Сравнивать с снимком можно только примеры **без своего `main.py`**: у 01–05 и 18 снимок «после» снят их `main.py` (у 03 — наложение $T$ на `temperature_profiles.png` и печать `tpa.report`), а команда даёт штатный набор без этой части. Проверки 2–5 — с `GPN_EXAMPLES_EMF=0`, как снимок.
   2. в `venv_wheels`: копии папок `examples/06_table_corey_rp` и `examples/07_degassing_adiabatic_only` (с CSV; имя папки сохранить — по нему подписан рисунок баланса энергии) в `<work>\cases\`; из `<work>` (посторонний каталог) — `venv_wheels\Scripts\python -I -m gpn_multiphase_solver run cases\06_table_corey_rp\config.json` → код 0; хеши всех 12 файлов `output` равны хешам `06_table_corey_rp` в `snap_after.json` (`files`) — при тех же numpy/matplotlib (ограничения версий) PNG тоже побайтно; если PNG разошлись при равных CSV — записать, это не дефект команды; печать (stdout) после замены пути копии на `<TREE>\examples` равна снимку, кроме строки времени;
   3. `venv_wheels\Scripts\gpn-solver.exe run cases\07_degassing_adiabatic_only\config.json` → код 0, хеши файлов равны снимку `07`;
   4. конфиг с `"output": {"n_profiles": 1}` → код 2, в stderr `output.n_profiles`;
   5. `--output cases\06_table_corey_rp` (папка конфига) → код 2, `config.json` и CSV на месте.
   6. Без `GPN_EXAMPLES_EMF` (как у заказчика) и с `INKSCAPE` на несуществующий путь: команда на `07` → код 0, ровно одно «ПРЕДУПРЕЖДЕНИЕ: Inkscape не найден», в `output\emf\` — SVG без EMF.
   Запуск:
   ```powershell
   cd <W>\numerical_solver
   & $PY -X utf8 <W>\vault\issues\feat-030\probes\clean_env_command.py --snapshot <W>\vault\issues\feat-030\probes\out\snap_after.json
   ```
   Вывод — в `clean_env_command.out.txt` рядом (коммитится, как у DEBT-059).
2. Полный прогон — если после шага 7 менялся код (шаг 8 — только документы, повторять не нужно): `$PY -m pytest tests/ -q`.
3. Vault:
   - `vault/knowledge/decisions/архитектура библиотеки numerical_solver.md`: в дереве «Модульная структура» — `__main__.py`, `cli.py`, `io/figures.py`, `report/` (8 модулей) с однострочными пояснениями; раздел «Диагностика и граница пакет / examples (DEBT-011)» → «… (DEBT-011, FEAT-030)»: абзац «В `examples/` до FEAT-030 …» заменить на «Рисунки с записью файлов, печать и конвейер — `report/` (FEAT-030); в `examples/` — конфиги, README, `main.py` 01–05/18 со своей частью, исследования сходимости и средства разработки»; раздел «Структура JSON-конфига» — секция `output` с четырьмя полями;
   - **новая заметка** `vault/knowledge/decisions/пример — это конфиг и README, штатный набор рисунков и проверок даёт команда пакета.md`: решение модели «Б» (2026-10-10), решения 1–5 этого плана с обоснованием (почему `steady_state` по умолчанию `false`; почему `rmtree` + узкая защита; почему параметры в конфиге, а не флагами), граница `diagnostics/` / `report/` / `io/output.py`, коды возврата, побочные эффекты импорта → `configure_batch_run`; ссылки на [[FEAT-030]], [[DEBT-011]], [[FEAT-031]];
   - `vault/knowledge/decisions/проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП.md` — дописать: с FEAT-030 общий модуль — `gpn_multiphase_solver/report/`, подключение — `run_case`;
   - `vault/knowledge/decisions/рисунки примеров дублируются в SVG и EMF через Inkscape.md` — путь `examples/figure_io.py` → `gpn_multiphase_solver/io/figures.py`; поведение без Inkscape проверено тестом `test_figures.py`;
   - `vault/knowledge/decisions/имена скриптов examples проверяются разбором AST — импорт файла не видит импорты в функциях и обращения к модулю через точку.md` — (д): `run_case`;
   - реестр `vault/roadmap/планируемые фичи.md`, FEAT-030: «Статус: ✅ ГОТОВО (дата)» с итогом (числа тестов N0 → N1, итог сравнения снимков, приёмка); в FEAT-031 — «Зависит от FEAT-030 — выполнено» и что приёмку можно строить на `clean_env_command.py`;
   - `vault/00-home/index.md` — новая заметка решения;
   - комментарий к #104: `vault/issues/feat-030/05-comment-done.md`.

**Проверка после шага:** проба — все «ОК»; полный прогон зелёный.
**Зависимости:** требует шаги 7, 8.
**Оценка:** проба ~180 строк, ~60 мин (из них ~10 мин — сборка и установка).

## 5. Тестовая стратегия

Подтип — инфраструктура: формул нет, физические инварианты проверяет неизменность вывода (снимки) и прежние тесты примеров. Подпроцессы тестов: `env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(SOLVER), str(PROTO)])}` (`SOLVER = Path(__file__).resolve().parents[1]`, `PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"`, как в `test_packaging.py`), `GPN_EXAMPLES_EMF` наследуется из `conftest.py` («0»), `PYTHONIOENCODING=utf-8`.

**Шаг 1 — `tests/test_figures.py` (новый, 3):**
- `test_save_figure_png_only_when_disabled` — `GPN_EXAMPLES_EMF=0`: есть `x.png`, нет `emf/`. Предотвращает: SVG в тестах и при выключенном EMF.
- `test_save_figure_writes_svg_when_enabled` — переменная снята (`monkeypatch.delenv`): `x.png` и `emf/x.svg`, `emf/x.emf` нет (ждёт конвертации).
- `test_export_emf_without_inkscape_keeps_svg` — EMF включён, `INKSCAPE` = `tmp_path / "нет" / "inkscape.com"`: `export_emf` возвращает `[]`, печатает «Inkscape не найден», `emf/x.svg` на месте, код не падает. Закрывает открытый вопрос реестра «поведение на машине без Inkscape не проверено».

**Шаг 3 — `tests/test_config.py` (+14):**
- `test_output_defaults` — минимальный конфиг (`_minimal_raw()`): `title is None`, `n_profiles is None`, `steady_state is False`, `closed_form_overlays == ["p", "Sg"]`.
- `test_output_fields_read` — `{"title": "Скв. 1", "n_profiles": 5, "steady_state": true, "closed_form_overlays": ["p"]}` читаются как есть.
- `test_output_field_rejected` — параметризован, 12 случаев → `ValueError` с именем поля: `title` = `""`, `5`; `n_profiles` = `1`, `2.5`, `true`, `"6"`; `steady_state` = `1`, `"true"`, `null`; `closed_form_overlays` = `"p"`, `["T"]`, `["p", "p"]`. Предотвращает: опечатка в конфиге заказчика молча меняет состав вывода (как `log_level` до DEBT-008).

**Шаг 4 — `tests/test_examples.py`:**
- 13 проверок текста `main.py` → проверки `_output(name)` (таблица шага 4; число тестов то же).
- `TestConfigs.test_output_explicit` (+1) — у каждого из 23 примеров в сыром JSON `output.title` — непустая строка, `output.steady_state` — `bool`; множество примеров с `true` = `{01, 02, 03, 04, 04a, 05, 06, 07, 08, 09, 10, 11, 12, 13a, 15}`. Предотвращает: пример тихо теряет стационарную аналитику из-за смены умолчания на `false`.

**Шаг 5 — `tests/test_examples.py`, раздел H (5 прежних на `run_case` + 4 новых):**
- прежние: `test_pipeline_writes_output` (+ проверка `CaseResult`: `r.simulator.pvt is not None`, `r.title == "тест pipeline"`, `r.output_dir == tmp_path`), `test_profile_times_default_and_uniform`, `test_pick_overlay_none_disables_default`, `test_steady_state_false_skips_steady_analytics`, `test_energy_balance_reported_for_all_examples`;
- `test_run_case_reads_output_section` — копия конфига 05 в `tmp_path` (с `relperm.csv`), `output` = `{"title": "X", "n_profiles": 5, "steady_state": true, "closed_form_overlays": ["p"]}`; шпионы `make_overlay_pressure`, `make_overlay_saturation` (возвращают `None`) и `_profile_times` (пропускает в оригинал, запоминает `n_profiles`): вызван только `make_overlay_pressure`, `_profile_times` получил 5, в stdout `=== X ===`. Пример 05 — ~5 с.
- `test_run_case_refuses_output_containing_inputs` — копия 05; `run_case(cfg, output_dir=cfg.parent)` → `CaseConfigError` с «содержит входной файл»; `Simulator.run` подменён на падение (расчёт не начат); `config.json`, `relperm.csv` на месте.
- `test_run_case_config_errors` — нет файла; лишний ключ `geometry.foo` → `CaseConfigError` (подкласс `ValueError`), до печати заголовка (`capsys` пуст).
- `test_run_case_run_failure` — `Simulator.run` подменён на `RuntimeError("шаг не сошёлся")` → `CaseRunError`, текст сохранён; каталог вывода с файлом-меткой не тронут.

**Шаг 6 — `tests/test_cli.py` (новый, 13):**
1. `test_help_via_module` — подпроцесс `python -m gpn_multiphase_solver run --help` из `tmp_path`: код 0, в выводе `--output`, `--profiles`, «Коды возврата».
2. `test_run_from_foreign_directory` — подпроцесс из `tmp_path`; конфиг — сырой JSON примера 03 с `grid.N = 20`, `time.history = [{"duration": 86400, "dt_out": 43200, "control": "pressure", "p_wf": <p_wf примера 03>}]`, `output.title = "тест команды"`; код 0; в `case/output` 12 файлов (`well_history.csv`, `profiles.csv`, `pressure_profiles.png`, `temperature_profiles.png`, `saturation_profiles.png`, `rs_profiles.png`, `well_rates.png`, `wellbore_dynamics.png`, `relperm.png`, `pvt.png`, `energy_balance.png`, `mass_balance.png`); stdout — `=== тест команды ===`, `Шагов сохранено`; пакет — из этого дерева (тот же `env`, `-c "import gpn_multiphase_solver as g; print(g.__file__)"`). ~8 с.
3. `test_missing_config_returns_2` — в процессе: `main(["run", str(tmp_path / "нет.json")]) == 2`, stderr содержит `нет.json`.
4. `test_invalid_field_returns_2` — `output.n_profiles = 1` → 2, stderr `output.n_profiles`.
5. `test_unknown_key_returns_2` — `geometry.foo` → 2.
6. `test_run_failure_returns_1` — `Simulator.run` подменён на `RuntimeError("шаг не сошёлся")` → 1; stderr содержит «Расчёт не завершён» и текст, без `Traceback`.
7. `test_output_with_config_refused` — `--output <папка конфига>` → 2 до расчёта; конфиг на месте.
8. `test_flags_passed_to_run_case` — шпион `pipeline.run_case`: `main(["run", "cfg.json", "--title", "T", "--profiles", "5", "--output", "o"])` → аргументы: абсолютный путь конфига, абсолютный `o`, `title="T"`, `n_profiles=5`; без `--output` — `None` (умолчание `run_case`).
9. `test_profiles_below_two_rejected` — `--profiles 1` → `SystemExit` с кодом 2.
10. `test_command_required` — `main([])` → `SystemExit` с кодом 2.
11. `test_console_script_declared` — `pyproject.toml` `[project.scripts]["gpn-solver"] == "gpn_multiphase_solver.cli:main"`, объект вызываем (`tomllib` — пропуск на Python 3.10, как в `test_packaging.py`).
12. `test_report_import_has_no_side_effects` — подпроцесс с `PYTHONIOENCODING=cp1251`: `import matplotlib; matplotlib.use("svg"); import gpn_multiphase_solver.report.pipeline, gpn_multiphase_solver.cli; import sys; print(matplotlib.get_backend(), sys.stdout.encoding)` → `svg cp1251`. Предотвращает: возврат `matplotlib.use("Agg")`/`reconfigure` на уровень модуля пакета.
13. `test_configure_batch_run` — подпроцесс с `PYTHONIOENCODING=cp1251`: после `configure_batch_run()` — `Agg utf-8` (`get_backend()` возвращает имя в том регистре, в каком его передали `use`: проба аудита `audit_mpl_console.out.txt`; сравнивать `.lower() == "agg"`).

Допущения тестов 12, 13 и шага 2 о matplotlib 3.11.1 проверены пробой аудита `vault/issues/feat-030/probes/audit_mpl_console.py`: импорт pyplot режим не выбирает (`None`), `use("Agg")` после импорта pyplot работает (`FigureCanvasAgg`), режим `svg`, заданный до импорта модулей ядра, сохраняется; `PYTHONIOENCODING=cp1251` → `cp1251`, `reconfigure` → `utf-8`. Тест 2 (сценарий команды) проверен пробой `audit_key_scenario.py` через `run_example` из постороннего каталога: код 0, 12 файлов, 7.7 с.

**Шаг 7 — `tests/test_examples.py`, `tests/test_example_scripts.py`:**
- `TestStructure.test_required_files` (23) — `config.json`, `README.md`.
- `TestStructure.test_main_py_only_with_own_logic` (+1) — множество папок с `main.py` = `{01, 02, 03, 04, 05, 18}`. Предотвращает: возврат однострочных `main.py` — копий запуска, расходящихся с командой.
- `test_run_all_and_readme_exist` — `run_all.py`, `README.md` есть; `example_runner.py` нет.
- (д) `test_example_scripts.py` — `run_case`; `BROKEN_SNIPPETS["d_run_case_keyword"]` ловится.

**Категории:** unit — `test_figures`, проверки полей конфига, `_profile_times`, `_pick_overlay`; граничные — `n_profiles` = 1, пустой список наложений, отсутствие Inkscape, каталог вывода = папка конфига; согласованность — снимки (23 примера побайтно), конфиг ↔ ожидания тестов; интеграционные — `run_case` на 05/10/01, команда в подпроцессе; валидационные — нет (новых расчётов нет); регрессия — быстрый уровень после шагов, полный после шага 7.

**Число тестов** (N0 — на базе шага 0): +3 (ш. 1) +14 (ш. 3) +1 (ш. 4) +4 (ш. 5) +13 (ш. 6) +1 (ш. 7) = +36; −52 (`EXAMPLE_SCRIPTS` 46 → 20, два теста) −9 (`SHARED_EXAMPLE_FILES` 16 → 7) = −61. Итог ≈ N0 − 25. Записывать `--collect-only` после каждого шага; отклонение больше чем на 3 — разобрать.

## 6. Подводные камни (чеклист 2.5)

| пункт | оценка | как адресовано |
|---|---|---|
| Размерности, формулы | ✅ | новых формул нет; код проверок переносится без правок вычислений |
| Граничные случаи | ⚠️ | однофазные 01/02 (нет `rs_profiles.png` — как прежде), `steady_state` при $R_{s,0} = 0$ (наложений нет, асимптотика печатается — как прежде); `n_profiles` < 2 — отказ в конфиге и в `--profiles`; пустой `closed_form_overlays` (15) |
| Численная устойчивость | ✅ | не затрагивается |
| Обратная совместимость | ⚠️ | **умолчание `steady_state` меняется** (true → false): все 23 примера задают поле явно (шаг 4, тест `test_output_explicit`); внешних пользователей `run_example` нет (только `examples/`); API ядра не меняется |
| Состояние при ошибке | ✅ | ошибки конфига — до печати и расчёта; отказ решателя — до очистки каталога вывода (прежние результаты целы); защита входных файлов — до расчёта |
| Цепочки импорта | ✅ | `report/` импортирует ядро, ядро `report/` не импортирует; `cli` импортирует конвейер внутри `main` |
| Побочные эффекты импорта | ⚠️ | `matplotlib.use`/`reconfigure` — только в `configure_batch_run`; тест 12 шага 6; `conftest.py` задаёт Agg на сессию |
| Производительность | ✅ | тот же конвейер; `--help` не импортирует решатель |
| Пакет и прототип из чужого дерева (worktree) | ⚠️ | подпроцессы тестов и проб — `PYTHONPATH` на пакет **и прототип** дерева; проба снимка проверяет оба пути (аудит: без пути прототипа снимки брали его из основного каталога); запрет `pip install -e` из worktree (раздел 3, п. 5) |
| `rmtree` пользовательского каталога | ⚠️ | решение пользователя — как сейчас; узкая защита входных файлов; предупреждение в `--help` и README |
| EMF у заказчика без Inkscape | ✅ | тест `test_export_emf_without_inkscape_keeps_svg`; приёмка шага 9 |
| Связь с другими задачами | ⚠️ | DEBT-065, FEAT-032 — начинать после влития (шаг 0.1); BUG-025 правит прототип — не блокирует, снимки берут прототип из дерева (раздел 2.1); FEAT-031 строит приёмку на пробе шага 9 |
| Прототип | ✅ | не меняется; регрессия прототипа не нужна |

## 7. Варианты (итог issue и планирования)

- **Параметры примера:** конфиг (принят) / только флаги / `main.py` у всех — решение 1.
- **Каталог вывода:** только свои файлы / метка + отказ / `rmtree` (принят, + защита входных файлов) — решение 3.
- **Проверка переноса конвейера:** сразу удалить `example_runner` и переписать `main.py` (одна проверка в конце, нельзя отделить ошибку переноса от ошибки перехода на команду) / **временная обёртка на два шага** (принят: шаг 5 проверяется снимком через неизменённые `main.py`, шаг 7 — через команду).
- **Имена модулей:** по одному модулю пакета на модуль `examples/` (`git mv`, история сохраняется) против слияния в 2–3 модуля (меньше файлов, но правка всего текста и потеря истории) — принят первый.

## 8. Критерии завершения

- [ ] `python -m gpn_multiphase_solver run <конфиг>` и `gpn-solver run <конфиг>` работают в чистом окружении из постороннего каталога (проба шага 9); коды 0/1/2.
- [ ] Снимки: шаг 5 и шаг 7 — 23 «совпадает» с «до».
- [ ] В `examples/` нет `example_runner.py`, `figure_io.py`, 7 модулей печати/рисунков, 17 однострочных `main.py`; `main.py` 01–05/18 без второго `Simulator`.
- [ ] Модули пакета без побочных эффектов импорта (тест).
- [ ] Быстрый уровень зелёный после каждого шага; полный — после шага 7 (и в конце, если код менялся).
- [ ] Каждая новая функция — однострочный докстринг с «FEAT-030» (формул нет — ссылок на метки `.tex` не требуется; `test_eq_references.py` зелёный).
- [ ] README примеров, `examples/README.md`, `run.md`, CLAUDE.md — команда.
- [ ] Vault: архитектура, новая заметка решения, три заметки, реестр FEAT-030/031, индекс, комментарий #104.

## 9. После влития (для пользователя)

`gpn-solver.exe` в общем venv появится после переустановки в основном каталоге:
```powershell
cd <R>\numerical_solver
.venv\Scripts\python -m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"
```
`python -m gpn_multiphase_solver` работает и без неё.

## 10. Обнаруженные проблемы (при планировании)

- `report_energy_balance` (`examples/energy_balance.py:94-110`) нигде не вызывается — в пакет не переносится (шаг 2); отдельной записи не нужно.
- `02/main.py` и `05/main.py` повторяют выбор четырёх моментов профилей (`_times_to_plot` — копия умолчания `_profile_times`). Не правится: это демонстрационные скрипты со своими рисунками; если умолчание `_profile_times` изменится, их рисунки разойдутся со штатными. Кандидат в реестр (DEBT) после FEAT-030 — по решению пользователя.
- Переменная `GPN_EXAMPLES_EMF` в пакете — историческое имя (решение 4 — без изменений). Переименование — при FEAT-031, если инструкция заказчику потребует.

## 11. Связанные заметки

- [[FEAT-031]], [[DEBT-011]], [[DEBT-059]], [[DEBT-065]], [[FEAT-032]], [[DEBT-037]], [[DEBT-046]], [[FEAT-026]]
- [[debt-011 diagnostics-into-package]] — раздел 8 «Для следующих задач»
- [[архитектура библиотеки numerical_solver]]
- [[рисунки примеров дублируются в SVG и EMF через Inkscape]]
- [[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]]
- Пробы: `vault/issues/feat-030/probes/` — `factory_warnings.py` (+ `.out.txt`), `add_output_fields.py` (+ `.out.txt`), `snapshot_examples.py`; аудита 1 — `audit_mpl_console.py` (+ `.out.txt`, допущения о matplotlib и консоли), `audit_key_scenario.py` (+ `.out.txt`, сценарий теста команды; рабочий каталог `probes/out/` не коммитится)
