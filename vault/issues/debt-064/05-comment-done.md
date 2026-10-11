## Реализация завершена

**Ветка:** `refactor/debt-064/energy-note-advective-form` (worktree `.worktrees/debt-064`, от `numerical_scheme/implementation` `eedc718`)
**План:** `vault/plans/debt-064 energy-note-advective-form.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-064/energy-note-advective-form`

### Изменения (только vault, код и тесты не менялись)
- `vault/knowledge/decisions/модули-energy-tridiag.md` — переписана (161 строка): контракт `EnergySolver` с `bc: BoundaryConditions`, обязательство `collect`, порядок `solve` в 12 пунктах, таблица «величина → метод → метка `.tex` → раздел словаря», проектные решения (адвективная форма BUG-012, массивы граней $[N+1]$, забой, контур, выбор ячейки выше по потоку, отклонения $\theta$, проба матрицы, прогонка). Формул дивергентной формы и ссылок номерами нет; 19 меток `eq:…` существуют в `problem_statement.tex`, все `[[…]]` разрешаются.
- `vault/knowledge/decisions/конвенции-знаков.md` — дискретная форма JT по `eq:QJT_disc` (адвективная) вместо `J_face[j+1] − J_face[j]`; ссылки `eq:residual_oil`, `eq:main_QJT_muJT` вместо номеров.
- `vault/knowledge/decisions/словарь-код-физика.md` — подпись ссылки на заметку (не «коэффициенты СЛАУ» — они в словаре §6); §6: равенство $b_j - |a_j| - |c_j| = \text{cap}_j$ в строках $0 \dots N-2$, в строке контура больше на $Q_T[N] - \Phi^-_N$.
- `vault/knowledge/decisions/модули-hydro-newton.md`, `P6-тепловые-свойства.md` — подписи ссылок на заметку.
- `vault/knowledge/literature/` Salimi 2012 (`:109`, `:111`), Abadpour 2009 (`:104`) — ссылки на словарь §5/§5.7 и метки вместо разделов прежней заметки; «JT-поток $J$» → «JT-вклад $\mathcal J_j$». Выводы заметок не менялись.
- 19 заметок `vault/knowledge/decisions/` — висячие `[[architecture-numerical-solver]]` и `[[открытые-вопросы-проектирования]]` → по имени файла; поле `name:` у `архитектура библиотеки numerical_solver.md` и `открытые вопросы проектирования.md` = имя файла.
- `vault/knowledge/decisions/P8-формат-ввода-json.md` — эскиз `EnergyUnitDecorator.solve(..., bc, collect=None)` передаёт `collect` дальше; пометка «эскиз, в коде не реализован».

### Тесты
- Было: 1722 теста
- Стало: 1722 теста (код не менялся: `git diff` по `numerical_solver/` от базы пуст)
- Быстрый уровень на базе worktree: 1451 passed
- Полный прогон в worktree: 1722 passed, 1 warning, 569 с ✅

### Проверки (шаг 7 плана)
- В `vault/knowledge/` нет `J_face`, `J_cell`, `R_face`, `Phi_well_plus`, «JT-поток», «eq. 31», `[[architecture-numerical-solver]]`, `[[открытые-вопросы-проектирования]]` (поиск с учётом регистра).
- `name:` ≠ имени файла — только устаревшие `vault/ref_*.md` (по решению не трогались).

### Не входит
- 22 ссылки номерами уравнений в 7 заметках `vault/knowledge/` (`модули-hydro-newton` 7, `вопрос-кондуктивная-проводимость` 4, `грабли-реализации` 4, `модули-grid-сетка` 4, `P8` 1, ещё 2) — регистрация отдельной задачей по решению пользователя.
