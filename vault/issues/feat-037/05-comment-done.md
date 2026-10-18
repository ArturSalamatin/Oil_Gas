## Реализация завершена

**Ветка:** `feat/feat-037/solver-version-changelog` (worktree `.worktrees/feat-037`, от `numerical_scheme/implementation` `b9454a6` — после влития FEAT-035)
**План:** `vault/plans/feat-037 solver-version-changelog.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..feat/feat-037/solver-version-changelog`

### Изменения
- `gpn_multiphase_solver/__init__.py`: литерал `__version__ = "1.0.0.dev0"` — единственный источник номера.
- `pyproject.toml`: статический `version = "0.1.0"` → `dynamic = ["version"]`, `[tool.setuptools.dynamic] version = {attr = "gpn_multiphase_solver.__version__"}`.
- `CHANGELOG.md` (новый): правило номеров MAJOR/MINOR/PATCH, нумерация прототипа `1.0.3+gpn.N`, раздел «Не выпущено».
- `gpn_multiphase_solver/cli.py`: ключ `--version` → `gpn-multiphase-solver 1.0.0.dev0`, без импорта решателя и прототипа.
- `gpn_multiphase_solver/report/pipeline.py`: `_versions()`; строка «Версии: …» третьей в печати `run_case`; `output/versions.txt` — решатель, прототип, Python, numpy, scipy.
- `README.md` (6 правок), `examples/README.md`: номер, `--version`, журнал, `versions.txt`.
- Тесты: `test_packaging.py` (+3), `test_cli.py` (+3, `STANDARD_FILES`, команда из постороннего каталога), `test_examples.py` (`expected`).

### Тесты
- Было: 2395 тестов (база после FEAT-035)
- Стало: 2401 тест (+6 новых)
- Полный прогон: 2400 passed, 1 skipped (594 с) ✅
- Колесо из worktree: `gpn_multiphase_solver-1.0.0.dev0-py3-none-any.whl`, METADATA `1.0.0.dev0` ✅
- Прототип не менялся.

После влития по желанию — `pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"` в основном каталоге: метаданные редактируемой установки обновятся с `0.1.0` (тестам не нужно).
