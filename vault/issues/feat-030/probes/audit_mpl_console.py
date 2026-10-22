"""Аудит FEAT-030: допущения плана о matplotlib и консоли (шаги 2, 6; тесты 12, 13 test_cli).

Проверяет на версии matplotlib общего venv:
  1. импорт pyplot не выбирает режим (backend) — его выбирает первая фигура;
  2. matplotlib.use(...) после импорта pyplot переключает режим;
  3. в каком регистре get_backend() возвращает имя ("Agg" или "agg");
  4. режим, заданный до импорта модулей пакета, они не меняют (ядро — io/output,
     factory, diagnostics; модулей report/ ещё нет);
  5. PYTHONIOENCODING=cp1251 → sys.stdout.encoding, и reconfigure меняет его на utf-8.

Каждая проверка — отдельный процесс: режим matplotlib глобален для процесса.
Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-030\\probes\\audit_mpl_console.py
"""

import os
import subprocess
import sys

CASES = {
    "pyplot_import_keeps_backend_unset": (
        "import matplotlib; import matplotlib.pyplot as plt; "
        "print(matplotlib.rcParams._get_backend_or_none())"),
    "use_after_pyplot_import": (
        "import matplotlib.pyplot as plt, matplotlib; matplotlib.use('Agg'); "
        "fig = plt.figure(); print(matplotlib.get_backend(), type(fig.canvas).__name__)"),
    "svg_kept_after_package_import": (
        "import matplotlib; matplotlib.use('svg'); import matplotlib.pyplot; "
        "import gpn_multiphase_solver.io.output, gpn_multiphase_solver.factory, "
        "gpn_multiphase_solver.diagnostics.closed_form, gpn_multiphase_solver.energy.balance; "
        "print(matplotlib.get_backend())"),
    "stdout_cp1251_then_reconfigure": (
        "import sys; a = sys.stdout.encoding; "
        "sys.stdout.reconfigure(encoding='utf-8', errors='replace'); "
        "print(a, sys.stdout.encoding)"),
}

for name, code in CASES.items():
    env = dict(os.environ, PYTHONIOENCODING="cp1251", MPLBACKEND="")
    env.pop("MPLBACKEND")
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       env=env, encoding="cp1251", errors="replace")
    out = (p.stdout.strip() or p.stderr.strip().splitlines()[-1:] or ["—"])
    print(f"{name}: код {p.returncode}: {out if isinstance(out, str) else out[0]}")
