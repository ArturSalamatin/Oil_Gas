---
tags:
  - план
  - рефакторинг
date: 2026-10-22
issue: DEBT-085
github: 144
branch: refactor/debt-085/balance-figure-titles
status: в процессе
worktree: .worktrees/debt-085
audit:
  date: 2026-10-22
  found: 6
  auto-fixed: 6
  manual-required: 0
---

# DEBT-085: подписи рисунков балансов – заголовок расчёта вместо имени каталога конфигурации

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-085 в `vault/roadmap/известные баги и технический долг.md` (с уточнением при `/issue`) и issue [#144](https://github.com/ArturSalamatin/Oil_Gas/issues/144).
3. Ветку `refactor/debt-085/balance-figure-titles` и worktree `.worktrees/debt-085` создаёт `/implement` (§1.5) – вручную не создавать. База – `numerical_scheme/implementation`.
4. Venv: `numerical_solver\.venv\Scripts\python` (в worktree – тот же venv основного каталога; pytest берёт пакет своего дерева, скрипты вне pytest – с `PYTHONPATH` на worktree, правило 3 `/implement`).
5. Baseline из `numerical_solver/` worktree: `.venv\Scripts\python -m pytest tests/ --collect-only -q` (на `5f3617a` – **2650 тестов**) и `.venv\Scripts\python -m pytest tests/ -m "not slow" -q` (**~3 мин**: замер аудита 1 на копии дерева с правками плана – 188 с, 2354 passed, 4 skipped; «~70 с» в CLAUDE.md – замер DEBT-032 при 1100 тестах). Тайм-аут команды – не меньше 300000 мс: при стандартных 120000 мс прогон обрывается.
6. **Проверка выпуска до начала:** `git tag --list "v1.0.7"`. Если метка есть – остановиться и спросить пользователя (см. «Подводные камни», совместимость).
7. Запомни число тестов (всего и в быстром уровне) и время быстрого уровня – это baseline.
8. Начни с шага 1. После каждого шага – тесты шага и регресс по полю «Регресс»; полный прогон – в конце (`/implement` §3.1).

## Задача

Штатный набор `run_case` (`numerical_solver/gpn_multiphase_solver/report/pipeline.py`) строит десять рисунков. Восемь подписаны заголовком расчёта `title`: его задают аргумент `run_case(title=...)` или ключ `--title`, иначе `output.title` конфигурации, иначе имя каталога файла конфигурации (`pipeline.py:213-214`). Рисунки балансов `energy_balance.png` и `mass_balance.png` подписаны иначе – именем каталога файла конфигурации, `Path(config.config_dir).name`. Отсюда три расхождения, проверенные при `/issue`:

1. **Расчёт по книге Excel** (примеры 22, 23, любая книга): перевод лежит в `output/input/config.json`, подпись балансов – «input», остальные рисунки подписаны именем книги (`output.title` перевода, `io/workbook_convert.py:482`).
2. **Конфигурация с `output.title`** – 23 из 25 примеров: балансы подписаны именем папки (`02_single_phase_jt`), остальные рисунки – заголовком (`02: однофазная фильтрация с JT`). Ключ `--title` на балансы не действует.
3. **`run_case('config.json')` из Python с относительным путём:** `config_dir = Path('.')`, имя пустое, подпись обрывается на тире. Команду `gpn-solver run` это не касается: `cli.py:223` приводит путь к абсолютному.

Подтверждение случая 2 – проба `vault/issues/debt-085/probes/plan_capture_titles.py` (запуск из корня репозитория):

```
output.title: 02: однофазная фильтрация с JT
energy_balance.png: 'Баланс энергии — 02_single_phase_jt'
mass_balance.png:   'Баланс массы компонентов — 02_single_phase_jt'
```

Та же проба подтверждает приём тестов этого плана: функция закрывает рисунок сама (`plt.close`), но объект `Figure`, перехваченный подменой `save_figure`, после закрытия сохраняет оси и подписи.

## Решения пользователя (2026-10-22)

1. **Обязательный аргумент `title`** у `plot_energy_balance` и `plot_mass_balance` – как у `plot_relperm(config, history, output_dir, title, ...)` и `plot_pvt`. Правило заголовка остаётся одно – в `run_case`. Аргумент `config` в обеих функциях становится неиспользуемым и остаётся ради порядка аргументов (у `plot_energy_balance` так уже с `grid`).
2. **Подпись в две строки:** `f"{title}\nБаланс энергии"`, `f"{title}\nБаланс массы компонентов"` – как у остальных восьми рисунков (`f"{title}\nПрофили давления"`, `f"{title}\nОФП – …"`).
3. **Заодно – среднее тире во второй строке подписей ОФП и PVT:** `report/relperm.py:105` («ОФП — …») и `report/pvt.py:197` («PVT — …»). Остальные длинные тире пакета (комментарии, докстринги, печать, `pvt._describe`) не трогаются.

Отклонённые варианты (issue #144): необязательный `title=None` с запасным `output.title` – правило заголовка по умолчанию повторялось бы в двух модулях и в `run_case`; сигнатуры без изменений с подписью из `config.output.title` – `--title` и `run_case(title=...)` на балансы по-прежнему не действовали бы.

## Текущее состояние (baseline)

- База `5f3617a` (`numerical_scheme/implementation`, после FEAT-040), 2650 тестов, быстрый уровень зелёный по правилу мёржа.
- Вызовы функций балансов (grep `plot_energy_balance\(|plot_mass_balance\(` по `numerical_solver/` и `vault/knowledge/`): только `report/pipeline.py:378, 386` и `examples/23_source_tree_run/main.py:135, 137`. Тесты функции напрямую не вызывают. README пакета (§4, строка 997) и README примера 23 (таблица шагов, строка 51) называют функции без сигнатур – правка не нужна.
- Подписи рисунков балансов тесты не сверяют: проверяется только наличие файлов (`tests/test_cli.py:55`, `tests/test_examples.py:654-656, 1064-1069, 3387`, `tests/test_workbook_run.py:110`). Подписи ОФП и PVT тоже не сверяются: `test_public_api.py:148-151` проверяет ядро `plot_relperm_curves` с `title="T"`, `test_examples.py:1534` – только порядок аргументов `plot_pvt`.
- Публичный интерфейс: обе функции – в `numerical_solver/doc/source/api.rst:163, 165` (с FEAT-040, раздел «Не выпущено» `numerical_solver/CHANGELOG.md`). В выпуске 1.0.6 их в публичном интерфейсе нет.
- Выходы примеров (`examples/*/output/`) в git не входят – пересъёма файлов нет. Числа расчётов правка не затрагивает.

## Целевое состояние

- `plot_energy_balance(history, grid, config, output_dir, title)` и `plot_mass_balance(config, history, output_dir, title)`; подписи – `"<title>\nБаланс энергии"` (заголовок верхней оси) и `"<title>\nБаланс массы компонентов"` (общий заголовок фигуры).
- `run_case` и пример 23 передают свой заголовок. Все десять рисунков штатного набора подписаны одним заголовком расчёта, `--title` и `run_case(title=...)` действуют на все.
- Подписи ОФП и PVT: `"<title>\nОФП – <модель>"`, `"<title>\nPVT – <модель>"`.
- Докстринги обеих функций описывают `title` и неиспользуемый `config` (правило D2 `tests/test_docs.py`: имена записей «Параметры» = сигнатура).
- Два новых теста: 2650 → **2652**.

## Подводные камни (чеклист 2.5)

- ✅ **Все места вызова найдены:** `pipeline.py:378, 386`, `examples/23_source_tree_run/main.py:135, 137`; в тестах, README и vault вызовов нет.
- ✅ **Зависимости пакетов:** не изменяются.
- ⚠️ **Обратная совместимость.** Вызов без `title` перестаёт работать. В выпущенном интерфейсе (1.0.6) функций нет, поэтому несовместимости для выпусков нет, если задача влита до выпуска 1.0.7. Если к началу реализации метка `v1.0.7` уже есть – остановиться и спросить пользователя: обязательный аргумент тогда несовместим (MAJOR по правилу номеров журнала).
- ✅ **Состояние при ошибке:** `plot_mass_balance` при `bal is None` возвращает `None` до построения рисунка – `title` не нужен, поведение прежнее.
- ⚠️ **Докстринги публичного интерфейса:** D2 – запись `title` после `output_dir` в обеих функциях; D6 – номер задачи только в комментариях, не в докстрингах. Проверка – `tests/test_docs.py` в шаге 1.
- ✅ **Циклы импорта:** тесты импортируют модули `gpn_multiphase_solver.report.*` – как `pipeline` в `test_workbook_run.py`.
- ✅ **Ссылки на уравнения:** докстринг `plot_mass_balance` хранит «Ур. (eq:residual_oil)» без изменений.
- ✅ **Конфигурации:** ключи не изменяются.
- ⚠️ **matplotlib 3.7.** `Figure.get_suptitle()` появился в 3.8, пакет допускает `matplotlib>=3.7` (`numerical_solver/pyproject.toml`), в venv – 3.11.1. Тесты читают поле `fig._suptitle` (во всех версиях; `None`, если общего заголовка нет) – с комментарием.
- ⚠️ **Пример 23 вне быстрого уровня.** Пропущенную правку `main.py` ловит только `TestSourceTreeRun::test_runs_without_installed_packages` (метка `slow`, запускает `main.py`). В шаге 1 он запускается явно.
- ✅ **Производительность:** интеграционный тест использует уже существующий прогон фикстуры `case` (`test_workbook_run.py`), модульный – синтетическую историю без расчёта.
- ✅ **Прототип:** не изменяется.
- ⚠️ **Связь с задачами.** FEAT-040 (влит): пункт «Добавлено» журнала говорит «Их поведение не изменилось» – это описание самой FEAT-040, его не править, сигнатуру описывает пункт DEBT-085. DEBT-086 (#143, план готов 2026-10-22, база `5f3617a`) изменяет форму пунктов журнала и вводит её проверку: пункт DEBT-085 пишется по `/implement` 4.1, действующему на момент реализации (обе формы – в разделе «Журнал изменений»), и проверяется `pytest tests/test_packaging.py -k changelog -q`. Код пакета DEBT-086 не трогает. DEBT-084 отложен, не пересекается. Параллельных worktree на момент плана нет.

## Шаги

### Шаг 1: аргумент `title` у функций балансов, передача из `run_case` и примера 23, тесты подписей

**Цель:** рисунки балансов подписаны заголовком расчёта, который передаёт вызывающий.

**Файлы:**
- `numerical_solver/tests/test_public_api.py`
- `numerical_solver/tests/test_workbook_run.py`
- `numerical_solver/gpn_multiphase_solver/report/energy_balance.py`
- `numerical_solver/gpn_multiphase_solver/report/mass_balance.py`
- `numerical_solver/gpn_multiphase_solver/report/pipeline.py`
- `numerical_solver/examples/23_source_tree_run/main.py`

**Контекст:** функции балансов строят подпись сами, из `config.config_dir`, а остальные функции штатного набора получают заголовок от `run_case`. У книги `config_dir` – `output/input/`, отсюда «input» (раздел «Задача»). Решение пользователя – обязательный `title`, подпись в две строки. Сначала пишутся тесты, и они должны упасть на текущем коде: модульный – с `TypeError` (лишний позиционный аргумент), интеграционный – на сравнении строк, где видно «input».

**Что сделать:**

1. **Модульный тест** в `numerical_solver/tests/test_public_api.py`, раздел «Рисунки проверок» (после `test_plot_energy_balance_series_draws_all_terms`, строки 133–141).
   - Импорты в шапку (рядом с прочими `from gpn_multiphase_solver...`, с `# noqa: E402`, как у соседних):
     ```python
     from gpn_multiphase_solver.io.figures import save_figure  # noqa: E402
     from gpn_multiphase_solver.report import energy_balance, mass_balance  # noqa: E402
     ```
   - Помощник рядом с `_energy_history` (раздел «Ряды балансов», после строки 92) – история баланса массы с теми же числами, что в `test_compute_mass_balance_closes`:
     ```python
     def _mass_history():
         """История из двух записей запаса компонентов: нефть 100 → 90 м³ст, добыто 12, притекло 2."""
         snaps = [dict(M_o=100.0, M_g=0.0, cum_o_well=0.0, cum_o_ext=0.0,
                       cum_g_well=0.0, cum_g_ext=0.0),
                  dict(M_o=90.0, M_g=0.0, cum_o_well=-12.0, cum_o_ext=-2.0,
                       cum_g_well=0.0, cum_g_ext=0.0)]
         return SimulationHistory(times=[0.0, 1.0], mass_balance=snaps)
     ```
   - Тест:
     ```python
     def test_balance_figures_titled_by_argument(tmp_path, monkeypatch):
         """Рисунки балансов подписаны заголовком из аргумента title: первая строка – он, вторая – название рисунка.

         Прежде подпись бралась из имени каталога файла конфигурации: у
         расчёта по книге это перевод output/input/ – «input» (DEBT-085).
         Конфигурация – configs/baseline.json: имени её каталога в подписи
         быть не должно. Рисунок функция закрывает сама, поэтому он
         перехватывается подменой save_figure; закрытый Figure сохраняет оси.
         """
         figures = {}

         def keep(fig, path, dpi):
             """Запомнить рисунок по имени файла, затем записать как обычно."""
             figures[Path(path).name] = fig
             return save_figure(fig, path, dpi)

         monkeypatch.setattr(energy_balance, "save_figure", keep)
         monkeypatch.setattr(mass_balance, "save_figure", keep)
         cfg = load_config(BASELINE)
         energy_balance.plot_energy_balance(_energy_history(), None, cfg, tmp_path, "Расчёт")
         mass_balance.plot_mass_balance(cfg, _mass_history(), tmp_path, "Расчёт")

         # Баланс энергии – заголовок верхней оси (plot_energy_balance_series)
         assert figures["energy_balance.png"].axes[0].get_title() == "Расчёт\nБаланс энергии"
         # Баланс массы – общий заголовок фигуры. Figure.get_suptitle – с
         # matplotlib 3.8, пакет допускает 3.7: читается поле _suptitle
         assert (figures["mass_balance.png"]._suptitle.get_text()
                 == "Расчёт\nБаланс массы компонентов")
     ```
   - Ожидание до правки: `TypeError: plot_energy_balance() takes 4 positional arguments but 5 were given`.

2. **Интеграционный тест** в `numerical_solver/tests/test_workbook_run.py` – подписи рисунков расчёта по книге. Отдельного расчёта нет: перехват ставится в существующую фикстуру `case` (строки 89–98, один прогон на модуль, ~4 с).
   - Импорты (рядом с `import gpn_multiphase_solver.report.pipeline as pipeline`, строка 34):
     ```python
     import gpn_multiphase_solver.report.energy_balance as energy_balance
     import gpn_multiphase_solver.report.mass_balance as mass_balance
     import gpn_multiphase_solver.report.pvt as report_pvt
     import gpn_multiphase_solver.report.relperm as report_relperm
     from gpn_multiphase_solver.io.figures import save_figure
     ```
     Псевдонимы `report_pvt`, `report_relperm` – чтобы имена модулей не путались с понятиями PVT и ОФП в тексте тестов.
   - Фикстура `case`:
     До:
     ```python
     @pytest.fixture(scope="module")
     def case(tmp_path_factory):
         """run_case по малой книге с кириллицей и пробелом в имени; рядом — вывод прошлого расчёта: (книга, результат, печать)."""
         folder = tmp_path_factory.mktemp("book")
         book = _small_book(folder / "малая книга.xlsx")
         _old_output(folder)
         buf = io.StringIO()
         with contextlib.redirect_stdout(buf):
             r = run_case(book)
         return book, r, buf.getvalue()
     ```
     После:
     ```python
     @pytest.fixture(scope="module")
     def case(tmp_path_factory):
         """run_case по малой книге с кириллицей и пробелом в имени; рядом – вывод прошлого расчёта: (книга, результат, печать, рисунки по именам файлов)."""
         folder = tmp_path_factory.mktemp("book")
         book = _small_book(folder / "малая книга.xlsx")
         _old_output(folder)
         figures = {}

         def keep(fig, path, dpi):
             """Запомнить рисунок по имени файла, затем записать как обычно."""
             figures[Path(path).name] = fig
             return save_figure(fig, path, dpi)

         # Рисунки закрываются сразу после записи: перехват save_figure во всех
         # модулях штатного набора оставляет их объекты для проверки подписей
         # (DEBT-085). Фикстура модульная – monkeypatch функций здесь недоступен
         buf = io.StringIO()
         with pytest.MonkeyPatch.context() as mp, contextlib.redirect_stdout(buf):
             for module in (pipeline, report_relperm, report_pvt, energy_balance, mass_balance):
                 mp.setattr(module, "save_figure", keep)
             r = run_case(book)
         return book, r, buf.getvalue(), figures
     ```
   - Распаковка в трёх тестах фикстуры – четвёртый элемент:
     - `test_input_saved_and_output_cleared` (строка 103): `book, r, _ = case` → `book, r, _, _ = case`;
     - `test_title_and_print` (строка 116): `book, r, text = case` → `book, r, text, _ = case`;
     - `test_saved_input_reproduces_run` (строка 129): `book, r, _ = case` → `book, r, _, _ = case`.
   - Новый тест после `test_title_and_print`:
     ```python
     def test_figure_titles_from_book(case):
         """Все рисунки штатного набора подписаны именем книги первой строкой, рисунки балансов – тоже.

         Ловит: подпись рисунков балансов из имени каталога файла
         конфигурации – у книги это перевод output/input/, и выходило «input»
         вместо имени книги (DEBT-085). Подпись рисунка – общий заголовок
         фигуры, если он есть (PVT, баланс массы), иначе заголовок верхней оси.
         """
         book, _, _, figures = case
         # Перехвачены все записанные рисунки: рисунок модуля без подмены
         # save_figure выпал бы из проверки молча
         assert set(figures) == {p.name for p in (book.parent / "output").glob("*.png")}

         def heading(fig):
             # Figure.get_suptitle – с matplotlib 3.8, пакет допускает 3.7
             return (fig._suptitle.get_text() if fig._suptitle is not None
                     else fig.axes[0].get_title())

         titles = {name: heading(fig) for name, fig in figures.items()}
         assert titles["energy_balance.png"] == "малая книга\nБаланс энергии"
         assert titles["mass_balance.png"] == "малая книга\nБаланс массы компонентов"
         for name, text in titles.items():
             assert text.startswith("малая книга\n"), (name, text)
     ```
   - Ожидание до правки: падение на первом `assert` – `'Баланс энергии — input' == 'малая книга\nБаланс энергии'`. Остальные тесты модуля зелёные.

3. **Прогон тестов до правки кода** (из `numerical_solver/` worktree):
   ```powershell
   .venv\Scripts\python -m pytest tests/test_public_api.py tests/test_workbook_run.py -q
   ```
   Ожидание: 2 failed (`test_balance_figures_titled_by_argument` – `TypeError`, `test_figure_titles_from_book` – «input»), остальные passed. Иной исход – разобрать до правки.

4. **`numerical_solver/gpn_multiphase_solver/report/energy_balance.py`.**
   До (строка 50):
   ```python
   def plot_energy_balance(history, grid, config, output_dir: Path):
   ```
   После:
   ```python
   def plot_energy_balance(history, grid, config, output_dir: Path, title: str):
   ```
   Докстринг, раздел «Параметры». До (строки 66–70):
   ```
       config : SimulationConfig
           Конфигурация расчёта: имя каталога файла конфигурации – в
           заголовке рисунка.
       output_dir : str or pathlib.Path
           Каталог результатов; создаётся, если его нет.
   ```
   После:
   ```
       config : SimulationConfig
           Конфигурация расчёта; не используется, оставлена ради порядка
           аргументов.
       output_dir : str or pathlib.Path
           Каталог результатов; создаётся, если его нет.
       title : str
           Заголовок рисунка: первая строка, вторая – «Баланс энергии».
   ```
   Код. До (строки 77–80):
   ```python
       bal = compute_energy_balance(history)
       # Имя расчёта берём из пути к конфигу (папка конфига): модуль общий для всех расчётов.
       axes = plot_energy_balance_series(
           bal, title=f"Баланс энергии — {Path(config.config_dir).name}")
   ```
   После:
   ```python
       bal = compute_energy_balance(history)
       # Заголовок расчёта – от вызывающего (run_case), как у plot_relperm и
       # plot_pvt: имя каталога конфигурации у книги – «input» (DEBT-085)
       axes = plot_energy_balance_series(bal, title=f"{title}\nБаланс энергии")
   ```
   `from pathlib import Path` остаётся: он нужен для `output_dir = Path(output_dir)`.

5. **`numerical_solver/gpn_multiphase_solver/report/mass_balance.py`.**
   До (строка 43):
   ```python
   def plot_mass_balance(config, history, output_dir: Path) -> dict | None:
   ```
   После:
   ```python
   def plot_mass_balance(config, history, output_dir: Path, title: str) -> dict | None:
   ```
   Докстринг. До (строки 55–61):
   ```
       config : SimulationConfig
           Конфигурация расчёта: имя каталога файла конфигурации – в
           заголовке рисунка.
       history : SimulationHistory
           История расчёта: запас компонентов на записях и накопленные потоки.
       output_dir : str or pathlib.Path
           Каталог результатов; создаётся, если его нет.
   ```
   После:
   ```
       config : SimulationConfig
           Конфигурация расчёта; не используется, оставлена первым
           аргументом, как у ``plot_relperm`` и ``plot_pvt``.
       history : SimulationHistory
           История расчёта: запас компонентов на записях и накопленные потоки.
       output_dir : str or pathlib.Path
           Каталог результатов; создаётся, если его нет.
       title : str
           Заголовок рисунка: первая строка, вторая – «Баланс массы
           компонентов».
   ```
   Ссылки на функции – в двойных обратных кавычках, а не `:func:`: в контексте модуля `mass_balance` имя `plot_relperm` не разрешается, и при сборке Sphinx с `-W` это могло бы дать предупреждение.
   Код. До (строки 78–79):
   ```python
       # Имя расчёта — из пути к конфигу (папка конфига): модуль общий для всех расчётов.
       fig.suptitle(f"Баланс массы компонентов — {Path(config.config_dir).name}")
   ```
   После:
   ```python
       # Заголовок расчёта – от вызывающего (run_case), как у plot_relperm и
       # plot_pvt: имя каталога конфигурации у книги – «input» (DEBT-085)
       fig.suptitle(f"{title}\nБаланс массы компонентов")
   ```
   Комментарий о порядке аргументов (строки 69–71) остаётся. `Path` по-прежнему нужен (`output_dir = Path(output_dir)`).

6. **`numerical_solver/gpn_multiphase_solver/report/pipeline.py`.**
   До (строки 377–378 и 385–386):
   ```python
       print()
       plot_energy_balance(history, grid, config, output_dir)
   ...
       print()
       plot_mass_balance(config, history, output_dir)
   ```
   После:
   ```python
       print()
       plot_energy_balance(history, grid, config, output_dir, title)
   ...
       print()
       plot_mass_balance(config, history, output_dir, title)
   ```
   В конец комментария блока «── Баланс энергии ──» (строки 371–376), после строки `    # на подшагах внутри решателя, а не восстанавливаются по записям.` и перед `print()`, – строка `    # Заголовок – тот же, что у остальных рисунков (DEBT-085).`

7. **`numerical_solver/examples/23_source_tree_run/main.py`.**
   До (строки 133–137):
   ```python
       # ── Балансы энергии и массы: рисунок и печать итогов ──
       print()
       plot_energy_balance(history, grid, config, OUT)
       print()
       plot_mass_balance(config, history, OUT)
   ```
   После:
   ```python
       # ── Балансы энергии и массы: рисунок и печать итогов ──
       print()
       plot_energy_balance(history, grid, config, OUT, title)
       print()
       plot_mass_balance(config, history, OUT, title)
   ```
   `title` определён в строке 78 (`config.output.title`, у книги – её имя). README примера (таблица шагов, строка 51) называет функции без аргументов – не изменяется.

**Проверка после этого шага:**
- Тесты шага: `.venv\Scripts\python -m pytest tests/test_public_api.py tests/test_workbook_run.py tests/test_docs.py -q` – всё passed (оба новых теста зелёные; `test_docs.py` – правило D2 и сборка Sphinx без предупреждений: `test_docs_build_without_warnings` помечен `slow`, но при запуске файла целиком выполняется). Эмуляция аудита 1 на копии: 165 passed, 1 skipped (сверка номеров уравнений без `problem_statement.aux` – в копии его нет, к задаче не относится), ~55 с.
- Пример 23: `.venv\Scripts\python -m pytest tests/test_examples.py -k test_runs_without_installed_packages -q` – passed (тест `slow`, запускает `main.py` копии дерева; ловит пропущенную правку вызова).
- Регресс: быстрый.

**Подводные камни:** совместимость (метка `v1.0.7`), D2/D6 докстрингов, `_suptitle` для matplotlib 3.7, пример 23 вне быстрого уровня – см. чеклист.

**Зависимости:** требует – ничего; блокирует – шаг 2 (его проверка дополняет тест `test_figure_titles_from_book`).

**Оценка:** ~70 строк (тесты ~55, код ~15), ~30 минут.

### Шаг 2: среднее тире во второй строке подписей ОФП и PVT

**Цель:** разделитель «модель рисунка – описание модели» в подписях `relperm.png` и `pvt.png` – среднее тире.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/report/relperm.py`
- `numerical_solver/gpn_multiphase_solver/report/pvt.py`
- `numerical_solver/tests/test_workbook_run.py`

**Контекст:** решение пользователя 3. Правило «Тире» проекта допускает только среднее тире в любом тексте, подписи рисунков видит заказчик. Шаг ограничен двумя разделителями: длинные тире внутри `pvt._describe` (строки 115, 121) сверяет `tests/test_examples.py:1443` и цитирует README примера 20 (строка 207) – это вне задачи («Обнаруженные проблемы»).

**Что сделать:**

1. Дополнить `test_figure_titles_from_book` (шаг 1) проверкой разделителей – в конец теста, после цикла `for`, до правки кода, чтобы тест упал:
   ```python
       # Разделитель второй строки ОФП и PVT – среднее тире (правило «Тире»)
       assert titles["relperm.png"].startswith("малая книга\nОФП – "), titles["relperm.png"]
       assert titles["pvt.png"].startswith("малая книга\nPVT – "), titles["pvt.png"]
   ```
   `–` – среднее тире кодом, чтобы в исходнике было видно, какой знак ожидается. Прогон `pytest tests/test_workbook_run.py -k figure_titles -q` – failed на `relperm.png`.
2. `numerical_solver/gpn_multiphase_solver/report/relperm.py`, строка 105.
   До:
   ```python
                                  title=f"{title}\nОФП — {_describe(config)}")
   ```
   После:
   ```python
                                  title=f"{title}\nОФП – {_describe(config)}")
   ```
3. `numerical_solver/gpn_multiphase_solver/report/pvt.py`, строка 197.
   До:
   ```python
       fig.suptitle(f"{title}\nPVT — {_describe(config)}", fontsize=10)
   ```
   После:
   ```python
       fig.suptitle(f"{title}\nPVT – {_describe(config)}", fontsize=10)
   ```

**Проверка после этого шага:**
- `.venv\Scripts\python -m pytest tests/test_workbook_run.py -q` – passed.
- Регресс: быстрый.

**Подводные камни:** подпись PVT шире разделителя: `_describe` у корреляции Стендинга сам содержит длинное тире – тест шага его не проверяет (у книги табличный PVT), правка `_describe` вне задачи.

**Зависимости:** требует – шаг 1.

**Оценка:** ~5 строк, ~10 минут.

## Журнал изменений (выполняет `/implement` 4.1)

Раздел «## Не выпущено» `numerical_solver/CHANGELOG.md`, подраздел «### Изменено» (DEBT) – создать после «### Добавлено», если его нет. Форма пункта – по `/implement` 4.1, действующему на момент реализации. План DEBT-086 (`vault/plans/debt-086 release-notes-format.md`, готов 2026-10-22, #143) изменяет эту форму и добавляет её проверку в `tests/test_packaging.py -k changelog`. Поэтому перед записью пункта – `git log --oneline -5 numerical_scheme/implementation` и чтение `/implement` 4.1 из worktree.

Если DEBT-086 ещё не влит (форма «один абзац: задача, план, результат»):

```markdown
- **DEBT-085.** Рисунки балансов энергии и массы компонентов были подписаны
  именем каталога файла конфигурации, а не заголовком расчёта, которым
  подписаны остальные рисунки: при расчёте по книге Excel – «input», у
  конфигурации с `output.title` – именем её папки, а ключ `--title` на них не
  действовал. Функции `plot_energy_balance` и `plot_mass_balance` получили
  обязательный аргумент `title`, как `plot_relperm` и `plot_pvt`, и
  `run_case` передаёт им свой заголовок. Подписи рисунков балансов – в две
  строки: заголовок расчёта и название рисунка. Во второй строке подписей ОФП
  и PVT стоит среднее тире. Числа расчётов не изменились.
```

Если DEBT-086 влит (форма «суть, *Было.*, *Стало.*»; блока *Числа.* нет – числа не изменяются; строки абзаца – одной строкой или по правилу склейки DEBT-086):

```markdown
- **DEBT-085.** Рисунки балансов подписаны заголовком расчёта, как остальные рисунки.

  *Было.* Рисунки балансов энергии и массы компонентов были подписаны именем каталога файла конфигурации: при расчёте по книге Excel – «input», у конфигурации с `output.title` – именем её папки, а ключ `--title` на них не действовал.

  *Стало.* Функции `plot_energy_balance` и `plot_mass_balance` получили обязательный аргумент `title`, как `plot_relperm` и `plot_pvt`, и `run_case` передаёт им свой заголовок. Подписи рисунков балансов – в две строки: заголовок расчёта и название рисунка. Во второй строке подписей ОФП и PVT стоит среднее тире.
```

Пункт FEAT-040 в «Добавлено» не править: он описывает свою задачу (форму его изменяет DEBT-086). DEBT-086 тоже добавляет пункт в «### Изменено»: при влитии второй из задач возможен конфликт в «Не выпущено» – `/merge` сохраняет оба пункта.

## Тестовая стратегия

**Тест:** `test_balance_figures_titled_by_argument`
**Файл:** `numerical_solver/tests/test_public_api.py` (существующий)
**Сценарий:** функции балансов вызываются напрямую с `title="Расчёт"` и конфигурацией `configs/baseline.json`.
**Setup:** синтетические истории `_energy_history()` и `_mass_history()` (две записи), перехват `save_figure` через `monkeypatch`.
**Ожидание:** заголовок верхней оси баланса энергии – `"Расчёт\nБаланс энергии"`, общий заголовок баланса массы – `"Расчёт\nБаланс массы компонентов"`.
**Baseline:** до правки – `TypeError` (лишний аргумент).
**Предотвращает:** возврат подписи из `config` и потерю аргумента `title` в публичных функциях.

**Тест:** `test_figure_titles_from_book`
**Файл:** `numerical_solver/tests/test_workbook_run.py` (существующий, фикстура `case`)
**Сценарий:** `run_case` по малой книге «малая книга.xlsx» – случай из записи реестра.
**Setup:** перехват `save_figure` в пяти модулях штатного набора внутри фикстуры (`pytest.MonkeyPatch.context`).
**Ожидание:** перехвачены все записанные PNG (множества имён совпадают – 10 рисунков); подписи балансов – `"малая книга\nБаланс энергии"`, `"малая книга\nБаланс массы компонентов"`; все десять подписей начинаются с `"малая книга\n"`; после шага 2 вторые строки ОФП и PVT начинаются с «ОФП – », «PVT – ». Подписи всех рисунков после обоих шагов – проба `vault/issues/debt-085/probes/audit_titles.py` (запуск из каталога `numerical_solver/` worktree).
**Baseline:** до правки – «Баланс энергии — input».
**Предотвращает:** рисунок штатного набора, подписанный не заголовком расчёта; передачу заголовка из `run_case` мимо какой-либо функции.

**Случай 3 (относительный путь в `run_case`)** отдельным тестом не проверяется: после правки функции балансов не читают `config_dir`, а заголовок по умолчанию `run_case` строит от `config_path.resolve()` (`pipeline.py:214`). Возврат к `config_dir` ловит критерий завершения – grep `config_dir` по модулям балансов пуст.

**Регрессия поведения:** числа расчётов и печать в консоль не изменяются. Их охраняют существующие тесты: `test_workbook_run.py::test_saved_input_reproduces_run` (побитовое совпадение расчёта), `test_examples.py` на фикстуре `results` (балансы, границы, README – полный уровень), `TestSourceTreeRun::test_runs_without_installed_packages` (вывод примера 23 против README).

## Критерии завершения

- [ ] Шаги 1–2 выполнены, оба новых теста зелёные, до правки кода они падали (зафиксировано в отчёте).
- [ ] Быстрый уровень зелёный после каждого шага; полный прогон в конце `/implement` – зелёный, 2652 теста.
- [ ] `tests/test_docs.py` зелёный (D2, D6, сборка Sphinx `-W`).
- [ ] `test_runs_without_installed_packages` зелёный (пример 23 вызывает функции с `title`).
- [ ] grep `config_dir` по `numerical_solver/gpn_multiphase_solver/report/energy_balance.py` и `mass_balance.py` – пусто.
- [ ] Пункт журнала в «Не выпущено → Изменено», `pytest tests/test_packaging.py -k changelog -q` зелёный.
- [ ] Визуальная проверка: пример 22 (`.venv\Scripts\python -m gpn_multiphase_solver run examples\22_workbook_input\22_workbook_input.xlsx`) – `energy_balance.png` и `mass_balance.png` подписаны «22_workbook_input» первой строкой; `relperm.png`, `pvt.png` – среднее тире во второй строке.
- [ ] Vault: статус DEBT-085 в реестре, `05-comment-done.md` в issue #144.

## Обнаруженные проблемы

1. **Случай 3 в первой редакции issue был неверен** («`gpn-solver run config.json` даёт пустое имя»): `cli.py:223` приводит путь к абсолютному. Исправлено при планировании – тело issue #144 и уточнение в реестре.
2. **Длинное тире в подписи модели PVT** – `report/pvt.py:115` («$\mu_o$ выше $p_b$ — Бил») и `:121` («от $p$ — только через $R_s$»), видно на `pvt.png` у корреляции Стендинга. Текст сверяет `tests/test_examples.py:1443` и цитирует README примера 20 (строка 207). Вне задачи по решению пользователя 3; не блокирует. Регистрировать ли отдельной задачей – решает пользователь (в пакете ~200 длинных тире только в `report/`, большей частью в комментариях и печати).

## Связь с задачами

- FEAT-040 (#142, влит `3a23970`) – ввёл обе функции в публичный интерфейс; находка DEBT-085 – при его планировании.
- FEAT-036 (#136) – расчёт по книге, перевод в `output/input/`.
- DEBT-086 (#143, план готов 2026-10-22) – форма пунктов журнала; пересечение только в «Не выпущено».

## Оценка

2 шага, 9 файлов (пакет 5, пример 23 – 1, тесты 2, журнал 1), ~75 строк, ~50 минут с прогонами (быстрый уровень дважды по ~3 мин, тест примера 23 ~25 с, тесты шага 1 ~55 с, полный прогон в конце ~10 мин).

## Эмуляция аудита 1 (2026-10-22)

План применён к копии дерева `git archive HEAD numerical_solver` (база `5f3617a`) скриптом `vault/issues/debt-085/probes/audit_apply.py` по фазам: все блоки «До» встретились ровно столько раз, сколько ожидалось (распаковка `case = …` – дважды). Результаты на копии:

| Фаза | Прогон | Итог |
|---|---|---|
| тесты шага 1 до правки кода | `test_public_api.py`, `test_workbook_run.py` | 2 failed (`TypeError`; «Баланс энергии — input»), 30 passed |
| код шага 1 | те же + `test_docs.py` | 165 passed, 1 skipped (нет `.aux` в копии) |
| код шага 1 | `test_runs_without_installed_packages` | 1 passed, 23 с |
| тест шага 2 до правки | `test_workbook_run.py -k figure_titles` | failed на `relperm.png` |
| код шага 2 | `test_workbook_run.py` | 19 passed (с проверкой множества PNG) |
| итог | `--collect-only` / `-m "not slow"` | 2652 / 2354 passed, 4 skipped, 188 с |

`audit_apply.py` хранит правки плана дословно и пригоден как образец «До/После» при реализации. Копия дерева удалена после аудита.
