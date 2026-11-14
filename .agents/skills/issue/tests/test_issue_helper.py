"""Проверки операций навыка issue на изолированных данных."""

import argparse
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(os.environ.get("ISSUE_HELPER_PATH", Path(__file__).resolve().parents[1] / "scripts" / "issue_helper.py"))
spec = importlib.util.spec_from_file_location("issue_helper", SCRIPT)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    # Реестры создаются отдельно, чтобы проверки не изменили рабочий vault.
    root = tmp_path / "проект"
    for path in set(helper.REGISTRY_MAP.values()):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    monkeypatch.setattr(helper, "find_repo_root", lambda: root)
    return root


def call_update(url="https://github.com/ArturSalamatin/Oil_Gas/issues/42", branch="fix/bug-001/example"):
    helper.cmd_update_vault(argparse.Namespace(id="BUG-001", issue_url=url, branch=branch))


def test_next_id_counts_only_type_and_keeps_gaps(repo, capsys):
    # BUG и DEBT имеют общий файл, но независимые последовательности номеров.
    path = repo / helper.REGISTRY_MAP["BUG"]
    path.write_text("### BUG-001: a\n### DEBT-090: b\n### BUG-004: c\n", encoding="utf-8")
    helper.cmd_next_id(argparse.Namespace(type="BUG"))
    assert capsys.readouterr().out.strip() == "BUG-005"


def test_next_id_for_empty_registry(repo, capsys):
    # Пустой реестр начинает нумерацию отдельно для выбранного типа.
    helper.cmd_next_id(argparse.Namespace(type="VAL"))
    assert capsys.readouterr().out.strip() == "VAL-001"


def test_duplicate_requires_exact_id(monkeypatch, capsys):
    # Идентификатор с дополнительной цифрой не является той же задачей.
    data = [{"number": 10, "title": "BUG-0010: другая", "url": "https://example/issues/10", "state": "OPEN"},
            {"number": 1, "title": "BUG-001: нужная", "url": "https://example/issues/1", "state": "OPEN"}]
    monkeypatch.setattr(helper.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, json.dumps(data), ""))
    helper.cmd_check_duplicate(argparse.Namespace(id="BUG-001"))
    assert [item["number"] for item in json.loads(capsys.readouterr().out)["issues"]] == [1]


def test_update_replaces_placeholders_and_preserves_neighbors(repo):
    # Заполнители заменяются, соседняя задача и окончания строк сохраняются.
    path = repo / helper.REGISTRY_MAP["BUG"]
    original = "### BUG-001: a\r\n- **GitHub:** – (после /issue)\r\n- **Ветка:** –\r\n- **Статус:** открыта\r\n\r\n### BUG-002: b\r\n- **GitHub:** [#3](https://github.com/x/y/issues/3)\r\n"
    path.write_bytes(original.encode("utf-8"))
    call_update()
    content = path.read_bytes().decode("utf-8")
    assert "- **GitHub:** [#42](https://github.com/ArturSalamatin/Oil_Gas/issues/42)\r\n" in content
    assert "- **Ветка:** `fix/bug-001/example`\r\n" in content
    assert content.endswith("### BUG-002: b\r\n- **GitHub:** [#3](https://github.com/x/y/issues/3)\r\n")
    call_update()
    assert path.read_bytes().decode("utf-8") == content


def test_update_refuses_existing_conflict_without_changes(repo):
    # Запись существующего issue не заменяется URL другой задачи.
    path = repo / helper.REGISTRY_MAP["BUG"]
    original = "### BUG-001: a\n- **GitHub:** [#7](https://github.com/ArturSalamatin/Oil_Gas/issues/7)\n"
    path.write_text(original, encoding="utf-8")
    with pytest.raises((ValueError, SystemExit)):
        call_update()
    assert path.read_text(encoding="utf-8") == original


def test_update_rejects_wrong_repository(repo):
    # Нельзя записать в реестр ссылку на issue другого репозитория.
    path = repo / helper.REGISTRY_MAP["BUG"]
    original = "### BUG-001: a\n- **Статус:** открыта\n"
    path.write_text(original, encoding="utf-8")
    with pytest.raises((ValueError, SystemExit)):
        call_update(url="https://github.com/other/repo/issues/42")
    assert path.read_text(encoding="utf-8") == original


def test_existing_unrelated_github_link_does_not_block_note_update(repo):
    # Ссылка на другой репозиторий не заменяет ссылку на issue текущей задачи.
    path = repo / helper.REGISTRY_MAP["BUG"]
    note = repo / "vault/knowledge/debugging/заметка.md"
    note.parent.mkdir(parents=True)
    note.write_text("[источник](https://github.com/other/repo)\n", encoding="utf-8")
    path.write_text("### BUG-001: a\n- **Подробности:** [[заметка]]\n", encoding="utf-8")
    call_update()
    assert "https://github.com/ArturSalamatin/Oil_Gas/issues/42" in note.read_text(encoding="utf-8")
    call_update()
    assert note.read_text(encoding="utf-8").count("/issues/42") == 1


def test_update_handles_draft_wikilink_with_alias(repo):
    # Подробности могут указывать на черновик с подписью ссылки Obsidian.
    path = repo / helper.REGISTRY_MAP["BUG"]
    note = repo / "vault/issues/bug-001/00-draft.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Контекст\n", encoding="utf-8")
    path.write_text("### BUG-001: a\n- **Подробности:** [[vault/issues/bug-001/00-draft.md|черновик]]\n", encoding="utf-8")
    call_update()
    assert "https://github.com/ArturSalamatin/Oil_Gas/issues/42" in note.read_text(encoding="utf-8")


def test_update_inserts_missing_fields_in_last_section(repo):
    # Последняя запись без завершающего перевода строки остаётся читаемой.
    path = repo / helper.REGISTRY_MAP["BUG"]
    path.write_text("### BUG-001: a", encoding="utf-8")
    call_update()
    content = path.read_text(encoding="utf-8")
    assert content.startswith("### BUG-001: a\n- **GitHub:**")
    assert "\n- **Ветка:** `fix/bug-001/example`\n" in content


def test_check_branch_with_actual_git(tmp_path, monkeypatch, capsys):
    # Проверяем реальную локальную ветку Git в каталоге с кириллицей.
    repo = tmp_path / "репозиторий"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "--allow-empty", "-qm", "initial"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "branch", "fix/bug-001/example"], check=True, capture_output=True)
    monkeypatch.chdir(repo)
    helper.cmd_check_branch(argparse.Namespace(name="fix/bug-001/example"))
    assert json.loads(capsys.readouterr().out)["local"] is True
    helper.cmd_check_branch(argparse.Namespace(name="fix/bug-002/missing"))
    assert json.loads(capsys.readouterr().out)["exists"] is False


def test_find_root_in_git_worktree(tmp_path, monkeypatch):
    # В worktree служебный .git является файлом, а не каталогом.
    repo = tmp_path / "основной"
    worktree = tmp_path / "рабочее-дерево"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "--allow-empty", "-qm", "initial"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-qb", "test-branch", str(worktree)], check=True, capture_output=True)
    monkeypatch.chdir(worktree)
    assert helper.find_repo_root() == worktree.resolve()


def test_registry_commit_leaves_other_task_draft_untracked(tmp_path):
    # Коммит общего реестра включает обе записи и не добавляет черновик другой задачи.
    repo = tmp_path / "общий-реестр"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    registry = repo / "реестр.md"
    draft = repo / "vault/issues/bug-002/00-draft.md"
    draft.parent.mkdir(parents=True)
    draft.write_text("контекст другой задачи\n", encoding="utf-8")
    registry.write_text("### BUG-001: первая\n### BUG-002: вторая\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "--", "реестр.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "-qm", "registry"], check=True, capture_output=True)
    tree = subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", "HEAD"], check=True, capture_output=True, text=True, encoding="utf-8")
    assert "реестр.md" in tree.stdout
    assert "00-draft.md" not in tree.stdout
    assert draft.read_text(encoding="utf-8") == "контекст другой задачи\n"
