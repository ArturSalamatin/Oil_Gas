## Реализация завершена

**Ветка:** `refactor/debt-068/rock-compressibility-sign` (worktree `.worktrees/debt-068`, от `numerical_scheme/implementation` `6adea25`)
**План:** `vault/plans/debt-068 rock-compressibility-sign.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-068/rock-compressibility-sign`

### Изменения
- `numerical_solver/gpn_multiphase_solver/io/config.py`: в `_validate` после проверок `porosity`, `permeability` — `ValueError` при `rock.compressibility < 0`, текст `rock.compressibility = <значение> 1/Па < 0: …`; комментарий — физика $c_r$, загрузчик прототипа, замер до правки, отсутствие верхней границы.
- `numerical_solver/tests/test_config.py`: `TestValidationRock` — `test_negative_compressibility_rejected` ($-4.5\cdot10^{-10}$, $-10^{-9}$, $-2\cdot10^{-9}$, $-5\cdot10^{-324}$) и `test_nonnegative_compressibility_accepted` (0, $4.5\cdot10^{-10}$).
- `numerical_solver/doc/problem_statement.tex`: $c_r \ge 0$ в допущении у `eq:porosity`; $C_p \ge 0$ при любой $S_g$ ⇔ $c_{ot} \ge -c_r$, $c_g \ge -c_r$ (при $c_r \ge 0$ достаточно $c_{ot}, c_g \ge 0$); «при $c_{ot} < -c_r$ … некорректно» после `eq:D_operator`. Сборка — 39 стр., без неопределённых ссылок.
- `vault/knowledge/decisions/P8-формат-ввода-json.md` §5, `json-config-schema.md`: ограничение $c_r \ge 0$ с замером; заодно `porosity` ≤ 1 и λ ≥ 0 по коду.
- Прототип, конвертер примера 18, конфиги и примеры не менялись.

### Тесты
- Было: 1932 теста
- Стало: 1938 (+6 новых)
- Все зелёные: ✅ (полный прогон 1938 passed, 628 с; быстрый уровень 1662 passed)

### Проба на ветке (`vault/issues/debt-068/probes/red_state_green.out.txt`, конфиг примера 18, 2 сут)
| $c_r$, 1/Па | До | После |
|---|---|---|
| $+4.5\cdot10^{-10}$, 0 | расчёт, $q_o$ на 1 сут 2.22 / 2.162 м³ст/сут | то же |
| $-4.5\cdot10^{-10}$, $-10^{-9}$ | расчёт молча, $q_o$ на 6 и 14 % ниже | `ValueError` в `load_config` |
| $-2\cdot10^{-9}$ … $-2\cdot10^{-8}$ | `RuntimeError` после dt/512 ($C_p < 0$) | `ValueError` в `load_config` |
