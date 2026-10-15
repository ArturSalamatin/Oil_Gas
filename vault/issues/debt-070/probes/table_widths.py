"""Ширина ячеек таблицы обозначений problem_statement.tex — какая строка задаёт Overfull.

Таблица `lll`: ширина = сумма максимумов по колонкам. Скрипт берёт строки между
\\endlastfoot и \\end{longtable}, меряет каждую ячейку в LaTeX (\\settowidth) и печатает
пять самых широких по каждой колонке.

Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-070\\probes\\table_widths.py <путь к .tex>
Временные файлы — в probes/measure/, удаляются в конце.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "measure"


def main():
    tex = Path(sys.argv[1]).read_text(encoding="utf-8")
    preamble = tex[:tex.index(r"\begin{document}")]
    body = tex[tex.index(r"\endlastfoot") + len(r"\endlastfoot"):tex.index(r"\end{longtable}")]
    rows = [r.strip() for r in body.split(r"\\") if r.strip() and r"\multicolumn" not in r]
    cells = []
    for r in rows:
        parts = [c.strip() for c in r.split("&")]
        if len(parts) == 3:
            cells.append(parts)
    lines = [preamble, r"\begin{document}", r"\newlength{\w}"]
    for i, row in enumerate(cells):
        for k, c in enumerate(row):
            lines.append(r"\settowidth{\w}{" + c + r"}\typeout{W " + f"{i} {k}" + r" \the\w}")
    lines.append(r"\end{document}")
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()
    (WORK / "m.tex").write_text("\n".join(lines), encoding="utf-8")
    out = subprocess.run(["pdflatex", "-interaction=nonstopmode", "m.tex"], cwd=WORK,
                         capture_output=True, text=True, encoding="latin-1").stdout
    widths = {}
    for m in re.finditer(r"W (\d+) (\d) ([\d.]+)pt", out):
        widths[(int(m.group(1)), int(m.group(2)))] = float(m.group(3))
    for k in range(3):
        top = sorted(((w, i) for (i, kk), w in widths.items() if kk == k), reverse=True)[:5]
        print(f"Колонка {k + 1}, максимум {top[0][0]:.1f} pt:")
        for w, i in top:
            print(f"  {w:7.1f} pt  {cells[i][k][:90]}")
    total = sum(max(w for (i, kk), w in widths.items() if kk == k) for k in range(3))
    print(f"Сумма максимумов: {total:.1f} pt (+ 6·\\tabcolsep = 36 pt)")
    shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    main()
