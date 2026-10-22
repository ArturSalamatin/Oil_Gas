---
tags: [решение, упаковка, версии, FEAT-037]
date: 2026-10-18
issue: FEAT-037
---

# Номер версии решателя — литерал `__version__`, журнал сводится при выпуске

**GitHub issue:** [#134](https://github.com/ArturSalamatin/Oil_Gas/issues/134) · план [[feat-037 solver-version-changelog]]

**Что было.** Номер решателя `0.1.0` был записан только литералом в `numerical_solver/pyproject.toml`. В пакете не было `__version__`, журнала изменений не было, в результатах расчёта версия не записывалась. По каталогу `output/` нельзя было установить, каким кодом получены результаты.

**Решение (FEAT-037, решения пользователя 2026-10-18):**

| Вопрос | Решение | Почему |
|---|---|---|
| Источник номера | литерал `gpn_multiphase_solver.__version__`; `pyproject.toml` — `dynamic = ["version"]`, `[tool.setuptools.dynamic] version = {attr = …}` | один источник, как у прототипа ([[прототип — отдельный дистрибутив radial-blackoil с точной версией, тесты берут его из своего дерева]]); работает без установки и в изолированной сборке. `importlib.metadata` не годится — у редактируемой установки метаданные отстают; `setuptools-scm` — у среза поставки нет `.git` |
| Номер до выпуска | `1.0.0.dev0`; `1.0.0` — в момент выпуска (FEAT-031) | номер не утверждает, что код равен поставке, пока цепочка книги ввода открыта |
| Правило номеров | в `numerical_solver/CHANGELOG.md`: MAJOR — несовместимость интерфейса (README §4), конфига или книги; MINOR — новые возможности; PATCH — исправления; изменение чисел результатов — отдельно в разделе выпуска; прототип — `1.0.3+gpn.N`, N растёт при выпуске, если код прототипа менялся | журнал читает команда разработки заказчика |
| Пополнение журнала | между выпусками — не пополняется; раздел выпуска сводится при выпуске по истории git; в «Не выпущено» — только запись FEAT-037 | решение пользователя; `/implement` не меняется |
| Версии в результатах | `output/versions.txt` — 5 строк «имя номер»: `gpn-multiphase-solver`, `radial-blackoil`, `Python`, `numpy`, `scipy`; та же строка «Версии: …» — третьей в печати `run_case` | от numpy и scipy зависят последние разряды чисел |
| Номер прототипа в записи | `radial_blackoil.__version__` импортированного модуля | метаданные pip отстают; `build_info.VERSION` (`'1.0.3'`) — номер для регрессии прототипа |
| Ключ команды | `gpn-solver --version` → `gpn-multiphase-solver <номер>`, только решатель, без импорта решателя и прототипа | строка совпадает с первой строкой `versions.txt`; `%(prog)s` зависит от способа запуска |

**Ловушки:**
- Метаданные редактируемой установки записаны при `pip install -e`: после смены литерала `importlib.metadata.version("gpn-multiphase-solver")` возвращает прежний номер до переустановки. Из `numerical_solver/` метаданные находит ещё и устаревший `gpn_multiphase_solver.egg-info` каталога. Тесты метаданные не сверяют.
- В worktree **не запускать `pip install -e`**: venv общий, установка перенаправится на worktree и сломается после его удаления. Номер в метаданных проверяется сборкой колеса (`vault/issues/feat-037/probes/plan_checks.py <каталог решателя>`).
- `'1.0'` по PEP 440 — каноническая форма: тест правила проверяет ещё и ровно три числа (`len(Version(v).release) == 3`).
- pip без `--pre` устанавливает `1.0.0.dev0`, если других версий нет (установка без PyPI по README §1 работает).
- `versions.txt` на Windows — с CRLF (`Path.write_text`); тесты читают через `splitlines()`.

**Выпуск (FEAT-031):** литерал без `.dev`; раздел `## 1.0.0 — <дата>` вместо «Не выпущено» (тест `test_changelog_has_section_for_version` требует раздел своего номера); `+gpn.2` прототипа; `release` Sphinx — из `__version__`. После влития — переустановка в основном каталоге обновляет метаданные (тестам не нужна).

**Сторожа** — `tests/test_packaging.py`: `test_solver_version_is_dynamic_from_literal`, `test_solver_version_literal_follows_rule`, `test_changelog_has_section_for_version`; `tests/test_cli.py`: `test_version_flag`, `test_version_does_not_import_solver`, `test_versions_sources`, `test_run_from_foreign_directory` (13 файлов, строка версий, `versions.txt`).
