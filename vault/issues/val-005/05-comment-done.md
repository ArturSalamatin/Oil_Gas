## Реализация завершена

**Ветка:** `val/val-005/prototype-template-example` (worktree `.worktrees/val-005`, от `numerical_scheme/implementation` `9acb14d`)
**План:** `vault/plans/val-005 prototype-template-example.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..val/val-005/prototype-template-example`

### Изменения
- `numerical_solver/examples/18_prototype_input/prototype_input.py`: перевод книги прототипа в `config.json` и CSV (СИ), применимость эталона IMEX T07, прогон прототипа (`run_workbook`), сверка (метрики авторов прототипа), рисунки `prototype_profiles.png`, `prototype_rates.png`
- `numerical_solver/examples/18_prototype_input/{config.json, oil_pvt.csv, gas_pvt.csv, relperm.csv}`: вывод конвертации `INPUT_TEMPLATE.xlsx`; теплофизика и плотности — значения примера 14 (в книге их нет)
- `numerical_solver/examples/18_prototype_input/main.py`, `README.md`: расчёт с температурой, сверка с прототипом и CMG IMEX
- `numerical_solver/tests/test_examples.py`: 18 в списках; фикстура `prototype_18`, класс `TestPrototypeInput` (9 тестов)
- `numerical_solver/tests/test_energy_matrix_examples.py`, `numerical_solver/tests/conftest.py`: 18 в сверке матрицы; `prototype_18` — тяжёлая фикстура
- `numerical_solver/examples/README.md`: 18 во всех таблицах и перечнях

### Тесты
- Было: 1592 тестов
- Стало: 1619 тестов (+27: класс 9, общие параметризованные 16, проверка скриптов DEBT-046 2)
- Все зелёные: ✅ (полный прогон 1619 passed, 563 с)

### Метрики (валидация)
| Метрика | Значение | Tolerance | Статус |
|---|---|---|---|
| против прототипа, max\|Δp\| (22 отметки) | 0.0054 бар | 0.02 бар | ✅ |
| против прототипа, max\|ΔS_g\| / max\|ΔR_s\| | 3.1e-4 / 0.0017 | 1e-3 / 0.005 | ✅ |
| против прототипа, q_o / q_g / GOR | 0.006 / 0.068 / 0.067 % | 0.2 % | ✅ |
| против IMEX T07, max\|Δp\| (1–30 сут) | 0.1373 бар (авторы 0.1374) | 0.15 бар | ✅ |
| против IMEX T07, max\|ΔS_g\| / RMSE S_g / max\|ΔR_s\| | 0.0046 / 0.00227 / 0.0445 | 0.005 / 0.0025 / 0.05 | ✅ |
| против IMEX T07, q_o / q_g / GOR | 0.51 / 2.59 / 2.62 % (авторы 0.51 / 2.52 / 2.56) | 0.6 / 3 / 3 % | ✅ |
| ΔT(r_w), все записи после пуска | −0.64…−0.20 К | (−1, −0.1) К | ✅ |
| баланс энергии / массы газа | 3.1e-15 / 1.6e-8 | 1e-12 / 1e-6 | ✅ |

Проверка доказывает перевод книги, адаптер и шаг по времени; гидродинамику считает Ньютон прототипа, для температуры внешнего эталона нет. Заметка: `vault/knowledge/validation/решатель на книге прототипа совпадает с прототипом до 0.005 бар, с CMG IMEX — на уровне приёмки авторов.md`.
