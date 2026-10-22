"""FEAT-029, аудит: применить тексты плана §7.1–§7.5 к копии tests/ + examples/.

Копия — probes/impl/numerical_solver/{tests, examples, pyproject.toml};
HydroSolverPrototype и gpn_multiphase_solver — ссылки-переходы (junction) на
основной каталог (conftest.py и один тест ищут их рядом с tests/). Тексты
берутся из файла плана дословно; каждая правка «Было → Стало» проверяет, что
«Было» найдено ровно один раз. §7.6 (сводный README) и §7.7 (README 16) не
применяются — только проверка, что исходные строки на месте.

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\feat-029\\probes\\apply_plan.py
Удаление копии: cmd /c rmdir (только ссылки!), затем Remove-Item -Recurse.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC = ROOT / "numerical_solver"
PLAN = ROOT / "vault" / "plans" / "feat-029 shutin-strong-cooling-example.md"
DST = HERE / "impl" / "numerical_solver"
NAME = "17_shut_in_strong_cooling"

plan = PLAN.read_text(encoding="utf-8")


def section(title: str) -> str:
    """Текст подраздела плана от заголовка '### <title>' до следующего '### ' или '## '."""
    i = plan.index(f"### {title}")
    m = re.search(r"\n(### |## )", plan[i + 4:])
    return plan[i: i + 4 + m.start()] if m else plan[i:]


def blocks(text: str, lang: str) -> list[str]:
    """Блоки кода ```lang … ``` с учётом отступа (пункты списка — 3 пробела)."""
    out = []
    for m in re.finditer(rf"^( *)```{lang}\n(.*?)^\1```", text, re.S | re.M):
        ind = len(m.group(1))
        out.append("\n".join(l[ind:] for l in m.group(2).splitlines()) + "\n")
    return out


def replace_once(path: Path, old: str, new: str, what: str) -> None:
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        print(f"  ✗ {what}: «Было» найдено {n} раз")
        return
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"  ✓ {what}")


# ── Копия ──
if DST.exists():
    print("копия уже есть — удалите её (см. docstring) и запустите снова")
    sys.exit(1)
DST.mkdir(parents=True)
ign = shutil.ignore_patterns("output", "__pycache__", ".pytest_cache")
shutil.copytree(SRC / "tests", DST / "tests", ignore=ign)
shutil.copytree(SRC / "examples", DST / "examples", ignore=ign)
shutil.copy2(SRC / "pyproject.toml", DST / "pyproject.toml")
for link in ("HydroSolverPrototype", "gpn_multiphase_solver"):
    subprocess.run(["cmd", "/c", "mklink", "/J", str(DST / link), str(SRC / link)],
                   check=True, capture_output=True)
print(f"копия: {DST}")

# ── §7.1–§7.3: папка примера ──
ex = DST / "examples" / NAME
ex.mkdir()
(ex / "config.json").write_text(blocks(section("7.1."), "json")[0], encoding="utf-8")
(ex / "main.py").write_text(blocks(section("7.2."), "python")[0], encoding="utf-8")
# README содержит заголовки «##» — ищем блок от заголовка §7.3, а не в section()
i73 = plan.index("### 7.3.")
md = re.search(r"````markdown\n(.*?)\n````", plan[i73:], re.S).group(1) + "\n"
(ex / "README.md").write_text(md, encoding="utf-8")
print("  ✓ §7.1–7.3: config.json, main.py, README.md")

# ── §7.4: списки и комментарии ──
s74 = section("7.4.")
py = blocks(s74, "python")
te = DST / "tests" / "test_examples.py"
tm = DST / "tests" / "test_energy_matrix_examples.py"
replace_once(te, '    "16_well_shut_in",\n    "19_rs150_cooling",',
             '    "16_well_shut_in",\n    "17_shut_in_strong_cooling",\n    "19_rs150_cooling",',
             "§7.4.1 ALL_EXAMPLES (test_examples)")
replace_once(te, py[0], py[1], "§7.4.2 ENDS_SHUT_IN")
replace_once(te, "стоит одного расчёта, а не двадцати одного (~255 с)",
             "стоит одного расчёта, а не двадцати двух (~6 мин)", "§7.4.3 комментарий фикстуры")
# conftest.py копируется вместе с tests/ — правится в копии
replace_once(DST / "tests" / "conftest.py", py[5], py[6], "§7.4.7 комментарий conftest")
replace_once(tm, "# Те же 21 сценарий", "# Те же 22 сценария", "§7.4.4 комментарий списка")
replace_once(tm, '    "16_well_shut_in",\n    "19_rs150_cooling",',
             '    "16_well_shut_in",\n    "17_shut_in_strong_cooling",\n    "19_rs150_cooling",',
             "§7.4.4 ALL_EXAMPLES (матрица)")
replace_once(tm, py[2], py[3].replace("<замер>", "~150"), "§7.4.5 комментарий slow")
anchor = 'SUBDIVIDING_EXAMPLES = ["10_deep_degassing"]'
replace_once(tm, anchor, py[4] + anchor, "§7.4.6 комментарий SUBDIVIDING")

# ── §7.5: класс в конец test_examples.py ──
cls = blocks(section("7.5."), "python")[0]
with te.open("a", encoding="utf-8") as f:
    f.write("\n\n" + cls)
print("  ✓ §7.5 класс TestShutInStrongCooling")

# ── §7.6, §7.7: только проверка исходных строк ──
readme = (SRC / "examples" / "README.md").read_text(encoding="utf-8")
for frag in ("у 19–21\nгазонасыщенность у забоя 0.41–0.45",
             "после BUG-020 считается при `dt_integration` ≤ 3600 с.",
             "кроме 04a, 14 и 19–21", "У 16 последний интервал — останов",
             "(03, 05, 19–21)", "кондукция — в 10, 11, 12, 13a, 13b, 14, 15, 16 и 19–21",
             "У 13b, 14, 16 и 19–21 она", "Сценарии 19–21 задают параметры",
             "кроме 10, 11, 12, 13a, 13b, 14, 15, 16 и 19–21", "У 10–16 и 19–21"):
    print(f"  {'✓' if frag in readme else '✗'} §7.6 «{frag[:50]}»")
r16 = (SRC / "examples" / "16_well_shut_in" / "README.md").read_text(encoding="utf-8")
frag = "Пример останова с развитой газовой зоной и\nсильным охлаждением — FEAT-029 в реестре проекта."
print(f"  {'✓' if frag in r16 else '✗'} §7.7 README 16")
