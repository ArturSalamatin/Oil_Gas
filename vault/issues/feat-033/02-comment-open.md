### Контекст при открытии

- **Ветка:** `feat/feat-033/workbook-input-format`
- **Коммит:** `2b71387`
- **Фаза roadmap:** поставка заказчику, ввод книгой Excel: FEAT-033 → FEAT-035 → FEAT-036 → FEAT-031 (#114); FEAT-034 — параллельно; зависимостей нет
- **Формулы:** новых нет; φ₀ = φ_ref·exp(c_r(p₀ − p_ref)) — из `_REMOVED_KEYS["rock"]["p_ref"]` (`io/config.py`); (ρc_p)_s = ρ_ma·c_ma — определение под `eq:main_rhocpeff`; проверка демонстрационных значений — `eq:lambda_eff`, `eq:muJT_def` (`problem_statement.tex`)
- **Модуль:** `numerical_solver/gpn_multiphase_solver/io/` (таблица полей, генератор — имена при планировании), `cli.py` (подкоманда `template`), `pyproject.toml` (XlsxWriter)
- **Оценка сложности:** средний — формул нет. Объём даёт таблица полей (~35 строк, 7 листов), проверки данных и защита XlsxWriter, тексты Comment. Есть открытый вопрос формата: удаление строки на защищённом листе и смысл пустой ячейки Value у поля с умолчанием.
