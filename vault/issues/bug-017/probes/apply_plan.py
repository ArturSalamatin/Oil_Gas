"""Аудит BUG-017: применить блоки кода плана к экспорту дерева (по умолчанию fix_tree).

Блоки берутся из файла плана как есть (```python ... ```), по порядку.
Этап tests — шаг 1 плана; этап fix — шаги 2–4. Исходники проекта не трогаются.
Подготовка дерева (из корня проекта, Git Bash):
  git archive <коммит> numerical_solver | tar -x -C vault/issues/bug-017/probes/fix_tree
Запуск (из каталога проб): python apply_plan.py tests|s2|s3|s4|fix [каталог дерева]
(s2, s3, s4 — по одному шагу плана, по порядку; fix = s2 + s3 + s4)
Затем pytest из <дерево>/numerical_solver — `python -m pytest` берёт код дерева (cwd в sys.path).
Деревья после проверки удалять: это копии, а не рабочий код.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[3]
PLAN = ROOT / "vault" / "plans" / "bug-017 rs0-table-range-check.md"
TREE = HERE / (sys.argv[2] if len(sys.argv) > 2 else "fix_tree") / "numerical_solver"

blocks = re.findall(r"```python\n(.*?)```", PLAN.read_text(encoding="utf-8"), re.S)
print(f"python-блоков в плане: {len(blocks)}")


def replace_once(path, before, after):
    text = path.read_text(encoding="utf-8")
    n = text.count(before)
    assert n == 1, f"{path.name}: блок «До» найден {n} раз:\n{before}"
    path.write_text(text.replace(before, after), encoding="utf-8")


def stage_tests():
    tp = TREE / "tests" / "test_factory_prototype.py"
    replace_once(tp, "from pathlib import Path\n",
                 "from pathlib import Path\nimport logging\nimport shutil\n")
    tp.write_text(tp.read_text(encoding="utf-8").rstrip("\n") + "\n\n\n" + blocks[0],
                  encoding="utf-8")
    ts = TREE / "tests" / "test_factory_standing_hydro.py"
    replace_once(ts, "from pathlib import Path\n", "from pathlib import Path\nimport logging\n")
    ts.write_text(ts.read_text(encoding="utf-8").rstrip("\n") + "\n\n\n" + blocks[1],
                  encoding="utf-8")


FACTORY = TREE / "gpn_multiphase_solver" / "factory.py"


def stage_s2():
    replace_once(FACTORY, blocks[2], blocks[3])
    replace_once(FACTORY, "\n\ndef _create_relperm(",
                 "\n\n" + blocks[4] + "\n\ndef _create_relperm(")


def stage_s3():
    replace_once(FACTORY, blocks[5], blocks[6])
    replace_once(FACTORY, "\n\ndef _create_relperm(",
                 "\n\n" + blocks[7] + "\n\ndef _create_relperm(")


def stage_s4():
    replace_once(FACTORY, blocks[8], blocks[9])
    replace_once(FACTORY, blocks[10], blocks[11])
    replace_once(FACTORY, "\n\ndef _create_relperm(",
                 "\n\n" + blocks[12] + "\n\ndef _create_relperm(")


def stage_fix():
    stage_s2(); stage_s3(); stage_s4()


{"tests": stage_tests, "s2": stage_s2, "s3": stage_s3, "s4": stage_s4,
 "fix": stage_fix}[sys.argv[1]]()
print("ok", sys.argv[1])
