"""DEBT-039: индексировать в основном каталоге только свои фрагменты общих файлов vault.

В index.md и реестре лежат незакоммиченные правки параллельных сессий; git add
целиком забрал бы и их. Скрипт берёт `git diff -U0` файла, оставляет фрагменты,
в добавленных строках которых есть метка, и кладёт их в индекс
(`git apply --cached --unidiff-zero`). Рабочие файлы не меняются.

Запуск: python stage_own_hunks.py <корень репозитория> <метка> <файл> [<файл> ...]
"""
import subprocess
import sys

root, mark, files = sys.argv[1], sys.argv[2], sys.argv[3:]
for f in files:
    diff = subprocess.run(["git", "-C", root, "-c", "core.quotepath=off", "diff", "-U0", "--", f],
                          capture_output=True, check=True).stdout.decode("utf-8")
    lines = diff.splitlines(keepends=True)
    head_end = next(i for i, ln in enumerate(lines) if ln.startswith("@@"))
    header, body = lines[:head_end], lines[head_end:]
    hunks, cur = [], []
    for ln in body:
        if ln.startswith("@@") and cur:
            hunks.append(cur)
            cur = []
        cur.append(ln)
    if cur:
        hunks.append(cur)
    keep = [h for h in hunks if any(ln.startswith("+") and mark in ln for ln in h[1:])]
    print(f"{f}: фрагментов {len(hunks)}, своих {len(keep)}")
    if not keep:
        continue
    patch = "".join(header) + "".join("".join(h) for h in keep)
    subprocess.run(["git", "-C", root, "apply", "--cached", "--unidiff-zero", "-"],
                   input=patch.encode("utf-8"), check=True)
