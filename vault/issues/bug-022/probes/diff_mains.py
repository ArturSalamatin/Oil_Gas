"""BUG-022: строки консоли main.py, которые отличаются между двумя вариантами (run_mains.py).

Пути к копиям examples_copy_<вариант> приводятся к одному виду, строки «Сохранён: …»
и время счёта отбрасываются. Вывод: по примеру — пары строк «-» база / «+» вариант.
Запуск (из этого каталога): <python> diff_mains.py 0 pv1e-8
"""
import difflib
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
a, b = sys.argv[1], sys.argv[2]
SKIP = re.compile(r"^(Сохранён:|Конфиг:)|\d+\.\d+ с\b|за \d+\.\d+ с|время")


def norm(text):
    out = []
    for line in text.splitlines():
        line = re.sub(r"examples_copy_[^\\/]+", "examples", line)
        if SKIP.search(line.strip()):
            continue
        out.append(line.rstrip())
    return out


lines = [f"=== консоль main.py: {a} против {b} (без путей, «Сохранён» и времени счёта)"]
for fa in sorted((HERE / f"mains_{a}").glob("*.txt")):
    fb = HERE / f"mains_{b}" / fa.name
    if not fb.exists():
        lines.append(f"--- {fa.stem}: нет вывода варианта {b}")
        continue
    la, lb = norm(fa.read_text(encoding="utf-8")), norm(fb.read_text(encoding="utf-8"))
    diff = [d for d in difflib.unified_diff(la, lb, lineterm="", n=0) if not d.startswith(("---", "+++", "@@"))]
    lines.append(f"--- {fa.stem}: строк отличается {sum(d.startswith('-') for d in diff)}")
    lines.extend("    " + d for d in diff)
text = "\n".join(lines)
print(text)
(HERE / f"diff_mains_{a}_{b}.out.txt").write_text(text + "\n", encoding="utf-8")
