"""Проба DEBT-087: проверка шапки журнала функциями, предложенными в плане (копия кода плана).

Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-087\\probes\\header_check.py

Печатает замечания к шапке: журнала в рабочем дереве, журнала с новой шапкой
(header_new.md + журнал от «## Не выпущено») и того же журнала в форме дерева
метки выпуска («## Не выпущено» → «## 1.0.7 — 2026-10-23»), затем – образцы.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CHANGELOG = ROOT / "numerical_solver" / "CHANGELOG.md"
HEADER_NEW = Path(__file__).with_name("header_new.md")

# ── Код плана (шаг 2) ──
CHANGELOG_EM_DASH = chr(0x2014)
CHANGELOG_CODE_SPAN_RE = re.compile(r"`[^`]*`")
CHANGELOG_RELEASE_HEAD_RE = re.compile(r"## (Не выпущено|\d+\.\d+\.\d+)( |$)")


def _changelog_symbol_problems(n, line):
    plain = CHANGELOG_CODE_SPAN_RE.sub("", line)
    problems = []
    if CHANGELOG_EM_DASH in plain:
        problems.append(f"строка {n}: длинное тире (U+2014), нужно «–»")
    if re.search(r"\d,\d", plain):
        problems.append(f"строка {n}: десятичная запятая, нужна точка")
    return problems


def _changelog_header(lines):
    end = next((i for i, s in enumerate(lines) if CHANGELOG_RELEASE_HEAD_RE.match(s)), None)
    assert end is not None, "в журнале нет раздела выпуска"
    return lines[:end]


def header_problems(lines):
    return [p for n, s in enumerate(_changelog_header(lines), 1) for p in _changelog_symbol_problems(n, s)]


# ── Проба ──
old = CHANGELOG.read_text(encoding="utf-8").splitlines()
start = next(i for i, s in enumerate(old) if s == "## Не выпущено")
new = HEADER_NEW.read_text(encoding="utf-8").splitlines() + [""] + old[start:]
tag = ["## 1.0.7 — 2026-10-23" if s == "## Не выпущено" else s for s in new]

for name, lines in (("рабочее дерево", old), ("новая шапка", new), ("новая шапка, дерево метки", tag)):
    header = _changelog_header(lines)
    print(f"{name}: строк шапки {len(header)}, «## Правило номеров» в шапке – "
          f"{'## Правило номеров' in header}, замечаний {len(header_problems(lines))}")
    for p in header_problems(lines):
        print("   ", p)

SAMPLE = ["# Журнал", "", "Текст – норма.", "", "## Правило номеров", "",
          f"Номер {CHANGELOG_EM_DASH} три числа.", f"Заголовок `## <номер> {CHANGELOG_EM_DASH} <дата>`.",
          "Число 1,5 и интервал `[0,1]`.", "",
          f"## 1.0.7 {CHANGELOG_EM_DASH} 2026-10-23", "", f"- **FEAT-001.** А {CHANGELOG_EM_DASH} Б."]
print("образец:", header_problems(SAMPLE))
hn = HEADER_NEW.read_text(encoding="utf-8").splitlines()
print("шапка журнала в дереве совпадает с header_new.md:", old[:len(hn)] == hn)

# ── Функции выпуска на журнале с новой шапкой: шапка не задевает разбор разделов ──
import importlib.util
spec = importlib.util.spec_from_file_location("release", ROOT / "tools" / "release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
text_new = "\n".join(new) + "\n"
text_old = CHANGELOG.read_text(encoding="utf-8")
for name, text in (("рабочее дерево", text_old), ("новая шапка", text_new)):
    released = release.changelog_release(text, "1.0.7", "2026-10-23")
    notes = release.release_notes(released, "1.0.7")
    reopened = release.changelog_new_unreleased(released, "1.0.7")
    print(f"{name}: строк в описании выпуска {len(notes.splitlines())}, "
          f"«Не выпущено» после начала разработки – {reopened.count(chr(10) + '## Не выпущено' + chr(10))}")
print("описания выпуска совпадают:",
      release.release_notes(release.changelog_release(text_old, "1.0.7", "2026-10-23"), "1.0.7")
      == release.release_notes(release.changelog_release(text_new, "1.0.7", "2026-10-23"), "1.0.7"))
