"""Аудит плана FEAT-034: быстрый уровень всего набора тестов на чистой копии HEAD с кодом плана.

plan_apply.py гоняет только новые тесты, сторож меток и тест зависимостей; здесь —
все тесты быстрого уровня, в том числе сторожа, обходящие все модули пакета
(test_packaging, test_public_api). Копия — git archive HEAD numerical_solver
(только файлы из git: черновика руководителя нет, как в worktree), в неё —
plan_code/xlsx_reader.py и plan_code/test_xlsx_reader.py. Python — venv основного
каталога, запуск из каталога копии: pytest берёт пакет и прототип копии.

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault/issues/feat-034/probes/audit_quick_level.py
Вывод: audit_quick_level.out.txt. Каталог audit_tree/ в конце удаляется.
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TREE = HERE / "audit_tree"
CODE = HERE / "plan_code"


def main():
    if TREE.exists():
        shutil.rmtree(TREE)
    TREE.mkdir()
    tar = TREE / "head.tar"
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "archive", "--format=tar", "-o", str(tar), "HEAD", "numerical_solver"],
                   cwd=ROOT, check=True)
    subprocess.run(["tar", "-xf", str(tar), "-C", str(TREE)], check=True)
    tar.unlink()
    solver = TREE / "numerical_solver"
    shutil.copy2(CODE / "xlsx_reader.py", solver / "gpn_multiphase_solver" / "io" / "xlsx_reader.py")
    shutil.copy2(CODE / "test_xlsx_reader.py", solver / "tests" / "test_xlsx_reader.py")
    out = [f"HEAD {head}"]
    for args in (["--collect-only", "-q"], ["-m", "not slow", "-q", "-rs"]):
        r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-p", "no:cacheprovider",
                            *args], cwd=solver, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        tail = [ln for ln in r.stdout.strip().splitlines() if not ln.startswith(".")][-6:]
        out.append(" ".join(args) + ":\n  " + "\n  ".join(tail))
    shutil.rmtree(TREE)
    text = "\n".join(out)
    (HERE / "audit_quick_level.out.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
