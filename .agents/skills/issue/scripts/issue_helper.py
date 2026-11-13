#!/usr/bin/env python3
"""Вспомогательный скрипт для автоматизации навыка issue.

Выполняет детерминированные операции:
- определение следующего доступного номера ID;
- проверка дубликатов задач на GitHub через gh;
- проверка наличия веток git;
- точечное обновление реестров задач в vault.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

REPO_NAME = "ArturSalamatin/Oil_Gas"

REGISTRY_MAP = {
    "BUG": "vault/roadmap/известные баги и технический долг.md",
    "DEBT": "vault/roadmap/известные баги и технический долг.md",
    "FEAT": "vault/roadmap/планируемые фичи.md",
    "VAL": "vault/roadmap/валидационные кейсы.md",
}


def find_repo_root() -> Path:
    """Определяет корень репозитория git."""
    current = Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return current


def get_registry_path(repo_root: Path, prefix: str) -> Path:
    rel_path = REGISTRY_MAP.get(prefix.upper())
    if not rel_path:
        raise ValueError(f"Неизвестный тип задачи: {prefix}. Допустимы: BUG, DEBT, FEAT, VAL")
    return repo_root / rel_path


def cmd_next_id(args: argparse.Namespace) -> None:
    repo_root = find_repo_root()
    prefix = args.type.upper()
    registry_file = get_registry_path(repo_root, prefix)

    if not registry_file.exists():
        print(f"Ошибка: файл реестра не найден: {registry_file}", file=sys.stderr)
        sys.exit(1)

    content = registry_file.read_text(encoding="utf-8")
    pattern = re.compile(rf"^###\s+{re.escape(prefix)}-(\d+)", re.MULTILINE)
    numbers = [int(match.group(1)) for match in pattern.finditer(content)]

    next_num = max(numbers, default=0) + 1
    next_id = f"{prefix}-{next_num:03d}"
    print(next_id)


def cmd_check_duplicate(args: argparse.Namespace) -> None:
    task_id = args.id.upper()
    cmd = [
        "gh",
        "issue",
        "list",
        "--repo",
        REPO_NAME,
        "--search",
        task_id,
        "--state",
        "all",
        "--json",
        "number,title,url,state",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
        )
    except FileNotFoundError:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "Утилита gh не найдена в PATH.",
                    "found": False,
                    "issues": [],
                },
                ensure_ascii=False,
            )
        )
        return

    if proc.returncode != 0:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": proc.stderr.strip(),
                    "found": False,
                    "issues": [],
                },
                ensure_ascii=False,
            )
        )
        return

    try:
        issues: list[dict[str, Any]] = json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError:
        issues = []

    matching = [
        iss for iss in issues if task_id in iss.get("title", "") or task_id in iss.get("url", "")
    ]

    print(
        json.dumps(
            {
                "status": "ok",
                "found": len(matching) > 0,
                "issues": matching,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_check_branch(args: argparse.Namespace) -> None:
    branch = args.name.strip()
    cmd_local = ["git", "branch", "--list", branch]
    proc_local = subprocess.run(cmd_local, capture_output=True, text=True, check=False)
    local_exists = bool(proc_local.stdout.strip())

    cmd_remote = ["git", "branch", "-r", "--list", f"origin/{branch}"]
    proc_remote = subprocess.run(cmd_remote, capture_output=True, text=True, check=False)
    remote_exists = bool(proc_remote.stdout.strip())

    exists = local_exists or remote_exists
    print(
        json.dumps(
            {
                "branch": branch,
                "exists": exists,
                "local": local_exists,
                "remote": remote_exists,
            },
            ensure_ascii=False,
        )
    )


def cmd_update_vault(args: argparse.Namespace) -> None:
    repo_root = find_repo_root()
    task_id = args.id.upper()
    prefix = task_id.split("-")[0]
    registry_file = get_registry_path(repo_root, prefix)

    if not registry_file.exists():
        print(f"Ошибка: файл реестра не найден: {registry_file}", file=sys.stderr)
        sys.exit(1)

    content = registry_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    section_start = -1
    section_end = len(lines)

    header_re = re.compile(rf"^###\s+{re.escape(task_id)}(?::|\s|$)", re.IGNORECASE)

    for i, line in enumerate(lines):
        if header_re.match(line):
            section_start = i
            break

    if section_start == -1:
        print(f"Ошибка: секция для {task_id} не найдена в {registry_file.name}", file=sys.stderr)
        sys.exit(1)

    for i in range(section_start + 1, len(lines)):
        if lines[i].startswith("### "):
            section_end = i
            break

    section_lines = lines[section_start:section_end]

    num_match = re.search(r"/issues/(\d+)", args.issue_url)
    issue_num = num_match.group(1) if num_match else "?"
    github_entry = f"- **GitHub:** [#{issue_num}]({args.issue_url})"
    branch_entry = f"- **Ветка:** `{args.branch}`"

    has_github = any(line.strip().startswith("- **GitHub:**") for line in section_lines)
    has_branch = any(line.strip().startswith("- **Ветка:**") for line in section_lines)

    insert_idx = len(section_lines)
    for idx, line in enumerate(section_lines):
        if line.strip().startswith(("- **Статус:**", "- **План:**")):
            insert_idx = idx
            break

    entries_to_add: list[str] = []
    if not has_github:
        entries_to_add.append(github_entry)
    if not has_branch:
        entries_to_add.append(branch_entry)

    if entries_to_add:
        for entry in reversed(entries_to_add):
            section_lines.insert(insert_idx, entry)

        new_lines = lines[:section_start] + section_lines + lines[section_end:]
        registry_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print(f"Обновлен реестр: {registry_file.name} для {task_id}")
    else:
        print(f"Записи GitHub и Ветка уже присутствуют в {task_id}")

    detail_match = None
    for line in section_lines:
        m = re.search(r"-\s+\*\*(?:Подробности|План):\*\*\s+\[\[(.*?)\]\]", line)
        if m:
            detail_match = m.group(1).strip()
            break

    if detail_match:
        for knowledge_dir in ["knowledge/debugging", "knowledge/decisions", "knowledge/science", "knowledge/validation"]:
            candidate = repo_root / "vault" / knowledge_dir / f"{detail_match}.md"
            if candidate.exists():
                note_text = candidate.read_text(encoding="utf-8")
                if "github.com" not in note_text:
                    addition = f"\n**GitHub issue:** [#{issue_num}]({args.issue_url})\n"
                    candidate.write_text(note_text + addition, encoding="utf-8")
                    print(f"Обновлена заметка знаний: {candidate.name}")
                break


def main() -> None:
    parser = argparse.ArgumentParser(description="Вспомогательный скрипт для навыка issue")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_next = subparsers.add_parser("next-id", help="Получить следующий свободный ID")
    p_next.add_argument("type", choices=["BUG", "DEBT", "FEAT", "VAL"], help="Тип задачи")
    p_next.set_defaults(func=cmd_next_id)

    p_dup = subparsers.add_parser("check-duplicate", help="Проверить дубликаты задачи на GitHub")
    p_dup.add_argument("id", help="Идентификатор задачи (например, BUG-001)")
    p_dup.set_defaults(func=cmd_check_duplicate)

    p_branch = subparsers.add_parser("check-branch", help="Проверить существование ветки git")
    p_branch.add_argument("name", help="Имя ветки")
    p_branch.set_defaults(func=cmd_check_branch)

    p_update = subparsers.add_parser("update-vault", help="Обновить запись в vault")
    p_update.add_argument("id", help="Идентификатор задачи")
    p_update.add_argument("--issue-url", required=True, help="URL созданного GitHub issue")
    p_update.add_argument("--branch", required=True, help="Имя ветки git")
    p_update.set_defaults(func=cmd_update_vault)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
