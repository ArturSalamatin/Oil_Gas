"""Выпуск решателя для испытаний внутри команды: python tools/release.py X.Y.Z (FEAT-038).

Перед запуском раздел «## Не выпущено» в numerical_solver/CHANGELOG.md
заполнен и закоммичен. Пункты задач пишет /implement (фаза 4.1, там же форма
пункта). Правки без задачи (например, README) Claude по просьбе сводит по
git log от прошлой метки в ту же форму, вместо номера – область:
«- **README.** …». Форму проверяет tests/test_packaging.py -k changelog из
numerical_solver – после правки раздела и в самопроверке шага 3.
Запуск — из корня репозитория, интерпретатором venv решателя
(нужны packaging, pytest и Sphinx – группа [dev]), в основном каталоге на ветке
numerical_scheme/implementation:

    numerical_solver\\.venv\\Scripts\\python tools\\release.py 1.0.0

Не запускать, пока другая сессия вливает ветку в базовую (/merge): скрипт
коммитит в ту же ветку. Push уносит на origin и все прежние локальные
коммиты базовой ветки.

Порядок:
  1. Проверки, до любых изменений: gh установлен и авторизован; в venv
     есть pytest и Sphinx; ветка
     numerical_scheme/implementation, не позади origin; в numerical_solver/
     нет незакоммиченных правок отслеживаемых файлов (неотслеживаемые не
     мешают: сборка идёт из метки); X.Y.Z — три числа без суффикса, больше
     текущего номера и прошлого выпуска; метки vX.Y.Z нет ни локально, ни на
     origin; в «Не выпущено» есть хотя бы один пункт «- ».
  2. Номера — локальный коммит «release: X.Y.Z» и метка vX.Y.Z:
     __version__ = "X.Y.Z"; «## Не выпущено» → «## X.Y.Z — <дата>»; если с
     прошлого выпуска (у первого — с 29a1ffa, DEBT-059) изменились
     radial_blackoil/ или pyproject.toml прототипа — +gpn.N → +gpn.N+1 в
     литерале прототипа и в требовании numerical_solver/pyproject.toml.
  3. Сборка из метки, не из рабочего каталога, в dist/vX.Y.Z/: дерево
     numerical_solver метки → архив примеров examples-vX.Y.Z.zip (без
     примеров 18 и 23) → README.md решателя → HTML-документация (sphinx -W),
     архив docs-vX.Y.Z.zip → самопроверка tests/test_packaging.py дерева
     метки → pip wheel --no-deps: ровно два колеса с ожидаемыми номерами
     в именах.
  4. Следующая разработка — локальный коммит «release: начало X.Y.(Z+1).dev0»:
     __version__ = "X.Y.(Z+1).dev0" (заглушка: номер следующего выпуска
     задаёт аргумент команды), пустой раздел «Не выпущено»; самопроверка
     рабочего каталога.
  5. Один push: ветка и метка вместе (--atomic).
  6. Публикация: gh release create vX.Y.Z — пять файлов: два колеса, архив
     примеров, README.md решателя и архив HTML-документации; заметки —
     раздел выпуска из журнала, строки каждого абзаца склеены в одну:
     перенос строки в описании выпуска GitHub показывает как <br> (DEBT-086).

Отказ на шагах 2–5 — скрипт откатывает свои коммиты и метку (git tag -d,
git reset --keep к исходному коммиту; другие незакоммиченные файлы, например
vault, не трогаются) и завершается с кодом 1; dist/vX.Y.Z/ остаётся для
разбора. Отказ шага 6 — ветка и метка уже на origin: скрипт печатает команду
gh для повтора. Опубликованный выпуск не меняется; исправление — новый выпуск.

Установка у получателя – README решателя, раздел «Начало работы», «Поставка для расчётов».
"""

from __future__ import annotations

import datetime
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

try:
    from packaging.version import InvalidVersion, Version
except ImportError:   # системный Python без packaging — нужен venv решателя
    sys.exit("Нет пакета packaging: запускать интерпретатором numerical_solver\\.venv")

ROOT = Path(__file__).resolve().parents[1]      # корень репозитория Oil_Gas
BRANCH = "numerical_scheme/implementation"      # базовая ветка солвера (CLAUDE.md)
REPO = "ArturSalamatin/Oil_Gas"

# Пути — от корня репозитория, через «/»: они же пути git
SOLVER = "numerical_solver"
PROTO = f"{SOLVER}/HydroSolverPrototype/Prototype_1.0.3"
SOLVER_INIT = f"{SOLVER}/gpn_multiphase_solver/__init__.py"
PROTO_INIT = f"{PROTO}/radial_blackoil/__init__.py"
SOLVER_PYPROJECT = f"{SOLVER}/pyproject.toml"
CHANGELOG = f"{SOLVER}/CHANGELOG.md"
EDITED = (SOLVER_INIT, PROTO_INIT, SOLVER_PYPROJECT, CHANGELOG)   # всё, что правит скрипт
# Всё, из чего собирается колесо прототипа: изменение повышает +gpn.N
PROTO_WHEEL_SOURCES = (f"{PROTO}/radial_blackoil", f"{PROTO}/pyproject.toml")
FIRST_BASE = "29a1ffa"     # DEBT-059: введён номер 1.0.3+gpn.1 — база первого выпуска
HANDOVER = Path(__file__).resolve().parent / "handover.py"   # передача, шаг 3 (DEBT-089)

UNRELEASED = "## Не выпущено"
# Пример 18 читает книги и эталон CMG IMEX из дерева прототипа — в архиве
# примеров и в колесе их нет (решение пользователя 2026-10-18). Пример 23
# считает из папки с исходным кодом решателя и прототипа (FEAT-040) – в
# поставке для расчётов её нет
EXCLUDED_EXAMPLES = ("18_prototype_input", "23_source_tree_run")
# Хвост описания выпуска; {archive} – имя архива передачи этого номера
NOTES_TAIL = ("Архив `{archive}` содержит поставку для разработки: исходный код "
              "решателя и прототипа, тесты, все примеры, собранные HTML-документацию "
              "и PDF постановки. Остальные пять файлов составляют поставку для "
              "расчётов. Порядок работы с обеими поставками описан в README, раздел "
              "«Начало работы». "
              "Архив примеров – без примеров 18 (`18_prototype_input`) и 23 "
              "(`23_source_tree_run`): примеру 18 нужны книги и эталон CMG IMEX "
              "из дерева прототипа, примеру 23 – исходный код решателя и прототипа.")

# Литерал __version__ = "…" (у прототипа — без пробелов и в одинарных кавычках)
VERSION_RE = re.compile(r"""^(__version__\s*=\s*)(['"])([^'"]+)\2""", re.M)


class ReleaseError(Exception):
    """Отказ выпуска; текст — для пользователя."""


# ── Вызовы git и проверка ──

def run(cmd: list, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Команда без проверки кода возврата (по умолчанию — в корне репозитория); вывод — текст UTF-8."""
    # PYTHONUTF8: вывод pytest и pip с кириллицей — в UTF-8, не в кодовой странице консоли
    return subprocess.run([str(c) for c in cmd], cwd=cwd or ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          env={**os.environ, "PYTHONUTF8": "1"})


def git(*args: str) -> str:
    """git в корне репозитория; при ненулевом коде — ReleaseError."""
    r = run(["git", *args])
    if r.returncode != 0:
        raise ReleaseError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


# ── Литералы номеров ──
# Файлы читаются и пишутся байтами: в рабочем дереве окончания строк CRLF
# (core.autocrlf=true), текстовый режим Python их бы не сохранил

def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def read_version(path: Path) -> str:
    """Единственный литерал __version__ файла."""
    found = VERSION_RE.findall(read_text(path))
    if len(found) != 1:
        raise ReleaseError(f"{path}: литералов __version__ {len(found)}, ожидался один")
    return found[0][2]


def write_version(path: Path, new: str) -> None:
    """Заменить литерал __version__, сохранив кавычки."""
    text, n = VERSION_RE.subn(lambda m: f"{m[1]}{m[2]}{new}{m[2]}", read_text(path))
    if n != 1:
        raise ReleaseError(f"{path}: литералов __version__ {n}, ожидался один")
    write_text(path, text)


def write_proto_pin(path: Path, old: str, new: str) -> None:
    """Требование radial-blackoil==old → ==new в pyproject.toml решателя."""
    text = read_text(path)
    old_pin, new_pin = f'"radial-blackoil=={old}"', f'"radial-blackoil=={new}"'
    if text.count(old_pin) != 1:
        raise ReleaseError(f"{path}: строка {old_pin} встречается {text.count(old_pin)} раз")
    write_text(path, text.replace(old_pin, new_pin))


def next_gpn(version: str) -> str:
    """1.0.3+gpn.N → 1.0.3+gpn.N+1 (правило номеров прототипа, CHANGELOG.md)."""
    m = re.fullmatch(r"(.+\+gpn\.)(\d+)", version)
    if m is None:
        raise ReleaseError(f"номер прототипа {version!r} — не вида 1.0.3+gpn.N")
    return f"{m[1]}{int(m[2]) + 1}"


def next_dev(version: str) -> str:
    """X.Y.Z → X.Y.(Z+1).dev0."""
    v = Version(version)
    return f"{v.major}.{v.minor}.{v.micro + 1}.dev0"


# ── Журнал ──

def section_body(text: str, head: str) -> str:
    """Текст раздела от строки, начинающейся с head, до следующего «## »."""
    lines = text.splitlines()
    starts = [i for i, s in enumerate(lines) if s.startswith(head)]
    if len(starts) != 1:
        raise ReleaseError(f"{CHANGELOG}: заголовков «{head}…» {len(starts)}, ожидался один")
    body = []
    for line in lines[starts[0] + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body).strip()


def changelog_release(text: str, version: str, date: str) -> str:
    """«## Не выпущено» → «## X.Y.Z — дата»."""
    # (?=\r?$): в рабочем дереве строки кончаются CRLF, «$» в re.M стоит перед \n
    new, n = re.subn(rf"^{UNRELEASED}(?=\r?$)", f"## {version} — {date}", text, flags=re.M)
    if n != 1:
        raise ReleaseError(f"{CHANGELOG}: строк «{UNRELEASED}» {n}, ожидалась одна")
    return new


def changelog_new_unreleased(text: str, version: str) -> str:
    """Пустой «## Не выпущено» над разделом выпуска X.Y.Z."""
    eol = "\r\n" if "\r\n" in text else "\n"
    found = list(re.finditer(rf"^## {re.escape(version)} — ", text, flags=re.M))
    if len(found) != 1:
        raise ReleaseError(f"{CHANGELOG}: разделов «## {version} — » {len(found)}, ожидался один")
    i = found[0].start()
    return text[:i] + UNRELEASED + eol + eol + text[i:]


# Заголовок – «#»…«######» и пробел (или конец строки): «#143» в начале
# перенесённой строки – продолжение абзаца, а не заголовок
HEADING_RE = re.compile(r"\s*#{1,6}(\s|$)")
# Начало элемента разметки: пустая строка, заголовок, пункт списка (и
# вложенного), строка таблицы, цитата. Такая строка к предыдущей не клеится
BLOCK_START_RE = re.compile(r"\s*($|#{1,6}(\s|$)|[-*+] |\d+[.)] |\||>)")


def unwrap_paragraphs(text: str) -> str:
    """Строки каждого абзаца и пункта списка – в одну; блоки кода не трогаются (DEBT-086)."""
    # В описании выпуска GitHub отображает перенос строки исходного текста
    # как <br>: пункт журнала, перенесённый по ~76 знаков, рвался посреди фраз
    out: list[str] = []
    fence = False                       # внутри блока кода ```
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```"):
            fence = not fence
            out.append(line)
            continue
        prev = out[-1].strip() if out else ""
        # Продолжение абзаца: предыдущая строка – текст (не пустая, не
        # заголовок, не ограда кода), текущая не начинает новый элемент
        if (not fence and prev and not prev.startswith("```") and not HEADING_RE.match(prev)
                and not BLOCK_START_RE.match(line)):
            out[-1] = f"{out[-1].rstrip()} {s}"
        else:
            out.append(line)
    return "\n".join(out)


def release_notes(text: str, version: str) -> str:
    """Описание выпуска: раздел «## X.Y.Z — …» журнала со склеенными строками и NOTES_TAIL."""
    notes = unwrap_paragraphs(section_body(text, f"## {version} — "))
    return f"{notes}\n\n{NOTES_TAIL.format(archive=handover_archive(version).name)}\n"


# ── Шаг 1: проверки ──

def released_versions() -> list[Version]:
    """Номера прошлых выпусков — метки v*."""
    out = []
    for tag in git("tag", "--list", "v*").splitlines():
        try:
            out.append(Version(tag[1:]))
        except InvalidVersion:
            pass
    return out


def check_new_version(arg: str, current: str, released: list[Version]) -> None:
    """X.Y.Z — три числа без суффикса, больше текущего номера и прошлых выпусков."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", arg) or str(Version(arg)) != arg:
        raise ReleaseError(f"номер {arg!r}: нужны три числа MAJOR.MINOR.PATCH без "
                           "ведущих нулей и суффиксов, например 1.0.0")
    if Version(arg) <= Version(current):
        raise ReleaseError(f"{arg} не больше текущего номера {current}")
    if released and Version(arg) <= max(released):
        raise ReleaseError(f"{arg} не больше прошлого выпуска {max(released)}")


def prototype_changed(base: str) -> bool:
    """Изменились ли с base исходники колеса прототипа."""
    r = run(["git", "diff", "--quiet", base, "HEAD", "--", *PROTO_WHEEL_SOURCES])
    if r.returncode not in (0, 1):
        raise ReleaseError(f"git diff {base}: {r.stderr.strip()}")
    return r.returncode == 1


def preflight(version: str) -> dict:
    """Все проверки шага 1; ничего не меняет. Результат — номера выпуска."""
    # PDF постановки собирает передача в шаге 3 – уже после коммита и метки
    # (DEBT-089): без pdflatex выпуск отказывает здесь, а не откатом
    if shutil.which("pdflatex") is None:
        raise ReleaseError("нет pdflatex в PATH (MiKTeX или TeX Live): PDF постановки в передаче")
    if shutil.which("gh") is None:
        raise ReleaseError("нет команды gh (GitHub CLI)")
    if run(["gh", "auth", "status"]).returncode != 0:
        raise ReleaseError("gh не авторизован: gh auth login")
    for module in ("pytest", "sphinx"):        # самопроверка и HTML-документация
        if importlib.util.find_spec(module) is None:
            raise ReleaseError(f"нет {module}: запускать интерпретатором numerical_solver\\.venv "
                               "с группой [dev]")
    branch = git("branch", "--show-current")
    if branch != BRANCH:
        raise ReleaseError(f"текущая ветка {branch!r}, выпуск — только из {BRANCH} основного каталога")
    git("fetch", "origin", BRANCH)
    behind = int(git("rev-list", "--count", f"HEAD..origin/{BRANCH}"))
    if behind:
        raise ReleaseError(f"ветка позади origin на {behind} коммитов: git pull")
    # Весь репозиторий, не только numerical_solver: файл выпуска собирает и
    # tools/handover.py рабочего каталога, а правки vault коммитятся до
    # выпуска (решение пользователя 2026-10-27). Неотслеживаемые файлы не
    # мешают: сборка идёт из метки
    dirty = git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise ReleaseError(f"незакоммиченные правки отслеживаемых файлов:\n{dirty}")

    current = read_version(ROOT / SOLVER_INIT)
    released = released_versions()
    check_new_version(version, current, released)
    tag = f"v{version}"
    if git("tag", "--list", tag) or git("ls-remote", "--tags", "origin", f"refs/tags/{tag}"):
        raise ReleaseError(f"метка {tag} уже есть")
    # У черновика выпуска метки нет — проверка выше его не видит, а gh release
    # create отказал бы уже после push, единственного шага без отката
    if run(["gh", "release", "view", tag, "--repo", REPO]).returncode == 0:
        raise ReleaseError(f"выпуск {tag} уже есть на GitHub (возможно, черновик)")
    body = section_body(read_text(ROOT / CHANGELOG), UNRELEASED)
    if not any(s.startswith("- ") for s in body.splitlines()):
        raise ReleaseError(f"в разделе «{UNRELEASED}» {CHANGELOG} нет ни одного пункта")

    proto_old = read_version(ROOT / PROTO_INIT)
    base = f"v{max(released)}" if released else FIRST_BASE
    proto_new = next_gpn(proto_old) if prototype_changed(base) else proto_old
    return {"version": version, "current": current, "base": base,
            "proto_old": proto_old, "proto_new": proto_new}


# ── Шаги 2 и 4: правка номеров ──

def apply_release_edits(root: Path, version: str, date: str, proto_old: str, proto_new: str) -> None:
    """Номера выпуска в дереве root (корень репозитория или его копия)."""
    write_version(root / SOLVER_INIT, version)
    if proto_new != proto_old:
        write_version(root / PROTO_INIT, proto_new)
        write_proto_pin(root / SOLVER_PYPROJECT, proto_old, proto_new)
    cl = root / CHANGELOG
    write_text(cl, changelog_release(read_text(cl), version, date))


def apply_dev_edits(root: Path, version: str) -> str:
    """Номер следующей разработки и пустой «Не выпущено»; возвращает номер."""
    dev = next_dev(version)
    write_version(root / SOLVER_INIT, dev)
    cl = root / CHANGELOG
    write_text(cl, changelog_new_unreleased(read_text(cl), version))
    return dev


# ── Шаг 3: сборка из метки ──

def handover_archive(version: str) -> Path:
    """Архив передачи tools/handover.py: dist/handover-<версия>/gpn-multiphase-solver-<версия>.zip."""
    # Один источник пути для выпуска и передачи: handover.py импортирует
    # release, обратный импорт невозможен (этот файл при запуске – __main__)
    top = f"gpn-multiphase-solver-{version}"
    return ROOT / "dist" / f"handover-{version}" / f"{top}.zip"      # dist/ – в .gitignore


def extract(treeish: str, dest: Path) -> Path:
    """Дерево numerical_solver из git (метка), не из рабочего каталога; путь к нему."""
    # Из рабочего каталога в колесо попали бы неотслеживаемые .py пакета и
    # устаревший build/ (подводный камень FEAT-038)
    r = subprocess.run(["git", "archive", "--format=tar", treeish, SOLVER],
                       cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        raise ReleaseError(f"git archive {treeish}: {r.stderr.decode('utf-8', 'replace')}")
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tar:
        tar.extractall(dest, filter="data")
    return dest / SOLVER


def zip_examples(examples: Path, target: Path) -> int:
    """Архив examples/ без EXCLUDED_EXAMPLES; пути внутри — examples/…; число файлов."""
    n = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(examples.rglob("*")):
            rel = p.relative_to(examples)
            if p.is_file() and rel.parts[0] not in EXCLUDED_EXAMPLES:
                z.write(p, Path("examples") / rel)
                n += 1
    return n


def build_docs(tree: Path, out: Path, version: str) -> tuple[Path, int]:
    """HTML-документация дерева метки (sphinx -W) – архив docs-vX.Y.Z.zip, index.html в корне; путь и число файлов."""
    # Номера уравнений – из doc/source/eq_numbers.json под git: LaTeX не нужен.
    # HTML и doctrees – вне дерева метки
    html = out / "html"
    r = run([sys.executable, "-m", "sphinx", "-W", "-b", "html", "-q", "-d", out / "doctrees",
             "doc/source", html], cwd=tree)
    if r.returncode != 0 or not (html / "index.html").is_file():
        raise ReleaseError(f"sphinx: код {r.returncode}\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
    target = out / f"docs-v{version}.zip"
    n = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(html.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(html))
                n += 1
    return target, n


def selfcheck(tree: Path) -> str:
    """tests/test_packaging.py дерева tree: все прошли, пропусков нет; итоговая строка."""
    # Тесты сверяют номер прототипа с требованием решателя, раздел журнала с
    # номером, форму литерала. На Python 3.10 тесты pyproject.toml
    # пропускаются (нет tomllib) — пропуск считается отказом
    r = run([sys.executable, "-m", "pytest", "tests/test_packaging.py", "-q",
             "-p", "no:cacheprovider"], cwd=tree)
    lines = r.stdout.strip().splitlines()
    last = lines[-1] if lines else ""
    if r.returncode != 0 or "passed" not in last or "skipped" in last:
        raise ReleaseError(f"самопроверка {tree}: {last}\n{r.stdout[-3000:]}")
    return last


def build_wheels(tree: Path, wheels: Path, version: str, proto_version: str) -> list[Path]:
    """Ровно два колеса: решатель и прототип с ожидаемыми номерами в именах."""
    # Изолированная сборка скачивает setuptools>=68: в venv его нет, нужен PyPI или кеш pip
    r = run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", wheels,
             tree / "HydroSolverPrototype" / "Prototype_1.0.3", tree])
    if r.returncode != 0:
        raise ReleaseError(f"pip wheel: код {r.returncode}\n{r.stderr[-3000:]}")
    expected = sorted([f"gpn_multiphase_solver-{version}-py3-none-any.whl",
                       f"radial_blackoil-{proto_version}-py3-none-any.whl"])
    got = sorted(p.name for p in wheels.glob("*.whl"))
    if got != expected:
        raise ReleaseError(f"колёса {got}, ожидались {expected}")
    return [wheels / name for name in expected]


def run_handover(tag: str, version: str, acceptance: bool) -> Path:
    """tools/handover.py для метки tag отдельным процессом; путь архива передачи."""
    # Отдельный процесс, не импорт: handover.py импортирует release, а этот
    # файл при запуске – модуль __main__, импорт загрузил бы его второй раз.
    # Вывод не перехватывается: прогресс передачи (с приёмкой – около 15 мин)
    # идёт сразу в консоль. PYTHONUTF8 не ставится: дочерний Python пишет в
    # тот же канал в той же кодировке, что и этот процесс (| Tee-Object, >)
    cmd = [sys.executable, HANDOVER, tag] + (["--acceptance"] if acceptance else [])
    sys.stdout.flush()      # строки выпуска – раньше вывода передачи и при выводе в канал
    code = subprocess.run([str(c) for c in cmd], cwd=ROOT).returncode
    if code != 0:
        raise ReleaseError(f"передача {tag}: код {code}, причина – в выводе выше")
    # Код проверяется до архива: при отказе в dist/ может лежать архив прошлой
    # попытки того же номера, и выпуск не должен его взять. Код 0 без архива
    # при нынешнем handover.py невозможен – проверка на случай его правки
    archive = handover_archive(version)
    if not archive.is_file():
        raise ReleaseError(f"передача {tag}: нет архива {archive.relative_to(ROOT)}")
    return archive


def build(tag: str, out: Path, version: str, proto_version: str, acceptance: bool) -> list[Path]:
    """Шаг 3: архив примеров, README, документация, заметки, самопроверка, колёса и передача из метки."""
    if out.exists():          # остаток прошлой неудачной попытки с тем же номером
        shutil.rmtree(out)
    tree = extract(tag, out / "src")
    examples_zip = out / f"examples-v{version}.zip"
    # Архив — до запуска тестов и сборки: они пишут в дерево (__pycache__, build/)
    n = zip_examples(tree / "examples", examples_zip)
    print(f"  архив примеров: {examples_zip.name}, файлов {n}")
    # README решателя и документация – получателю выпуска: без них нет
    # описания файла конфигурации (README §3) и вызова из Python (§4)
    readme = out / "README.md"
    shutil.copyfile(tree / "README.md", readme)
    docs_zip, n = build_docs(tree, out, version)
    print(f"  README.md; документация: {docs_zip.name}, файлов {n}")
    write_text(out / "notes.md", release_notes(read_text(tree / "CHANGELOG.md"), version))
    print(f"  самопроверка метки: {selfcheck(tree)}")
    wheels = build_wheels(tree, out / "wheels", version, proto_version)
    print("  колёса: " + ", ".join(p.name for p in wheels))
    # Передача – последней: она дольше всех (с приёмкой – около 15 мин), и
    # отказ более быстрой сборки откатывает выпуск, не дожидаясь её
    print(f"  передача: tools/handover.py {tag}" + (" --acceptance" if acceptance else ""))
    archive = run_handover(tag, version, acceptance)
    return wheels + [examples_zip, readme, docs_zip, archive]


# ── Откат ──

def rollback(start: str, tag: str) -> None:
    """Вернуть ветку к start и удалить метку; другие незакоммиченные файлы не трогаются."""
    # Сначала — незакоммиченные правки скрипта в EDITED (на старте эти файлы
    # были чистыми, шаг 1): иначе reset --keep откажет на них
    git("restore", "--source=HEAD", "--staged", "--worktree", "--", *EDITED)
    if git("tag", "--list", tag):
        git("tag", "-d", tag)
    if git("rev-parse", "HEAD") != start:
        # --keep, не --hard: незакоммиченные файлы вне EDITED (vault) остаются
        git("reset", "--keep", start)


# ── Выпуск ──

def main(argv: list[str]) -> int:
    # Вывод в канал или файл (| Tee-Object, >) без PYTHONIOENCODING — в cp1251:
    # «→» и выводы git/pytest в нём не кодируются. Знак заменяется «?», а не
    # обрывает выпуск трассировкой (как _print_safe в examples/run_all.py)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")
    # Приёмка архива передачи – только по явному ключу, как у tools/handover.py
    args = [a for a in argv if a != "--acceptance"]
    with_acceptance = len(args) != len(argv)
    if len(args) != 1 or args[0].startswith("-"):
        print(__doc__)
        return 2
    try:
        p = preflight(args[0])
    except ReleaseError as e:
        print(f"Отказ (ничего не изменено): {e}")
        return 1
    version, tag = p["version"], f"v{p['version']}"
    out = ROOT / "dist" / tag       # dist/ — в .gitignore
    start = git("rev-parse", "HEAD")
    proto = p["proto_new"]
    print(f"Выпуск {version}: решатель {p['current']} → {version}, прототип "
          + (f"{p['proto_old']} → {proto} (изменён с {p['base']})" if proto != p["proto_old"]
             else f"{proto} (не менялся с {p['base']})")
          + ("; с приёмкой архива передачи" if with_acceptance else ""))
    push_started = False
    try:
        print("Шаг 2: номера, коммит и метка (локально)")
        apply_release_edits(ROOT, version, datetime.date.today().isoformat(), p["proto_old"], proto)
        git("commit", "-m", f"release: {version}", "--", *EDITED)
        git("tag", "-a", tag, "-m", f"Выпуск {version}")
        print(f"Шаг 3: сборка из метки в {out.relative_to(ROOT)}")
        assets = build(tag, out, version, proto, with_acceptance)
        print("Шаг 4: следующая разработка (локально)")
        dev = apply_dev_edits(ROOT, version)
        git("commit", "-m", f"release: начало {dev}", "--", SOLVER_INIT, CHANGELOG)
        print(f"  самопроверка рабочего каталога: {selfcheck(ROOT / SOLVER)}")
        print("Шаг 5: push ветки и метки")
        push_started = True
        git("push", "--atomic", "origin", BRANCH, f"refs/tags/{tag}")
    except BaseException as e:      # и Ctrl+C: локальные коммиты не должны остаться
        if push_started:
            # push --atomic: метка на origin — значит, и ветка; откат разошёлся бы с origin
            r = run(["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"])
            if r.returncode != 0 or r.stdout.strip():
                print(f"Отказ на push ({e}): метка {tag} на origin или проверить не удалось — "
                      f"откат не выполняется. Проверить: git ls-remote --tags origin {tag}")
                return 1
        try:
            rollback(start, tag)
            print(f"Отказ: {e}\nОткат выполнен: ветка на {start[:7]}, метки {tag} нет; "
                  f"сборка – {out.relative_to(ROOT)}, передача – "
                  f"{handover_archive(version).parent.relative_to(ROOT)}")
        except ReleaseError as e2:
            print(f"Отказ: {e}\nОткат не удался: {e2}\nВручную: git tag -d {tag}; "
                  f"git reset --keep {start}")
        return 1

    print("Шаг 6: публикация")
    cmd = ["gh", "release", "create", tag, *assets, "--repo", REPO, "--title", version,
           "--notes-file", out / "notes.md", "--verify-tag"]
    r = run(cmd)
    if r.returncode != 0:
        print(f"Отказ gh: {r.stderr.strip()}\nВетка и метка уже на origin. Повторить:\n"
              + subprocess.list2cmdline([str(c) for c in cmd]))
        return 1
    print(f"Выпуск {tag}: {r.stdout.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
