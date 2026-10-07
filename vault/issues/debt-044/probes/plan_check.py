r"""DEBT-044: проверка кода плана подменой — правки плана применяются к текстам файлов в памяти.

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-044\probes\plan_check.py
Файлы проекта не меняются. Правки берутся из плана по меткам
«<!-- правка <файл> #N до|после|в конец -->» перед блоками кода. Этапы:
  1. каждая правка «до» встречается в своём файле ровно один раз;
  2. тесты из плана (файл тестов с правками — во временном каталоге рядом) на текущем коде;
  3. те же тесты на коде factory.py с правками (подмена в памяти: exec в пространстве имён модуля);
  3a. то же с настройками pytest из pyproject.toml, хуком tests/conftest.py и -m "not slow";
  4. таблицы и конфиги проекта (tables_check.py) на подменённом коде;
  5. проба red_state.py на подменённом коде (зелёное состояние);
  6. быстрый уровень существующих тестов на подменённом коде (--fast; ~70 с).
Этапы 2–6 — отдельные процессы: модуль тестов, импортированный до подмены,
держал бы ссылки на старые функции.
"""
import re
import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
ROOT = SOLVER.parent
PROBES = Path(__file__).resolve().parent
PLAN = PROBES.parents[2] / "plans" / "debt-044 csv-table-value-checks.md"
TMP = PROBES / "plan_check_tmp"
FACTORY = "numerical_solver/gpn_multiphase_solver/factory.py"
TESTS = "numerical_solver/tests/test_factory_prototype.py"

EDIT_RE = re.compile(
    r"<!-- правка (\S+) #(\d+) (до|после|в конец) -->\n(`{3,})[^\n]*\n(.*?)^\4[ \t]*$",
    re.S | re.M)


def patched_texts(verbose=False):
    """{файл: текст с правками плана}; правка «до» обязана встречаться ровно один раз."""
    edits = {}
    for path, num, kind, _, body in EDIT_RE.findall(PLAN.read_text(encoding="utf-8")):
        edits.setdefault(path, {}).setdefault(int(num), {})[kind] = body
    out, ok = {}, True
    for path, by_num in edits.items():
        text = (ROOT / path).read_text(encoding="utf-8")
        for num in sorted(by_num):
            e = by_num[num]
            if "в конец" in e:
                text += e["в конец"]
                status = "в конец"
            else:
                n = text.count(e["до"])
                status = f"«до» найдено {n} раз"
                if n != 1 or "после" not in e:
                    ok = False
                    status += " — ОШИБКА"
                else:
                    text = text.replace(e["до"], e["после"])
            if verbose:
                print(f"   {path} #{num}: {status}")
        out[path] = text
    return out, ok


def setup_paths():
    sys.path.insert(0, str(SOLVER))
    sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))


def patch_factory():
    """Код factory.py с правками плана — в пространство имён загруженного модуля."""
    from gpn_multiphase_solver import factory
    src = patched_texts()[0][FACTORY]
    exec(compile(src, factory.__file__, "exec"), factory.__dict__)
    return factory


def write_test_file():
    """Файл тестов с правками плана во временном каталоге; TABLE_CONFIG — абсолютный путь."""
    src = patched_texts()[0][TESTS]
    old = 'TABLE_CONFIG = Path(__file__).parent.parent / "configs" / "table_pvt" / "config.json"'
    assert src.count(old) == 1, "строка TABLE_CONFIG изменилась"
    src = src.replace(old, f'TABLE_CONFIG = Path(r"{SOLVER}") / "configs" / "table_pvt" / "config.json"')
    TMP.mkdir(exist_ok=True)
    path = TMP / "test_debt044_plan.py"
    path.write_text(src, encoding="utf-8")
    return path


def child(stage):
    """Этап в отдельном процессе."""
    setup_paths()
    import pytest
    if stage == "before":
        sys.exit(pytest.main([str(TMP / "test_debt044_plan.py"), "-q", "-p", "no:cacheprovider",
                              "--rootdir", str(TMP)]))
    patch_factory()
    if stage == "after":
        sys.exit(pytest.main([str(TMP / "test_debt044_plan.py"), "-q", "-p", "no:cacheprovider",
                              "--rootdir", str(TMP)]))
    if stage == "real":
        # Как в быстром уровне: настройки pytest из pyproject.toml, хук метки
        # slow из tests/conftest.py (подключён плагином), отбор -m "not slow"
        import importlib.util
        spec = importlib.util.spec_from_file_location("conftest_real", SOLVER / "tests" / "conftest.py")
        conftest = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conftest)
        sys.exit(pytest.main([str(TMP / "test_debt044_plan.py"), "-q", "-p", "no:cacheprovider",
                              "-c", str(SOLVER / "pyproject.toml"), "--rootdir", str(SOLVER),
                              "-m", "not slow", "-W", "error::pytest.PytestUnknownMarkWarning"],
                             plugins=[conftest]))
    if stage == "tables":
        sys.path.insert(0, str(PROBES))
        import tables_check
        sys.exit(1 if tables_check.check_all() else 0)
    if stage == "green":
        sys.path.insert(0, str(PROBES))
        import red_state
        import shutil
        red_state.WORK = PROBES / "plan_check_tmp" / "green"
        red_state.WORK.mkdir(parents=True)
        try:
            red_state.run_cases(15e6)
            red_state.run_cases(10e6)
        finally:
            shutil.rmtree(red_state.WORK)
        sys.exit(0)
    if stage == "fast":
        sys.exit(pytest.main(["tests/", "-m", "not slow", "-q", "-p", "no:cacheprovider"]))


def run(stage, tail=None, grep=None):
    """Запустить этап, показать хвост вывода или строки по образцу."""
    r = subprocess.run([sys.executable, __file__, "--child", stage], cwd=SOLVER,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = r.stdout.splitlines()
    shown = [s for s in lines if grep and re.search(grep, s)] if grep else lines[-(tail or 3):]
    for s in shown:
        print(f"   {s}")
    if r.returncode not in (0, 1) or (not lines and r.stderr):
        print("   stderr:", r.stderr[-800:])


if __name__ == "__main__":
    if "--child" in sys.argv:
        child(sys.argv[sys.argv.index("--child") + 1])
    import shutil
    if TMP.exists():
        shutil.rmtree(TMP)
    try:
        print(f"Код: {SOLVER / 'gpn_multiphase_solver' / 'factory.py'}")
        print(f"План: {PLAN.name}")
        print("== 1. Правки плана")
        texts, ok = patched_texts(verbose=True)
        print(f"   итог: {'все применимы' if ok else 'ЕСТЬ ОШИБКИ'}")
        if not ok:
            sys.exit(1)
        # TestReadme (tests/test_examples.py:453-478) ищет в README эти строки
        readme = "numerical_solver/examples/04_table_table/README.md"
        before = (ROOT / readme).read_text(encoding="utf-8")
        keys = ("Как модифицировать", "PrototypeHydroAdapter", "TridiagEnergySolver",
                "увеличить газонасыщенность")
        same = all(before.lower().count(k.lower()) == texts[readme].lower().count(k.lower())
                   for k in keys)
        print(f"   README 04: строки, которые ищет TestReadme, {'сохранены' if same else 'ИЗМЕНЕНЫ'}")
        write_test_file()
        print("== 2. Тесты плана на текущем коде (ожидание: 25 failed, 54 passed)")
        run("before", tail=2)
        print("== 3. Тесты плана на коде с правками (ожидание: 79 passed)")
        run("after", tail=2)
        print("== 3a. То же с настройками pytest проекта и conftest, -m \"not slow\" (ожидание: 79 passed)")
        run("real", tail=2)
        print("== 4. Таблицы и конфиги проекта на коде с правками")
        run("tables", grep=r"^(Код|Таблиц|Конфигов|  )")
        print("== 5. Проба red_state на коде с правками")
        run("green", grep=r"^(Код|==|\S)")
        if "--fast" in sys.argv:
            print("== 6. Быстрый уровень на коде с правками (ожидание: 1108 passed)")
            run("fast", tail=2)
    finally:
        if TMP.exists():
            shutil.rmtree(TMP)
