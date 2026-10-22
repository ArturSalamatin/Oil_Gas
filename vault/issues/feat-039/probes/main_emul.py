"""FEAT-039 (планирование): консоль main.py примера до и после нарастания на пуске.

Запускает examples/<имя>/main.py в этом процессе (runpy); аргумент emul – эмуляция
FEAT-039 (feat039_emul): интервал 0 – смена управления. Вывод примера пишется в его
output/ (в git не входит): после прогона с emul запустить без него – вывод вернётся.

Запуск из numerical_solver/ (P – путь к скрипту): .venv\\Scripts\\python P <имя> [emul]
"""

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

name = sys.argv[1]
if sys.argv[2:] == ["emul"]:
    import feat039_emul
    feat039_emul.pytest_configure(None)
main = Path.cwd() / "examples" / name / "main.py"
sys.argv = [str(main)]
runpy.run_path(str(main), run_name="__main__")
