"""Аудит 1 DEBT-085: правки плана на копии дерева – дословно по блокам «До/После», по фазам.

Фазы: tests1 (шаг 1, п. 1–2), code1 (шаг 1, п. 4–7), tests2 (шаг 2, п. 1), code2 (шаг 2, п. 2–3).
Каждый блок «До» обязан встретиться в файле ровно столько раз, сколько указано, –
иначе Edit при реализации не найдёт old_string.

Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-085\\probes\\audit_apply.py <корень копии numerical_solver> <фаза>
"""

import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
PHASE = sys.argv[2]

API = "tests/test_public_api.py"
WBR = "tests/test_workbook_run.py"
EB = "gpn_multiphase_solver/report/energy_balance.py"
MB = "gpn_multiphase_solver/report/mass_balance.py"
PL = "gpn_multiphase_solver/report/pipeline.py"
M23 = "examples/23_source_tree_run/main.py"
RP = "gpn_multiphase_solver/report/relperm.py"
PV = "gpn_multiphase_solver/report/pvt.py"

TESTS1 = [
    # ── test_public_api.py: импорты, помощник, тест ──
    (API, "from gpn_multiphase_solver.io.config import load_config  # noqa: E402\n",
     "from gpn_multiphase_solver.io.config import load_config  # noqa: E402\n"
     "from gpn_multiphase_solver.io.figures import save_figure  # noqa: E402\n", 1),
    (API, "from gpn_multiphase_solver.pvt.relperm import CoreyRP  # noqa: E402\n",
     "from gpn_multiphase_solver.pvt.relperm import CoreyRP  # noqa: E402\n"
     "from gpn_multiphase_solver.report import energy_balance, mass_balance  # noqa: E402\n", 1),
    (API, "    return SimulationHistory(times=[0.0, 10.0], balance=[zero, last])\n",
     r'''    return SimulationHistory(times=[0.0, 10.0], balance=[zero, last])


def _mass_history():
    """История из двух записей запаса компонентов: нефть 100 → 90 м³ст, добыто 12, притекло 2."""
    snaps = [dict(M_o=100.0, M_g=0.0, cum_o_well=0.0, cum_o_ext=0.0,
                  cum_g_well=0.0, cum_g_ext=0.0),
             dict(M_o=90.0, M_g=0.0, cum_o_well=-12.0, cum_o_ext=-2.0,
                  cum_g_well=0.0, cum_g_ext=0.0)]
    return SimulationHistory(times=[0.0, 1.0], mass_balance=snaps)
''', 1),
    (API, "        plt.close(axes[0].figure)\n\n\n@pytest.mark.parametrize(\"sg_max, n_panels\"",
     r'''        plt.close(axes[0].figure)


def test_balance_figures_titled_by_argument(tmp_path, monkeypatch):
    """Рисунки балансов подписаны заголовком из аргумента title: первая строка – он, вторая – название рисунка.

    Прежде подпись бралась из имени каталога файла конфигурации: у
    расчёта по книге это перевод output/input/ – «input» (DEBT-085).
    Конфигурация – configs/baseline.json: имени её каталога в подписи
    быть не должно. Рисунок функция закрывает сама, поэтому он
    перехватывается подменой save_figure; закрытый Figure сохраняет оси.
    """
    figures = {}

    def keep(fig, path, dpi):
        """Запомнить рисунок по имени файла, затем записать как обычно."""
        figures[Path(path).name] = fig
        return save_figure(fig, path, dpi)

    monkeypatch.setattr(energy_balance, "save_figure", keep)
    monkeypatch.setattr(mass_balance, "save_figure", keep)
    cfg = load_config(BASELINE)
    energy_balance.plot_energy_balance(_energy_history(), None, cfg, tmp_path, "Расчёт")
    mass_balance.plot_mass_balance(cfg, _mass_history(), tmp_path, "Расчёт")

    # Баланс энергии – заголовок верхней оси (plot_energy_balance_series)
    assert figures["energy_balance.png"].axes[0].get_title() == "Расчёт\nБаланс энергии"
    # Баланс массы – общий заголовок фигуры. Figure.get_suptitle – с
    # matplotlib 3.8, пакет допускает 3.7: читается поле _suptitle
    assert (figures["mass_balance.png"]._suptitle.get_text()
            == "Расчёт\nБаланс массы компонентов")


@pytest.mark.parametrize("sg_max, n_panels"''', 1),
    # ── test_workbook_run.py: импорты, фикстура, распаковка, тест ──
    (WBR, "import gpn_multiphase_solver.report.pipeline as pipeline\n",
     "import gpn_multiphase_solver.report.energy_balance as energy_balance\n"
     "import gpn_multiphase_solver.report.mass_balance as mass_balance\n"
     "import gpn_multiphase_solver.report.pipeline as pipeline\n"
     "import gpn_multiphase_solver.report.pvt as report_pvt\n"
     "import gpn_multiphase_solver.report.relperm as report_relperm\n", 1),
    (WBR, "from gpn_multiphase_solver.io import workbook_format as wf\n",
     "from gpn_multiphase_solver.io import workbook_format as wf\n"
     "from gpn_multiphase_solver.io.figures import save_figure\n", 1),
    (WBR, r'''@pytest.fixture(scope="module")
def case(tmp_path_factory):
    """run_case по малой книге с кириллицей и пробелом в имени; рядом — вывод прошлого расчёта: (книга, результат, печать)."""
    folder = tmp_path_factory.mktemp("book")
    book = _small_book(folder / "малая книга.xlsx")
    _old_output(folder)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = run_case(book)
    return book, r, buf.getvalue()
''', r'''@pytest.fixture(scope="module")
def case(tmp_path_factory):
    """run_case по малой книге с кириллицей и пробелом в имени; рядом – вывод прошлого расчёта: (книга, результат, печать, рисунки по именам файлов)."""
    folder = tmp_path_factory.mktemp("book")
    book = _small_book(folder / "малая книга.xlsx")
    _old_output(folder)
    figures = {}

    def keep(fig, path, dpi):
        """Запомнить рисунок по имени файла, затем записать как обычно."""
        figures[Path(path).name] = fig
        return save_figure(fig, path, dpi)

    # Рисунки закрываются сразу после записи: перехват save_figure во всех
    # модулях штатного набора оставляет их объекты для проверки подписей
    # (DEBT-085). Фикстура модульная – monkeypatch функций здесь недоступен
    buf = io.StringIO()
    with pytest.MonkeyPatch.context() as mp, contextlib.redirect_stdout(buf):
        for module in (pipeline, report_relperm, report_pvt, energy_balance, mass_balance):
            mp.setattr(module, "save_figure", keep)
        r = run_case(book)
    return book, r, buf.getvalue(), figures
''', 1),
    (WBR, "    book, r, _ = case\n", "    book, r, _, _ = case\n", 2),
    (WBR, "    book, r, text = case\n", "    book, r, text, _ = case\n", 1),
    (WBR, "    assert lines[1] == f\"Книга: {book}\"\n",
     r'''    assert lines[1] == f"Книга: {book}"


def test_figure_titles_from_book(case):
    """Все рисунки штатного набора подписаны именем книги первой строкой, рисунки балансов – тоже.

    Ловит: подпись рисунков балансов из имени каталога файла
    конфигурации – у книги это перевод output/input/, и выходило «input»
    вместо имени книги (DEBT-085). Подпись рисунка – общий заголовок
    фигуры, если он есть (PVT, баланс массы), иначе заголовок верхней оси.
    """
    book, _, _, figures = case
    # Перехвачены все записанные рисунки: рисунок модуля без подмены
    # save_figure выпал бы из проверки молча
    assert set(figures) == {p.name for p in (book.parent / "output").glob("*.png")}

    def heading(fig):
        # Figure.get_suptitle – с matplotlib 3.8, пакет допускает 3.7
        return (fig._suptitle.get_text() if fig._suptitle is not None
                else fig.axes[0].get_title())

    titles = {name: heading(fig) for name, fig in figures.items()}
    assert titles["energy_balance.png"] == "малая книга\nБаланс энергии"
    assert titles["mass_balance.png"] == "малая книга\nБаланс массы компонентов"
    for name, text in titles.items():
        assert text.startswith("малая книга\n"), (name, text)
''', 1),
]

CODE1 = [
    (EB, "def plot_energy_balance(history, grid, config, output_dir: Path):\n",
     "def plot_energy_balance(history, grid, config, output_dir: Path, title: str):\n", 1),
    (EB, '''    config : SimulationConfig
        Конфигурация расчёта: имя каталога файла конфигурации – в
        заголовке рисунка.
    output_dir : str or pathlib.Path
        Каталог результатов; создаётся, если его нет.
''', '''    config : SimulationConfig
        Конфигурация расчёта; не используется, оставлена ради порядка
        аргументов.
    output_dir : str or pathlib.Path
        Каталог результатов; создаётся, если его нет.
    title : str
        Заголовок рисунка: первая строка, вторая – «Баланс энергии».
''', 1),
    (EB, '''    bal = compute_energy_balance(history)
    # Имя расчёта берём из пути к конфигу (папка конфига): модуль общий для всех расчётов.
    axes = plot_energy_balance_series(
        bal, title=f"Баланс энергии — {Path(config.config_dir).name}")
''', r'''    bal = compute_energy_balance(history)
    # Заголовок расчёта – от вызывающего (run_case), как у plot_relperm и
    # plot_pvt: имя каталога конфигурации у книги – «input» (DEBT-085)
    axes = plot_energy_balance_series(bal, title=f"{title}\nБаланс энергии")
''', 1),
    (MB, "def plot_mass_balance(config, history, output_dir: Path) -> dict | None:\n",
     "def plot_mass_balance(config, history, output_dir: Path, title: str) -> dict | None:\n", 1),
    (MB, '''    config : SimulationConfig
        Конфигурация расчёта: имя каталога файла конфигурации – в
        заголовке рисунка.
    history : SimulationHistory
        История расчёта: запас компонентов на записях и накопленные потоки.
    output_dir : str or pathlib.Path
        Каталог результатов; создаётся, если его нет.
''', '''    config : SimulationConfig
        Конфигурация расчёта; не используется, оставлена первым
        аргументом, как у ``plot_relperm`` и ``plot_pvt``.
    history : SimulationHistory
        История расчёта: запас компонентов на записях и накопленные потоки.
    output_dir : str or pathlib.Path
        Каталог результатов; создаётся, если его нет.
    title : str
        Заголовок рисунка: первая строка, вторая – «Баланс массы
        компонентов».
''', 1),
    (MB, '''    # Имя расчёта — из пути к конфигу (папка конфига): модуль общий для всех расчётов.
    fig.suptitle(f"Баланс массы компонентов — {Path(config.config_dir).name}")
''', r'''    # Заголовок расчёта – от вызывающего (run_case), как у plot_relperm и
    # plot_pvt: имя каталога конфигурации у книги – «input» (DEBT-085)
    fig.suptitle(f"{title}\nБаланс массы компонентов")
''', 1),
    (PL, "    plot_energy_balance(history, grid, config, output_dir)\n",
     "    plot_energy_balance(history, grid, config, output_dir, title)\n", 1),
    (PL, "    plot_mass_balance(config, history, output_dir)\n",
     "    plot_mass_balance(config, history, output_dir, title)\n", 1),
    (PL, "    # на подшагах внутри решателя, а не восстанавливаются по записям.\n",
     "    # на подшагах внутри решателя, а не восстанавливаются по записям.\n"
     "    # Заголовок – тот же, что у остальных рисунков (DEBT-085).\n", 1),
    (M23, "    plot_energy_balance(history, grid, config, OUT)\n",
     "    plot_energy_balance(history, grid, config, OUT, title)\n", 1),
    (M23, "    plot_mass_balance(config, history, OUT)\n",
     "    plot_mass_balance(config, history, OUT, title)\n", 1),
]

TESTS2 = [
    (WBR, '        assert text.startswith("малая книга\\n"), (name, text)\n',
     r'''        assert text.startswith("малая книга\n"), (name, text)
    # Разделитель второй строки ОФП и PVT – среднее тире (правило «Тире»)
    assert titles["relperm.png"].startswith("малая книга\nОФП – "), titles["relperm.png"]
    assert titles["pvt.png"].startswith("малая книга\nPVT – "), titles["pvt.png"]
''', 1),
]

CODE2 = [
    (RP, '                               title=f"{title}\\nОФП — {_describe(config)}")\n',
     '                               title=f"{title}\\nОФП – {_describe(config)}")\n', 1),
    (PV, '    fig.suptitle(f"{title}\\nPVT — {_describe(config)}", fontsize=10)\n',
     '    fig.suptitle(f"{title}\\nPVT – {_describe(config)}", fontsize=10)\n', 1),
]

PHASES = {"tests1": TESTS1, "code1": CODE1, "tests2": TESTS2, "code2": CODE2}

for rel, old, new, count in PHASES[PHASE]:
    path = ROOT / rel
    # newline="" – концы строк как есть: у файла с CRLF блоки сверяются в CRLF
    text = path.read_text(encoding="utf-8", newline="")
    if "\r\n" in text:
        old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
    found = text.count(old)
    assert found == count, f"{rel}: «До» найдено {found} раз, ожидалось {count}:\n{old[:120]}"
    path.write_text(text.replace(old, new), encoding="utf-8", newline="")
    print(f"{PHASE}: {rel} – правка легла ({count})")
