## Реализация завершена

**Ветка:** `refactor/debt-010/docstring-eq-labels` (worktree `.worktrees/debt-010`, от `numerical_scheme/implementation` `98ff4a6`)
**План:** `vault/plans/debt-010 docstring-eq-labels.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-010/docstring-eq-labels`

### Изменения
- `numerical_solver/gpn_multiphase_solver/` — 30 ссылок в 7 файлах (`state.py`, `fluxes.py`, `grid/log_radial.py`, `energy/tridiag.py`, `energy/balance.py`, `energy/base.py`, `pvt/base.py`): номера уравнений, ссылка на строку `.tex` и форма `eq. bc_Sg_ext` → метки `eq:*`. $Q_{ad}$ — `eq:Qad_disc` с пометкой «$c_r = 0$, DEBT-057»; $\Phi_\alpha$ — «определение под `eq:energy_conv_face`».
- `numerical_solver/tests/test_energy.py`, `test_examples.py`, `test_prototype_adapter.py`; `examples/two_phase_analytics.py`, `examples/closed_form.py`; README примеров 03 и 11 — ещё 12 ссылок.
- `numerical_solver/tests/test_eq_references.py` (новый) — тест-сторож: (а) нет `eq. N`, `ур. N`, `eq. имя`, `.tex:N`, `.tex, строки`; (б) каждая метка `eq:`, `sec:`, `ssec:`, `sssec:`, `app:` из `.py` и README примеров объявлена в `doc/problem_statement.tex`.
- `CLAUDE.md` — правило «ссылка меткой, не номером» в разделе «Связь формула → код».
- `vault/knowledge/decisions/словарь-код-физика.md` — 23 номера и 2 ссылки на разделы → метки; разделы 5–6 (энергия, коэффициенты СЛАУ) переписаны по адвективной схеме BUG-012.

### Проверка
- Сторож: до правок — 42 нарушения в 14 файлах, после — 0; на временном файле с `(eq. 8)` и `eq:no_such_label` оба теста краснеют.
- Проба `vault/issues/debt-010/probes/ast_same.py`: AST 12 изменённых `.py` без докстрингов совпадает с базой — логика не изменилась.
- Прототип не тронут.

### Тесты
- Было: 1677 тестов (быстрый уровень 1415 passed)
- Стало: 1679 (+2 новых); быстрый уровень 1417 passed
- Полный прогон: 1679 passed, 10 мин 36 с ✅
