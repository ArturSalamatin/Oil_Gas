## Реализация завершена

**Ветка:** `refactor/debt-076/std-density-sign-check` (worktree `.worktrees/debt-076`, от `numerical_scheme/implementation` `e480af7`)
**План:** `vault/plans/debt-076 std-density-sign-check.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-076/std-density-sign-check`

### Изменения
- `numerical_solver/gpn_multiphase_solver/io/config.py`: блок «PVT» в `_validate` после породы — `pvt.rho_o_std` ≤ 0 или `pvt.rho_g_std` ≤ 0 → `ValueError` «`pvt.rho_o_std = -850.0 кг/м³: плотность нефти при стандартных условиях (не пластовая) должна быть > 0`», при любой модели PVT, до фабрики; предел в комментариях полей `PVTConfig`.
- `numerical_solver/tests/test_config.py`: класс `TestValidationPVT` — 5 значений (−850, 0 у нефти; −0.85, 0, −5e-324 у газа) × модели `standing` / `table` + 3 пары плотностей конфигов проекта; строка в докстринге модуля.
- `numerical_solver/tests/test_workbook_format.py` (FEAT-033): `test_excel_not_stricter_than_program` — `assert stricter == set(), sorted(stricter)`; докстринги без исключения для плотностей.
- `numerical_solver/gpn_multiphase_solver/io/workbook_format.py`: комментарий над `Param("pvt.rho_o_std", …)`.
- Vault: P8 §5 (строка `_validate`, абзац «PVT»), `json-config-schema.md` («Ограничения:» секции `pvt`), заметка о книге Excel версии 1, план FEAT-035; выходы проб `probes/*.after.out.txt`.

Отступление от плана: во влитом FEAT-033 есть решение 65 — постоянные строки книги намеренно строже JSON, тест их пропускает. Докстринги теста и заметка о книге поэтому говорят «кроме постоянных строк», а не «исключений нет».

### Пробы
| случай | до | после |
|---|---|---|
| таблица PVT, пример 18, `rho_o_std` = −850 | расчёт молча, $\Delta T(r_w)$ = −3.02 К вместо −0.23 К | отказ `load_config`: `pvt.rho_o_std = -850.0 кг/м³: …` |
| Стендинг, пример 03, 4 случая | отказ `from_config` «Начальное состояние пересыщено газом» / `ZeroDivisionError` | отказ `load_config` с именем поля во всех 4 |
| исходный конфиг примера 18 | $T(r_w)$ = 349.7666 К | то же, дословно |

### Тесты
- Было: 2116 тестов (быстрый уровень 1840)
- Стало: 2129 (+13), быстрый уровень 1853
- Полный прогон: 2129 passed (584 с), сторож меток `test_eq_references.py` 13 passed — ✅
