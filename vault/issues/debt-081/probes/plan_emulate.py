"""DEBT-081: эмуляция плана на копии дерева.

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-081\\probes\\plan_emulate.py
Вывод — plan_emulate.out.txt рядом со скриптом.

1. Копия numerical_solver/ и vault/knowledge/ из `git archive HEAD` в probes/_emu/
   (сторож test_eq_references.py читает заметки vault/knowledge от корня копии).
2. Блоки «До/После» берутся из текста плана (vault/plans/debt-081 …md) по порядку:
   1–4 — tests/test_config.py, 5 — io/config.py, 6 — P8, 7 — заметка о переводе книги.
   Каждый «До» обязан встретиться в своём файле ровно один раз.
3. Только тесты (блоки 1–4) → TestValidationGrid и страж целых полей:
   ожидается 10 failed, 11 passed (аудит 1; до аудита — блоки 1–2, 7 failed, 2 passed).
4. Весь план → test_config.py, test_grid.py, test_workbook_convert.py,
   test_eq_references.py, число тестов, быстрый уровень, red_state.py на копии.
5. probes/_emu/ удаляется.
"""
import io
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
EMU = HERE / "_emu"
PY = ROOT / "numerical_solver" / ".venv" / "Scripts" / "python.exe"
PLAN = ROOT / "vault" / "plans" / "debt-081 grid-n-integer-check.md"
OUT = HERE / "plan_emulate.out.txt"

TARGETS = [
    "numerical_solver/tests/test_config.py",
    "numerical_solver/tests/test_config.py",
    "numerical_solver/tests/test_config.py",
    "numerical_solver/tests/test_config.py",
    "numerical_solver/gpn_multiphase_solver/io/config.py",
    "vault/knowledge/decisions/P8-формат-ввода-json.md",
    "vault/knowledge/decisions/перевод книги в конфиг проверяет только книгу — "
    "моменты SCHEDULE в целых мс.md",
]

lines = []


def say(s=""):
    print(s, flush=True)
    lines.append(s)


def run(args, cwd, tail=3):
    """Команда в копии; печать последних строк вывода и времени."""
    t0 = time.perf_counter()
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    dt = time.perf_counter() - t0
    out = (r.stdout + r.stderr).strip().splitlines()
    say(f"$ {' '.join(str(a) for a in args[1:])}   [{dt:.0f} с, код {r.returncode}]")
    for s in out[-tail:]:
        say(f"    {s}")
    return r


def apply(blocks, which):
    """Применить блоки с номерами which к файлам копии."""
    for i in which:
        before, after = blocks[i]
        f = EMU / TARGETS[i]
        text = f.read_text(encoding="utf-8")
        n = text.count(before)
        assert n == 1, f"блок {i + 1}: «До» найден {n} раз в {TARGETS[i]}"
        f.write_text(text.replace(before, after), encoding="utf-8")
        say(f"блок {i + 1} → {TARGETS[i]}: «До» найден 1 раз, заменён")


head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                      capture_output=True, text=True).stdout.strip()
say(f"HEAD: {head}; план: {PLAN.name}")

plan = PLAN.read_text(encoding="utf-8")
blocks = re.findall(r"До:\n```\w*\n(.*?)\n```\nПосле:\n```\w*\n(.*?)\n```", plan, re.S)
say(f"блоков «До/После» в плане: {len(blocks)}")
assert len(blocks) == len(TARGETS), "число блоков не совпадает с TARGETS"
# Длина строк кода (блоки 1–5); линтера длины в проекте нет, ориентир — ≤ 100
code_max = max(len(s) for _, after in blocks[:5] for s in after.splitlines())
say(f"самая длинная строка кода в блоках «После» 1–5: {code_max} символов")

if EMU.exists():
    shutil.rmtree(EMU)
EMU.mkdir()
tar = subprocess.run(["git", "archive", "--format=tar", "HEAD", "numerical_solver",
                      "vault/knowledge"], cwd=ROOT, capture_output=True, check=True).stdout
with tarfile.open(fileobj=io.BytesIO(tar)) as t:
    t.extractall(EMU, filter="data")
NS = EMU / "numerical_solver"
say(f"копия: {EMU.relative_to(ROOT)} ({len(tar) / 1e6:.1f} МБ tar)")
say()

try:
    say("── 1. только тесты (блоки 1–4): ожидается 10 failed, 11 passed ──")
    apply(blocks, [0, 1, 2, 3])
    run([PY, "-m", "pytest", "tests/test_config.py", "-q", "-p", "no:cacheprovider",
         "-k", "TestValidationGrid or int_field_rejects or int_field_list"], NS, tail=12)
    say()

    say("── 2. весь план (блоки 5–7) ──")
    apply(blocks, [4, 5, 6])
    run([PY, "-c", "import gpn_multiphase_solver as g; print(g.__file__)"], NS, tail=1)
    run([PY, "-m", "pytest", "tests/", "--collect-only", "-q", "-p", "no:cacheprovider"],
        NS, tail=1)
    run([PY, "-m", "pytest", "tests/", "-m", "not slow", "--collect-only", "-q",
         "-p", "no:cacheprovider"], NS, tail=1)
    run([PY, "-m", "pytest", "tests/test_config.py", "tests/test_grid.py",
         "tests/test_workbook_convert.py", "tests/test_eq_references.py", "-q",
         "-p", "no:cacheprovider"], NS, tail=2)
    run([PY, "-m", "pytest", "tests/", "-m", "not slow", "-q", "-p", "no:cacheprovider"],
        NS, tail=3)
    say()

    say("── 3. red_state.py на копии ──")
    tmp_name = "_emu_state.out.txt"
    run([PY, str(HERE / "red_state.py"), tmp_name], NS, tail=0)
    for s in (HERE / tmp_name).read_text(encoding="utf-8").splitlines():
        say(f"    {s}")
    (HERE / tmp_name).unlink()
finally:
    shutil.rmtree(EMU, ignore_errors=True)
    say()
    say(f"{EMU.name}/ удалён: {not EMU.exists()}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
