r"""DEBT-068: правки плана на копии дерева — «до» единственны, тесты краснеют и зеленеют, .tex собирается.

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-068\probes\plan_check.py
Блоки «До:/После:» читаются из файла плана (vault/plans/debt-068 …md) — проверяется
дословно его текст. Копия — во временном каталоге рядом с пробой, удаляется в конце.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/, не из {SOLVER}")
ROOT = SOLVER.parent
PLAN = next((ROOT / "vault" / "plans").glob("debt-068 *.md"))
WORK = Path(__file__).resolve().parent / "plan_check_tmp"
COPY = WORK / "numerical_solver"
VAULT = WORK / "vault"

# Правка → файл копии
TARGETS = {
    "1": COPY / "tests" / "test_config.py",
    "2": COPY / "gpn_multiphase_solver" / "io" / "config.py",
    "3": COPY / "doc" / "problem_statement.tex",
    "4.1": VAULT / "P8-формат-ввода-json.md",
    "4.2": VAULT / "P8-формат-ввода-json.md",
    "4.3": VAULT / "json-config-schema.md",
}

# Запреты и метки tests/test_eq_references.py (DEBT-010)
FORBIDDEN = [r"\b[Ee]qs?\.\s*\(?\d", r"\b[Уу]р\.\s*\d", r"\b[Ee]q\.\s*`?[A-Za-z_]",
             r"\.tex:\s*\d", r"\.tex,?\s*строк"]
LABEL_REF = re.compile(r"(?<![A-Za-z])(?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+")
LABEL_DEF = re.compile(r"\\label\{((?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+)\}")


def edits_from_plan():
    """[(номер правки, до, после)] из плана: блок между «Правка N.M» и следующей правкой или шагом."""
    text = PLAN.read_text(encoding="utf-8")
    parts = re.split(r"^Правка (\d\.\d)[^\n]*\n", text, flags=re.M)
    out = []
    for num, body in zip(parts[1::2], parts[2::2]):
        body = re.split(r"^(?:### |\*\*Проверка)", body, flags=re.M)[0]
        before = re.search(r"До:\n```\n(.*?)\n```", body, re.S).group(1)
        after = re.search(r"После:\n```\n(.*?)\n```", body, re.S).group(1)
        out.append((num, before, after))
    return out


def target(num: str) -> Path:
    return TARGETS.get(num, TARGETS.get(num.split(".")[0]))


def apply(edits, step: str) -> None:
    for num, before, after in edits:
        if not num.startswith(step + "."):
            continue
        path = target(num)
        text = path.read_text(encoding="utf-8")
        n = text.count(before)
        print(f"  правка {num} → {path.name}: «до» найдено {n} раз", flush=True)
        if n != 1:
            sys.exit("    ОШИБКА: «до» должно встречаться ровно один раз")
        path.write_text(text.replace(before, after), encoding="utf-8")


def pytest(*args) -> str:
    env = dict(os.environ, PYTHONPATH=str(COPY))   # пакет копии раньше установленного
    r = subprocess.run([sys.executable, "-m", "pytest", *args, "-q", "-p", "no:cacheprovider"],
                       cwd=COPY, env=env, capture_output=True, text=True, encoding="utf-8")
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    return "\n".join(ln for ln in lines
                     if re.search(r"passed|failed|error|DID NOT|^E ", ln, re.I))[-3000:]


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(SOLVER / "gpn_multiphase_solver", COPY / "gpn_multiphase_solver",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (COPY / "tests").mkdir(exist_ok=True)
    for name in ("__init__.py", "conftest.py", "test_config.py"):
        shutil.copy2(SOLVER / "tests" / name, COPY / "tests" / name)
    shutil.copytree(SOLVER / "configs", COPY / "configs")
    # test_project_configs_have_no_removed_keys читает configs/ и tests/data/*/config.json
    shutil.copytree(SOLVER / "tests" / "data", COPY / "tests" / "data",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(SOLVER / "pyproject.toml", COPY / "pyproject.toml")
    (COPY / "doc").mkdir()
    shutil.copy2(SOLVER / "doc" / "problem_statement.tex", COPY / "doc" / "problem_statement.tex")
    VAULT.mkdir()
    for name in ("P8-формат-ввода-json.md", "json-config-schema.md"):
        shutil.copy2(ROOT / "vault" / "knowledge" / "decisions" / name, VAULT / name)

    edits = edits_from_plan()
    print(f"План: {PLAN.name}; правок: {len(edits)} ({', '.join(e[0] for e in edits)})")
    env_check = subprocess.run(
        [sys.executable, "-c", "import gpn_multiphase_solver as g; print(g.__file__)"],
        cwd=COPY, env=dict(os.environ, PYTHONPATH=str(COPY)), capture_output=True, text=True)
    print(f"Пакет в pytest копии: {env_check.stdout.strip()}")

    print("\nШаг 1 — тесты:")
    apply(edits, "1")
    print(pytest("tests/test_config.py::TestValidationRock"))

    print("\nШаг 2 — проверка в _validate:")
    apply(edits, "2")
    print(pytest("tests/test_config.py::TestValidationRock"))
    print(pytest("tests/test_config.py"))

    # Правило ссылок формула → код для новых строк config.py и тестов
    tex = (COPY / "doc" / "problem_statement.tex").read_text(encoding="utf-8")
    labels = set(LABEL_DEF.findall(tex))
    new_text = "\n".join(a for n, _, a in edits if n[0] in "12")
    bad = [p for p in FORBIDDEN if re.search(p, new_text)]
    refs = sorted(set(LABEL_REF.findall(new_text)))
    print(f"\nСсылки в новом коде: метки {refs}, не объявлены: "
          f"{[r for r in refs if r not in labels]}; запрещённые формы: {bad}")

    print("\nШаг 3 — постановка:")
    apply(edits, "3")
    doc = COPY / "doc"
    for _ in range(2):
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "problem_statement.tex"],
                       cwd=doc, capture_output=True)
    log = (doc / "problem_statement.log").read_text(encoding="utf-8", errors="replace")
    undefined = [ln for ln in log.splitlines() if "undefined" in ln.lower()]
    pages = re.search(r"Output written on .*?\((\d+) pages", log)
    print(f"  pdflatex: {pages.group(1) if pages else '?'} стр., строк с «undefined»: "
          f"{len(undefined)}{': ' + undefined[0] if undefined else ''}")

    print("\nШаг 4 — vault:")
    apply(edits, "4")
    print("\nГотово.")


if __name__ == "__main__":
    try:
        main()
    finally:
        if WORK.exists():
            shutil.rmtree(WORK)
