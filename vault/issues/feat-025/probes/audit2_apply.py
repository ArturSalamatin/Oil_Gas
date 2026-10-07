"""FEAT-025, аудит раунд 2: исполнить шаги 2–4 и 6 плана на копии (песочница audit2/).

Копирует numerical_solver/examples (без output/, __pycache__) и три файла tests/
в probes/audit2/, затем применяет правки ДОСЛОВНО из текста плана:
  шаг 2 — make_configs.py <audit2/examples> names=1 (+ побайтное сравнение с probes/final);
  шаг 3 — main.py 19 из блока плана, 20 и 21 — подстановками из таблицы плана;
  шаг 4.1 — ALL_EXAMPLES test_examples.py;
  шаг 4.2 — правки test_energy_matrix_examples.py («было» ищется буквально);
  шаг 4.3 — блок «R.» в конец test_examples.py;
  шаг 6 — README 19 из блока плана; README 20/21 — из README 19 заменой заголовка
          (только для тестов структуры README; содержание 20/21 план задаёт описанием).
Каждая замена «было → стало» проверяет, что «было» встречается в файле ровно один раз.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-025\\probes\\audit2_apply.py
"""

import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOLVER = ROOT / "numerical_solver"
PLAN = ROOT / "vault" / "plans" / "feat-025 standing-corey-cooling-examples.md"
BOX = HERE / "audit2"

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

plan = PLAN.read_text(encoding="utf-8")
problems = []


def section(start, end):
    """Текст плана между двумя заголовками (по началу строки)."""
    i = plan.index(start)
    j = plan.index(end, i + len(start))
    return plan[i:j]


def blocks(text, lang=None, fence="```"):
    """Код-блоки секции: [(язык, код)], код — с dedent по отступу открывающей черты."""
    out = []
    pat = re.compile(rf"^([ \t]*){re.escape(fence)}(\w*)\n(.*?)^\1{re.escape(fence)}[ \t]*$",
                     re.S | re.M)
    for m in pat.finditer(text):
        indent, lng, body = m.group(1), m.group(2), m.group(3)
        body = "\n".join(l[len(indent):] if l.startswith(indent) else l
                         for l in body.split("\n"))
        if lang is None or lng == lang:
            out.append((lng, body))
    return out


def replace_once(src, old, new, what):
    n = src.count(old)
    if n != 1:
        problems.append(f"{what}: «было» найдено {n} раз")
        return src
    return src.replace(old, new)


# ── Песочница ──
if BOX.exists():
    shutil.rmtree(BOX)
shutil.copytree(SOLVER / "examples", BOX / "examples",
                ignore=shutil.ignore_patterns("output", "__pycache__"))
(BOX / "tests").mkdir(parents=True)
for f in ("conftest.py", "test_examples.py", "test_energy_matrix_examples.py"):
    shutil.copy2(SOLVER / "tests" / f, BOX / "tests" / f)

# ── Шаг 2: конфиги генератором ──
subprocess.run([sys.executable, str(HERE / "make_configs.py"), str(BOX / "examples"),
                "names=1"], check=True, capture_output=True)
for nm in ("19_rs150_cooling", "20_rs500_cooling", "21_rs100_cooling"):
    a = (BOX / "examples" / nm / "config.json").read_bytes()
    b = (HERE / "final" / nm / "config.json").read_bytes()
    print(f"шаг 2: {nm}/config.json побайтно = probes/final: {a == b}")
    if a != b:
        problems.append(f"шаг 2: {nm} конфиг отличается от probes/final")

# ── Шаг 3: main.py ──
s3 = section("### Шаг 3: `main.py`", "### Шаг 4: Тесты")
main19 = blocks(s3, "python")[0][1]
(BOX / "examples" / "19_rs150_cooling" / "main.py").write_text(main19, encoding="utf-8")
rows = re.findall(r"^\| (2[01]) \| `([^`]*)` \| `([^`]*)` \| `([^`]*)` \|$", s3, re.M)
doc19 = re.search(r'"""(.*?)"""', main19).group(1)
title19 = re.search(r'title="([^"]*)"', main19).group(1)
gor19 = "(GOR = 128.7 < R_s0 = 150 и растёт)"
if gor19 not in main19:
    problems.append("шаг 3: в main.py 19 нет фрагмента комментария GOR для подстановки")
for num, doc, title, gor in rows:
    nm = {"20": "20_rs500_cooling", "21": "21_rs100_cooling"}[num]
    txt = main19.replace(doc19, doc).replace(title19, title)
    # комментарий в main.py 19 разбит на строки: GOR = 128.7 < R_s0 = 150 и растёт)
    txt = txt.replace("(GOR = 128.7 < R_s0 = 150 и растёт)", gor)
    (BOX / "examples" / nm / "main.py").write_text(txt, encoding="utf-8")
print(f"шаг 3: main.py 19 + строки таблицы для {[r[0] for r in rows]}")

# ── Шаг 4.1 и 4.3: test_examples.py ──
te_path = BOX / "tests" / "test_examples.py"
te = te_path.read_text(encoding="utf-8")
s41 = section("**4.1**", "**4.2**")
ins = blocks(s41, "python")[0][1]
te = replace_once(te, '    "15_oil_rate_ramp_up",\n]', '    "15_oil_rate_ramp_up",\n' + ins + "]",
                  "4.1 ALL_EXAMPLES")
s43 = section("**4.3**", "**Проверка после шага**")
blk = blocks(s43, "python")[0][1]
te = te.rstrip("\n") + "\n" + blk
te_path.write_text(te, encoding="utf-8")

# ── Шаг 4.2: test_energy_matrix_examples.py ──
tm_path = BOX / "tests" / "test_energy_matrix_examples.py"
tm = tm_path.read_text(encoding="utf-8")
s42 = section("**4.2**", "**4.3**")
b = [code for _, code in blocks(s42, "python")]
# порядок блоков в плане: [0] _ref_d_scale, [1] хвост build_reference было, [2] стало,
# [3] вызов было, [4] вызов стало, [5] сверка d было, [6] стало
print(f"шаг 4.2: python-блоков в плане {len(b)}")
tm = replace_once(tm, "# Те же 17 сценариев, что в tests/test_examples.py::ALL_EXAMPLES.",
                  "# Те же 20 сценариев, что в tests/test_examples.py::ALL_EXAMPLES.", "4.2 строка 55")
tm = replace_once(tm, '    "15_oil_rate_ramp_up",\n]', '    "15_oil_rate_ramp_up",\n' + ins + "]",
                  "4.2 ALL_EXAMPLES")
# _ref_d_scale — после конца _ref_assemble, перед def build_reference
tm = replace_once(tm, "\n\ndef build_reference(", "\n\n" + b[0].rstrip("\n") + "\n\n\ndef build_reference(",
                  "4.2 вставка _ref_d_scale")
tm = replace_once(tm, "def build_reference(grid, pvt, rock, hydro_result, state_prev, dt, bc):",
                  "def build_reference(grid, pvt, rock, hydro_result, state_prev, dt, bc,\n"
                  "                    with_scale=False):", "4.2 сигнатура")
tm = replace_once(tm, b[1].rstrip("\n"), b[2].rstrip("\n"), "4.2 хвост build_reference")
tm = replace_once(tm, b[3].rstrip("\n"), b[4].rstrip("\n"), "4.2 вызов эталона")
tm = replace_once(tm, b[5].rstrip("\n"), b[6].rstrip("\n"), "4.2 сверка d")
tm = replace_once(tm, "Ожидание: a, b, c, d совпадают с эталоном при rtol=1e-12; границы",
                  "Ожидание: a, b, c совпадают с эталоном при rtol=1e-12, d — с допуском\n"
                  "    от слагаемых ячейки (см. RTOL); границы", "4.2 docstring")
tm_path.write_text(tm, encoding="utf-8")

# ── Шаг 6: README ──
s6 = section("#### `numerical_solver/examples/19_rs150_cooling/README.md`",
             "#### `numerical_solver/examples/20_rs500_cooling/README.md`")
readme19 = blocks(s6, "markdown", fence="````")[0][1]
(BOX / "examples" / "19_rs150_cooling" / "README.md").write_text(readme19, encoding="utf-8")
for nm, head in (("20_rs500_cooling", "# 20 — $R_{s,0} = 500$, летучая нефть: охлаждение забоя"),
                 ("21_rs100_cooling", "# 21 — $R_{s,0} = 100$, горячий пласт: охлаждение забоя")):
    first, rest = readme19.split("\n", 1)
    (BOX / "examples" / nm / "README.md").write_text(head + "\n" + rest, encoding="utf-8")

# ── Синтаксис ──
for p in (te_path, tm_path, *(BOX / "examples").glob("2[01]_*/main.py"),
          BOX / "examples" / "19_rs150_cooling" / "main.py"):
    try:
        compile(p.read_text(encoding="utf-8"), str(p), "exec")
    except SyntaxError as e:
        problems.append(f"синтаксис {p.name}: {e}")
long_lines = [(p.name, i + 1, len(l)) for p in (te_path, tm_path)
              for i, l in enumerate(p.read_text(encoding="utf-8").split("\n")) if len(l) > 100]
print(f"строк длиннее 100 в тестовых файлах песочницы: {long_lines}")
print("ПРОБЛЕМЫ:" if problems else "проблем применения нет", *problems, sep="\n   ")
