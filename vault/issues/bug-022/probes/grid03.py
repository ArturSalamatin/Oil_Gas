"""BUG-022: таблица «Сходимость по сетке» README 03 (N = 25…200) — база и эмуляция плана.

Своего скрипта у таблицы нет: столбцы — строки консоли main.py 03 (example_runner).
Скрипт кладёт в копию examples_copy_<вариант>/ (run_mains.py) папки 03_N<N> с config.json
(N изменён) и main.py примера 03, запускает их через run_mains.main и разбирает консоль:
ячеек с газом, |GOR - Rs0|, Дюпюи, max|ΔS_g|, r_b, q_o, расхождение с замкнутым решением,
T(r_w). Вывод — таблица в формате README и grid03_<вариант>.out.txt.
Запуск (из numerical_solver; варианты — отдельными процессами):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\grid03.py 0
    .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\grid03.py pv1e-8
"""

import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_mains  # noqa: E402

NS = (25, 50, 100, 150, 200)
PATTERNS = {
    "gas": r"ячейки с газом \(Sg > 1e-08\) — (\d+)",
    "gor": r"\|GOR - Rs0\| = (\S+)",
    "dup": r"max\|p - Дюпюи\| = (\S+) Па",
    "dsg": r"B\. S_g из GOR=Rs0 при численном p: \d+ ячеек, max\|ΔS_g\| = (\S+)",
    "rb": r"C\. фронт: r_b = (\S+) м",
    "qo": r"q_o = \S+ м³ст/с \(аналитика\) vs (\S+) \(расчёт\), расхожд\. (\S+) %",
    "T": r"T\(r_w\) финал:\s+(\S+) К",
}


def sci(x):
    m, e = f"{float(x):.1e}".split("e")
    return f"${m}\\cdot10^{{{int(e)}}}$"


def main(variant):
    copy = HERE / f"examples_copy_{variant}"
    run_mains.COPY = copy
    run_mains.prepare_copy()
    src = copy / "03_standing_corey"
    names = []
    for n in NS:
        d = copy / f"03_N{n}"
        d.mkdir(exist_ok=True)
        shutil.copy(src / "main.py", d / "main.py")
        cfg = json.loads((src / "config.json").read_text(encoding="utf-8"))
        cfg["grid"]["N"] = n
        (d / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        names.append(d.name)
    run_mains.main(variant, names)
    lines = [f"вариант {variant}: таблица «Сходимость по сетке» README 03",
             "| $N$ | ячеек в 2ф зоне | $|{\\rm GOR}-R_{s,0}|$ | Дюпюи, Па | max$|\\Delta S_g|$ | $r_b$, м | $q_o$, м³ст/с | $q_o$ vs замкн. реш. | $T(r_w)$, К |"]
    for n, name in zip(NS, names):
        text = (HERE / f"mains_{variant}" / f"{name}.txt").read_text(encoding="utf-8")
        v = {}
        for k, p in PATTERNS.items():
            m = re.search(p, text)
            v[k] = m.groups() if m else ("?",)
        qo, qpct = v["qo"] if len(v["qo"]) == 2 else ("?", "?")
        lines.append(f"| {n} | {v['gas'][0]} | {sci(v['gor'][0])} | {sci(v['dup'][0])} | {sci(v['dsg'][0])} | "
                     f"{float(v['rb'][0]):.5f} | {sci(qo).replace('.1', '.1')} ({qo}) | {float(qpct):.3f} % | {v['T'][0]} |")
    text = "\n".join(lines)
    print(text)
    (HERE / f"grid03_{variant}.out.txt").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
