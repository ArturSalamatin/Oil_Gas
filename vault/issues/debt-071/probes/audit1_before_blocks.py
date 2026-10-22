"""DEBT-071, аудит 1: каждая цитата «До» шагов 1–2 плана есть в файле базы ровно один раз.

Цитаты извлекаются из файла плана: блок ```…``` после строки «До…:» внутри шага; файл —
по ближайшему выше упоминанию имени файла в пункте. Проверка — по содержимому, без номеров
строк. Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-071\\probes\\audit1_before_blocks.py
"""
import re
from pathlib import Path

ROOT = Path.cwd()
PLAN = ROOT / "vault" / "plans" / "debt-071 standing-relperm-range-check.md"
FILES = {
    "diagnostics.py": "numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/diagnostics.py",
    "test_pvt_clamp.py": "numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_pvt_clamp.py",
    "prototype_adapter.py": "numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py",
    "factory.py": "numerical_solver/gpn_multiphase_solver/factory.py",
    "hydro_to_blackoil_adapter.py": "numerical_solver/gpn_multiphase_solver/pvt/hydro_to_blackoil_adapter.py",
    "test_factory_standing_hydro.py": "numerical_solver/tests/test_factory_standing_hydro.py",
}

lines = PLAN.read_text(encoding="utf-8").splitlines()
current = None
blocks = []
i = 0
while i < len(lines):
    line = lines[i]
    for name in FILES:
        if f"`{name}`" in line or f"{name}`" in line or f"/{name}" in line:
            current = name
    if re.match(r"\s*(\d+\.\s*)?.*До( \(строк[аи] [\d\-, ]+\))?:\s*$", line) and "После" not in line:
        # следующий ``` блок
        j = i + 1
        while j < len(lines) and not lines[j].strip().startswith("```"):
            j += 1
        k = j + 1
        while k < len(lines) and not lines[k].strip().startswith("```"):
            k += 1
        indent = len(lines[j]) - len(lines[j].lstrip())
        body = [ln[indent:] if ln.strip() else "" for ln in lines[j + 1:k]]
        blocks.append((i + 1, current, body))
        i = k
    i += 1

bad = 0
for at, name, body in blocks:
    src = (ROOT / FILES[name]).read_text(encoding="utf-8").splitlines()
    # «...» в цитате — пропуск строк: каждая часть ищется отдельно, по порядку
    parts, cur = [], []
    for ln in body:
        if ln.strip() == "...":
            parts.append(cur); cur = []
        else:
            cur.append(ln)
    parts.append(cur)
    for part in parts:
        n = sum(1 for s in range(len(src) - len(part) + 1) if src[s:s + len(part)] == part)
        ok = n == 1
        bad += not ok
        print(f"план:{at:4d} {name:32s} строк {len(part):2d}: найдено {n} {'OK' if ok else '<-- ПРОБЛЕМА'}")
print(f"итог: цитат-частей {sum(1 for _ in blocks)} блоков, проблем {bad}")
