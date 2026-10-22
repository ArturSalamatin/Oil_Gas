"""DEBT-063, шаг 4: выходы проб на новом коде против планирования.

Для energy_windows, energy_all, fronts: в строках выхода «старое → новое».
После реализации оба значения каждой пары в impl_<проба>.out.txt должны
равняться правому значению той же пары в <проба>.out.txt (планирование,
подмена формулы). Печатает расхождения и итог.

Запуск:  python compare_impl.py   (из любого каталога)
"""
import re
from pathlib import Path

D = Path(__file__).resolve().parent
PAIR = re.compile(r"([-+]?\d[\d.]*(?:e[-+]\d+)?)\s*→\s*([-+]?\d[\d.]*(?:e[-+]\d+)?)")

total = bad = 0
for name in ("energy_windows", "energy_all", "fronts"):
    plan = (D / f"{name}.out.txt").read_text(encoding="utf-8-sig").splitlines()
    impl = (D / f"impl_{name}.out.txt").read_text(encoding="utf-8-sig").splitlines()
    plan = [s for s in plan if PAIR.search(s)]
    impl = [s for s in impl if PAIR.search(s)]
    if len(plan) != len(impl):
        bad += 1
        print(f"! {name}: строк с парами {len(plan)} в планировании, {len(impl)} сейчас")
        continue
    for sp, si in zip(plan, impl):
        rp, ri = PAIR.findall(sp), PAIR.findall(si)
        for (_, new_p), (a_i, b_i) in zip(rp, ri):
            total += 1
            if not (a_i == new_p and b_i == new_p):
                bad += 1
                print(f"! {name}: {si.strip()[:70]} — ждали {new_p}, есть {a_i} → {b_i}")
print(f"пар сравнено: {total}, расхождений: {bad}")
