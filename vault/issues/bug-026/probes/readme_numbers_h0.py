"""BUG-026 (планирование): числа README и тестов 16, 17 при заданном h0 — без правки конфигов.

Обёртка над feat-032/probes/readme_numbers.py в режиме «конфиг как есть»:
load_config подменяется так, что time.dt_after_control_change = h0, нарастание —
штатное (FEAT-032). При h0 = 2 вывод обязан совпасть с readme_numbers.py без
аргумента (конфиги 16, 17 сейчас с 2 с) — проверка обёртки.

Запуск из numerical_solver/ (P — путь к скрипту): .venv\\Scripts\\python P <h0>
"""

import sys
from pathlib import Path

PROBES_032 = Path.cwd().parent / "vault" / "issues" / "feat-032" / "probes"
sys.path.insert(0, str(PROBES_032))
import readme_numbers as rn  # noqa: E402

H0 = float(sys.argv[1])
_load = rn.load_config


def load_with_h0(path):
    cfg = _load(path)
    cfg.time.dt_after_control_change = H0
    return cfg


rn.load_config = load_with_h0
print(f"BUG-026: time.dt_after_control_change = {H0:g} с (подмена load_config)")
sys.argv = sys.argv[:1]       # readme_numbers без аргумента — без эмуляции ramp_probe.patch
rn.main()
