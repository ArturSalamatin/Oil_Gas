## Реализация завершена

**Ветка:** `refactor/debt-074/vault-notes-eq-labels` (worktree `.worktrees/debt-074`, от `numerical_scheme/implementation` `9a8eb3e`)
**План:** `vault/plans/debt-074 vault-notes-eq-labels.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-074/vault-notes-eq-labels`

### Изменения
- `numerical_solver/tests/test_eq_references.py`: `VAULT`, `_vault_lines()` и три теста — `test_vault_notes_no_numeric_equation_references` (запрещённые формы `FORBIDDEN` по заметкам `vault/knowledge/` без `literature/`), `test_vault_notes_label_references_exist` (каждая метка заметок есть в `problem_statement.tex`), `test_vault_checks_skip_without_vault` (без `vault/` — поставка заказчику — проверки пропускаются). Код пакета и прототип не менялись.
- 12 заметок `vault/knowledge/`: 40 замен — 37 ссылок на постановку (номера уравнений, параграфов, строк `.tex`) → метки по смыслу текста, 3 номера чужих документов → «формула (N) у Автор Год». Применены пробой `vault/issues/debt-074/probes/plan_apply.py --write`: каждый «До» найден ровно один раз; после — 0 нарушений, 0 отсутствующих меток; остаток числовых форм вне `FORBIDDEN` — 6 строк, все — чужие документы и местная нумерация.
- `CLAUDE.md`, «Связь формула → код»: правило называет заметки `vault/knowledge/`.
- Заметка результатов: `vault/knowledge/debugging/номера уравнений в заметках проектного этапа не соответствовали ни одной редакции постановки — заметки ссылаются метками.md`.

### Тесты
- Было: 1996 тестов (база выросла с плановых 1993 на 3 теста влитого DEBT-073)
- Стало: 1999 тестов (+3 новых)
- Быстрый уровень: 1720 → 1723 passed; полный прогон: 1999 passed (581 с)
- Все зелёные: ✅

Коммит теста `4aaa39d` стоит раньше коммита заметок `c8f263e`: сам по себе он красный (падает `test_vault_notes_no_numeric_equation_references`), начиная с `c8f263e` — зелёный. Порядок оставлен по решению пользователя.
