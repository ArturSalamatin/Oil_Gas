"""BUG-022, аудит раунд 2: целые строки «до/после» для правок README шага 5, где значение
встречается в файле не один раз (Edit по подстроке неоднозначен). Вывод — readme_lines.out.txt.
Запуск (из numerical_solver): .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\readme_lines.py
"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
EX = Path.cwd() / "examples"
EDITS = [  # (файл, строка, [(было, стало)])
    ("01_single_phase_no_jt/README.md", 133, [(r"$7.5 \times 10^{-17}$", r"$1.5 \times 10^{-16}$")]),
    ("01_single_phase_no_jt/README.md", 149, [(r"$7.5 \times 10^{-17}$ | $3.8 \times 10^{-16}$ | $4.0 \times 10^{-15}$",
                                              r"$1.5 \times 10^{-16}$ | $3.8 \times 10^{-16}$ | $3.0 \times 10^{-16}$")]),
    ("02_single_phase_jt/README.md", 200, [(r"$2.0 \times 10^{-16}$", r"$6.3 \times 10^{-16}$")]),
    ("02_single_phase_jt/README.md", 222, [(r"$2.0 \times 10^{-16}$ | $6.3 \times 10^{-16}$ | $5.5 \times 10^{-16}$",
                                           r"$6.3 \times 10^{-16}$ | $2.4 \times 10^{-16}$ | $3.4 \times 10^{-15}$")]),
    ("03_standing_corey/README.md", 88, [(r"$2.5\cdot10^{-9}$", r"$9.5\cdot10^{-13}$")]),
    ("03_standing_corey/README.md", 260, [(r"$4.0\times10^{-16}$ (абсолютная $1.9\cdot10^{-5}$ Дж)",
                                           r"$6.5\times10^{-16}$ (абсолютная $3.1\cdot10^{-5}$ Дж)")]),
    ("03_standing_corey/README.md", 278, [(r"$4.0\times10^{-16}$ | $2.1\times10^{-15}$ | $3.1\times10^{-16}$",
                                           r"$6.5\times10^{-16}$ | $1.6\times10^{-15}$ | $8.7\times10^{-16}$")]),
    ("04_table_table/README.md", 180, [(r"$5.8\times10^{-16}$", r"$3.2\times10^{-16}$")]),
    ("04_table_table/README.md", 194, [(r"$5.8\times10^{-16}$ | $2.2\times10^{-15}$ | $3.8\times10^{-15}$",
                                        r"$3.2\times10^{-16}$ | $1.9\times10^{-15}$ | $4.4\times10^{-15}$")]),
    ("05_standing_table_rp/README.md", 130, [(r"$+2.0\times10^{-5}$ ($4.1\cdot10^{-16}$)",
                                              r"$+2.1\times10^{-5}$ ($4.4\cdot10^{-16}$)")]),
    ("README.md", 473, [(r"$5.3\cdot10^{-15}$", r"$3.6\cdot10^{-15}$")]),
    ("README.md", 477, [(r"$7.1\cdot10^{-15}$", r"$5.3\cdot10^{-15}$")]),
    ("README.md", 484, [("79.51 … 332.41", "79.54 … 332.41")]),
    ("README.md", 697, [(r"$2.5\cdot10^{-9}$", r"$9.5\cdot10^{-13}$")]),
]
out = []
for f, n, reps in EDITS:
    lines = (EX / f).read_text(encoding="utf-8").splitlines()
    line = new = lines[n - 1]
    for a, b in reps:
        assert new.count(a) == 1, (f, n, a, new)
        new = new.replace(a, b)
    whole = sum(1 for x in lines if x == line)
    out += [f"{f}:{n} (строка целиком в файле ×{whole})", "  до:    " + line, "  после: " + new]
text = "\n".join(out)
print(text)
(HERE / "readme_lines.out.txt").write_text(text + "\n", encoding="utf-8")
