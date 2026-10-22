"""DEBT-079, планирование: каждый блок «До» шагов 1–2 плана найден ровно один раз ровно в одном файле.

Блоки берутся из vault/plans/debt-079 relperm-immobile-gas-first-row.md: после строки «До:»
ограждение «   ```<язык>» … «   ```», отступ пункта списка (3 пробела) снимается. Якоря вставок
(п. 2 и п. 6 шага 1) проверяются отдельно.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-079\\probes\\plan_blocks_check.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PLAN = ROOT / "vault" / "plans" / "debt-079 relperm-immobile-gas-first-row.md"
SOLVER = ROOT / "numerical_solver"
FILES = [
    SOLVER / "gpn_multiphase_solver" / "factory.py",
    SOLVER / "tests" / "test_factory_prototype.py",
    SOLVER / "tests" / "test_table_range_warnings.py",
    SOLVER / "examples" / "04_table_table" / "README.md",
    SOLVER / "examples" / "05_standing_table_rp" / "README.md",
    ROOT / "vault" / "knowledge" / "decisions" / "P8-формат-ввода-json.md",
]
ANCHORS = [
    "    # DEBT-073: выше последней строки TabulatedRelPerm берёт k_ro, k_rg из неё\n",
    "    # ── Последняя строка ОФП: k_ro = 0 (DEBT-073) ──\n",
    "Не меньше двух строк, $S_g$ строго растёт (`_check_relperm_table`, DEBT-044). Последняя строка",
    "CSV-таблицы: числа, пределы, монотонность, ветви PVTO, $k_{ro} = 0$ в последней строке ОФП "
    "(DEBT-042, DEBT-044, DEBT-038, DEBT-073)",
]


def before_blocks(text):
    steps = text.split("### Шаг 1", 1)[1].split("### Шаг 3", 1)[0]
    out, lines, i = [], steps.split("\n"), 0
    while i < len(lines):
        if lines[i].strip() == "До:" and re.fullmatch(r"   ```\w*", lines[i + 1]):
            j, body = i + 2, []
            while lines[j] != "   ```":
                body.append(lines[j][3:] if lines[j].startswith("   ") else lines[j])
                j += 1
            out.append("\n".join(body) + "\n")
            i = j
        i += 1
    return out


def main():
    texts = {p: p.read_text(encoding="utf-8") for p in FILES}
    blocks = before_blocks(PLAN.read_text(encoding="utf-8"))
    bad = 0
    for k, b in enumerate(blocks, 1):
        hits = {p.name: texts[p].count(b) for p in FILES if texts[p].count(b)}
        ok = len(hits) == 1 and list(hits.values()) == [1]
        bad += not ok
        print(f"{'OK  ' if ok else 'FAIL'} «До» {k}: {hits or 'не найден'} — {b.splitlines()[0][:70]}")
    for a in ANCHORS:
        hits = {p.name: texts[p].count(a) for p in FILES if texts[p].count(a)}
        ok = list(hits.values()) == [1]
        bad += not ok
        print(f"{'OK  ' if ok else 'FAIL'} якорь: {hits or 'не найден'} — {a.strip()[:70]}")
    print(f"\nблоков «До»: {len(blocks)}, якорей: {len(ANCHORS)}, ошибок: {bad}")


if __name__ == "__main__":
    main()
