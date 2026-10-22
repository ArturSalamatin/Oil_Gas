"""Проба DEBT-086: склейка строк абзаца и отрисовка описания выпуска GitHub (gh api markdown, режим gfm).

Запуск из корня репозитория: numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-086\\probes\\p1_unwrap_render.py
Для каждого раздела журнала: notes.md по-старому (как build в tools/release.py) и со склейкой;
число <br> в HTML обоих; совпадение последовательности слов (склейка не теряет и не добавляет текст);
идемпотентность склейки.
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent / "out_p1"
OUT.mkdir(exist_ok=True)

spec = importlib.util.spec_from_file_location("release", ROOT / "tools" / "release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
print("release.py:", spec.origin)

# Черновик функции плана (шаг 2)
BLOCK_START_RE = re.compile(r"\s*($|#|[-*+] |\d+[.)] |\||>)")


def unwrap_paragraphs(text: str) -> str:
    out, fence = [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```"):
            fence = not fence
            out.append(line)
            continue
        prev = out[-1].strip() if out else ""
        if (not fence and prev and not prev.startswith(("#", "```"))
                and not BLOCK_START_RE.match(line)):
            out[-1] = f"{out[-1].rstrip()} {s}"
        else:
            out.append(line)
    return "\n".join(out)


def render(text: str, name: str) -> str:
    src = OUT / f"{name}.md"
    src.write_text(text, encoding="utf-8")
    r = subprocess.run(["gh", "api", "markdown", "-f", "mode=gfm",
                        "-f", "context=ArturSalamatin/Oil_Gas", "-F", f"text=@{src}"],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"gh api markdown: {r.stderr}")
    (OUT / f"{name}.html").write_text(r.stdout, encoding="utf-8")
    return r.stdout


text = release.read_text(ROOT / release.CHANGELOG)
heads = [s for s in text.splitlines() if s.startswith("## ") and s != "## Правило номеров"]
for head in heads:
    body = release.section_body(text, head)
    if not body:
        print(f"{head}: пусто")
        continue
    old = f"{body}\n\n{release.NOTES_TAIL}\n"
    new = f"{unwrap_paragraphs(body)}\n\n{release.NOTES_TAIL}\n"
    tag = re.sub(r"\W+", "_", head[3:]).strip("_")
    br_old = render(old, f"{tag}_old").count("<br>")
    br_new = render(new, f"{tag}_new").count("<br>")
    same_words = old.split() == new.split()
    idem = unwrap_paragraphs(unwrap_paragraphs(body)) == unwrap_paragraphs(body)
    print(f"{head}: <br> {br_old} -> {br_new}; слова совпадают: {same_words}; идемпотентна: {idem}")
