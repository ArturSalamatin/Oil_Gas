### Контекст при открытии

- **Ветка:** `refactor/debt-028/compute-fluxes-shutin-upwind`
- **Коммит:** `c51e137`
- **Мотивация:** тестовый путь потоков `compute_fluxes` при $p_{wf} > p[0]$ считает закачку через забой вместо закрытия скважины по `eq:bc_pwf_shutin`, на этом стоят 82 теста; выбор ячейки выше по потоку записан в пакете дважды, и у адаптера он не совпадает с прототипом при $k_{ro} = 0$ (по коду, замером не проверено).
- **Затронутые модули:** `gpn_multiphase_solver/fluxes.py`, `gpn_multiphase_solver/hydro/prototype_adapter.py`, `tests/test_fluxes.py`, `tests/test_energy.py`, `tests/test_energy_matrix_examples.py`
- **Оценка сложности:** простой (вариант 1) / средний (с правкой адаптера и побитовой сверкой историй примеров)
