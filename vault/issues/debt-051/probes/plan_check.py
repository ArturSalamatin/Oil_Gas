r"""DEBT-051: проверка кода плана подменой — правки плана применяются к текстам файлов в памяти.

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-051\probes\plan_check.py [--fast]
Файлы проекта не меняются. Правки берутся из плана по меткам
«<!-- правка <файл> #N до|после -->» перед блоками кода. Этапы:
  1. каждая правка «до» встречается в своём файле ровно один раз; длина добавленных строк кода;
  2. test_config.py с правками плана (во временном каталоге рядом) на текущем коде;
  3. тот же файл на коде io/config.py с правками (подмена в памяти);
  3a. то же с настройками pytest из pyproject.toml, хуком tests/conftest.py и -m "not slow";
  4. проба red_state.py (все разделы) на подменённом коде — зелёное состояние;
  5. быстрый уровень существующих тестов на подменённом коде (--fast; ~80 с).
Образец — vault/issues/debt-049/probes/plan_check.py. Подмена: текст модуля с
правками исполняется в пространстве имён загруженного модуля, прежние объекты
dataclass возвращаются (factory.py и тесты сравнивают типы с ними). Этапы 2–5 —
отдельные процессы: модуль, импортированный до подмены, держал бы старые функции.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
ROOT = SOLVER.parent
PROBES = Path(__file__).resolve().parent
PLAN = PROBES.parents[2] / "plans" / "debt-051 config-numeric-fields-finite.md"
TMP = PROBES / "plan_check_tmp"
PKG = TMP / "tests_plan"
CONFIG = "numerical_solver/gpn_multiphase_solver/io/config.py"
TEST = "numerical_solver/tests/test_config.py"

EDIT_RE = re.compile(
    # Путь — до « #N»: имена заметок vault содержат пробелы
    r"<!-- правка (.+?) #(\d+) (до|после) -->\n(`{3,})[^\n]*\n(.*?)^\4[ \t]*$",
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
            n = text.count(e.get("до", "\0"))
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
            for line in e.get("после", "").splitlines():
                if line not in old:
                    worst = max(worst, len(line))
                    if len(line) > limit:
                        bad.append(f"{path} #{num}: {len(line)} симв.: {line.strip()[:60]}")
    return worst, bad


def setup_paths():
    sys.path.insert(0, str(SOLVER))
    sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))


def patch_code():
    """io/config.py с правками плана — подмена в памяти; классы прежние, функции новые."""
    from gpn_multiphase_solver.io import config
    old_classes = {k: v for k, v in config.__dict__.items()
                   if isinstance(v, type) and v.__module__ == config.__name__}
    exec(compile(patched_texts()[0][CONFIG], config.__file__, "exec"), config.__dict__)
    config.__dict__.update(old_classes)


def write_test_files():
    """test_config.py с правками плана — пакет tests_plan во временном каталоге."""
    src = patched_texts()[0][TEST]
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "__init__.py").write_text("", encoding="utf-8")
    old = 'BASELINE = Path(__file__).parent.parent / "configs" / "baseline.json"'
    assert src.count(old) == 1, "строка BASELINE изменилась"
    src = src.replace(old, f'BASELINE = Path(r"{SOLVER}") / "configs" / "baseline.json"')
    (PKG / "test_config.py").write_text(src, encoding="utf-8")


def child(stage):
    """Этап в отдельном процессе."""
    setup_paths()
    import pytest
    args = [str(PKG), "-q", "-p", "no:cacheprovider", "--rootdir", str(TMP)]
    if stage == "before":
        sys.exit(pytest.main(args + ["-k", "TestValidationNumbers", "-rf", "--tb=no"]))
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
        # Все разделы пробы в этом процессе: подпроцессы пробы взяли бы код без
        # подмены. После правки отказ — при загрузке, расчёт идёт у эталонов.
        sys.path.insert(0, str(PROBES))
        import red_state
        red_state.WORK = TMP / "green"
        sections = {"A": {"эталон (без подмены)": ("pressure", None), **red_state.SECTION_A},
                    "B": red_state.SECTION_B, "C": red_state.SECTION_C,
                    "D": red_state.SECTION_D, "E": red_state.SECTION_E}
        try:
            for tag, cases in sections.items():
                print(f"== Раздел {tag}")
                for i, (name, (kind, change)) in enumerate(cases.items()):
                    path = red_state._config_path(red_state.WORK / f"{tag}_{i}", kind, change)
                    print(f"{name:34s} ", end="", flush=True)
                    red_state.child(str(path))
        finally:
            shutil.rmtree(red_state.WORK, ignore_errors=True)
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
        print(f"Код: {SOLVER / 'gpn_multiphase_solver' / 'io' / 'config.py'}")
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
        print("== 2. TestValidationNumbers на текущем коде (прошедшие — без FAILED)")
        run("before", grep=r"^(PASSED|\d+ (passed|failed)|.*\d+ failed)")
        print("== 3. test_config.py плана на коде с правками")
        run("after", tail=2)
        print("== 3a. То же с настройками pytest проекта и conftest, -m \"not slow\"")
        run("real", tail=2)
        print("== 4. Проба red_state (все разделы) на коде с правками")
        run("green", grep=r"\S")
        if "--fast" in sys.argv:
            print("== 5. Быстрый уровень на коде с правками")
            run("fast", tail=2)
    finally:
        if TMP.exists():
            shutil.rmtree(TMP)
