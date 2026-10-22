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

Пошаговая инструкция – в README решателя
([numerical_solver/README.md](numerical_solver/README.md)), раздел «Начало
работы», «Поставка для разработки». README входит в архив, заказчик получает
её вместе с кодом.

## Поставка для использования

Пакеты без исходного кода – для расчётов без изменения кода. Выпуск `vX.Y.Z`
состоит из пяти файлов, все их собирает и публикует `tools/release.py` из
метки выпуска:

| Файл | Содержание |
|---|---|
| `gpn_multiphase_solver-X.Y.Z-py3-none-any.whl` | решатель |
| `radial_blackoil-1.0.3+gpn.N-py3-none-any.whl` | прототип – обязательная зависимость решателя ровно этой версии |
| `examples-vX.Y.Z.zip` | примеры: конфигурации, таблицы, README с эталонными значениями; без примера 18 – ему нужны книги и эталон CMG IMEX из дерева прототипа |
| `README.md` | README решателя: пошаговая инструкция получателя (раздел «Начало работы»), формат файла конфигурации и таблиц (§3), книга Excel (§3.6), вызов из Python (§4) |
| `docs-vX.Y.Z.zip` | собранная HTML-документация: README, техническое описание, публичный интерфейс |

Выпуски v1.0.0–v1.0.2 опубликованы до этого – в них три файла, без
README и документации. Тесты и PDF постановки не передаются. Решатель ставится без группы `[dev]`
(pytest, Sphinx), с зависимостями numpy, scipy, matplotlib и XlsxWriter.

Команды – PowerShell. `X.Y.Z` – номер выпуска (например, `1.0.2`), его
нужно подставить. Корень репозитория – `D:\Lessons\Grants\2026\GPN\Oil_Gas`.

### Что делаем мы

1. Проверить ветку и рабочее дерево: все задачи влиты в
   `numerical_scheme/implementation`, незакоммиченных правок в
   `numerical_solver/` нет, ветка не позади origin.

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   git branch --show-current
   git status --short numerical_solver
   git fetch origin
   git rev-list --count HEAD..origin/numerical_scheme/implementation
   ```

   Ожидается `numerical_scheme/implementation`, пустой вывод `git status`
   и `0` в последней строке (число коммитов origin, которых нет локально).

2. Проверить, нужен ли новый выпуск: последняя метка и изменения
   `numerical_solver/` после неё.

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   git tag --list "v*" --sort=-v:refname | Select-Object -First 1
   git diff --stat vX.Y.Z HEAD -- numerical_solver
   ```

   В `git diff` – последняя метка из первой команды. Пустой вывод – выпуск
   уже есть, перейти к шагу 6 с её номером.

3. Проверить раздел «Не выпущено» журнала изменений: в нём есть пункты
   обо всех изменениях с прошлого выпуска, раздел закоммичен. Раздел
   становится заметками выпуска в Releases.

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   Select-String -Path numerical_solver\CHANGELOG.md -Encoding UTF8 -Pattern "^## Не выпущено" -Context 0,20
   ```

4. Проверить GitHub CLI – печатается `Logged in to github.com`:

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   gh auth status
   ```

   Убедиться, что в другой сессии не идёт `/merge`: скрипт выпуска
   коммитит в ту же ветку.

5. Выпуск:

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   numerical_solver\.venv\Scripts\python tools\release.py X.Y.Z
   $LASTEXITCODE
   ```

   Номер – три числа без суффикса, больше текущего и прошлого выпуска.
   Скрипт делает коммит `release: X.Y.Z` и метку `vX.Y.Z`, собирает из
   метки (не из рабочего каталога) в `dist\vX.Y.Z\` архив примеров, README
   решателя, HTML-документацию (архив `docs-vX.Y.Z.zip`) и wheels,
   проверяет дерево метки тестами `tests/test_packaging.py`, делает коммит
   `release: начало X.Y.(Z+1).dev0`, одним push отправляет ветку с меткой и
   публикует все пять файлов в Releases репозитория `ArturSalamatin/Oil_Gas`.
   Нужен Sphinx в venv решателя (группа `[dev]`) – без него скрипт
   отказывает до любых изменений. Подробности – в докстринге
   [tools/release.py](tools/release.py).

   Итог: `$LASTEXITCODE` – 0. При отказе до push скрипт откатывает свои
   коммиты и метку и завершается с кодом 1, каталог `dist\vX.Y.Z\`
   остаётся для разбора. При отказе публикации ветка и метка уже на
   origin – скрипт печатает команду `gh` для повтора. Опубликованный
   выпуск не меняется; исправление – новый выпуск.

6. Проверить выпуск в Releases – пять файлов: `docs-vX.Y.Z.zip`,
   `examples-vX.Y.Z.zip`, `gpn_multiphase_solver-X.Y.Z-py3-none-any.whl`,
   `radial_blackoil-1.0.3+gpn.N-py3-none-any.whl`, `README.md`:

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   gh release view vX.Y.Z --repo ArturSalamatin/Oil_Gas --json assets --jq '.assets[].name'
   ```

7. Скачать пять файлов выпуска в одну папку `dist\release-X.Y.Z`,
   проверить её и открыть:

   ```powershell
   cd D:\Lessons\Grants\2026\GPN\Oil_Gas
   gh release download vX.Y.Z --repo ArturSalamatin/Oil_Gas --dir dist\release-X.Y.Z
   Get-ChildItem D:\Lessons\Grants\2026\GPN\Oil_Gas\dist\release-X.Y.Z
   explorer D:\Lessons\Grants\2026\GPN\Oil_Gas\dist\release-X.Y.Z
   ```

8. Передать получателю папку `release-X.Y.Z` с пятью файлами.

### Что делает получатель

Пошаговая инструкция – в README решателя
([numerical_solver/README.md](numerical_solver/README.md)), раздел «Начало
работы», «Поставка для расчётов». README – один из пяти файлов выпуска.
