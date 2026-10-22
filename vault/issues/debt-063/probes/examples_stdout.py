"""DEBT-063, проба: вывод всех main.py и скриптов сходимости — центры как есть и √.

Каждый скрипт запускается дважды через run_with_centers.py (base, sqrt);
stdout — в probes/stdout/<base|sqrt>/<пример>__<скрипт>.txt. Сравнение —
diff_stdout.py. Графики пишутся в examples/*/output/ (в .gitignore) —
после пробы там останутся графики варианта sqrt; перезапуск main.py
примера восстанавливает штатные.

Запуск из numerical_solver/ (варианты — двумя процессами параллельно):
    .venv\\Scripts\\python -u ..\\vault\\issues\\debt-063\\probes\\examples_stdout.py base
    .venv\\Scripts\\python -u ..\\vault\\issues\\debt-063\\probes\\examples_stdout.py sqrt
Готовый вывод (файл есть и код 0) не пересчитывается.

impl — после реализации DEBT-063 (код worktree, без подмены): вывод в
probes/stdout/impl/, сравнение с sqrt — `diff_stdout.py sqrt impl`
(ожидание: различий нет).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Вывод дочернего процесса через канал — в UTF-8, иначе кириллица и знаки
# вроде «≈» падают на кодировке консоли Windows (BUG-009)
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

SOLVER = Path.cwd()
PROBES = Path(__file__).resolve().parent
RUNNER = PROBES / "run_with_centers.py"
EX = SOLVER / "examples"

scripts = sorted(EX.glob("*/main.py")) + [
    EX / "01_single_phase_no_jt" / "spatial_convergence.py",
    EX / "02_single_phase_jt" / "check_slopes.py",
    EX / "04_table_table" / "grid_convergence.py",
    EX / "04a_high_gas_saturation" / "grid_convergence.py",
    EX / "05_standing_table_rp" / "closed_form_convergence.py",
]
modes = sys.argv[1:] or ["base", "sqrt"]
for mode in modes:
    (PROBES / "stdout" / mode).mkdir(parents=True, exist_ok=True)

for s in scripts:
    tag = f"{s.parent.name}__{s.stem}"
    for mode in modes:
        out = PROBES / "stdout" / mode / f"{tag}.txt"
        if out.exists() and "[stderr]" not in out.read_text(encoding="utf-8"):
            continue
        t0 = time.time()
        # impl — без подмены формулы, как base
        res = subprocess.run([sys.executable, str(RUNNER), str(s),
                              "base" if mode == "impl" else mode],
                             cwd=SOLVER, env=ENV, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        out.write_text(
            res.stdout + ("\n[stderr]\n" + res.stderr[-3000:] if res.returncode else ""),
            encoding="utf-8")
        print(f"{tag:55s} {mode:4s} код {res.returncode}  {time.time() - t0:7.1f} с",
              flush=True)
