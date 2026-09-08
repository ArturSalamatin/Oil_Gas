"""Сценарий 04: разгазирование, табличные PVT + табличные ОФП (комбинация B)."""

import sys
from pathlib import Path

# examples/ в sys.path — для импорта example_runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Папка примера — для импорта pressure_gor_closure (аналитика для overlay).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from example_runner import run_example  # noqa: E402
from pressure_gor_closure import overlay_pressure, overlay_saturation  # noqa: E402
from temperature_ode import overlay_temperature  # noqa: E402

if __name__ == "__main__":
    here = Path(__file__).parent
    run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title="04: Table PVT + Table ОФП",
        # Аналитика из условия GOR = Rs0 — на профилях давления и насыщенности.
        # Для T — ОДУ первого порядка: в конфиге все lambda = 0, поэтому
        # уравнение энергии не краевое и решается точно (temperature_ode.py).
        overlays={"p": overlay_pressure,
                  "Sg": overlay_saturation,
                  "T": overlay_temperature},
    )
