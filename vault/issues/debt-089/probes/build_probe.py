"""Проба DEBT-089: шаг 3 выпуска (release.build) на опубликованной метке v1.0.6.

Запуск из корня worktree интерпретатором venv основного каталога:
    <КОРЕНЬ>\\numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-089\\probes\\build_probe.py [--acceptance | --no-pdflatex]
Выходы – dist/ worktree (в .gitignore).
"""
import os
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path.cwd()                         # корень worktree: tools/ ветки, не основного каталога
sys.path.insert(0, str(ROOT / "tools"))
import release  # noqa: E402

TAG, VERSION, PROTO = "v1.0.6", "1.0.6", "1.0.3+gpn.2"
OUT = ROOT / "dist" / "probe-v1.0.6"
EXPECTED = sorted(["docs-v1.0.6.zip", "examples-v1.0.6.zip", "gpn-multiphase-solver-1.0.6.zip",
                   "gpn_multiphase_solver-1.0.6-py3-none-any.whl",
                   "radial_blackoil-1.0.3+gpn.2-py3-none-any.whl", "README.md"])


def main(argv: list[str]) -> int:
    # Как release.main: при выводе в файл (cp1251) незнакомый знак – «?», а не трассировка
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")
    print(f"release: {release.__file__}", flush=True)
    # В worktree скрипт обязан взять tools/ ветки (память: worktree и PYTHONPATH)
    assert Path(release.__file__).resolve().parent == (ROOT / "tools").resolve()
    if "--no-pdflatex" in argv:
        # PATH без каталогов с pdflatex: передача отказывает (код 1), build – ReleaseError
        os.environ["PATH"] = os.pathsep.join(
            d for d in os.environ["PATH"].split(os.pathsep)
            if d and not (Path(d) / "pdflatex.exe").is_file())
        try:
            release.build(TAG, OUT, VERSION, PROTO, False)
        except release.ReleaseError as e:
            print(f"ожидаемый отказ: {e}")
            return 0
        print("ОШИБКА: сборка без pdflatex не отказала")
        return 1
    t = time.perf_counter()
    assets = release.build(TAG, OUT, VERSION, PROTO, "--acceptance" in argv)
    print(f"build: {time.perf_counter() - t:.0f} с")
    names = sorted(p.name for p in assets)
    assert names == EXPECTED, names
    archive = assets[-1]
    assert archive == release.handover_archive(VERSION), archive
    with zipfile.ZipFile(archive) as z:
        files = z.namelist()
    top = "gpn-multiphase-solver-1.0.6/"
    assert all(f.startswith(top) for f in files)
    assert top + "doc/problem_statement.pdf" in files
    assert top + "doc/build/html/index.html" in files
    assert not any("__pycache__" in f or f.endswith("acceptance.py") for f in files)
    print(f"архив: файлов {len(files)}, {archive.stat().st_size / 1e6:.2f} МБ")
    notes = (OUT / "notes.md").read_text(encoding="utf-8")
    assert "`gpn-multiphase-solver-1.0.6.zip`" in notes
    print("проба: все проверки прошли")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
