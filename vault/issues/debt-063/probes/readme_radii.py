"""DEBT-063, проба: радиусы центров ячеек в README примеров, которые изменятся при √.

Для README примера берутся числа с единицей «м» (вида 47.11 м, 3.6–24 м).
Число считается радиусом центра, если при его точности (число знаков после
запятой) совпадает с одним из центров exp<ln r> сетки примера, а центр √
той же ячейки при этой точности печатается иначе — такие строки нужно
править. Сводный examples/README.md и tests/test_examples.py проверяются
против сеток всех примеров. Ложные совпадения возможны (число — не радиус
центра, а совпало случайно): кандидаты проверять по тексту.

Запуск из numerical_solver/:  python ..\\vault\\issues\\debt-063\\probes\\readme_radii.py
"""

import json
import re
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
EX = SOLVER / "examples"
# Число перед «м»: допускаются диапазон «3.6–24 м», закрывающий «$» формулы
# и пробелы LaTeX («\,», «~», «\ »)
NUM_M = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)"
                   r"(?=\s*(?:[–-]\s*\$?\d+(?:\.\d+)?\s*)?\$?\s*(?:~|\\ |\\,|\s)?\s*м\b)")


def centers(cfg):
    g, n = cfg["geometry"], cfg["grid"]["N"]
    f = np.geomspace(g["r_well"], g["R_ext"], n + 1)
    a, b = f[:-1], f[1:]
    x = (a / b) ** 2
    old = b * np.sqrt(np.exp(-x * np.log(x) / (1.0 - x) - 1.0))
    return old, np.sqrt(a * b)


def fmt(v, d):
    return f"{v:.{d}f}"


grids = {}
for c in sorted(EX.glob("*/config.json")):
    grids[c.parent.name] = centers(json.loads(c.read_text(encoding="utf-8")))


CELL_NUM = re.compile(r"^\**\$?(\d+(?:\.\d+)?)\$?\**$")
M_HEADER = re.compile(r"(,\s*м\b|\(м\)|\bм\s*$|r_b)")


def check(path, n, s, line, names, where):
    d = len(s.split(".")[1]) if "." in s else 0
    v = float(s)
    for name in names:
        old, new = grids[name]
        j = np.where(np.array([fmt(o, d) for o in old]) == fmt(v, d))[0]
        for jj in j:
            if fmt(new[jj], d) != s:
                print(f"{path.relative_to(SOLVER)}:{n}: «{s}» ({where}) — центр {jj} "
                      f"[{name}] → {fmt(new[jj], d)}   | {line.strip()[:90]}")


def scan(path, names):
    lines = path.read_text(encoding="utf-8").splitlines()
    m_cols = None                       # номера столбцов таблицы с «м» в заголовке
    for n, line in enumerate(lines, 1):
        for m in NUM_M.finditer(line):
            check(path, n, m.group(1), line, names, "текст, «м»")
        # Таблицы: единица в заголовке столбца («газ до, м»), в ячейках — числа
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if m_cols is None:
                m_cols = [i for i, c in enumerate(cells) if M_HEADER.search(c)]
            elif not set(line) <= set("|-: "):
                for i in m_cols:
                    if i < len(cells):
                        mm = CELL_NUM.match(cells[i])
                        if mm:
                            check(path, n, mm.group(1), line, names, "столбец таблицы, м")
        else:
            m_cols = None


for name in grids:
    readme = EX / name / "README.md"
    if readme.exists():
        scan(readme, [name])
scan(EX / "README.md", list(grids))
scan(SOLVER / "tests" / "test_examples.py", list(grids))
