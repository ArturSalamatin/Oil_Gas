"""Блоки шага 1 плана DEBT-074 для test_eq_references.py — сборка копии и прогон.

Берёт numerical_solver/tests/test_eq_references.py корня запуска, применяет блоки
«До → После» (тот же текст, что в шаге 1 плана), пишет копию в probes/preview/
(ROOT копии — numerical_solver/ корня запуска, SELF — исходный файл, чтобы его
запрещённые формы не попали в обход), прогоняет pytest и удаляет копию.

Ожидание на дереве без замен шага 2: test_vault_notes_no_numeric_equation_references
падает с 27 нарушениями в 9 заметках, остальные 12 тестов проходят.
С ключом --after VAULT копии указывает на копию vault/knowledge с заменами
plan_apply.py (состояние после шага 2): 13 passed.

Запуск из корня репозитория:
    numerical_solver/.venv/Scripts/python -I vault/issues/debt-074/probes/guard_preview.py [--after]
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
SRC = ROOT / "numerical_solver/tests/test_eq_references.py"
OUT = Path(__file__).resolve().parent / "preview"

BLOCKS = [
    # ── Блок 1: докстринг модуля ──
    ('''Обход: .py ядра, тестов и примеров и README примеров. Этот файл исключён —
в нём записаны сами запрещённые формы.
"""''',
     '''Обход: .py ядра, тестов и примеров и README примеров. Этот файл исключён —
в нём записаны сами запрещённые формы. Заметки vault/knowledge/ без
literature/ проверяются теми же шаблонами отдельными тестами (DEBT-074).
"""'''),
    # ── Блок 2: обход заметок — после _lines() ──
    ('''            yield rel, n, line


def test_no_numeric_equation_or_line_references():''',
     '''            yield rel, n, line


# Заметки vault (DEBT-074) ссылаются на постановку, как код, — метками.
# literature/ не проверяется: номера уравнений обозреваемых статей — предмет
# этих заметок. vault/plans/, vault/issues/, реестры vault/roadmap/ — снимки
# на дату, не проверяются. В поставке заказчику vault/ нет (FEAT-031) —
# проверки заметок пропускаются, а не падают.
VAULT = ROOT.parent / "vault" / "knowledge"


def _vault_lines():
    """(путь от vault/knowledge/, номер строки, текст) по заметкам без literature/."""
    if not VAULT.is_dir():
        pytest.skip("нет vault/knowledge/ — копия без vault (поставка, FEAT-031)")
    for f in sorted(VAULT.rglob("*.md")):
        rel = f.relative_to(VAULT)
        if rel.parts[0] == "literature":
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            yield rel, n, line


def test_no_numeric_equation_or_line_references():'''),
    # ── Блок 3: три теста — в конец файла ──
    ('''    assert not missing, ("Метки нет в doc/problem_statement.tex — переименована "
                         "или удалена; поправьте ссылку:\\n" + "\\n".join(missing))
''',
     '''    assert not missing, ("Метки нет в doc/problem_statement.tex — переименована "
                         "или удалена; поправьте ссылку:\\n" + "\\n".join(missing))


def test_vault_notes_no_numeric_equation_references():
    """Заметки vault/knowledge/ (без literature/) ссылаются на постановку не номером.

    До DEBT-074 (0d5c491) — 27 нарушений в 9 заметках: номера ранних редакций
    постановки, ни один не указывал на имеющееся в виду уравнение. После — ни
    одного. Номер чужого документа — словами: «формула (23) у Peszyńska 2006».
    Не ловятся (решение пользователя, DEBT-074), правлены вручную: «уравнение N»
    и «Ур. (N)» — задели бы местную нумерацию («уравнения (1)», «Ур. (3)» в
    diagnostics/closed_form.py, «уравнение (1)» в заметке о пороге Кори);
    «формула (N)» — так пишется номер чужого документа; «стр. N» — страницы
    статей; «§N» — разделы планов и заметок. Параграф постановки пишется
    меткой ssec:, её проверяет test_vault_notes_label_references_exist.
    """
    lines = list(_vault_lines())
    # Обход не пуст: заметок вне literature/ на 0d5c491 — 93.
    assert len({rel for rel, _, _ in lines}) > 50
    bad = [f"{rel}:{n}: {what}: {line.strip()}"
           for rel, n, line in lines
           for what, rx in FORBIDDEN.items() if rx.search(line)]
    assert not bad, ("Ссылка в заметке не меткой (DEBT-074; постановка — "
                     "`eq:<метка>`, параграф — `ssec:<метка>`; чужой документ — "
                     "«формула (N) у Автор Год»):\\n" + "\\n".join(bad))


def test_vault_notes_label_references_exist():
    """Каждая метка в заметках vault/knowledge/ (без literature/) объявлена в постановке.

    Ловит переименование или удаление метки в problem_statement.tex: заметка
    ссылается на уравнение, которого больше нет. На 0d5c491 — ни одной
    отсутствующей. Метку другого .tex (two_phase_energy.tex и др.) шаблон
    не отличит — такая ссылка упадёт; сейчас их нет.
    """
    labels = set(LABEL_DEF.findall(TEX.read_text(encoding="utf-8")))
    missing = [f"{rel}:{n}: {m.group()}"
               for rel, n, line in _vault_lines()
               for m in LABEL_REF.finditer(line) if m.group() not in labels]
    assert not missing, ("Метки нет в doc/problem_statement.tex — переименована "
                         "или удалена; поправьте заметку:\\n" + "\\n".join(missing))


def test_vault_checks_skip_without_vault(monkeypatch, tmp_path):
    """Без vault/knowledge/ (поставка заказчику, FEAT-031) проверки заметок пропускаются."""
    # VAULT читается из глобалов модуля при каждом вызове _vault_lines.
    monkeypatch.setitem(globals(), "VAULT", tmp_path / "нет")
    with pytest.raises(pytest.skip.Exception):
        list(_vault_lines())
'''),
]

ROOT_LINE = 'ROOT = Path(__file__).resolve().parents[1]          # numerical_solver/'
SELF_LINE = 'SELF = Path(__file__).resolve()'


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    with open(SRC, encoding="utf-8", newline="") as f:
        text = f.read()
    crlf = "\r\n" in text
    text = text.replace("\r\n", "\n")
    for i, (old, new) in enumerate(BLOCKS, 1):
        print(f"Блок {i}: «До» встречается {text.count(old)} раз")
        text = text.replace(old, new)
    long = [n for n, line in enumerate(text.splitlines(), 1) if len(line) > 100]
    print(f"CRLF в исходном: {crlf}; строк длиннее 100: {long or 'нет'}")
    # Копия вне tests/: корень — numerical_solver/ корня запуска, исходный файл исключён.
    text = text.replace(ROOT_LINE, f'ROOT = Path(r"{ROOT / "numerical_solver"}")')
    text = text.replace(SELF_LINE, 'SELF = (ROOT / "tests" / "test_eq_references.py").resolve()')
    OUT.mkdir(exist_ok=True)
    if "--after" in sys.argv:
        # Состояние после шага 2: копия vault/knowledge с заменами plan_apply.py.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from plan_apply import apply_in_memory  # noqa: E402
        texts, _, count_errors = apply_in_memory()
        assert not count_errors, "«До» найден не ровно один раз — см. plan_apply.py"
        shutil.copytree(ROOT / "vault/knowledge", OUT / "vault/knowledge")
        for f, body in texts.items():
            with open(OUT / f, "w", encoding="utf-8", newline="") as dst:
                dst.write(body)
        text = text.replace('VAULT = ROOT.parent / "vault" / "knowledge"',
                            f'VAULT = Path(r"{OUT / "vault/knowledge"}")')
        print(f"--after: VAULT — копия с заменами ({len(texts)} заметок изменено)")
    (OUT / "test_eq_references.py").write_text(text, encoding="utf-8")
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", str(OUT / "test_eq_references.py"),
                            "-q", "-p", "no:cacheprovider", "--rootdir", str(OUT), "-rA",
                            "--tb=line"],
                           cwd=OUT, capture_output=True, text=True, encoding="utf-8",
                           # Вывод pytest — в UTF-8, иначе на Windows кодовая страница консоли.
                           env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
        out = r.stdout.splitlines()
        print("\n".join(line for line in out if line.startswith(("PASSED", "FAILED", "SKIPPED", "ERROR"))
                        or "passed" in line or "failed" in line))
    finally:
        shutil.rmtree(OUT)


if __name__ == "__main__":
    main()
