"""BUG-022: невязки балансов (энергия на конце, масса max по записям) по примерам для вариантов.

Читает examples_all_<вариант>.out.txt (строки «балансы:» после строки примера, их пишет cell_tol.py).
Запуск (из этого каталога): <python> bal_table.py 0_bal pv1e-8_bal
"""
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
pat = re.compile(r"энергия на конце (\S+); масса max — нефть (\S+), газ (\S+)")
runs = {}
for v in sys.argv[1:]:
    cur, d = None, {}
    for line in (HERE / f"examples_all_{v}.out.txt").read_text(encoding="utf-8").splitlines():
        if "отпечаток" in line:
            cur = line.split()[0]
        m = pat.search(line)
        if m and cur:
            d[cur] = m.groups()
    runs[v] = d
vs = sys.argv[1:]
lines = ["пример".ljust(28) + "".join(f"{v + ': энерг. / нефть / газ':>40}" for v in vs)]
for name in runs[vs[0]]:
    lines.append(name.ljust(28) + "".join(f"{' / '.join(runs[v].get(name, ('—',) * 3)):>40}" for v in vs))
text = "\n".join(lines)
print(text)
(HERE / f"bal_table_{'_'.join(vs)}.out.txt").write_text(text + "\n", encoding="utf-8")
