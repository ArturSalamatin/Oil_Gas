"""DEBT-063, шаг 4: применить замены таблицы 4.1 плана (пары table41_check.py).

Каждая пара «было → станет»: «было» должно встречаться в файле ровно один
раз, иначе файл не трогается и скрипт сообщает об ошибке. Сводная таблица
баланса энергии — замена внутри строки примера. Концы строк файла (CRLF
рабочей копии Windows) сохраняются: файл читается и пишется без перевода
концов строк, многострочные «было» приводятся к концам строк файла.

Запуск из numerical_solver/ (worktree):  python ..\\vault\\issues\\debt-063\\probes\\apply_table41.py
Проверка после — `table41_check.py after`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from table41_check import EX, PAIRS, SUMMARY, summary_row  # noqa: E402


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


print("solver:", Path.cwd())
errors = 0
texts = {}
for rel, old, new in PAIRS:
    path = EX / rel
    text = texts.setdefault(path, read(path))
    nl = "\r\n" if "\r\n" in text else "\n"
    o, n = old.replace("\n", nl), new.replace("\n", nl)
    if text.count(o) != 1:
        errors += 1
        print(f"! {rel}: «было» найдено {text.count(o)} раз — {old[:60]!r}")
        continue
    texts[path] = text.replace(o, n)

path = EX / "README.md"
text = texts.setdefault(path, read(path))
nl = "\r\n" if "\r\n" in text else "\n"
lines = text.split(nl)
for ex, (old, new) in SUMMARY.items():
    rows = summary_row(lines, ex)
    if len(rows) != 1 or rows[0].count(old) != 1:
        errors += 1
        print(f"! README.md, сводная таблица, {ex}: строк {len(rows)}")
        continue
    i = lines.index(rows[0])
    lines[i] = rows[0].replace(old, new)
texts[path] = nl.join(lines)

if errors:
    print(f"ошибок: {errors} — файлы не записаны")
    sys.exit(1)
for path, text in texts.items():
    write(path, text)
print(f"записано файлов: {len(texts)}; замен: {len(PAIRS)} + строк сводной таблицы: {len(SUMMARY)}")
