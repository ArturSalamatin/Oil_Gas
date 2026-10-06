"""Сценарий 16: 15 сут добычи при 6 МПа, затем 15 сут останова (q_oil = 0)."""

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
        title="16: останов скважины после 15 сут добычи",
        # 7 моментов равномерно по времени: 0, 5, 10, 15 сут — добыча
        # (15 — её конец), 20, 25, 30 сут — останов. Само восстановление
        # давления (первые часы) — на wellbore_dynamics.png: первые сутки
        # останова записаны по часам.
        n_profiles=7,
        # Без стационарной аналитики: стационар последнего интервала
        # (q = 0) тривиален — p = p_ext всюду, а асимптотика температуры
        # сравнивала бы незавершённую релаксацию с пределом t -> inf.
        # Проверка R_s и баланс энергии остаются.
        steady_state=False,
    )
