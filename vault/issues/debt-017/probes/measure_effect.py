"""DEBT-017: величина сдвига T после перехода к свойствам ГУ на контуре.

Сверяет текущее поле T с эталоном дефектного поведения, снятым до правки
(tests/baseline_vectorization_T.npz, шаг 1 плана).

    cd numerical_solver
    .venv\Scripts\python -m pytest ../vault/issues/debt-017/probes/measure_effect.py -s -q
"""
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve()
# probes -> debt-017 -> issues -> vault -> корень проекта
_SOLVER = _HERE.parents[4] / "numerical_solver"
EXAMPLES = _SOLVER / "examples"
BASELINE = _SOLVER / "tests" / "baseline_vectorization_T.npz"

# Прототип radial_blackoil нужен табличному PVT примеров 07-11. Его
# подключает tests/conftest.py, но он не действует за пределами tests/,
# поэтому путь добавляем сами (правило из шапки /implement).
_PROTO = _SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO) not in sys.path:
    sys.path.insert(0, str(_PROTO))

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CASES = ["07_degassing_adiabatic_only", "08_degassing_jt",
         "09_degassing_latent_heat", "10_deep_degassing",
         "11_degassing_at_boundary"]


def test_measure():
    """Печатает сдвиг T по каждому примеру. Не проверяет — измеряет."""
    ref = np.load(BASELINE)
    print(f"\n{'пример':<28} {'max|ΔT|, К':>12} {'|ΔT| в N-1':>12} "
          f"{'T[N-1] было':>14} {'T[N-1] стало':>14}")
    for name in CASES:
        cfg = load_config(EXAMPLES / name / "config.json")
        cfg.output.log_level = "ERROR"
        sim, init = SimulatorFactory.from_config(cfg)
        T_new = np.asarray(sim.run(init).states[-1].T, dtype=float)
        T_old = ref[name]
        d = np.abs(T_new - T_old)
        print(f"{name:<28} {d.max():>12.3e} {d[-1]:>12.3e} "
              f"{T_old[-1]:>14.8f} {T_new[-1]:>14.8f}")
