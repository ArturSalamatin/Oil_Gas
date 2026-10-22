"""DEBT-063, проба: какие строки вывода примеров меняются при центрах √.

Сравнивает probes/stdout/base/*.txt и probes/stdout/sqrt/*.txt построчно
(difflib), пропуская строки со временем счёта и путями. Печатает по
скрипту пары «было / стало».

Запуск:  python diff_stdout.py [было стало]   (из любого каталога;
по умолчанию base sqrt; после реализации — sqrt impl, ожидание: различий нет)
"""

import difflib
import re
import sys
from pathlib import Path

D = Path(__file__).resolve().parent / "stdout"
OLD, NEW = (sys.argv[1:3] if len(sys.argv) >= 3 else ("base", "sqrt"))
SKIP = re.compile(r"время|elapsed|сек|\[base\]|\[sqrt\]|\d+\.\d+ с\b|\d+ с$|Сохранено|сохран|output")

changed = 0
for fb in sorted((D / OLD).glob("*.txt")):
    fs = D / NEW / fb.name
    a = [s for s in fb.read_text(encoding="utf-8").splitlines() if not SKIP.search(s)]
    b = [s for s in fs.read_text(encoding="utf-8").splitlines() if not SKIP.search(s)]
    diff = [d for d in difflib.unified_diff(a, b, lineterm="", n=0)
            if d.startswith(("-", "+")) and not d.startswith(("---", "+++"))]
    if not diff:
        continue
    changed += 1
    print(f"\n=== {fb.stem}")
    for d in diff:
        print("  " + d)
print(f"\n{OLD} → {NEW}: скриптов с изменённым выводом: {changed} из "
      f"{len(list((D / OLD).glob('*.txt')))}")
