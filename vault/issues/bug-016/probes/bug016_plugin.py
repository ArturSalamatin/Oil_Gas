"""BUG-016: pytest-плагин — ставит патч прототипа до сбора тестов.

Запуск (из numerical_solver основного каталога):
    $env:BUG016_MODE = "fallback"; $env:BUG016_CAP = "0.3"
    $env:PYTHONPATH = "..\\vault\\issues\\bug-016\\probes"
    python -m pytest tests -q -p bug016_plugin
"""

import os

import patch


def pytest_configure(config):
    mode = os.environ.get("BUG016_MODE", "none")
    cap = os.environ.get("BUG016_CAP")
    chop = os.environ.get("BUG016_CHOP")
    patch.install(mode, cap=float(cap) if cap else None, chop=float(chop) if chop else None)
    print(f"\nBUG-016 патч: {patch.CFG}")
