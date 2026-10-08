"""DEBT-015, шаг 7: какие числа README примера 17 и сводного README сдвинулись после DEBT-015.

Число README (≥ 3 значащих цифр) «подозрительно», если оно есть в выводе пробы FEAT-029
на коде базы (impl_17_pre.out.txt) и нет в выводе на коде ветки (impl_17.out.txt).
Печать: файл, строка, число, строка README. Поиск по тексту вывода — грубый: числа README,
округлённые иначе, чем в выводе, проверяются глазами по строке.

Запуск из <W>\\numerical_solver:
    <PY> ..\\vault\\issues\\debt-015\\probes\\readme17_check.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = Path.cwd()
pre = (HERE / "impl_17_pre.out.txt").read_text(encoding="utf-8-sig")
post = (HERE / "impl_17.out.txt").read_text(encoding="utf-8-sig")

NUM = re.compile(r"[−-]?\d+(?:[.,]\d+)?(?:e[+−-]?\d+)?")


def sig_digits(s):
    d = re.sub(r"[^0-9]", "", s.split("e")[0]).lstrip("0")
    return len(d)


for readme in (SOLVER / "examples" / "17_shut_in_strong_cooling" / "README.md",
               SOLVER / "examples" / "README.md"):
    for i, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
        if readme.parent.name == "examples" and "17" not in line:
            continue                      # сводный README — только строки о 17
        for m in NUM.finditer(line):
            tok = m.group(0).replace("−", "-").replace(",", ".")
            if sig_digits(tok) < 3:
                continue
            bare = tok.lstrip("-")
            if bare in pre and bare not in post:
                print(f"{readme.parent.name}/README.md:{i}: {tok} | {line.strip()[:110]}")
