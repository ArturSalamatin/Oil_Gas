"""Проба DEBT-086: проверка формы пунктов журнала – черновик для tests/test_packaging.py.

Запуск из корня репозитория: numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-086\\probes\\p2_format_check.py
1. Текущий «Не выпущено» (FEAT-040 в старой форме) – ожидаются нарушения.
2. Раздел после задачи (FEAT-040 переведён, пункт DEBT-086) – нарушений нет; отрисовка gfm:
   метки курсивом, абзацы пункта – <p> внутри <li>, <br> нет (после склейки).
3. Образцы нарушений – каждое поймано.
"""

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = HERE / "out_p2"
OUT.mkdir(exist_ok=True)

spec = importlib.util.spec_from_file_location("p1", HERE / "p1_unwrap_render.py")

# ── Черновик проверки (шаг 3 плана) ──
SUBSECTIONS = ("### Добавлено", "### Изменено", "### Исправлено", "### Удалено")
ITEM_RE = re.compile(r"- \*\*([^*]+)\.\*\* \S")
TASK_ID_RE = re.compile(r"(BUG|DEBT|FEAT|VAL)-\d{3}")
LABEL_RE = re.compile(r"  \*([^*]+)\.\* \S")
LABEL_SETS = (["Было", "Стало"], ["Было", "Стало", "Числа"])


def changelog_format_problems(lines):
    problems, subs, item, labels, prev = [], [], None, [], ""

    def close():
        if item is not None and labels not in LABEL_SETS:
            problems.append(f"строка {item}: блоки пункта {labels}, нужны «Было», «Стало» и, если "
                            "меняются результаты, «Числа» – по порядку")

    for n, line in enumerate(lines, 1):
        if "—" in line:
            problems.append(f"строка {n}: длинное тире «—», нужно «–»")
        if re.search(r"\d,\d", line):
            problems.append(f"строка {n}: десятичная запятая, нужна точка")
        if line.startswith("#"):
            close()
            item = None
            if line not in SUBSECTIONS:
                problems.append(f"строка {n}: подраздел {line!r} не из {SUBSECTIONS}")
            subs.append(line)
        elif line.startswith("- "):
            close()
            item, labels = n, []
            m = ITEM_RE.match(line)
            if m is None:
                problems.append(f"строка {n}: пункт не начинается с «- **<номер задачи или область>.** »")
            elif re.search(r"\d", m[1]) and not TASK_ID_RE.fullmatch(m[1]):
                problems.append(f"строка {n}: номер {m[1]!r} не вида FEAT-040")
            if prev:
                problems.append(f"строка {n}: перед пунктом нет пустой строки")
            if not subs:
                problems.append(f"строка {n}: пункт вне подраздела")
        elif line.startswith("  ") and not line.startswith(("  - ", "    ")) and not prev and item:
            m = LABEL_RE.match(line)
            if m is None or m[1] not in LABEL_SETS[1]:
                problems.append(f"строка {n}: абзац пункта не начинается с метки *Было.*, *Стало.* или *Числа.*")
            else:
                labels.append(m[1])
        elif line and not line.startswith(" ") and subs:
            problems.append(f"строка {n}: текст вне пункта внутри подраздела")
        prev = line
    close()
    order = [SUBSECTIONS.index(s) for s in subs if s in SUBSECTIONS]
    if order != sorted(set(order)):
        problems.append(f"подразделы {subs}: порядок – {SUBSECTIONS}, каждый один раз")
    return problems


# ── 1. Текущий раздел ──
release_spec = importlib.util.spec_from_file_location("release", ROOT / "tools" / "release.py")
release = importlib.util.module_from_spec(release_spec)
release_spec.loader.exec_module(release)
current = release.section_body(release.read_text(ROOT / release.CHANGELOG), release.UNRELEASED)
print("1. Текущий «Не выпущено»:")
for p in changelog_format_problems(current.splitlines()):
    print("   ", p)

# ── 2. Раздел после задачи ──
AFTER = (HERE / "after_unreleased.md").read_text(encoding="utf-8")
probs = changelog_format_problems(AFTER.splitlines())
print("2. После задачи:", probs or "нарушений нет")
p1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p1)            # печатает таблицу p1 по журналу – побочный вывод
html = p1.render(f"{p1.unwrap_paragraphs(AFTER)}\n\n{release.NOTES_TAIL}\n", "after")
(OUT / "after.html").write_text(html, encoding="utf-8")
print("   <br>:", html.count("<br>"), "| <em>Было.</em>:", html.count("<em>Было.</em>"),
      "| <em>Стало.</em>:", html.count("<em>Стало.</em>"), "| <p> всего:", html.count("<p>"))

# ── 3. Образцы нарушений ──
GOOD = ["### Добавлено", "", "- **FEAT-001.** Суть.", "", "  *Было.* А.", "", "  *Стало.* Б."]
BAD = {
    "без жирного номера": ["### Добавлено", "", "- FEAT-001. Суть.", "", "  *Было.* А.", "", "  *Стало.* Б."],
    "номер не вида": ["### Добавлено", "", "- **FEAT-1.** Суть.", "", "  *Было.* А.", "", "  *Стало.* Б."],
    "нет «Стало»": ["### Добавлено", "", "- **FEAT-001.** Суть.", "", "  *Было.* А."],
    "блоки не по порядку": ["### Добавлено", "", "- **FEAT-001.** Суть.", "", "  *Стало.* Б.", "", "  *Было.* А."],
    "чужая метка": GOOD + ["", "  *Итог.* В."],
    "абзац без метки": GOOD + ["", "  Просто текст."],
    "метка жирным": ["### Добавлено", "", "- **FEAT-001.** Суть.", "", "  **Было.** А.", "", "  *Стало.* Б."],
    "нет пустой строки между пунктами": GOOD + ["- **FEAT-002.** Суть.", "", "  *Было.* А.", "", "  *Стало.* Б."],
    "длинное тире": GOOD[:4] + ["  *Было.* А — Б."] + GOOD[5:],
    "десятичная запятая": GOOD[:4] + ["  *Было.* 10,67 м."] + GOOD[5:],
    "чужой подраздел": ["### Прочее"] + GOOD[1:],
    "подразделы не по порядку": ["### Изменено"] + GOOD[1:] + ["", "### Добавлено"] + GOOD[1:],
    "пункт вне подраздела": GOOD[1:],
    "текст вне пункта": GOOD + ["", "Текст."],
}
print("3. Образец без нарушений:", changelog_format_problems(GOOD) or "нарушений нет")
for name, lines in BAD.items():
    p = changelog_format_problems(lines)
    print(f"   {'пойман' if p else 'ПРОПУЩЕН'}: {name}: {p[:1]}")
