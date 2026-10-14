"""BUG-028 (/plan-fix): вариант 1 в дочерних процессах — регрессия и тесты прототипа.

Каталог кладётся в PYTHONPATH; при BUG028_V1=1 Python при старте импортирует этот
модуль, а он — variant1.py (подменяет RadialBlackOilModel._advance_phases, события —
в файл BUG028_LOG). Без BUG028_V1 ничего не делает.
"""

import os
import sys

if os.environ.get("BUG028_V1") == "1":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import variant1  # noqa: F401,E402
    # Метка: подмена действительно стоит в этом процессе (pid, аргументы)
    if os.environ.get("BUG028_MARK"):
        with open(os.environ["BUG028_MARK"], "a", encoding="utf-8") as _f:
            _f.write(f"{os.getpid()} {variant1.RadialBlackOilModel._advance_phases is variant1.advance_phases_v1} {sys.argv[1:2]}\n")
