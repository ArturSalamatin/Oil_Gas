### Контекст при открытии

- **Ветка:** `feat/feat-022/daily-bhp-schedule-examples` (от `numerical_scheme/implementation` после вливания FEAT-021)
- **Коммит:** `91485a4` (ветка `feat/feat-021/large-drainage-radius-example`; FEAT-021 в базу не влит)
- **Фаза roadmap:** FEAT-022 — примеры и демонстрация; зависит от FEAT-021 (#39); закрывает п. 1, 3, 4, 5 мотивации FEAT-019
- **Формулы:** новых нет; `problem_statement.tex`: `eq:bc_p_ext`, `eq:bc_Sg_ext`, `eq:bc_flux_well`, `eq:bc_flux_well_gas` (расхождение: постановка не описывает закрытие скважины при p_0 ≤ p_wf)
- **Модуль:** `numerical_solver/examples/13a_*/`, `13b_*/`; `examples/example_runner.py`, `examples/closed_form.py`, `examples/energy_balance.py`; `numerical_solver/gpn_multiphase_solver/io/output.py` (время в сутках)
- **Оценка сложности:** средний — ядро не меняется; основной риск — сходимость на скачках p_wf вверх в 13б (закрытие скважины внутри итераций Ньютона), проверяется замером первым шагом
