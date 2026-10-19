# Oil_Gas

Модель призабойной зоны добывающей скважины: неизотермическая фильтрация
газированной нефти (Black Oil). Решатель – каталог
[numerical_solver/](numerical_solver/), установка и работа с ним – в
[его README](numerical_solver/README.md).

## Передача заказчику

Два вида поставки:

- для разработки – архив исходного кода, `tools/handover.py` (этот раздел);
- для использования – wheels и примеры из выпуска, `tools/release.py`
  (раздел «Поставка для использования» ниже).

Для разработки заказчику передаётся один архив
`gpn-multiphase-solver-<версия>.zip` финального выпуска. В архиве – срез
`numerical_solver` из метки выпуска: код решателя и прототипа, тесты,
примеры, README, собранные HTML-документация и PDF постановки. История git,
vault, перечни задач и скрипт приёмки не передаются.

Команды – PowerShell. `X.Y.Z` – номер выпуска (например, `1.0.2`), его
нужно подставить. Корень репозитория – `D:\Lessons\Grants\2026\GPN\Oil_Gas`.

### Что делаем мы

1. Проверить ветку и рабочее дерево: все задачи влиты в
   `numerical_scheme/implementation`, незакоммиченных правок в
   `numerical_solver/` нет.

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   git branch --show-current
   git status --short numerical_solver
   ```

   Ожидается `numerical_scheme/implementation` и пустой вывод `git status`.

2. Проверить, нужен ли выпуск: последняя метка и изменения
   `numerical_solver/` после неё.

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   git tag --list "v*" --sort=-v:refname | Select-Object -First 1
   git diff --stat vX.Y.Z HEAD -- numerical_solver
   ```

   В `git diff` – последняя метка из первой команды. Пустой вывод – выпуск
   не нужен, перейти к шагу 5.

3. Проверить раздел «Не выпущено» журнала изменений: в нём есть пункты
   обо всех изменениях с прошлого выпуска, раздел закоммичен.

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   Select-String -Path numerical_solver\CHANGELOG.md -Encoding UTF8 -Pattern "^## Не выпущено" -Context 0,20
   ```

4. Выпуск – коммиты номеров, метка `vX.Y.Z`, push и публикация в Releases
   (подробности – в докстринге [tools/release.py](tools/release.py) и в
   разделе «Поставка для использования»):

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   gh auth status
   numerical_solver\.venv\Scripts\python tools\release.py X.Y.Z
   ```

5. Проверить, что другой прогон передачи сейчас не идёт: скрипт передачи
   первым делом удаляет `dist\handover-X.Y.Z\` и сломает его.

   ```powershell
   Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -match 'handover|acceptance' -or $_.ExecutablePath -match 'dist\\handover' } | Select-Object ProcessId, CreationDate, CommandLine
   ```

   Пустой вывод – можно запускать. Если выпуск сделан на другом
   компьютере, сначала получить его метку:

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   git fetch --tags
   ```

6. Собрать архив:

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   numerical_solver\.venv\Scripts\python tools\handover.py
   $LASTEXITCODE
   ```

   Без аргумента берётся последний выпуск – локальная метка `vX.Y.Z` с
   наибольшим номером (скрипт печатает, какая). Другой выпуск задаётся
   меткой:

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   numerical_solver\.venv\Scripts\python tools\handover.py vX.Y.Z
   ```

   Скрипт берёт срез `numerical_solver` из метки, собирает PDF постановки и
   HTML-документацию, упаковывает архив. Git не меняется. Нужны pdflatex в
   PATH, Sphinx и packaging в venv решателя (группа `[dev]`).

   Приёмка архива по умолчанию не выполняется – только по ключу
   `--acceptance` (вместе с меткой или без неё):

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   numerical_solver\.venv\Scripts\python tools\handover.py --acceptance
   $LASTEXITCODE
   ```

   Скрипт распаковывает копию архива в `dist\handover-X.Y.Z\check\` и
   проверяет её ([tools/acceptance.py](tools/acceptance.py): установка в
   свежее окружение, все тесты, сборка документации, расчёты по книге Excel
   и по файлу конфигурации). Приёмка идёт около 15 мин, нужен доступ к
   PyPI.

7. Проверить итог: `$LASTEXITCODE` – 0, в последней строке вывода – путь к
   архиву. С ключом `--acceptance` – ещё строка «ПРИЁМКА: ПРОЙДЕНА» и в
   последней строке «приёмка – пройдена». Архив создаётся до приёмки и
   остаётся на диске и при её отказе – такой архив не передаётся. При
   отказе (код 1) каталог `dist\handover-X.Y.Z\` остаётся для разбора;
   повторный запуск создаёт его заново.

8. Передать заказчику файл `gpn-multiphase-solver-X.Y.Z.zip` из папки:

   ```powershell
   explorer D:\Lessons\Grants\2026\GPN\Oil_Gas\dist\handover-X.Y.Z
   ```

### Что делает заказчик

Нужны Python 3.10 или новее и доступ к PyPI. Папка `D:\gpn` – пример;
архив положен в неё.

1. Распаковать архив:

   ```powershell
   cd D:\gpn
   Expand-Archive D:\gpn\gpn-multiphase-solver-X.Y.Z.zip -DestinationPath D:\gpn
   ```

   Появится папка `D:\gpn\gpn-multiphase-solver-X.Y.Z`.

2. Установить решатель и прототип в режиме разработки (с pytest и
   Sphinx) – скриптом:

   ```powershell
   cd D:\gpn\gpn-multiphase-solver-X.Y.Z
   .\setup.bat
   ```

   или вручную:

   ```powershell
   cd D:\gpn\gpn-multiphase-solver-X.Y.Z
   python -m venv .venv
   .venv\Scripts\python -m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"
   ```

   Проверка – печатается `gpn-multiphase-solver X.Y.Z`:

   ```powershell
   cd D:\gpn\gpn-multiphase-solver-X.Y.Z
   .venv\Scripts\python -m gpn_multiphase_solver --version
   ```

3. Открыть документацию и постановку:

   ```powershell
   start D:\gpn\gpn-multiphase-solver-X.Y.Z\doc\build\html\index.html
   start D:\gpn\gpn-multiphase-solver-X.Y.Z\doc\problem_statement.pdf
   ```

4. Рассчитать пример по файлу конфигурации – результаты в
   `examples\06_table_corey_rp\output\`:

   ```powershell
   cd D:\gpn\gpn-multiphase-solver-X.Y.Z
   .venv\Scripts\python -m gpn_multiphase_solver run examples\06_table_corey_rp\config.json
   ```

   Рассчитать свой вариант по книге Excel – шаблон, заполнение, расчёт;
   результаты в `D:\gpn\output\`:

   ```powershell
   cd D:\gpn
   D:\gpn\gpn-multiphase-solver-X.Y.Z\.venv\Scripts\python -m gpn_multiphase_solver template my_case.xlsx
   D:\gpn\gpn-multiphase-solver-X.Y.Z\.venv\Scripts\python -m gpn_multiphase_solver run my_case.xlsx
   ```

   Вызов из Python (`run_case`, `load_config`, `SimulatorFactory`) – README
   решателя, §4.

5. После правок кода – тесты решателя: быстрый уровень (1–2 мин) и
   полный (около 10 мин, сверяет числа примеров с их README):

   ```powershell
   cd D:\gpn\gpn-multiphase-solver-X.Y.Z
   .venv\Scripts\python -m pytest tests/ -m "not slow" -q
   .venv\Scripts\python -m pytest tests/ -q
   ```

   После правок прототипа – ещё его тесты и регрессия по эталону, сверенному
   с CMG IMEX (тесты решателя отклонение прототипа от эталона не
   обнаружат):

   ```powershell
   cd D:\gpn\gpn-multiphase-solver-X.Y.Z\HydroSolverPrototype\Prototype_1.0.3
   D:\gpn\gpn-multiphase-solver-X.Y.Z\.venv\Scripts\python -m unittest discover -s tests -v
   D:\gpn\gpn-multiphase-solver-X.Y.Z\.venv\Scripts\python .\regression\run_regression.py
   ```

6. После правок докстрингов или README – пересобрать HTML-документацию:

   ```powershell
   cd D:\gpn\gpn-multiphase-solver-X.Y.Z
   .venv\Scripts\python -m sphinx -W -b html doc/source doc/build/html
   ```

   После правки постановки – PDF (pdflatex дважды) и таблица номеров
   уравнений для HTML, затем снова сборка HTML:

   ```powershell
   cd D:\gpn\gpn-multiphase-solver-X.Y.Z\doc
   pdflatex -interaction=nonstopmode problem_statement.tex
   pdflatex -interaction=nonstopmode problem_statement.tex
   cd D:\gpn\gpn-multiphase-solver-X.Y.Z
   .venv\Scripts\python tools\eq_numbers.py
   .venv\Scripts\python -m sphinx -W -b html doc/source doc/build/html
   ```

## Поставка для использования

Пакеты без исходного кода – для расчётов без изменения кода. Выпуск `vX.Y.Z`
состоит из трёх файлов:

| Файл | Содержание |
|---|---|
| `gpn_multiphase_solver-X.Y.Z-py3-none-any.whl` | решатель |
| `radial_blackoil-1.0.3+gpn.N-py3-none-any.whl` | прототип – обязательная зависимость решателя ровно этой версии |
| `examples-vX.Y.Z.zip` | примеры: конфигурации, таблицы, README с эталонными значениями; без примера 18 – ему нужны книги и эталон CMG IMEX из дерева прототипа |

Тесты, README решателя, HTML-документация и PDF постановки в выпуск не
входят.

### Порядок

Все команды выполняются из корня репозитория, интерпретатором venv решателя.

1. Убедиться, что раздел «Не выпущено» в
   [numerical_solver/CHANGELOG.md](numerical_solver/CHANGELOG.md) заполнен
   и закоммичен: он становится заметками выпуска.
2. Условия запуска: основной каталог на ветке
   `numerical_scheme/implementation`, ветка не позади origin; в
   `numerical_solver/` нет незакоммиченных правок отслеживаемых файлов;
   GitHub CLI авторизован (`gh auth login`); другая сессия в это время не
   вливает ветку (`/merge`) – скрипт коммитит в ту же ветку.
3. Выпуск:

   ```powershell
   numerical_solver\.venv\Scripts\python tools\release.py X.Y.Z
   ```

   Номер – три числа без суффикса, больше текущего и прошлого выпуска.
   Скрипт делает коммит `release: X.Y.Z` и метку `vX.Y.Z`, собирает из
   метки (не из рабочего каталога) архив примеров и wheels в
   `dist\vX.Y.Z\`, проверяет дерево метки тестами
   `tests/test_packaging.py`, делает коммит
   `release: начало X.Y.(Z+1).dev0`, одним push отправляет ветку с меткой и
   публикует выпуск в Releases репозитория `ArturSalamatin/Oil_Gas`.
   Подробности – в докстринге [tools/release.py](tools/release.py).

   Если выпуск `vX.Y.Z` уже есть, шаг не повторяется: файлы лежат в
   `dist\vX.Y.Z\` и в Releases.
4. Проверка итога: код возврата 0, в Releases – выпуск `vX.Y.Z` с тремя
   файлами. При отказе до push скрипт откатывает свои коммиты и метку и
   завершается с кодом 1, каталог `dist\vX.Y.Z\` остаётся для разбора. При
   отказе публикации ветка и метка уже на origin – скрипт печатает команду
   `gh` для повтора. Опубликованный выпуск не меняется; исправление – новый
   выпуск.
5. Передать получателю три файла: `dist\vX.Y.Z\wheels\*.whl` и
   `dist\vX.Y.Z\examples-vX.Y.Z.zip`. Репозиторий закрытый: скачать выпуск
   из Releases (`gh release download vX.Y.Z --repo ArturSalamatin/Oil_Gas`)
   может только тот, у кого есть доступ ко всему репозиторию.

Установка у получателя – [README решателя](numerical_solver/README.md),
§1 «Из выпуска», шаги 3–9: три файла кладутся в папку `release-X.Y.Z`
вместо скачивания на шаге 2. Зависимости (numpy, scipy, matplotlib,
XlsxWriter) ставятся из PyPI.
