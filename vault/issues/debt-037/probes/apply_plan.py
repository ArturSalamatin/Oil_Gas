"""Проба аудита DEBT-037: применить блоки «До/После» плана к копии теста и прогнать.

Проверяет без правки проекта:
  1. блоки «До:» шага 2 встречаются в tests/test_examples.py ровно один раз
     (иначе Edit при реализации не найдёт old_string);
  2. пропатченный тест собирается и проходит на настоящем examples/;
  3. пробы А и Б плана — на фиктивном каталоге примеров (копия figure_io.py
     в папке примера; новый файл верхнего уровня с копией);
  4. пустой глоб (каталога нет) — тест SKIPPED, а не FAIL.

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-037\\probes\\apply_plan.py
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
NS = ROOT / "numerical_solver"
PLAN = ROOT / "vault" / "plans" / "debt-037 shared-modules-copy-guard.md"
TEST = NS / "tests" / "test_examples.py"
CONFTEST = NS / "tests" / "conftest.py"
OUT = HERE / "tests_patched"
FAKE = HERE / "fake_examples"


def plan_blocks(marker):
    """Два первых ```python-блока после строки-маркера: (До, После)."""
    text = PLAN.read_text(encoding="utf-8")
    tail = text[text.index(marker):]
    blocks = re.findall(r"```python\n(.*?)```", tail, flags=re.S)
    return blocks[0], blocks[1]


def patched_source(glob_dir):
    """Тест после шага 2; EXAMPLES_DIR — настоящий (модуль на сборке читает
    config.json всех примеров), глоб проверки копий — по glob_dir."""
    src = TEST.read_text(encoding="utf-8")
    for marker in ("**Изменения 2a", "**Изменения 2b"):
        before, after = plan_blocks(marker)
        n = src.count(before)
        print(f"{marker[2:]}: «До» найдено {n} раз")
        assert n == 1, f"{marker}: «До» не совпадает с файлом"
        src = src.replace(before, after)
    old = 'EXAMPLES_DIR = Path(__file__).parent.parent / "examples"'
    assert src.count(old) == 1
    src = src.replace(old, f"EXAMPLES_DIR = Path(r\"{NS / 'examples'}\")")
    assert src.count("EXAMPLES_DIR.glob(") == 2
    return src.replace("EXAMPLES_DIR.glob(", f"Path(r\"{glob_dir}\").glob(")


def write_suite(glob_dir):
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / "test_examples.py").write_text(
        patched_source(glob_dir), encoding="utf-8")
    conf = CONFTEST.read_text(encoding="utf-8").replace(
        'Path(__file__).parent.parent / "HydroSolverPrototype"',
        f'Path(r"{NS}") / "HydroSolverPrototype"')
    (OUT / "conftest.py").write_text(conf, encoding="utf-8")


def run(*args):
    cmd = [sys.executable, "-m", "pytest", str(OUT / "test_examples.py"),
           "-p", "no:cacheprovider", "--rootdir", str(OUT), "-q", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=NS)
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    return lines


def make_fake(names, copies):
    """Фиктивный examples/: пустые файлы верхнего уровня + копии в папках."""
    if FAKE.exists():
        shutil.rmtree(FAKE)
    FAKE.mkdir()
    for n in names:
        (FAKE / n).write_text("", encoding="utf-8")
    for folder, n in copies:
        (FAKE / folder).mkdir(exist_ok=True)
        (FAKE / folder / n).write_text("", encoding="utf-8")


for m in ("**Изменения 2a", "**Изменения 2b"):
    longest = max(len(ln) for ln in plan_blocks(m)[1].splitlines())
    print(f"{m[2:]}: самая длинная новая строка — {longest} символов")

K = ["-k", "duplicate_helper or shared_modules_exist"]
real_names = sorted(p.name for p in (NS / "examples").glob("*.py"))
print(f"examples/*.py: {len(real_names)}")

print("\n── 1–2. Настоящий examples/ ──")
write_suite(NS / "examples")
print("\n".join(run(*K, "--collect-only")[-3:]))
print(run(*K)[-1])

print("\n── 3А. Копия figure_io.py в папке примера ──")
make_fake(real_names, [("01_single_phase_no_jt", "figure_io.py")])
write_suite(FAKE)
out = run("-k", "duplicate_helper")
print("\n".join(out[-15:]))

print("\n── 3Б. Новый файл верхнего уровня + копия ──")
make_fake(real_names + ["zz_debt037_probe.py"],
          [("03_standing_corey", "zz_debt037_probe.py")])
write_suite(FAKE)
out = run("-k", "duplicate_helper")
print("\n".join(out[-15:]))

print("\n── 4. Каталога examples/ нет ──")
write_suite(HERE / "no_such_dir")
print("\n".join(run("-k", "duplicate_helper", "-rs")[-12:]))

shutil.rmtree(OUT)
shutil.rmtree(FAKE)
