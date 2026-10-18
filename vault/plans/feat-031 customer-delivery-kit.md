---
tags:
  - план
  - инфраструктура
  - поставка
date: 2026-10-18
issue: FEAT-031
github: 114
branch: feat/feat-031/customer-delivery-kit
model_level: null
status: в процессе
worktree: .worktrees/feat-031
audit:
  date: 2026-10-18
  found: 13
  auto-fixed: 13
  manual-required: 1
---

# FEAT-031: передача команде разработки заказчика — срез финального выпуска, документация, приёмка

**GitHub issue:** [#114](https://github.com/ArturSalamatin/Oil_Gas/issues/114). Тело issue описывает прежний объём (дистрибутивы, инструкции инженерам, `constraints.txt`); нынешний объём — этот план и комментарий `vault/issues/feat-031/03-comment-plan.md`.

**База плана:** `numerical_scheme/implementation` на `024e19a` (`release: начало 1.0.1.dev0`, после выпуска 1.0.0 — FEAT-038); сверена аудитом 1 на `887c5ca` (сверху `ee36397` — README §1 «Из выпуска» переписан, +59 строк; номера строк README ниже — на `887c5ca`). Тестов 2461 (быстрый уровень 2177, `slow` 284). Черновик заметок к плану — 2026-10-17 (§0 ниже — его решения дословно), план — 2026-10-18.

**Начинать после влития [[DEBT-082]]** (реализована, ждёт мержа — ветка `refactor/debt-082/locked-output-dir`): она правит те же файлы, что шаги 5 и 12, — `numerical_solver/README.md`, `gpn_multiphase_solver/cli.py`, `gpn_multiphase_solver/report/pipeline.py` (+132 строки в `run_case`), а также `CHANGELOG.md`, `tests/test_cli.py`. Worktree FEAT-031 — от базы с DEBT-082; номера строк `pipeline.py`, `cli.py`, README — сверить по тексту.

Цепочка: [[feat-033 workbook-input-format|FEAT-033]] → [[feat-034 xlsx-cell-reader|FEAT-034]] → [[feat-035 workbook-to-config|FEAT-035]] → [[feat-036 run-from-workbook|FEAT-036]] → [[FEAT-037]] → [[FEAT-038]] → **FEAT-031**. Всё до FEAT-031 влито.

## Как начать работу по этому плану

1. Прочитай этот файл целиком: §0 — решения пользователя (обязательны), §1 — замеры, §3 — шаги.
2. Код и постановка — источник фактов для документации: `numerical_solver/doc/problem_statement.tex` (раздел `ssec:domain` — допущения, `ssec:T_independent` — гидродинамика без температуры), `numerical_solver/README.md`, модули пакета. Заметки vault — только подсказка, что проверить: они устаревают ([[DEBT-080]]).
3. Пробы планирования — `vault/issues/feat-031/probes/`: `sphinx_probe.py` (+ `.out.txt`), `sphinx_module_sections.py` (+ `.out.txt`), `slice_full_fresh_venv.out.txt`, `docstring_census.py`. Пробы аудита 1: `audit_plan_docs.py` (+ `.out.txt`) — сборка ровно по `conf.py`/`api.rst` шага 3 и покрытие импортов примеров; `audit_classmethod_fixture.py`, `audit_module_fixture.py` — обе формы фикстуры шага 1 на pytest 7.4 и 9.1.
4. Worktree: `git worktree add .worktrees/feat-031 -b feat/feat-031/customer-delivery-kit numerical_scheme/implementation` (база — не `master`, CLAUDE.md «Базовые ветки»).
5. Проверь, что [[DEBT-082]] влита (`git log --oneline -8 numerical_scheme/implementation`; см. выше «Начинать после влития DEBT-082»). Номера строк README в шагах — на `887c5ca`; DEBT-082 правит README — тексты искать по содержанию.
6. Venv: `numerical_solver\.venv\Scripts\python` (общий для основного каталога и worktree). Sphinx ставится в шаге 1 **без** переустановки `-e` (иначе общий venv начнёт указывать на worktree).
7. Baseline из `numerical_solver/` worktree: `..\..\..\numerical_solver\.venv\Scripts\python -m pytest tests/ --collect-only -q` (2461 на `887c5ca`; DEBT-082 добавляет свои тесты — записать фактическое) и `... -m "not slow" -q` (в worktree ожидается 1 пропуск — черновик руководителя не под git и в worktree отсутствует, `test_xlsx_reader.py:476`; vault под git — проверки заметок идут; в основном каталоге пропусков 0).
8. Шаги 1–14 по порядку. После каждого — тест шага и регресс по полю «Регресс»; полный прогон — в конце (`/implement` §3.1).

Прототип (`HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/`) план **не меняет**: правятся только `CHANGELOG_1.0.3.md` (шаг 12). Тесты прототипа и его регрессия не нужны.

## 0. Решения пользователя

### 0.1. Прежние, в силе

1. 2026-10-10 — заказчик получает решатель гидродинамики и температуры, код прототипа, примеры и тесты. Модель запуска «Б»: команда расчёта из установленного пакета ([[FEAT-030]]).
2. 2026-10-11 — номер `radial-blackoil` повышается при поставке, а не в каждой задаче, меняющей прототип (аудит 3 плана [[DEBT-048]]).
3. 2026-10-14 — книга Excel — часть поставки; FEAT-031 ждёт FEAT-033…036.

### 0.2. 2026-10-17 — смена получателя

4. Поставку инженерам готовит команда разработки заказчика. Мы передаём материалы **этой команде**.
5. Цепочку FEAT-033…036 ждём: пользователь будет запускать расчёт книгой.
6. Передаётся срез кода на дату, без истории git.
7. Одно руководство разработчика. Файлы vault не передаются; заметки в `numerical_solver/` не переносятся.
8. Перечни задач — ни открытых, ни завершённых — не передаются: завершённые задачи — формализация выполненных работ для удобства отслеживания, заказчику интересен готовый функционал.
9. `numerical_solver/deliverables/` и черновик руководителя `configs/INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx` не включаются.
10. Прототип разработан в рамках того же заказа; особых условий использования нет.
11. Версия поставки — 1.0.0. *(заменено решением 45)*
12. Уточнение к решению 7: документация в значительной части — техническое описание, а также сведения для конечного пользователя-инженера.
13. Состав документации: файл README с основной информацией и документация из докстрингов по стандартам Python; README включается в эту документацию.
14. Инструмент — Sphinx: `autodoc`, `napoleon` (стиль NumPy), `myst-parser` для включения `README.md`.
15. Докстринги публичного интерфейса — в стиле NumPy: разделы параметров, результата и исключений с единицами; внутренний код — одна строка и ссылка на уравнение, как прежде. Правило внесено в `CLAUDE.md` («Файлы и код») и `.claude/commands/implement.md` 2026-10-17. Следствие: новые публичные функции FEAT-033…036 (`template`, `convert`, расчёт по книге) пишутся сразу по новому правилу.
16. Документируется только публичный интерфейс: имена из `tests/test_public_api.py` и README §4, абстрактные классы для расширения (PVT, ОФП, граничные условия) — не все 319 имён (§1.4). *(уточнено решением 51)*
17. Метки `eq:` в докстрингах при сборке документации переводятся в номера уравнений по `problem_statement.aux`.
18. **Прототип и примеры в документацию не входят** — документируется только пакет `gpn_multiphase_solver` (отменяет решение «прототип входит», принятое ранее в тот же день).
19. Заголовки разделов докстрингов — на русском. Следствие: расширение `numpydoc` не годится (знает только английские заголовки) — `napoleon` с `napoleon_custom_sections`, где русский заголовок объявляется синонимом стандартного (например, «Параметры» → `Parameters`, «Возвращает» → `Returns`, «Исключения» → `Raises`; имена — при планировании). Распознавание с подчёркиванием `---` в стиле NumPy проверить пробой. *(проверено, §1.2)*
20. Формат выхода — HTML.
21. Файлы README ради документации не правятся: ссылки на файлы и каталоги остаются как есть (вопрос 17 — вариант б).
22. В README обязательно указать команду сборки HTML-документации и где лежит главный файл `index.html`. Это добавление раздела в `numerical_solver/README.md`, а не правка ссылок — решению 21 не противоречит (подтверждено пользователем).
23. Номера уравнений для меток `eq:` (решение 17) — из таблицы «метка → номер» в `doc/source/` под git: генерируется скриптом из `problem_statement.aux` при изменении постановки и при сборке среза; тест сверяет таблицу с `.aux`, когда он есть, иначе пропускается. Для сборки HTML нужен только Python, LaTeX не нужен (вопрос 23 — вариант б).

### 0.3а. Ответы на вопросы черновика (2026-10-17)

24. Вопрос 1 — `radial-blackoil` → `1.0.3+gpn.2`: защита локальной меткой сохраняется.
25. Вопрос 2 — `__version__` пакета; версии обоих пакетов записываются в `output/`.
26. Вопрос 9 — метка `v1.0.0` в git; на origin — вместе с `/merge`. *(механизм меток — [[FEAT-038]])*
27. Вопрос 3 — ID задач в комментариях кода и тестов остаются, **в документации не поясняются**; в докстринги публичного интерфейса при переписывании не переносятся; ссылки на `vault/` убираются из README примеров 13a, 14 и `CHANGELOG_1.0.3.md` прототипа.
28. Вопрос 6 — дистрибутивы wheel не передаются.
29. Вопрос 21 — собранный HTML кладётся в срез, как PDF постановки.
30. Вопрос 22 — исходники Sphinx в `doc/source/`, сборка в `doc/build/html/`, главный файл — `doc/build/html/index.html`.
31. `README.md` — под git сразу, как есть (2026-10-17). *(выполнено)*
32. Вопрос 4 — совместимость оставить как есть: `requires-python >= 3.10` и нижние границы зависимостей не меняются и не проверяются, `constraints.txt` не делается, ОС заказчика не выясняется.
33. Вопрос 5 — в README установка общим порядком, как в нынешнем §1.
34. Вопрос 7 — раздел «Ограничения» нужен: свойства функционала, не перечень задач.
35. Вопрос 18 — сборка документации без предупреждений (`-W`): в приёмке и медленным тестом (метка `slow`).
36. Вопрос 20 — формулы в докстрингах не пишутся, только ссылки на уравнения; MathJax у заказчика есть — вопрос закрыт.
37. Вопрос 8 — скрипт сборки среза (работает с git и меткой версии, нужен только нам) лежит в новой папке верхнего уровня `Oil_Gas/tools/`: срез — поддерево `numerical_solver/`, поэтому скрипт в него не попадает без `export-ignore`. Скрипт приёмки и генератор таблицы «метка → номер» нужны и заказчику — лежат в `numerical_solver/tools/` и входят в срез. При создании `Oil_Gas/tools/` — строка в таблице «Структура проекта» `CLAUDE.md`. *(папку создал FEAT-038 — `tools/release.py`)*

### 0.3б. Скрипт установки (2026-10-18)

38. В FEAT-031 входит скрипт установки `setup.bat` — отдельная задача не заводится.
39. Установка заканчивается проверкой `gpn_multiphase_solver run --help`, без прогона тестов.
40. Только Windows: `setup.sh` для Linux не нужен.

### 0.3в. Версионирование (2026-10-18)

41. Механизм версий выделен в отдельную задачу [[FEAT-037]]: единый `__version__` решателя, журнал `CHANGELOG.md`, правило номеров. В FEAT-031 остаётся выпуск 1.0.0.
42. До выпуска номер решателя — `1.0.0.dev0`; `1.0.0` — в момент выпуска.
43. `radial-blackoil` → `1.0.3+gpn.2` — при выпуске (решение 2026-10-11 в силе; уточняет решение 24).
44. Ссылки на `vault/` в README примеров 13a, 14 и `CHANGELOG_1.0.3.md` — в FEAT-031 (решение 27), не в FEAT-037.

### 0.3г. Номер поставки (2026-10-18, регистрация [[FEAT-038]])

45. Номер версии для передачи заказчику не важен; важно, чтобы заказчик получил финальную версию со всеми изменениями. Решение 7 («версия поставки — 1.0.0») заменено.
46. `1.0.0` и `radial-blackoil` → `1.0.3+gpn.2` ставит первый выпуск FEAT-038 — до FEAT-031; решения 41–43 в части момента смены номера заменены. *(выполнено: `v1.0.0`, 2026-10-18)*
47. Вывод, подтвердить при планировании: срез строится из метки выпуска, сделанного после всех изменений поставки; номер поставки — номер этого выпуска. *(подтверждено планом: §6)*

### 0.3д. Решения при планировании (2026-10-18)

48. Подраздел README §1 «Из выпуска» (установка из Releases закрытого репозитория через `gh`, FEAT-038) **остаётся в README** как есть. Следствие: в срезе остаются упоминания `tools/release.py` (README §1, комментарий `pyproject.toml`, README прототипа), которого в срезе нет, — принято.
49. Зависимости сборки документации (`sphinx`, `myst-parser`) — **в группе `[dev]`**: `setup.bat` и команда README §1 не меняются; тест сборки документации не пропускается.
50. Числа расчёта у заказчика сверяет **полный прогон тестов** (результаты примеров против чисел README с допусками). Приёмка добавляет запуск из постороннего каталога — по книге и по конфигу: код 0, набор файлов вывода, `versions.txt` = установленные версии. Эталон не хранится.
51. Публичный интерфейс для документации: README §4 + `tests/test_public_api.py` + **функции, которые вызывают скрипты примеров** (diagnostics: `solve_closed`, `front_radius`, `single_phase_asymptote`, пять функций `two_phase`; `report_relperm`) + абстрактные классы расширения (PVT, ОФП, сетка, режим скважины). Перечень — §3, шаг 3 (`api.rst`).

### 0.4. Следствия (сверены с кодом при планировании)

- Отпадают сборки для установки: переносная папка со встроенным Python, дистрибутивы numpy/scipy/matplotlib для установки без сети. Сведения для инженера-пользователя остаются — в README (решение 12).
- Формат книги и команда `gpn-solver template` описаны в README §3.6 (FEAT-036) — для разработчика и для инженера.
- `setup.bat` (решения 38–40): `numerical_solver/setup.bat`, свой каталог — через `%~dp0`; Python ≥ 3.10 — сначала `py -3`, затем `python` (заглушка Microsoft Store не проходит проверку версии); `.venv`, если её нет; `pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"`; проверка `run --help`; Python не устанавливает; нужен PyPI или зеркало; сообщения — на английском (cmd в кодировке 866); `.bat`, не `.ps1` (ExecutionPolicy); после переноса каталога — запустить заново; приёмка создаёт окружение вызовом `setup.bat`; README §1 — `setup.bat` первым способом, ручной порядок остаётся.
- Манифест `PACKAGE_MANIFEST_SHA256.txt`, `VERSION.txt`, `BUILD.txt` прототипа **не меняются**: решение DEBT-059 — запись поставки 2026-08-25; регрессия прототипа сверяет `build_info.VERSION`/`BUILD_ID` с эталоном. README прототипа это уже объясняет (строка 89). Пункт «манифест» черновика §8 снят.
- Журнал решателя `CHANGELOG.md`: FEAT-031 его не пополняет (правило FEAT-037 — раздел выпуска сводится при выпуске). Пункт «Не выпущено» для выпуска поставки заполняется перед `tools/release.py` (§6).

## 1. Замеры при планировании (база `024e19a`)

### 1.1. Срез самодостаточен

`git archive v1.0.0:numerical_solver` → `dist/probe-feat031/slice/` (483 файла; `dist/` в `.gitignore`), тесты — интерпретатором общего venv, из каталога среза:

| Проверка | Итог |
|---|---|
| `--collect-only` | 2461 тест |
| быстрый уровень | **2174 passed, 3 skipped**, 1 предупреждение, 174 с |
| пропуски | 2 × `test_eq_references.py:80` «нет vault/knowledge/ — копия без vault (поставка, FEAT-031)»; 1 × `test_xlsx_reader.py:476` «черновик руководителя вне git (решение 11)» |
| предупреждение | `PytestRemovedIn10Warning: Class-scoped fixture defined as instance method is deprecated` — `tests/test_val002.py:474` (`TestCaseC_MeshConvergence.solutions`). В pytest 10 станет ошибкой; у заказчика pytest ставится без верхней границы (`pytest>=7.0`) → шаг 1 |
| ссылки тестов и кода на файлы вне `numerical_solver/` | нет (только в комментариях — пути `vault/`, ID задач) |

Полный прогон среза в **свежем окружении** (numpy 2.5.4, matplotlib 3.11.2, scipy 1.18.1 с PyPI; общий venv — numpy 2.5.2, matplotlib 3.11.1) — `vault/issues/feat-031/probes/slice_full_fresh_venv.out.txt`, итог — §1.6.

Сохранённых побайтных эталонов (хешей) в тестах нет: `test_matrix_matches_reference` сверяет коэффициенты СЛАУ с независимой сборкой в том же процессе (`rtol = 1e-12`), числа примеров — с README с допусками. Поэтому решение 50 реализуемо без снимка.

### 1.2. Sphinx: пробы `sphinx_probe.py`, `sphinx_module_sections.py`

Окружение пробы: `dist/probe-feat031/venv` — Sphinx 9.1.0, myst-parser 5.1.0, docutils 0.22.4; оба пакета из среза `v1.0.0`.

| Что | Итог |
|---|---|
| русские заголовки NumPy через `napoleon_custom_sections` (`("Параметры", "Parameters")` и т. д.) | распознаются; при `language = "ru"` подписи полей в HTML: **«Параметры», «Результат», «Тип результата», «Исключение»**; рубрики: Notes → «Заметки», Examples → «Примеры»; тип атрибута — «Type» (не переведён). При `"en"` — английские |
| замена меток в докстрингах обработчиком `autodoc-process-docstring` по таблице из `.aux` | «Ур. (eq:energy_disc_full)» → «Ур. (68)», «ssec:time_scheme» → «п. 4.1»; меток в HTML не осталось |
| включение `README.md` директивой MyST `{include}` | **26 предупреждений `myst.xref_missing`** — все от ссылок README на файлы и каталоги (`doc/problem_statement.tex`, `gpn_multiphase_solver/`, `CHANGELOG.md`, `examples/README.md`…); формулы `$…$` (расширение `dollarmath`) — без предупреждений |
| autodoc нынешнего публичного интерфейса (31 функция, 35 классов, 4 модуля) | **9 ошибок docutils** (`plot_pvt_properties` и др.: «Unexpected indentation», «Definition list ends without a blank line», `|G^o|` — «Undefined substitution») — уходят при переписывании |
| подразделы в докстринге модуля (обзор пакета) | объявленный в `napoleon_custom_sections` простой строкой — **рубрика**; необъявленный — настоящий заголовок `<h2>`; рубрика `.. rubric::` — рубрика; предупреждений нет ни в одном случае |
| время сборки | 9.6 с |

### 1.3. Постановка и таблица номеров

- `problem_statement.tex`: 161 метка `eq:`/`sec:`/`ssec:`/`sssec:`/`app:` (130 `eq:`).
- `.aux` с hyperref: `\newlabel{eq:energy_disc_full}{{68}{23}{}{equation.68}{}}`, `\newlabel{ssec:time_scheme}{{4.1}{28}{}{subsection.4.1}{}}` — номер — первая группа.
- `pdflatex` (MiKTeX, `C:\Users\Artur\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe`) — два прохода 3.4 с, PDF 0.6 МБ, после двух проходов — все 161 метки. `.aux` основного каталога от 14.10 старше `.tex` (15.10) — таблицу строить только по свежему `.aux`.

### 1.4. Докстринги сейчас (проба `docstring_census.py`, 2026-10-17)

| | `gpn_multiphase_solver` |
|---|---|
| модули | 49: нет 5 / одна строка 10 / многострочный 34 |
| классы | 52: 0 / 33 / 19 |
| функции | 64: 0 / 27 / 37 |
| методы | 154: 72 / 65 / 17 |
| разделы Parameters/Returns | 0 (и у функций FEAT-033…036 — тоже 0) |
| с ID задач / с `vault/` | 67 / 2 |

### 1.5. Что ещё найдено

- `numerical_solver/README.md` (526 строк на `887c5ca`, под git): строка 237 — «`dt_after_control_change` … рекомендуемое значение — 2», строка 331 — «задать `time.dt_after_control_change` = 2»; после [[BUG-026]] в примерах 16, 17 — 0.11 с (README 16, строки 61, 146: при 2 с $R_s$ у забоя 4.79 вместо 5.08). Строка 238 — `skin` без оговорки [[BUG-029]] (только гидродинамика, при $s > 0$ — предупреждение, `io/config.py::_warn_skin_not_in_energy`). Все 20 относительных ссылок README ведут на существующие файлы (аудит 1).
- Ссылки на `vault/` в передаваемых `.md`: `CHANGELOG_1.0.3.md` — 21 строка «- Issue: …; plan: `vault/plans/…` of the GPN project.», README 13a строка 214, README 14 строка 254.
- `CHANGELOG_1.0.3.md`: раздела о `1.0.3+gpn.2` нет; в каждом разделе после DEBT-059 — «The distribution version stays `1.0.3+gpn.1`» (верно на момент правки).
- `numerical_solver/pyproject.toml:10` — `description = "FVM solver for two-phase Black Oil filtration with energy equation"`: гидродинамику решает прототип; `gpn_multiphase_solver/__init__.py:1` — та же неточность. Комментарий `pyproject.toml:56-57` ссылается на пробу в `vault/issues/debt-059/`.
- `py -0p` на этой машине: Python 3.13 и 3.9 — `setup.bat` обязан проверять версию после `py -3`.
- Подпакеты без докстрингов: `energy/__init__.py`, `hydro/__init__.py`, `io/__init__.py` (пустые), `grid/__init__.py`, `pvt/__init__.py` (только импорты).

### 1.6. Полный прогон среза в свежем окружении

Срез `v1.0.0`, окружение `dist/probe-feat031/venv` с PyPI на 2026-10-18 (numpy 2.5.4, scipy 1.18.1, matplotlib 3.11.2, pytest 9.1.1; оба пакета установлены из среза без `-e`), `pytest tests/ -q -rs` из каталога среза (`vault/issues/feat-031/probes/slice_full_fresh_venv.out.txt`):

- **2458 passed, 3 skipped**, 1 предупреждение (фикстура `test_val002.py:474`), 694 с;
- пропуски — те же три причины, что в §1.1.

Вывод: числа примеров против README сходятся и на версиях, отличных от общего venv, — приёмка без хранимого эталона (решение 50) работоспособна. Время полного прогона в приёмке — ~12 мин на этой машине.

## 2. Анализ

### 2.1. Формулы → код

Новых формул нет (подтип «Инфраструктура»). Ссылки на уравнения в переписанных докстрингах — метками постановки (правило CLAUDE.md, сторож `tests/test_eq_references.py`); в HTML метка заменяется номером (решение 17, §1.2).

### 2.2. Обратная совместимость

- [x] Поведение пакета не меняется: правятся докстринги, `description`, README; новые файлы — `doc/source/`, `tools/`, `setup.bat`, тесты.
- [x] Конфиги, книги, истории примеров — без изменений (ни одного вычисления не трогаем).
- [x] Публичный API — прежний.
- [x] Существующие тесты проходят без изменений, кроме `tests/test_val002.py` (форма фикстуры, шаг 1 — числа те же).
- [ ] Общий venv получает `sphinx`, `myst-parser` (шаг 1) — после влития `pip install -e ".[dev]"` в основном каталоге ничего не меняет (уже стоят).

### 2.3. Варианты и выбор

**Сборка среза (решение 37: `Oil_Gas/tools/`).**

| Вариант | Суть | За | Против |
|---|---|---|---|
| А | ключ у `tools/release.py` | одна команда | выпуск (коммиты, метка, push, Releases) и передача — разные действия; передаче нужны LaTeX и Sphinx, выпуску — нет |
| **Б (выбран)** | отдельный `tools/handover.py <метка>`, берёт `extract()` из `tools/release.py` | не трогает git (только чтение), можно повторять; общий код — один | второй скрипт в `tools/` |

**Сверка в приёмке** — решение 50 (числа сверяют тесты).

**Страж правила докстрингов.** Правило «публичный интерфейс — в стиле NumPy» без проверки разойдётся с кодом при первой правке сигнатуры. Выбран тест `tests/test_docs.py`: перечень объектов — из `doc/source/api.rst` (один источник), проверки — разделы, имена параметров и полей dataclass, отсутствие ID задач и `vault/`. Переход — списком `PENDING` со строгим `xfail`: объект, у которого докстринг уже переписан, падает как XPASS и обязан уйти из списка; после шага 9 список пуст и удаляется.

### 2.4. Решения плана (подтверждаются аудитом)

- П1. `tools/handover.py <метка>` — §3, шаг 13. Только чтение git; выход — `dist/handover-<версия>/` (`dist/` в `.gitignore`).
- П2. `numerical_solver/tools/acceptance.py` — только стандартная библиотека; на свежем срезе (`.venv` нет); окружение — `setup.bat`; полный прогон тестов с белым списком причин пропуска; сборка документации `-W`; книга (`template` → `run`) и конфиг из постороннего каталога (`<срез>-acceptance` рядом со срезом).
- П3. Документация: `doc/source/{conf.py, index.md, readme.md, package.rst, api.rst, eq_numbers.json}`, тема `alabaster` (входит в Sphinx), `language = "ru"`, `suppress_warnings = ["myst.xref_missing"]` (решение 21) + тест, что каждая относительная ссылка README ведёт на существующий файл (возмещает подавление).
- П4. Замена меток: `eq:` → «(N)», `sec:`/`ssec:`/`sssec:`/`app:` → «п. N»; метки нет в таблице — предупреждение Sphinx (с `-W` — отказ сборки).
- П5. Заголовки разделов докстрингов: «Параметры», «Возвращает», «Исключения», «Атрибуты», «Примеры» (синонимы стандартных), «Примечания» — простая строка (рубрика «Примечания», а не переведённое «Заметки»); подразделы технического описания — простыми строками в `napoleon_custom_sections` (иначе выходят заголовками `<h2>`); тест сверяет, что все заголовки докстрингов документируемых модулей объявлены.
- П6. «Ограничения» (решение 34) — один раздел README (входит и в HTML); техническое описание на него ссылается.
- П7. Нижние границы `sphinx>=7.2`, `myst-parser>=2.0` — не проверялись (решение 32); проверено на Sphinx 9.1, myst-parser 5.1. Причина не ставить 9.1/5.1: на Python 3.10 (разрешён `requires-python`) свежих версий нет — `setup.bat` упал бы.
- П8. Выпуск поставки после влития — `1.0.1` (PATCH: документация и скрипты, поведение пакета не меняется; номер не важен — решение 45). Передача — `python tools/handover.py v1.0.1` (§6).

### 2.5. Подводные камни

| # | Камень | Статус |
|---|---|---|
| К1 | `tools/release.py` ищет литерал регуляркой `^(__version__\s*=\s*)…` по всему тексту `__init__.py` (`re.M`): строка докстринга, начинающаяся с `__version__ =`, даст «литералов 2» и сорвёт выпуск. `test_packaging.py` этого **не** ловит — читает литерал разбором AST, строка докстринга для него не присваивание (аудит 1). Поэтому шаг 9 добавляет тест той же регуляркой | ⚠️ шаг 9 |
| К2 | Общий venv: `pip install -e` из worktree перенаправит пакеты общего venv на worktree. В шаге 1 — только `pip install "sphinx>=7.2" "myst-parser>=2.0"`. `conf.py` кладёт в `sys.path` дерево своего каталога и прототип — документация worktree описывает код worktree (как `pythonpath` pytest) | ⚠️ шаги 1, 3 |
| К3 | `-W` и ссылки README (26 × `myst.xref_missing`) — подавление типа + тест ссылок README | ⚠️ шаги 3, 9 |
| К4 | Старые myst-parser могут называть тип предупреждения иначе — тогда подавление не сработает и `-W` откажет на старых версиях (Python 3.10) | ⚠️ принято (решение 32), §5 |
| К5 | Перевод подписей: «Возвращает» в HTML выходит «Результат», Notes — «Заметки» (поэтому «Примечания» — простая строка) | ✅ П5 |
| К6 | `PENDING` со строгим `xfail`: если внести в список объект, который уже проходит, тест упадёт XPASS. Список — не руками, а по факту прогона (шаг 4) | ⚠️ шаг 4 |
| К7 | Переписывая докстринг, легко потерять обоснование («решение пользователя …», ID задачи). Обоснование переносится в комментарий кода рядом (правило «не удалять комментарии»), в докстринг публичного интерфейса — только контракт | ⚠️ шаги 5–9 |
| К8 | `tests/test_eq_references.py` обходит `tests/*.py`: в `tests/test_docs.py` нельзя писать запрещённые формы («eq. N», «eq. имя», «.tex:N», «метка (N)»), а метки в строках теста должны существовать в постановке | ⚠️ шаги 2–4 |
| К9 | `tools/handover.py` в worktree архивирует `HEAD` worktree — только закоммиченное. `/implement` коммитит по шагам — перед шагом 13 рабочее дерево чистое | ⚠️ шаг 13 |
| К10 | Приёмка: ~15 мин и доступ к PyPI (`setup.bat`); полный прогон в свежем окружении — версии с PyPI на день прогона | ⚠️ шаг 13, §1.6 |
| К11 | [[DEBT-082]] в работе (каталог вывода, README) — тексты README искать по содержанию | ⚠️ «Как начать», п. 5 |
| К12 | Срез содержит упоминания `tools/release.py` (README §1 «Из выпуска», комментарий `pyproject.toml`, README прототипа) — его в срезе нет | ✅ принято (решение 48) |
| К13 | `setup.bat`: `py -3` на машине с 3.9 и 3.13 берёт 3.13, но при одной 3.9 — 3.9; поэтому проверка версии после каждого кандидата | ✅ шаг 10 |
| К15 | `.aux` разработчика может быть старше `.tex` (в основном каталоге — от 14.10 при `.tex` от 15.10; номера пока совпадают, 0 различий из 161): сверка «таблица = `.aux`» дала бы ложный отказ — тест пропускается, если `.aux` старше `.tex` | ⚠️ шаг 2 |
| К16 | `git archive` на этой машине (`core.autocrlf=true`) отдаёт `.bat` с CRLF (проверено на `run.bat`); в индексе — LF. У команды заказчика, положившей срез в свой git с другими настройками, `setup.bat` выйдет с LF. Успешный путь `setup.bat` с LF проверен пробой, переход `goto fail` в LF-файле cmd исполняет ненадёжно — `numerical_solver/.gitattributes`: `*.bat text eol=crlf` | ⚠️ шаг 10 |
| К17 | При `p_wf` выше давления у забоя прототип не отказывает и не нагнетает, а останавливает скважину (дебит 0, `radial_blackoil/blackoil.py:217-247`); конфиг отвергает только `q_oil < 0` — формулировка раздела «Ограничения» | ⚠️ шаг 12 |
| К14 | Sphinx импортирует пакет при сборке и пишет `__pycache__` в срез — в `tools/handover.py` сборка с `PYTHONDONTWRITEBYTECODE=1` и `-d` вне среза | ⚠️ шаг 13 |
| Прототип | код прототипа не меняется — тесты прототипа и регрессия не нужны; `CHANGELOG_1.0.3.md` — текст | ✅ |

### 2.6. Новые проблемы

- Фикстура `test_val002.py:474` — устаревшая форма pytest (§1.1): исправляется в шаге 1 (блокирует будущую приёмку у заказчика с pytest 10), в реестр не идёт.
- Полный прогон в свежем окружении (§1.6) — без отказов; регистрировать нечего.

## 3. Шаги

### Шаг 0: подготовка

**Цель:** worktree, baseline, проверка базы.
**Что сделать:**
1. «Как начать», пп. 4–7. Записать HEAD базы, число тестов, итог быстрого уровня.
2. `git diff 024e19a numerical_scheme/implementation --stat -- numerical_solver/README.md numerical_solver/gpn_multiphase_solver` — если база уехала, сверить номера строк шагов 5–12 с текущими (тексты — по содержанию).

**Проверка:** baseline записан.

### Шаг 1: зависимости документации, `description`, фикстура pytest 10

**Цель:** Sphinx в `[dev]`; точное описание пакета; тесты без устаревшей формы фикстуры.
**Файлы:** `numerical_solver/pyproject.toml`, `numerical_solver/tests/test_val002.py`.

**Что сделать:**
1. `pyproject.toml`, группа `dev` (строки 29–32):
   ```toml
   dev = [
       "pytest>=7.0",
       # Сборка HTML-документации из README и докстрингов (FEAT-031):
       # python -m sphinx -W -b html doc/source doc/build/html. Нижние границы
       # не проверялись; проверено на Sphinx 9.1, myst-parser 5.1
       "sphinx>=7.2",
       "myst-parser>=2.0",
   ]
   ```
2. `pyproject.toml:10`: `description = "Near-wellbore non-isothermal Black Oil flow: energy equation solver coupled with the radial-blackoil hydrodynamic prototype"`.
3. `pyproject.toml:56-57`: «Установку проверяет приёмка в чистом окружении (vault/issues/debt-059/probes/clean_env_acceptance.py)» → «Установку проверяет приёмка среза (tools/acceptance.py)».
4. Общий venv: `numerical_solver\.venv\Scripts\python -m pip install "sphinx>=7.2" "myst-parser>=2.0"` — **без** `-e` (К2).
5. `tests/test_val002.py`, класс `TestCaseC_MeshConvergence`: `_run_to_stationary` (строка 455) использует только константы класса — сделать `@classmethod` (`cls.MU_JT`, `cls.DT_LARGE`, `cls.N_STEPS`); фикстуру (строка 474) — классовым методом, как советует сообщение pytest:
   ```python
   @pytest.fixture(scope="class")
   @classmethod
   def solutions(cls):
       ...
           r, T = cls._run_to_stationary(N)
   ```
   Порядок декораторов проверен аудитом 1 (`vault/issues/feat-031/probes/audit_classmethod_fixture.py`): pytest 9.1.1 с `-W error::pytest.PytestRemovedIn10Warning` и pytest 7.4.4 (нижняя граница `pytest>=7.0`) — passed, фикстура считается один раз на класс. Запасной вариант (проба `audit_module_fixture.py`, тоже 7.4 и 9.1) — фикстура уровня модуля над классом, вызывающая `TestCaseC_MeshConvergence._run_to_stationary(N)`. Комментарий — почему (pytest 10 удаляет фикстуры класса в форме метода экземпляра; поставка ставит pytest без верхней границы).

**Проверка после шага:**
- `.venv\Scripts\python -m pytest tests/test_val002.py -k MeshConvergence -q -W error::pytest.PytestRemovedIn10Warning` — passed, предупреждения нет.
- `.venv\Scripts\python -m pytest tests/test_packaging.py -q` — passed (`test_declared_dependencies_cover_imports` смотрит импорты пакета, `doc/` в пакет не входит).
- `.venv\Scripts\python -c "import sphinx, myst_parser; print(sphinx.__version__, myst_parser.__version__)"`.
- Регресс: быстрый.

**Оценка:** ~15 строк, 15 мин.

### Шаг 2: таблица «метка → номер»

**Цель:** решение 23 — таблица в `doc/source/` под git, генератор в `numerical_solver/tools/`, тесты.
**Файлы:** `numerical_solver/tools/eq_numbers.py` (новый), `numerical_solver/doc/source/eq_numbers.json` (новый), `numerical_solver/tests/test_docs.py` (новый).

**Что сделать:**
1. `tools/eq_numbers.py`:
   ```python
   """Таблица «метка → номер» для HTML-документации: doc/problem_statement.aux → doc/source/eq_numbers.json.

   Номера уравнений видны только в PDF постановки; в докстрингах ссылка —
   метка (правило CLAUDE.md «Связь формула → код»). При сборке HTML метка
   заменяется номером по этой таблице (doc/source/conf.py). Таблица хранится
   в git, поэтому для сборки HTML LaTeX не нужен.

   После правки problem_statement.tex, из каталога numerical_solver:

       cd doc; pdflatex problem_statement.tex; pdflatex problem_statement.tex; cd ..
       .venv\\Scripts\\python tools\\eq_numbers.py           # записать таблицу
       .venv\\Scripts\\python tools\\eq_numbers.py --check   # сверить; код 1 — расходится
   """
   import argparse
   import json
   import re
   import sys
   from pathlib import Path

   ROOT = Path(__file__).resolve().parents[1]                  # numerical_solver/
   AUX = ROOT / "doc" / "problem_statement.aux"
   TABLE = ROOT / "doc" / "source" / "eq_numbers.json"
   # С hyperref: \newlabel{eq:x}{{68}{23}{}{equation.68}{}}; без него — {{68}{23}}.
   # Номер — первая группа. Префиксы — как в tests/test_eq_references.py
   NEWLABEL = re.compile(r"\\newlabel\{((?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+)\}\{\{([^}]*)\}")


   def read_aux(path: Path = AUX) -> dict[str, str]:
       """Метки постановки и их номера из .aux."""
       return dict(NEWLABEL.findall(path.read_text(encoding="utf-8")))


   def dump(table: dict[str, str]) -> str:
       """Текст таблицы: JSON, ключи по алфавиту, по строке на метку."""
       return json.dumps(dict(sorted(table.items())), ensure_ascii=False, indent=1) + "\n"


   def main(argv: list[str] | None = None) -> int:
       ...  # --check: сравнить dump(read_aux()) с TABLE, напечатать расхождения, код 1;
            # без ключа — записать TABLE; нет .aux — сообщение с командой pdflatex, код 2


   if __name__ == "__main__":
       sys.exit(main())
   ```
2. В worktree: `cd numerical_solver\doc; pdflatex -interaction=nonstopmode problem_statement.tex` два раза, затем `..\..\..\numerical_solver\.venv\Scripts\python tools\eq_numbers.py` → `doc/source/eq_numbers.json` (161 метка). PDF и `.aux` — в `.gitignore`.
3. `tests/test_docs.py` — модуль загружается так: `spec_from_file_location("eq_numbers", ROOT / "tools" / "eq_numbers.py")` (`tools/` — не пакет). Тесты:
   - `test_eq_numbers_cover_tex_labels` — множество ключей таблицы равно множеству `\label{…}` постановки (шаблон `LABEL_DEF` как в `test_eq_references.py`); работает без `.aux` — ловит новую метку без пересборки таблицы;
   - `test_eq_numbers_match_aux` — `pytest.skip("нет problem_statement.aux — таблицу сверить нечем")`, если `.aux` нет; `pytest.skip("problem_statement.aux старше problem_statement.tex — пересоберите PDF")`, если `aux.stat().st_mtime < tex.stat().st_mtime` (К15: старый PDF у разработчика — не ошибка таблицы); иначе таблица равна `read_aux()`. Причину «нет problem_statement.aux» взять **дословно** в белый список приёмки (шаг 11); вторая в срезе не возникает (`.aux` в архив не входит).

**Проверка:** `pytest tests/test_docs.py -q` — 2 passed. Регресс: быстрый.
**Подводные камни:** К8.
**Оценка:** ~90 строк, 30 мин.

### Шаг 3: исходники документации

**Цель:** `doc/source/` — конфигурация, страницы, перечень публичного интерфейса.
**Файлы:** `numerical_solver/doc/source/conf.py`, `index.md`, `readme.md`, `package.rst`, `api.rst` (все новые); `numerical_solver/tests/test_docs.py`.

**Что сделать:**
1. `conf.py`:
   ```python
   """Сборка HTML-документации пакета gpn_multiphase_solver (Sphinx).

   Из каталога numerical_solver:

       .venv\\Scripts\\python -m sphinx -W -b html doc/source doc/build/html

   Главный файл — doc/build/html/index.html. Состав: README.md пакета,
   техническое описание (докстринги пакета и подпакетов), публичный интерфейс
   (api.rst). Прототип и примеры не входят.
   """
   import json
   import re
   import sys
   from pathlib import Path

   from sphinx.util import logging

   ROOT = Path(__file__).resolve().parents[2]                  # numerical_solver/
   # Документируется код этого дерева, а не установленный пакет: в worktree
   # общий venv указывает на основной каталог (так же pythonpath pytest в pyproject.toml)
   sys.path[:0] = [str(ROOT), str(ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")]

   import gpn_multiphase_solver  # noqa: E402

   project = "gpn-multiphase-solver"
   version = release = gpn_multiphase_solver.__version__
   language = "ru"
   extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "myst_parser"]
   html_theme = "alabaster"
   html_title = f"gpn-multiphase-solver {release}"
   autodoc_member_order = "bysource"

   # ── Докстринги в стиле NumPy с русскими заголовками ──
   # Синоним стандартного раздела — подписи полей переводит language = "ru"
   # («Параметры», «Результат», «Исключение»). «Примечания» — простой строкой:
   # синоним Notes вышел бы рубрикой «Заметки». Подразделы технического
   # описания — тоже простыми строками (рубрики); необъявленный подраздел
   # вышел бы заголовком страницы (проба FEAT-031)
   napoleon_google_docstring = False
   napoleon_numpy_docstring = True
   napoleon_custom_sections = [
       ("Параметры", "Parameters"), ("Возвращает", "Returns"),
       ("Исключения", "Raises"), ("Атрибуты", "Attributes"),
       ("Примеры", "Examples"),
       "Примечания",
       "Назначение и границы модели", "Устройство пакета", "Поток данных расчёта",
       "Связь с прототипом", "Конвенция знаков", "Связь формула → код",
       "Шаг по времени и сходимость", "Тесты", "Расширение", "Соглашения кода",
       "Модули",
   ]

   # ── README (MyST) ──
   # Ссылки README на файлы и каталоги в HTML не разрешаются (README не
   # правится ради документации — решение пользователя); их существование
   # проверяет tests/test_docs.py::test_readme_links_exist
   myst_enable_extensions = ["dollarmath"]
   suppress_warnings = ["myst.xref_missing"]

   # ── Метки постановки → номера (таблица — tools/eq_numbers.py) ──
   _logger = logging.getLogger(__name__)
   _NUMBERS = json.loads((Path(__file__).parent / "eq_numbers.json").read_text(encoding="utf-8"))
   _REF = re.compile(r"\(?((?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+)\)?")


   def _numbers(app, what, name, obj, options, lines):
       """Метка eq: → «(N)», раздела → «п. N»; метки нет в таблице — предупреждение."""
       def sub(m):
           label = m.group(1)
           n = _NUMBERS.get(label)
           if n is None:
               _logger.warning(f"{name}: метки {label} нет в eq_numbers.json")
               return m.group(0)
           return f"({n})" if label.startswith("eq:") else f"п. {n}"
       lines[:] = [_REF.sub(sub, s) for s in lines]


   def setup(app):
       app.connect("autodoc-process-docstring", _numbers)
   ```
2. `index.md`:
   ````markdown
   # gpn-multiphase-solver

   Документация пакета `gpn_multiphase_solver`: сведения для пользователя
   (README), техническое описание и публичный интерфейс.

   ```{toctree}
   :maxdepth: 2

   readme
   package
   api
   ```
   ````
3. `readme.md`: ````markdown```{include} ../../README.md``` ```` (одна директива, как в пробе).
4. `package.rst` — «Техническое описание»: `.. automodule:: gpn_multiphase_solver`, затем подраздел «Подпакеты» — `.. automodule::` без `:members:` для `gpn_multiphase_solver.pvt`, `.energy`, `.hydro`, `.grid`, `.io`, `.diagnostics`, `.report`.
5. `api.rst` — **единственный перечень публичного интерфейса** (решение 51; объекты — как в пробе `sphinx_probe.py`, `FUNCTIONS`/`CLASSES`/`MODULES`). Разделы и директивы:
   - «Расчёт»: `autofunction` `report.pipeline.run_case`; `autoclass` `report.pipeline.CaseResult`; `autoexception` `report.pipeline.CaseConfigError`, `report.pipeline.CaseRunError`; `autofunction` `cli.configure_batch_run`, `cli.main`.
   - «Конфигурация и книга ввода»: `io.config.load_config`; `autoclass` `io.config.SimulationConfig`, `GeometryConfig`, `GridConfig`, `RockConfig`, `PVTConfig`, `RelPermConfig`, `ThermalConfig`, `InitialConfig`, `HistoryInterval`, `TimeConfig`, `NumericsConfig`, `OutputConfig`; `io.workbook_template.write_template`, `io.workbook_convert.convert_workbook`.
   - «Сборка решателя»: `autoclass` `factory.SimulatorFactory` с `:members: from_config`; `factory.create_pvt`, `factory.create_relperm`.
   - «Решатель и история расчёта»: `simulator.Simulator` с `:members: run, grid, pvt, relperm`; `state.SimulationState`, `state.WellData`, `state.SimulationHistory`.
   - «Режим работы скважины и граничные условия»: `bc.WellControl`; `bc.PressureControl` с `:members: p_wf`; `bc.RateControl` с `:members: q_oil, min_bhp`; `state.BoundaryConditions`.
   - «Сетка»: `grid.base.Grid` с `:members:`; `grid.log_radial.LogRadialGrid`.
   - «PVT и ОФП»: `pvt.base.HydroPVT`, `pvt.base.FullPVT`, `pvt.base.DifferentiableHydroPVT`, `pvt.base.RelPermModel`, `pvt.base.DifferentiableRelPerm` — с `:members:`; `pvt.standing.StandingFullPVT`, `pvt.table_full.TableFullPVT`, `pvt.relperm.CoreyRP`, `pvt.prototype_adapter.PrototypeRPAdapter` — без членов.
   - «Запись результатов и рисунки»: `io.output.save_csv`, `save_well_csv`, `save_npz`, `plot_profiles`, `plot_well_rate`, `plot_wellbore_dynamics`, `plot_pvt_properties`, `plot_relperm_curves`, `plot_energy_balance_series`, `pvt_table_nodes`; `io.figures.save_figure`, `export_emf`.
   - «Балансы»: `energy.balance.compute_energy_balance`, `mass_balance.compute_mass_balance`.
   - «Проверки»: `diagnostics.closed_form.solve_closed`, `diagnostics.rs.front_radius`, `diagnostics.temperature.single_phase_asymptote`, `diagnostics.two_phase.compute_gor`, `compute_free_gas_prediction`, `predict_saturation`, `dupuit_check`, `degassing_front`; `report.relperm.report_relperm`.
   - «Единицы»: `.. automodule:: gpn_multiphase_solver.units` (константы перечисляются в докстринге модуля).
   Все имена — полные (`gpn_multiphase_solver.…`). Dataclass — без `:members:` (поля — в разделе «Атрибуты» докстринга; `:members:` дал бы дубли).
6. `tests/test_docs.py` — разбор `api.rst`: строки `.. auto(function|class|exception|module):: <имя>` и следующие за ними `:members: a, b` (или `:members:` без списка — открытые члены из `cls.__dict__`). Функция `api_objects()` → список `(полное имя, вид)`, где вид — module / class / function / method / property. Тесты:
   - `test_api_objects_importable` — каждый объект импортируется (`importlib.import_module` + `getattr` по цепочке);
   - `test_api_covers_required_names` — в перечне есть: имена README §4 и `tests/test_public_api.py` (список `REQUIRED` в тесте, с комментарием-источником) и **все** имена `from gpn_multiphase_solver… import …` из `examples/**/*.py` (разбор AST), кроме констант (ИМЕНА_ЗАГЛАВНЫМИ) и скриптов белого ящика `WHITE_BOX = {"verify_balance_vs_solver.py"}` (подменяет `TridiagEnergySolver.solve`); `cli.main` и `units` — в перечне.
   - `test_readme_links_exist` — каждая относительная ссылка `[…](путь)` в `numerical_solver/README.md` (без `http`, `#`; якорь отрезать) ведёт на существующий путь от `numerical_solver/` (К3).
7. Пробная сборка без `-W`: `.venv\Scripts\python -m sphinx -b html -q doc/source <worktree>\dist\docs_try` (каталог `dist/` игнорируется) — записать число предупреждений. Ожидание (проба аудита `audit_plan_docs.py` — ровно этот `conf.py` и этот перечень на срезе `v1.0.0`): **9 ошибок docutils** — `io.output.plot_pvt_properties` (3), `plot_relperm_curves` (3), `plot_energy_balance_series` (2), `diagnostics.two_phase.compute_free_gas_prediction` (1), все уходят в шаге 8; `myst.xref_missing` — 0 (подавлены); предупреждений о метках нет; меток `eq:` в `api.html` — 0. Импорты примеров перечень покрывает полностью (67 объектов, непокрытых 0). `doc/build/` — в `.gitignore` (правило `build/`).

**Проверка:** `pytest tests/test_docs.py -q` — passed. Регресс: быстрый.
**Подводные камни:** К2, К3, К8.
**Оценка:** ~250 строк, 1.5 ч.

### Шаг 4: страж правила докстрингов

**Цель:** проверка правила CLAUDE.md «Docstring публичного интерфейса — в стиле NumPy» для объектов `api.rst`.
**Файлы:** `numerical_solver/tests/test_docs.py`.

**Что сделать:** тест `test_public_docstring(name)`, параметризованный по `api_objects()` (и по модулям `package.rst` + `api.rst`). Разбор разделов: строка-заголовок, за ней строка из `-` (≥ 3 знаков); раздел — до следующего заголовка (вспомогательная `sections(doc) -> dict[str, list[str]]`). Докстринг — `inspect.cleandoc(obj.__doc__ or "")` собственного объекта, **не** `inspect.getdoc`: тот подставляет докстринг базового класса или переопределённого метода, и объект без своего докстринга прошёл бы проверку. У свойства — `fget.__doc__` (`inspect.getattr_static(cls, имя)`). Правила:
- D1 — докстринг непуст, первая строка заканчивается точкой.
- D2 — функция или метод с параметрами (кроме `self`, `cls`) — раздел «Параметры»; множество имён записей раздела (строки без отступа вида `имя :` или `имя : тип`; запись napoleon `a, b : float` — два имени; `*args` — со звёздочкой) **равно** множеству параметров `inspect.signature`.
- D3 — «Возвращает» обязателен, если в теле есть `return <значение>` (AST исходника функции; вложенные `def`/`lambda` не считать) или есть аннотация результата, кроме `None`.
- D4 — свойство (`property`): непустая первая строка (с единицами), разделов «Параметры» нет.
- D5 — dataclass: раздел «Атрибуты», множество имён записей равно `dataclasses.fields`; класс не-dataclass с **собственным** `__init__` (`"__init__" in cls.__dict__`) с параметрами — «Параметры» в докстринге класса (как D2 для `__init__`). Унаследованный `__init__` не считается: у `CaseConfigError(ValueError)` он из `BaseException` (`*args`), разделу там не место. Dataclass с «Атрибутами» под `autoclass` без `:members:` и `autoexception` дублей и предупреждений не дают (проба аудита `audit_plan_docs.py`, п. 2).
- D6 — ни в одном докстринге объектов и модулей перечня нет `\b(BUG|DEBT|FEAT|VAL)-\d{3}\b` и `vault/` (решение 27).
- D7 — модули: все заголовки разделов (строка + `---`) объявлены в `napoleon_custom_sections` `doc/source/conf.py` (читать `ast.literal_eval` присваивания, без импорта conf).

Переход: `PENDING = frozenset({...})` — объекты, чьи докстринги ещё не переписаны; параметр получает `pytest.mark.xfail(strict=True, reason="докстринг ещё не переписан (FEAT-031)")`. **Список получить прогоном**, не руками (К6): сначала `PENDING = frozenset()`, `pytest tests/test_docs.py -q -k public_docstring` → имена упавших → в `PENDING`. Ожидание — почти весь перечень (~120 объектов); прошедшие сразу (если есть) в список не включать.

**Проверка:** `pytest tests/test_docs.py -q` — passed + xfailed, ни одного XPASS. Регресс: быстрый.
**Оценка:** ~200 строк, 1.5 ч.

### Образцы докстрингов (для шагов 5–9)

Функция:
```python
def compute_mass_balance(history) -> dict | None:
    """Ряды баланса массы нефтяного и газового компонентов по истории расчёта. Ур. (eq:residual_oil) problem_statement.tex.

    Параметры
    ---------
    history : SimulationHistory
        История расчёта; используется ``history.mass_balance`` — запасы и
        накопленные потоки компонентов на каждой записи.

    Возвращает
    ----------
    dict or None
        Ряды по моментам записей: ``t``, с; запасы, добыча, приток, м³ст;
        невязки — абсолютные, м³ст, и относительные. ``None`` — решатель не
        вёл запас компонентов.
    """
```
Dataclass (поля — по `dataclasses.fields`, единицы и умолчания — из комментариев полей и README §3.1; комментарии полей остаются):
```python
@dataclass
class GeometryConfig:
    """Геометрия скважины и пласта — раздел ``geometry`` файла конфигурации.

    Атрибуты
    --------
    r_well : float
        Радиус скважины r_w, м.
    R_ext : float
        Радиус контура питания r_e, м.
    h : float
        Толщина пласта, м.
    """
```
Абстрактный метод:
```python
@abstractmethod
def Bo(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
    """Объёмный коэффициент нефти B_o(p, R_s).

    Параметры
    ---------
    p : numpy.ndarray
        Давление, Па.
    Rs : numpy.ndarray
        Газосодержание, м³ст/м³ст; той же формы, что ``p``.

    Возвращает
    ----------
    numpy.ndarray
        B_o, м³/м³ст.
    """
```
Свойство: `"""Радиусы центров ячеек, м; массив длины N."""`.

Правила для всех: первая строка — что это (и метка уравнения, если есть); единицы у каждой величины; «Исключения» — только реально возбуждаемые (читать код: `raise`, вызовы `_validate`); без ID задач, `vault/`, «решение пользователя» (К7 — в комментарии); формул нет (решение 36), величины — словами или обозначениями CLAUDE.md в простом тексте (`r_w`, `p_wf`); `` ``код`` `` — двойными обратными кавычками (RST). Метки — только существующие (`test_eq_references.py`).

Каждый из шагов 5–8: прочитать код объекта → переписать докстринг → убрать имя из `PENDING` → `pytest tests/test_docs.py -q` (без XPASS) → пробная сборка без `-W`, число предупреждений не растёт.

### Шаг 5: докстринги — расчёт, конфигурация, книга

**Файлы:** `gpn_multiphase_solver/report/pipeline.py` (`run_case`, `CaseResult`, `CaseConfigError`, `CaseRunError`), `gpn_multiphase_solver/cli.py` (`configure_batch_run`, `main`), `gpn_multiphase_solver/io/config.py` (`load_config`, `SimulationConfig` и 11 классов разделов), `io/workbook_template.py` (`write_template`), `io/workbook_convert.py` (`convert_workbook`). 21 объект.

**Контекст:** `run_case` (`pipeline.py:76-115` на `887c5ca`; DEBT-082 добавляет в `run_case` ~130 строк — искать по имени) — нынешний докстринг описывает аргументы абзацами; в NumPy-вид: параметры по **фактической** сигнатуре после DEBT-082 (на `887c5ca`: `config_path`, `output_dir`, `title`, `n_profiles`, `steady_state`, `overlays`) → «Параметры»; `CaseResult` → «Возвращает»; «Исключения»: `ValueError` (`n_profiles`), `CaseConfigError`, `CaseRunError` и то, что добавила DEBT-082 (занятый каталог вывода), — проверить по коду все пути. Разделы конфига: поля, единицы и умолчания — из `config.py` (комментарии полей) и README §3.1 (таблица, строки 211–241); `load_config` — какие ошибки (`ValueError` с именем поля) и предупреждения (`_warn_large_skin`, `_warn_skin_not_in_energy` и др.).
**Регресс:** быстрый.
**Оценка:** ~350 строк докстрингов, 2 ч.

### Шаг 6: докстринги — сборка, решатель, история, режим скважины, сетка

**Файлы:** `factory.py` (`SimulatorFactory`, `.from_config`, `create_pvt`, `create_relperm`), `simulator.py` (`Simulator`, `.run`, `.grid`, `.pvt`, `.relperm`), `state.py` (`SimulationState`, `WellData`, `SimulationHistory`, `BoundaryConditions`), `bc.py` (`WellControl`, `PressureControl`, `.p_wf`, `RateControl`, `.q_oil`, `.min_bhp`), `grid/base.py` (`Grid` и 13 свойств), `grid/log_radial.py` (`LogRadialGrid`). ~33 объекта.

**Контекст:** README §4 (строки 455–476) — содержимое истории: `history.times`, с; `states[i]` — `p`, Па, `T`, К, `Sg`, `Rs`, м³ст/м³ст; `well_data[i]` — `q_o_std`, `q_g_std`, м³ст/с, `m_o_well`, `m_g_well`, кг/с, `p_wf`, Па, `T_wf`, К. Знаки — конвенция CLAUDE.md (положительно — от скважины; дебит при добыче в `WellData` — проверить по `state.py`/адаптеру, README §3.5: «Дебиты при добыче положительны»). `Simulator.run` — какие исключения: `RuntimeError` при отказе шага (`simulator.py:325`), от `_check_temperature` (строка 430) и `_check_hydro_state` (строка 448).
**Регресс:** быстрый.
**Оценка:** ~300 строк, 2 ч.

### Шаг 7: докстринги — PVT и ОФП

**Файлы:** `pvt/base.py` (`HydroPVT` + 10 членов, `FullPVT` + 5, `DifferentiableHydroPVT` + 6, `RelPermModel` + 2, `DifferentiableRelPerm` + 2), `pvt/standing.py` (`StandingFullPVT`), `pvt/table_full.py` (`TableFullPVT`), `pvt/relperm.py` (`CoreyRP`), `pvt/prototype_adapter.py` (`PrototypeRPAdapter`). ~34 объекта.

**Контекст:** это контракт расширения (решение 16): для каждого метода — величина, единицы входов и результата, форма массивов. Метки — замыкающие соотношения постановки (`ssec:closures`): проверить имена в `problem_statement.tex` (`grep "\\label{eq:" doc/problem_statement.tex`).
**Регресс:** быстрый.
**Оценка:** ~350 строк, 2 ч.

### Шаг 8: докстринги — результаты, рисунки, балансы, проверки

**Файлы:** `io/output.py` (10 функций), `io/figures.py` (`save_figure`, `export_emf`), `energy/balance.py` (`compute_energy_balance`; ключи — `CUMULATIVE_KEYS` в разделе «Возвращает»), `mass_balance.py` (`compute_mass_balance`), `diagnostics/closed_form.py` (`solve_closed`), `diagnostics/rs.py` (`front_radius`), `diagnostics/temperature.py` (`single_phase_asymptote`), `diagnostics/two_phase.py` (5 функций), `report/relperm.py` (`report_relperm`). 23 объекта.

**Контекст:** все 9 ошибок docutils пробы — отсюда (`plot_pvt_properties` 3, `plot_relperm_curves` 3, `plot_energy_balance_series` 2, `compute_free_gas_prediction` 1): после шага их 0. `export_emf` — Inkscape, переменные `INKSCAPE`, `GPN_EXAMPLES_EMF` (README §1, строки 163–169).
**Регресс:** быстрый.
**Оценка:** ~300 строк, 2 ч.

### Шаг 9: техническое описание; страж без `PENDING`; сборка `-W`

**Цель:** решение 13 — техническое описание в докстрингах пакета и подпакетов; документация собирается без предупреждений.
**Файлы:** `gpn_multiphase_solver/__init__.py`, `pvt/__init__.py`, `energy/__init__.py`, `hydro/__init__.py`, `grid/__init__.py`, `io/__init__.py`, `diagnostics/__init__.py`, `report/__init__.py`, `units.py`; `tests/test_docs.py`.

**Что сделать:**
1. Докстринг `gpn_multiphase_solver/__init__.py` — обзор, подразделы (объявлены в `conf.py`, П5). Содержание — по коду и постановке, каждое утверждение проверить:
   - «Назначение и границы модели» — две фазы, воды нет, одномерная радиальная задача; гидродинамику ($p$, $S_g$, $R_s$) решает прототип `radial_blackoil`, пакет — уравнение энергии и управление расчётом; ограничения — раздел README «Ограничения».
   - «Устройство пакета» — модули и подпакеты одной строкой каждый: `bc`, `cli`, `diagnostics`, `energy` (`tridiag` — решатель энергии, `balance` — баланс энергии), `factory`, `fluxes`, `grid`, `hydro` (`prototype_adapter`), `io` (`config`, `output`, `figures`, `workbook_*`, `xlsx_reader`), `log`, `mass_balance`, `pvt`, `report`, `simulator`, `state`, `units`.
   - «Поток данных расчёта» — книга → `io.workbook_convert` → конфиг → `load_config` → `SimulatorFactory.from_config` → `Simulator.run` (на подшаге: гидродинамика прототипом через `PrototypeHydroAdapter`, затем энергия `TridiagEnergySolver`) → `SimulationHistory` → `report.pipeline.run_case` → `output/`.
   - «Связь с прототипом» — адаптер, единицы, отображение состояния и знаков потоков; почему ровно одна версия `radial-blackoil` (`pyproject.toml`); изменения прототипа — `CHANGELOG_1.0.3.md`.
   - «Конвенция знаков» — положительное направление — от скважины (рост $r$): скорости, расходы, потоки компонентов при добыче < 0; дебит скважины $q_{o,ст} = -G^o$ на забое > 0.
   - «Связь формула → код» — метки постановки в докстрингах и комментариях; в HTML — номера по `doc/source/eq_numbers.json` (`tools/eq_numbers.py`); сторож `tests/test_eq_references.py`.
   - «Шаг по времени и сходимость» — интервалы истории, `dt_integration`, деление шага при отказе (`max_retries`), нарастающий шаг после смены режима (`dt_after_control_change`), условие сходимости Ньютона прототипа, проверки состояния после шага.
   - «Тесты» — уровни (быстрый `-m "not slow"`, полный), метка `slow`, тесты и регрессия прототипа (`run_tests.bat`, `regression/`), приёмка среза `tools/acceptance.py`.
   - «Расширение» — новая PVT-модель (наследник `FullPVT`, ветка в `factory.create_pvt`, значение `pvt.model` в проверке конфига), ОФП (`RelPermModel`), режим скважины (`WellControl`) — проверить по коду, что именно нужно; новый пример (конфиг + README).
   - «Соглашения кода» — `numpy`, не `math`; докстринги: публичный интерфейс — NumPy, внутренний код — строка и метка; комментарии к знакам потоков и выбору ячейки выше по потоку.
   - Ни одной строки, начинающейся с `__version__ =` (К1); импортов не добавлять (`--help` команды не тянет scipy и прототип).
2. Докстринги подпакетов: `pvt`, `energy`, `hydro`, `grid`, `io` — новые, раздел «Модули»; `diagnostics`, `report` — переписать без ID задач; `units` — константы с единицами.
3. `PENDING` пуст → удалить его и `xfail` из теста.
4. `tests/test_docs.py::test_version_literal_unique` (К1) — в тексте `gpn_multiphase_solver/__init__.py` ровно одно совпадение `re.findall(r"^__version__\s*=", text, re.M)` — та же форма, что ищет `tools/release.py` (`VERSION_RE`); `tools/release.py` в срез не входит, поэтому шаблон — копией с комментарием-ссылкой.
5. `tests/test_docs.py::test_docs_build_without_warnings` — `@pytest.mark.slow`: `subprocess.run([sys.executable, "-m", "sphinx", "-W", "-b", "html", "-q", "-d", tmp_path / "doctrees", "doc/source", tmp_path / "html"], cwd=ROOT)` → код 0, `index.html` есть; при отказе — вывод в сообщении.

**Проверка:** `pytest tests/test_docs.py -q` (без `slow`; в том числе `test_version_literal_unique`) и `pytest tests/test_docs.py -q -m slow` — passed; `-W`-сборка вручную — 0 предупреждений; `pytest tests/test_packaging.py -q` — passed. Регресс: быстрый.
**Оценка:** ~250 строк, 2 ч.

### Шаг 10: `setup.bat`

**Цель:** решения 38–40.
**Файлы:** `numerical_solver/setup.bat` (новый), `numerical_solver/.gitattributes` (новый), `numerical_solver/tests/test_setup_bat.py` (новый).

**Проверено аудитом 1:** текст ниже дословно, в LF-варианте, в копии среза `v1.0.0` (`dist/probe-feat031/slice/`), запуск `call setup.bat` из другого каталога в одной сессии cmd: Python 3.13 найден через `py -3`, `.venv` создана, оба пакета установлены, «Done.», текущий каталог вызывающей консоли не изменился, 121 с. Путь `goto fail` не проверялся.

**Что сделать:**
1. `setup.bat` (только ASCII; CRLF):
   ```bat
   @echo off
   rem Setup of gpn-multiphase-solver for development (Windows): finds Python 3.10+,
   rem creates .venv next to this file if absent, installs both packages in
   rem editable mode with test and documentation tools, checks the command.
   rem Messages are in English: cmd prints UTF-8 Cyrillic as garbage (codepage 866).
   setlocal
   pushd "%~dp0"
   set "PY="
   py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1 && set "PY=py -3"
   if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1 && set "PY=python"
   if not defined PY (
       echo Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ and run setup.bat again.
       goto fail
   )
   if not exist ".venv\Scripts\python.exe" (
       echo Creating .venv with %PY% ...
       %PY% -m venv .venv || goto fail
   )
   echo Installing radial-blackoil and gpn-multiphase-solver[dev] ...
   ".venv\Scripts\python.exe" -m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]" || goto fail
   ".venv\Scripts\python.exe" -m gpn_multiphase_solver run --help >nul || goto fail
   echo Done. Run: .venv\Scripts\python -m gpn_multiphase_solver run path\to\config.json
   popd
   exit /b 0
   :fail
   echo Setup failed.
   popd
   exit /b 1
   ```
   Проверить вручную: запуск из другого каталога не меняет текущий каталог вызывающей консоли; повторный запуск доустанавливает в существующую `.venv`. В **worktree** не запускать без копии: создаст `.venv` в worktree — запуск только в копии среза (шаг 13 делает это сам).
2. `numerical_solver/.gitattributes` (К16):
   ```
   # Пакетные файлы cmd — с CRLF при любой настройке core.autocrlf, и в срезе
   # (git archive применяет атрибуты): переход goto по метке в LF-файле cmd
   # исполняет ненадёжно (FEAT-031)
   *.bat text eol=crlf
   ```
   Индекс хранит LF (`git ls-files --eol` у `run.bat` прототипа: `i/lf w/crlf`) — перенормализация не нужна; проверить `git archive HEAD:numerical_solver setup.bat` → в файле есть байты CR.
3. `tests/test_setup_bat.py`: файл есть; только ASCII; содержит команду `pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"`, та же строка (с `.venv\Scripts\python -m`) есть в README §1 (после шага 12 — тест падает до него: в шаге 10 проверять только `setup.bat`, сверку с README добавить в шаге 12); каталог прототипа существует; проверка версии `(3, 10)` совпадает с `requires-python` `pyproject.toml`; в `.gitattributes` есть `*.bat text eol=crlf`.

**Проверка:** `pytest tests/test_setup_bat.py -q`. Регресс: быстрый.
**Подводные камни:** К13, К16.
**Оценка:** ~65 строк, 40 мин.

### Шаг 11: скрипт приёмки

**Цель:** решение 50, П2 — приёмка, которую повторяет заказчик.
**Файлы:** `numerical_solver/tools/acceptance.py` (новый), `numerical_solver/tests/test_acceptance_script.py` (новый).

**Что сделать:**
1. `tools/acceptance.py` — только стандартная библиотека; запуск — любым Python ≥ 3.10 из любого каталога: `py -3 tools\acceptance.py`. Корень — `Path(__file__).resolve().parents[1]`; рабочий каталог — `<корень>.parent / f"{<корень>.name}-acceptance"` (посторонний каталог рядом со срезом; удаляется и создаётся заново). Вывод — строки «ОК»/«ОШИБКА» (как проба `vault/issues/feat-030/probes/clean_env_command.py`), итог — «ПРИЁМКА: ПРОЙДЕНА» / «ПРИЁМКА: НЕ ПРОЙДЕНА — N», код 0/1. Порядок:
   1. `.venv` в корне нет — иначе отказ: «приёмка — на свежей копии: распакуйте архив заново».
   2. `cmd /c setup.bat` → код 0 (окружение без `VIRTUAL_ENV`).
   3. Версии: `.venv\Scripts\python -m gpn_multiphase_solver --version` = `gpn-multiphase-solver <литерал __version__ корня>`; `radial_blackoil.__version__` = требование `radial-blackoil==…` из `pyproject.toml`.
   4. Тесты: `.venv\Scripts\python -m pytest tests -q -rs -p no:cacheprovider` (cwd — корень) → код 0; строки `SKIPPED [n] …: причина` — каждая причина содержит одну из `ALLOWED_SKIPS`: «нет vault/knowledge/», «черновик руководителя вне git», «нет problem_statement.aux», «could not import 'tomllib'» (Python 3.10). Печать: passed, skipped по причинам, время.
   5. Документация: `python -m sphinx -W -b html -q -d <раб>/doctrees doc/source <раб>/html` → код 0, `index.html` есть.
   6. Книга из постороннего каталога: `gpn-solver.exe template <раб>\book\case.xlsx` → код 0; `gpn-solver.exe run case.xlsx` (cwd `<раб>\book`) → код 0; в `output/` есть `REQUIRED_OUTPUT` (`well_history.csv`, `profiles.csv`, `versions.txt`, `pressure_profiles.png`, `temperature_profiles.png`, `saturation_profiles.png`, `rs_profiles.png`, `well_rates.png`, `wellbore_dynamics.png`, `relperm.png`, `pvt.png`, `energy_balance.png`, `mass_balance.png`, `input/config.json`); `versions.txt`: `gpn-multiphase-solver` и `radial-blackoil` — как в п. 3, `Python`, `numpy`, `scipy` — как у `.venv` (сверить с `python -c "import platform, numpy, scipy; …"`).
   7. Конфиг из постороннего каталога: скопировать `examples/06_table_corey_rp/config.json` и `*.csv` в `<раб>\case06`; `python -I -m gpn_multiphase_solver run case06\config.json` (cwd `<раб>`) → код 0, `REQUIRED_OUTPUT` без `input/config.json`.
   Чистые функции — отдельно, для тестов: `parse_skips(stdout) -> list[tuple[int, str]]`, `disallowed_skips(skips, allowed) -> list[str]`, `missing_outputs(directory, required) -> list[str]`, `read_versions(path) -> dict[str, str]`.
2. `tests/test_acceptance_script.py` — модуль из `tools/acceptance.py` через `spec_from_file_location`; тесты чистых функций на строках вывода pytest (образец — строки §1.1) и на `tmp_path`; `ALLOWED_SKIPS` содержит дословно причины пропусков `test_eq_references.py:80`, `test_xlsx_reader.py:476`, `test_docs.py::test_eq_numbers_match_aux` (сверка с исходниками тестов — так причина не разойдётся молча).

**Проверка:** `pytest tests/test_acceptance_script.py -q`. Запуск целиком — шаг 13. Регресс: быстрый.
**Оценка:** ~250 строк, 1.5 ч.

### Шаг 12: README и документы среза

**Цель:** README — основной документ для инженера и разработчика (решения 22, 33, 34, 48); ссылки на vault — убрать (решение 27).
**Файлы:** `numerical_solver/README.md`, `numerical_solver/examples/13a_pwf_ramp_down/README.md`, `numerical_solver/examples/14_high_gor_cooling/README.md`, `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md`, `numerical_solver/tests/test_setup_bat.py`.

**Что сделать (строки README — на `887c5ca`; после DEBT-082 искать по тексту):**
1. «Состав каталога» (15–25): строки `setup.bat` — установка для разработки (Windows); `tools/` — `acceptance.py` (приёмочная проверка копии), `eq_numbers.py` (таблица номеров уравнений для HTML); `doc/` — «постановка задачи (LaTeX) и исходники HTML-документации (`doc/source/`)».
2. Новый раздел **«Ограничения»** после «Состав каталога» — свойства функционала (решение 34), каждое сверить с постановкой и кодом:
   - одномерная осесимметричная задача: горизонтальный однородный пласт постоянной толщины, вертикальная скважина (`ssec:domain`);
   - две фазы — нефть с растворённым газом и свободный газ; воды нет; испарение нефтяного компонента в газ не учитывается;
   - фазовое равновесие мгновенное — кинетика разгазирования не учитывается;
   - капиллярное давление не учитывается ($p_o = p_g$); силы тяжести нет (пласт горизонтальный, величины осреднены по толщине);
   - теплообмен с кровлей и подошвой не учитывается;
   - гидродинамика от температуры не зависит: PVT в балансах масс — при пластовой температуре (`ssec:T_independent`); температура — только в уравнении энергии;
   - теплоёмкости, коэффициенты Джоуля–Томсона и теплота разгазирования — постоянные из конфигурации (проверить `pvt/standing.py:181-194`, `pvt/table_full.py:43-47`);
   - на контуре питания — постоянные $p_0$, $T_0$, $R_{s,0}$, приток однофазный; начальное состояние однородное, нефть недонасыщенная;
   - скин ≥ 0 и учитывается только в гидродинамике: в уравнении энергии его нет, при $s > 0$ — предупреждение (проверить текст предупреждения в `load_config`);
   - скважина только добывающая: заданное забойное давление или дебит нефти с нижним пределом давления; останов — дебит 0. Отрицательный дебит конфиг отвергает (`io/config.py`, `q_oil >= 0`); забойное давление выше давления у забоя не отвергается — прототип останавливает скважину (дебит 0), нагнетания нет (`radial_blackoil/blackoil.py:217-247`, К17);
   - погрешность по времени не контролируется: шаг задаёт пользователь (`dt_integration`, интервалы истории, нарастающий шаг после смены режима);
   - `setup.bat` — только Windows; EMF — только при установленном Inkscape.
3. §1 (41–55): первым способом — `setup.bat` (текст по §0.4: что делает, Python не ставит, нужен PyPI, после переноса каталога — заново); строка 49: «Вариант `[dev]` дополнительно устанавливает pytest и Sphinx (сборка документации, §7)». Подраздел «Из выпуска» — без изменений (решение 48).
4. §3.1, строка 237: «рекомендуемое значение — 2» → «`null` — выключено; в примерах останова 16 и 17 — 0,11 с (README примера 16: газосодержание у забоя после останова задают первые доли секунды)». Строка 238 (`skin`): «скин-фактор скважины (≥ 0); учитывается только в гидродинамике — в уравнении энергии его нет, при значении больше нуля выводится предупреждение».
5. §3.4, строка 331: «задать `time.dt_after_control_change` = 2» → «задать `time.dt_after_control_change` (в примерах останова 16 и 17 — 0,11 с)».
6. §6 (503–518): строка о тесте сборки документации (`tests/test_docs.py`, метка `slow`); абзац о приёмке: `py -3 tools\acceptance.py` на свежей копии (~15 мин, нужен PyPI): `setup.bat` → все тесты → документация без предупреждений → расчёт по книге и по конфигу из постороннего каталога.
7. §7 (520–526): первым пунктом — HTML-документация:
   ```powershell
   .venv\Scripts\python -m sphinx -W -b html doc/source doc/build/html
   ```
   «Главный файл — `doc/build/html/index.html`: этот README, техническое описание пакета и его публичный интерфейс. В архиве передачи документация и PDF постановки (`doc/problem_statement.pdf`) уже собраны. После правки `problem_statement.tex` обновить таблицу номеров уравнений: `tools/eq_numbers.py`.» `doc/build/html/index.html` и `doc/problem_statement.pdf` — моноширинным шрифтом, **не ссылками**: в git их нет, `test_readme_links_exist` упал бы.
8. README 13a (строка 214), README 14 (строка 254): упоминание пробы в `vault/issues/…` — убрать, смысл фразы сохранить (как получен конфиг: «конфиг собран скриптом из заготовки» — без пути).
9. `CHANGELOG_1.0.3.md`: в 21 строке «- Issue: <url>; plan: `vault/plans/…` of the GPN project.» убрать часть `; plan: …` (решение 27 — только ссылки vault; URL issue остаются). Перед первым разделом «## Local changes — GPN project (BUG-014)» (строка 45) — раздел версий:
   ```markdown
   ## GPN distribution versions
   - `1.0.3+gpn.1` — the local changes up to and including DEBT-059 below (GPN commit 29a1ffa).
   - `1.0.3+gpn.2` — GPN solver release 1.0.0 (2026-10-18): adds DEBT-048, DEBT-054, BUG-025, DEBT-055, BUG-028, DEBT-027, DEBT-069, DEBT-067, DEBT-071.
   - "The distribution version stays ..." in a section is the version at the time of that change. N of `+gpn.N` is raised at a solver release when this package changed.
   ```
   Перечень сверен при планировании: `git show 29a1ffa:numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` кончается разделом DEBT-059; девять разделов после него — в файле на `v1.0.0`. Перед правкой убедиться, что `git diff v1.0.0 HEAD -- numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` пуст (иначе добавились разделы — они идут в `gpn.3`, не в этот перечень).
10. `tests/test_setup_bat.py` — добавить сверку команды `setup.bat` с README §1 (шаг 10, п. 2).

**Проверка:** `pytest tests/test_docs.py tests/test_setup_bat.py tests/test_eq_references.py -q`; `-W`-сборка — 0 предупреждений; `git grep -n "vault/" -- "numerical_solver/*.md" "numerical_solver/**/*.md"` — пусто. Регресс: быстрый.
**Оценка:** ~150 строк текста, 1.5 ч.

### Шаг 13: скрипт передачи; приёмка на срезе ветки

**Цель:** П1 — одна команда: срез из метки → PDF и HTML → архив → приёмка на распакованном архиве.
**Файлы:** `tools/handover.py` (новый, корень репозитория).

**Что сделать:**
1. `tools/handover.py`:
   ```python
   """Передача команде разработки заказчика: python tools/handover.py <метка> (FEAT-031).

   Срез numerical_solver из метки выпуска (git archive — только файлы под git),
   PDF постановки, HTML-документация, архив gpn-multiphase-solver-<версия>.zip
   и приёмка на его распакованной копии. Git не меняется: ни коммитов, ни
   меток, ни push. Запуск — из корня репозитория, интерпретатором venv решателя
   (нужен Sphinx — группа [dev]); нужны pdflatex в PATH и доступ к PyPI
   (приёмка ставит пакеты в свежее окружение):

       numerical_solver\\.venv\\Scripts\\python tools\\handover.py v1.0.1

   Выход — dist/handover-<версия>/. Метка не вида vX.Y.Z или номер с .dev —
   предупреждение: заказчику передаётся только выпуск (метка tools/release.py).
   """
   ```
   Порядок:
   1. `git rev-parse --verify <метка>^{commit}`; версия — литерал `__version__` из `git show <метка>:numerical_solver/gpn_multiphase_solver/__init__.py` (`release.VERSION_RE`).
   2. `out = ROOT / "dist" / f"handover-{версия}"` — удалить, если есть; `tree = release.extract(<метка>, out / "src")` (импорт `release` из той же папки); перенести в `out / f"gpn-multiphase-solver-{версия}"`.
   3. PDF: `pdflatex -interaction=nonstopmode -halt-on-error problem_statement.tex` два раза (cwd `doc/`); код 0 и `problem_statement.pdf` есть.
   4. `python tools/eq_numbers.py --check` в срезе → код 0, иначе отказ «таблица номеров устарела: обновите doc/source/eq_numbers.json и закоммитьте до выпуска».
   5. Удалить побочные файлы LaTeX (`problem_statement.*`, кроме `.tex` и `.pdf`).
   6. HTML: `sys.executable -m sphinx -W -b html -q -d out/doctrees doc/source doc/build/html` в срезе, `PYTHONDONTWRITEBYTECODE=1` (К14); `index.html` есть.
   7. Архив `out / f"gpn-multiphase-solver-{версия}.zip"` с верхним каталогом `gpn-multiphase-solver-{версия}/`.
   8. Приёмка: распаковать архив в `out / "check"`; `sys.executable check/…/tools/acceptance.py` (окружение без `VIRTUAL_ENV`) → код 0.
   9. Итог: путь архива, размер, SHA256, итог приёмки; предупреждение, если метка — не выпуск.
   Коды: 0 — архив готов и приёмка пройдена; 1 — отказ (каталог `out` остаётся для разбора).
2. Прогон в worktree на ветке: `..\..\numerical_solver\.venv\Scripts\python tools\handover.py HEAD` из корня worktree (К9: всё закоммичено) — ожидаются предупреждение «не выпуск» (номер `1.0.1.dev0`) и «ПРИЁМКА: ПРОЙДЕНА». Записать: число файлов архива, размер, время, итог pytest в срезе (passed / skipped по причинам), предупреждения сборки — 0.

**Проверка:** прогон п. 2 — код 0. Регресс: быстрый (скрипт вне `numerical_solver/`).
**Подводные камни:** К9, К10, К14.
**Оценка:** ~180 строк, 1.5 ч + ~15 мин прогона.

### Шаг 14: `CLAUDE.md` и vault

**Файлы:** `CLAUDE.md`; vault — по `/implement`.

**Что сделать:**
1. `CLAUDE.md`, «Структура проекта»: строка `tools/handover.py` — «Передача заказчику: срез из метки выпуска, PDF постановки, HTML-документация, архив, приёмка на распакованной копии (FEAT-031)».
2. `CLAUDE.md`, раздел `numerical_solver`: документация — `python -m sphinx -W -b html doc/source doc/build/html` (из `numerical_solver/`), главный файл `doc/build/html/index.html`; перечень публичного интерфейса — `doc/source/api.rst`, правило докстрингов проверяет `tests/test_docs.py`; после правки `problem_statement.tex` — `tools/eq_numbers.py`; приёмка среза — `tools/acceptance.py`.
3. Правило «Docstring публичного интерфейса» (CLAUDE.md, «Файлы и код»): «Публичный интерфейс — имена из `tests/test_public_api.py` и README §4» → «Публичный интерфейс — объекты `doc/source/api.rst` (README §4, `tests/test_public_api.py`, функции, которые вызывают примеры, абстрактные классы расширения)».
4. Реестр FEAT-031, поле «Модуль»: там перечислены `VERSION.txt`, `PACKAGE_MANIFEST_SHA256.txt` и `radial_blackoil/__init__.py` прототипа — план их не меняет (§0.4: номер поднял выпуск FEAT-038, манифест и `VERSION.txt` — запись поставки 2026-08-25). Привести поле к фактическому составу.
5. Vault (`/implement`): заметка-решение `vault/knowledge/decisions/передача заказчику — срез метки выпуска с документацией Sphinx и приёмкой на распакованной копии.md` (что передаётся, чем собирается, что проверяет приёмка, почему эталон не хранится); реестр FEAT-031; `index.md`.

**Проверка:** `--collect-only -q`. Итоговый полный прогон — `/implement` §3.1.

## 4. Тестовая стратегия

| Тест | Файл | Что ловит |
|---|---|---|
| `test_eq_numbers_cover_tex_labels` | `tests/test_docs.py` | новая или удалённая метка постановки без пересборки таблицы |
| `test_eq_numbers_match_aux` | там же | номера таблицы разошлись со свежим `.aux` (пропуск без `.aux`) |
| `test_api_objects_importable` | там же | переименованный или удалённый объект перечня |
| `test_api_covers_required_names` | там же | функция, которую вызывает пример или README §4, не документирована |
| `test_readme_links_exist` | там же | ссылка README на переименованный файл (возмещает `suppress_warnings`) |
| `test_public_docstring[…]` (~120) | там же | правило NumPy: разделы, параметры = сигнатура, поля dataclass, без ID и `vault/`, заголовки модулей объявлены |
| `test_version_literal_unique` | там же | строка `__version__ =` в докстринге пакета сорвала бы `tools/release.py` (К1) |
| `test_docs_build_without_warnings` (`slow`) | там же | любое предупреждение сборки (`-W`) |
| `test_setup_bat_*` | `tests/test_setup_bat.py` | не-ASCII, расхождение команды с README, путь прототипа, граница версии Python |
| `test_*` чистых функций приёмки | `tests/test_acceptance_script.py` | разбор пропусков pytest, белый список = причины в тестах, набор файлов вывода |
| `TestCaseC_MeshConvergence` | `tests/test_val002.py` | прежние проверки; без `PytestRemovedIn10Warning` |
| приёмка на срезе | `tools/handover.py HEAD` (шаг 13) | срез без забытых файлов, установка `setup.bat`, полный прогон в свежем окружении, документация, расчёт из постороннего каталога |

Категории шаблона (аналитика, предельные случаи, сходимость, инварианты) к задаче неприменимы: вычисления не меняются; регрессия — все существующие тесты без изменений. Ожидаемое число тестов: 2461 → ≈ 2600 (≈ +140; точно — по факту, большая часть — параметризация `test_public_docstring`).

## 5. Критерии завершения

- [ ] `pyproject.toml`: `sphinx`, `myst-parser` в `[dev]`; `description` точный; комментарий о приёмке — на `tools/acceptance.py`.
- [ ] `doc/source/` под git; `-W`-сборка — 0 предупреждений; в HTML нет меток `eq:`.
- [ ] Все объекты `api.rst` — докстринги NumPy с русскими заголовками и единицами; `PENDING` удалён.
- [ ] Техническое описание — докстринги пакета и 7 подпакетов + `units`.
- [ ] README: «Ограничения», `setup.bat`, сборка HTML и `index.html`, приёмка, 0.11 с вместо 2 с, оговорка о скине; ссылок на `vault/` в передаваемых `.md` нет.
- [ ] `setup.bat`, `tools/acceptance.py`, `tools/eq_numbers.py`, `tools/handover.py`.
- [ ] `tools/handover.py HEAD` в worktree — «ПРИЁМКА: ПРОЙДЕНА».
- [ ] Быстрый уровень после каждого шага, полный прогон в конце — зелёные.
- [ ] Прототип не менялся (`git diff --stat <база> -- numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil` пуст).
- [ ] `CLAUDE.md`, vault, комментарий в #114.

Не критерий FEAT-031 (§6): выпуск поставки и передача архива — после влития, по команде пользователя.

## 6. После влития — передача

1. Раздел «Не выпущено» журнала `numerical_solver/CHANGELOG.md` — сводка изменений после 1.0.0 (Claude по просьбе, по `git log v1.0.0..`): документация, `setup.bat`, приёмка, исправления после 1.0.0.
2. `numerical_solver\.venv\Scripts\python tools\release.py 1.0.1` (FEAT-038; номер — П8, не важен по решению 45).
3. `numerical_solver\.venv\Scripts\python tools\handover.py v1.0.1` → `dist/handover-1.0.1/gpn-multiphase-solver-1.0.1.zip`, «ПРИЁМКА: ПРОЙДЕНА».
4. Архив — команде разработки заказчика (решение пользователя: когда и каким способом); SHA256 — из вывода скрипта.

Если после выпуска поставки появятся изменения, которые заказчик должен получить, — новый выпуск и новый архив (решение 45: финальная версия со всеми изменениями).

## 7. Связь с другими задачами

- [[FEAT-038]] — `tools/release.py`: `extract()` переиспользуется; выпуск поставки — его командой.
- [[FEAT-037]] — `__version__`, `CHANGELOG.md`, `versions.txt` (проверяется приёмкой).
- [[DEBT-082]] — в работе; README §3.4/§3.6 могут измениться до реализации.
- [[BUG-026]], [[BUG-029]] — тексты README (0.11 с, скин).
- [[DEBT-080]] — пример устаревшей заметки: документация пишется по коду.
- [[DEBT-059]] — манифест прототипа — запись поставки 2026-08-25, не обновляется.

## 8. Верификация плана

**Раунд 1 — полнота.** Формул нет (2.1). Каждому новому файлу — тест или проверка шага (§4). Зависимости шагов: 1 → 2 → 3 → 4 → 5…8 (независимы между собой) → 9 → 10 → 11 → 12 → 13 → 14; циклов нет. Подводные камни К1–К14 привязаны к шагам. Обратная совместимость — 2.2.

**Аудит 1 (2026-10-18, база `887c5ca`).** Исполнено: сборка документации ровно по `conf.py`/`api.rst` шага 3 (`audit_plan_docs.py`), `setup.bat` шага 10 в копии среза, обе формы фикстуры шага 1 на pytest 7.4 и 9.1, `git archive` и концы строк `.bat`, ссылки README, `.aux` против свежего. Исправлено: номера строк README после `ee36397`; порядок с DEBT-082; К1 (AST-тест литерал в докстринге не видит → новый тест); К15–К17; правила стража (собственный `__doc__`, `a, b : тип`, собственный `__init__`); PDF и `index.html` в README — не ссылками; поле «Модуль» реестра.

**Раунд 2 — корректность.** Проверено grep/чтением на `024e19a` (номера README — пересняты на `887c5ca`): существуют `tools/release.py` (`extract`, `VERSION_RE`, `ROOT`), `tests/test_public_api.py`, `tests/test_eq_references.py` (`VAULT`, пропуск строки 80), `tests/test_xlsx_reader.py:476`, `tests/test_val002.py:455,474`, все 31 функция и 35 классов перечня (проба их импортировала), строки README 15–25, 41–55, 178, 179, 272, 444–467, `CHANGELOG_1.0.3.md:45`, README 13a:214, 14:254, `pyproject.toml:10,29-32,56-57`. Подписи HTML, замена меток, предупреждения README — замерены пробой (§1.2). Правило докстрингов — CLAUDE.md «Файлы и код».

**Раунд 3 — автономность.** Шаги содержат полные пути, тексты `conf.py`, `setup.bat`, `eq_numbers.py`, каркасы скриптов, образцы докстрингов, тексты README; «Как начать» — с командами; baseline — 2461 / 2177.

## Приложение А. Вопросы черновика 2026-10-17 (история обсуждения)

Ответы — §0.3а (решения 24–37), §0.3д (48–51). Тексты вопросов — в последней закоммиченной версии черновика (`git show 2a0d6c7:"vault/plans/feat-031 customer-delivery-kit.md"`, §7), там же черновое оглавление документации (§2) и набросок порядка работ (§8).
