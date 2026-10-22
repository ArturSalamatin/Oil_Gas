"""DEBT-082: отказывает ли Windows в переименовании каталога, когда файл в нём открыт.

Вариант проверки до расчёта из реестра: переименовать каталог вывода в соседний и
обратно. Файл держится открытым на запись (Python на Windows открывает без
FILE_SHARE_DELETE — как Excel; см. audit_locked_output.py FEAT-036). Второй случай —
файл в подкаталоге (output/input/ у книги, FEAT-036). Каталоги — рядом со скриптом,
удаляются в конце.
Запуск: numerical_solver\\.venv\\Scripts\\python vault/issues/debt-082/probes/rename_check.py
"""

import os
import shutil
from pathlib import Path

here = Path(__file__).resolve().parent


def probe(label: str, locked_rel: str) -> None:
    out = here / "locked_output"
    tmp = here / "locked_output.check"
    locked = out / locked_rel
    locked.parent.mkdir(parents=True, exist_ok=True)
    (out / "a.png").write_bytes(b"1")
    f = open(locked, "w", encoding="utf-8")
    try:
        os.rename(out, tmp)
        print(f"{label}: переименование прошло (проверка НЕ ловит открытый файл)")
        os.rename(tmp, out)
    except OSError as exc:
        print(f"{label}: {type(exc).__name__}, winerror {getattr(exc, 'winerror', None)}, "
              f"strerror {exc.strerror!r}; каталог на месте: {out.is_dir()}, "
              f"файлы целы: {sorted(p.name for p in out.iterdir())}")
    finally:
        f.close()
        shutil.rmtree(out, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)


probe("файл в корне каталога", "well_history.csv")
probe("файл в подкаталоге input/", "input/config.json")
