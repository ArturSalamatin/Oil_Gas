"""DEBT-083, план шаг 1: функция _check_output_path (текст — как в плане) на случаях модульных тестов.

Запуск из корня проекта: numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-083\\probes\\plan_code\\check_output_path.py
CaseConfigError — из установленного пакета основного каталога.
"""
import os
import shutil
from pathlib import Path

from gpn_multiphase_solver.report.pipeline import CaseConfigError


# ── Текст функции из плана (шаг 1) ──
def _check_output_path(output_dir: Path) -> None:
    """Путь вывода годится под каталог: первый существующий среди него и его предков — каталог, иначе CaseConfigError. DEBT-083."""
    # Опечатка в --output (имя CSV или книги вместо каталога) обнаруживалась
    # только после расчёта: mkdir на файле падает FileExistsError даже с
    # exist_ok, на пути через файл (well_history.csv\sub) — тоже, на
    # несуществующем диске — FileNotFoundError (пробы DEBT-083,
    # vault/issues/debt-083/probes/). Проверка ничего не создаёт. abspath, а
    # не resolve, — как в _sibling: диск subst и сетевой остаются собой
    path = Path(os.path.abspath(output_dir))
    existing = next((p for p in (path, *path.parents) if p.exists()), None)
    if existing is None:
        raise CaseConfigError(
            f"каталог вывода {path}: диск {path.anchor} не найден. Укажите "
            f"другой каталог вывода. Расчёт не начат.")
    if not existing.is_dir():
        head = (f"каталог вывода {path}" if existing == path
                else f"каталог вывода {path} не создать: {existing}")
        raise CaseConfigError(
            f"{head} — файл, а не каталог. Укажите другой каталог вывода. "
            f"Расчёт не начат.")


def refused(p) -> str:
    try:
        _check_output_path(p)
    except CaseConfigError as exc:
        return str(exc)
    return ""


here = Path(__file__).resolve().parent
work = here / "_work"
if work.exists():
    shutil.rmtree(work)
work.mkdir()
try:
    f = work / "well_history.csv"
    f.write_text("1", encoding="utf-8")
    out = work / "out"
    out.mkdir()

    msg = refused(f)
    print("файл:", msg)
    assert "файл, а не каталог" in msg and str(f) in msg and "Расчёт не начат" in msg
    assert f.read_text(encoding="utf-8") == "1"

    for sub in (f / "sub", f / "a" / "b"):
        msg = refused(sub)
        print("через файл:", msg)
        assert f"{sub} не создать: {f}" in msg

    for ok in (out, work / "new" / "out", Path("relative_not_created")):
        assert refused(ok) == "", ok
    assert sorted(p.name for p in work.iterdir()) == ["out", "well_history.csv"]
    assert not Path("relative_not_created").exists()

    free = [d for d in "QRSTUVWXYZ" if not Path(f"{d}:\\").exists()]
    msg = refused(Path(f"{free[0]}:\\out"))
    print("нет диска:", msg)
    assert "не найден" in msg
    print("OK")
finally:
    shutil.rmtree(work)
