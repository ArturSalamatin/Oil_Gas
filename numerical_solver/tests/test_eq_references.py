"""Ссылки «формула → код» — метками problem_statement.tex, не номерами (DEBT-010).

Номер уравнения и номер строки .tex сдвигаются молча при любой вставке выше
по документу: к DEBT-010 все 27 числовых ссылок numerical_solver/ и все 3
ссылки на строки указывали не туда (вставка eq:c_ot в BUG-019 сдвинула
нумерацию ещё на единицу). Метка \\label{} при правках не сдвигается; её
удаление или переименование ловит второй тест.

Обход: .py ядра, тестов и примеров и README примеров. Этот файл исключён —
в нём записаны сами запрещённые формы. Заметки vault/knowledge/ без
literature/ проверяются теми же шаблонами отдельными тестами (DEBT-074).
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]          # numerical_solver/
TEX = ROOT / "doc" / "problem_statement.tex"
SELF = Path(__file__).resolve()

# Описание формы «метка (N)» — ключ в FORBIDDEN, по нему же берёт шаблон
# test_label_number_form.
LABEL_NUMBER = "номер после метки «eq:имя (N)»"

# Запрещённые формы ссылки на постановку. Уравнение чужой статьи называется
# словами («формула (5) у Coats 1999»), а не «eq. 5» — иначе его не отличить
# от номера постановки.
FORBIDDEN = {
    "номер уравнения «eq. N»": re.compile(r"\b[Ee]qs?\.\s*\(?\d"),
    "номер уравнения «ур. N»": re.compile(r"\b[Уу]р\.\s*\d"),
    "метка без двоеточия «eq. имя»": re.compile(r"\b[Ee]q\.\s*`?[A-Za-z_]"),
    "номер строки «.tex:N»": re.compile(r"\.tex:\s*\d"),
    "номер строки «.tex, строки N»": re.compile(r"\.tex,?\s*строк"),
    # Номер рядом с меткой (DEBT-062): метка проверяема, а число уезжает —
    # в «eq:bc_props_ext (74)» номер устарел, на 6d27358 эта метка — (80).
    # Префиксы — как в LABEL_REF; между меткой и номером — закрывающие ` ) }
    # и пробелы.
    # Строгая форма: номер целиком в скобках, иначе задело бы «eq:x (3 ячейки)».
    LABEL_NUMBER: re.compile(
        r"(?<![A-Za-z])(?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+[`)}]*\s*\(\d+\)"),
}

# Ссылка на метку постановки — уравнения (eq:) или раздела (sec:, ssec:,
# sssec:, app:) — в докстринге, комментарии или \\eqref{...}. Слева не буква,
# чтобы не зацепить слово, оканчивающееся на «eq». Префикс tab: не берётся:
# в коде это цвета matplotlib («tab:blue»), а не метки.
LABEL_REF = re.compile(r"(?<![A-Za-z])(?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+")
LABEL_DEF = re.compile(r"\\label\{((?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+)\}")


def _sources():
    """Файлы со ссылками на постановку: .py ядра, тестов, примеров и README примеров."""
    files = [p for d in ("gpn_multiphase_solver", "tests", "examples")
             for p in (ROOT / d).rglob("*.py")]
    files += (ROOT / "examples").rglob("*.md")
    return sorted(f for f in files if f.resolve() != SELF)


def _lines():
    """(путь от numerical_solver/, номер строки, текст) по всем источникам."""
    for f in _sources():
        rel = f.relative_to(ROOT)
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            yield rel, n, line


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


def test_no_numeric_equation_or_line_references():
    """Ни одной ссылки номером уравнения или номером строки .tex.

    До DEBT-010 (c0ec060) — 42 нарушения в 14 файлах, после — ни одного.
    Форма «метка (N)» добавлена DEBT-062: 3 нарушения в
    test_energy_matrix_examples.py («eq:bc_props_ext (74)»), после — ни одного.
    """
    bad = [f"{rel}:{n}: {what}: {line.strip()}"
           for rel, n, line in _lines()
           for what, rx in FORBIDDEN.items() if rx.search(line)]
    assert not bad, ("Ссылка на постановку не меткой (DEBT-010; пишите "
                     "«Ур. (eq:<метка>) problem_statement.tex»):\n"
                     + "\n".join(bad))


# Граница строгого шаблона «метка (N)» (DEBT-062, решение пользователя):
# ловит номер, стоящий в скобках целиком сразу после метки, — в том числе
# после `метки`, (метки) и \eqref{метки}; пропускает законный текст в скобках
# после метки — другую метку, пояснение, «3 ячейки». Диапазон «(74–75)» и
# квадратные скобки сознательно не ловятся: широкий шаблон задел бы «(3 ячейки)».
# Если шаблон расширят, упадут случаи False — решение не уйдёт молча.
@pytest.mark.parametrize("text, caught", [
    ("# ── Контур (f=N) ── eq:bc_props_ext (74)", True),   # форма до DEBT-062
    ("Ур. (eq:bc_props_ext) (80) problem_statement.tex", True),
    ("`eq:bc_props_ext` (80)", True),
    (r"\eqref{eq:bc_props_ext} (80)", True),
    ("ssec:bc_disc (5)", True),                            # метка раздела
    ("eq:residual_oil (eq:residual_gas)", False),          # mass_balance.py
    ("eq:QJT_disc (АДВЕКТИВНАЯ форма, BUG-012)", False),   # test_energy_matrix_examples.py
    ("eq:bc_props_ext (3 ячейки)", False),
])
def test_label_number_form(text, caught):
    """Шаблон «метка (N)» ловит номер в скобках после метки и пропускает пояснения (DEBT-062)."""
    assert bool(FORBIDDEN[LABEL_NUMBER].search(text)) is caught


def test_label_references_exist_in_problem_statement():
    """Каждая метка из кода, тестов и примеров объявлена в problem_statement.tex.

    Ловит переименование или удаление метки в документе: ссылка осталась,
    а уравнения (раздела) под ней больше нет. На c0ec060 — 162 ссылки
    (152 на уравнения, 10 на раздел ssec:bc_disc), 157 меток.
    """
    labels = set(LABEL_DEF.findall(TEX.read_text(encoding="utf-8")))
    # Разбор .tex не сломан: меток заведомо больше сотни (157 на c0ec060).
    assert len(labels) > 100
    missing = [f"{rel}:{n}: {m.group()}"
               for rel, n, line in _lines()
               for m in LABEL_REF.finditer(line) if m.group() not in labels]
    assert not missing, ("Метки нет в doc/problem_statement.tex — переименована "
                         "или удалена; поправьте ссылку:\n" + "\n".join(missing))


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
                     "«формула (N) у Автор Год»):\n" + "\n".join(bad))


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
                         "или удалена; поправьте заметку:\n" + "\n".join(missing))


def test_vault_checks_skip_without_vault(monkeypatch, tmp_path):
    """Без vault/knowledge/ (поставка заказчику, FEAT-031) проверки заметок пропускаются."""
    # VAULT читается из глобалов модуля при каждом вызове _vault_lines.
    monkeypatch.setitem(globals(), "VAULT", tmp_path / "нет")
    with pytest.raises(pytest.skip.Exception):
        list(_vault_lines())
