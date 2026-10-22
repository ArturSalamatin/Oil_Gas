### Контекст при открытии

- **Ветка:** `feat/feat-028/pvto-style-pvt-plot`
- **Коммит:** `b38471b` (рабочее дерево с незакоммиченными правками DEBT-034)
- **Фаза roadmap:** FEAT-028 — примеры и демонстрация; зависит от FEAT-017 (#25, влит); перед реализацией влить DEBT-034 (#53); связано с FEAT-027 (#54)
- **Формулы:** новых нет; $\rho_o$ — `eq:rho_oil` (`problem_statement.tex`), остальное — вызовы `FullPVT` (`Rs_eq`, `pb`, `Bo`, `mu_o`, `rho_o`)
- **Модуль:** `numerical_solver/gpn_multiphase_solver/io/output.py` (`plot_pvt_properties`), `numerical_solver/examples/pvt_plot.py` (`plot_pvt`)
- **Оценка сложности:** средний — код рисунка несложный, но семь открытых вопросов оформления и переписывание ~8 тестов; PNG всех 20 примеров перегенерировать
