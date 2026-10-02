"""Сценарий 14: высокий газовый фактор (R_s0 = 150, S_gc = 0.1) — охлаждение забоя за год."""

import sys
from pathlib import Path

# examples/ в sys.path — для импорта example_runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from example_runner import run_example  # noqa: E402

if __name__ == "__main__":
    here = Path(__file__).parent
    run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title="14: высокий газовый фактор — охлаждение забоя",
        n_profiles=6,
        # Без стационарной аналитики: газ ещё копится в пласте, GOR = 149.2 <
        # R_s0 = 150, а замыкание GOR = R_s0 требует S_g >= S_gc = 0.1 во всей
        # двухфазной зоне при численной 0.091 в ячейке у фронта. Сверка
        # report_closed сравнивала бы нестационарное состояние с пределом
        # t -> inf. Флаг снимает пунктир давления и S_g, report_closed и
        # асимптотику температуры; проверка R_s остаётся.
        steady_state=False,
    )
