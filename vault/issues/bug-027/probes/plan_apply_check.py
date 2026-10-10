"""BUG-027, аудит: текст плана применяется к копии tests/ и .tex, тесты — на копии.

Блоки ```python после строк «До…»/«После…» берутся из файла плана как есть.
Каждое «до» должно встретиться ровно один раз среди изменяемых файлов.
Новый тест (блок после строки «Новый тест — …») вставляется после
`    return Q_T_internal, Q_T_ext` в test_energy_matrix_examples.py.
.tex — пробой tex_apply.py (те же блоки, что в шагах 1–2 плана).

Проверки на копии: тесты шагов 3–4, тест-сторож DEBT-010 (против исправленного
.tex), число тестов в четырёх файлах (+1), длина изменённых строк (≤ 100),
негатив — эталон в старой записи документа валит новый тест.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-027\\probes\\plan_apply_check.py [--keep]
Копия — в probes/tree/, удаляется в конце (--keep — оставить).
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/, cwd = {SOLVER}")
PROBES = Path(__file__).resolve().parent
PLAN = SOLVER.parent / "vault" / "plans" / "bug-027 tex-conductive-face-mean.md"
TREE = PROBES / "tree"
FILES = ["test_grid.py", "test_energy_matrix_examples.py",
         "test_energy.py", "test_val002.py"]
ANCHOR = "    return Q_T_internal, Q_T_ext\n\n\n"

print(f"Код: {SOLVER}")
print(f"План: {PLAN.name}")

# ── Копия tests/ и исправленный .tex ──
if TREE.exists():
    shutil.rmtree(TREE)
shutil.copytree(SOLVER / "tests", TREE / "tests",
                ignore=shutil.ignore_patterns("__pycache__", "output"))
(TREE / "doc").mkdir()
r = subprocess.run([sys.executable, str(PROBES / "tex_apply.py"),
                    str(SOLVER / "doc" / "problem_statement.tex"),
                    str(TREE / "doc" / "problem_statement.tex")],
                   capture_output=True, text=True, encoding="utf-8")
print(r.stdout.strip())
if r.returncode:
    sys.exit("tex_apply.py: отказ")

# ── Блоки из плана ──
plan = PLAN.read_text(encoding="utf-8")
blocks = []          # (вид, текст)
for m in re.finditer(r"```python\n(.*?)```", plan, flags=re.S):
    head = plan[:m.start()].rstrip("\n").splitlines()
    prev = next((ln for ln in reversed(head) if ln.strip()), "")
    if prev.startswith("До"):
        kind = "до"
    elif prev.startswith("После"):
        kind = "после"
    elif prev.startswith("Новый тест"):
        kind = "вставка"
    else:
        continue          # блоки vault (шаг 5) и прочие — не про тесты
    blocks.append((kind, m.group(1)))

texts = {f: (TREE / "tests" / f).read_text(encoding="utf-8") for f in FILES}
orig = dict(texts)
pairs = 0
ok = True
i = 0
while i < len(blocks):
    kind, body = blocks[i]
    if kind == "до":
        after_kind, after = blocks[i + 1]
        assert after_kind == "после", f"блок {i}: за «до» нет «после»"
        hits = {f: t.count(body) for f, t in texts.items() if t.count(body)}
        first = body.splitlines()[0].strip()[:60]
        if sum(hits.values()) != 1:
            print(f"  ✗ «до» «{first}…»: найдено {hits or 0}")
            ok = False
        else:
            (f,) = hits
            line = orig[f][:orig[f].find(body)].count("\n") + 1 \
                if body in orig[f] else "после предыдущих замен"
            texts[f] = texts[f].replace(body, after)
            pairs += 1
            print(f"  ✓ {f}:{line}  «{first}…»")
        i += 2
    elif kind == "вставка":
        f = "test_energy_matrix_examples.py"
        n = texts[f].count(ANCHOR)
        if n != 1:
            print(f"  ✗ якорь вставки найден {n} раз")
            ok = False
        else:
            texts[f] = texts[f].replace(ANCHOR, ANCHOR + body + "\n\n")
            print(f"  ✓ {f}: вставка после `return Q_T_internal, Q_T_ext`")
        i += 1
    else:
        print(f"  ✗ блок «{kind}» без пары")
        ok = False
        i += 1
print(f"Пар «до/после»: {pairs}")
if not ok:
    sys.exit("отказ: план не ложится на дерево")
for f, t in texts.items():
    (TREE / "tests" / f).write_text(t, encoding="utf-8")

# ── Длина изменённых строк ──
for f in FILES:
    old = set(orig[f].splitlines())
    for n, ln in enumerate(texts[f].splitlines(), 1):
        if ln not in old and len(ln) > 100:
            print(f"  длинная строка {f}:{n} ({len(ln)})")


def pytest(*args):
    """pytest на копии; возвращает (код, последняя строка вывода)."""
    r = subprocess.run([sys.executable, "-m", "pytest", *args, "-q",
                        "-p", "no:cacheprovider",
                        "-W", "ignore::pytest.PytestUnknownMarkWarning"],
                       capture_output=True, text=True, encoding="utf-8",
                       cwd=SOLVER)
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    return r.returncode, (lines[-1] if lines else r.stderr.strip()[-300:])


T = TREE / "tests"
checks = [
    ("TestHarmonicInterpolation", [f"{T / 'test_grid.py'}::TestHarmonicInterpolation"]),
    ("новый тест + самопроверка JT",
     [str(T / "test_energy_matrix_examples.py"), "-k", "annulus or ref_jt"]),
    ("TestComputeConductiveTransmissibility",
     [f"{T / 'test_energy.py'}::TestComputeConductiveTransmissibility"]),
    ("test_val002 single_ln", [str(T / "test_val002.py"), "-k", "single_ln"]),
    ("сторож DEBT-010 на копии", [str(T / "test_eq_references.py")]),
]
print("\nТесты на копии:")
for name, args in checks:
    code, last = pytest(*args)
    print(f"  {'✓' if code == 0 else '✗'} {name}: {last}")

print("\nЧисло тестов (оригинал → копия):")
for f in FILES:
    _, a = pytest("--collect-only", str(SOLVER / "tests" / f))
    _, b = pytest("--collect-only", str(T / f))
    print(f"  {f}: {a.split()[0]} → {b.split()[0]}")

# ── Негатив: эталон в записи документа до BUG-027 ──
f = T / "test_energy_matrix_examples.py"
good = f.read_text(encoding="utf-8")
old_num = "    lam_face[ok] = ((w_L[ok] + w_R[ok])\n"
assert good.count(old_num) == 1
f.write_text(good.replace(old_num, "    lam_face[ok] = ((1.0)\n"), encoding="utf-8")
code, last = pytest(str(f), "-k", "annulus")
print(f"\nНегатив (эталон без множителя w_L + w_R): "
      f"{'✓ красный' if code else '✗ зелёный'} — {last}")
f.write_text(good, encoding="utf-8")

if "--keep" not in sys.argv:
    shutil.rmtree(TREE)
    print("копия удалена")
