### Контекст при открытии

- **Ветка:** `refactor/debt-014/compact-history-configs`
- **Коммит:** `98ff4a6`
- **Мотивация:** 22 конфига записывают расписание повтором одинаковых объектов (2337 объектов против 80 в краткой форме), правка режима требует скрипта, замысел расписания в файле не виден; парсер краткую форму уже принимает (FEAT-018).
- **Затронутые модули:** 22 конфига (`examples/01…15, 19, 21`, `configs/baseline.json`, `configs/table_pvt/config.json`, `configs/val001.json`); тесты `tests/test_energy_balance_examples.py::_run_schedule`, `tests/test_config.py::TestHistoryBlocks::test_baseline_as_blocks`; генератор `examples/04a_high_gas_saturation/rewrite_history.py` (удалить); README 04a, 15. Код пакета не меняется.
- **Оценка сложности:** простой
