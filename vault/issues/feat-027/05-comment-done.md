## Реализация завершена

**Ветка:** `feat/feat-027/undersaturated-oil-viscosity` (worktree `.worktrees/feat-027`, база `c5cb103` — после DEBT-034)
**План:** `vault/plans/feat-027 undersaturated-oil-viscosity.md`
**Коммиты** (`git log --oneline numerical_scheme/implementation..HEAD`):
- `86d88bb` vault: начало реализации
- `4034d9f` feat: ветвь Била в `StandingFullPVT`
- `c0b74ff` feat: параметр `pvt.mu_o_undersaturated` в конфиге и фабрике
- `304f607` test: VAL-001 против решения Кирхгофа
- `0ce4406` feat: подпись PVT-графиков
- `f7ba5ac` vault: заметка PVT, схема JSON

### Изменения
- `pvt/standing.py`:
  - `mu_o` при `mu_o_undersaturated="beal"` считает выше $p_b(R_s)$ по формуле $\mu_o = \mu_{ob} + \beta(\mu_{ob})\max(p - p_b, 0)$ (Бил–Стендинг), где $\beta$ — новый `_beal_slope`;
  - удалены мёртвая ветвь «выше $p_b$» (обе ветви `np.where` давали одно значение) и неиспользуемый `_mu_o_at_pb`;
  - по умолчанию `"none"`: вязкость, как и раньше, зависит только от $R_s$, флаг `co_undersaturated` её больше не касается.
- `io/config.py`: поле `PVTConfig.mu_o_undersaturated = "none"`.
- `factory.py`: передача поля в `StandingFullPVT`; значение `"beal"` при `model = "table"` даёт `ValueError` (у таблицы вязкость выше $p_b$ задают её ветви).
- `examples/pvt_plot.py`: подпись `_describe` перечисляет свойства, горизонтальные выше $p_b$. Для всех примеров она совпадает с прежней.
- vault: `pvt-корреляции-стендинг.md` (Бил вместо Васкеса–Беггса, таблица расходимости), `json-config-schema.md`, `открытые вопросы проектирования.md`.

### Тесты
- Было: 1145 тестов
- Стало: 1165 тестов (+20)
  - `test_pvt.py` — 12;
  - `test_config.py` — 2;
  - `test_factory_standing_hydro.py` — 2;
  - `test_val001.py` — 3;
  - `test_examples.py` — 1.
- Полный прогон: 1165 passed, 666 с ✅
- Существующие тесты не менялись.

### Метрики (VAL-001 с вязкостью Била против решения Кирхгофа)
| Метрика | Значение | Допуск | Статус |
|---|---|---|---|
| $q_\text{точн}$ (Кирхгоф) | 4.2597423435e-3 м³ст/с | rel 1e-9 | ✅ |
| $q_\text{Бил}/q_\text{Дюпюи}$ | 0.932299 | rel 1e-6 | ✅ |
| $e_{20} = q/q_\text{точн} - 1$ | −1.0235e-3 | (−1.5e-3, −0.5e-3) | ✅ |
| $e_{20}/e_{40}$ (порядок 1) | 1.974 | (1.8, 2.2) | ✅ |
| Бил против Васкеса–Беггса, пример 20, $p$ = 33 МПа | 1.033892 / 1.034385 | $|\Delta| < 10^{-3}$ | ✅ |
| Вязкость конечна при $p_b < 0$ ($R_s = 0$), $p$ = 33 МПа | ×1.401884 | конечно, ≤ 1.4019 | ✅ |
