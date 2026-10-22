## Реализация завершена

**Ветка:** `refactor/debt-065/unify-isobar-radius` (worktree `.worktrees/debt-065`, от `numerical_scheme/implementation` `3f3df63`)
**План:** `vault/plans/debt-065 unify-isobar-radius.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-065/unify-isobar-radius`

### Изменения
- `diagnostics/rs.py`: новая `isobar_radius(r, p, pb, R_ext, p_ext)` — интерполяция $\ln r$ по $p$ с узлом контура $(R_{ext}, p_{ext})$. Краевые случаи:
  - давление ниже $p_b$ во всех ячейках — интерполяция до контура;
  - $p_{ext} < p_b$ — nan;
  - $p[0] \ge p_b$ — nan;
  - немонотонный профиль — первое пересечение от забоя;
  - узел контура не дальше последнего центра — `ValueError`.

  `front_radius` переведена на неё.
- `diagnostics/two_phase.py`: `degassing_front["r_b_interp"]` — через `isobar_radius`; уточнён комментарий `dupuit_check`: условие Дирихле стоит на грани контура, а не в ячейке.
- `diagnostics/closed_form.py`: `solve_closed["r_b"]` — через `isobar_radius` с узлом $(R_e, p_e)$; копия `_front_radius` удалена; дополнен докстринг модуля.
- `examples/04_table_table/grid_convergence.py`: текст печати — «от сетки не зависит» относится только к $q_o$.
- `examples/README.md`: что рисует `rs_profiles.png`, когда давление ниже $p_b$ во всех ячейках.
- `tests/test_isobar_radius.py`: 15 новых тестов, все быстрого уровня.
- vault: заметка решения о краевых случаях, ссылка в заметке о пороге подвижности Кори, `index.md`.

### Тесты
- Было: 1826 тестов (быстрый уровень 1555).
- Стало: 1841 (+15), быстрый уровень 1570.
- Полный прогон: 1841 passed (531 с) ✅

### Вывод примеров (снимок 23 `main.py` до и после)
| Пример | Результат |
|---|---|
| 22 примера | совпали побайтно (у 18 — без 4 файлов с временем выполнения прототипа) |
| 11 | печать `фронт r_b = 46.9873 м` → `47.7342 м` (опорное значение 47.7338 м); `pressure_profiles.png`, `saturation_profiles.png` — линия 47.734 м; `rs_profiles.png` — новая линия «фронт $r_b$ = 47.766 м» |

Это ровно то, что предсказали план и аудит. Рисунки примера 11 просмотрены.
