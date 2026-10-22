---
tags:
  - план
  - инфраструктура
date: 2026-10-18
issue: FEAT-038
github: 137
branch: feat/feat-038/team-releases-script
model_level: null
status: реализован
worktree: .worktrees/feat-038; удалён после влития
merged: 225985e (2026-10-18)
audit:
  date: 2026-10-18
  found: 9
  auto-fixed: 9
  manual-required: 0
---

# FEAT-038: выпуски для испытаний внутри команды — `python tools/release.py X.Y.Z`

**Issue:** [#137](https://github.com/ArturSalamatin/Oil_Gas/issues/137) · **Ветка:** `feat/feat-038/team-releases-script` (от `numerical_scheme/implementation`) · **База плана:** `46925a1` — после влития FEAT-036 (`c156604`); 2461 тест решателя, 109 — прототипа (план написан на `83a5838`, сверен с новой базой на аудите 1) · **Подтип:** инфраструктура, формул нет.

Цепочка: [[feat-037 solver-version-changelog|FEAT-037]] (номер `__version__`, `CHANGELOG.md`, `gpn-solver --version`, `output/versions.txt`; влит `5ea30e7`) → **FEAT-038** → первый выпуск `1.0.0` сразу после влития. [[DEBT-059]] — прототип как дистрибутив `radial-blackoil`, база `29a1ffa`. [[FEAT-031]] (поставка заказчику) от FEAT-038 не зависит.

## 0. Суть

Испытатель (возможно, только автор, в другом каталоге) пользуется библиотекой только как установленным пакетом и получает регулярные выпуски. Выпуск — в Releases самого `Oil_Gas` (личный закрытый репозиторий): `gpn_multiphase_solver-X.Y.Z-py3-none-any.whl`, `radial_blackoil-1.0.3+gpn.N-py3-none-any.whl`, `examples-vX.Y.Z.zip`. Вручную — только текст раздела «Не выпущено» журнала; всё остальное делает одна команда `numerical_solver\.venv\Scripts\python tools\release.py X.Y.Z`.

Что делает реализация:
1. `tools/release.py` (новый, корень репозитория) — копия кода плана `vault/issues/feat-038/probes/plan_code/release.py` (450 строк, sha256 `7585fcfa7d852977…` — после аудита 1).
2. Комментарии с буквальным «+gpn.1» / «set 1» → «+gpn.N» (`numerical_solver/pyproject.toml`, `radial_blackoil/__init__.py`).
3. Номер прототипа в трёх README → ссылка на литерал; в README пакета — установка из выпуска.
4. `CLAUDE.md` — тип коммита `release`, строка `tools/release.py`, исключение в «Коммиты».

Новых тестов нет (решение пользователя 2026-10-18 — исключение из правила CLAUDE.md «новый код — с тестами»). Проверка: самопроверка внутри скрипта, проба функций `vault/issues/feat-038/probes/plan_check.py` (репозиторий не меняет) и первый выпуск, установленный в другом каталоге.

## 1. Решения пользователя

Из записи реестра (2026-10-18):
1. Выпуски — в Releases самого `Oil_Gas`; отдельный репозиторий, приглашения, проверка в чистом окружении внутри скрипта, подкоманды, команда `/release`, `RELEASING.md` — отменены. Порядок выпуска — в докстринге скрипта.
2. Номера меняет скрипт; вручную — только содержание «Не выпущено» (черновик по `git log` от прошлой метки сводит Claude по просьбе).
3. Номер прототипа в README → ссылка на файл, где он хранится (`radial_blackoil/__init__.py`); скрипт README не правит. `CHANGELOG_1.0.3.md` не трогается.
4. Тип коммитов скрипта — новый `release` в списке CLAUDE.md; тесты скрипта не пишутся.
5. Первый выпуск — сразу после влития FEAT-038: `1.0.0`, прототип `+gpn.2`. Опубликованный выпуск не меняется; исправление — новый выпуск.

При планировании (2026-10-18):

6. **Один push в конце, откат автоматический.** Коммит выпуска и метка — локально → сборка из метки и самопроверка → коммит `.dev0` → один `git push --atomic` ветки и метки → `gh release create`. Отказ до push — скрипт сам откатывает: `git tag -d`, `git reset --keep` к исходному коммиту (не `--hard`: незакоммиченные файлы vault остаются). Отказ `gh` после push — печатается одна команда для повтора. Причина: в записи реестра push стоял до сборки — отказ самопроверки оставил бы на `origin` метку без выпуска, а номер нельзя было бы использовать повторно.
7. **Пример 18 в архив не входит.** `examples/18_prototype_input/prototype_input.py` и `main.py` читают `HydroSolverPrototype/Prototype_1.0.3/INPUT_TEMPLATE.xlsx`, `regression/inputs/T07.xlsx`, `regression/reference_imex_normalized/` — в архиве и в колесе их нет. README примеров по-прежнему упоминает пример 18; в заметках выпуска — одна строка об этом.
8. **Знак `+` в имени файла выпуска — проверен на черновике** (2026-10-18): черновик с файлом `probe-1.0.3+gpn.2-py3-none-any.whl` — имя сохранено (`gh release view --json assets`: `name` = `probe-1.0.3+gpn.2-py3-none-any.whl`, в URL — `%2B`), `gh release download` сохраняет его так же. Черновик удалён, метки он не создавал (`--cleanup-tag` → 422 «Reference does not exist»), выпусков в репозитории 0. Обходной вариант не нужен.
9. **Репетиции всей процедуры на клоне нет** — только самопроверка и первый выпуск. Проба плана `plan_check.py` проверяет функции скрипта на копии дерева HEAD в `dist/` и откат — на учебном репозитории; `main()` целиком, push и `gh release create` она не выполняет.

## 2. Умолчания плана (пользователь может изменить на аудите)

10. Скрипт — в `tools/release.py` корня (каталога `tools/` нет), запуск интерпретатором `numerical_solver\.venv` (нужны `packaging`, `pytest`; без `packaging` — понятный отказ при импорте).
11. Выпуск — только из основного каталога на `numerical_scheme/implementation`: в worktree эту ветку не переключить, проверка ветки отказывает.
12. Проверка «нет правок» — только отслеживаемые файлы `numerical_solver/` (`git status --porcelain --untracked-files=no -- numerical_solver`): сейчас там лежат неотслеживаемые `configs/INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx` и `deliverables/`, в сборку из метки они не попадают.
13. Коммиты скрипта — по именам четырёх файлов (`git commit -- <файлы>`), не `-a`: другие индексированные и изменённые файлы (vault) в коммит не попадают.
14. Ветка не позади `origin` (`git fetch` + `rev-list HEAD..origin/…`); впереди — допустимо: push уносит и прежние локальные коммиты базы (сказано в докстринге).
15. «Прототип изменился» — `git diff --quiet <база> HEAD -- radial_blackoil/ pyproject.toml` прототипа (всё, из чего собирается колесо); база — последняя метка `v*` по PEP 440, у первого выпуска `29a1ffa`.
16. Номер `X.Y.Z` — ровно три числа, каноническая форма PEP 440 (`01.0.0`, `1.0`, `1.0.0rc1`, `1.0.0.dev1` — отказ), больше текущего `__version__` и прошлого выпуска.
17. «Не выпущено» не пуст — в разделе есть строка, начинающаяся с `- `.
18. Заголовок раздела выпуска — `## X.Y.Z — ГГГГ-ММ-ДД` (как в журнале и в `test_changelog_has_section_for_version`); над ним при `.dev0` — пустой `## Не выпущено`.
19. Метка аннотированная: `git tag -a vX.Y.Z -m "Выпуск X.Y.Z"`.
20. Сборка — в `dist/vX.Y.Z/` корня (`dist/` в `.gitignore`, строка 31; не временный каталог — CLAUDE.md, «Файлы и код»): `src/` (дерево `numerical_solver` метки через `git archive`), `examples-vX.Y.Z.zip`, `notes.md`, `wheels/`. Остаток прошлой попытки с тем же номером удаляется. Каталог остаётся после выпуска.
21. Самопроверка — `tests/test_packaging.py` дерева метки (11 тестов) после правки номеров и рабочего каталога после `.dev0`; пропуск теста считается отказом (на Python 3.10 тесты `pyproject.toml` пропускаются — нет `tomllib`).
22. Заметки выпуска — раздел журнала + строка «Архив примеров — без примера 18 (`18_prototype_input`): ему нужны книги и эталон CMG IMEX из дерева прототипа.»; заголовок выпуска — `X.Y.Z`; `gh release create … --verify-tag`.
23. Файлы скрипт читает и пишет байтами: в рабочем дереве CRLF (`core.autocrlf=true`, `git ls-files --eol`: `i/lf w/crlf`), окончания строк сохраняются.
24. В `CLAUDE.md`, кроме типа `release` и строки `tools/`, — строка-исключение в «Коммиты»: скрипт коммитит и делает push базовой ветки; запускает пользователь или Claude по прямой просьбе, `/implement` его не запускает.
25. README пакета §1 — абзац «Из выпуска» (команды для PowerShell). Оставлять ли его в поставке заказчику — решает [[FEAT-031]] (в абзаце — имя закрытого репозитория).
26. Комментарий прототипа `radial_blackoil/__init__.py` (строки 1–6) переписывается без «set 1» — это правка файла `radial_blackoil/` (только комментарий; AST не меняется — проверка в шаге 2). На номер первого выпуска не влияет: прототип менялся с `29a1ffa` и без неё (13 коммитов).
27. *(аудит 1)* `preflight` проверяет и выпуск с тем же именем на GitHub: `gh release view vX.Y.Z --repo …` с кодом 0 — отказ. У черновика выпуска метки нет, проверка меток его не видит, а `gh release create` отказал бы уже после push — единственного шага без отката. Все проверяемые заранее условия шага 6 (авторизация `gh`, свободное имя выпуска) — в шаге 1.
28. *(аудит 1)* В начале `main` — `sys.stdout.reconfigure(errors="replace")` (и `stderr`): при выводе в канал или файл без `PYTHONIOENCODING` Python пишет в cp1251, а `«→»` в печати скрипта и в докстринге там не кодируется. Проверено: `print('→')` в канал без переменной — `UnicodeEncodeError`, код 1; в сессии Claude задана `PYTHONIOENCODING=utf-8`, поэтому проба плана этого не видела. Тот же приём — `_print_safe` в `examples/run_all.py`.

## 3. Контекст

### 3.1. Что уже есть (FEAT-037, DEBT-059)

| Что | Где | Значение на `46925a1` |
|---|---|---|
| номер решателя | `numerical_solver/gpn_multiphase_solver/__init__.py:8` | `__version__ = "1.0.0.dev0"` |
| номер прототипа | `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/__init__.py:7` | `__version__='1.0.3+gpn.1'` (одинарные кавычки, без пробелов) |
| требование решателя | `numerical_solver/pyproject.toml:25` | `"radial-blackoil==1.0.3+gpn.1",`; комментарий над ним (строка 22) — «+gpn.1» буквально |
| журнал | `numerical_solver/CHANGELOG.md:35` | `## Не выпущено` → `### Добавлено`, три пункта FEAT-037 и пункт FEAT-036 (расчёт по книге) |
| сторожа | `numerical_solver/tests/test_packaging.py` | 11 тестов, в т.ч. `test_gpn_pins_prototype_version` (требование = литерал прототипа), `test_solver_version_literal_follows_rule` (три числа, PEP 440), `test_changelog_has_section_for_version` (`.devN` → «Не выпущено»; выпуск → `## X.Y.Z( |$)`) |
| версия из литерала | оба `pyproject.toml` | `dynamic = ["version"]`, `{attr = "…__version__"}` |
| метки, выпуски | `git tag --list`, `gh release list` | нет |
| setuptools в venv | `pip list` | нет — изолированная сборка скачивает `setuptools>=68` (нужен PyPI или кеш pip) |

Внутри пакетов `gpn_multiphase_solver/` и `radial_blackoil/` отслеживаются только `.py` — данных пакета, которые колесо могло бы потерять, нет.

### 3.2. Что проверено при планировании

Проба `vault/issues/feat-038/probes/plan_check.py` — на `83a5838` 54 ОК; после правок аудита 1 на `46925a1` — **55 ОК, 0 ошибок** (вывод `plan_check.out.txt`, ~65 с):
- чистые функции: литералы, `next_gpn`, `next_dev`, отказы номера (7 случаев), `released_versions() == []`, `prototype_changed("29a1ffa") = True`, `prototype_changed("HEAD") = False`; журнал выпуска и `.dev0` — CRLF сохранены (44 → 44 → 46);
- `preflight("1.0.0")` на настоящем репозитории (только чтение; `gh auth status`, `git fetch`) → `{current: 1.0.0.dev0, base: 29a1ffa, proto_old: 1.0.3+gpn.1, proto_new: 1.0.3+gpn.2}`; `preflight("1.0.0.dev0")` — отказ; HEAD и метки не изменились;
- сборка из `git archive HEAD`: архив — 124 файла = 131 отслеживаемый − 7 примера 18 (на `46925a1`, с примером 22), все пути `examples/…`; самопроверка 11 passed до правки номеров, после правки выпуска (`1.0.0`, `+gpn.2`) и после `.dev0` (`1.0.1.dev0`); колёса `gpn_multiphase_solver-1.0.0-py3-none-any.whl` и `radial_blackoil-1.0.3+gpn.2-py3-none-any.whl`, METADATA `Version` совпадает, `Requires-Dist: radial-blackoil==1.0.3+gpn.2`, в колесе прототипа — только `radial_blackoil`; порча требования (литерал `+gpn.2`, требование `+gpn.1`) — самопроверка отказывает; колесо с другим номером — проверка имён отказывает;
- откат на учебном репозитории `dist/plan-check-feat-038/rb` (`core.autocrlf=true`): коммит выпуска содержит только четыре файла; незакоммиченная правка `.dev0` + коммит + метка → `rollback` → HEAD на старте, метки нет, четыре файла как на старте, незакоммиченная правка `vault/note.md` осталась;
- *(аудит 1)* вызов скрипта без аргумента в канал без `PYTHONIOENCODING`/`PYTHONUTF8` — код 2 (докстринг с «→» напечатан); без `reconfigure` (умолчание 28) тот же докстринг в канал — код 1.

Найдено пробой: METADATA колеса, собранного setuptools на Windows, — с CRLF (сверять по строкам). На скрипт не влияет: он проверяет имена колёс.

### 3.3. Параллельная работа

[[feat-036 run-from-workbook|FEAT-036]] влита во время планирования (`c156604`, итог `46925a1`; полный прогон 2460 passed, 1 skipped). Сверено на аудите 1: README §1 (строки 33–53) и строки CLAUDE.md, которые правит план, не изменились; абзац `examples/README.md` сдвинулся с 248–250 на 266–268 (текст тот же); пример 22 (`22_workbook_input`: книга, `main.py`, README) самодостаточен — ссылок за пределы `examples/` нет — и входит в архив; пункт FEAT-036 уже в «Не выпущено» и попадёт в первый выпуск. Открытая [[DEBT-082]] (очистка каталога вывода) правит `pipeline.py`, `cli.py`, README §3.4 — с FEAT-038 не пересекается. Правки плана привязаны к тексту, номера строк — для ориентира.

## 4. Варианты и выбор

| Вариант | Суть | Итог |
|---|---|---|
| А — как в записи реестра | коммит, метка, push → сборка → публикация | отклонён: отказ сборки после push — метка без выпуска на `origin` |
| **Б — один push после самопроверки, автооткат** | вся работа git локально; push `--atomic` ветки и метки последним перед `gh` | **выбран** (решение 6) |
| В — Б + черновик выпуска и сверка имён | `--draft`, `gh release view --json assets`, затем публикация | не нужен: `+` сохраняется (решение 8) |

## 5. Подводные камни

| Камень | Статус | Как адресован |
|---|---|---|
| сборка из рабочего каталога захватывает неотслеживаемые `.py` пакета и устаревший `build/` | ✅ | `git archive` метки → `dist/vX.Y.Z/src` |
| неотслеживаемые файлы в `numerical_solver/` блокируют выпуск | ✅ | `--untracked-files=no` (умолчание 12) |
| коммит скрипта захватывает vault | ✅ | `git commit -- <четыре файла>` (умолчание 13; проба — п. 4) |
| push отвергнут после метки (ветка позади или ушла вперёд) | ✅ | проверка «не позади» + push `--atomic` последним: при отказе ничего не уходит, откат |
| отказ после push / Ctrl+C во время push | ✅ | `push_started`: если метка на `origin` или проверить не удалось — откат не выполняется, печатается команда проверки |
| `reset --keep` откажет на незакоммиченных правках скрипта | ✅ | `rollback` сначала `git restore --source=HEAD` четырёх файлов (на старте они чистые) |
| CRLF в рабочем дереве | ✅ | чтение/запись байтами; регулярные выражения с `(?=\r?$)` (проба: CRLF сохранены) |
| `+` в имени файла выпуска | ✅ | проверено на черновике (решение 8) |
| установка по имени с `--find-links` — подмена пакетом с PyPI | ✅ | README: установка по путям файлов |
| PowerShell не раскрывает `*.whl` для pip | ✅ | README: `(Get-ChildItem …\*.whl).FullName` |
| закрытый репозиторий: скачивание только с авторизацией | ✅ | README: `gh auth login`; скрипт проверяет `gh auth status` |
| изолированная сборка требует PyPI | ⚠️ | комментарий в `build_wheels`; без сети — отказ `pip wheel`, откат |
| пример 18 не работает из архива | ✅ | исключён (решение 7), строка в заметках |
| Python 3.10 — тесты `pyproject.toml` пропускаются | ✅ | пропуск = отказ самопроверки (умолчание 21) |
| параллельная сессия вливает в базу во время выпуска | ⚠️ | предупреждение в докстринге; проверка не автоматизирована |
| `README` пакета уйдёт заказчику с именем закрытого репозитория | ⚠️ | решает FEAT-031 (умолчание 25) |
| `importlib.metadata` редактируемой установки отстаёт от литерала | ✅ | скрипт метаданные не читает; после выпуска в основном каталоге — по желанию `pip install -e …` |
| правка прототипа без регрессии | ✅ | только комментарий; шаг 2 проверяет равенство AST и гоняет тесты прототипа; регрессия не нужна |
| *(аудит 1)* вывод в канал/файл в cp1251 — `UnicodeEncodeError` на «→» посреди выпуска | ✅ | `reconfigure(errors="replace")` в `main` (умолчание 28); проба, п. 5 |
| *(аудит 1)* черновик выпуска с тем же именем — отказ `gh` после push | ✅ | `gh release view` в `preflight` (умолчание 27) |
| *(аудит 1)* `reset --keep` снимает индексирование чужих файлов | ✅ | допустимо: содержимое сохраняется, файлы остаются изменёнными, но не индексированными (таблица `--keep` в `git reset --help`: индекс → цель, рабочее дерево не трогается); отдельной обработки не нужно |
| *(аудит 1)* обновление: `Expand-Archive` в каталог, где уже лежат примеры прошлого выпуска, отказывает без `-Force` | ✅ | README: архив распаковывается в каталог своего выпуска (`release-X.Y.Z\examples\…`), шаг 3.2 |

Обратная совместимость: код пакетов не меняется; конфиги, публичный интерфейс, тесты — без изменений; число тестов 2461 и 109 остаётся.

## 6. Шаги реализации

### Шаг 1: скрипт выпуска `tools/release.py`

**Цель:** одна команда выпуска по решениям 1–9 и умолчаниям 10–23.
**Файлы:** `tools/release.py` (новый; каталога `tools/` нет).

**Что сделать:**
1. Скопировать `vault/issues/feat-038/probes/plan_code/release.py` в `tools/release.py` **побайтно** (`Copy-Item`; sha256 начинается с `7585fcfa7d852977`, 450 строк — после аудита 1; если код плана правился позже — сверить с итоговым файлом плана).
2. Ничего не менять: `ROOT = Path(__file__).resolve().parents[1]` в `tools/` — корень репозитория.

Устройство (для понимания, код — в файле плана):
- `preflight(version)` — все проверки шага 1 (и свободное имя выпуска на GitHub — умолчание 27), ничего не меняет; возвращает номера (`current`, `base`, `proto_old`, `proto_new`).
- `apply_release_edits(root, …)` / `apply_dev_edits(root, …)` — правка литералов и журнала в дереве `root` (корень репозитория или его копия — так их проверяет проба).
- `extract` → `zip_examples` → `section_body` (заметки) → `selfcheck` → `build_wheels` — шаг 3 (`build`).
- `rollback(start, tag)` — `restore` четырёх файлов → `tag -d` → `reset --keep`.
- `main` — `reconfigure(errors="replace")` потоков вывода (умолчание 28), затем порядок решения 6; коды возврата: 0 — выпуск создан, 1 — отказ, 2 — неверный вызов (печать докстринга).

**Проверка после шага** (из основного каталога, на базовой ветке; репозиторий проба не меняет):
```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas
numerical_solver\.venv\Scripts\python -X utf8 vault\issues\feat-038\probes\plan_check.py .worktrees\feat-038\tools\release.py
```
Ожидание: первая строка `Скрипт: …\.worktrees\feat-038\tools\release.py`, итог «все проверки ОК», 55 ОК. Если в основном каталоге в этот момент есть незакоммиченные правки отслеживаемых файлов `numerical_solver/` или база позади `origin` — `preflight` в пробе честно откажет; разобрать по тексту отказа, не обходить. Число файлов архива проба считает по `git ls-files` (на `46925a1` — 124).
- Регресс: `--collect-only -q` из `numerical_solver/` — 2461 (скрипт вне пакета).

**Подводные камни:** §5, все строки про скрипт. Проба `preflight` выполняет `git fetch origin numerical_scheme/implementation` — меняет только `origin/*`.
**Зависимости:** блокирует шаг 4 (CLAUDE.md ссылается на файл).
**Оценка:** копия 450 строк, ~10 мин с пробой.

### Шаг 2: комментарии с номером прототипа

**Цель:** после первого выпуска в комментариях не должно остаться буквального `+gpn.1` / «set 1».
**Файлы:** `numerical_solver/pyproject.toml`, `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/__init__.py`.

**2.1. `numerical_solver/pyproject.toml`, строки 20–23.** До:
```toml
    # дистрибутив в этом же репозитории (DEBT-059). Ровно эта версия: с нашими
    # правками прототипа совместима только она (тест test_packaging.py). Метка
    # «+gpn.1» — локальная; PyPI таких версий не принимает, поэтому чужой
    # пакет с тем же именем зависимость не удовлетворит. Ставить вместе:
```
После:
```toml
    # дистрибутив в этом же репозитории (DEBT-059). Ровно эта версия: с нашими
    # правками прототипа совместима только она (тест test_packaging.py). Метка
    # «+gpn.N» — локальная; PyPI таких версий не принимает, поэтому чужой
    # пакет с тем же именем зависимость не удовлетворит. N и это требование
    # повышает tools/release.py при выпуске (FEAT-038). Ставить вместе:
```
Строку требования `"radial-blackoil==1.0.3+gpn.1",` не трогать: её меняет скрипт (`write_proto_pin` ищет строку в кавычках ровно один раз — в комментарии её нет).

**2.2. `radial_blackoil/__init__.py`, строки 1–6.** До:
```python
# Distribution version (pip): Prototype 1.0.3 + local changes of the GPN
# project, set 1 (CHANGELOG_1.0.3.md, DEBT-059). numerical_solver/pyproject.toml
# requires radial-blackoil of exactly this version. Keep a plain literal:
# setuptools reads it without importing the package. build_info.VERSION
# ('1.0.3') is the version written to run_summary and compared by the
# regression with the golden outputs; it is unchanged.
```
После:
```python
# Distribution version (pip): Prototype 1.0.3 + local changes of the GPN
# project, set N = the number after "+gpn." (CHANGELOG_1.0.3.md, DEBT-059);
# tools/release.py raises N at a solver release if this package changed
# (FEAT-038). numerical_solver/pyproject.toml requires radial-blackoil of
# exactly this version. Keep a plain literal: setuptools reads it without
# importing the package. build_info.VERSION ('1.0.3') is the version written
# to run_summary and compared by the regression with the golden outputs; it
# is unchanged.
```
Строку `__version__='1.0.3+gpn.1'` не трогать.

**Проверка после шага** (из корня worktree, до коммита шага — сравнение с HEAD):
```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\feat-038
# AST прототипа не изменился — правка только комментария, регрессия не нужна
D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python -c "import ast,subprocess; f='numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/__init__.py'; old=subprocess.run(['git','show','HEAD:'+f],capture_output=True,text=True,encoding='utf-8').stdout; print(ast.dump(ast.parse(old))==ast.dump(ast.parse(open(f,encoding='utf-8').read())))"
```
Ожидание `True` (команда проверена при планировании на неизменённом файле). Далее из `numerical_solver/` worktree: `.venv\Scripts\python -m pytest tests/test_packaging.py -q` — 11 passed (TOML разбирается, требование = литерал); из `numerical_solver/HydroSolverPrototype/Prototype_1.0.3`: `..\..\.venv\Scripts\python -m pytest tests -q` — 109 passed.
- Регресс: `--collect-only -q` — 2461. Регресс прототипа: только тесты прототипа; `run_regression.py` не нужен — AST равен.

**Оценка:** 2 правки, ~5 мин.

### Шаг 3: README — номер прототипа и установка из выпуска

**Цель:** README не называют номер прототипа литералом; испытатель находит команды установки из выпуска.
**Файлы:** `numerical_solver/README.md`, `numerical_solver/examples/README.md`, `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/README.md`.

**3.1. `numerical_solver/README.md`, §1, абзац «Решатель и прототип…» (строки 33–37).** До:
```markdown
Решатель и прототип — два отдельных пакета, и устанавливать их нужно
**вместе, одной командой**: решатель требует строго определённую версию
прототипа `radial-blackoil==1.0.3+gpn.1`, и без прототипа `pip install .`
завершится ошибкой «No matching distribution found for radial-blackoil».
Все команды выполняются из каталога `numerical_solver`.
```
После:
```markdown
Решатель и прототип — два отдельных пакета, и устанавливать их нужно
**вместе, одной командой**: решатель требует строго определённую версию
прототипа `radial-blackoil` (номер — литерал `__version__` в
[`radial_blackoil/__init__.py`](HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/__init__.py)),
и без прототипа `pip install .` завершится ошибкой «No matching
distribution found for radial-blackoil». Команды ниже, кроме установки из
выпуска, выполняются из каталога `numerical_solver`.
```

**3.2. Там же — новый абзац после блока «Только для расчётов»** (после закрывающей ``` блока `pip install HydroSolverPrototype\Prototype_1.0.3 .`, перед «**На компьютере без доступа к PyPI.**»):
````markdown
**Из выпуска** (испытания: пакеты без исходного кода). Выпуски публикуются
в разделе Releases репозитория `ArturSalamatin/Oil_Gas`; к каждому
приложены колёса решателя и прототипа и архив примеров
`examples-vX.Y.Z.zip` (без примера 18: ему нужны файлы дерева прототипа).
Репозиторий закрытый — нужен GitHub CLI, авторизованный командой
`gh auth login`. Команды выполняются из любого каталога; номер выпуска —
вместо `1.0.0`:

```powershell
gh release download v1.0.0 --repo ArturSalamatin/Oil_Gas --dir release-1.0.0
Expand-Archive release-1.0.0\examples-v1.0.0.zip -DestinationPath release-1.0.0
python -m venv .venv                       # один раз
.venv\Scripts\python -m pip install (Get-ChildItem release-1.0.0\*.whl).FullName
.venv\Scripts\python -m gpn_multiphase_solver run release-1.0.0\examples\06_table_corey_rp\config.json
```

Колёса ставятся по путям файлов: при установке по имени пакета с
`--find-links` pip может взять одноимённый пакет с PyPI. Шаблон `*.whl`
раскрывает `Get-ChildItem` — сам pip его не раскрывает. Обновление — те же
команды, кроме создания `.venv`, с номером нового выпуска: примеры
распаковываются в каталог своего выпуска, pip заменит установленные версии.
````

Почему примеры — в каталог выпуска *(аудит 1)*: `Expand-Archive` отказывает, если файл уже существует (перезапись — только с `-Force`), а при `-Force` в каталоге остались бы файлы и результаты прошлого выпуска.

**3.3. `numerical_solver/examples/README.md`, строки 266–268** (на `83a5838` были 248–250; сдвиг — таблицы примера 22 FEAT-036). До:
```markdown
Ставить оба одной командой, как выше: решатель требует ровно версию `1.0.3+gpn.1`,
и `pip install -e .` без прототипа завершится ошибкой «No matching distribution
found for radial-blackoil». `PYTHONPATH` задавать не нужно.
```
После:
```markdown
Ставить оба одной командой, как выше: решатель требует ровно ту версию
прототипа, что записана литералом `__version__` в
`HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/__init__.py`, и
`pip install -e .` без прототипа завершится ошибкой «No matching distribution
found for radial-blackoil». `PYTHONPATH` задавать не нужно.
```

**3.4. `HydroSolverPrototype/Prototype_1.0.3/README.md`, строка 83** (английский, как весь README). Фрагмент до:
```markdown
… is an installable distribution `radial-blackoil` (`pyproject.toml` in this directory), version `1.0.3+gpn.1`: Prototype 1.0.3 with the local changes listed in `CHANGELOG_1.0.3.md`. The GPN solver …
```
После:
```markdown
… is an installable distribution `radial-blackoil` (`pyproject.toml` in this directory). Its version is the literal `__version__` in `radial_blackoil/__init__.py`, of the form `1.0.3+gpn.N`: Prototype 1.0.3 with the local changes listed in `CHANGELOG_1.0.3.md`; N is raised by `tools/release.py` at a solver release if this package changed (FEAT-038). The GPN solver …
```

**Проверка после шага:**
- `Select-String -Path numerical_solver/README.md, numerical_solver/examples/README.md, numerical_solver/HydroSolverPrototype/Prototype_1.0.3/README.md -Pattern "gpn\.1"` — пусто (на базе — три совпадения: строки 35, 266, 83).
- Регресс: `--collect-only -q` — 2461; дополнительно `pytest tests/test_eq_references.py tests/test_examples.py -m "not slow" -q` (они читают README примеров).

**Оценка:** 4 правки, ~15 мин.

### Шаг 4: `CLAUDE.md`

**Цель:** тип коммита `release`, строка о скрипте, исключение в «Коммиты».
**Файлы:** `CLAUDE.md` (корень).

1. «Структура проекта», таблица — после строки `| `black_oil_gas_mass.html` | … |`:
   ```markdown
   | `tools/release.py` | Выпуск решателя для испытаний: номера, метка, два колеса и архив примеров в Releases; порядок — в докстринге (FEAT-038) |
   ```
2. «Коммиты», список исключений — после пункта `/merge` («…`--force` — никогда.»):
   ```markdown
   - `tools/release.py` (FEAT-038) — выпуск: коммиты `release: X.Y.Z` и `release: начало X.Y.(Z+1).dev0` и метка в базовой ветке, один push ветки с меткой, публикация в Releases. Запускает пользователь или Claude по прямой просьбе; `/implement` его не запускает.
   ```
3. «Коммиты», строка `- Типы: `feat`, `fix`, `refactor`, `test`, `docs`, `vault`` → 
   ```markdown
   - Типы: `feat`, `fix`, `refactor`, `test`, `docs`, `vault`, `release` (только коммиты `tools/release.py`)
   ```

**Проверка:** нет (документ вне тестов).
**Оценка:** ~5 мин.

### Шаг 5: vault

**Файлы:** `vault/knowledge/decisions/выпуск решателя — одна команда, push только после самопроверки сборки из метки.md` (новая), реестр `vault/roadmap/планируемые фичи.md` (FEAT-038), `vault/00-home/index.md`.

Заметка: таблица решений 1–9 и умолчаний, которые оказались существенными (12, 13, 15, 20, 21, 23); ловушки — CRLF рабочего дерева и METADATA, `reset --keep` вместо `--hard`, `+` в имени файла выпуска сохраняется (проверено на черновике), `dist/vX.Y.Z/`; порядок первого выпуска (§8). Ссылка на [[номер версии решателя — литерал __version__, журнал сводится при выпуске]].

## 7. Тестовая стратегия

Новых тестов нет (решение 4). Чем закрыт каждый класс ошибок:

| Класс ошибок | Чем ловится | Когда |
|---|---|---|
| литерал записан не той формы / не туда | `test_solver_version_literal_follows_rule`, `test_gpn_pins_prototype_version` в самопроверке | каждый выпуск (шаги 3, 4 скрипта) |
| раздел журнала не согласован с номером | `test_changelog_has_section_for_version` в самопроверке | каждый выпуск |
| колесо не того номера / лишнее колесо | `build_wheels`: ровно два имени | каждый выпуск |
| ошибка в функциях скрипта | проба `plan_check.py` (55 проверок, включая порчи и печать в канал cp1251) | план, аудит 1, шаг 1 `/implement` |
| откат теряет данные | проба, п. 4 (учебный репозиторий) | план, шаг 1 `/implement` |
| весь путь до `gh` и установка | первый выпуск + установка в другом каталоге (§8) | после влития |

Регрессия: шаги 1, 3 — `--collect-only` (2461); шаг 2 — `test_packaging.py` + тесты прототипа (109); итоговый полный прогон — `/implement` §3.1 (ожидание: как на базе `46925a1` — 2461 тест, полный прогон FEAT-036: 2460 passed, 1 skipped; в worktree пропуск — тест черновика книги вне git).

## 8. После влития: первый выпуск (не часть `/implement`)

1. Claude по просьбе сводит раздел «Не выпущено» для `1.0.0` по `git log` (первый выпуск — описание возможностей библиотеки, не перечень задач; без ссылок на vault); пользователь правит.
2. Пользователь коммитит журнал: `docs: журнал выпуска 1.0.0`.
3. `numerical_solver\.venv\Scripts\python tools\release.py 1.0.0` из корня, на `numerical_scheme/implementation`, когда другие сессии не вливают ветки. Ожидаемая печать: «прототип 1.0.3+gpn.1 → 1.0.3+gpn.2 (изменён с 29a1ffa)», шаги 2–6, адрес выпуска.
4. В другом каталоге — команды README §1 «Из выпуска»; `.venv\Scripts\python -m gpn_multiphase_solver --version` → `gpn-multiphase-solver 1.0.0`; расчёт примера 06 из архива; `release-1.0.0\examples\06_table_corey_rp\output\versions.txt` — `gpn-multiphase-solver 1.0.0`, `radial-blackoil 1.0.3+gpn.2`.
5. В основном каталоге — по желанию `pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"`: метаданные редактируемой установки обновятся.

## 9. Критерии завершения

- [ ] `tools/release.py` побайтно равен коду плана; проба на нём — 55 ОК.
- [ ] Комментарии `pyproject.toml` и `radial_blackoil/__init__.py` без «+gpn.1» / «set 1»; AST прототипа не изменился; `test_packaging.py` 11 passed; тесты прототипа 109 passed.
- [ ] Три README без `gpn.1`; в README §1 — «Из выпуска».
- [ ] `CLAUDE.md`: строка `tools/release.py`, исключение, тип `release`.
- [ ] Полный прогон (`/implement` §3.1) — как на базе.
- [ ] Vault: заметка решения, реестр, index; комментарий в #137.

## 10. Как начать работу по этому плану

1. Прочитать этот файл целиком; заметку [[номер версии решателя — литерал __version__, журнал сводится при выпуске]]; код плана `vault/issues/feat-038/probes/plan_code/release.py` и пробу `plan_check.py`.
2. Worktree по `/implement`: `.worktrees/feat-038`, ветка `feat/feat-038/team-releases-script` от `numerical_scheme/implementation`.
3. Baseline из `numerical_solver/` worktree: `.venv\Scripts\python -m pytest tests/ --collect-only -q` → 2461 (на `46925a1`); `-m "not slow" -q` — быстрый уровень. Прототип не меняется по коду (только комментарий, шаг 2) — регрессия не нужна, тесты прототипа — в шаге 2.
4. Шаги 1–5 по порядку. Скрипт выпуска в `/implement` **не запускать**: он коммитит и публикует (CLAUDE.md, «Коммиты»); в worktree проверка ветки всё равно откажет.

## 11. Новые проблемы

Не найдено.
