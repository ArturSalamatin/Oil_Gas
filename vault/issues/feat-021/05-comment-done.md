## Реализация завершена

**Ветка:** `feat/feat-021/large-drainage-radius-example`
**План:** `vault/plans/feat-021 large-drainage-radius-example.md`
**Коммиты** (`git log --oneline numerical_scheme/implementation..HEAD`):
- `e4b9f31` vault: FEAT-021 начало реализации (baseline 861 passed, 383 с)
- `1583564` feat: пример 12 — большая область дренирования, 15 сут (FEAT-021)
- `1b53f4c` docs: README примеров — пример 12 в индексе и сводных таблицах (FEAT-021)
- vault-коммит с результатом (этот комментарий, реестр, заметка)

### Изменения
- `numerical_solver/examples/12_large_drainage_radius/`: `config.json` ($R_{ext} = 200$ м, $p_0 = 15.5$ МПа, история 15 × 86400 с, `dt_integration` 3600 с), копии `oil_pvt.csv`, `gas_pvt.csv`, `relperm.csv`, `main.py`, `README.md`
- `numerical_solver/tests/test_examples.py`: 12 в `ALL_EXAMPLES` и `NEEDS_SG_SECTION`; класс `TestLargeDrainageRadius` (контурная ячейка однофазна на всей истории; GOR строго убывает и на 15 сут выше $R_s^0$)
- `numerical_solver/tests/test_energy_matrix_examples.py`: 12 в `ALL_EXAMPLES` и `SUBDIVIDING_EXAMPLES` (первый подшаг 128 × 28.125 с)
- `numerical_solver/examples/README.md`: 12 в «С какого начать», новый раздел, таблицы времени, замкнутого решения, проверки $R_s$, баланса энергии, общие параметры

Пример 11 не изменён.

### Тесты
- Было: 861 (383 с)
- Стало: 879 (+18), 463 с
- Все зелёные: ✅

### Контрольные числа примера 12 (15 сут)

| Величина | Значение |
|---|---|
| записей истории | 16 |
| $q_o$ / GOR | $3.2365\cdot10^{-3}$ м³ст/с / 36.67 (стационар: $3.2827\cdot10^{-3}$ / 30) |
| $S_g(r_w)$ | 0.0239 (стационар 0.0193) |
| $T(r_w)$ | 345.303 К |
| контурная ячейка | $\min_t p_{N-1} - p_b = +419$ кПа, $S_{g,N-1} \equiv 0$ |
| баланс энергии | $1.70\cdot10^{-11}$ (порог $10^{-10}$) |
| время `main.py` | 33.6 с |

Физический вывод оформлен заметкой `vault/knowledge/science/давление и газонасыщенность выходят на стационар вместе — различается амплитуда.md`.

Открытые вопросы, не вошедшие в задачу (решение за пользователем): текст «за 3 суток» в `examples/temperature_asymptotics.py:123`; учёт недонасыщенной нефти при $p < p_b$ в `rs_analytics`; `time.start_day` в DEBT-008; устаревший докстринг модуля `tests/test_examples.py`.
