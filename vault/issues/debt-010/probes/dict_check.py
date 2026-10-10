"""Аудит DEBT-010, шаг 5: строки словаря и новый текст разделов 5–6 против кода и .tex.

Запуск из numerical_solver/:  .venv\\Scripts\\python ..\\vault\\issues\\debt-010\\probes\\dict_check.py
"""
import re
from pathlib import Path

SOLVER = Path.cwd()
ROOT = SOLVER.parent
PLAN = (ROOT / "vault" / "plans" / "debt-010 docstring-eq-labels.md").read_text(encoding="utf-8")
DICT = (ROOT / "vault" / "knowledge" / "decisions" / "словарь-код-физика.md").read_text(encoding="utf-8")
TEX = (SOLVER / "doc" / "problem_statement.tex").read_text(encoding="utf-8")
TRI = (SOLVER / "gpn_multiphase_solver" / "energy" / "tridiag.py").read_text(encoding="utf-8")
labels = set(re.findall(r"\\label\{(eq:[A-Za-z0-9_]+)\}", TEX))
dlines = DICT.splitlines()

# ── 5.1: «было» на заявленной строке словаря, «стало» — существующие метки ──
s51 = PLAN[PLAN.index("5.1. **Номера → метки"):PLAN.index("5.2. **Разделы 5 и 6")]
for line in s51.splitlines():
    cells = [c.strip() for c in line.split("|")[1:-1]]
    if len(cells) != 4 or not cells[0].isdigit():
        continue
    n, what, was, now = cells
    text = dlines[int(n) - 1]
    ok_was = all(tok.strip() in text for tok in re.split(r",\s*|\s+\(режим \d\)", was) if tok.strip()
                 and tok.strip().startswith(("eq.", "§", "из eq.")))
    ok_what = re.sub(r"[`«»]", "", what).split(" ")[0].strip() in text.replace("`", "")
    bad = [l for l in re.findall(r"eq:[A-Za-z0-9_]+", now) if l not in labels]
    flag = "OK " if ok_was and ok_what and not bad else "✗  "
    print(f"{flag}{n}: {what} | {was} → {now[:50]}" + (f"  нет меток {bad}" if bad else "")
          + ("" if ok_was else "  «было» не найдено") + ("" if ok_what else "  объект не найден"))

# ── 5.2: новый текст разделов 5–6 ──
s52 = PLAN[PLAN.index("5.2. **Разделы 5 и 6"):PLAN.index("5.3. После заголовка")]
new = s52[s52.index("````markdown"):s52.rindex("````")]
miss = sorted({l for l in re.findall(r"eq:[A-Za-z0-9_]+", new) if l not in labels})
print("метки нового текста:", len(set(re.findall(r"eq:[A-Za-z0-9_]+", new))), "отсутствуют:", miss)
idents = ["Phi_plus", "Phi_minus", "Phi_o", "Phi_g", "Q_T_internal", "Q_T_ext", "J_jt", "Q_ad",
          "Q_deg", "mdot", "R_adv", "cap", "mu_o_face", "mu_g_face", "assemble_tridiag",
          "compute_cell_properties", "compute_convective_coefficients",
          "compute_conductive_transmissibility", "compute_jt", "compute_adiabatic",
          "compute_degassing", "'rho_cp_eff'", "'lambda_eff'", "TridiagEnergySolver"]
print("идентификаторы, которых нет в tridiag.py:", [i for i in idents if i not in TRI])
# Границы заменяемого блока в словаре
i5 = next(i for i, l in enumerate(dlines, 1) if l.startswith("## 5. Уравнение энергии"))
i7 = next(i for i, l in enumerate(dlines, 1) if l.startswith("## 7. PVT-функции"))
print(f"заменяемый блок словаря: строки {i5}–{i7 - 1}")
left = [f"{i}: {l.strip()[:60]}" for i, l in enumerate(dlines, 1)
        if re.search(r"\beq\.\s*\d|§\s*\d", l) and not (i5 <= i < i7)]
listed = {int(c.split("|")[1]) for c in s51.splitlines() if re.match(r"\|\s*\d+\s*\|", c)}
print("номера/§ вне 5–6, не попавшие в таблицу 5.1:",
      [x for x in left if int(x.split(":")[0]) not in listed])
