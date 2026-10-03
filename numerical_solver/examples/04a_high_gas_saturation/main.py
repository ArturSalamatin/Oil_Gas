"""Сценарий 04a: высокая газонасыщенность (S_g = 0.7 на забое).

Табличный PVT и ОФП Кори с k_rg^max = 0.0014, вычисленной ОБРАТНЫМ
РАСЧЁТОМ из условия GOR = Rs0 (вывод — в README).
Показывает, что насыщенность управляется подвижностью газа, а не депрессией.
"""

import sys
from pathlib import Path

# examples/ в sys.path — для импорта example_runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from example_runner import run_example  # noqa: E402

HERE = Path(__file__).parent


if __name__ == "__main__":
    run_example(
        config_path=HERE / "config.json",
        output_dir=HERE / "output",
        title="04a: высокая газонасыщенность (Table PVT + Corey ОФП)",
        # p, Sg и Rs аналитику ставит сам example_runner из общих модулей
        # closed_form.py и rs_analytics.py — она не зависит ни от источника
        # PVT, ни от вида ОФП. Аналитики для T в двухфазной зоне нет:
        # схема проверяется балансом энергии и сверкой матрицы с постановкой.
    )
