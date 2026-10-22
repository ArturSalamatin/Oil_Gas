"""Проба DEBT-078 после правки: три случая — какие отказы и с каким текстом.

Запуск из корня дерева (в worktree — с PYTHONPATH на его numerical_solver;
путь пакета печатается первой строкой):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-078\\probes\\co_after.py
"""

import copy
import json
from pathlib import Path

from gpn_multiphase_solver import factory
from gpn_multiphase_solver.io.config import load_config

ROOT = Path(__file__).resolve().parents[4]
EXAMPLES = ROOT / "numerical_solver" / "examples"
print(f"пакет: {Path(factory.__file__).resolve()}")


def outcome(fn):
    try:
        fn()
        return "без отказа"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


# 1. Таблица (пример 04), c_o = 3.3e-9 — отказ create_pvt
cfg = load_config(EXAMPLES / "04_table_table" / "config.json")
c = copy.deepcopy(cfg)
c.pvt.co_undersaturated = 3.3e-9
print(f"\n1. пример 04 (таблица), c_o = 3.3e-9, create_pvt:\n   {outcome(lambda: factory.create_pvt(c))}")
print(f"   то же, c_o = 0:\n   {outcome(lambda: factory.create_pvt(cfg))}")

# 2. Стендинг (пример 03), c_o = −1e-9 — отказ load_config
# 3. Таблица (пример 04), c_o = −1e-9 — отказ load_config с сообщением о знаке
for n, (name, co) in enumerate((("03_standing_corey", -1e-9), ("04_table_table", -1e-9)), start=2):
    d = EXAMPLES / name
    src = json.loads((d / "config.json").read_text(encoding="utf-8"))
    src["pvt"]["co_undersaturated"] = co
    # конфиг рядом с исходным: табличным нужны CSV из того же каталога
    tmp = d / "debt078_tmp.json"
    tmp.write_text(json.dumps(src, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        print(f"\n{n}. {name}, c_o = {co:g}, load_config:\n   {outcome(lambda: load_config(tmp))}")
    finally:
        tmp.unlink(missing_ok=True)
