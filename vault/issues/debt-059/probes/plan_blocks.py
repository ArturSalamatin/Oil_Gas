"""Блоки кода плана DEBT-059 (```...```) с подписью и шагом — для аудита: что именно вставит реализация.

Импортируется пробой audit_plan_dry_run.py; запуск сам по себе печатает список:

    numerical_solver\\.venv\\Scripts\\python -X utf8 vault\\issues\\debt-059\\probes\\plan_blocks.py
"""

import re
from pathlib import Path

PLAN = Path(__file__).resolve().parents[3] / "plans" / "debt-059 installable-prototype-package.md"


def blocks(plan: Path = PLAN) -> list[dict]:
    """[{step, label, lang, code}] в порядке плана; code — без отступа ограды."""
    out, step, label = [], None, ""
    lines = plan.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"### Шаг (\d+)", line)
        if m:
            step = int(m.group(1))
        fence = re.match(r"^(\s*)```(\w*)\s*$", line)
        if fence:
            indent, lang = len(fence.group(1)), fence.group(2)
            body = []
            i += 1
            while not re.match(r"^\s*```\s*$", lines[i]):
                body.append(lines[i][indent:] if lines[i][:indent].strip() == "" else lines[i])
                i += 1
            out.append({"step": step, "label": label.strip(), "lang": lang,
                        "code": "\n".join(body) + "\n"})
        elif line.strip():
            label = line
        i += 1
    return out


if __name__ == "__main__":
    for k, b in enumerate(blocks()):
        first = b["code"].splitlines()[0] if b["code"].strip() else ""
        print(f"[{k:2}] шаг {b['step']} {b['lang']:6} | {b['label'][:70]!r} | {first[:60]!r}")
