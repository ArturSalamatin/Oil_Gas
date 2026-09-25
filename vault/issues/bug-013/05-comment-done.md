## Реализация завершена

**Ветка:** `fix/bug-013/jt-asymptote-reference-pressure`
**План:** `vault/plans/bug-013 jt-asymptote-reference-pressure.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..fix/bug-013/jt-asymptote-reference-pressure`

```
81aa249 docs: README 02, 03, 04, 04a — асимптотика от p0 (BUG-013)
d8996e3 refactor: пример 02 — асимптотика из общего модуля (BUG-013)
5d89b23 fix: JT-асимптотика отсчитывается от давления на контуре (BUG-013)
6624e7e vault: BUG-013 начало реализации (аудит раунд 3: baseline 860)
```

### Изменения
- `numerical_solver/examples/temperature_asymptotics.py`: `single_phase_asymptote` отсчитывает от `config.initial_conditions.p0` (тем же значением фабрика задаёт давление ГУ на контуре); докстринг объясняет полуячейку у контура.
- `numerical_solver/examples/02_single_phase_jt/main.py`: копия формулы с `p[-1]` заменена вызовом общего модуля; докстринг исправлен.
- `numerical_solver/tests/test_examples.py`: `test_02_relaxes_toward_jt_asymptote` берёт асимптоту из общего модуля и проверяет все ячейки, включая приконтурную (прежде исключалась и маскировала сдвиг); новый `test_single_phase_asymptote_reference_is_contour`.
- README 02, 03, 04, 04a: формула с p_0, новые печатаемые отставания.

### Тесты
- Было: 860
- Стало: 861 (+1 новый, 1 переписан)
- Все зелёные: ✅ (393 с)
- Оба теста шага 1 падали на исходном коде: приконтурная ячейка на 0.0044 К ниже старой асимптоты; `allclose` — сдвиг 0.0067 К.

### Метрики
| Метрика | До | После |
|---|---|---|
| min(T − T_as) по всем ячейкам, 02, 3 сут | −0.0044 К | +0.0023 К |
| отставание у забоя 02 | 0.284 К | 0.291 К |
| печать асимптоты 03 / 04 / 04a | 0.42 / 0.42 / 0.40 К | 0.44 / 0.46 / 0.41 К |
| копий формулы с `p[-1]` (`grep "mu_JT.*\[-1\])"`) | 3 | 0 |

Issue закрывается при merge ветки в `numerical_scheme/implementation`.
