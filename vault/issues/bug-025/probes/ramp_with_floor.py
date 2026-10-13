"""BUG-025 (аудит 1): сценарии планирования FEAT-032 с пределом округления в допуске — добыча, грубая сетка.

План FEAT-032 нашёл предел округления BUG-025 на добыче: с нарастающим шагом после смены управления
(h0 = 0.44 с) примеры 15 и 13b (N = 50, внешняя ячейка в ~6 раз крупнее, чем при N = 350)
падают — «невязка 1.26e-11 (допуск 1.03e-11) … не выполнено только абсолютное условие».
Скрипт подставляет допуск с пределом округления (floor_probe.patch, та же арифметика, что шаг 3 плана
BUG-025) и запускает пробу FEAT-032 vault/issues/feat-032/probes/ramp_probe.py как есть.

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P KAPPA <аргументы ramp_probe.py>
KAPPA = 0 — без подмены. Пример: P 4 example 15_oil_rate_ramp_up 0 0.44
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fp = _load("floor_probe", HERE / "floor_probe.py")
kappa = float(sys.argv[1])
if kappa > 0:
    fp.patch(kappa)
print(f"предел округления в допуске: kappa = {sys.argv[1]}" + (" (без подмены)" if kappa == 0 else ""), flush=True)
rp = _load("ramp_probe", HERE.parent.parent / "feat-032" / "probes" / "ramp_probe.py")
sys.argv = [sys.argv[0]] + sys.argv[2:]
rp.main()
