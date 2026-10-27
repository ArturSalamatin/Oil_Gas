### Контекст при открытии

- **Ветка:** `refactor/debt-089/release-with-handover`
- **Коммит:** `386cb9a`
- **Мотивация:** архив передачи должен быть привязан к метке и храниться в Releases рядом с колёсами, а отказ передачи – откатывать выпуск до push (решение пользователя 2026-10-27).
- **Затронутые модули:** `tools/release.py`, `tools/handover.py` (докстринг и общий путь архива), `numerical_solver/README.md`, `numerical_solver/CHANGELOG.md`, `numerical_solver/tests/test_release_notes.py`, `CLAUDE.md`
- **Оценка сложности:** средний – около 40 строк кода в `release.py` и 5 в `handover.py`, правка README под шесть файлов; основной риск – проверка без настоящего выпуска (проба `release.build` на `v1.0.6`) и вывод дочернего процесса в консоль
