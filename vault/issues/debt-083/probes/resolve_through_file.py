"""DEBT-083, план: Path.resolve() на пути через файл — его зовут _check_inputs_outside и отказ «содержит книгу» до новой проверки."""
import shutil
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
work = here / "_work_resolve"
if work.exists():
    shutil.rmtree(work)
work.mkdir()
try:
    f = work / "well_history.csv"
    f.write_text("1", encoding="utf-8")
    print("python", sys.version.split()[0])
    for p in (f, f / "sub", f / "a" / "b"):
        try:
            print(f"{p.relative_to(work)}: resolve -> {p.resolve().relative_to(work.resolve())}")
        except OSError as exc:
            print(f"{p.relative_to(work)}: resolve -> {type(exc).__name__} winerror={getattr(exc, 'winerror', None)} {exc}")
finally:
    shutil.rmtree(work)
