## Реализация завершена

**Ветка:** `refactor/debt-045/readme-energy-conduction-table` (worktree `.worktrees/debt-045`, от `numerical_scheme/implementation` `fba5d08`)
**План:** `vault/plans/debt-045 readme-energy-conduction-table.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-045/readme-energy-conduction-table`

### Изменения
- `numerical_solver/examples/README.md` — таблица баланса энергии: $E_{\text{конд}}$ у 14 — $-9.97\cdot10^{8}$ (было $-1.41\cdot10^{8}$), у 20 — $+8.78\cdot10^{6}$ (было $-1.04\cdot10^{8}$); абзац под таблицей — кондуктивный член отрицателен только у 14, у остальных примеров с $\lambda \ne 0$ положителен.
- README примеров 08, 09, 12, 13a, 13b, 14, 15, 19, 20, 21 — невязка баланса энергии по замеру после DEBT-043: $0 \ldots 8.7\cdot10^{-16}$ вместо $2.4\cdot10^{-14} \ldots 3.5\cdot10^{-11}$.
- README примера 03 — в перечне проверок пороги теста `test_energy_balance_examples.py` ($10^{-12}$; на укороченном конфиге 03 — $10^{-14}$) вместо уровня до DEBT-043 ($10^{-13}$…$10^{-12}$).
- Код, тесты, конфиги не менялись: изменены 12 файлов README.

### Проверка
- Замер на коде ветки (`vault/issues/debt-045/probes/impl_energy_table.out.txt`, 21 пример) побитово совпал с замером плана (без учёта времени счёта).
- Все 12 изменённых чисел сверены с выводом замера; строки 14 и 20 сводной таблицы совпадают с README самих примеров 14 и 20.
- Историческая скобка «до DEBT-043 … было» в README 04 не тронута.

### Тесты
- Было: 1344 теста
- Стало: 1344 (+0 новых)
- Все зелёные: ✅ — полный прогон 1344 passed (391 с), быстрый уровень 1108 passed, `TestReadme` 55 passed
