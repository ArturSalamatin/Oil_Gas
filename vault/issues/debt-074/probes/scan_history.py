"""По какой редакции постановки писались номера заметок (DEBT-074).

Для каждого коммита problem_statement.tex с 2026-08-20 по 2026-09-20 печатает,
какие метки стоят под номерами, которые цитируют заметки. Редакция, где под
номерами стоят уравнения, описанные в тексте заметки, — та, по которой
заметка писалась; её метки и подставляются вместо номеров.

Запуск из корня проекта:
    numerical_solver/.venv/Scripts/python -I vault/issues/debt-074/probes/scan_history.py
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eq_numbers_at import ROOT, TEX, numbering, tex_at  # noqa: E402

# Номера, цитируемые заметкой, и что под ними подразумевается по тексту заметки.
NOTES = {
    "grid (Грани 10, Объёмы 13, Проводимости 19, Лог. веса 21)": ["10", "13", "19", "21"],
    "hydro (Невязки 14, 15, 16-17; накопл. 22-27; режимы 28, 29)": ["14", "15", "16", "17", "22", "27", "28", "29"],
    "грабли (газ. поток 9, конв. энергии 23, Q_o 24, ṁ 32)": ["9", "23", "24", "32"],
    "вопрос (кондуктивный поток 25)": ["25"],
    "P8 (центр масс кольца 12)": ["12"],
    "Кори (уравнение на S_g 8-9)": ["8", "9"],
    "накопление (5, 23, 28-31, 33-36)": ["5", "23", "28", "31", "33", "36"],
}
SECTIONS = ["2.1", "3", "4.1", "4.2.4", "5.2"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    log = subprocess.run(
        ["git", "log", "--follow", "--reverse", "--format=%h %ci",
         "--since=2026-08-19", "--until=2026-09-21", "--", TEX],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    for line in filter(None, log):
        c, date = line.split()[0], " ".join(line.split()[1:3])[:16]
        try:
            lab = numbering(tex_at(c))
        except subprocess.CalledProcessError:
            print(f"{c} {date}: файла нет по этому пути")
            continue
        inv = {}
        for k, v in lab.items():
            if re.match(r"(eq|sec|ssec|sssec|app):", k):
                inv.setdefault(v, []).append(k.split(":", 1)[1])
        print(f"\n== {c} {date}")
        for name, nums in NOTES.items():
            print(f"  {name}: " + "  ".join(f"{n}={'/'.join(inv.get(n, ['—']))}" for n in nums))
        print("  разделы: " + "  ".join(
            f"§{n}={'/'.join(x for x in inv.get(n, ['—']))}" for n in SECTIONS))


if __name__ == "__main__":
    main()
