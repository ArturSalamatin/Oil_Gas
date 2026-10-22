"""Аудит 1 FEAT-036: shutil.rmtree каталога вывода, когда файл в нём открыт (как CSV в Excel).

Файл держится открытым на запись (Python на Windows открывает без FILE_SHARE_DELETE,
Excel — тоже без него). Каталог — рядом со скриптом, удаляется в конце.
Запуск: numerical_solver\\.venv\\Scripts\\python vault/issues/feat-036/probes/audit_locked_output.py
"""

import shutil
from pathlib import Path

out = Path(__file__).resolve().parent / "locked_output"
out.mkdir(exist_ok=True)
(out / "a.png").write_bytes(b"1")
(out / "z.csv").write_text("1", encoding="utf-8")
f = open(out / "well_history.csv", "w", encoding="utf-8")
try:
    shutil.rmtree(out)
    print("rmtree прошёл")
except OSError as exc:
    left = sorted(p.name for p in out.iterdir())
    print(f"{type(exc).__name__}: errno {exc.errno}, winerror {getattr(exc, 'winerror', None)}, "
          f"filename {Path(exc.filename).name}, strerror {exc.strerror!r}; осталось: {left}")
finally:
    f.close()
    shutil.rmtree(out, ignore_errors=True)
