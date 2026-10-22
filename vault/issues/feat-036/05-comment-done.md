## Реализация завершена

**Ветка:** `feat/feat-036/run-from-workbook` (worktree `.worktrees/feat-036`, от `numerical_scheme/implementation` `83a5838`)
**План:** `vault/plans/feat-036 run-from-workbook.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..feat/feat-036/run-from-workbook`

### Изменения
- `gpn_multiphase_solver/report/pipeline.py`: `run_case` принимает книгу Excel (`EXCEL_SUFFIXES`: `.xlsx`, `.xlsm`, `.xls`, `.xlsb` без учёта регистра); `_translate_workbook` — книга внутри каталога вывода — отказ, перевод в памяти (книга с ошибкой каталог не трогает), очистка каталога вывода, `output/input/` (`config.json` и CSV), расчёт по переводу без второй очистки; файл каталога вывода, открытый в другой программе, — отказ с подсказкой до расчёта; печать «Книга: …», ошибки с путём книги; явный `n_profiles` проверяется первым.
- `gpn_multiphase_solver/cli.py`: справка `run` о книге и очистке «по книге — до него»; «Ошибка книги: …» с кодом 2.
- `gpn_multiphase_solver/io/workbook_template.py`: строка «Run» листа COMMENTS; `configs/INPUT_TEMPLATE_v1.xlsx` пересоздана.
- `examples/22_workbook_input/`: книга-шаблон, `main.py` — обёртка `run` по книге, README с эталонными числами.
- `tests/test_examples.py`, `tests/test_energy_matrix_examples.py`, `examples/check_energy_balance_all.py`: пример 22 в общих проверках (книга переводится во временный каталог), в сверке матрицы энергии и в сводной проверке баланса.
- `README.md` §3.6 «Книга ввода Excel» (`template`, `run книга.xlsx`, `convert`), §2, §3.4, §3.5, §4; `examples/README.md`; `CHANGELOG.md`; `CLAUDE.md`.

### Тесты
- Было: 2421 тест
- Стало: 2461 (+40: 17 — новый `tests/test_workbook_run.py`, 3 — `test_cli.py`, 19 — `test_examples.py`, 1 — `test_energy_matrix_examples.py`)
- Быстрый уровень: 2176 passed, 1 skipped; полный: 2460 passed, 1 skipped (черновик книги руководителя вне git), 662 с
- Все зелёные: ✅

### Пример 22 (код worktree)
| Величина | Значение |
|---|---|
| время | 25 с (расчёт 14.8 с) |
| $T(r_w)$ на 30 сут | 350.105 К ($T_0$ = 350 К) |
| $p(r_w)$, $q_o$ | 10.071 МПа, $3.5618\cdot10^{-5}$ м³ст/с |
| невязка баланса энергии | $5.47\cdot10^{-15}$ |
| невязка баланса массы, нефть / газ | $2.4\cdot10^{-10}$ / $1.6\cdot10^{-8}$ |
| проверка $R_s$ | 73 ячейки с газом, $\max\|R_s - R_s^{eq}\| = 7.1\cdot10^{-15}$ |

Попутно (аудит 1): у расчёта по конфигу файл каталога вывода, открытый в другой программе, ломает очистку после расчёта — зарегистрирован DEBT-082.
