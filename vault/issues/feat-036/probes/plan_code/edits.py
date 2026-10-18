"""Правки плана FEAT-036 в существующих файлах: {путь от numerical_solver/: [(было, стало), …]}.

Каждое «было» встречается в файле базы ровно один раз (проверяет plan_apply.py).
База — numerical_scheme/implementation после влития FEAT-037 (до влития —
ветка feat/feat-037/solver-version-changelog): правки pipeline.py и cli.py
стоят рядом с правками FEAT-037 (строка «Версии», ключ --version).
"""

PIPELINE = "gpn_multiphase_solver/report/pipeline.py"
CLI = "gpn_multiphase_solver/cli.py"
TEMPLATE = "gpn_multiphase_solver/io/workbook_template.py"
TEST_TEMPLATE = "tests/test_workbook_template.py"
TEST_EXAMPLES = "tests/test_examples.py"
TEST_CLI = "tests/test_cli.py"
TEST_MATRIX = "tests/test_energy_matrix_examples.py"
CHECK_BALANCE = "examples/check_energy_balance_all.py"

EDITS = {
    # ── Шаг 1: run_case принимает книгу ──
    PIPELINE: [
        # 1.1 Докстринг модуля
        ("CaseResult с решателем; входные файлы внутри каталога вывода — отказ до\n"
         "расчёта. Режим matplotlib и кодировку консоли модуль не трогает —\n"
         "cli.configure_batch_run.\n"
         '"""\n',
         "CaseResult с решателем; входные файлы внутри каталога вывода — отказ до\n"
         "расчёта. Режим matplotlib и кодировку консоли модуль не трогает —\n"
         "cli.configure_batch_run.\n"
         "\n"
         "Вход — JSON-конфиг или книга ввода Excel (FEAT-036): книга переводится в\n"
         "output/input/ — вход, по которому расчёт повторяется без книги; каталог\n"
         "вывода при этом очищается до перевода (решение пользователя 2026-10-18).\n"
         '"""\n'),
        # 1.2 Импорт перевода и разбора книги
        ("from ..io.output import (plot_profiles, plot_well_rate, plot_wellbore_dynamics,\n"
         "                         save_csv, save_well_csv)\n",
         "from ..io.output import (plot_profiles, plot_well_rate, plot_wellbore_dynamics,\n"
         "                         save_csv, save_well_csv)\n"
         "from ..io.workbook_convert import workbook_to_config, write_files\n"
         "from ..io.xlsx_reader import WorkbookError, read_workbook\n"),
        # 1.3 Расширения книги и подкаталог перевода
        ("class CaseConfigError(ValueError):\n"
         '    """Конфиг не читается, не проходит проверку или не собирается фабрикой; расчёт не начат. FEAT-030."""\n',
         "# Вход run_case — книга, если расширение файла Excel (FEAT-036). Формат книги —\n"
         "# .xlsx; .xlsm разбор читает так же, а .xls и .xlsb отвергает с подсказкой,\n"
         "# как пересохранить, — понятнее отказа загрузчика JSON «Expecting value»\n"
         'EXCEL_SUFFIXES = (".xlsx", ".xlsm", ".xls", ".xlsb")\n'
         "# Подкаталог вывода с переводом книги: config.json и CSV таблиц — вход, по\n"
         "# которому расчёт повторяется командой run без книги (FEAT-036, решение 3)\n"
         'INPUT_DIR = "input"\n'
         "\n"
         "\n"
         "class CaseConfigError(ValueError):\n"
         '    """Конфиг или книга не читаются, не проходят проверку или не собираются фабрикой; расчёт не начат. FEAT-030."""\n'),
        # 1.3а Докстринг CaseRunError: у книги прежних результатов нет (аудит 1)
        ('    """Решатель отказал на шаге по времени; результаты прошлого прогона не тронуты. FEAT-030."""\n',
         '    """Решатель отказал на шаге по времени; у конфига результаты прошлого прогона не тронуты, у книги в каталоге вывода только input/. FEAT-030, FEAT-036."""\n'),
        # 1.4 Докстринг run_case
        ('    """Полный штатный расчёт по конфигу: решение → CSV + PNG + печать проверок. FEAT-030.\n'
         "\n"
         "    Все выходные файлы кладутся в output_dir (None — папка output рядом с\n"
         "    конфигом). Каталог очищается целиком после успешного расчёта (решение\n"
         "    пользователя 2026-10-13); конфиг и его CSV внутри него — отказ до расчёта.\n",
         '    """Полный штатный расчёт по конфигу или книге: решение → CSV + PNG + печать проверок. FEAT-030.\n'
         "\n"
         "    config_path — JSON-конфиг или книга ввода Excel (расширение из\n"
         "    EXCEL_SUFFIXES, FEAT-036). Все выходные файлы кладутся в output_dir\n"
         "    (None — папка output рядом с конфигом или книгой). Каталог очищается\n"
         "    целиком после успешного расчёта (решение пользователя 2026-10-13);\n"
         "    конфиг и его CSV внутри него — отказ до расчёта.\n"
         "\n"
         "    Книга: внутри output_dir — отказ до чтения; с ошибкой — отказ, каталог\n"
         "    не тронут. Переведённая книга: каталог очищается до записи перевода в\n"
         "    output_dir/input/ (решение пользователя 2026-10-18), расчёт идёт по\n"
         "    output_dir/input/config.json; при ошибке конфига или отказе решателя в\n"
         "    каталоге остаётся только input/. Заголовок по умолчанию — имя книги.\n"),
        # 1.5 Явный n_profiles — до всего, что трогает файлы; перевод книги
        ("    config_path = Path(config_path)\n"
         "    t_start = time.perf_counter()\n"
         "    # Ошибки чтения и проверки конфига — до печати и до расчёта. TypeError —\n"
         "    # лишний ключ секции (строгая распаковка dataclass), KeyError —\n"
         "    # пропущенный ключ внутри секции (time.history).\n"
         "    try:\n"
         "        config = load_config(config_path)\n"
         "    except (OSError, KeyError, TypeError, ValueError) as exc:\n"
         '        raise CaseConfigError(f"{config_path}: {exc}") from exc\n',
         "    config_path = Path(config_path)\n"
         "    t_start = time.perf_counter()\n"
         "    # Явный аргумент проверяется до всего, что трогает файлы: у книги\n"
         "    # каталог вывода очищается до расчёта (FEAT-036)\n"
         "    if n_profiles is not None and (isinstance(n_profiles, bool)\n"
         "                                   or not isinstance(n_profiles, int) or n_profiles < 2):\n"
         '        raise ValueError(f"n_profiles = {n_profiles!r}: нужно целое не меньше двух")\n'
         "    # ── Книга ввода (FEAT-036) ──\n"
         "    # Перевод в output/input/ — до чтения конфига; дальше расчёт идёт по\n"
         "    # переведённому config.json, как по любому конфигу. В печати и\n"
         "    # сообщениях об ошибках — путь книги: ключ её строки равен пути поля\n"
         "    # JSON (FEAT-035), и отказ _validate называет строку книги\n"
         "    workbook = config_path if config_path.suffix.lower() in EXCEL_SUFFIXES else None\n"
         "    if workbook is not None:\n"
         "        output_dir = (Path(output_dir) if output_dir is not None\n"
         '                      else workbook.parent / "output")\n'
         "        config_path = _translate_workbook(workbook, output_dir)\n"
         "    source = workbook if workbook is not None else config_path\n"
         "    # Ошибки чтения и проверки конфига — до печати и до расчёта. TypeError —\n"
         "    # лишний ключ секции (строгая распаковка dataclass), KeyError —\n"
         "    # пропущенный ключ внутри секции (time.history).\n"
         "    try:\n"
         "        config = load_config(config_path)\n"
         "    except (OSError, KeyError, TypeError, ValueError) as exc:\n"
         '        raise CaseConfigError(f"{source}: {exc}") from exc\n'),
        # 1.6 Значение из конфига — после чтения; явный аргумент проверен выше
        ("    if n_profiles is None:\n"
         "        n_profiles = out.n_profiles\n"
         "    elif isinstance(n_profiles, bool) or not isinstance(n_profiles, int) or n_profiles < 2:\n"
         "        # Явный аргумент проверяется здесь, а не после расчёта в _profile_times\n"
         '        raise ValueError(f"n_profiles = {n_profiles!r}: нужно целое не меньше двух")\n',
         "    if n_profiles is None:\n"
         "        n_profiles = out.n_profiles\n"),
        # 1.7 Защита входных файлов — только у конфига
        ("    _check_inputs_outside(config_path, config, output_dir)\n",
         "    if workbook is None:\n"
         "        # Перевод книги лежит в output/input/ по замыслу; саму книгу\n"
         "        # проверил _translate_workbook\n"
         "        _check_inputs_outside(config_path, config, output_dir)\n"),
        # 1.8 Печать входа
        ('    print(f"Конфиг: {config_path}")\n',
         '    print(f"Книга: {workbook}" if workbook is not None else f"Конфиг: {config_path}")\n'),
        # 1.9 Ошибка фабрики — с путём книги
        ("        # же категория: расчёт не начат\n"
         '        raise CaseConfigError(f"{config_path}: {exc}") from exc\n',
         "        # же категория: расчёт не начат\n"
         '        raise CaseConfigError(f"{source}: {exc}") from exc\n'),
        # 1.10 Комментарий к отказу решателя
        ("        # решателя написаны для пользователя. Каталог вывода не тронут:\n"
         "        # очистка — после расчёта.\n",
         "        # решателя написаны для пользователя. Каталог вывода не тронут:\n"
         "        # очистка — после расчёта (у книги — до него: в каталоге только\n"
         "        # input/, вход, на котором расчёт остановился).\n"),
        # 1.11 Очистка после расчёта — только у конфига
        ("    # прошлые результаты уцелеют.\n"
         "    if output_dir.is_dir():\n"
         "        shutil.rmtree(output_dir)\n",
         "    # прошлые результаты уцелеют. Книга — исключение: каталог очищен до\n"
         "    # перевода (_translate_workbook), в нём только input/ этого расчёта.\n"
         "    if workbook is None and output_dir.is_dir():\n"
         "        shutil.rmtree(output_dir)\n"),
        # 1.12 Перевод книги
        ('                f"каталог очищается целиком, и файл был бы удалён. Укажите "\n'
         '                f"другой каталог вывода.")\n',
         '                f"каталог очищается целиком, и файл был бы удалён. Укажите "\n'
         '                f"другой каталог вывода.")\n'
         "\n"
         "\n"
         "def _translate_workbook(workbook: Path, output_dir: Path) -> Path:\n"
         '    """Книга → output_dir/input/ (config.json и CSV таблиц), каталог вывода очищается до записи; путь config.json. FEAT-036."""\n'
         "    # Книга внутри каталога вывода — отказ до чтения: очистка удалила бы её\n"
         "    # (решение 4 черновика плана; по образцу _check_inputs_outside)\n"
         "    out, book = output_dir.resolve(), workbook.resolve()\n"
         "    if book == out or out in book.parents:\n"
         "        raise CaseConfigError(\n"
         '            f"каталог вывода {out} содержит книгу {book}: перед расчётом по книге "\n'
         '            f"каталог очищается целиком, и книга была бы удалена. Укажите "\n'
         '            f"другой каталог вывода.")\n'
         "    # Перевод в памяти — до очистки: книга с ошибкой (не .xlsx, значения\n"
         "    # ячеек) каталог вывода не трогает. Сообщение WorkbookError уже\n"
         "    # начинается с пути книги\n"
         "    try:\n"
         "        config, tables = workbook_to_config(read_workbook(workbook))\n"
         "    except WorkbookError as exc:\n"
         "        raise CaseConfigError(str(exc)) from exc\n"
         "    except FileNotFoundError as exc:\n"
         '        raise CaseConfigError(f"{workbook}: книга не найдена") from exc\n'
         "    except OSError as exc:\n"
         '        raise CaseConfigError(f"{workbook}: {exc.strerror or exc}") from exc\n'
         "    # Очистка — до записи перевода и до расчёта (решение пользователя\n"
         "    # 2026-10-18): input/ и результаты в каталоге всегда от одного запуска.\n"
         "    # Цена: при ошибке конфига или отказе решателя прежних результатов нет,\n"
         "    # остаётся input/ — вход, на котором расчёт остановился\n"
         "    if output_dir.is_dir():\n"
         "        try:\n"
         "            shutil.rmtree(output_dir)\n"
         "        except OSError as exc:\n"
         "            # Windows: файл каталога открыт в другой программе (CSV в Excel) —\n"
         "            # WinError 32, rmtree успевает удалить часть файлов (аудит 1). Расчёт\n"
         "            # ещё не начат: отказ с подсказкой, а не трассировка (у конфига — DEBT-082)\n"
         "            raise CaseConfigError(\n"
         '                f"каталог вывода {output_dir} очищен не полностью — {exc.filename}: "\n'
         '                f"{exc.strerror}. Файл открыт в другой программе? Закройте его и "\n'
         '                f"повторите расчёт.") from exc\n'
         "    try:\n"
         "        return write_files(output_dir / INPUT_DIR, config, tables)\n"
         "    except OSError as exc:\n"
         '        raise CaseConfigError(f"{output_dir / INPUT_DIR}: {exc.strerror or exc}") from exc\n'),
    ],
    # ── Шаг 2: командная строка ──
    CLI: [
        ("Перевод книги в конфиг: gpn-solver convert книга.xlsx каталог (FEAT-035) —\n"
         "config.json и CSV таблиц в СИ в новом или пустом каталоге; ошибки книги, файла\n"
         "и каталога — код 2.\n",
         "Перевод книги в конфиг: gpn-solver convert книга.xlsx каталог (FEAT-035) —\n"
         "config.json и CSV таблиц в СИ в новом или пустом каталоге; ошибки книги, файла\n"
         "и каталога — код 2.\n"
         "\n"
         "Расчёт по книге: gpn-solver run книга.xlsx (FEAT-036) — run_case переводит\n"
         "книгу в output/input/ и считает по переводу; каталог вывода очищается до\n"
         "расчёта. Ошибки книги — код 2, сообщение «Ошибка книги: …».\n"),
        ('        "run", help="расчёт по конфигу: CSV, рисунки, печать проверок",\n'
         '        description="Расчёт по JSON-конфигу: история скважины и профили (CSV), "\n'
         '                    "штатные рисунки (PNG), печать проверок.",\n'
         '        epilog="Коды возврата: 0 — расчёт завершён; 1 — решатель отказал; "\n'
         '               "2 — ошибка аргументов или конфига. Каталог вывода после "\n'
         '               "расчёта очищается целиком.")\n'
         '    run.add_argument("config", type=Path, help="JSON-конфиг расчёта")\n'
         '    run.add_argument("--output", type=Path, default=None,\n'
         '                     help="каталог результатов (по умолчанию — output рядом с "\n'
         '                          "конфигом); очищается целиком")\n'
         '    run.add_argument("--title", default=None,\n'
         '                     help="заголовок рисунков и печати (по умолчанию — "\n'
         '                          "output.title конфига или имя его папки)")\n',
         '        "run", help="расчёт по конфигу или книге Excel: CSV, рисунки, печать проверок",\n'
         '        description="Расчёт по JSON-конфигу или книге ввода Excel (.xlsx): история "\n'
         '                    "скважины и профили (CSV), штатные рисунки (PNG), печать "\n'
         '                    "проверок. Книга переводится в config.json и CSV таблиц в "\n'
         '                    "каталоге input внутри каталога вывода; по ним расчёт "\n'
         '                    "повторяется без книги.",\n'
         '        epilog="Коды возврата: 0 — расчёт завершён; 1 — решатель отказал; "\n'
         '               "2 — ошибка аргументов, конфига или книги. Каталог вывода "\n'
         '               "очищается целиком: при расчёте по конфигу — после расчёта, "\n'
         '               "по книге — до него.")\n'
         '    run.add_argument("config", type=Path, metavar="вход",\n'
         '                     help="JSON-конфиг расчёта или книга ввода Excel (.xlsx)")\n'
         '    run.add_argument("--output", type=Path, default=None,\n'
         '                     help="каталог результатов (по умолчанию — output рядом с "\n'
         '                          "конфигом или книгой); очищается целиком")\n'
         '    run.add_argument("--title", default=None,\n'
         '                     help="заголовок рисунков и печати (по умолчанию — "\n'
         '                          "output.title конфига или имя его папки; у книги — "\n'
         '                          "её имя без расширения)")\n'),
        ("    from .report.pipeline import CaseConfigError, CaseRunError, run_case\n"
         "    # Абсолютные пути: печать «Конфиг: …» однозначна при любом каталоге\n",
         "    from .report.pipeline import EXCEL_SUFFIXES, CaseConfigError, CaseRunError, run_case\n"
         "    # Абсолютные пути: печать «Конфиг: …» и «Книга: …» однозначна при любом каталоге\n"),
        ("    except CaseConfigError as exc:\n"
         '        print(f"Ошибка конфига: {exc}", file=sys.stderr)\n'
         "        return 2\n",
         "    except CaseConfigError as exc:\n"
         "        # Книга (FEAT-036): и ошибки ячеек, и отказ проверки конфига по её\n"
         "        # переводу — ключ строки книги равен пути поля JSON (FEAT-035)\n"
         '        what = "книги" if config.suffix.lower() in EXCEL_SUFFIXES else "конфига"\n'
         '        print(f"Ошибка {what}: {exc}", file=sys.stderr)\n'
         "        return 2\n"),
    ],
    # ── Шаг 3: строка «Run» листа COMMENTS ──
    TEMPLATE: [
        ("# Строку «Run» добавит FEAT-036 (решение 62)\n",
         "# Строка «Run» — расчёт по книге (FEAT-036; решение 62 FEAT-033)\n"),
        ('     "Команда gpn-solver template my_case.xlsx создаёт эту книгу с демонстрационными "\n'
         '     "значениями. Существующий файл команда не перезаписывает."),\n',
         '     "Команда gpn-solver template my_case.xlsx создаёт эту книгу с демонстрационными "\n'
         '     "значениями. Существующий файл команда не перезаписывает."),\n'
         '    ("Run",\n'
         '     "gpn-solver run my_case.xlsx runs the calculation. Results go to the folder output "\n'
         '     "next to the workbook; the folder is cleared before the run. The subfolder "\n'
         '     "output/input keeps the workbook converted to config.json and CSV tables in SI "\n'
         '     "units: gpn-solver run output/input/config.json --output new_folder repeats the "\n'
         '     "run without the workbook.",\n'
         '     "Команда gpn-solver run my_case.xlsx выполняет расчёт. Результаты записываются в "\n'
         '     "папку output рядом с книгой; перед расчётом папка очищается. В папке output/input "\n'
         '     "сохраняется книга, переведённая в config.json и таблицы CSV в единицах СИ: "\n'
         '     "команда gpn-solver run output/input/config.json --output new_folder повторяет "\n'
         '     "расчёт без книги."),\n'),
    ],
    TEST_TEMPLATE: [
        ('    assert any("gpn-solver template" in text for _, text, _ in COMMENTS)\n',
         '    assert any("gpn-solver template" in text for _, text, _ in COMMENTS)\n'
         "    # Строка «Run» — вторая, после «Template»: команда расчёта по книге на обоих\n"
         "    # языках (FEAT-036; FEAT-033 описывала только работающие команды, решение 62)\n"
         '    assert [topic for topic, _, _ in COMMENTS][:2] == ["Template", "Run"]\n'
         '    assert all("gpn-solver run my_case.xlsx" in t for t in COMMENTS[1][1:])\n'),
    ],
    # ── Шаг 4: пример 22 в тестах примеров ──
    TEST_EXAMPLES: [
        ("  A. Структура: каждая подпапка содержит config.json, main.py, README.md\n",
         "  A. Структура: каждая подпапка содержит config.json (у 22 — книгу ввода\n"
         "     Excel, FEAT-036), main.py, README.md\n"),
        ("считается один раз, при первом обращении; все 23 — около 5.5 мин.\n",
         "считается один раз, при первом обращении; все 24 — около 6 мин.\n"),
        ("import json\nfrom pathlib import Path\n",
         "import atexit\nimport functools\nimport json\nimport shutil\nimport tempfile\n"
         "from pathlib import Path\n"),
        ("from gpn_multiphase_solver.io.output import pvt_table_nodes, relperm_table_nodes\n",
         "from gpn_multiphase_solver.io.output import pvt_table_nodes, relperm_table_nodes\n"
         "from gpn_multiphase_solver.io.workbook_convert import convert_workbook\n"),
        ('    "21_rs100_cooling",\n]\n',
         '    "21_rs100_cooling",\n    "22_workbook_input",\n]\n'),
        ("# Образец обёртки без докстринга — то же, что python -m gpn_multiphase_solver\n"
         "# run <папка примера>/config.json (сравнивается дерево разбора, не текст)\n",
         "# Образец обёртки без докстринга — то же, что python -m gpn_multiphase_solver\n"
         "# run <папка примера>/<вход> (сравнивается дерево разбора, не текст); вход —\n"
         "# config.json или книга примера (WORKBOOK_EXAMPLES)\n"),
        ('    sys.exit(main(["run", str(Path(__file__).parent / "config.json")]))\n'
         "'''\n",
         '    sys.exit(main(["run", str(Path(__file__).parent / "{input}")]))\n'
         "'''\n"
         "\n"
         "# Примеры с книгой ввода Excel вместо config.json (FEAT-036): папка → книга.\n"
         "# Вход такого примера — только книга; тестам она переводится тем же\n"
         "# переводом, что и у команды run (_config_path)\n"
         'WORKBOOK_EXAMPLES = {"22_workbook_input": "22_workbook_input.xlsx"}\n'
         "\n"
         "# Переводы книг примеров — во временном каталоге на сессию тестов: в папке\n"
         "# примера перевод был бы второй копией входа. Нужен уже при сборке тестов\n"
         "# (TABLE_PVT), поэтому не фикстура tmp_path_factory\n"
         '_TRANSLATED = Path(tempfile.mkdtemp(prefix="gpn-examples-"))\n'
         "atexit.register(shutil.rmtree, _TRANSLATED, ignore_errors=True)\n"
         "\n"
         "\n"
         "@functools.cache\n"
         "def _config_path(name: str) -> Path:\n"
         '    """Конфиг примера: config.json его папки или перевод его книги (FEAT-036), один раз на сессию."""\n'
         "    if name not in WORKBOOK_EXAMPLES:\n"
         '        return EXAMPLES_DIR / name / "config.json"\n'
         "    return convert_workbook(EXAMPLES_DIR / name / WORKBOOK_EXAMPLES[name], _TRANSLATED / name)\n"),
        ('    "18_prototype_input",\n]\n',
         '    "18_prototype_input",\n    "22_workbook_input",\n]\n'),
        ('    cfg = load_config(EXAMPLES_DIR / name / "config.json")\n'
         "    simulator, initial = SimulatorFactory.from_config(cfg)\n",
         "    cfg = load_config(_config_path(name))\n"
         "    simulator, initial = SimulatorFactory.from_config(cfg)\n"),
        ('    return load_config(EXAMPLES_DIR / name / "config.json").output\n',
         "    return load_config(_config_path(name)).output\n"),
        ('        """Каждый пример самодостаточен: конфиг, точка входа, описание."""\n'
         "        folder = EXAMPLES_DIR / name\n"
         '        for fname in ("config.json", "main.py", "README.md"):\n'
         '            assert (folder / fname).is_file(), f"{name}: нет {fname}"\n',
         '        """Каждый пример самодостаточен: вход (конфиг или книга), точка входа, описание."""\n'
         "        folder = EXAMPLES_DIR / name\n"
         '        source = WORKBOOK_EXAMPLES.get(name, "config.json")\n'
         '        for fname in (source, "main.py", "README.md"):\n'
         '            assert (folder / fname).is_file(), f"{name}: нет {fname}"\n'
         "        # У примера с книгой config.json рядом — второй вход, расходящийся с ней\n"
         "        if name in WORKBOOK_EXAMPLES:\n"
         '            assert not (folder / "config.json").exists(), f"{name}: config.json рядом с книгой"\n'),
        ("        assert ast.dump(body) == ast.dump(ast.parse(_THIN_MAIN)), (\n",
         '        thin = _THIN_MAIN.format(input=WORKBOOK_EXAMPLES.get(name, "config.json"))\n'
         "        assert ast.dump(body) == ast.dump(ast.parse(thin)), (\n"),
        ('        """Валидация конфига проходит (проверяет физические ограничения)."""\n'
         '        cfg = load_config(EXAMPLES_DIR / name / "config.json")\n',
         '        """Валидация конфига проходит (проверяет физические ограничения)."""\n'
         "        cfg = load_config(_config_path(name))\n"),
        ("        folder = EXAMPLES_DIR / name\n"
         '        cfg = load_config(folder / "config.json")\n',
         "        # У примера с книгой — каталог её перевода: CSV пишет перевод\n"
         "        folder = _config_path(name).parent\n"
         "        cfg = load_config(_config_path(name))\n"),
        ('        raw = json.loads((EXAMPLES_DIR / name / "config.json").read_text(encoding="utf-8"))\n',
         '        raw = json.loads(_config_path(name).read_text(encoding="utf-8"))\n'),
        ("        for name in ALL_EXAMPLES:\n"
         '            out = json.loads((EXAMPLES_DIR / name / "config.json")\n',
         "        for name in ALL_EXAMPLES:\n"
         "            if name in WORKBOOK_EXAMPLES:\n"
         "                # Листа OUTPUT в книге нет (FEAT-033, решение 44): заголовок —\n"
         "                # имя книги, steady_state — умолчание false (TestWorkbookInput)\n"
         "                continue\n"
         '            out = json.loads((EXAMPLES_DIR / name / "config.json")\n'),
        ('    if load_config(EXAMPLES_DIR / name / "config.json").pvt.model == "table"\n',
         '    if load_config(_config_path(name)).pvt.model == "table"\n'),
    ],
    # Сверка матрицы энергии (DEBT-016): свой список примеров, сверяется с диском
    TEST_MATRIX: [
        ("from gpn_multiphase_solver.io.config import load_config\n",
         "from gpn_multiphase_solver.io.config import load_config\n"
         "from gpn_multiphase_solver.io.workbook_convert import convert_workbook\n"),
        ("# Те же 23 сценария, что в tests/test_examples.py::ALL_EXAMPLES.\n",
         "# Те же 24 сценария, что в tests/test_examples.py::ALL_EXAMPLES.\n"),
        ('    "21_rs100_cooling",\n]\n',
         '    "21_rs100_cooling",\n    "22_workbook_input",\n]\n'
         "\n"
         "# Примеры с книгой ввода Excel вместо config.json (FEAT-036): папка → книга.\n"
         "# Дублирует tests/test_examples.py::WORKBOOK_EXAMPLES — по той же причине,\n"
         "# что и список выше\n"
         'WORKBOOK_EXAMPLES = {"22_workbook_input": "22_workbook_input.xlsx"}\n'
         "\n"
         "\n"
         "def _example_config(example: str, tmp_path: Path):\n"
         '    """Конфиг примера: config.json его папки или перевод его книги в tmp_path (FEAT-036)."""\n'
         "    if example in WORKBOOK_EXAMPLES:\n"
         "        return load_config(convert_workbook(\n"
         '            EXAMPLES_DIR / example / WORKBOOK_EXAMPLES[example], tmp_path / "input"))\n'
         '    return load_config(EXAMPLES_DIR / example / "config.json")\n'),
        ("# slow (DEBT-032): 23 штатных прогона с эталоном на каждом вызове solve —\n",
         "# slow (DEBT-032): 24 штатных прогона с эталоном на каждом вызове solve —\n"),
        ("# не урезается: все 23 примера идут в полном прогоне (развилка предусмотрена\n",
         "# не урезается: все 24 примера идут в полном прогоне (развилка предусмотрена\n"),
        ("def test_matrix_matches_reference(example):\n",
         "def test_matrix_matches_reference(example, tmp_path):\n"),
        ("    d сверяется в отклонениях от T_ref, которые передаёт решатель (DEBT-043).\n"
         '    """\n'
         '    cfg = load_config(EXAMPLES_DIR / example / "config.json")\n',
         "    d сверяется в отклонениях от T_ref, которые передаёт решатель (DEBT-043).\n"
         '    """\n'
         "    cfg = _example_config(example, tmp_path)\n"),
    ],
    # Сводная проверка баланса энергии: поиск примеров — и по книге
    CHECK_BALANCE: [
        ("import sys\nfrom pathlib import Path\n",
         "import sys\nimport tempfile\nfrom pathlib import Path\n"),
        ("from gpn_multiphase_solver.energy.balance import compute_energy_balance  # noqa: E402\n"
         "\n"
         "def find_examples() -> list[str]:\n"
         '    """Папки примеров: NN_имя с config.json внутри, по порядку номера.\n',
         "from gpn_multiphase_solver.energy.balance import compute_energy_balance  # noqa: E402\n"
         "from gpn_multiphase_solver.io.workbook_convert import convert_workbook  # noqa: E402\n"
         "\n"
         "\n"
         "def _source(folder: Path) -> Path | None:\n"
         '    """Вход примера: config.json или книга <имя папки>.xlsx (пример 22, FEAT-036); None — не пример."""\n'
         '    for path in (folder / "config.json", folder / f"{folder.name}.xlsx"):\n'
         "        if path.is_file():\n"
         "            return path\n"
         "    return None\n"
         "\n"
         "\n"
         "def find_examples() -> list[str]:\n"
         '    """Папки примеров: NN_имя с config.json или книгой <имя папки>.xlsx, по порядку номера.\n'),
        ("    return sorted(d.name for d in HERE.iterdir()\n"
         '                  if d.is_dir() and (d / "config.json").is_file()\n'
         "                  and d.name[0].isdigit())\n",
         "    return sorted(d.name for d in HERE.iterdir()\n"
         "                  if d.is_dir() and d.name[0].isdigit() and _source(d))\n"),
        ("    try:\n"
         '        config = load_config(example_dir / "config.json")\n'
         '        config.output.log_level = "WARNING"\n'
         "        # Члены баланса копятся на подшагах внутри решателя, поэтому\n"
         "        # структура истории на баланс не влияет.\n"
         "\n"
         "        simulator, initial_state = SimulatorFactory.from_config(config)\n"
         "        history = simulator.run(initial_state)\n",
         "    try:\n"
         "        source = _source(example_dir)\n"
         "        # Книга — перевод во временный каталог (как в tests/test_examples.py):\n"
         "        # таблицы CSV перевода фабрика читает при сборке решателя\n"
         '        with tempfile.TemporaryDirectory(prefix="gpn-balance-") as tmp:\n'
         '            if source.suffix == ".xlsx":\n'
         '                source = convert_workbook(source, Path(tmp) / "input")\n'
         "            config = load_config(source)\n"
         '            config.output.log_level = "WARNING"\n'
         "            # Члены баланса копятся на подшагах внутри решателя, поэтому\n"
         "            # структура истории на баланс не влияет.\n"
         "\n"
         "            simulator, initial_state = SimulatorFactory.from_config(config)\n"
         "        history = simulator.run(initial_state)\n"),
        ('        print(f"В {HERE} не найдено ни одного примера с config.json")\n',
         '        print(f"В {HERE} не найдено ни одного примера с config.json или книгой")\n'),
    ],
    TEST_CLI: [
        ("\nПодпроцессы получают PYTHONPATH на пакет и прототип этого дерева: иначе в\n",
         "\nРасчёт по книге (run книга.xlsx, FEAT-036): справка, коды возврата и\n"
         "«Ошибка книги»; сам расчёт и команду в отдельном процессе проверяет\n"
         "tests/test_workbook_run.py.\n"
         "\n"
         "Подпроцессы получают PYTHONPATH на пакет и прототип этого дерева: иначе в\n"),
    ],
}
