"""DEBT-082, план: краевые случаи проверки «каталог удаляется целиком» переименованием.

Для каждого случая — два свежих каталога: в одном пробуется os.rename (проверка
плана), в другом shutil.rmtree (текущая очистка). Ложный отказ проверки — rename
отказал, а rmtree прошёл бы целиком; пропуск — rename прошёл, а rmtree отказал.

Случаи:
  1. файл открыт без FILE_SHARE_DELETE (Python open, как Excel) — базовый, rename_check.py;
  2. файл открыт с FILE_SHARE_DELETE (CreateFileW, разделение чтение/запись/удаление);
  3. дескриптор самого каталога с разделением всего (как наблюдение Проводника
     за открытой папкой: ReadDirectoryChangesW);
  4. текущий каталог другого процесса — каталог вывода (консоль, сделавшая cd в output).
Каталоги — рядом со скриптом, удаляются в конце.
Запуск: numerical_solver\\.venv\\Scripts\\python vault/issues/debt-082/probes/edge_cases.py
"""

import ctypes
import os
import shutil
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

here = Path(__file__).resolve().parent
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
FILE_LIST_DIRECTORY = 0x0001
SHARE_ALL = 0x1 | 0x2 | 0x4            # FILE_SHARE_READ | WRITE | DELETE
OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS = 3, 0x02000000
INVALID = wintypes.HANDLE(-1).value


def _win_open(path: Path, access: int, flags: int = 0):
    h = k32.CreateFileW(str(path), access, SHARE_ALL, None, OPEN_EXISTING, flags, None)
    if h == INVALID:
        raise ctypes.WinError(ctypes.get_last_error())
    return lambda: k32.CloseHandle(h)


def hold_plain(out):
    f = open(out / "well_history.csv", "w", encoding="utf-8")
    return f.close


def hold_share_delete(out):
    return _win_open(out / "well_history.csv", GENERIC_READ | GENERIC_WRITE)


def hold_dir_handle(out):
    return _win_open(out, FILE_LIST_DIRECTORY, FILE_FLAG_BACKUP_SEMANTICS)


def hold_cwd(out):
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], cwd=out)
    time.sleep(0.5)
    return lambda: (p.kill(), p.wait())


def fresh(name: str) -> Path:
    out = here / name
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    for n in ("a.png", "well_history.csv", "z.csv"):
        (out / n).write_text("1", encoding="utf-8")
    return out


def outcome(action, out: Path) -> str:
    try:
        action(out)
        return "прошло"
    except OSError as exc:
        left = sorted(p.name for p in out.iterdir()) if out.is_dir() else "каталога нет"
        return f"отказ WinError {getattr(exc, 'winerror', None)}, осталось {left}"


def rename_there_and_back(out: Path) -> None:
    tmp = out.with_name(out.name + ".check")
    os.rename(out, tmp)
    os.rename(tmp, out)


for label, hold in (("1 файл без FILE_SHARE_DELETE", hold_plain),
                    ("2 файл с FILE_SHARE_DELETE", hold_share_delete),
                    ("3 дескриптор каталога (Проводник)", hold_dir_handle),
                    ("4 текущий каталог процесса", hold_cwd)):
    res = []
    for action, name in ((rename_there_and_back, "rename"), (shutil.rmtree, "rmtree")):
        out = fresh(f"edge_{name}")
        release = hold(out)
        try:
            res.append(f"{name}: {outcome(action, out)}")
        finally:
            release()
            shutil.rmtree(out, ignore_errors=True)
            shutil.rmtree(out.with_name(out.name + ".check"), ignore_errors=True)
    print(f"{label}: " + "; ".join(res))
