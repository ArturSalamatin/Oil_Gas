"""DEBT-019: замер запаса p[0] − p_wf на штатных конфигах.

Зачем. Вариант 1 по DEBT-019 предполагает отказ (ValueError) при
Δp_w = p_wf − p[0] >= 0. Прежде чем ставить строгую проверку, нужно
знать, насколько близко давление ячейки 0 подходит к забойному на
штатном добычном режиме: если запас p[0] − p_wf падает до величин
порядка машинной точности, строгое сравнение начнёт обрывать
корректные расчёты и потребуется допуск.

Замеряется минимум по всем сохранённым шагам истории.

Запуск (из numerical_solver/):
    .venv\\Scripts\\python examples\\debt019_margin_probe.py

Утилита одноразовая, диагностическая: в pytest не входит, на результат
расчёта не влияет.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Подключение прототипа radial_blackoil ────────────────────
# Тот же механизм, что в examples/example_runner.py и tests/conftest.py:
# прототип не установлен в venv, но Factory импортирует его при создании
# PrototypeHydroAdapter.
_SOLVER_ROOT = Path(__file__).resolve().parents[1]      # numerical_solver/
_PROTO_ROOT = _SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROTO_ROOT))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


def probe(config_path: Path) -> None:
    """Прогнать конфиг, напечатать статистику запаса p[0] − p_wf."""
    config = load_config(config_path)
    sim, state0 = SimulatorFactory.from_config(config)
    history = sim.run(state0)

    # Шаг 0 — начальное состояние: потоков нет, well_data нулевая.
    # Сравниваем p[0] каждого сохранённого шага с заданным p_wf того же шага.
    margins = np.array([
        st.p[0] - w.p_wf
        for st, w in zip(history.states[1:], history.well_data[1:])
    ])

    p_wf_ref = history.well_data[1].p_wf

    print(f"\n=== {config_path.name} ===")
    print(f"  сохранённых шагов:      {len(margins)}")
    print(f"  min(p[0] - p_wf):       {margins.min():.6e} Па")
    print(f"  max(p[0] - p_wf):       {margins.max():.6e} Па")
    print(f"  min относительно p_wf:  {margins.min() / p_wf_ref:.3e}")
    print(f"  запас всюду > 0:        {bool((margins > 0).all())}")


if __name__ == "__main__":
    # baseline — штатный добычной режим; 04a и 10 — худшие по подвижности
    # случаи (высокая Sg, глубокое разгазирование): там запас минимален,
    # если он вообще способен обратиться в ноль.
    probe(_SOLVER_ROOT / "configs" / "baseline.json")
    probe(_SOLVER_ROOT / "examples" / "10_deep_degassing" / "config.json")
    probe(_SOLVER_ROOT / "examples" / "04a_high_gas_saturation" / "config.json")
