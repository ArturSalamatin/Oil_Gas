### Контекст при открытии

- **Ветка:** `refactor/debt-086/release-notes-format`
- **Коммит:** `1ac708d`
- **Мотивация:** описание выпуска первым читает получатель выпуска – команда заказчика; сейчас каждый перенос строки журнала становится `<br>`, пункт – сплошной абзац.
- **Затронутые модули:** `.claude/commands/implement.md` (4.1), `.claude/commands/merge.md`, `tools/release.py` (`build`, `NOTES_TAIL`, докстринг), `numerical_solver/tests/test_packaging.py`
- **Оценка сложности:** простой
