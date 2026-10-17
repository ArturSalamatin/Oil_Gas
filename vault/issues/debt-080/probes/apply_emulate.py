"""DEBT-080, аудит: замены note_apply.py — на копиях заметок; переводы строк, объём diff, сторож DEBT-074.

Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-080\\probes\\apply_emulate.py
Пишет копии до/после в vault/issues/debt-080/probes/emul/ (удаляются в конце) и печатает
git diff --no-index --numstat, нарушения шаблонов FORBIDDEN и метки, не объявленные в постановке.
"""
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
HERE = ROOT / "vault/issues/debt-080/probes"
EMUL = HERE / "emul"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


na = load("note_apply", HERE / "note_apply.py")
eq = load("test_eq_references", ROOT / "numerical_solver/tests/test_eq_references.py")

texts, errors = na.apply_all()
if errors:
    sys.exit("замены не применяются: " + "; ".join(errors))

EMUL.mkdir(exist_ok=True)
labels = set(eq.LABEL_DEF.findall((ROOT / "numerical_solver/doc/problem_statement.tex").read_text(encoding="utf-8")))
bad = 0
for i, (path, text) in enumerate(texts.items()):
    before, after = EMUL / f"{i}_before.md", EMUL / f"{i}_after.md"
    shutil.copyfile(path, before)                     # байты как в рабочем каталоге
    crlf = na.read(path)[1]
    with open(after, "w", encoding="utf-8", newline="\r\n" if crlf else "\n") as f:
        f.write(text)
    num = subprocess.run(["git", "diff", "--no-index", "--numstat", str(before), str(after)],
                         capture_output=True, text=True).stdout.split()[:2]
    raw = after.read_bytes()
    n_crlf, n_lf = raw.count(b"\r\n"), raw.count(b"\n")
    print(f"{path.name}: CRLF до={crlf}; после: CRLF {n_crlf}, LF без CR {n_lf - n_crlf}; "
          f"diff +{num[0]} -{num[1]}")
    # Сторож DEBT-074 — те же шаблоны, что test_vault_notes_no_numeric_equation_references
    for lineno, line in enumerate(text.splitlines(), 1):
        for what, rx in eq.FORBIDDEN.items():
            if rx.search(line):
                bad += 1
                print(f"  {path.name}:{lineno}: {what}: {line[:100]}")
        for lab in eq.LABEL_REF.findall(line):
            if lab not in labels:
                bad += 1
                print(f"  {path.name}:{lineno}: метка {lab} не объявлена в постановке")
shutil.rmtree(EMUL)
print(f"нарушений сторожа: {bad}")
