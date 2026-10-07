## Реализация завершена

**Ветка:** `refactor/debt-038/pvto-branch-checks` (worktree `.worktrees/debt-038`, от `ecacacc`)
**План:** `vault/plans/debt-038 pvto-branch-checks.md`
**Коммиты:**
```
0a4b6e0 docs: README 04 — требования к веткам oil_pvt.csv (DEBT-038)
503ca3f test: комментарий фикстуры ветви из одной строки — CSV-путь фабрики и XLSX-ридер её отвергают, BlackOilPVT принимает (DEBT-038)
e551d4c feat: фабрика проверяет ветви oil_pvt.csv до BlackOilPVT — не меньше двух строк, давление и p_b(R_s) строго растут, пустая таблица; 8 тестов (DEBT-038)
```

### Изменения
- `numerical_solver/gpn_multiphase_solver/factory.py`: новая функция `_check_pvto_branches(oil_rows, oil_pvt_file)` рядом с `_check_rs0_in_table`. Вызывается в `_create_pvt` до `BlackOilPVT`. Правила:
  - таблица не пуста;
  - в ветви $R_s$ не меньше двух строк;
  - давление внутри ветви строго растёт по порядку файла;
  - давление насыщения $p_b$ строго растёт с $R_s$.

  Нарушение — `ValueError` с именем файла, $R_s$ ветви и давлениями в МПа.
- `numerical_solver/tests/test_factory_prototype.py`: раздел G, класс `TestPVTOBranches`, 8 тестов через `from_config`. Ветвь из одной строки проверяется в середине и последней, опечатка в $R_s$ — отдельно. Ещё случаи: повтор давления, давление не по возрастанию, немонотонная $p_b$, пустая таблица, чередование строк ветвей (последняя таблица корректна и должна проходить).
- `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_pvto_vectorized.py`: исправлен комментарий фикстуры «one-row branch». Код `radial_blackoil/` не менялся.
- `numerical_solver/examples/04_table_table/README.md`: требования к веткам `oil_pvt.csv`.
- Vault, коммитом на базовой ветке: заметки P8 и json-config-schema. Описание колонок табличного пути в json-config-schema было неверным и исправлено.

### Тесты
- Было: 1289 тестов (быстрый уровень 1053).
- Стало: 1297 (+8), быстрый уровень 1061. До реализации 7 из 8 новых тестов были красными, как ожидалось планом.
- Полный прогон: 1297 passed (317 с). Тесты прототипа: 97 passed. Все зелёные: ✅
- После влития в базу (DEBT-037 уже влит, база 1299) ожидается 1307 тестов. Общих файлов с DEBT-037 нет.
