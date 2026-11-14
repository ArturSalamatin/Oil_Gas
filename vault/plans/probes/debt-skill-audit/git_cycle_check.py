"""Проверка порядка Git на отдельном локальном репозитории."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent / "git-cycle"
REPO = ROOT / "repo"
REMOTE = ROOT / "remote.git"
WORK = ROOT / "worktree"


def git(*args, cwd=None):
    return subprocess.run(["git", *map(str, args)], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def main():
    # Новый изолированный каталог исключает изменение рабочего репозитория проекта.
    ROOT.mkdir(exist_ok=False)
    git("init", "--bare", "-q", REMOTE)
    git("init", "-q", "-b", "base", REPO)
    git("config", "user.name", "Test", cwd=REPO)
    git("config", "user.email", "test@example.org", cwd=REPO)
    git("remote", "add", "origin", REMOTE, cwd=REPO)
    (REPO / "code.py").write_text("value = 1\n", encoding="utf-8")
    git("add", "--", "code.py", cwd=REPO)
    git("commit", "-qm", "base", cwd=REPO)
    git("push", "-q", "origin", "base", cwd=REPO)

    # Общий реестр попадает в базу целиком, чужой черновик остаётся локальным.
    registry = REPO / "vault/roadmap/реестр.md"
    other_draft = REPO / "vault/issues/debt-002/00-draft.md"
    registry.parent.mkdir(parents=True)
    other_draft.parent.mkdir(parents=True)
    registry.write_text("### DEBT-001: первая\n### DEBT-002: вторая\n", encoding="utf-8")
    other_draft.write_text("контекст второй задачи\n", encoding="utf-8")
    git("add", "--", "vault/roadmap/реестр.md", cwd=REPO)
    git("commit", "-qm", "registry", "--", "vault/roadmap/реестр.md", cwd=REPO)
    assert other_draft.is_file()
    assert "00-draft.md" not in git("ls-tree", "-r", "--name-only", "HEAD", cwd=REPO)

    # Ветка создаётся от актуальной базы и не изменяет чужой черновик.
    git("worktree", "add", "-qb", "debt/debt-001/test", WORK, "base", cwd=REPO)
    (WORK / "code.py").write_text("value = 2\n", encoding="utf-8")
    git("add", "--", "code.py", cwd=WORK)
    git("commit", "-qm", "change", "--", "code.py", cwd=WORK)
    git("push", "-q", "-u", "origin", "debt/debt-001/test", cwd=REPO)
    git("merge", "--no-ff", "--no-edit", "debt/debt-001/test", cwd=REPO)
    assert (REPO / "code.py").read_text(encoding="utf-8") == "value = 2\n"
    assert len(git("rev-list", "--parents", "-n", "1", "HEAD", cwd=REPO).split()) == 3
    git("worktree", "remove", WORK, cwd=REPO)
    git("push", "-q", "origin", "base", cwd=REPO)
    assert git("branch", "--list", "debt/debt-001/test", cwd=REPO)
    assert other_draft.read_text(encoding="utf-8") == "контекст второй задачи\n"
    print("PASS: local base, worktree, branch push, merge, base push and draft preservation")


if __name__ == "__main__":
    main()
