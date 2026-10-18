"""DEBT-082, план: функции шага 1 (дословно как в плане) на реальной файловой системе Windows.

Функции _sibling, _busy_message, _check_output_free, _clear_output скопированы из
плана; CaseConfigError и user_log — заглушки с тем же поведением. Сценарии:
свободный каталог, нет каталога, открытый файл (Python open — как Excel), консоль в
каталоге (текущий каталог дочернего процесса), корень диска, занятое соседнее имя,
неудача обратного переименования, неудача удаления переименованного каталога,
запасной каталог с меткой времени.
Запуск: numerical_solver\\.venv\\Scripts\\python vault/issues/debt-082/probes/plan_code/helpers_check.py
"""

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(format="[%(levelname)s] %(message)s")
user_log = logging.getLogger("gpn_multiphase_solver")


class CaseConfigError(ValueError):
    pass


# ── Код плана, шаг 1 (дословно) ──────────────────────────────

def _sibling(path: Path, suffix: str) -> Path:
    """Свободное имя <имя каталога><suffix>[-k] рядом с каталогом path; корень диска — CaseConfigError. DEBT-082."""
    # abspath, а не resolve: resolve на сетевом диске и диске subst заменил
    # бы букву диска реальным путём (проба аудита 1), и сообщения назвали бы
    # путь, которого инженер не вводил
    path = Path(os.path.abspath(path))
    # У корня диска (D:\) нет имени: соседнего каталога нет, переименовать
    # корень нельзя, а rmtree стёр бы весь диск. Отказ до любого действия
    if not path.name:
        raise CaseConfigError(
            f"каталог вывода {path} — корень диска: перед записью результатов "
            f"каталог очищается целиком. Укажите подкаталог.")
    k = 0
    while True:
        cand = path.with_name(f"{path.name}{suffix}" + (f"-{k}" if k else ""))
        if not cand.exists():
            return cand
        k += 1


def _busy_message(output_dir: Path, exc: OSError) -> str:
    """Текст отказа очистки каталога вывода: причина ОС и подсказка. DEBT-082."""
    return (f"каталог вывода {output_dir} не удаётся очистить ({exc.strerror or exc}): "
            f"файл в нём открыт в другой программе (например, CSV в Excel) или "
            f"каталог — текущий в консоли. Закройте файл или перейдите в консоли "
            f"в другой каталог")


def _check_output_free(output_dir: Path) -> None:
    """Каталог вывода удаляется целиком: проба переименованием туда и обратно, иначе CaseConfigError. DEBT-082."""
    # Windows не переименовывает каталог, в котором открыт файл без права
    # удаления (так открывает Excel) или который служит текущим каталогом
    # процесса, — и ничего при этом не трогает. rmtree на том же каталоге
    # удалил бы часть файлов, а при консоли в каталоге — все, и только
    # потом упал бы (пробы DEBT-082, vault/issues/debt-082/probes/).
    # Файл, открытый с правом удаления, переименование тоже не пропускает,
    # хотя rmtree прошёл бы, — отказ с запасом. На POSIX переименование
    # проходит, как и rmtree
    if not output_dir.is_dir():
        return
    probe = _sibling(output_dir, f".check-{os.getpid()}")
    try:
        os.rename(output_dir, probe)
    except OSError as exc:
        raise CaseConfigError(
            f"{_busy_message(output_dir, exc)} и повторите расчёт. Расчёт не "
            f"начат, каталог не изменён.") from exc
    try:
        os.rename(probe, output_dir)
    except OSError as exc:
        raise CaseConfigError(
            f"каталог вывода {output_dir} при проверке переименован в {probe} и "
            f"не возвращён ({exc.strerror or exc}): верните ему прежнее имя и "
            f"повторите расчёт.") from exc


def _clear_output(output_dir: Path) -> None:
    """Очистка каталога вывода: переименование в соседний, затем его удаление; OSError переименования — каталог цел. DEBT-082."""
    # Переименование — точка невозврата. Прошло — каталог свободен (см.
    # _check_output_free), удаляется уже переименованный. Не прошло —
    # OSError вызывающему, ни один файл не тронут: прямой rmtree успевал
    # удалить часть файлов до отказа (проба аудита 1 FEAT-036)
    if not output_dir.is_dir():
        return
    trash = _sibling(output_dir, f".old-{os.getpid()}")
    os.rename(output_dir, trash)
    try:
        shutil.rmtree(trash)
    except OSError as exc:
        # Файл открыли в уже переименованном каталоге — почти невозможно, но
        # прежние результаты под чужим именем не должны остаться молча
        user_log.warning(f"прежние результаты перенесены в {trash} и не удалены "
                         f"({exc.strerror or exc}); удалите этот каталог вручную.")


# ── Сценарии ──────────────────────────────────────────────────

here = Path(__file__).resolve().parent
base = here / "work"


def fresh() -> Path:
    shutil.rmtree(base, ignore_errors=True)
    out = base / "output"
    out.mkdir(parents=True)
    for n in ("a.png", "well_history.csv", "z.csv"):
        (out / n).write_text("1", encoding="utf-8")
    return out


def state(out: Path) -> str:
    names = sorted(p.name for p in out.iterdir()) if out.is_dir() else "нет каталога"
    extra = sorted(p.name for p in base.iterdir() if p.name != "output")
    return f"в output: {names}; рядом: {extra}"


def report(label: str, fn) -> None:
    try:
        fn()
        print(f"{label}: прошло")
    except (CaseConfigError, OSError) as exc:
        print(f"{label}: {type(exc).__name__}: {exc}")


try:
    out = fresh()
    report("1 свободный: проверка", lambda: _check_output_free(out))
    print("   " + state(out))
    report("1 свободный: очистка", lambda: _clear_output(out))
    print("   " + state(out))

    report("2 нет каталога: проверка и очистка",
           lambda: (_check_output_free(out), _clear_output(out)))

    out = fresh()
    f = open(out / "well_history.csv", "w", encoding="utf-8")
    report("3 открытый файл: проверка", lambda: _check_output_free(out))
    print("   " + state(out))
    report("3 открытый файл: очистка", lambda: _clear_output(out))
    print("   " + state(out))
    f.close()

    out = fresh()
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], cwd=out)
    time.sleep(0.5)
    report("4 консоль в каталоге: проверка", lambda: _check_output_free(out))
    report("4 консоль в каталоге: очистка", lambda: _clear_output(out))
    print("   " + state(out))
    p.kill()
    p.wait()

    report("5 корень диска: проверка", lambda: _check_output_free(Path(Path.cwd().anchor)))

    out = fresh()
    (base / f"output.check-{os.getpid()}").mkdir()
    print(f"6 занятое соседнее имя: {_sibling(out, f'.check-{os.getpid()}').name}")
    report("6 занятое соседнее имя: проверка", lambda: _check_output_free(out))
    print("   " + state(out))

    out = fresh()
    real_rename = os.rename

    def back_fails(src, dst):
        if Path(dst) == out:
            raise PermissionError(13, "Access is denied", str(src))
        return real_rename(src, dst)
    os.rename = back_fails
    report("7 обратное переименование не прошло", lambda: _check_output_free(out))
    os.rename = real_rename
    print("   " + state(out))

    out = fresh()
    real_rmtree = shutil.rmtree

    def rmtree_fails(path, *a, **k):
        raise PermissionError(13, "Access is denied", str(path))
    shutil.rmtree = rmtree_fails
    report("8 удаление переименованного не прошло", lambda: _clear_output(out))
    shutil.rmtree = real_rmtree
    print("   " + state(out))

    out = fresh()
    stamp = time.strftime("_%Y-%m-%d_%H-%M-%S")
    a = _sibling(out, stamp)
    a.mkdir()
    b = _sibling(out, stamp)
    print(f"9 запасной каталог: {a.name}, при занятом имени — {b.name}")
finally:
    shutil.rmtree(base, ignore_errors=True)
