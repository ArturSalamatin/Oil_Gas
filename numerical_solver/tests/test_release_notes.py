"""tools/release.py: описание выпуска (DEBT-086), разбор аргументов и вызов передачи (DEBT-089).

tools/release.py лежит в корне репозитория, вне numerical_solver: в срезе
заказчика (tools/handover.py, FEAT-031) его нет – тесты пропускаются, причина
пропуска записана в ALLOWED_SKIPS tools/acceptance.py. В test_packaging.py эти
тесты не кладутся: самопроверка выпуска запускает его в дереве метки, где
tools/ тоже нет, и считает пропуск отказом.
"""

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SOLVER = Path(__file__).resolve().parents[1]                 # numerical_solver/
TOOLS = SOLVER.parent / "tools"
SKIP_REASON = "нет tools/release.py – копия без корня репозитория (поставка, FEAT-031)"
if not (TOOLS / "release.py").is_file():
    pytest.skip(SKIP_REASON, allow_module_level=True)


def _load(name: str):
    """Модуль tools/<name>.py этого дерева; main() не вызывается (__name__ не "__main__")."""
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = _load("release")


def test_unwrap_joins_paragraph_lines():
    """Перенесённые строки первой строки пункта и абзаца-блока склеиваются через пробел."""
    # Каждый перенос в описании выпуска GitHub показал бы как <br>: после
    # склейки у абзаца ровно одна строка, пустые строки между абзацами целы
    text = ("- **FEAT-001.** Суть\n  одной фразой.\n\n"
            "  *Было.* Первая строка\n  вторая строка.\n")
    assert release.unwrap_paragraphs(text) == (
        "- **FEAT-001.** Суть одной фразой.\n\n"
        "  *Было.* Первая строка вторая строка.")
    # «#143» в начале перенесённой строки – не заголовок (нет пробела после «#»)
    assert release.unwrap_paragraphs("  *Было.* См. issue\n  #143.") == "  *Было.* См. issue #143."


def test_unwrap_keeps_block_starts():
    """Строка, начинающая элемент, к предыдущей не клеится: заголовок, пункт, вложенный пункт."""
    # Продолжение вложенного пункта (отступ 4) клеится к нему, а не к блоку «Числа»
    text = ("### Добавлено\n\n"
            "- **FEAT-001.** Суть.\n\n"
            "  *Числа.* Изменяются первые записи.\n"
            "  - пример 22: дебит 10.67 → 8.21,\n"
            "    давление 151.79 → 151.38\n"
            "  - пример 17: T +0.050 К\n"
            "- **FEAT-002.** Суть.")
    assert release.unwrap_paragraphs(text).splitlines() == [
        "### Добавлено", "",
        "- **FEAT-001.** Суть.", "",
        "  *Числа.* Изменяются первые записи.",
        "  - пример 22: дебит 10.67 → 8.21, давление 151.79 → 151.38",
        "  - пример 17: T +0.050 К",
        "- **FEAT-002.** Суть.",
    ]
    # Текст сразу под заголовком (без пустой строки) не вклеивается в заголовок
    assert release.unwrap_paragraphs("### Изменено\nТекст.") == "### Изменено\nТекст."


def test_unwrap_keeps_fenced_code():
    """Строки блока кода не склеиваются: перенос строки в коде значим."""
    text = "Команда:\n```\npip install a\npip install b\n```\nдалее текст"
    assert release.unwrap_paragraphs(text) == text


def test_unwrap_keeps_words_of_changelog():
    """На всём журнале склейка не теряет и не добавляет слов, а повторная ничего не меняет."""
    # Настоящие данные: разделы всех выпусков, старая и новая форма пунктов
    text = release.read_text(SOLVER / "CHANGELOG.md")
    once = release.unwrap_paragraphs(text)
    assert once.split() == text.split()
    assert release.unwrap_paragraphs(once) == once
    assert len(once.splitlines()) < len(text.splitlines())    # склейка действительно была


def test_release_notes_unwrapped_with_tail():
    """Описание выпуска – раздел своего номера со склеенными строками и NOTES_TAIL с именем архива передачи; соседние разделы не входят."""
    # «—» в заголовках выпусков – служебный маркер, его разбирает release.py
    text = ("# Журнал\n\n## Не выпущено\n\n"
            "## 1.2.3 — 2026-10-22\n\n### Добавлено\n\n"
            "- **FEAT-001.** Суть\n  одной фразой.\n\n"
            "## 1.2.2 — 2026-10-21\n\n- **FEAT-000.** Прошлый.\n")
    # Имя архива передачи – буквально: описание выпуска называет архив этого номера
    tail = release.NOTES_TAIL.format(archive="gpn-multiphase-solver-1.2.3.zip", wheels="gpn-multiphase-solver-wheels-1.2.3.zip")
    assert release.release_notes(text, "1.2.3") == (
        "### Добавлено\n\n- **FEAT-001.** Суть одной фразой.\n\n" + tail + "\n")
    assert all(s in tail for s in ("gpn-multiphase-solver-1.2.3.zip", "gpn-multiphase-solver-wheels-1.2.3.zip", "README.md"))


def test_skip_reason_allowed_in_acceptance():
    """Причина пропуска этих тестов в срезе заказчика – среди допустимых в tools/acceptance.py."""
    # Иначе приёмка среза (tools/handover.py --acceptance) отметит пропуск
    # как ошибку, и выяснится это только при передаче
    acceptance = _load("acceptance")
    assert acceptance.disallowed_skips([(1, SKIP_REASON)]) == []


def test_preflight_requires_pdflatex(monkeypatch):
    """Без pdflatex в PATH выпуск отказывает первой проверкой шага 1 – до вызовов gh и git."""
    # PDF постановки собирает передача в шаге 3, уже после коммита и метки:
    # отказ там стоил бы отката. run подменён – вызов gh или git до
    # проверки pdflatex попал бы в calls
    calls = []
    monkeypatch.setattr(release.shutil, "which", lambda name: None if name == "pdflatex" else name)
    monkeypatch.setattr(release, "run", lambda cmd, cwd=None: calls.append(cmd))
    with pytest.raises(release.ReleaseError, match="pdflatex"):
        release.preflight("1.0.7")
    assert calls == []


@pytest.mark.parametrize("argv", [[], ["--acceptance"], ["1.0.7", "1.0.8"], ["-h"],
                                  ["1.0.7", "--accept"]])
def test_main_rejects_bad_arguments(argv, monkeypatch, capsys):
    """Неверный набор аргументов – докстринг и код 2, проверки шага 1 не начинаются."""
    # Опечатка в ключе («--accept») – второй позиционный аргумент, а не
    # номер: выпуск не начинается, а не идёт молча без приёмки
    monkeypatch.setattr(release, "preflight", lambda version: pytest.fail("вызван preflight"))
    assert release.main(argv) == 2
    assert "Порядок:" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["1.0.7"], ["1.0.7", "--acceptance"], ["--acceptance", "1.0.7"]])
def test_main_passes_version_to_preflight(argv, monkeypatch, capsys):
    """Ключ --acceptance в любом месте не принимается за номер: в шаг 1 идёт только номер."""
    # preflight подменён отказом: дальше шага 1 тест не идёт, git не вызывается
    seen = []

    def fake_preflight(version):
        seen.append(version)
        raise release.ReleaseError("стоп")

    monkeypatch.setattr(release, "preflight", fake_preflight)
    assert release.main(argv) == 1
    assert seen == ["1.0.7"]
    assert "Отказ (ничего не изменено): стоп" in capsys.readouterr().out


@pytest.mark.parametrize("acceptance, tail", [(False, []), (True, ["--acceptance"])])
def test_run_handover_command_and_archive(acceptance, tail, monkeypatch, tmp_path):
    """Передача – handover.py метки тем же интерпретатором из корня, вывод не перехватывается; результат – архив."""
    # Имя архива записано буквально: его называют README и описание выпуска.
    # Без capture_output и env вывод передачи идёт в консоль выпуска сразу
    # и в той же кодировке, что и вывод самого выпуска
    monkeypatch.setattr(release, "ROOT", tmp_path)
    archive = tmp_path / "dist" / "handover-1.2.3" / "gpn-multiphase-solver-1.2.3.zip"
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b"zip")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(release.subprocess, "run", fake_run)
    assert release.run_handover("v1.2.3", "1.2.3", acceptance) == archive
    [(cmd, kwargs)] = calls
    assert cmd == [sys.executable, str(release.HANDOVER), "v1.2.3", *tail]
    assert kwargs == {"cwd": tmp_path}


@pytest.mark.parametrize("code, old_archive", [(1, True), (0, False)])
def test_run_handover_failure(code, old_archive, monkeypatch, tmp_path):
    """Отказ передачи или код 0 без архива – ReleaseError, то есть откат выпуска до push."""
    # Архив прошлой неудачной попытки того же номера отказ не отменяет
    monkeypatch.setattr(release, "ROOT", tmp_path)
    if old_archive:
        archive = release.handover_archive("1.2.3")
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b"old")
    monkeypatch.setattr(release.subprocess, "run",
                        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, code))
    with pytest.raises(release.ReleaseError, match="передача v1.2.3"):
        release.run_handover("v1.2.3", "1.2.3", False)


def test_calculation_archive_contents(tmp_path):
    """Поставка содержит файлы примеров, документации, два колеса и тот же README."""
    # Снимок примеров отбирает каталоги до сборки и сохраняет вложенные файлы.
    examples = tmp_path / "examples"
    for name in ("06_case/nested/config.json", "18_prototype_input/a", "23_source_tree_run/b"):
        path = examples / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
    snapshot = tmp_path / "examples.zip"
    release.zip_examples(examples, snapshot)
    docs = tmp_path / "docs.zip"
    with zipfile.ZipFile(docs, "w") as z:
        z.writestr("index.html", "docs")
        z.writestr("_static/a.js", "script")
    wheels = [tmp_path / "gpn.whl", tmp_path / "radial.whl"]
    for path in wheels:
        path.write_bytes(path.name.encode())
    readme = tmp_path / "README.md"
    readme.write_bytes(b"readme")
    target = tmp_path / "delivery.zip"
    release.zip_calculation_delivery(snapshot, docs, wheels, readme, target)
    with zipfile.ZipFile(target) as z:
        names = z.namelist()
        assert len(names) == len(set(names))
        assert set(names) == {"examples/06_case/nested/config.json", "docs/index.html",
                              "docs/_static/a.js", "wheels/gpn.whl", "wheels/radial.whl", "README.md"}
        assert z.read("README.md") == readme.read_bytes()
        assert z.read("docs/index.html") == b"docs"
        assert z.read("wheels/gpn.whl") == b"gpn.whl"


def test_calculation_archive_missing_input_fails(tmp_path):
    """Отсутствующий вход останавливает упаковку и не создаёт готовый архив."""
    target = tmp_path / "delivery.zip"
    with pytest.raises((release.ReleaseError, OSError)):
        release.zip_calculation_delivery(tmp_path / "missing.zip", tmp_path / "docs.zip",
                                         [], tmp_path / "README.md", target)
    assert not target.exists()


@pytest.mark.parametrize("acceptance", [False, True])
def test_build_returns_three_assets_from_clean_examples(tmp_path, monkeypatch, acceptance):
    """Список публикации содержит два архива и README, примеры сняты до изменения дерева."""
    tree = tmp_path / "tree"
    example = tree / "examples" / "06_case" / "config.json"
    example.parent.mkdir(parents=True)
    example.write_bytes(b"clean")
    (tree / "README.md").write_bytes(b"readme")
    (tree / "CHANGELOG.md").write_text("## 1.2.3 — 2026-01-01\n\nText\n", encoding="utf-8")
    def extract(tag, dest):
        dest.mkdir(parents=True)
        return tree
    monkeypatch.setattr(release, "extract", extract)

    def docs(tree, out, version):
        path = out / "docs.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("index.html", "docs")
        return path, 1

    def selfcheck(tree):
        example.write_bytes(b"changed")
        (example.parent / "generated.txt").write_bytes(b"generated")
        return "passed"

    def wheels(tree, folder, version, proto):
        folder.mkdir()
        paths = [folder / "gpn.whl", folder / "radial.whl"]
        for p in paths:
            p.write_bytes(p.name.encode())
        return paths

    seen = []
    archive = tmp_path / "gpn-multiphase-solver-1.2.3.zip"
    archive.write_bytes(b"development")
    monkeypatch.setattr(release, "build_docs", docs)
    monkeypatch.setattr(release, "selfcheck", selfcheck)
    monkeypatch.setattr(release, "build_wheels", wheels)
    monkeypatch.setattr(release, "run_handover", lambda tag, version, flag: seen.append(flag) or archive)
    out = tmp_path / "output"
    assets = release.build("v1.2.3", out, "1.2.3", "1.0.3+gpn.1", acceptance)
    assert {p.name for p in assets} == {archive.name, "gpn-multiphase-solver-wheels-1.2.3.zip", "README.md"}
    assert len(assets) == 3 and seen == [acceptance]
    with zipfile.ZipFile(out / "gpn-multiphase-solver-wheels-1.2.3.zip") as z:
        assert z.read("examples/06_case/config.json") == b"clean"
        assert "examples/06_case/generated.txt" not in z.namelist()
        assert z.read("README.md") == (out / "README.md").read_bytes()
        assert z.read("docs/index.html") == b"docs"


@pytest.mark.parametrize("failed", ["build_docs", "selfcheck", "build_wheels", "run_handover"])
def test_build_propagates_failure(tmp_path, monkeypatch, failed):
    """Ошибка любого этапа сборки не возвращает список файлов публикации."""
    tree = tmp_path / "tree"
    (tree / "examples").mkdir(parents=True)
    (tree / "examples" / "example.txt").write_text("example")
    (tree / "README.md").write_text("readme")
    (tree / "CHANGELOG.md").write_text("## 1.2.3 — 2026-01-01\n\nText\n", encoding="utf-8")

    def extract(tag, dest):
        dest.mkdir(parents=True)
        return tree

    def docs(tree, out, version):
        path = out / "docs.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("index.html", "docs")
        return path, 1

    def wheels(tree, folder, version, proto):
        folder.mkdir()
        paths = [folder / "gpn.whl", folder / "radial.whl"]
        for p in paths:
            p.write_bytes(b"wheel")
        return paths

    monkeypatch.setattr(release, "extract", extract)
    monkeypatch.setattr(release, "build_docs", docs)
    monkeypatch.setattr(release, "selfcheck", lambda tree: "passed")
    monkeypatch.setattr(release, "build_wheels", wheels)
    monkeypatch.setattr(release, "run_handover", lambda *args: tmp_path / "handover.zip")

    def fail(*args):
        raise release.ReleaseError("ошибка сборки")

    monkeypatch.setattr(release, failed, fail)
    with pytest.raises(release.ReleaseError, match="ошибка сборки"):
        release.build("v1.2.3", tmp_path / "out", "1.2.3", "1.0.3+gpn.1", False)


def test_main_passes_exact_assets_to_release(tmp_path, monkeypatch):
    """Публикация получает три пути из сборки без настоящих вызовов Git и GitHub."""
    assets = [tmp_path / "dev.zip", tmp_path / "calculation.zip", tmp_path / "README.md"]
    calls = []
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "preflight", lambda version: {
        "version": version, "current": "1.2.2", "proto_new": "1.0.3",
        "proto_old": "1.0.3", "base": "v1.2.2"})
    monkeypatch.setattr(release, "git", lambda *args: "head")
    monkeypatch.setattr(release, "apply_release_edits", lambda *args: None)
    monkeypatch.setattr(release, "apply_dev_edits", lambda *args: "1.2.4.dev0")
    monkeypatch.setattr(release, "build", lambda *args: assets)
    monkeypatch.setattr(release, "selfcheck", lambda tree: "passed")
    monkeypatch.setattr(release, "run", lambda cmd: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""))
    assert release.main(["1.2.3"]) == 0
    assert len(calls) == 1
    assert calls[0][:4] == ["gh", "release", "create", "v1.2.3"]
    assert calls[0][4:7] == assets
