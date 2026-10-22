"""Замены номеров метками в заметках vault/knowledge/ (DEBT-074) — источник точных строк плана.

Режимы (запуск из корня репозитория или worktree):
    numerical_solver/.venv/Scripts/python -I vault/issues/debt-074/probes/plan_apply.py
        проверка в памяти: каждый «До» встречается в файле ровно один раз;
        сторож DEBT-010 (FORBIDDEN и проверка меток из
        numerical_solver/tests/test_eq_references.py) по заметкам без literature/
        до и после замен. Файлы не меняются.
    ... plan_apply.py --table   таблица «До → После» в markdown (для плана)
    ... plan_apply.py --write   применить замены к файлам (шаг 2 плана)

Заметки — по корню, из которого запущен скрипт (Path.cwd()): в worktree правятся
файлы worktree.
"""

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
K = "vault/knowledge/"
D, N = K + "decisions/", K + "numerics/"

GRID = D + "модули-grid-сетка.md"
HYDRO = D + "модули-hydro-newton.md"
RAKE = D + "грабли-реализации.md"
COND = D + "вопрос-кондуктивная-проводимость.md"
P8 = D + "P8-формат-ввода-json.md"
EXT = D + "свойства-фаз-на-контурной-грани-берутся-из-ГУ-при-притоке.md"
ARCH = D + "архитектура библиотеки numerical_solver.md"
PVT = D + "модули-pvt-контракт.md"
COREY = N + "порог-подвижности-Кори-портит-обусловленность-замыкания.md"
ACC = K + "debugging/накопление в балансе энергии считается по приращениям а не как разность запасов.md"
UPW = N + "upstream для подвижностей фаз а не среднее.md"
COMPR = N + ("сжимаемость насыщенной нефти по Стендингу отрицательна выше 345 бар — "
             "при малой S_g шаг вырождается на последовательности Δt.md")

# (файл, строка на 0d5c491, «До», «После»). «До» — уникальный фрагмент строки.
REPLACEMENTS = [
    # ── Номера постановки: по смыслу текста заметки ──
    (GRID, 3, "из problem_statement.tex §4.1, проводимости",
              "из problem_statement.tex (ssec:grid), проводимости"),
    (GRID, 79, "Формулы из problem_statement.tex §4.1.",
               "Формулы из problem_statement.tex, `ssec:grid`."),
    (GRID, 81, "### Грани (eq. 10)", "### Грани (`eq:log_grid`)"),
    (GRID, 100, "### Объёмы (eq. 13)", "### Объёмы (`eq:volume`)"),
    (GRID, 106, "### Проводимости внутренних граней (eq. 19)",
                "### Проводимости внутренних граней (`eq:transmissibility`)"),
    (GRID, 123, "### Логарифмические веса для интерполяции (eq. 21)",
                "### Логарифмические веса для интерполяции (`eq:face_interp`)"),
    (HYDRO, 139, "## Невязки (problem_statement.tex eq. 14, 15, 16-17)",
                 "## Невязки (problem_statement.tex: `eq:residual_oil`, `eq:residual_gas`, "
                 "`eq:residual_eq_r1`, `eq:residual_eq_r2`)"),
    # Строки 184–193 — внутри блока ```python: метка без обратных кавычек.
    (HYDRO, 184, "# Баланс нефтяного компонента (eq. 14)",
                 "# Баланс нефтяного компонента (eq:residual_oil)"),
    (HYDRO, 188, "# Баланс газового компонента (eq. 15)",
                 "# Баланс газового компонента (eq:residual_gas)"),
    (HYDRO, 193, "# Замыкающее уравнение (eq. 16-17)",
                 "# Замыкающее уравнение (eq:residual_eq_r1, eq:residual_eq_r2)"),
    (HYDRO, 206, "- производные членов накопления (eq. 22-27)",
                 "- производные членов накопления (`eq:daccum_oil_dp` … `eq:daccum_gas_dRs`)"),
    (HYDRO, 210, "- Режим 1 (eq. 28):", "- Режим 1 (`eq:deq_r1`):"),
    (HYDRO, 211, "- Режим 2 (eq. 29):", "- Режим 2 (`eq:deq_r2`):"),
    (HYDRO, 251, "## Переключение режимов (problem_statement.tex §4.2.4)",
                 "## Переключение режимов (problem_statement.tex, `sssec:switching_disc`)"),
    (HYDRO, 276, "Критерий сходимости — покомпонентный (§5.2):",
                 "Критерий сходимости — покомпонентный (problem_statement.tex, `ssec:convergence`):"),
    (RAKE, 14, "Поток газового компонента (eq. 9):",
               "Поток газового компонента (`eq:flux_gas`):"),
    # Заметка пишет консервативную форму ⟨Φ·T⟩, ⟨G·Rs⟩; под метками сейчас адвективная.
    (RAKE, 27, "a) Конвективный поток энергии (eq. 23):",
               "a) Конвективный поток энергии (`eq:energy_conv_face`, оператор `eq:upstream_operator`; "
               "сейчас — адвективная форма):"),
    (RAKE, 29, "b) Конвективный поток газосодержания для ṁ (eq. 32):",
               "b) Конвективный поток газосодержания для ṁ (`eq:mdot_conv_face`; сейчас — адвективная "
               "форма):"),
    (RAKE, 44, "Δp` (eq. 24) — не содержит Bo.", "Δp` (`eq:phase_flux`) — не содержит Bo."),
    (COND, 14, "Кондуктивный поток (eq. 25):",
               "Кондуктивный поток (`eq:heat_cond_disc`; здесь и ниже — редакция до BUG-027):"),
    (COND, 19, "Гармоническое среднее (eq. face_interp):", "Гармоническое среднее (`eq:face_interp`):"),
    (COND, 31, "Подставляя в eq. 25:", "Подставляя в `eq:heat_cond_disc`:"),
    (COND, 47, "1. **Ошибка в eq. 25:**", "1. **Ошибка в `eq:heat_cond_disc`:**"),
    (COND, 49, "2. **Ошибка в eq. face_interp:**", "2. **Ошибка в `eq:face_interp`:**"),
    (COND, 51, "в eq. 25 — это грани, не центры.", "в `eq:heat_cond_disc` — это грани, не центры."),
    (P8, 312, "на центр масс кольца (problem_statement.tex eq. 12).",
              "на центр масс кольца (тогдашняя формула `eq:cell_center` problem_statement.tex; "
              "после DEBT-063 там √, как в прототипе)."),
    # Номер рядом с меткой; «(» остаётся, продолжение — на следующей строке заметки.
    (EXT, 30, "`eq:bc_props_ext` (уравнение 74,", "`eq:bc_props_ext` ("),
    # Номера строк .tex: цитата верна на f4fb8c4 (строки 1461–1463), абзац переписан, он в ssec:bc_disc.
    (EXT, 53, "| Постановка, стр. 1461-1473 |",
              "| Постановка, `ssec:bc_disc`, абзац о граничных гранях (цитата — редакция `f4fb8c4`) |"),
    (EXT, 116, "обновлён по формуле (74);", "обновлён по формуле `eq:bc_props_ext`;"),
    (ARCH, 138, "Контракт из problem_statement.tex §2.1 (таблица требований к PVT-модели):",
                "Контракт из problem_statement.tex — таблица «Требования к PVT-модели» в `ssec:closures`:"),
    (PVT, 14, "Из problem_statement.tex, splitting (§3):",
              "Из problem_statement.tex, разделение задачи (`sec:splitting`):"),
    # Докстринги внутри блока ```python заметки: «Ур. (N)» — форма, которую FORBIDDEN не ловит.
    (PVT, 44, "Rs_eq(p). Ур. (3) problem_statement.tex.",
              "Rs_eq(p). Таблица «Требования к PVT-модели» (ssec:closures) problem_statement.tex."),
    (PVT, 55, "Bo(p, Rs). Ур. (8) problem_statement.tex.",
              "Bo(p, Rs). Таблица «Требования к PVT-модели» (ssec:closures) problem_statement.tex."),
    (PVT, 108, "/ Bo. Ур. (51) problem_statement.tex.", "/ Bo. Ур. (eq:rho_oil) problem_statement.tex."),
    (PVT, 182, "k_ro(Sg). Ур. (6) problem_statement.tex.",
               "k_ro(Sg). «Требования к модели ОФП» (ssec:closures) problem_statement.tex."),
    (COREY, 13, "уравнение на насыщенность (problem_statement.tex, eq. 8–9):",
                "уравнение на насыщенность (из потоков компонентов `eq:flux_oil`, `eq:flux_gas` "
                "problem_statement.tex при G^g/G^o = Rs0):"),
    (ACC, 145, "- `numerical_solver/doc/problem_statement.tex` — eq. 5, 23, 28–31, 33–36",
               "- `numerical_solver/doc/problem_statement.tex` — уравнение энергии `eq:main_energy_final`; "
               "накопление $V_j(\\rho c_p)_j/\\Delta t$ — в `eq:tridiag_b`, `eq:tridiag_d`; конвекция — "
               "`eq:energy_conv_face`; JT, адиабатика, дегазация — `eq:QJT_disc`, `eq:Qad_disc`, "
               "`eq:Qdeg_disc`; ṁ — `eq:mdot_conv_face`, `eq:mdot_disc` (метки подобраны по тексту "
               "заметки в DEBT-074: номера «5, 23, 28–31, 33–36» ни одной редакции постановки "
               "в git не соответствуют)"),
    # ── Номера чужих документов: «формула (N) у …», как в коде (CLAUDE.md) ──
    (UPW, 41, "§1.2, eq. (1.16)–(1.20):", "§1.2, формулы (1.16)–(1.20):"),
    (COMPR, 45, "$\\bar c_t \\ge 0$ (ур. 23);", "$\\bar c_t \\ge 0$ (формула (23) у Peszyńska 2006);"),
    (COMPR, 48, "многофазном потоке]] (Eq. 4).", "многофазном потоке]] (там формула (4))."),
]


def guard():
    """Модуль сторожа DEBT-010: FORBIDDEN, LABEL_REF, LABEL_DEF — те же шаблоны, что в тесте."""
    path = ROOT / "numerical_solver/tests/test_eq_references.py"
    spec = importlib.util.spec_from_file_location("test_eq_references", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def notes(texts):
    """(путь от vault/knowledge/, номер строки, текст) по заметкам без literature/."""
    base = ROOT / K
    for f in sorted(base.rglob("*.md")):
        rel = f.relative_to(base)
        if rel.parts[0] == "literature":
            continue
        text = texts.get(f.relative_to(ROOT).as_posix(), None)
        if text is None:
            text = f.read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), 1):
            yield rel.as_posix(), n, line


def survey(g, texts, labels):
    """Нарушения FORBIDDEN и метки, которых нет в постановке."""
    bad = [(rel, n, what) for rel, n, line in notes(texts)
           for what, rx in g.FORBIDDEN.items() if rx.search(line)]
    missing = [(rel, n, m.group()) for rel, n, line in notes(texts)
               for m in g.LABEL_REF.finditer(line) if m.group() not in labels]
    return bad, missing


# Числовые формы вне FORBIDDEN (аудит 2026-10-15): после замен остаются только
# чужие документы и местная нумерация — список печатается для просмотра глазами.
BROAD = re.compile(r"[Уу]р\.\s*\(\d|(?:формул|уравнени)\w*\s+\(?\d|стр\.\s*\d")
STATEMENT_SECTION = re.compile(r"(?:problem_statement|[Пп]остановк)[^\n]*§\s?\d")


def apply_in_memory():
    """Замены в памяти: (тексты по пути от корня, замечания, число «До» не ровно один раз)."""
    texts, problems, count_errors = {}, [], 0
    for f, line, old, new in REPLACEMENTS:
        if f not in texts:
            # newline="" — окончания строк как в файле (CRLF не превращается в LF).
            with open(ROOT / f, encoding="utf-8", newline="") as src:
                texts[f] = src.read()
        text = texts[f]
        count = text.count(old)
        if count != 1:
            problems.append(f"{f}:{line}: «До» встречается {count} раз")
            count_errors += 1
            continue
        at = text[:text.index(old)].count("\n") + 1
        if at != line:
            problems.append(f"{f}: «До» на строке {at}, в плане {line} (сдвиг — не ошибка)")
        texts[f] = text.replace(old, new)
    return texts, problems, count_errors


def residual(texts):
    """Строки с числовыми ссылками, которых сторож не ловит, — после замен."""
    return [(rel, n, line.strip()[:110]) for rel, n, line in notes(texts)
            if BROAD.search(line) or STATEMENT_SECTION.search(line)]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"

    if mode == "--table":
        print("| # | Заметка | Строка | До | После |\n|---|---|---|---|---|")
        for i, (f, line, old, new) in enumerate(REPLACEMENTS, 1):
            short = f.split("/", 2)[2]
            cell = lambda s: s.replace("|", "\\|")  # noqa: E731
            print(f"| {i} | `{short}` | {line} | {cell(old)} | {cell(new)} |")
        return

    texts, problems, count_errors = apply_in_memory()
    print(f"Замен: {len(REPLACEMENTS)}, файлов: {len(texts)}")
    print("Замечания:" if problems else "Каждый «До» найден ровно один раз на своей строке.")
    for p in problems:
        print("  ", p)

    g = guard()
    labels = set(g.LABEL_DEF.findall(g.TEX.read_text(encoding="utf-8")))
    n_notes = len({rel for rel, _, _ in notes({})})
    print(f"Заметок без literature/: {n_notes}; меток в постановке: {len(labels)}")
    for name, state in (("до", {}), ("после", texts)):
        bad, missing = survey(g, state, labels)
        print(f"\n[{name}] нарушений FORBIDDEN: {len(bad)} в {len({b[0] for b in bad})} заметках; "
              f"меток нет в постановке: {len(missing)}")
        for b in bad + missing:
            print("  ", *b)

    rest = residual(texts)
    print(f"\n[после] числовых форм вне FORBIDDEN: {len(rest)} — должны быть только чужие "
          f"документы и местная нумерация:")
    for r in rest:
        print("  ", *r)

    if mode == "--write":
        # Сдвиг строки не мешает записи; мешает только «До», найденный не ровно один раз.
        if count_errors:
            print("\nНе применено: «До» найден не ровно один раз.")
            return
        for f, text in texts.items():
            # newline="" — не менять окончания строк заметки.
            with open(ROOT / f, "w", encoding="utf-8", newline="") as out:
                out.write(text)
        print(f"\nЗаписано файлов: {len(texts)}")


if __name__ == "__main__":
    main()
