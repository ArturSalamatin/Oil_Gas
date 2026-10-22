### Контекст при открытии

- **Ветка:** `feat/feat-020/oil-rate-control` (от `numerical_scheme/implementation`)
- **Коммит:** `a8e7e6c`
- **Фаза roadmap:** FEAT-020 (зависит от FEAT-022 #40 — влит)
- **Формулы:** `problem_statement.tex`: `eq:bc_p_well`, `eq:pwf_history`, `eq:bc_flux_well`, `eq:bc_flux_well_gas`, JT-вклад забойной грани (строки 1697-1701, `eq:QJT_disc`); подраздел об управлении по дебиту — дописать
- **Модуль:** `numerical_solver/gpn_multiphase_solver/` — `bc.py`, `io/config.py`, `factory.py`, `hydro/prototype_adapter.py`, `state.py`, `energy/tridiag.py`, `simulator.py`, `fluxes.py`; пример — `numerical_solver/examples/14_oil_rate_ramp_up/`
- **Оценка сложности:** средний — физика в прототипе готова; работа в контракте `HydroResult.p_wf` (8 конструкторов), проброс через 4 слоя, точный тест согласованности двух управлений и постобработка примеров
