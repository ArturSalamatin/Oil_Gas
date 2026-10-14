"""DEBT-062: что стоит после меток постановки в источниках сторожа test_eq_references.

Запуск из numerical_solver/ (основного каталога или worktree):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-062\\probes\\label_number_survey.py [корень numerical_solver]

Печатает:
  1. срабатывания кандидатов шаблона «метка, затем номер» (строгий и широкий);
  2. все случаи «метка, затем открывающая скобка» — чтобы видеть, какой
     законный текст стоит после метки и не задевает ли его шаблон.
Источники — те же, что у сторожа (_sources): .py ядра, тестов, примеров и
.md примеров, без самого test_eq_references.py.
"""

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
SELF = ROOT / "tests" / "test_eq_references.py"
print(f"ROOT = {ROOT}")

LABEL = r"(?<![A-Za-z])(?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+"
CANDIDATES = {
    # Строгий: номер целиком в круглых скобках — «eq:x (74)», «(eq:x) (74)», «`eq:x` (74)».
    "строгий": re.compile(LABEL + r"[`)}]*\s*\(\d+\)"),
    # Широкий: любая цифра сразу после открывающей скобки — ловит и «(74–75)», «[74]».
    "широкий": re.compile(LABEL + r"[`)}]*[\s,~]*[(\[]\d"),
}
# Обзор: метка, затем (через пробелы/кавычки) открывающая скобка — что внутри.
SURVEY = re.compile(LABEL + r"[`)}]*\s*[(\[][^)\]]{0,30}[)\]]?")


def sources():
    files = [p for d in ("gpn_multiphase_solver", "tests", "examples")
             for p in (ROOT / d).rglob("*.py")]
    files += (ROOT / "examples").rglob("*.md")
    return sorted(f for f in files if f.resolve() != SELF.resolve())


lines = [(f.relative_to(ROOT), n, line)
         for f in sources()
         for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)]
print(f"источников: {len(sources())}, строк: {len(lines)}")

for name, rx in CANDIDATES.items():
    hits = [(rel, n, line.strip()) for rel, n, line in lines if rx.search(line)]
    print(f"\n== кандидат «{name}»: {len(hits)} срабатываний")
    for rel, n, text in hits:
        print(f"  {rel}:{n}: {text}")

survey = [(rel, n, m.group()) for rel, n, line in lines for m in SURVEY.finditer(line)]
print(f"\n== обзор «метка, затем скобка»: {len(survey)}")
for rel, n, text in survey:
    print(f"  {rel}:{n}: {text}")
