## Реализация завершена

**Ветка:** `refactor/debt-062/label-number-guard` (worktree `.worktrees/debt-062`, от `numerical_scheme/implementation` `31177be`)
**План:** `vault/plans/debt-062 label-number-guard.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-062/label-number-guard` — `bb5e24d` (тесты), `0cc7e22` (CLAUDE.md), коммит vault

### Изменения
- `numerical_solver/tests/test_eq_references.py`: в `FORBIDDEN` — шестая форма «номер после метки «eq:имя (N)»» (константа `LABEL_NUMBER`), строгий шаблон `(?<![A-Za-z])(?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+[`)}]*\s*\(\d+\)`; новый тест `test_label_number_form` (8 случаев: 5 ловит — `eq:x (74)`, `(eq:x) (80)`, `` `eq:x` (80) ``, `\eqref{eq:x} (80)`, `ssec:x (5)`; 3 пропускает — `eq:residual_oil (eq:residual_gas)`, `eq:QJT_disc (АДВЕКТИВНАЯ форма, BUG-012)`, `eq:x (3 ячейки)`).
- `numerical_solver/tests/test_energy_matrix_examples.py`: три ссылки `eq:bc_props_ext (74)` → `eq:bc_props_ext` (строки 254, 383, 805; в плане — 799, сдвиг от коммита DEBT-066). Только комментарии и докстринг: AST файла без докстрингов совпадает с базой (`vault/issues/debt-010/probes/ast_same.py`, выход `vault/issues/debt-062/probes/ast_same.out.txt`).
- `CLAUDE.md`, «Связь формула → код»: «не номером рядом с меткой (`eq:x (74)`, DEBT-062)».

### Проверка шаблона
- После шага 1 (шаблон есть, номера ещё есть): `test_eq_references.py` — **1 failed, 9 passed**, нарушений ровно 3 — те самые строки.
- После шага 2: **10 passed**; проба `label_number_survey.py` — строгий и широкий шаблоны 0 срабатываний, законный текст после меток (3 случая) на месте.

### Тесты
- Было: 1938 тестов (база `31177be`, после влития DEBT-068)
- Стало: 1946 (+8 — случаи `test_label_number_form`)
- Быстрый уровень: 1662 → 1670 passed
- Полный прогон: 1946 passed (644 с) ✅
- Прототип не тронут.
