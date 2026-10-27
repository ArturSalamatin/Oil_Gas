## Реализация завершена

**Ветка:** `refactor/debt-087/changelog-header-dash` (worktree `.worktrees/debt-087`, от `numerical_scheme/implementation` `027e38c`)
**План:** `vault/plans/debt-087 changelog-header-dash.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-087/changelog-header-dash`

### Изменения
- `numerical_solver/CHANGELOG.md`: шапка (вступление и «Правило номеров») переписана по тексту плана – 9 длинных тире заменены средним или развёрнуты в предложения с глаголом, сняты точки с запятой в строках 5 и 17, «меняются» → «изменяются»; служебный образец `## <номер> — <дата>` в обратных кавычках остался. Содержание правила номеров то же. Пункт DEBT-087 в «Не выпущено», «Изменено».
- `numerical_solver/tests/test_packaging.py`: проверка знаков строки выделена из `_changelog_format_problems` в `_changelog_symbol_problems` (сообщения те же) и применена к шапке – до первого заголовка раздела выпуска (`CHANGELOG_RELEASE_HEAD_RE`: `## Не выпущено` или `## X.Y.Z — <дата>`), поэтому проверка действует и в самопроверке `tools/release.py`. Новые тесты `test_changelog_header_symbols` (шапка настоящего журнала) и `test_changelog_header_sample` (образец в форме дерева метки).
- `tools/release.py`, `.claude/text-check.py`, пакет `gpn_multiphase_solver` не изменялись – числа расчётов те же.

### Тесты
- Было: 2675 тестов
- Стало: 2677 тестов (+2 новых)
- `-k changelog`: 18 → 20 passed; быстрый уровень 2382 passed, 1 skipped; полный 2676 passed, 1 skipped
- На шапке базы `027e38c` проверка находит 7 строк с длинным тире (11, 17, 19, 23, 26, 31, 32), на новой – 0
- Проба `vault/issues/debt-087/probes/header_check.py`: шапка совпадает с `header_new.md`, описание выпуска функциями `release.py` то же, что со старой шапкой
- Все зелёные: ✅
