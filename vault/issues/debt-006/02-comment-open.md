### Контекст при открытии

- **Ветка:** `refactor/debt-006/factory-explicit-proto-access`
- **Коммит:** `3dd0638`
- **Мотивация:** фабрика выбирает, отдать ли прототипу общий объект таблицы или создать новый, по приватным полям обёрток; переименование поля `PrototypeRPAdapter._rp` молча подменит табличную ОФП прототипа пересчётом на 101 узле — рассогласование с нашими модулями без ошибки и без предупреждения.
- **Затронутые модули:** `gpn_multiphase_solver/factory.py` (3 проверки `hasattr`: строки 450, 460, 472), `gpn_multiphase_solver/pvt/prototype_adapter.py`, `gpn_multiphase_solver/pvt/table_full.py`, `tests/test_factory_prototype.py`, `tests/test_factory_standing_hydro.py`
- **Исходный замер:** 1493 теста собрано на `3dd0638`
- **Рекомендуемый вариант:** 2 — публичные свойства обёрток + `isinstance` в фабрике; ABC не трогать
- **Оценка сложности:** простой
