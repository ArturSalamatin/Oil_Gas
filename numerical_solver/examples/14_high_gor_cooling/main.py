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
        # Без стационарного решения на профилях S_g (как 13a, решение
        # пользователя 2026-09-30): газ ещё копится в пласте, GOR = 146 <
        # R_s0 = 150, а замыкание GOR = R_s0 требует S_g >= S_gc = 0.1 во всей
        # двухфазной зоне при численных 0.005-0.11 у фронта. Пунктир давления
        # остаётся — предел t -> inf.
        overlays={"Sg": None},
    )
