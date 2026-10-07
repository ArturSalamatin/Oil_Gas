### Контекст при открытии

- **Ветка:** `feat/feat-018/stepped-history-schedule`
- **Коммит:** `00af963`
- **Фаза roadmap:** FEAT-018 — временная сетка и вывод результатов; зависимость DEBT-013 закрыта (#26); форма записи согласуется с DEBT-014 (без issue)
- **Формулы:** новых нет; подгонка подшагов $n_{sub} = \lceil \Delta t_{hist} / \Delta t_{int} \rceil$, $\Delta t_{actual} = \Delta t_{hist} / n_{sub}$ (`TimeSchedule.substeps`, `simulator.py:60-74`); постановка `numerical_solver/doc/problem_statement.tex` без изменений
- **Модуль:** `numerical_solver/gpn_multiphase_solver/io/config.py` (разбор и валидация `time.history`)
- **Оценка сложности:** простой (варианты Б/В — только парсер); средний, если будет решено добавить свой `dt_integration` у блока (вариант Г, затрагивает ядро)
- **Уточнение к записи в реестре:** побитовое совпадение с равномерным расписанием гарантировано только при кратности всех интервалов `dt_integration`; мелкий шаг вывода меньше `dt_integration` автоматически мельчит и шаг интегрирования
