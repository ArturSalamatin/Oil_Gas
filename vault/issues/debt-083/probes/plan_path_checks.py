"""DEBT-083, план: поведение exists()/mkdir и проверки «первый существующий предок — каталог» на Windows.

Запуск из корня проекта: numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-083\\probes\\plan_path_checks.py
"""
import os
import shutil
import string
from pathlib import Path

here = Path(__file__).resolve().parent
work = here / "_work"
if work.exists():
    shutil.rmtree(work)
work.mkdir()


def first_existing(path: Path):
    """Кандидат реализации: первый существующий путь среди path и его предков (None — нет ни одного)."""
    path = Path(os.path.abspath(path))
    return next((p for p in (path, *path.parents) if p.exists()), None)


def mkdir_outcome(path: Path) -> str:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return "создан"
    except OSError as exc:
        return f"{type(exc).__name__} errno={exc.errno} winerror={getattr(exc, 'winerror', None)} {exc.strerror!r}"


f = work / "well_history.csv"
f.write_text("1\n", encoding="utf-8")
(work / "dir").mkdir()
drives = {d for d in string.ascii_uppercase if Path(f"{d}:\\").exists()}
missing_drive = next(d for d in "QRSTUVWXYZ" if d not in drives)

cases = {
    "файл": f,
    "файл-предок": f / "sub",
    "файл-предок, глубже": f / "a" / "b",
    "нет пути, предок — каталог": work / "dir" / "new" / "out",
    "существующий каталог": work / "dir",
    f"нет диска {missing_drive}:": Path(f"{missing_drive}:\\out"),
    "недопустимый символ": work / "out<1>",
    "относительный путь": Path("vault_issues_debt083_rel_probe"),
}
try:
    for name, p in cases.items():
        try:
            ex = p.exists()
        except OSError as exc:
            ex = f"исключение {type(exc).__name__}: {exc}"
        fe = first_existing(p)
        kind = None if fe is None else ("каталог" if fe.is_dir() else "НЕ каталог")
        # mkdir — только там, где он ничего не создаст вне _work (относительный — пропуск)
        mk = mkdir_outcome(p) if name != "относительный путь" else "—"
        print(f"{name}: exists={ex}; первый существующий={fe} ({kind}); mkdir: {mk}")
finally:
    shutil.rmtree(work)
print("диски:", sorted(drives))
