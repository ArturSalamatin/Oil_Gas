"""FEAT-039 (планирование): числа README и тестов 16, 17 до и после нарастания на пуске.

Обёртка над feat-032/probes/readme_numbers.py в режиме «конфиг как есть» (поле 0.11 с
в 16, 17). Аргумент emul – эмуляция FEAT-039 (feat039_emul.pytest_configure: интервал 0 –
смена управления). Разность двух выводов – числа README и тестов, которые меняет FEAT-039.

Запуск из numerical_solver/ (P – путь к скрипту): .venv\\Scripts\\python P [emul]
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES_032 = HERE.parent.parent / "feat-032" / "probes"
sys.path.insert(0, str(PROBES_032))
sys.path.insert(0, str(HERE))
import readme_numbers as rn  # noqa: E402

emul = sys.argv[1:] == ["emul"]
if emul:
    import feat039_emul  # noqa: E402
    feat039_emul.pytest_configure(None)
print(f"FEAT-039: {'эмуляция' if emul else 'код как есть'}")
sys.argv = sys.argv[:1]
rn.main()
