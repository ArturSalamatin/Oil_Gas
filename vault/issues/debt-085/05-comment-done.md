## Реализация завершена

**Ветка:** `refactor/debt-085/balance-figure-titles` (worktree `.worktrees/debt-085`, от `numerical_scheme/implementation` `48d7967`)
**План:** `vault/plans/debt-085 balance-figure-titles.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-085/balance-figure-titles`

### Изменения
- `report/energy_balance.py`, `report/mass_balance.py`: обязательный аргумент `title`, как у `plot_relperm` и `plot_pvt`. Подпись в две строки: заголовок расчёта и «Баланс энергии» или «Баланс массы компонентов». Имени каталога конфигурации в подписи больше нет.
- `report/pipeline.py`: `run_case` передаёт свой заголовок обеим функциям.
- `examples/23_source_tree_run/main.py`: вызовы с `title`.
- `report/relperm.py`, `report/pvt.py`: среднее тире во второй строке подписей ОФП и PVT.
- `tests/test_public_api.py`: `test_balance_figures_titled_by_argument`.
- `tests/test_workbook_run.py`: фикстура `case` перехватывает рисунки, `test_figure_titles_from_book` сверяет подписи всех рисунков расчёта по книге и полноту перехвата.
- `CHANGELOG.md`: пункт DEBT-085 в «Не выпущено → Изменено».

### Тесты
- Было: 2650 тестов
- Стало: 2652 теста (+2 новых), до правки кода оба падали (`TypeError` и подпись балансов «input»)
- Полный прогон: 2651 passed, 1 skipped, 765 с
- Быстрый уровень: 2357 passed, 1 skipped
- Все зелёные: ✅

Пример 22, посчитанный командой пакета из worktree: рисунки балансов подписаны «22_workbook_input», в подписях ОФП и PVT стоит среднее тире. Числа расчётов не изменились.

Пункт журнала записан в действующей форме, одним абзацем. DEBT-086 вводит новую форму пунктов и её проверку, и тот, кто вливается вторым, приводит пункт DEBT-085 к новой форме.
