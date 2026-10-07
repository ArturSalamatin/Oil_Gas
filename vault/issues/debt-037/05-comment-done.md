## Реализация завершена

**Ветка:** `refactor/debt-037/shared-modules-copy-guard` (worktree `.worktrees/debt-037`, от `d390b85`)
**План:** `vault/plans/debt-037 shared-modules-copy-guard.md`
**Коммиты:**
- `f6fbf56` test: проверка копий общих модулей примеров — по всем examples/*.py, список строится по диску (DEBT-037)
- `42a9994` (базовая ветка) vault: DEBT-037 — заметка-решение: порядок sys.path у примеров, защита по всем examples/*.py

### Изменения
- `numerical_solver/tests/test_examples.py`:
  - новая константа `SHARED_EXAMPLE_FILES = sorted(p.name for p in EXAMPLES_DIR.glob("*.py"))`, теперь 16 файлов;
  - `test_no_duplicate_helper_scripts` параметризован ею, было 6 модулей из ручного списка;
  - `SHARED_CHECK_MODULES` остался только для `test_shared_modules_exist`;
  - комментарий описывает оба исхода копии: перекрытие (`main.py` 01, 02, 03, 05 и скрипты сходимости 04, 04a, 05) и игнорирование (остальные `main.py`).
- `vault/knowledge/decisions/проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП.md`: исправлено неверное «каждый `main.py` делает две вставки `sys.path`», добавлено, что защита идёт по диску.

Код решателя, примеры и прототип не менялись.

### Тесты
- Было: 1289 тестов, быстрый уровень 1053 passed.
- Стало: 1299 тестов (+10 параметров), быстрый уровень 1063 passed (63 с), полный прогон 1299 passed (310 с).
- Все зелёные: ✅

### Отрицательные пробы (в worktree, пробные файлы удалены)
| Проба | До правки | После правки |
|---|---|---|
| копия `figure_io.py` в `01_single_phase_no_jt/` | 7 passed (не ловится) | 1 failed: `figure_io.py снова скопирован в папки примеров: ['01_single_phase_no_jt']` |
| новый `examples/zz_debt037_probe.py` + копия в `03_standing_corey/` | — | 1 failed, 16 passed (`[zz_debt037_probe.py]`) |
