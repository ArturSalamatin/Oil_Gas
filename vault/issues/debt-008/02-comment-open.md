### Контекст при открытии

- **Ветка:** `refactor/debt-008/dead-config-fields`
- **Коммит:** `26ddb34`
- **Мотивация:** 12 полей конфига принимают любые значения (проба: `grid.type` = «ЭТО_ЧУШЬ_А_НЕ_СЕТКА», `newton_max_iter = -3`, `rs_switch_tol = -1` — `_validate` и фабрика проходят, прототип работает со своими умолчаниями), а P8 и докстринг `NumericsConfig` обещают, что они передаются решателю.
- **Затронутые модули:** `io/config.py` (`load_config`, `_validate`), `factory.py`, `hydro/prototype_adapter.py`, прототип `radial_blackoil/blackoil.py`, `log.py` (смежное), 30 JSON, 13 README примеров, P8, `json-config-schema.md`.
- **Порядок:** после BUG-022 (#82) и DEBT-048 (#78) — те же строки `NumericsConfig` и `blackoil.py`.
- **Оценка сложности:** средний (кода немного, но 30 JSON, 13 README и правка прототипа с побитовой проверкой эталона).
