"""DEBT-036, проверка текста плана: блоки «До/После» шагов 2–5 и код тестов применяются к копии прототипа.

Запуск — из каталога numerical_solver основного дерева:
    .venv\\Scripts\\python d:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\vault\\issues\\debt-036\\probes\\apply_plan.py

Копия: probes/applied/Prototype_1.0.3/{radial_blackoil,tests,...}. Каждый блок «До» должен найтись в файле
ровно один раз. Затем — тесты прототипа в копии (unittest) и сверка файлов тестов с probes/planned_tests/.
Историю примеров на копии считает history_snapshot.py с DEBT036_PROTO=<копия>.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "vault" / "plans" / "debt-036 table-pvt-residual-speedup.md"
SRC = Path.cwd() / "HydroSolverPrototype" / "Prototype_1.0.3"
DST = HERE / "applied" / "Prototype_1.0.3"

text = PLAN.read_text(encoding="utf-8")
steps = text[text.index("## Шаги"):]
blocks = re.findall(r"```python\n(.*?)```", steps, flags=re.S)
assert len(blocks) == 18, f"блоков python: {len(blocks)}, ожидалось 18"
# 0–7, 14–15 — blackoil.py; 8–13 — pvt.py; 16, 17 — файлы тестов
target = {i: "blackoil.py" for i in (0, 1, 2, 3, 4, 5, 6, 7, 14, 15)}
target.update({i: "pvt.py" for i in range(8, 14)})

if DST.exists():
    shutil.rmtree(DST)
DST.mkdir(parents=True)
for name in ("radial_blackoil", "tests"):
    shutil.copytree(SRC / name, DST / name, ignore=shutil.ignore_patterns("__pycache__"))
for f in SRC.iterdir():
    if f.is_file():   # run_prototype.py, VERSION.txt, BUILD.txt, ... (test_output_contract их проверяет)
        shutil.copy2(f, DST / f.name)

for i in range(0, 16, 2):
    path = DST / "radial_blackoil" / target[i]
    src = path.read_text(encoding="utf-8")
    before, after = blocks[i], blocks[i + 1]
    n = src.count(before)
    assert n == 1, f"блок {i} («До» для {target[i]}) найден {n} раз:\n{before}"
    path.write_text(src.replace(before, after), encoding="utf-8")
    print(f"блок {i // 2 + 1}: {target[i]} — применён")

for i, name in ((16, "test_inventories_cache.py"), (17, "test_pvto_vectorized.py")):
    (DST / "tests" / name).write_text(blocks[i], encoding="utf-8")
    same = blocks[i] == (HERE / "planned_tests" / name).read_text(encoding="utf-8")
    print(f"{name}: {'совпадает' if same else 'ОТЛИЧАЕТСЯ'} с planned_tests/{name}")

# Удалённое не должно остаться
pvt = (DST / "radial_blackoil" / "pvt.py").read_text(encoding="utf-8")
bo = (DST / "radial_blackoil" / "blackoil.py").read_text(encoding="utf-8")
assert "_branch_prop_delta" not in pvt and re.search(r"_oil_prop\b", pvt) is None, "остался _oil_prop/_branch_prop_delta"
assert "self.component_inventories(state_old); qo" not in bo, "physical_residual не переведён на _old_inventories"

def run_tests(label):
    r = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], cwd=DST, capture_output=True, text=True)
    print(f"{label}: " + (r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-2000:]))
    if r.returncode != 0:
        print(r.stdout[-4000:])


run_tests("шаги 2–5 целиком")

if "--stepwise" in sys.argv:
    # Пошагово, как /implement: после шага N — код шагов 2..N и только тесты, которые план относит к шагам 2..N
    def keep_tests(code, names, drop_lines=()):
        """Файл теста с методами test_* только из names (шапка и помощники — целиком)."""
        parts = re.split(r"(?m)^(?=    def test_)", code)
        head, tests = parts[0], parts[1:]
        last = tests[-1]
        tail = last[last.index("\nif __name__"):] if "\nif __name__" in last else ""
        if tail: tests[-1] = last[:last.index("\nif __name__")] + "\n"
        kept = [t for t in tests if re.match(r"    def (test_\w+)", t).group(1) in names]
        out = head + "".join(kept) + tail
        for line in drop_lines: out = out.replace(line + "\n", "")
        return out
    plan_steps = [
        (2, (0,), {"test_inventories_cache.py": {"test_inventories_without_viscosities"}}, 84),
        (3, (2, 4, 6), {"test_inventories_cache.py": {"test_inventories_without_viscosities", "test_old_inventories_once_per_state",
                                                       "test_residual_bitwise_fresh_model", "test_old_inventories_follow_in_place_change"}}, 87),
        (4, (8, 10), {"test_pvto_vectorized.py": {"test_bo_mu_bitwise_former_loop", "test_shapes_as_before", "test_single_rs_branch_rejected"}}, 90),
        (5, (12, 14), {"test_pvto_vectorized.py": {"test_bo_mu_bitwise_former_loop", "test_shapes_as_before", "test_single_rs_branch_rejected",
                                                    "test_bo_mu_o_one_pass", "test_mobilities_one_pvto_pass"}}, 92),
    ]
    shutil.rmtree(DST); DST.mkdir(parents=True)
    for name in ("radial_blackoil", "tests"):
        shutil.copytree(SRC / name, DST / name, ignore=shutil.ignore_patterns("__pycache__"))
    for f in SRC.iterdir():
        if f.is_file(): shutil.copy2(f, DST / f.name)
    code_of = {"test_inventories_cache.py": blocks[16], "test_pvto_vectorized.py": blocks[17]}
    for step, idx, tests, expect in plan_steps:
        for i in idx:
            path = DST / "radial_blackoil" / target[i]
            src = path.read_text(encoding="utf-8")
            assert src.count(blocks[i]) == 1, f"шаг {step}: блок {i} найден {src.count(blocks[i])} раз"
            path.write_text(src.replace(blocks[i], blocks[i + 1]), encoding="utf-8")
        for fname, names in tests.items():
            drop = ("from radial_blackoil.units import CP_TO_PA_S",) if step == 4 else ()
            (DST / "tests" / fname).write_text(keep_tests(code_of[fname], names, drop), encoding="utf-8")
        run_tests(f"после шага {step} (план: {expect} passed)")
