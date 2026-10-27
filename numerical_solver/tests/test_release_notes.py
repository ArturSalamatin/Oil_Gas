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
    tail = release.NOTES_TAIL.format(archive="gpn-multiphase-solver-1.2.3.zip")
    assert release.release_notes(text, "1.2.3") == (
        "### Добавлено\n\n- **FEAT-001.** Суть одной фразой.\n\n" + tail + "\n")


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
