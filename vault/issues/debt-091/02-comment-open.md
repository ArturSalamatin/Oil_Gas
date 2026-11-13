### Контекст при открытии

- **Ветка:** `refactor/debt-091/wheels-delivery-archive`
- **Коммит:** `e000a3b`
- **Мотивация:** Устранить асимметрию и необходимость повторной распаковки архивов в поставке для расчётов – объединить колёса, распакованные примеры, документацию и README в единый архив `gpn-multiphase-solver-wheels-X.Y.Z.zip`, оставив `README.md` отдельным файлом рядом.
- **Затронутые модули:** `tools/release.py`, `numerical_solver/README.md`, `CLAUDE.md`, `numerical_solver/tests/test_packaging.py`.
- **Оценка сложности:** простой
