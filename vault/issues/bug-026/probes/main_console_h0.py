"""BUG-026 (планирование): консоль команды run для примера при заданном h0 — без правки конфига.

После FEAT-030 main.py примера — обёртка `python -m gpn_multiphase_solver run
<пример>/config.json`. Проба вызывает ту же команду (cli.main) с подменой
report.pipeline.load_config (time.dt_after_control_change = h0) и каталогом вывода
main_out/<пример>_h<h0> рядом с пробой (не output/ примера; удалить после разбора —
в нём CSV). Консольные блоки README (баланс массы, проверка R_s, баланс энергии) — отсюда.

Запуск из numerical_solver/ (P — путь к скрипту): .venv\\Scripts\\python P <пример> <h0>
"""

import sys
from pathlib import Path

SOLVER_ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOLVER_ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.cli import main  # noqa: E402
from gpn_multiphase_solver.report import pipeline  # noqa: E402

NAME, H0 = sys.argv[1], float(sys.argv[2])
_load = pipeline.load_config


def load_with_h0(path):
    cfg = _load(path)
    cfg.time.dt_after_control_change = H0
    return cfg


pipeline.load_config = load_with_h0
print(f"BUG-026: {NAME}, time.dt_after_control_change = {H0:g} с (подмена load_config); "
      f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
out = HERE / "main_out" / f"{NAME}_h{H0:g}"
sys.exit(main(["run", str(SOLVER_ROOT / "examples" / NAME / "config.json"), "--output", str(out)]))
