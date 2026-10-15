"""BUG-029: предупреждение о скине видно при загрузке конфига в свежем процессе (без caplog)."""
import json
import os
import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()  # запуск из numerical_solver/ worktree
HERE = Path(__file__).resolve().parent
base = json.loads((SOLVER / "configs" / "baseline.json").read_text(encoding="utf-8"))
# Дочерний процесс пишет stderr в UTF-8 — кириллица сообщения без порчи
env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
out = []

for s in (0.0, 2.0, 100.0):
    raw = {**base, "numerics": {**base.get("numerics", {}), "skin": s}}
    cfg = HERE / f"baseline_skin{s:g}.json"
    cfg.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    # Свежий процесс: обработчиков журнала нет (setup_logging — в фабрике),
    # запись WARNING печатает резервный обработчик logging в stderr
    code = ("import gpn_multiphase_solver as g; print(g.__file__); "
            "from gpn_multiphase_solver.io.config import load_config; "
            f"load_config(r'{cfg}')")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, encoding="utf-8", env=env, cwd=SOLVER)
    out += [f"--- skin = {s:g}: код возврата {r.returncode}",
            f"stdout: {r.stdout.strip()}",
            f"stderr: {r.stderr.strip() or '(пусто)'}"]

# Вывод — файлом в UTF-8: конвейер PowerShell 5.1 портит кириллицу
(HERE / "warn_visible.out.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"записано: {HERE / 'warn_visible.out.txt'}")
