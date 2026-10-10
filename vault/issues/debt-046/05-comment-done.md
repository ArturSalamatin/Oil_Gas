## Реализация завершена

**Ветка:** `refactor/debt-046/examples-scripts-import-check` (worktree `.worktrees/debt-046`, от `numerical_scheme/implementation` `81d1474`)
**План:** `vault/plans/debt-046 examples-scripts-import-check.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-046/examples-scripts-import-check`

### Изменения
- `numerical_solver/tests/test_example_scripts.py` (новый): `test_script_names_resolve` по всем 45 `.py` в `examples/` (список по диску). Текст разбирается модулем `ast`, скрипты не исполняются. Проверяются:
  - импорты на любом уровне вложенности, включая функции и блок `__main__`;
  - обращения `alias.name` (`tpa.report`);
  - глобальные имена функций против имён модуля (`LOAD_GLOBAL`);
  - именованные аргументы `run_example(...)` по сигнатуре.

  Учтены модули из папки примера и пакет `radial_blackoil`. Тест `test_checker_sees_broken_names` проверяет саму проверку на 8 синтетических поломках.
- `numerical_solver/tests/test_examples.py`: удалён `test_convergence_users_import` (DEBT-031), на его месте — комментарий-указатель.
- `numerical_solver/examples/README.md`: абзац о проверке скриптов в разделе «Автоматические тесты».
- Код решателя, примеров и прототипа не менялся.

### Тесты
- Было: 1429 тестов, быстрый уровень 1179.
- Стало: 1481 (+53 новых, −1 удалённый), быстрый уровень 1231 passed (79 с).
- Полный прогон: 1481 passed (509 с) ✅

### Проверка на подменах (код ветки, `probes/red_impl_check.out.txt`)
| Удалено | Помечено файлов | Совпадает с планом |
|---|---|---|
| `figure_io.export_emf` | 11 | ✅ |
| `closed_form.solve_closed` | 3 | ✅ |
| `gpn_multiphase_solver.factory.SimulatorFactory` | 17 | ✅ |
| `gpn_multiphase_solver.io.config.load_config` | 14 | ✅ |
| `gpn_multiphase_solver.units.S_TO_DAY` | 4 | ✅ |
| `two_phase_analytics.report` | 3 | ✅ |
| `two_phase_analytics.SG_EPS` | 3 | ✅ |
| `temperature_asymptotics.single_phase_asymptote` | 3 | ✅ |
| `two_phase_analytics.solve_closed` | 1 | ✅ |
| `example_runner._PROTO_ROOT` | 2 | ✅ |
| параметр `title` у `run_example` | 22 | ✅ |
| строка `from copy import deepcopy` в `convergence.py` | поймана | ✅ |
| строка `import two_phase_analytics as tpa` в `main.py` 03 | поймана | ✅ |
