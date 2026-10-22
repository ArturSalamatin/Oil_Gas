"""Аудит DEBT-014: блоки «До/После» шагов 1–2 плана — дословно к копии дерева; сверка конфигов.

Блоки ```python шага берутся из файла плана по порядку и идут парами
(До, После); каждый «До» должен встретиться в целевом файле ровно один раз.

Запуск из numerical_solver/ копии дерева:
    python plan_check.py step1     # шаг 1 → tests/test_energy_balance_examples.py
    python plan_check.py step2     # шаг 2 → tests/test_config.py
    python plan_check.py equal     # load_config: основной каталог (база) против текущего
"""

import dataclasses
import re
import sys
from pathlib import Path

SOLVER = Path.cwd()
ROOT = Path(__file__).resolve().parents[4]          # корень проекта
PLAN = ROOT / "vault" / "plans" / "debt-014 compact-history-configs.md"
BASE_SOLVER = ROOT / "numerical_solver"              # база: рабочая копия = HEAD по конфигам

TARGETS = {
    "step1": ("### Шаг 1:", "### Шаг 2:", "tests/test_energy_balance_examples.py"),
    "step2": ("### Шаг 2:", "### Шаг 3:", "tests/test_config.py"),
}


def blocks(start: str, stop: str) -> list[str]:
    """Блоки ```python раздела плана между заголовками start и stop."""
    text = PLAN.read_text(encoding="utf-8")
    section = text[text.index(start):text.index(stop)]
    return re.findall(r"```python\n(.*?)\n```", section, flags=re.S)


def apply(step: str) -> None:
    """Применить пары (До, После) шага к файлу копии."""
    start, stop, rel = TARGETS[step]
    found = blocks(start, stop)
    if len(found) % 2:
        sys.exit(f"{step}: нечётное число блоков python ({len(found)})")
    path = SOLVER / rel
    text = path.read_text(encoding="utf-8")
    for old, new in zip(found[::2], found[1::2]):
        n = text.count(old)
        if n != 1:
            sys.exit(f"{step}: «До» встречается {n} раз:\n{old}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"{step}: {rel} — применено пар: {len(found) // 2}")


def equal() -> None:
    """Полный SimulationConfig базы и копии равны (кроме config_dir) по 22 файлам."""
    sys.path.insert(0, str(SOLVER))
    from gpn_multiphase_solver.io.config import load_config
    sys.path.insert(0, str(Path(__file__).parent))
    import compact_history
    print(f"пакет: {sys.modules['gpn_multiphase_solver'].__file__}")
    for rel in compact_history.FILES:
        old = dataclasses.asdict(load_config(BASE_SOLVER / rel))
        new = dataclasses.asdict(load_config(SOLVER / rel))
        old.pop("config_dir", None)
        new.pop("config_dir", None)
        print(f"{rel}: {'равны' if old == new else 'РАЗЛИЧАЮТСЯ'}")
        if old != new:
            diff = [k for k in old if old[k] != new.get(k)]
            sys.exit(f"  секции: {diff}")
    print(f"файлов: {len(compact_history.FILES)}, SimulationConfig базы и копии равны")


if __name__ == "__main__":
    cmd = sys.argv[1]
    equal() if cmd == "equal" else apply(cmd)
