"""Сценарий 04a: высокая газонасыщенность (S_g = 0.7 на забое).

Тот же табличный PVT, что в примере 04, но ОФП Кори с k_rg^max = 0.0014,
вычисленной ОБРАТНЫМ РАСЧЁТОМ из условия GOR = Rs0 (вывод — в README).
Показывает, что насыщенность управляется подвижностью газа, а не депрессией.
"""

import sys
from pathlib import Path

# examples/ в sys.path — для импорта example_runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Папка примера 04 — оттуда берётся ОДУ-аналитика температуры.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "04_table_table"))

from example_runner import run_example  # noqa: E402
import temperature_ode as tode  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

HERE = Path(__file__).parent


def overlay_temperature(ax, history, grid, simulator):
    """ОДУ-аналитика T на СВОЁМ конфиге.

    Готовый хук temperature_ode.overlay_temperature брать нельзя: он читает
    config.json из своей папки (04), а там dt_integration = 3600 против 300
    здесь. dt входит в kappa = (rho c_p)_eff / dt — коэффициент ОДУ, поэтому
    подстановка чужого значения исказила бы кривую в 12 раз по kappa.
    Всё остальное (solve_ode_at_steps) параметризовано и переиспользуется.
    """
    config = load_config(HERE / "config.json")
    # Те же 4 момента, что рисует run_example; нулевой шаг пропускаем —
    # там T = T_0 всюду, сравнивать нечего.
    n = len(history.times)
    steps = sorted({n // 3, 2 * n // 3, n - 1})
    sols = tode.solve_ode_at_steps(history, config, grid, simulator._energy,
                                   steps=steps)
    for k, s in enumerate(steps):
        r_ode, T_ode = sols[s]
        ax.plot(r_ode, T_ode, "k--", lw=1.6, zorder=5,
                label="ОДУ ($\\lambda = 0$)" if k == 0 else None)


if __name__ == "__main__":
    run_example(
        config_path=HERE / "config.json",
        output_dir=HERE / "output",
        title="04a: высокая газонасыщенность (Table PVT + Corey ОФП)",
        # p, Sg и Rs аналитику ставит сам example_runner из общих модулей
        # closed_form.py и rs_analytics.py — она не зависит ни от источника
        # PVT, ни от вида ОФП. Здесь передаём только T.
        overlays={"T": overlay_temperature},
    )
