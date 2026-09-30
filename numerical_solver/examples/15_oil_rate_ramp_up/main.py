"""Сценарий 15: пуск скважины, дебит нефти 18 -> 270 м³ст/сут за 15 сут (R_ext = 200 м)."""

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
        title="15: пуск скважины с линейно растущим дебитом нефти",
        # 6 моментов равномерно по времени: 0, 3, ..., 15 сут (как 13a).
        n_profiles=6,
        # Без стационарного решения на профилях давления и S_g (решения
        # пользователя 2026-09-30 и 2026-09-29). Стационар — предел t -> inf
        # при 270 м³ст/сут с GOR = Rs0 = 30, а на 15 сут у забоя избыток
        # свободного газа: GOR 58.1, S_g 0.038 против 0.018 — давление в
        # расчёте ниже стационарного на 464 кПа. Сверка — в консоли
        # (report_closed).
        overlays={"p": None, "Sg": None},
    )
