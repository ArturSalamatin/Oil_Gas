"""BUG-026 (планирование): два быстрых теста на конфиге примера 16 — при h0 = 0.11 с.

test_energy_balance_examples.py::test_stepped_schedule_matches_uniform_across_shut_in и
test_mass_balance.py::test_mass_balance_through_shut_in берут конфиг примера 16 целиком,
вместе с time.dt_after_control_change. Проба вызывает сами тестовые функции, подменив
у их модулей json.loads: в словарь конфига дописывается h0 (как будет в конфиге после
шага 3). Первый интервал останова 300 с → подшаг 300/2**12 = 0.073 с.
Временные конфиги — в tmp_n25/ рядом с пробой (удаляется в конце).

Запуск из numerical_solver/ (P — путь к скрипту): .venv\\Scripts\\python P <h0>
"""

import json
import shutil
import sys
from pathlib import Path

SOLVER_ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOLVER_ROOT))      # tests — пакет (относительные импорты)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
import tests.test_energy_balance_examples as teb  # noqa: E402
import tests.test_mass_balance as tmb  # noqa: E402

H0 = float(sys.argv[1])


class _Json:
    """Модуль json с подменённым loads: h0 в секции time конфига."""

    dumps = staticmethod(json.dumps)

    @staticmethod
    def loads(s, *args, **kwargs):
        d = json.loads(s, *args, **kwargs)
        if isinstance(d, dict) and "time" in d:
            d["time"]["dt_after_control_change"] = H0
        return d


teb.json = tmb.json = _Json
print(f"код: {Path(gpn_multiphase_solver.__file__).parent}; h0 = {H0:g} с", flush=True)
tmp = HERE / "tmp_n25"
for name, fn in (("energy across shut-in", teb.test_stepped_schedule_matches_uniform_across_shut_in),
                 ("mass through shut-in", tmb.test_mass_balance_through_shut_in)):
    d = tmp / name.split()[0]
    d.mkdir(parents=True, exist_ok=True)
    try:
        fn(d)
        print(f"{name}: PASSED", flush=True)
    except AssertionError as exc:
        print(f"{name}: FAILED — {exc}", flush=True)
shutil.rmtree(tmp, ignore_errors=True)
