## Реализация завершена

**Ветка:** `feat/feat-033/workbook-input-format` (worktree `.worktrees/feat-033`, от `numerical_scheme/implementation` `d736795`)
**План:** `vault/plans/feat-033 workbook-input-format.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..feat/feat-033/workbook-input-format` — `47aea89`…`ef86e93`, 6 коммитов

### Изменения
- `numerical_solver/gpn_multiphase_solver/io/workbook_format.py` (новый) — таблица полей формата версии 1:
  - MODEL 14 строк, THERMAL 10, NUMERICS 11;
  - SCHEDULE, OIL_PVT, GAS_PVT, RELPERM;
  - пределы как у программы;
  - `UNIT_TO_SI`, `DERIVED`, `NOT_FROM_WORKBOOK`.
- `numerical_solver/gpn_multiphase_solver/io/workbook_template.py` (новый) — генератор на XlsxWriter:
  - Key, Unit, заголовки и версия формата заблокированы; защита листов без пароля;
  - выпадающие списки и проверки данных Excel;
  - демо-значения с 15 значащими цифрами;
  - книга собирается в памяти, файл создаётся `open(path, "xb")`.
- `numerical_solver/gpn_multiphase_solver/cli.py`, `__main__.py` — подкоманда `gpn-solver template книга.xlsx`. Код 0 — шаблон записан; код 2 — файл уже существует (не меняется), не `.xlsx` или не записывается.
- `numerical_solver/pyproject.toml` — `XlsxWriter>=3.2` в `dependencies`.
- `numerical_solver/gpn_multiphase_solver/units.py` — `HOUR_TO_S`.
- `numerical_solver/configs/INPUT_TEMPLATE_v1.xlsx` (новый) — книга генератора, 18.5 КБ.
- Тесты:
  - `tests/test_workbook_format.py` (43): полнота полей конфига, единицы, пределы; проверка Excel не строже `load_config` — строже только плотности, DEBT-076;
  - `tests/test_workbook_template.py` (46): листы, значения, защита, проверки данных, отказ перезаписи, книга генератора;
  - `tests/test_cli.py` (+6): подкоманда `template`;
  - `tests/_xlsx.py` — чтение книги стандартной библиотекой.
- Vault: заметка «книга ввода Excel версии 1 — все параметры явно, единицы фиксированы», ссылки в P8 и в индексе.

### Тесты
- Было: 2020 тестов
- Стало: 2115 тестов (+95)
- Все зелёные: ✅ — полный прогон 2115 passed (586 с)

Прототип не менялся. Осталась приёмка книги в Excel пользователем: защита, списки, сообщения проверок.

### Доработка по замечаниям (решения 64–69 плана, `915968b`)
- Слова `none` в книге нет. h0 и Newton cell tolerance — числа > 0; h0 ≥ Δt отключает нарастание шага.
- Jacobian mode = grouped и Linear solver = sparse — постоянные значения, ячейки заблокированы.
- Комментарии на двух языках:
  - столбец «Комментарии» (F) по-русски на MODEL, THERMAL, NUMERICS;
  - столбец C по-русски на COMMENTS;
  - в теме Units объяснено, что такое bar(a), Sm3, rm3.
- RELPERM:
  - обязательные строки Sg = 0 (krg = 0) и Sg = 1 (kro = 0), эти ячейки заблокированы;
  - промежуточные точки добавляются и удаляются вставкой и удалением строк — лист защищён без пароля, вставка и удаление строк разрешены;
  - в демо добавлена строка (1, 0, 0.8), расчёт не меняется.
- Комментарии без минуса U+2212 и тире. Тексты sg_switch_tol, max_active_set_iter, newton_max_iter, newton_cell_tol переписаны.
- Тестов 2116, полный прогон 2116 passed (597 с).
- Проверить в Excel: строка, вставленная сразу под строкой Sg = 0, наследует её заблокированные ячейки.
