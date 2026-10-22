## Реализация завершена

**Ветка:** `refactor/debt-032/test-tiers-fast-regression` (worktree `.worktrees/debt-032`, от `132c9c8`)
**План:** `vault/plans/debt-032 test-tiers-fast-regression.md`
**Коммиты:**
```
f631223 docs: CLAUDE.md — уровни прогона тестов (DEBT-032)
6f77153 docs: шаблоны /plan-* — поле «Регресс» и baseline без полного прогона (DEBT-032)
4daffde docs: /audit-plan — baseline через --collect-only, проверка поля «Регресс» (DEBT-032)
34e04bc docs: /implement — быстрый уровень после шага, полный прогон в конце (DEBT-032)
00b7580 test: фикстура results считает пример при первом обращении (DEBT-032)
e1c6d8f test: метка slow для тяжёлых тестов — фикстура results и сверка матрицы (DEBT-032)
```

### Изменения
- `numerical_solver/tests/conftest.py`: хук `pytest_collection_modifyitems` — метка `slow` тестам на фикстуре `results`
- `numerical_solver/tests/test_energy_matrix_examples.py`: явная метка `slow` на `test_matrix_matches_reference`
- `numerical_solver/tests/test_examples.py`: `results` — ленивый словарь (`__missing__`) с кешем упавших расчётов; docstring модуля
- `numerical_solver/pyproject.toml`: описание метки `slow`
- `.claude/commands/implement.md`, `audit-plan.md`, `plan-feature.md`, `plan-fix.md`, `plan-improve.md`, `plan-validate.md`: быстрый уровень после шага, полный в конце, поле «Регресс», baseline без полного прогона, `--lf`, `-q`
- `CLAUDE.md`: таблица уровней прогона

### Тесты
- Было: 1121 тест; стало: 1121 (новых нет, id собранных тестов не изменились)
- Все зелёные: ✅

| Метрика | До | После |
|---|---|---|
| `-m slow` / `-m "not slow"` | 1 / 1120 | 227 / 894 |
| Быстрый уровень | — | 894 passed, 72.7 с |
| Полный прогон | 1121 passed, 611.2 с | 1121 passed, 601.8 с |
| Выборочный тест на одном примере | 224 с | 2.2 с |

Пробное слияние с текущей базой (`26aeab6`) — без конфликтов. Issue закрывается при merge.
