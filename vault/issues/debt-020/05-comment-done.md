## Реализация завершена

**Ветка:** `refactor/debt-020/unified-face-conductance` (worktree `.worktrees/debt-020`, от `numerical_scheme/implementation` `6cf8515`)
**План:** `vault/plans/debt-020 unified-face-conductance.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-020/unified-face-conductance`

### Изменения
- `numerical_solver/gpn_multiphase_solver/energy/tridiag.py`:
  - `compute_conductive_transmissibility` возвращает массив `Q_T` $[N+1]$ по номеру грани (`Q_T[0] = 0` — Нейман, `Q_T[N]` — контур), без ветви `if N > 1`;
  - `assemble_tridiag(…, Q_T, …)` собирает $a, b, c$ по `eq:tridiag_a`…`eq:tridiag_c` операциями над массивами на всех строках; ГУ — точечные поправки (`a[0]`, $\Phi^+$ грани 0 не входит в `b[0]`, `c[N-1]`, `d[N-1]`); цикла по ячейкам и ветви $N = 1$ нет;
  - `solve` передаёт `Q_T` в сборку и `Q_T[N]` в накопитель баланса (`balance.py` не менялся).
- `numerical_solver/tests/test_energy.py`: вызовы под новую сигнатуру; +3 теста — `test_wellbore_face_phi_plus_not_in_matrix` (Φ⁺ забойной грани не входит в сборку, $N = 1, 2, 5$), `test_two_cells_rows_by_formulas` ($N = 2$ по формулам постановки), `test_face_indexed_array` (форма $[N+1]$, `Q_T[0] = 0` точно).
- `numerical_solver/tests/test_val002.py`, `test_energy_matrix_examples.py` (только самопроверка эталона, сам эталон DEBT-016 не тронут): вызовы под новую сигнатуру.
- `numerical_solver/tests/test_examples.py`, `examples/02_single_phase_jt/main.py`: ссылки `tridiag.py:NNN` → имена методов.
- `vault/knowledge/decisions/словарь-код-физика.md` — §5.2, §5.4, §6; новая заметка `vault/knowledge/numerics/сдвиг матрицы энергии на 1 ULP не меняет записанных T — …`.

### Тесты
- Было: 1699 тестов (быстрый уровень 1428)
- Стало: 1702 тестов (+3), быстрый уровень 1431
- Все зелёные: ✅ — полный прогон после шага 3: 1702 passed (619 с); итоговый полный прогон на вершине кода (`be58cca`) — 1702 passed (646 с)

### Побитовая сверка (`vault/issues/debt-020/probes/bits_capture.py`)
| Сравнение | Синтетика (800) | 07 | 10 | 11 | 14 | 16 | Статус |
|---|---|---|---|---|---|---|---|
| хеши $a, b, c, d$ на каждом вызове `solve`, base → после шага 2 | ✓ | 72 | 73 | 72 | 361 | 720 | ✅ побитово |
| то же, base → после шага 3 | ✓ | 72 | 73 | 72 | 361 | 720 | ✅ побитово |
| записанные поля $T$, base → шаг 3 | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✅ побитово |

Чувствительность пробы — 1 ULP в одном элементе матрицы (отрицательный контроль при планировании); сверка одного поля $T$ такой сдвиг не видит.
