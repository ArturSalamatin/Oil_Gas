

# ═══════════════════════════════════════════════════════════
# Пример 22: расчёт по книге ввода Excel (FEAT-036)
# ═══════════════════════════════════════════════════════════
# Блок дописывается в конец tests/test_examples.py

class TestWorkbookInput:
    """22_workbook_input: вход — только книга, main.py — обёртка команды run по книге.

    Книга — шаблон gpn-solver template с демонстрационными значениями
    (FEAT-033): k = 1 мД, R_e = 100 м, p_0 = 200 бар, R_s0 = 50 (p_b = 180 бар),
    p_wf 150 → 120 → 100 бар на 5 и 15 сут, 30 сут, N = 100. Общие проверки
    (балансы, границы, R_s, README) идут по её переводу, как у остальных
    примеров (_config_path); здесь — то, что задаёт книга.
    """

    NAME = "22_workbook_input"

    def test_config_from_book(self):
        """Перевод книги: таблицы PVT и ОФП, N = 100, 22 интервала на 30 сут ровно; заголовок — имя книги; стационарной аналитики нет.

        Ловит: книгу примера заменили, а README и ожидания остались прежними;
        в переводе потерян заголовок (листа OUTPUT в книге нет).
        """
        cfg = load_config(_config_path(self.NAME))
        assert cfg.pvt.model == "table" and cfg.relperm.model == "table"
        assert cfg.grid.N == 100
        assert len(cfg.time.history) == 22
        # Моменты SCHEDULE — в целых мс (FEAT-035, решение 19): сумма точна
        assert sum(h.dt for h in cfg.time.history) == 30 * 86400.0
        assert sorted({h.p_wf for h in cfg.time.history}) == [100e5, 120e5, 150e5]
        assert cfg.output.title == self.NAME
        assert cfg.output.steady_state is False

    def test_folder_holds_only_book_as_input(self):
        """В папке примера — книга, main.py, README.md; перевода (config.json, CSV) нет: вход один."""
        names = {p.name for p in (EXAMPLES_DIR / self.NAME).iterdir()
                 if p.name not in ("output", "__pycache__")}
        assert names == {"22_workbook_input.xlsx", "main.py", "README.md"}
