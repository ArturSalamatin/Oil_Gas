"""BUG-022: таблицы «Сходимость невязки» README 01–05 — energy_balance_convergence.py на базе и плане.

Общий модуль examples/energy_balance_convergence.py прогоняет пример при трёх шагах
по времени (3600 / 900 / 360 с) и печатает max и final относительной невязки баланса
энергии. Запуск на копии examples_copy_<вариант>/ (run_mains.py), эмуляция плана — как
в run_mains.install_emulation. Вывод: mains_<вариант>/conv_<пример>.txt и
conv_energy_<вариант>.out.txt (строки «пример: final rel при 3600 / 900 / 360»).
Запуск (из numerical_solver; варианты — отдельными процессами):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\conv_energy.py 0 01 02 03 04 05
    .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\conv_energy.py pv1e-8 01 02 03 04 05
"""

import contextlib
import io
import re
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_mains  # noqa: E402


def main(variant, names):
    run_mains.COPY = HERE / f"examples_copy_{variant}"
    run_mains.prepare_copy()
    run_mains.install_emulation(variant)
    out_dir = HERE / f"mains_{variant}"
    out_dir.mkdir(exist_ok=True)
    lines = [f"вариант {variant}: energy_balance_convergence, final rel при dt = 3600 / 900 / 360 с (max rel)"]
    for name in names:
        buf = io.StringIO()
        sys.argv = ["energy_balance_convergence.py", name]
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                runpy.run_path(str(run_mains.COPY / "energy_balance_convergence.py"), run_name="__main__")
            except SystemExit:
                pass
        text = buf.getvalue()
        (out_dir / f"conv_{name}.txt").write_text(text, encoding="utf-8")
        rows = re.findall(r"max rel = (\S+), final rel = (\S+)", text)
        lines.append(f"{name}: " + " / ".join(f"{f} ({m})" for m, f in rows))
        print(lines[-1], flush=True)
    (HERE / f"conv_energy_{variant}.out.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
