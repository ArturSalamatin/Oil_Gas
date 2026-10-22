"""Снимок вывода примеров: печать и хеши файлов output/ — через main.py или команду пакета (FEAT-030).

Копия пробы DEBT-011 (vault/issues/debt-011/probes/snapshot_examples.py) с
одним отличием — способом запуска примера. По исходному плану FEAT-030
убирал main.py у примеров без собственной логики, их вывод давала команда
    python -m gpn_multiphase_solver run <конфиг>
Решение 6 плана оставило main.py у всех 23 (у 17 — обёртка этой команды),
поэтому все примеры запускаются своим main.py; ветка «без main.py —
командой» сохранена на случай примера без скрипта. Способ записывается в снимок
("runner") и при сравнении не учитывается: критерий неизменности — тот же
вывод при любом способе запуска.

DEBT-011 / FEAT-030 — перенос кода без изменения чисел. Критерий
неизменности — вывод всех примеров до и после переноса совпадает: текст
печати (stdout, stderr) и побайтно каждый файл в examples/<пример>/output/
(PNG, CSV).

Запуск каждого примера — отдельный процесс из numerical_solver проверяемого
дерева, с PYTHONPATH на это дерево: в worktree скрипты примеров без него
берут пакет основного каталога (заметка reference_worktree_pythonpath).
Команде путь к конфигу передаётся абсолютным — так же его печатал
run_example (main.py передавал Path(__file__).parent / "config.json").
EMF выключен (GPN_EXAMPLES_EMF=0): Inkscape не нужен, emf/ не создаётся.

Нормализация печати:
  - путь к дереву заменяется на <TREE> (main.py печатают пути конфига и
    output/, у worktree и основного каталога они разные);
  - строки времени выполнения (TIME_PATTERNS) при сравнении отбрасываются;
    в снимке хранится полный текст, фильтр применяется в --compare, поэтому
    новый шаблон не требует повторного прогона.

Снимок:
    cd <дерево>\\numerical_solver
    <python> <этот файл> snap --tree . --out <файл.json> [--only 01 03]
Сравнение:
    <python> <этот файл> compare <до.json> <после.json>
Код возврата compare: 0 — совпало, 1 — есть расхождения.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Строки, зависящие от времени выполнения, — не от чисел расчёта.
TIME_PATTERNS = [
    re.compile(r"^Время расчёта:"),
]

# Файлы, в которые прототип пишет время выполнения ("wall_seconds"), — от
# прогона к прогону разные при одном и том же коде (проверено двумя прогонами
# примера 18 на одном дереве, DEBT-011). Сравниваются не побайтно, а
# отмечаются отдельно.
TIME_FILES = {
    "18_prototype_input": {"prototype/results.xlsx", "prototype/run_summary.json",
                           "prototype/run_summary.txt", "prototype/summary.json"},
}


def _sha(path: Path) -> str:
    """SHA-256 содержимого файла."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize(text: str, tree: Path) -> str:
    """Путь дерева → <TREE>, в обеих формах разделителей."""
    for form in {str(tree), str(tree).replace("\\", "/")}:
        text = text.replace(form, "<TREE>")
    return text


def _package_path(env: dict, cwd: Path) -> str:
    """Путь пакета, который увидят скрипты примеров с этим окружением."""
    out = subprocess.run(
        [sys.executable, "-c",
         "import gpn_multiphase_solver as g; print(g.__file__)"],
        cwd=cwd, env=env, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def snap(tree: Path, out: Path, only: list[str] | None) -> None:
    """Прогнать main.py примеров дерева и записать снимок в JSON."""
    tree = tree.resolve()
    examples = tree / "examples"
    env = dict(os.environ)
    # Пакет и прототип — из проверяемого дерева (правило 3 /implement).
    # Прототип без этого брался бы из основного каталога (установка -e), и
    # задача, влитая в базу между снимками «до» и «после» с правкой прототипа
    # (аудит FEAT-030: BUG-025 правит radial_blackoil/blackoil.py), дала бы
    # ложное расхождение — или скрыла настоящее.
    proto = tree / "HydroSolverPrototype" / "Prototype_1.0.3"
    env["PYTHONPATH"] = os.pathsep.join([str(tree), str(proto)])
    env["GPN_EXAMPLES_EMF"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"

    # Страж: пакет и прототип должны браться из проверяемого дерева, а не из
    # основного каталога, — иначе снимок «после» молча повторит снимок «до».
    pkg = Path(_package_path(env, tree)).resolve()
    if tree not in pkg.parents:
        raise SystemExit(f"пакет взят не из дерева {tree}: {pkg}")
    print(f"пакет: {pkg}")
    rb = Path(subprocess.run(
        [sys.executable, "-c", "import radial_blackoil as r; print(r.__file__)"],
        cwd=tree, env=env, capture_output=True, text=True, check=True).stdout.strip()).resolve()
    if tree not in rb.parents:
        raise SystemExit(f"прототип взят не из дерева {tree}: {rb}")
    print(f"прототип: {rb}")

    # Пример — папка с config.json (после FEAT-030 main.py есть не у всех)
    folders = sorted(d for d in examples.iterdir()
                     if d.is_dir() and (d / "config.json").is_file())
    if only:
        folders = [d for d in folders if any(d.name.startswith(p) for p in only)]

    result = {"tree": str(tree), "examples": {}}
    for d in folders:
        t0 = time.perf_counter()
        if (d / "main.py").is_file():
            runner = "main.py"
            cmd = [sys.executable, str(d / "main.py")]
        else:
            runner = "command"
            cmd = [sys.executable, "-m", "gpn_multiphase_solver", "run",
                   str((d / "config.json").resolve())]
        proc = subprocess.run(
            cmd, cwd=tree, env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        files = {}
        output = d / "output"
        if output.is_dir():
            for f in sorted(output.rglob("*")):
                if f.is_file():
                    files[f.relative_to(output).as_posix()] = _sha(f)
        result["examples"][d.name] = {
            "runner": runner,
            "returncode": proc.returncode,
            "stdout": _normalize(proc.stdout, tree),
            "stderr": _normalize(proc.stderr, tree),
            "files": files,
        }
        print(f"{d.name} ({runner}): код {proc.returncode}, файлов {len(files)}, "
              f"{time.perf_counter() - t0:.0f} с", flush=True)

    out.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"снимок: {out}")


def _lines(text: str) -> list[str]:
    """Строки печати без строк времени выполнения."""
    return [s for s in text.splitlines()
            if not any(p.search(s) for p in TIME_PATTERNS)]


def compare(a_path: Path, b_path: Path) -> int:
    """Сравнить два снимка; напечатать расхождения. 0 — совпало."""
    a = json.loads(a_path.read_text(encoding="utf-8"))["examples"]
    b = json.loads(b_path.read_text(encoding="utf-8"))["examples"]
    bad = 0
    for name in sorted(set(a) | set(b)):
        if name not in a or name not in b:
            print(f"{name}: есть только в {'после' if name in b else 'до'}")
            bad += 1
            continue
        ea, eb = a[name], b[name]
        msgs = []
        if ea["returncode"] != eb["returncode"]:
            msgs.append(f"код возврата {ea['returncode']} → {eb['returncode']}")
        for stream in ("stdout", "stderr"):
            la, lb = _lines(ea[stream]), _lines(eb[stream])
            if la != lb:
                diff = [(i, x, y) for i, (x, y) in enumerate(zip(la, lb)) if x != y]
                msgs.append(f"{stream}: строк {len(la)} → {len(lb)}, "
                            f"различий {len(diff) + abs(len(la) - len(lb))}")
                for i, x, y in diff[:5]:
                    msgs.append(f"    [{i}] до:    {x}")
                    msgs.append(f"    [{i}] после: {y}")
        fa, fb = ea["files"], eb["files"]
        skipped = TIME_FILES.get(name, set())
        for f in sorted(set(fa) | set(fb)):
            if f in skipped:
                continue
            if fa.get(f) != fb.get(f):
                state = ("нет до" if f not in fa else
                         "нет после" if f not in fb else "содержимое")
                msgs.append(f"файл {f}: {state}")
        if msgs:
            bad += 1
            print(f"{name}:")
            for m in msgs:
                print(f"  {m}")
        else:
            note = (f", без {len(skipped)} файлов с временем выполнения"
                    if skipped else "")
            print(f"{name}: совпадает ({len(fa) - len(skipped)} файлов{note})")
    print(f"итог: {'совпадает' if not bad else f'расхождения в {bad} примерах'}")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snap")
    s.add_argument("--tree", type=Path, required=True,
                   help="каталог numerical_solver проверяемого дерева")
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--only", nargs="*", help="префиксы папок примеров")
    c = sub.add_parser("compare")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)
    args = ap.parse_args()
    if args.cmd == "snap":
        snap(args.tree, args.out, args.only)
    else:
        sys.exit(compare(args.a, args.b))
