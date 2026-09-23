"""Сценарий 04: разгазирование, табличные PVT + табличные ОФП (комбинация B)."""

import sys
from pathlib import Path

# examples/ в sys.path — для импорта example_runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Папка примера — для импорта pressure_gor_closure (аналитика для overlay).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from example_runner import run_example  # noqa: E402
from pressure_gor_closure import overlay_pressure, overlay_saturation  # noqa: E402

if __name__ == "__main__":
    here = Path(__file__).parent
    run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title="04: Table PVT + Table ОФП",
        # Аналитика из условия GOR = Rs0 — на профилях давления и насыщенности.
        # Для T аналитики нет: прежнее ОДУ было дивергентным и после
        # BUG-012 расходилось с ядром на 2.57 К (DEBT-022). Стационарной
        # замены не существует — здесь T выходит на режим ~150 суток
        # против 8-12 ч у давления (см. README, «Гидродинамика и
        # температура стационарны в разное время»).
        overlays={"p": overlay_pressure,
                  "Sg": overlay_saturation},
    )
