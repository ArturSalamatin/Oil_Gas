r"""BUG-023: проверка кода плана подменой — правки плана применяются к тексту теста в памяти.

Запуск из numerical_solver/ (основного каталога или worktree):
    .venv\Scripts\python ..\vault\issues\bug-023\probes\plan_check.py [--message] [--full]
Файлы проекта не меняются. Правки берутся из плана по меткам
«<!-- правка <файл> #N до|после -->» перед блоками кода. Этапы:
  1. каждая правка «до» встречается в файле ровно один раз (или уже применена);
     длина добавленных строк; сдвиг строк, на которые ссылается план VAL-005;
  2. файл только с правками шага 1 (#2, #6) — новый тест обязан упасть на эталоне;
  3. файл со всеми правками, -m "not slow";
  4. --message: сверка примера 02 с испорченным эталоном — сообщения текущего кода и кода плана;
  5. --full: файл со всеми правками целиком, со slow (~5 мин).
Образец — vault/issues/debt-049/probes/plan_check.py. Этапы 2–5 — отдельные процессы.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
ROOT = SOLVER.parent
PROBES = Path(__file__).resolve().parent
PLAN = PROBES.parents[2] / "plans" / "bug-023 jt-reference-left-face.md"
TMP = PROBES / "plan_check_tmp"
TEST = "numerical_solver/tests/test_energy_matrix_examples.py"
STEP1 = {2, 6}          # правки шага 1: импорт и новый тест
NEW_TEST = "test_ref_jt_outflow_matches_hand_formula"

EDIT_RE = re.compile(
    r"<!-- правка (.+?) #(\d+) (до|после) -->\n(`{3,})[^\n]*\n(.*?)^\4[ \t]*$",
    re.S | re.M)


def _edits():
    """{номер: {вид: текст}} правок файла теста из меток плана."""
    edits = {}
    for path, num, kind, _, body in EDIT_RE.findall(PLAN.read_text(encoding="utf-8")):
        assert path == TEST, f"правка не того файла: {path}"
        edits.setdefault(int(num), {})[kind] = body
    return edits


def patched_text(only=None, verbose=False):
    """Текст теста с правками плана (only — подмножество номеров); ok — все применимы."""
    text = (ROOT / TEST).read_text(encoding="utf-8")
    ok = True
    for num, e in sorted(_edits().items()):
        if only is not None and num not in only:
            continue
        n_old, n_new = text.count(e["до"]), text.count(e["после"])
        if n_old == 1:
            text = text.replace(e["до"], e["после"])
            status = "«до» найдено 1 раз"
        elif n_old == 0 and n_new == 1:
            status = "уже применена («после» найдено 1 раз)"
        else:
            ok = False
            status = f"«до» найдено {n_old} раз, «после» — {n_new} — ОШИБКА"
        if verbose:
            print(f"   #{num}: {status}")
    return text, ok


def long_lines(limit=100):
    """Максимум длины добавленных строк; строки длиннее limit."""
    worst, bad = 0, []
    for num, e in _edits().items():
        old = set(e["до"].splitlines())
        for line in e["после"].splitlines():
            if line not in old:
                worst = max(worst, len(line))
                if len(line) > limit:
                    bad.append(f"#{num}: {len(line)} симв.: {line.strip()[:60]}")
    return worst, bad


def line_of(text, needle):
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    return None


def write_test_file(name, text):
    """Файл теста во временном пакете; EXAMPLES_DIR — абсолютный путь к examples/."""
    pkg = TMP / name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    old = 'EXAMPLES_DIR = Path(__file__).parent.parent / "examples"'
    assert text.count(old) == 1, "строка EXAMPLES_DIR изменилась"
    text = text.replace(old, f'EXAMPLES_DIR = Path(r"{SOLVER}") / "examples"')
    path = pkg / "test_energy_matrix_examples.py"
    path.write_text(text, encoding="utf-8")
    return path


def setup_paths():
    sys.path.insert(0, str(SOLVER))
    sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))


def run_pytest(path, extra):
    """pytest с настройками проекта и хуком slow из tests/conftest.py."""
    import importlib.util
    import pytest
    spec = importlib.util.spec_from_file_location("conftest_real", SOLVER / "tests" / "conftest.py")
    conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conftest)
    return pytest.main([str(path), "-q", "-p", "no:cacheprovider",
                        "-c", str(SOLVER / "pyproject.toml"), "--rootdir", str(SOLVER), *extra],
                       plugins=[conftest])


def message_stage():
    """Сверка 02 с испорченным эталоном: какое сообщение даёт текущий код и код плана."""
    import importlib.util
    import numpy as np
    sys.path.insert(0, str(SOLVER / "tests"))
    import test_energy_matrix_examples as current
    spec = importlib.util.spec_from_file_location(
        "tme_plan", TMP / "all" / "test_energy_matrix_examples.py")
    plan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plan)

    def spoil_zero(ref_d, scale):      # нулевой допуск в ячейке 0
        ref_d[0], scale[0] = 0.0, 0.0

    def spoil_nan(ref_d, scale):       # NaN в эталоне ячейки 0
        ref_d[0] = np.nan

    def spoil_shift(ref_d, scale):     # сдвиг эталона ячейки 3 на 1e-9 отн.
        ref_d[3] *= 1.0 + 1e-9

    cases = {"нулевой допуск в ячейке 0": spoil_zero, "NaN в d_ref[0]": spoil_nan,
             "d_ref[3] · (1 + 1e-9)": spoil_shift}
    for label, mod in (("текущий код", current), ("код плана ", plan)):
        print(f"   {label}: {mod.__file__}")
        original = mod.build_reference
        for case, spoil in cases.items():
            def wrapped(*args, _orig=original, _spoil=spoil, **kw):
                ref_a, ref_b, ref_c, ref_d, scale = _orig(*args, **kw)
                ref_d, scale = ref_d.copy(), scale.copy()
                _spoil(ref_d, scale)
                return ref_a, ref_b, ref_c, ref_d, scale
            mod.build_reference = wrapped
            try:
                mod.test_matrix_matches_reference("02_single_phase_jt")
                print(f"     {case:28s}: ПРОШЛА — сверка не поймала порчу")
            except AssertionError as exc:
                msg = str(exc).splitlines()[0]
                print(f"     {case:28s}: {msg[msg.find('правая часть'):]}")
            finally:
                mod.build_reference = original


def child(stage):
    setup_paths()
    if stage == "red":
        sys.exit(run_pytest(TMP / "step1" / "test_energy_matrix_examples.py", ["-k", NEW_TEST]))
    if stage == "green":
        sys.exit(run_pytest(TMP / "all" / "test_energy_matrix_examples.py", ["-m", "not slow"]))
    if stage == "full":
        sys.exit(run_pytest(TMP / "all" / "test_energy_matrix_examples.py", []))
    if stage == "message":
        import warnings
        warnings.simplefilter("ignore", RuntimeWarning)   # 0/0 в старом сообщении
        message_stage()
        sys.exit(0)


def run(stage, grep=None, tail=3):
    r = subprocess.run([sys.executable, __file__, "--child", stage], cwd=SOLVER,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = r.stdout.splitlines()
    shown = [s for s in lines if re.search(grep, s)] if grep else lines[-tail:]
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
        print(f"Тест: {ROOT / TEST}")
        print(f"План: {PLAN.name}")
        print("== 1. Правки плана")
        text_all, ok = patched_text(verbose=True)
        print(f"   итог: {'все применимы' if ok else 'ЕСТЬ ОШИБКИ'}")
        if not ok:
            sys.exit(1)
        worst, bad = long_lines()
        print(f"   добавленные строки: максимум {worst} симв." + ("" if not bad else " — ДЛИННЕЕ 100:"))
        for s in bad:
            print(f"     {s}")
        base = (ROOT / TEST).read_text(encoding="utf-8")
        for needle in ("ALL_EXAMPLES = [", "# slow (DEBT-032): 22 штатных",
                       "Те же 22 сценария", "def test_matrix_matches_reference"):
            print(f"   строка «{needle}»: {line_of(base, needle)} → {line_of(text_all, needle)}")
        text_step1, _ = patched_text(only=STEP1)
        write_test_file("step1", text_step1)
        write_test_file("all", text_all)
        print("== 2. Только шаг 1 (#2, #6): новый тест на текущем эталоне — ожидание: 1 failed")
        run("red", grep=r"err_msg|Mismatch|ACTUAL|DESIRED|x: array|y: array|эталон _ref_jt|failed|passed")
        print("== 3. Все правки, -m \"not slow\" — ожидание: 3 passed")
        run("green", tail=1)
        if "--message" in sys.argv:
            print("== 4. Сверка 02 с испорченным эталоном")
            run("message", grep=r"\S")
        if "--full" in sys.argv:
            print("== 5. Все правки, файл целиком со slow — ожидание: 25 passed")
            run("full", tail=1)
    finally:
        if TMP.exists():
            shutil.rmtree(TMP)
