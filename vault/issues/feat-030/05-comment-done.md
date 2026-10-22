## Реализация завершена

**Ветка:** `feat/feat-030/run-command-from-config` (worktree `.worktrees/feat-030`, от `numerical_scheme/implementation` `b487f80`)
**План:** `vault/plans/feat-030 run-command-from-config.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..feat/feat-030/run-command-from-config`

### Изменения
- `gpn_multiphase_solver/cli.py`, `__main__.py`, `pyproject.toml` (`[project.scripts]`): команда `python -m gpn_multiphase_solver run config.json [--output DIR] [--title T] [--profiles N]` / `gpn-solver run …`; коды возврата 0 / 1 (отказ решателя, без трассировки) / 2 (аргументы или конфиг, расчёт не начат); `configure_batch_run()` — консоль UTF-8 и matplotlib `Agg`.
- `gpn_multiphase_solver/report/pipeline.py`: `run_case` — штатный набор (перенос `examples/example_runner.py`), `CaseResult` с решателем, `CaseConfigError`, `CaseRunError`; отказ до расчёта, если в каталоге вывода лежит конфиг или его CSV.
- `gpn_multiphase_solver/report/` (7 модулей) ← `relperm_plot`, `pvt_plot`, `rs_analytics`, `closed_form`, `energy_balance`, `mass_balance`, `temperature_asymptotics` из `examples/`; без `matplotlib.use`, `sys.path`, CLI-блоков; `io/figures.py` ← `examples/figure_io.py`.
- `io/config.py`: поля `output.title`, `n_profiles`, `steady_state` (по умолчанию `false`), `closed_form_overlays` с проверкой.
- `examples/`: 23 конфига получили секцию `output` (значения — прежние аргументы `main.py`); 17 `main.py` — обёртки команды (решение 6); `main.py` 01–05, 18 — `run_case` без второго `Simulator`; `example_runner.py` удалён; `_resolve_example` — одна копия; конфиг 18 пишет перевод книги (`prototype_input.convert`).
- Документы: README 23 примеров и `examples/README.md` (команда, поля `output`, модули `report/`), `.claude/commands/run.md`, `CLAUDE.md`.

### Тесты
- Было: 1879 тестов
- Стало: 1904 (+36 новых: `test_cli.py` 13, `test_figures.py` 3, поля `output` 14, `run_case` 4, примеры 2; +17 стража обёрток `main.py`; −29 параметров за скрипты, ушедшие из `examples/`)
- Полный прогон: 1904 passed (560 с) ✅

### Проверка неизменности и приёмка
| проверка | итог |
|---|---|
| снимок 23 примеров (печать + побайтно `output/`) после шага 5 — через временную обёртку `run_example` → `run_case` | 23/23 совпадает ✅ |
| снимок после шага 7 — 17 обёрток команды + 6 `main.py` со своей логикой | 23/23 совпадает ✅ |
| приёмка в чистом окружении из колёс без PyPI (`probes/clean_env_command.py`): `python -I -m` (06) и `gpn-solver.exe` (07) из постороннего каталога | файлы побайтно = снимку, печать = снимку ✅ |
| там же: ошибка конфига / каталог вывода с конфигом | код 2 ✅ |
| там же: без Inkscape, EMF включён | код 0, одно предупреждение, SVG без EMF ✅ |

### Отклонения от плана
- Конфиг 18 порождается переводом книги прототипа, и тест сверяет файл с переводом — поля `output` пишет теперь `prototype_input.convert` (заголовок по имени книги).
- Решение 6 (пользователь, 2026-10-13, до шага 7): `main.py` не удаляются у 17 примеров, а становятся обёртками команды; `run_all.py` без правок.

После влития `gpn-solver.exe` в общем venv появится после переустановки в основном каталоге: `.venv\Scripts\python -m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"`. `python -m gpn_multiphase_solver` работает и без неё.
