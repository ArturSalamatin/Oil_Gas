"""DEBT-083: что делает mkdir, если каталог вывода — существующий файл (оба пути run_case)."""
from pathlib import Path

here = Path(__file__).resolve().parent
target = here / "not_a_dir.csv"
target.write_text("x\n", encoding="utf-8")
try:
    # Конфиг: pipeline.run_case после расчёта — output_dir.mkdir(parents=True, exist_ok=True)
    try:
        target.mkdir(parents=True, exist_ok=True)
        print("config: mkdir прошёл")
    except OSError as exc:
        print(f"config: {type(exc).__name__} errno={exc.errno} strerror={exc.strerror!r}")
    # Книга: _translate_workbook → write_files(output_dir / "input") → mkdir(parents=True, exist_ok=True)
    try:
        (target / "input").mkdir(parents=True, exist_ok=True)
        print("book: mkdir прошёл")
    except OSError as exc:
        print(f"book: {type(exc).__name__} errno={exc.errno} strerror={exc.strerror!r} "
              f"filename={exc.filename!r}")
    print(f"is_dir={target.is_dir()} exists={target.exists()}")
finally:
    target.unlink()
