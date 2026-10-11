## Реализация завершена

**Ветка:** `refactor/debt-059/installable-prototype-package` (worktree `.worktrees/debt-059`, от `numerical_scheme/implementation` `66d28d2`)
**План:** `vault/plans/debt-059 installable-prototype-package.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-059/installable-prototype-package` — `5b91e89`…`37d3b9f` плюс итоговый коммит vault

### Изменения
- `HydroSolverPrototype/Prototype_1.0.3/pyproject.toml` (новый): дистрибутив `radial-blackoil`. В него входит только пакет `radial_blackoil`. Зависимости: numpy, scipy, matplotlib, XlsxWriter. Версия берётся из литерала `__version__`.
- `radial_blackoil/__init__.py`: `__version__ = '1.0.3+gpn.1'`. `build_info.VERSION` и `BUILD_ID` не менялись: регрессия сверяет их с эталонами.
- `numerical_solver/pyproject.toml`: зависимость `radial-blackoil==1.0.3+gpn.1`; `XlsxWriter` убран из `dev` (теперь его тянет прототип); `pythonpath = ["HydroSolverPrototype/Prototype_1.0.3"]` для pytest.
- `tests/conftest.py`: вставка пути к прототипу удалена.
- 15 файлов `examples/`: убраны 13 вставок пути к прототипу и 2 импорта `_PROTO_ROOT`. В 04/04a вместо них `import example_runner`, иначе консоль не переключится на UTF-8.
- `tests/test_packaging.py` (новый, 8 тестов) проверяет:
  - согласованность версии;
  - что объявлены все сторонние импорты обоих пакетов;
  - что в дистрибутив прототипа входит только пакет;
  - что тесты берут код своего дерева;
  - что путь к прототипу в `sys.path` никто не вставляет.
- Документы: README примеров («Запуск»), README и CHANGELOG прототипа, 7 команд `.claude/` (механизм подключения прототипа; число тестов прототипа 80 → 97). В vault — заметка-решение и правка заметки о модулях проверок.

### Тесты
- Было: 1679 тестов (`b3ffaac`/`66d28d2`).
- Стало: 1687 (+8). Полный прогон — 1687 passed за 624 с; быстрый уровень — 1425 passed (база 1417).
- Прототип: тесты 97 passed; регрессия `--quick` 11/11 PASS до и после правки.
- Все зелёные: ✅

### Приёмка (`vault/issues/debt-059/probes/clean_env_acceptance.py`)
| Проверка | Итог |
|---|---|
| колесо прототипа — только `radial_blackoil` | ✅ |
| GPN объявляет `radial-blackoil==1.0.3+gpn.1` | ✅ |
| установка из колёс без PyPI, `pip check` | ✅ |
| пакеты — из site-packages чистого окружения, версия 1.0.3+gpn.1 | ✅ |
| отпечаток истории примеров 03, 04, 05 (SHA-256) = базовый | ✅ побитово |
| `run_workbook` — `results.xlsx` и PNG | ✅ |
| `pip install -e` обоих пакетов без PyPI, `pip check`, пакеты из дерева | ✅ |

Отпечаток в worktree до и после правки совпал. Общий venv не изменён.

### После влития (основной каталог, однократно)

Сразу после `/merge`. Без этого в основном каталоге не запускаются примеры и `run.md`. Тесты работают и без установки.

```powershell
cd <КОРЕНЬ>\numerical_solver
<PY> -m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"
<PY> -m pip check                                                   # No broken requirements found.
<PY> -c "import radial_blackoil as r; print(r.__file__, r.__version__)"   # <КОРЕНЬ>\...\Prototype_1.0.3\radial_blackoil\__init__.py 1.0.3+gpn.1
<PY> examples\03_standing_corey\main.py                             # без PYTHONPATH — работает
<PY> -X utf8 <КОРЕНЬ>\vault\issues\debt-059\probes\history_fingerprint.py --examples examples --out <КОРЕНЬ>\numerical_solver\build\debt059_main.out.txt
Compare-Object (Get-Content <КОРЕНЬ>\vault\issues\debt-059\probes\fingerprint_after.out.txt) (Get-Content <КОРЕНЬ>\numerical_solver\build\debt059_main.out.txt)   # пусто
```

Установка именно из основного каталога, а не из worktree: worktree удаляется при `/merge`.
