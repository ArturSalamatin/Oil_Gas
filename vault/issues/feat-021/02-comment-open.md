### Контекст при открытии

- **Ветка:** `feat/feat-021/large-drainage-radius-example`
- **Коммит:** `17d2400`
- **Фаза roadmap:** FEAT-021, примеры и демонстрация; блокирующих зависимостей нет
- **Формулы:** новых нет — `problem_statement.tex`: `eq:bc_p_ext` ($p(R_{ext}) = p_0$), `eq:bc_Sg_ext` ($S_g = 0$, $R_s = R_s^0$ на контуре)
- **Модуль:** `numerical_solver/examples/12_<имя>/` (код библиотеки не меняется); тесты — `tests/test_examples.py`, `tests/test_energy_matrix_examples.py`
- **Параметры:** копия примера 11 с `R_ext = 200` м и `p0 = 15.5` МПа; `N = 50`, 72 ч
- **Оценка сложности:** простой
