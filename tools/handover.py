"""Передача команде разработки заказчика: python tools/handover.py [<метка>] [--acceptance] (FEAT-031).

Срез numerical_solver из метки выпуска (git archive — только файлы под git,
вместе с атрибутами .gitattributes), PDF постановки, HTML-документация и
архив gpn-multiphase-solver-<версия>.zip; с ключом --acceptance – ещё приёмка
на его распакованной копии (tools/acceptance.py рядом – в срез не входит).
Git не меняется: ни коммитов, ни меток, ни push. Запуск — из корня
репозитория, интерпретатором venv решателя (нужны Sphinx — группа [dev] — и
packaging), нужны pdflatex в PATH, для приёмки – доступ к PyPI (она ставит
пакеты в свежее окружение):

    numerical_solver\\.venv\\Scripts\\python tools\\handover.py
    numerical_solver\\.venv\\Scripts\\python tools\\handover.py v1.0.1
    numerical_solver\\.venv\\Scripts\\python tools\\handover.py --acceptance

Без метки берётся последний выпуск – локальная метка vX.Y.Z с
наибольшим номером; меток выпуска нет – отказ.

Порядок:
  1. метка — коммит; версия — литерал __version__ решателя в метке;
  2. срез в dist/handover-<версия>/gpn-multiphase-solver-<версия>/;
  3. PDF постановки (pdflatex дважды), сверка таблицы номеров уравнений с
     .aux (tools/eq_numbers.py --check), побочные файлы LaTeX — удалить;
  4. HTML-документация (sphinx -W) в doc/build/html/ среза;
  5. архив gpn-multiphase-solver-<версия>.zip;
  6. только с --acceptance: приёмка на распакованной копии архива
     (dist/handover-<версия>/check/), около 15 мин.

Метка не вида vX.Y.Z или номер с .dev — предупреждение: заказчику
передаётся только выпуск (метка tools/release.py), а прогон на коммите
ветки — проверка самого скрипта. Код возврата: 0 — архив готов (с
--acceptance – и приёмка пройдена), 1 — отказ (каталог
dist/handover-<версия>/ остаётся для разбора), 2 — неверные аргументы.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

# release.py лежит рядом: общий для выпуска и передачи способ взять дерево из метки
sys.path.insert(0, str(Path(__file__).resolve().parent))
import release  # noqa: E402

ROOT = release.ROOT                                  # корень репозитория Oil_Gas
SOLVER = release.SOLVER                              # "numerical_solver"
INIT = f"{SOLVER}/gpn_multiphase_solver/__init__.py"
RELEASE_TAG_RE = re.compile(r"v\d+\.\d+\.\d+")       # метка выпуска tools/release.py


class HandoverError(Exception):
    """Отказ передачи с сообщением для пользователя."""


def run(cmd, cwd: Path, env: dict | None = None, timeout: float = 3600) -> subprocess.CompletedProcess:
    """Команда с выводом в строку (UTF-8, незнакомые байты — с заменой)."""
    # PYTHONUTF8: вывод дочернего Python с кириллицей — в UTF-8, а не в кодовой
    # странице консоли (как release.run)
    env = {**(env or os.environ), "PYTHONUTF8": "1"}
    return subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def tree_version(treeish: str) -> str:
    """Номер решателя в метке — литерал __version__, как его читает tools/release.py."""
    text = release.git("show", f"{treeish}:{INIT}")
    m = release.VERSION_RE.search(text)
    if not m:
        raise HandoverError(f"{treeish}:{INIT}: нет литерала __version__")
    return m.group(3)


def latest_release() -> str:
    """Последняя метка выпуска vX.Y.Z – наибольшая по номеру среди локальных меток."""
    # По номеру, а не по дате: v1.0.10 новее v1.0.9; метки другого вида не выпуск
    tags = [t for t in release.git("tag", "--list", "v*").splitlines()
            if RELEASE_TAG_RE.fullmatch(t)]
    if not tags:
        raise HandoverError("нет меток выпуска vX.Y.Z: сначала выпуск tools/release.py")
    return max(tags, key=lambda t: tuple(int(x) for x in t[1:].split(".")))


def build_pdf(slice_dir: Path) -> Path:
    """PDF постановки: pdflatex дважды (второй проход — ссылки и номера)."""
    doc = slice_dir / "doc"
    for _ in range(2):
        r = run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                 "problem_statement.tex"], cwd=doc, timeout=600)
        if r.returncode != 0:
            raise HandoverError(f"pdflatex: код {r.returncode}\n{r.stdout[-2000:]}")
    pdf = doc / "problem_statement.pdf"
    if not pdf.is_file():
        raise HandoverError("pdflatex не создал problem_statement.pdf")
    return pdf


def check_eq_table(slice_dir: Path) -> str:
    """Таблица номеров уравнений среза совпадает со свежим .aux; иначе — отказ."""
    r = run([sys.executable, "tools/eq_numbers.py", "--check"], cwd=slice_dir)
    if r.returncode != 0:
        raise HandoverError("таблица номеров уравнений устарела: обновите "
                            "doc/source/eq_numbers.json (tools/eq_numbers.py) и закоммитьте "
                            f"до выпуска\n{r.stdout[-2000:]}")
    return r.stdout.strip()


def clean_latex(slice_dir: Path) -> None:
    """Побочные файлы LaTeX — удалить: в срезе остаются .tex и .pdf."""
    for p in (slice_dir / "doc").glob("problem_statement.*"):
        if p.suffix not in (".tex", ".pdf"):
            p.unlink()


def build_html(slice_dir: Path, doctrees: Path) -> Path:
    """HTML-документация в doc/build/html/ среза, без предупреждений (-W)."""
    # Sphinx импортирует пакет из среза (conf.py): без __pycache__ в срезе;
    # промежуточные doctrees — вне среза
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = run([sys.executable, "-m", "sphinx", "-W", "-b", "html", "-q", "-d", doctrees,
             "doc/source", "doc/build/html"], cwd=slice_dir, env=env, timeout=600)
    index = slice_dir / "doc" / "build" / "html" / "index.html"
    if r.returncode != 0 or not index.is_file():
        raise HandoverError(f"sphinx: код {r.returncode}\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
    return index


def make_zip(slice_dir: Path, target: Path) -> int:
    """Архив среза с верхним каталогом — именем среза; число файлов."""
    n = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(slice_dir.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                z.write(p, Path(slice_dir.name) / p.relative_to(slice_dir))
                n += 1
    return n


def acceptance(archive: Path, check_dir: Path, top: str) -> int:
    """Распаковать архив и выполнить приёмку копии; код возврата приёмки."""
    if check_dir.exists():
        shutil.rmtree(check_dir)
    with zipfile.ZipFile(archive) as z:
        z.extractall(check_dir)
    # Скрипт приёмки – из рабочего дерева, не из метки: заказчику он не
    # передаётся и в срезе его нет (решение пользователя 2026-10-19)
    script = Path(__file__).resolve().parent / "acceptance.py"
    # Окружение без активированного venv: setup.bat ищет Python сам, как у заказчика.
    # Вывод приёмки — сразу в консоль: она идёт около 15 мин
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    return subprocess.run([sys.executable, str(script), str(check_dir / top)],
                          cwd=check_dir, env=env).returncode


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")
    # Приёмка – только по явному ключу: по умолчанию архив без неё
    args = [a for a in argv if a != "--acceptance"]
    with_acceptance = len(args) != len(argv)
    if len(args) > 1 or any(a.startswith("-") for a in args):
        print(__doc__)
        return 2
    t_all = time.perf_counter()
    try:
        if args:
            treeish = args[0]
        else:
            treeish = latest_release()
            print(f"Метка не указана – последний выпуск {treeish}")
        if shutil.which("pdflatex") is None:
            raise HandoverError("нет pdflatex в PATH (MiKTeX или TeX Live)")
        release.git("rev-parse", "--verify", f"{treeish}^{{commit}}")
        version = tree_version(treeish)
        if not RELEASE_TAG_RE.fullmatch(treeish) or ".dev" in version:
            print(f"ПРЕДУПРЕЖДЕНИЕ: {treeish} (номер {version}) — не выпуск: заказчику "
                  "передаётся только архив из метки выпуска tools/release.py")
        top = f"gpn-multiphase-solver-{version}"
        out = ROOT / "dist" / f"handover-{version}"      # dist/ — в .gitignore
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)

        print(f"1. Срез {treeish} → {out.relative_to(ROOT)}/{top}", flush=True)
        tree = release.extract(treeish, out / "src")
        slice_dir = out / top
        tree.rename(slice_dir)
        shutil.rmtree(out / "src")

        print("2. PDF постановки, таблица номеров уравнений", flush=True)
        build_pdf(slice_dir)
        print(f"   {check_eq_table(slice_dir)}")
        clean_latex(slice_dir)

        print("3. HTML-документация (sphinx -W)", flush=True)
        build_html(slice_dir, out / "doctrees")

        archive = out / f"{top}.zip"
        n = make_zip(slice_dir, archive)
        print(f"4. Архив {archive.name}: файлов {n}, {archive.stat().st_size / 1e6:.1f} МБ",
              flush=True)
    except (HandoverError, release.ReleaseError, subprocess.TimeoutExpired) as e:
        print(f"Отказ: {e}")
        return 1

    if not with_acceptance:
        print(f"Передача {version}: архив {archive}; приёмка не выполнялась "
              f"(ключ --acceptance); {time.perf_counter() - t_all:.0f} с")
        return 0

    print("5. Приёмка на распакованной копии", flush=True)
    code = acceptance(archive, out / "check", top)
    print(f"Передача {version}: архив {archive}; приёмка – "
          f"{'пройдена' if code == 0 else f'НЕ пройдена (код {code})'}; "
          f"{time.perf_counter() - t_all:.0f} с")
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
