"""BUG-016, аудит: применить план ТЕКСТОМ к копии дерева (worktree аудита).

Запуск: python <этот файл> <каталог numerical_solver копии> <этап>
этапы:
  tests — tests/test_prototype_globalization.py из блока шага 1 плана;
  step2 — блоки «До/После» шага 2 (blackoil.py), каждый «До» — ровно 1 вхождение;
  step3 — шаг 3: 3.2 — блоками «До/После»; 3.1 — как описано (в плане «...»).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = (ROOT / "vault" / "plans" / "bug-016 newton-line-search-norm.md").read_text(encoding="utf-8")
NS = Path(sys.argv[1]).resolve()
stage = sys.argv[2]


def section(title_start, next_title_start):
    i = PLAN.index(title_start)
    j = PLAN.index(next_title_start, i)
    return PLAN[i:j]


def blocks(text):
    return re.findall(r"```python\n(.*?)```", text, re.S)


def apply_pairs(path, pairs):
    src = path.read_text(encoding="utf-8")
    for k, (before, after) in enumerate(pairs, 1):
        n = src.count(before)
        print(f"  {path.name}: пара {k}: вхождений «До» = {n}")
        if n != 1:
            raise SystemExit(f"  СТОП: «До» пары {k} найдено {n} раз")
        src = src.replace(before, after)
    path.write_text(src, encoding="utf-8")


if stage == "tests":
    b = [x for x in blocks(section("### Шаг 1:", "### Шаг 2:")) if "BUG-016: третья ступень" in x]
    assert len(b) == 1, len(b)
    (NS / "tests" / "test_prototype_globalization.py").write_text(b[0], encoding="utf-8")
    print("  tests/test_prototype_globalization.py записан,", len(b[0].splitlines()), "строк")

elif stage == "step2":
    bl = blocks(section("### Шаг 2:", "### Шаг 3:"))
    print(f"  блоков python в шаге 2: {len(bl)}")
    assert len(bl) == 8, "ожидалось 4 пары «До/После»"
    pairs = [(bl[i], bl[i + 1]) for i in range(0, 8, 2)]
    apply_pairs(NS / "HydroSolverPrototype" / "Prototype_1.0.3" / "radial_blackoil" / "blackoil.py", pairs)

elif stage == "step3":
    s3 = section("### Шаг 3:", "### Шаг 4:")
    bl = blocks(s3)
    # 3.2 — единственная пара блоков python шага 3 (3.1 — фрагменты с «...»)
    pair = [x for x in bl if "SUBDIVIDING_EXAMPLES" in x]
    assert len(pair) == 2, len(pair)
    apply_pairs(NS / "tests" / "test_energy_matrix_examples.py", [(pair[0], pair[1])])
    # 3.1 — как сделал бы исполнитель по описанию плана
    wb = NS / "tests" / "test_prototype_well_branch.py"
    src = wb.read_text(encoding="utf-8")
    old_calls = 'assert calls == [ORIGINAL, ("shut", None), ("open", None)]'
    new_calls = ('assert calls == [ORIGINAL, ("shut", None), ("open", None), '
                 '("shut", None), ("open", None)]')
    print(f"  {wb.name}: вхождений старой последовательности = {src.count(old_calls)}")
    old_c = ("        # Отказ везде: после двух веток запасной путь сдаётся, converged = False —\n"
             "        # адаптер раздробит шаг, как раньше.\n")
    new_c = ("        # Отказ везде: после двух веток запасной путь сдаётся; третья ступень\n"
             "        # (BUG-016) повторяет его с ||F||_2 и ограничителем dS_g — тоже отказ.\n"
             "        # converged = False — адаптер раздробит шаг, как раньше.\n")
    assert src.count(old_c) == 1, "комментарий test_all_fail не найден"
    src = src.replace(old_c, new_c)
    # Последовательность меняется только в test_all_fail и test_both_branches_inconsistent;
    # у test_fallback_second_branch та же старая строка — её НЕ трогать
    parts = src.split("    def test_all_fail")
    head, tail = parts[0], "    def test_all_fail" + parts[1]
    k = tail.index("    def test_fallback_start_from_old_state")
    tail = tail[:k].replace(old_calls, new_calls) + tail[k:]
    wb.write_text(head + tail, encoding="utf-8")
    print(f"  {wb.name}: новых последовательностей = {(head + tail).count(new_calls)}")
