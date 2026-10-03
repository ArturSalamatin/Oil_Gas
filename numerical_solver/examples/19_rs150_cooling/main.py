"""Сценарий 19: R_s0 = 150, горячий пласт (T0 = 400 К) — охлаждение забоя за 30 сут."""

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
        title="19: R_s0 = 150, горячий пласт — охлаждение забоя",
        # Без стационарной аналитики: за 30 сут газ ещё копится в пласте
        # (GOR = 128.7 < R_s0 = 150 и растёт), а замкнутое решение строится
        # по условию GOR = R_s0 — сверка с пределом t -> inf точность расчёта
        # не характеризует. Проверка R_s и баланс энергии остаются.
        steady_state=False,
    )
