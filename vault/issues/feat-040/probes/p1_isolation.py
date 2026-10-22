"""Проба FEAT-040, п. 1: под python -S с PYTHONPATH = site-packages venv зависимости импортируются, решатель и прототип – нет.

Запуск (из любого каталога, кроме numerical_solver):
    $env:PYTHONPATH = "<КОРЕНЬ>\\numerical_solver\\.venv\\Lib\\site-packages"
    <КОРЕНЬ>\\numerical_solver\\.venv\\Scripts\\python.exe -S p1_isolation.py
Без -S – для сравнения: оба пакета находятся через поисковики editable-установки.
"""

import importlib
import sys

print("python:", sys.version.split()[0], "| -S:", sys.flags.no_site)
print("site загружен:", "site" in sys.modules)

for name in ("numpy", "scipy", "scipy.sparse.linalg", "scipy.optimize",
             "matplotlib", "matplotlib.pyplot", "xlsxwriter",
             "gpn_multiphase_solver", "radial_blackoil"):
    try:
        mod = importlib.import_module(name)
        print(f"{name:24s} {getattr(mod, '__file__', None)}")
    except ImportError as exc:
        print(f"{name:24s} ImportError: {exc}")

# Поисковики editable-установки встают в sys.meta_path при обработке .pth
print("meta_path:", [getattr(f, "__name__", type(f).__name__) for f in sys.meta_path])
