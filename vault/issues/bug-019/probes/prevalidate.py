"""BUG-019: подготовить проверку тестов шагов 3 и 5 плана до реализации.

Копирует test_pvt_consistency.py в _prevalidate/ с абсолютным путём к
numerical_solver (в реальном месте — tests/, путь считается от __file__) и
замороженный конфиг в _prevalidate/data/bug019_k10/ — после сверки хеша:
freeze.py перезаписывает frozen/config.json, а числа тестов сняты на этом файле.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-019\\probes\\prevalidate.py
    $env:PYTHONPATH = "..\\vault\\issues\\bug-019\\probes"
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\bug-019\\probes\\_prevalidate -p plan_impl_plugin -q
"""

import hashlib
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
SHA = "B262EF4B9D517D9E0131398D81514E44B724470A2A9772A25D61CAD12A4F8A61"

src = HERE / "frozen" / "config.json"
got = hashlib.sha256(src.read_bytes()).hexdigest().upper()
assert got == SHA, f"frozen/config.json изменён: {got}"
out = HERE / "_prevalidate"
(out / "data" / "bug019_k10").mkdir(parents=True, exist_ok=True)
shutil.copy(src, out / "data" / "bug019_k10" / "config.json")
text = (HERE / "test_pvt_consistency.py").read_text(encoding="utf-8")
old = "SOLVER = Path(__file__).resolve().parent.parent"
assert old in text
(out / "test_pvt_consistency.py").write_text(text.replace(old, f'SOLVER = Path(r"{SOLVER}")'),
                                              encoding="utf-8")
print(f"готово: {out}")
