## Реализация завершена

**Ветка:** `refactor/debt-063/unify-grid-prototype-centers` (worktree `.worktrees/debt-063`, от `numerical_scheme/implementation` `948678c`)
**План:** `vault/plans/debt-063 unify-grid-prototype-centers.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-063/unify-grid-prototype-centers`

### Изменения
- `numerical_solver/doc/problem_statement.tex`: `eq:cell_center` — середина ячейки по $\ln r$, $r_j = \sqrt{r_{j-1/2}r_{j+1/2}}$; почему (одна сетка с гидродинамикой; Дюпюи точен при любом центре); веса `eq:face_interp` на логарифмической сетке равны. Сборка — 0 ошибок, 0 неопределённых ссылок.
- `gpn_multiphase_solver/grid/log_radial.py`: центры — `np.sqrt(faces[:-1]*faces[1:])`, побитово как у `RadialGrid` прототипа; `_cell_centers_mass` (формула $\exp\langle\ln r\rangle$ с ветвью тонкого слоя) удалена.
- `tests/test_grid.py`: эталон $N = 3$ ($\sqrt{0.5}$), `TestCellCenterGeometricMean` (середина по $\ln r$, равные веса) вместо `TestCenterMassVerification`, докстринг `test_flux_exact_for_any_N`.
- `tests/test_prototype_adapter.py`: новый `TestGridsMatchPrototype` (×3, грани / центры / объёмы побитово); `TestMassBalance` — докстринг по факту, `atol` 0.02 → 1e-6 (гарантия критерия Ньютона 3.7e-7).
- `tests/test_val001.py`, `tests/test_factory_standing_hydro.py`: `rtol` 1e-2 → 1e-12 — давление прототипа теперь сверяется в его центрах (было 8.5e-4 и 1.03e-4 — разница точек).
- README 21 примера, сводный README, `04/grid_convergence.py`, `05/closed_form_convergence.py`, `18/prototype_input.py`, `tests/test_examples.py` (комментарии): 108 замен + 13 строк сводной таблицы — сверка с замкнутым решением, численный фронт, радиусы центров в тексте и таблицах, баланс энергии, таблицы сходимости 03 / 04 / 05.
- Заметки `vault/knowledge/decisions/` (словарь, `модули-grid-сетка`, P8, `hydro-prototype-анализ`, `порядок-реализации-модулей`) и новая заметка `vault/knowledge/numerics/центр ячейки — среднее геометрическое граней как у прототипа; выбор центра влияет только на второй порядок.md`.
- Прототип `HydroSolverPrototype/` не менялся.

### Тесты
- Было: 1699 тестов (быстрый уровень 1428 passed)
- Стало: 1703 (+4: `TestGridsMatchPrototype` ×3; в `test_grid.py` один тест заменён двумя)
- Быстрый уровень 1432 passed; полный прогон 1703 passed (595 с) ✅

### Сверка
| Проверка | Результат |
|---|---|
| Гидродинамика 23 примеров ($p$, $S_g$, $q_o$) | побитово как до правки |
| $T$ примеров | $\le 10^{-5}$ К; член теплопроводности баланса 10–21 — −0.6…−5.1 % |
| Вывод 28 скриптов примеров на новом коде против вывода при планировании (подмена формулы) | совпал; различия — только пути к конфигу и время счёта |
| Баланс энергии и фронты (`energy_*`, `fronts`) | 133 пары совпали |
| `table41_check.py after` / `readme_radii.py` | 0 нарушений / пусто |
| Порядок сходимости давления к замкнутому решению, пример 05 | 1.16 → 0.93 (первый, как у схемы против потока; прежний — артефакт разницы точек) |
