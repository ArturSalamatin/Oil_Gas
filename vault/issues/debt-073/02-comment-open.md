### Контекст при открытии

- **Ветка:** `refactor/debt-073/relperm-mobile-oil-edge`
- **Коммит:** `a7b0dc0`
- **Мотивация:** обрезанная таблица ОФП с $k_{ro} > 0$ в последнем узле принимается молча и даёт отказ первого шага с советом про шаг по времени, хотя причина — таблица.
- **Затронутые модули:** `gpn_multiphase_solver/factory.py` (`_check_relperm_table`, `create_relperm`), `gpn_multiphase_solver/simulator.py` (`_failure_message`) или `hydro/prototype_adapter.py` (`_failure_details`), `vault/knowledge/decisions/P8-формат-ввода-json.md`
- **Рекомендуемый вариант:** 1 + 3 (предупреждение фабрики + признак таблицы в тексте отказа, как факт); вариант 2 (`ValueError`) — по решению пользователя
- **Проверено при открытии:** все 18 таблиц ОФП проекта кончаются узлом $k_{ro} = 0$ ($S_g$ = 0.8–1) — проверка их не затронет. `_sg_activation_cap` сдвинулся: `blackoil.py:118-123` (в реестре 111-116). Тест DEBT-071 `test_relperm_above_table_before_failure` пока только в плане DEBT-071 — порядок с ней решить при планировании
- **Оценка сложности:** простой
