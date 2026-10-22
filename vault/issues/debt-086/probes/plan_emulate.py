"""Эмуляция шагов 1–2 плана DEBT-086 на копии: код берётся из блоков ```python плана.

Запуск из корня репозитория: numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-086\\probes\\plan_emulate.py
Копии tools/release.py, tools/acceptance.py, numerical_solver/CHANGELOG.md, tests/test_packaging.py,
gpn_multiphase_solver/__init__.py – в probes/emul/; правки плана накладываются заменой строк;
pytest – новые тесты шагов 1–2 и прежний тест журнала. Дословность пункта FEAT-040 – сверкой слов.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
EMUL = HERE / "emul"
PLAN = ROOT / "vault" / "plans" / "debt-086 release-notes-format.md"

blocks = re.findall(r"^```python\n(.*?)^```$", PLAN.read_text(encoding="utf-8"), re.M | re.S)
print("блоков python в плане:", len(blocks))
new_funcs, build_old, build_new, acc_old, acc_new, test_release, test_pack = blocks

if EMUL.exists():
    shutil.rmtree(EMUL)
for rel in ("tools/release.py", "tools/acceptance.py", "numerical_solver/CHANGELOG.md",
            "numerical_solver/tests/test_packaging.py", "numerical_solver/gpn_multiphase_solver/__init__.py",
            # Настоящая конфигурация pytest (ini_options) и conftest – прогон как в /implement
            "numerical_solver/pyproject.toml", "numerical_solver/tests/conftest.py"):
    (EMUL / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / rel, EMUL / rel)


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{path.name}: «{old[:60]}…» встречается {text.count(old)} раз"
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


# ── Шаг 1 ──
rel = EMUL / "tools" / "release.py"
anchor = "    return text[:i] + UNRELEASED + eol + eol + text[i:]\n"
replace_once(rel, anchor, anchor + new_funcs.rstrip("\n") + "\n")
replace_once(rel, build_old, build_new)
replace_once(EMUL / "tools" / "acceptance.py", acc_old, acc_new)
(EMUL / "numerical_solver" / "tests" / "test_release_notes.py").write_text(test_release, encoding="utf-8")

# ── Шаг 2 ──
pack = EMUL / "numerical_solver" / "tests" / "test_packaging.py"
pack.write_text(pack.read_text(encoding="utf-8").rstrip("\n") + "\n" + test_pack, encoding="utf-8")
cl = EMUL / "numerical_solver" / "CHANGELOG.md"
text = cl.read_text(encoding="utf-8")
old_item = re.search(r"^- \*\*FEAT-040\.\*\*.*?(?=\n\n## )", text, re.M | re.S)[0]
after = (HERE / "after_unreleased.md").read_text(encoding="utf-8")
new_item = re.search(r"^- \*\*FEAT-040\.\*\*.*?(?=\n\n### )", after, re.M | re.S)[0]
replace_once(cl, old_item, new_item)

# Дословность: слова старого пункта = слова блоков нового без первой строки (суть) и меток
old_words = old_item.split()[2:]                       # без «-», «**FEAT-040.**»
blocks_text = new_item.split("\n\n", 1)[1]
new_words = [w for w in blocks_text.split() if w not in ("*Было.*", "*Стало.*")]
print("FEAT-040 дословно:", old_words == new_words,
      "" if old_words == new_words else [(a, b) for a, b in zip(old_words, new_words) if a != b][:5])

# ── pytest на копии – как в /implement: из <дерево>\numerical_solver, конфигурация – его pyproject.toml ──
solver = EMUL / "numerical_solver"
r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-rs",
                    "tests/test_release_notes.py", "tests/test_packaging.py",
                    "-k", "changelog or unwrap or release_notes or skip_reason"],
                   cwd=solver, capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout[-3000:], r.stderr[-2000:])
# Шаг 2 «Проверка» дословно: группа -k changelog файла test_packaging.py
r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
                    "tests/test_packaging.py", "-k", "changelog"],
                   cwd=solver, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("-k changelog:", r.stdout.strip().splitlines()[-1])

# ── Пропуск без tools/ (срез заказчика) – как запускает приёмка: из каталога копии, путь tests/… ──
shutil.move(EMUL / "tools", EMUL / "tools_hidden")
r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-rs",
                    "tests/test_release_notes.py"],
                   cwd=solver, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("без tools/:", r.stdout.strip().splitlines()[-2:])
# Разбор итога – функциями приёмки (с правкой шага 1)
import importlib.util
spec = importlib.util.spec_from_file_location("acceptance", EMUL / "tools_hidden" / "acceptance.py")
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)
skips = acceptance.parse_skips(r.stdout)
print("приёмка: пропуски", skips, "| недопустимые:", acceptance.disallowed_skips(skips))
shutil.move(EMUL / "tools_hidden", EMUL / "tools")
