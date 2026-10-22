r"""DEBT-047: проверка кода плана подменой — правки плана применяются к текстам файлов в памяти.

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-047\probes\plan_check.py [--fast]
Файлы проекта не меняются. Правки берутся из плана по меткам
«<!-- правка <файл> #N до|после|в конец -->» перед блоками кода. Этапы:
  1. каждая правка «до» встречается в своём файле ровно один раз; длина добавленных строк кода;
  2. тесты из плана (файлы тестов с правками — во временном каталоге рядом) на текущем коде;
  3. те же тесты на коде simulator.py и io/config.py с правками (подмена в памяти);
  3a. то же с настройками pytest из pyproject.toml, хуком tests/conftest.py и -m "not slow";
  4. проба red_state.py на подменённом коде (зелёное состояние);
  5. быстрый уровень существующих тестов на подменённом коде (--fast; ~70 с).
Подмена: исполнить текст модуля с правками в пространстве имён загруженного
модуля, затем вернуть прежние объекты классов, передав им новые методы, — так
factory.py, импортировавший Simulator до подмены, видит новый код.
Этапы 2–5 — отдельные процессы: модуль, импортированный до подмены, держал бы
ссылки на старые функции.
"""
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
ROOT = SOLVER.parent
PROBES = Path(__file__).resolve().parent
PLAN = PROBES.parents[2] / "plans" / "debt-047 temperature-sanity-check.md"
TMP = PROBES / "plan_check_tmp"
PKG = TMP / "tests_plan"
SIMULATOR = "numerical_solver/gpn_multiphase_solver/simulator.py"
CONFIG = "numerical_solver/gpn_multiphase_solver/io/config.py"
TESTS = ("numerical_solver/tests/test_simulator.py", "numerical_solver/tests/test_config.py")

EDIT_RE = re.compile(
    r"<!-- правка (\S+) #(\d+) (до|после|в конец) -->\n(`{3,})[^\n]*\n(.*?)^\4[ \t]*$",
    re.S | re.M)


def _edits():
    """{файл: {номер: {вид: текст}}} из меток плана."""
    edits = {}
    for path, num, kind, _, body in EDIT_RE.findall(PLAN.read_text(encoding="utf-8")):
        edits.setdefault(path, {}).setdefault(int(num), {})[kind] = body
    return edits


def patched_texts(verbose=False):
    """{файл: текст с правками плана}; правка «до» обязана встречаться ровно один раз."""
    out, ok = {}, True
    for path, by_num in _edits().items():
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


def long_lines(limit=100):
    """Добавленные планом строки .py длиннее limit; максимум длины добавленных строк."""
    worst, bad = 0, []
    for path, by_num in _edits().items():
        if not path.endswith(".py"):
            continue
        for num, e in by_num.items():
            old = set(e.get("до", "").splitlines())
            new = e.get("после", e.get("в конец", ""))
            for line in new.splitlines():
                if line not in old:
                    worst = max(worst, len(line))
                    if len(line) > limit:
                        bad.append(f"{path} #{num}: {len(line)} симв.: {line.strip()[:60]}")
    return worst, bad


def setup_paths():
    sys.path.insert(0, str(SOLVER))
    sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))


def _patch_module(mod, key, texts):
    """Текст модуля с правками — в его пространство имён; классы прежние, методы новые."""
    old_classes = {k: v for k, v in mod.__dict__.items()
                   if isinstance(v, type) and v.__module__ == mod.__name__}
    exec(compile(texts[key], mod.__file__, "exec"), mod.__dict__)
    for name, old in old_classes.items():
        new = mod.__dict__[name]
        for attr, val in list(new.__dict__.items()):
            if isinstance(val, (types.FunctionType, staticmethod, classmethod, property)):
                setattr(old, attr, val)
        mod.__dict__[name] = old


def patch_code():
    """simulator.py и io/config.py с правками плана — подмена в памяти."""
    from gpn_multiphase_solver import simulator
    from gpn_multiphase_solver.io import config
    texts = patched_texts()[0]
    _patch_module(config, CONFIG, texts)
    _patch_module(simulator, SIMULATOR, texts)


def write_test_files():
    """Файлы тестов с правками плана — пакет tests_plan во временном каталоге."""
    texts = patched_texts()[0]
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy(SOLVER / "tests" / "_doubles.py", PKG / "_doubles.py")
    old = 'BASELINE = Path(__file__).parent.parent / "configs" / "baseline.json"'
    for key in TESTS:
        src = texts[key]
        assert src.count(old) == 1, f"строка BASELINE изменилась: {key}"
        src = src.replace(old, f'BASELINE = Path(r"{SOLVER}") / "configs" / "baseline.json"')
        (PKG / Path(key).name).write_text(src, encoding="utf-8")


def child(stage):
    """Этап в отдельном процессе."""
    setup_paths()
    import pytest
    args = [str(PKG), "-q", "-p", "no:cacheprovider", "--rootdir", str(TMP)]
    if stage == "before":
        sys.exit(pytest.main(args))
    patch_code()
    if stage == "after":
        sys.exit(pytest.main(args))
    if stage == "real":
        # Как в быстром уровне: настройки pytest из pyproject.toml, хук метки
        # slow из tests/conftest.py (подключён плагином), отбор -m "not slow"
        import importlib.util
        spec = importlib.util.spec_from_file_location("conftest_real",
                                                      SOLVER / "tests" / "conftest.py")
        conftest = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conftest)
        sys.exit(pytest.main([str(PKG), "-q", "-p", "no:cacheprovider",
                              "-c", str(SOLVER / "pyproject.toml"), "--rootdir", str(SOLVER),
                              "-m", "not slow", "-W", "error::pytest.PytestUnknownMarkWarning"],
                             plugins=[conftest]))
    if stage == "green":
        sys.path.insert(0, str(PROBES))
        import red_state
        red_state.WORK = TMP / "green"
        red_state.WORK.mkdir(parents=True)
        try:
            red_state.run_cases(10e6, red_state.CASES)
            red_state.run_cases(6e6, red_state.CASES)
            red_state.run_cases(6e6, red_state.BYPASS, bypass=True)
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
    shown = [s for s in lines if re.search(grep, s)] if grep else lines[-(tail or 3):]
    for s in shown:
        print(f"   {s}")
    if r.returncode not in (0, 1) or (not lines and r.stderr):
        print("   stderr:", r.stderr[-800:])


if __name__ == "__main__":
    if "--child" in sys.argv:
        child(sys.argv[sys.argv.index("--child") + 1])
    if TMP.exists():
        shutil.rmtree(TMP)
    try:
        print(f"Код: {SOLVER / 'gpn_multiphase_solver' / 'simulator.py'}")
        print(f"План: {PLAN.name}")
        print("== 1. Правки плана")
        texts, ok = patched_texts(verbose=True)
        print(f"   итог: {'все применимы' if ok else 'ЕСТЬ ОШИБКИ'}")
        if not ok:
            sys.exit(1)
        worst, bad = long_lines()
        print(f"   добавленные строки кода: максимум {worst} симв."
              + ("" if not bad else " — ДЛИННЕЕ 100:"))
        for s in bad:
            print(f"     {s}")
        write_test_files()
        # Ожидания — на базе 9a4669e (после DEBT-015): test_simulator.py 29,
        # test_config.py 117; до правки проходят 4 новых теста из 24
        print("== 2. Тесты плана на текущем коде (ожидание: 20 failed, 150 passed)")
        run("before", tail=2)
        print("== 3. Тесты плана на коде с правками (ожидание: 170 passed)")
        run("after", tail=2)
        print("== 3a. То же с настройками pytest проекта и conftest, -m \"not slow\" "
              "(ожидание: 170 passed)")
        run("real", tail=2)
        print("== 4. Проба red_state на коде с правками")
        run("green", grep=r"^(Код|==|\S|\s+журнал)")
        if "--fast" in sys.argv:
            print("== 5. Быстрый уровень на коде с правками (ожидание: 1155 passed)")
            run("fast", tail=2)
    finally:
        if TMP.exists():
            shutil.rmtree(TMP)
