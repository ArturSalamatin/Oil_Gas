r"""Аудит плана DEBT-052: применить пары «До → После» к копиям заметок в памяти.

Для каждой пары проверяет, что блок «До» встречается в файле ровно один раз
(иначе Edit не найдёт old_string или заменит не то), затем считает grep-проверки
шагов 2–6 и число удалённых строк (аналог `git diff --numstat`). Файлы не меняет.

Запуск из корня проекта:
    numerical_solver\.venv\Scripts\python vault\issues\debt-052\probes\apply_plan_blocks.py
"""
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "vault" / "plans" / "debt-052 history-step-notes-sync.md"


def parse_pairs(plan_text):
    """Пары (файл, до, после) в порядке плана; файл — из поля «**Файлы:**» шага."""
    lines = plan_text.splitlines()
    pairs, cur_file, mode, buf, pending_before = [], None, None, [], None
    expect = None  # "before" | "after" — какой блок ждём после строки «До»/«После»
    in_block = False
    for line in lines:
        if in_block:
            if line.strip() == "~~~":
                text = "\n".join(buf)
                if expect == "before":
                    pending_before = text
                else:
                    pairs.append((cur_file, pending_before, text))
                    pending_before = None
                in_block, buf, expect = False, [], None
            else:
                buf.append(line)
            continue
        m = re.match(r"\*\*Файлы:\*\* `([^`]+)`", line)
        if m:
            cur_file = m.group(1)
        if re.match(r"^До( \(|:)", line):
            expect = "before"
        elif re.match(r"^После", line):
            expect = "after"
        elif line.strip() == "~~~" and expect:
            in_block = True
    return pairs


def count(pattern, text):
    return len(re.findall(pattern, text, flags=re.M))


def main():
    pairs = parse_pairs(PLAN.read_text(encoding="utf-8"))
    print(f"пар «До → После»: {len(pairs)}")
    originals, edited = {}, {}
    ok = True
    for f, before, after in pairs:
        path = ROOT / f
        if f not in edited:
            originals[f] = path.read_text(encoding="utf-8")
            edited[f] = originals[f]
        n = edited[f].count(before)
        flag = "OK " if n == 1 else "FAIL"
        ok &= n == 1
        print(f"  [{flag}] {Path(f).name}: «До» найдено {n} раз; первая строка: {before.splitlines()[0][:60]!r}")
        if n == 1:
            edited[f] = edited[f].replace(before, after)

    print("\nУдалено строк (как второй столбец git diff --numstat):")
    for f in edited:
        a, b = originals[f].splitlines(), edited[f].splitlines()
        removed = sum(1 for d in difflib.ndiff(a, b) if d.startswith("- "))
        added = sum(1 for d in difflib.ndiff(a, b) if d.startswith("+ "))
        print(f"  {Path(f).name}: +{added} −{removed}")

    checks = {
        "контейнер-simulation-history.md": [
            (r"def to_arrays", 0), (r"plot_well_dynamics", 0),
            (r"save_npz\(history, path\)", 0), (r"### Методы \(будущее", 0),
            (r"не реализуем", 1), (r"## Реализация в фазе 3", 0), (r"четырьмя", 1),
            (r"balance: dict \| None = None", 2), (r"history_to_arrays", 2),
            (r"DEBT-052", 1)],
        "архитектура библиотеки numerical_solver.md": [
            (r"Проектный этап", 1), (r"Псевдокод проектного этапа", 1),
            (r"модули-simulator-оркестратор", 3)],
        "матрица температурной задачи сверена с постановкой поэлементно.md": [
            (r"A-retry", 1), (r"потребует", 0), (r"n_\{sub\}", 0), (r"639c80f", 1)],
        "модули-io-вывод.md": [
            (r"Эскизы проектного этапа", 1), (r"history_to_arrays", 1)],
        "P8-формат-ввода-json.md": [
            (r"A-retry", 0), (r"локальное, DEBT-015", 2)],
    }
    print("\nGrep-проверки шагов 2–6 по результату:")
    by_name = {Path(f).name: t for f, t in edited.items()}
    for name, items in checks.items():
        for pat, want in items:
            got = count(pat, by_name[name])
            flag = "OK " if got == want else "FAIL"
            ok &= got == want
            print(f"  [{flag}] {name}: {pat!r} — {got} (план: {want})")
    print("\nИТОГ:", "все проверки сошлись" if ok else "есть расхождения")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
