## Реализация завершена

**Ветка:** `feat/feat-026/emf-figure-export` (worktree `.worktrees/feat-026`, от `4bd1e8c`)
**План:** `vault/plans/feat-026 emf-figure-export.md`
**Коммиты:** `460e681` vault → `ea62388` → `a9704fd` → `a229677` → `d94b5da` → `078bc6c` → `9ac03c3` → `3658d2b` vault

### Изменения
- `examples/figure_io.py` (новый): `save_figure` — PNG + SVG в `output/emf/` (текст кривыми); `export_emf` — SVG без пары в EMF одним запуском Inkscape; `find_inkscape` (`INKSCAPE` → PATH → `C:\Program Files\Inkscape\bin\`); `emf_enabled` (`GPN_EXAMPLES_EMF`).
- `example_runner.py`, `pvt_plot.py`, `relperm_plot.py`, `energy_balance.py`, `energy_balance_convergence.py`, `convergence.py`: `savefig` → `save_figure`; `export_emf` в `run_example` и автономных запусках.
- Скрипты примеров 01 (`main.py`, `spatial_convergence.py`), 02 (`main.py`, `check_slopes.py`), 04a (`plot_profiles_50k.py`), 05 (`main.py`, `compare_with_corey.py`, `closed_form_convergence.py`): то же.
- `tests/conftest.py`: `GPN_EXAMPLES_EMF=0` — в pytest только PNG.
- `examples/README.md`: раздел о векторных копиях, строка `figure_io.py` в таблице модулей.

Итого 18 вызовов `savefig` в 14 файлах заменены; поиск `.savefig(` по `examples/` находит только `figure_io.py`.

### Тесты
- Было: 1035 (592 с)
- Стало: 1035 (+0 новых — решение пользователя), 598 с
- Все зелёные: ✅

### Ручная проверка
| Проверка | Результат |
|---|---|
| Пример 14 | 9 PNG / 9 SVG / 9 EMF, имена совпадают; Inkscape 6.4 с |
| Пример 01 (рисунки перестраиваются после `run_example`) | два пакета: 8 и 2 рис. |
| 04a `plot_profiles_50k.py` без Inkscape | предупреждение, SVG есть, EMF нет, код 0; повтор — 4 EMF |
| GDI+ (13 EMF 04a) | тип `Emf`, физический размер = `figsize` |
| Word | за пользователем |

**Расхождение с планом:** цена векторных копий ≈10 с на пример, а не ≈5 с (пример 14: 73.1 с без копий, 85.2 с с ними; Inkscape 6.4 с + сохранение SVG ≈3 с). В README — замеренная цифра.

Слияние с текущей базой (`8eee600`, влит BUG-017) — без конфликтов (`git merge-tree`), общих файлов нет.
