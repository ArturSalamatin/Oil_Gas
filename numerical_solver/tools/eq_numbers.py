"""Таблица «метка → номер» для HTML-документации: doc/problem_statement.aux → doc/source/eq_numbers.json.

Номера уравнений видны только в PDF постановки; в докстрингах ссылка —
метка (правило «Связь формула → код»). При сборке HTML метка заменяется
номером по этой таблице (doc/source/conf.py). Таблица хранится в git,
поэтому для сборки HTML LaTeX не нужен.

После правки problem_statement.tex, из каталога numerical_solver:

    cd doc; pdflatex problem_statement.tex; pdflatex problem_statement.tex; cd ..
    .venv\\Scripts\\python tools\\eq_numbers.py           # записать таблицу
    .venv\\Scripts\\python tools\\eq_numbers.py --check   # сверить; код 1 — расходится

Код 2 — нет problem_statement.aux (PDF не собран).
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]                  # numerical_solver/
AUX = ROOT / "doc" / "problem_statement.aux"
TABLE = ROOT / "doc" / "source" / "eq_numbers.json"
# С hyperref: \newlabel{eq:x}{{68}{23}{}{equation.68}{}}; без него — {{68}{23}}.
# Номер — первая группа. Префиксы меток — как в tests/test_eq_references.py
NEWLABEL = re.compile(r"\\newlabel\{((?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+)\}\{\{([^}]*)\}")


def read_aux(path: Path = AUX) -> dict[str, str]:
    """Метки постановки и их номера из .aux."""
    return dict(NEWLABEL.findall(path.read_text(encoding="utf-8")))


def dump(table: dict[str, str]) -> str:
    """Текст таблицы: JSON, ключи по алфавиту, по строке на метку."""
    return json.dumps(dict(sorted(table.items())), ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Записать таблицу по .aux или (--check) сверить с ней; код возврата."""
    p = argparse.ArgumentParser(description="Таблица номеров уравнений для HTML-документации")
    p.add_argument("--check", action="store_true",
                   help="только сверить doc/source/eq_numbers.json с .aux")
    args = p.parse_args(argv)
    if not AUX.is_file():
        print(f"Нет {AUX}: соберите PDF постановки — в каталоге doc дважды "
              "pdflatex problem_statement.tex")
        return 2
    text = dump(read_aux())
    if not args.check:
        TABLE.write_text(text, encoding="utf-8")
        print(f"Записано: {TABLE} ({len(json.loads(text))} меток)")
        return 0
    old = json.loads(TABLE.read_text(encoding="utf-8")) if TABLE.is_file() else {}
    new = json.loads(text)
    diff = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
    for k in diff:
        print(f"{k}: таблица {old.get(k)!r}, .aux {new.get(k)!r}")
    if diff:
        print(f"Таблица номеров устарела ({len(diff)} меток): tools\\eq_numbers.py без --check")
        return 1
    print(f"Таблица совпадает с .aux ({len(new)} меток)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
