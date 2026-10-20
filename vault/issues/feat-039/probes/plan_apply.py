"""FEAT-039 (аудит плана): наложить правки плана на копию дерева базы.

Копия – tree/numerical_solver (git archive 74c002e; в git не входит, удаляется после
аудита). Блоки «До/После» кода шагов 1, 2, 4, тесты шагов 2 и 3, строка README и
запись CHANGELOG шага 4 берутся из файла плана разбором fenced-блоков; короткие
правки в тексте (README, тесты примеров) – дословно из плана. Каждая «старая»
строка обязана встретиться в файле копии ровно один раз.

Запуск: <PY> plan_apply.py  (из любого каталога)
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PLAN = ROOT / "vault" / "plans" / "feat-039 ramp-on-production-start.md"
T = HERE / "tree" / "numerical_solver"

text = PLAN.read_text(encoding="utf-8")
steps = {int(m.group(1)): m.start() for m in re.finditer(r"^### Шаг (\d+):", text, re.M)}
order = sorted(steps)
bounds = {n: (steps[n], steps[order[i + 1]] if i + 1 < len(order) else len(text))
          for i, n in enumerate(order)}


def step(n):
    a, b = bounds[n]
    return text[a:b]


def fences(s):
    """Fenced-блоки шага по порядку: (строка перед блоком, содержимое)."""
    out = []
    for m in re.finditer(r"^( *)```[a-z]*\n(.*?)^\1```", s, re.M | re.S):
        before = s[:m.start()].rstrip("\n").splitlines()[-1] if s[:m.start()].strip() else ""
        body = m.group(2)
        ind = m.group(1)
        if ind:
            body = "\n".join(l[len(ind):] if l.startswith(ind) else l for l in body.splitlines()) + "\n"
        out.append((before, body))
    return out


def pairs(s):
    """Пары «До:/После:» из fenced-блоков шага."""
    fs = fences(s)
    res = []
    for i, (lab, body) in enumerate(fs):
        if lab.strip().startswith("До") and i + 1 < len(fs) and fs[i + 1][0].strip().startswith("После"):
            res.append((body, fs[i + 1][1]))
    return res


EDITS = []


def edit(rel, old, new):
    EDITS.append((rel, old, new))


# ── Шаг 1: test_val004 ──
(p1,) = pairs(step(1))
edit("tests/test_val004.py", p1[0], p1[1])

# ── Шаг 2: simulator.py (а) – строкой, (б)–(д) – блоками ──
s2 = step(2)
(f2a,) = [b for lab, b in fences(s2) if b.startswith("    Первый шаг интервала со сменой управления и первого")]
edit("gpn_multiphase_solver/simulator.py",
     "    Первый шаг интервала со сменой управления начинается с подшага dt/2**m (FEAT-032).",
     f2a.rstrip("\n"))
p2 = pairs(s2)
assert len(p2) == 5, len(p2)      # (б)–(е)
for old, new in p2:
    edit("gpn_multiphase_solver/simulator.py", old.rstrip("\n"), new.rstrip("\n"))
# Тест журнала (аудит, п. 4 тестов шага 2): import logging и тест после test_h0_not_less_than_step_keeps_path
(flog,) = [b for lab, b in fences(s2) if "test_log_names_start_and_change" in b]
edit("tests/test_simulator.py", "from dataclasses import replace\n",
     "import logging\nfrom dataclasses import replace\n")
edit("tests/test_simulator.py",
     "        assert hydro.dt_calls == [3600.0, 3600.0]\n"
     "        assert energy.dt_calls == [3600.0, 3600.0]\n",
     "        assert hydro.dt_calls == [3600.0, 3600.0]\n"
     "        assert energy.dt_calls == [3600.0, 3600.0]\n\n" + flog)

# Тесты шага 2: блоки 1 и 2 – из плана
f2 = [b for lab, b in fences(s2) if "test_off_by_default" in b or "test_first_interval_is_a_change" in b]
assert len(f2) == 2, len(f2)
edit("tests/test_simulator.py",
     '    def test_off_by_default(self):\n'
     '        """Без dt_after_control_change — 0 на любом интервале: путь исполнения прежний."""\n'
     '        s = _schedule([PressureControl(15e6), PressureControl(10e6)])\n'
     '        assert s.first_substep_depth(1) == 0\n',
     f2[0])
edit("tests/test_simulator.py",
     '    def test_first_interval_not_a_change(self):\n'
     '        """Интервал 0 — не смена (решение пользователя 2026-10-11; причина — BUG-028, исправлен)."""\n'
     '        s = _schedule([PressureControl(15e6), PressureControl(10e6)], h0=2.0)\n'
     '        assert s.first_substep_depth(0) == 0\n',
     f2[1])
# Тесты шага 2, п. 3 – ожидания (дословно из плана)
edit("tests/test_simulator.py",
     "        2048 — конец. Первый интервал — не смена: один шаг 3600 с.\n"
     "        \"\"\"\n"
     "        sim, hydro, energy = _ramp_run([15e6, 10e6], h0=900.0)\n"
     "        sim.run(_initial_state())\n"
     "        assert hydro.dt_calls == [3600.0, 900.0, 900.0, 1800.0]\n"
     "        assert energy.dt_calls == [3600.0, 900.0, 900.0, 1800.0]\n",
     "        2048 – конец. Первый интервал – пуск, тоже от 900 с (FEAT-039).\n"
     "        \"\"\"\n"
     "        sim, hydro, energy = _ramp_run([15e6, 10e6], h0=900.0)\n"
     "        sim.run(_initial_state())\n"
     "        assert hydro.dt_calls == [900.0, 900.0, 1800.0, 900.0, 900.0, 1800.0]\n"
     "        assert energy.dt_calls == [900.0, 900.0, 1800.0, 900.0, 900.0, 1800.0]\n")
edit("tests/test_simulator.py",
     '        """То же p_wf в соседних интервалах (разные объекты) — оба шага полные."""\n'
     "        sim, hydro, _ = _ramp_run([15e6, 15e6], h0=900.0)\n"
     "        sim.run(_initial_state())\n"
     "        assert hydro.dt_calls == [3600.0, 3600.0]\n",
     '        """То же p_wf в соседних интервалах (разные объекты) – второй шаг полный; первый – пуск, нарастает."""\n'
     "        sim, hydro, _ = _ramp_run([15e6, 15e6], h0=900.0)\n"
     "        sim.run(_initial_state())\n"
     "        assert hydro.dt_calls == [900.0, 900.0, 1800.0, 3600.0]\n")
edit("tests/test_simulator.py",
     "        assert hydro.dt_calls == [3600.0, 900.0, 900.0, 1800.0, 3600.0]\n",
     "        assert hydro.dt_calls == [900.0, 900.0, 1800.0, 900.0, 900.0, 1800.0, 3600.0]\n")
edit("tests/test_simulator.py",
     "        assert hydro.dt_calls == [3600.0, 900.0, 450.0, 450.0, 900.0, 1800.0]\n"
     "        assert energy.dt_calls == [3600.0, 450.0, 450.0, 900.0, 1800.0]\n",
     "        assert hydro.dt_calls == [900.0, 900.0, 1800.0, 900.0, 450.0, 450.0, 900.0, 1800.0]\n"
     "        assert energy.dt_calls == [900.0, 900.0, 1800.0, 450.0, 450.0, 900.0, 1800.0]\n")
edit("tests/test_simulator.py",
     "        assert hydro.dt_calls == [3600.0, 900.0, 450.0, 225.0]\n"
     "        assert energy.dt_calls == [3600.0]\n",
     "        assert hydro.dt_calls == [900.0, 900.0, 1800.0, 900.0, 450.0, 225.0]\n"
     "        assert energy.dt_calls == [900.0, 900.0, 1800.0]\n")

# ── Шаг 3: блок в конец test_dt_convergence.py ──
(f3,) = [b for lab, b in fences(step(3)) if "TestRampOnProductionStart" in b]
APPEND = [("tests/test_dt_convergence.py", "\n\n" + f3)]

# ── Шаг 4 ──
s4 = step(4)
p4 = pairs(s4)
assert len(p4) == 4, len(p4)
for rel, (old, new) in zip(("gpn_multiphase_solver/io/config.py",
                            "gpn_multiphase_solver/io/config.py",
                            "gpn_multiphase_solver/io/workbook_format.py",
                            "gpn_multiphase_solver/io/workbook_template.py"), p4):
    edit(rel, old.rstrip("\n"), new.rstrip("\n"))
edit("gpn_multiphase_solver/__init__.py",
     "отказ с сообщением. После смены\nрежима скважины подшаг может начинаться с",
     "отказ с сообщением. После пуска и\nсмены режима скважины подшаг может начинаться с")
edit("README.md", "нарастающий шаг после смены режима);", "нарастающий шаг после пуска и смены режима);")
(row,) = [b for lab, b in fences(s4) if b.startswith("| | `dt_after_control_change`")]
old_row = [l for l in (T / "README.md").read_text(encoding="utf-8").splitlines()
           if l.startswith("| | `dt_after_control_change`")]
assert len(old_row) == 1
edit("README.md", old_row[0], row.rstrip("\n"))
edit("README.md",
     "или увеличить `numerics.max_retries`; при резкой смене режима работы\n"
     "скважины — задать `time.dt_after_control_change` (в примерах останова 16 и\n"
     "17 — 0,11 с).",
     "или увеличить `numerics.max_retries`; на пуске и при резкой смене режима\n"
     "работы скважины – задать `time.dt_after_control_change` (в примерах 16 и\n"
     "17 – 0,11 с).")
(cl,) = [b for lab, b in fences(s4) if b.startswith("### Изменено")]
edit("CHANGELOG.md", "## Не выпущено\n\n", "## Не выпущено\n\n" + cl + "\n")

# ── Шаг 6: README 16, тесты 16 ──
R16 = "examples/16_well_shut_in/README.md"
edit(R16, "| первый подшаг после смены управления | `time.dt_after_control_change = 0.11` с: первый час останова — от 0.11 с с удвоением |",
     "| первый подшаг после пуска и смены управления | `time.dt_after_control_change = 0.11` с: первый час добычи и первый час останова – от 0.11 с с удвоением |")
for old, new in (
        ("| 1 | 1 | $3.237\\cdot10^{-3}$ | 6.1309 | 349.6759 |", "| 1 | 1 | $3.236\\cdot10^{-3}$ | 6.1309 | 349.6779 |"),
        ("| 6.1242 | 350.3507 |", "| 6.1242 | 350.3513 |"),
        ("| 13.0240 | **350.6756** |", "| 13.0242 | **350.6762** |"),
        ("| 13.4780 | 350.6668 |", "| 13.4782 | 350.6674 |"),
        ("| 14.4766 | 350.6366 |", "| 14.4769 | 350.6372 |"),
        ("| **15.0324** | 350.6234 |", "| **15.0326** | 350.6240 |"),
        ("| 15.4206 | 350.5836 |", "| 15.4207 | 350.5842 |"),
        ("| 15.5000 | 350.4298 |", "| 15.5000 | 350.4303 |"),
        ("| 15.5000 | 350.3169 |", "| 15.5000 | 350.3174 |"),
        ("подшаг вдвое длиннее, до 1800 с (16 подшагов). Остальные шаги — 3600 с.",
         "подшаг вдвое длиннее, до 1800 с (16 подшагов). Так же начинается первый час добычи: "
         "пуск из равновесия – такая же резкая смена режима. Остальные шаги – 3600 с."),
        ("| газ | $-84155$ | $220642$ | $136487$ | $3.5\\cdot10^{-9}$ |",
         "| газ | $-84160$ | $220647$ | $136488$ | $3.5\\cdot10^{-9}$ |"),
        ("Rs: 5.0847 … 30.0000", "Rs: 5.0845 … 30.0000"),
        ("первый час останова начинается с\n", "первые часы добычи и останова начинаются с\n"),
        ("`null` — первый час одним шагом;", "`null` – оба часа одним шагом;")):
    edit(R16, old, new)
TE = "tests/test_examples.py"
for old, new in (
        ("    (vault/issues/bug-026/probes/readme_numbers_h011.out.txt).\n    \"\"\"\n\n    NAME = \"16_well_shut_in\"",
         "    (vault/issues/bug-026/probes/readme_numbers_h011.out.txt). Первый час добычи – тоже от\n"
         "    0.11 с (FEAT-039); числа – замер плана FEAT-039\n"
         "    (vault/issues/feat-039/probes/readme_numbers_039.emul.out.txt).\n    \"\"\"\n\n    NAME = \"16_well_shut_in\""),
        ("13.024 (1 ч) → 15.0324 (запись 27,", "13.0242 (1 ч) → 15.0326 (запись 27,"),
        ("→ 15.4206 (16 сут)", "→ 15.4207 (16 сут)"),
        ("финал R_s(r_w) = 5.085,", "финал R_s(r_w) = 5.0845,"),
        ("pytest.approx(5.085, abs=1e-3)", "pytest.approx(5.0845, abs=1e-3)"),
        ("Замер (план BUG-026, первый час —\n        от подшага 0.11 с с удвоением): 350.3507 (15 сут) → 350.6756 (запись 16,\n        максимум) → 350.3169 К (30 сут).",
         "Замер (план FEAT-039, первые часы\n        добычи и останова – от подшага 0.11 с с удвоением): 350.3513 (15 сут) →\n        350.6762 (запись 16, максимум) → 350.3174 К (30 сут)."),
        ("pytest.approx(350.6756, abs=2e-4)", "pytest.approx(350.6762, abs=2e-4)"),
        ("pytest.approx(350.3169, abs=2e-4)", "pytest.approx(350.3174, abs=2e-4)"),
        ("0.048261 (запись 1)", "0.048267 (запись 1)"),
        ("pytest.approx(0.048261, rel=1e-4)", "pytest.approx(0.048267, rel=1e-4)")):
    edit(TE, old, new)

# ── Шаг 7: README 17, тесты 17 ──
R17 = "examples/17_shut_in_strong_cooling/README.md"
for old, new in (
        ("| первый подшаг после смены управления | `time.dt_after_control_change = 0.11` с | `time` |",
         "| первый подшаг после пуска и смены управления | `time.dt_after_control_change = 0.11` с | `time` |"),
        ("| 1 | 1 | $3.814\\cdot10^{-3}$ | 5.1726 | 366.3168 | 0.4433 |", "| 1 | 1 | $3.815\\cdot10^{-3}$ | 5.1726 | 366.3664 | 0.4432 |"),
        ("| 5.1545 | 365.0166 |", "| 5.1545 | 365.0162 |"),
        ("| 25.4409 | 369.2612 |", "| 25.4408 | 369.2608 |"),
        ("| 26.8595 | 370.0604 |", "| 26.8594 | 370.0600 |"),
        ("| **30.4251** | 372.6755 |", "| **30.4251** | 372.6750 |"),
        ("| 31.6346 | 373.7366 |", "| 31.6346 | 373.7362 |"),
        ("| 32.9704 | 376.0234 |", "| 32.9704 | 376.0230 |"),
        ("| 33.0000 | 377.3500 |", "| 33.0000 | 377.3497 |"),
        ("| нефть | $-339.6$ | $4522.6$ | $4183.0$ | $1.8\\cdot10^{-11}$ |", "| нефть | $-339.6$ | $4522.7$ | $4183.1$ | $2.0\\cdot10^{-11}$ |"),
        ("$1.255\\cdot10^{6}$ | $6.5\\cdot10^{-11}$ |", "$1.255\\cdot10^{6}$ | $7.9\\cdot10^{-11}$ |"),
        ("Rs: 88.5826 … 332.4101", "Rs: 88.5831 … 332.4101"),
        ("схема первого порядка по времени. Третий час останова и четыре часа на",
         "схема первого порядка по времени. Так же начинается первый час добычи – пуск из равновесия. Третий час останова и шесть часов на"),
        ("за ~6 с вместо ~25 с", "за ~7 с вместо ~25 с"),
        ("377.283 К вместо 377.350 К", "377.323 К вместо 377.350 К"),
        ("первый подшаг после останова", "первый подшаг после пуска и останова"),
        ("`null` — первый час одним\n  шагом,", "`null` – первые часы добычи и останова одним\n  шагом,")):
    edit(R17, old, new)
for old, new in (
        ("    (vault/issues/bug-026/probes/readme_numbers_h011.out.txt).\n    \"\"\"\n\n    NAME = \"17_shut_in_strong_cooling\"",
         "    (vault/issues/bug-026/probes/readme_numbers_h011.out.txt). Первый час добычи – тоже от\n"
         "    0.11 с (FEAT-039); числа – замер плана FEAT-039\n"
         "    (vault/issues/feat-039/probes/readme_numbers_039.emul.out.txt).\n    \"\"\"\n\n    NAME = \"17_shut_in_strong_cooling\""),
        ("T(r_w) = 365.0166 К (ΔT = -14.983 К), q_o = 3.33438e-3", "T(r_w) = 365.0162 К (ΔT = -14.984 К), q_o = 3.33434e-3"),
        ("pytest.approx(365.0166, abs=2e-3)", "pytest.approx(365.0162, abs=2e-3)"),
        ("pytest.approx(3.33438e-3, rel=1e-4)", "pytest.approx(3.33434e-3, rel=1e-4)"),
        ("5.1545 МПа (15 сут) -> 25.4409 (1 ч)", "5.1545 МПа (15 сут) -> 25.4408 (1 ч)"),
        ("не хватает 31.3 кПа", "не хватает 31.4 кПа"),
        ("pytest.approx(25.4409e6, rel=1e-4)", "pytest.approx(25.4408e6, rel=1e-4)"),
        ("# BUG-026: 88.5826 — первый час останова от подшага 0.11 с", "# BUG-026: 88.5831 – первый час останова от подшага 0.11 с"),
        ("pytest.approx(88.5826, abs=1e-3)", "pytest.approx(88.5831, abs=1e-3)"),
        ("Замер: 365.0166 (15 сут) -> 369.2612\n        (1 ч) -> 373.7366 (16 сут) -> 377.3500 К (30 сут)",
         "Замер: 365.0162 (15 сут) -> 369.2608\n        (1 ч) -> 373.7362 (16 сут) -> 377.3497 К (30 сут)"),
        ("Первый час — 16 подшагов от 0.11 с\n        с удвоением (FEAT-032, BUG-026); третий час останова и четыре часа на",
         "Первый час останова – 16 подшагов от\n        0.11 с с удвоением (FEAT-032, BUG-026), первый час добычи – тоже (FEAT-039);\n        третий час останова и шесть часов на"),
        ("pytest.approx(369.2612, abs=2e-3)", "pytest.approx(369.2608, abs=2e-3)"),
        ("pytest.approx(373.7366, abs=2e-3)", "pytest.approx(373.7362, abs=2e-3)"),
        ("pytest.approx(377.3500, abs=2e-3)", "pytest.approx(377.3497, abs=2e-3)")):
    edit(TE, old, new)

# ── Шаг 8: README 22, обзор примеров ──
R22 = "examples/22_workbook_input/README.md"
for old, new in (
        ("Интервал делится на подшаги не длиннее $\\Delta t$; после смены режима\n"
         "первый подшаг — $h_0$, округлённый вниз до подшага/$2^m$ (в журнале\n"
         "расчёта: «первый шаг от 0.0781 с»), дальше подшаг удваивается.",
         "Интервал делится на подшаги не длиннее $\\Delta t$; на пуске и после смены\n"
         "режима первый подшаг – $h_0$, округлённый вниз до подшага/$2^m$ (в журнале\n"
         "расчёта: «первый шаг от 0.0586 с (пуск)», «первый шаг от 0.0781 с (смена\n"
         "управления)»), дальше подшаг удваивается."),
        ("| 1 мин | 150 | 10.67 | 45.1 | −0.267 |", "| 1 мин | 150 | 8.212 | 45.5 | −0.252 |"),
        ("забой охлаждается: на 0.27 К в первую минуту", "забой охлаждается: на 0.25 К в первую минуту"),
        ("невязка $5.5\\cdot10^{-15}$", "невязка $6.4\\cdot10^{-15}$")):
    edit(R22, old, new)
RX = "examples/README.md"
for old, new in (
        ("В 16 и 17 первый час останова считается нарастающими подшагами от 0.11 с\n"
         "(`time.dt_after_control_change` = 0.11 с): газосодержание у забоя задаёт начало останова.",
         "В 16 и 17 первые часы добычи и останова считаются нарастающими подшагами от 0.11 с\n"
         "(`time.dt_after_control_change` = 0.11 с): газосодержание у забоя задаёт начало останова,\n"
         "а пуск – такая же резкая смена режима."),
        ("| **16** | **1.5 / 0.14 / 0.04** | $4.4\\cdot10^{-15}$ |", "| **16** | **1.5 / 0.14 / 0.04** | $9.2\\cdot10^{-15}$ |"),
        ("| **17** | **2.5 / 0.13 / 0.05** | $2.5\\cdot10^{-15}$ |", "| **17** | **2.5 / 0.13 / 0.05** | $3.7\\cdot10^{-15}$ |"),
        ("| **22** | **2.5 / 0.13 / 0.05** | $5.5\\cdot10^{-15}$ |", "| **22** | **2.5 / 0.13 / 0.05** | $6.4\\cdot10^{-15}$ |")):
    edit(RX, old, new)

# ── Шаг 9: комментарии test_energy_matrix_examples ──
TM = "tests/test_energy_matrix_examples.py"
edit(TM, "# на итерациях). Первый час останова — подшаги нарастания от 0.11 с\n"
         "# (FEAT-032, BUG-026): это не дробление, отказов в нём нет.",
     "# на итерациях). Первые часы добычи и останова – подшаги нарастания от\n"
     "# 0.11 с (FEAT-032, BUG-026, FEAT-039): это не дробление, отказов в них нет.")
edit(TM, "# гидродинамики), решаются целиком. После FEAT-032 и BUG-026 первый час —\n"
         "# нарастание от 0.11 с; третий час и четыре часа на 20.4–20.8 сут дробятся на\n"
         "# 2 × 1800 с (по одному отказу гидродинамики).",
     "# гидродинамики), решаются целиком. Первые часы добычи и останова –\n"
     "# нарастание от 0.11 с (FEAT-032, BUG-026, FEAT-039); третий час останова и\n"
     "# шесть часов на 20.4–20.8 сут дробятся на 2 × 1800 с (по одному отказу\n"
     "# гидродинамики; vault/issues/feat-039/probes/fails_17.out.txt).")

# ── Шаг 10: vault – только проверка «старых» строк в основном каталоге ──
VAULT = [
    (ROOT / "vault/knowledge/decisions/P4-адаптивный-шаг.md",
     "- первый интервал расчёта сменой не считается: мелкий первый шаг добычи из равновесия в примерах 19 и 21 не сходится ([[BUG-028]]);"),
    (next((ROOT / "vault/knowledge/decisions").glob("нарастающий шаг после смены управления*.md")),
     "- Первый интервал расчёта сменой управления не считается."),
    (ROOT / "vault/knowledge/decisions/json-config-schema.md",
     "Первый подшаг после смены управления скважиной (FEAT-032);"),
    (ROOT / "vault/knowledge/decisions/временная-сетка-и-история.md",
     "— первый подшаг после смены управления скважиной, с ([[FEAT-032]]);"),
]


def main():
    bad = 0
    for rel, old, new in EDITS:
        p = T / rel
        s = p.read_text(encoding="utf-8")
        n = s.count(old)
        if n != 1:
            bad += 1
            print(f"НЕ ЛЕГЛО ({n} вхождений): {rel}: {old[:90]!r}", flush=True)
            continue
        # newline="\n": копия из git archive – с LF; без этого Windows пишет CRLF
        p.write_text(s.replace(old, new), encoding="utf-8", newline="\n")
    for rel, block in APPEND:
        p = T / rel
        p.write_text(p.read_text(encoding="utf-8").rstrip("\n") + block, encoding="utf-8",
                     newline="\n")
    for path, old in VAULT:
        n = path.read_text(encoding="utf-8").count(old)
        if n != 1:
            bad += 1
            print(f"НЕ ЛЕГЛО ({n}): {path.name}: {old[:90]!r}", flush=True)
    print(f"правок {len(EDITS)} + дописано {len(APPEND)} + vault {len(VAULT)}; не легло {bad}", flush=True)
    return bad


if __name__ == "__main__":
    sys.exit(main())
