"""DEBT-023: текст плана применяется к копиям файлов в памяти.

Разбирает vault/plans/debt-023 physical-conductivity-examples.md: пункты N.M
шагов 2–7 с «До» / «После» (в строке — `…`, блоком — ```…```), сопоставляет
пункту файл и проверяет:
  - «до» встречается в файле ровно один раз (после предыдущих замен того же файла);
  - после замены «после» в файле есть.
Шаг 1 (конфиги) — отдельно: блок «До» есть в каждом из восьми config.json.
Файлы на диске не меняются.

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-023\\probes\\plan_check.py
"""

import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[4]   # probes → debt-023 → issues → vault → корень
PLAN = ROOT / "vault" / "plans" / "debt-023 physical-conductivity-examples.md"
NS = ROOT / "numerical_solver"
EX = NS / "examples"
KN = ROOT / "vault" / "knowledge"

FILES = {}
for k in ("2.1",):
    FILES[k] = NS / "gpn_multiphase_solver" / "io" / "config.py"
FILES["2.2"] = NS / "tests" / "test_config.py"
FILES["2.3"] = NS / "tests" / "test_energy_matrix_examples.py"
FILES["2.4"] = NS / "tests" / "test_dt_convergence.py"
for k in ("2.5", "2.6", "2.7"):
    FILES[k] = NS / "tests" / "test_energy_balance_examples.py"
FILES["2.8"] = NS / "tests" / "test_examples.py"
for i in range(1, 10):
    FILES[f"3.{i}"] = EX / "03_standing_corey" / "README.md"
for i in range(1, 10):
    FILES[f"4.{i}"] = EX / "04_table_table" / "README.md"
for i in range(10, 16):
    FILES[f"4.{i}"] = EX / "04a_high_gas_saturation" / "README.md"
for i in range(1, 5):
    FILES[f"5.{i}"] = EX / "05_standing_table_rp" / "README.md"
for i in (5, 6):
    FILES[f"5.{i}"] = EX / "06_table_corey_rp" / "README.md"
for i in (7, 8):
    FILES[f"5.{i}"] = EX / "07_degassing_adiabatic_only" / "README.md"
for i in (9, 10, 11):
    FILES[f"5.{i}"] = EX / "08_degassing_jt" / "README.md"
for i in (12, 13, 14):
    FILES[f"5.{i}"] = EX / "09_degassing_latent_heat" / "README.md"
for i in range(1, 8):
    FILES[f"6.{i}"] = EX / "README.md"
FILES["7.2"] = KN / "decisions" / "P8-формат-ввода-json.md"
FILES["7.3"] = next(p for p in (KN / "debugging").iterdir()
                    if p.name.startswith("нефизичная"))
for k in ("7.4", "7.5"):   # аудит 1: заметка о сверке матрицы
    FILES[k] = next(p for p in (KN / "validation").iterdir()
                    if p.name.startswith("матрица температурной задачи"))

ITEM = re.compile(r"^(\d+\.\d+)\. ")
INLINE = re.compile(r"`([^`]*)`")


def parse(lines):
    """[(пункт, до, после)] по тексту плана."""
    out, item, i = [], None, 0
    pending = None          # «до», ждущее «после»
    expect_two = False      # «До → После:» — два блока подряд
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            # Блок кода, не взятый как «до»/«после» (например, полный текст
            # заметки в 7.1): его строки — не маркеры, пропускаем целиком.
            i += 1
            while not lines[i].startswith("```"):
                i += 1
            i += 1
            continue
        m = ITEM.match(ln)
        if m:
            item, pending, expect_two = m.group(1), None, False
        head = ln.lstrip()
        if item and (head.startswith("До") or head.startswith("После")):
            is_before = head.startswith("До")
            if "→ После" in head:
                expect_two = True
            found = INLINE.findall(ln)
            if found and not ln.rstrip().endswith(":"):
                # последняя пара: в «До (на `6cf8515`): `…`» первая — коммит
                text = found[-1]
            else:
                # блок ``` на следующих строках
                j = i + 1
                while not lines[j].startswith("```"):
                    j += 1
                k = j + 1
                while not lines[k].startswith("```"):
                    k += 1
                text = "\n".join(lines[j + 1:k])
                if expect_two:
                    k2 = k + 1
                    while not lines[k2].startswith("```"):
                        k2 += 1
                    k3 = k2 + 1
                    while not lines[k3].startswith("```"):
                        k3 += 1
                    out.append((item, text, "\n".join(lines[k2 + 1:k3])))
                    expect_two, i = False, k3 + 1
                    continue
                i = k
            if is_before:
                pending = text
            elif pending is not None:
                out.append((item, pending, text))
                pending = None
        i += 1
    return out


def main():
    lines = PLAN.read_text(encoding="utf-8").split("\n")
    edits = parse(lines)
    # Шаг 1 — блок «До» из раздела шага 1 (первый ```json после «### Шаг 1»)
    s1 = lines.index(next(l for l in lines if l.startswith("### Шаг 1")))
    j = next(k for k in range(s1, len(lines)) if lines[k].startswith("```json"))
    k = next(n for n in range(j + 1, len(lines)) if lines[n].startswith("```"))
    cfg_before = "\n".join(lines[j + 1:k])
    names = ["03_standing_corey", "04_table_table", "04a_high_gas_saturation",
             "05_standing_table_rp", "06_table_corey_rp",
             "07_degassing_adiabatic_only", "08_degassing_jt", "09_degassing_latent_heat"]
    bad = 0
    for n in names:
        c = (EX / n / "config.json").read_text(encoding="utf-8").replace("\r\n", "\n").count(cfg_before)
        print(f"шаг 1 {n}: «до» встречается {c} раз")
        bad += c != 1

    texts, crlf = {}, set()
    for item, before, after in edits:
        f = FILES.get(item)
        if f is None:
            print(f"{item}: файл не сопоставлен — ПРОПУСК")
            bad += 1
            continue
        if f not in texts:
            raw = f.read_text(encoding="utf-8")
            if "\r\n" in raw:
                crlf.add(f)
            texts[f] = raw.replace("\r\n", "\n")
        n = texts[f].count(before)
        texts[f] = texts[f].replace(before, after, 1) if n == 1 else texts[f]
        ok_after = after in texts[f]
        flag = "OK" if (n == 1 and ok_after) else "ОШИБКА"
        bad += flag != "OK"
        print(f"{item} {f.relative_to(ROOT)}: «до» ×{n}, «после» найдено: {ok_after} — {flag}")
    print(f"\nпунктов с «до»/«после»: {len(edits)}; файлов: {len(texts)}; с CRLF: "
          f"{[str(p.relative_to(ROOT)) for p in crlf]}")

    # Остатки после применения — те же шаблоны, что в проверках шагов 3–8 плана
    print("\nостатки после применения:")
    readme_pat = re.compile(r"еплопроводность обнулена|обнулены, см|\\lambda = 0")
    for f, t in texts.items():
        if f.name == "README.md" and re.match(r"0[3-9]", f.parent.name):
            hits = [ln for ln in t.split("\n") if readme_pat.search(ln)]
            print(f"  {f.relative_to(ROOT)}: {len(hits)} {hits[:2]}")
    for f, t in texts.items():
        if f.suffix == ".py" or f.parent.parent.name == "knowledge":
            n = t.count("01–09, 04a") + t.count("01–09 (с 04a)")
            m = t.count("везде, кроме 10 и 11")
            print(f"  {f.relative_to(ROOT)}: «01–09, 04a» ×{n}, «везде, кроме 10 и 11» ×{m}")
    t = texts[EX / "README.md"]
    print(f"  examples/README.md: «10–21» ×{t.count('10–21')}, «кроме 10» ×{t.count('кроме 10')}")
    print("ИТОГ:", "всё легло" if bad == 0 else f"ошибок {bad}")


if __name__ == "__main__":
    main()
