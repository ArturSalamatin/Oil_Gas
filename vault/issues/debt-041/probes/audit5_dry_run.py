"""DEBT-041, аудит раунда 5: сухой прогон правок плана — блоки «До» → «После» на текущих файлах, в памяти.

Для каждой пары: «До» обязан встречаться в целевом файле ровно один раз (иначе Edit не найдёт или
заменит не то); замены применяются по порядку плана, накопительно. После всех замен .py-файлы
компилируются (синтаксис docstring и комментариев), а в README считается число столбцов таблиц.
Рабочие файлы не меняются.

Запуск — из корня проекта: numerical_solver\\.venv\\Scripts\\python <P>\\audit5_dry_run.py
"""
import re
import subprocess
from pathlib import Path

ROOT = Path.cwd()
PLAN = ROOT / "vault" / "plans" / "debt-041 example03-max-retries-table.md"
TARGETS = [
    "numerical_solver/examples/03_standing_corey/README.md",
    "numerical_solver/examples/04_table_table/README.md",
    "numerical_solver/examples/04a_high_gas_saturation/README.md",
    "numerical_solver/examples/05_standing_table_rp/README.md",
    "numerical_solver/gpn_multiphase_solver/io/config.py",
    "numerical_solver/tests/test_factory_standing_hydro.py",
    "numerical_solver/tests/test_config.py",
]


def blocks(lines):
    """Пары (До, После) в порядке плана: метка — строка, оканчивающаяся на «До:» / начинающаяся с «После»."""
    pairs, want, i = [], None, 0
    while i < len(lines):
        s = lines[i].strip()
        if s.endswith("До:"):
            want = "before"
        elif s.startswith("После") and s.endswith(":"):
            want = "after"
        elif s.startswith("```") and want and lines[i].startswith("```"):
            j = i + 1
            while not lines[j].startswith("```"):
                j += 1
            text = "\n".join(lines[i + 1:j]) + "\n"
            if want == "before":
                pairs.append([text, None])
            else:
                pairs[-1][1] = text
            want, i = None, j
        i += 1
    return pairs


files = {t: (ROOT / t).read_text(encoding="utf-8") for t in TARGETS}
head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
print(f"HEAD {head}; план: {PLAN.name}", flush=True)
pairs = blocks(PLAN.read_text(encoding="utf-8").splitlines())
print(f"пар «До → После»: {len(pairs)}", flush=True)

ok = True
for k, (before, after) in enumerate(pairs, 1):
    hits = [t for t in TARGETS if before in files[t]]
    counts = {t: files[t].count(before) for t in hits}
    first = before.strip().splitlines()[0][:60]
    if len(hits) != 1 or counts[hits[0]] != 1 or after is None:
        ok = False
        print(f"#{k} ОШИБКА «{first}»: файлов {len(hits)}, вхождений {counts}, После {'нет' if after is None else 'есть'}")
        continue
    t = hits[0]
    files[t] = files[t].replace(before, after)
    print(f"#{k} OK {Path(t).parent.name}/{Path(t).name}: «{first}»")

for t in TARGETS:
    if t.endswith(".py"):
        try:
            compile(files[t], t, "exec")
            print(f"compile OK: {t}")
        except SyntaxError as e:
            ok = False
            print(f"compile ОШИБКА: {t}: {e}")

# Таблицы README, затронутые правками: одинаковое число столбцов в строках таблицы
for t in TARGETS[:4]:
    for m in re.finditer(r"(?:^\|.*\|\n)+", files[t], flags=re.M):
        widths = {row.count("|") for row in m.group(0).splitlines()}
        if "max_retries" in m.group(0) and len(widths) != 1:
            ok = False
            print(f"таблица ОШИБКА {t}: разное число '|' в строках {sorted(widths)}")
print("ИТОГ:", "все пары применимы, .py компилируются" if ok else "есть ошибки")
