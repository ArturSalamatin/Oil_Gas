r"""DEBT-056: что делает расчёт при больших и отрицательных skin, p_wf, min_bhp (регистрация задачи).

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-056\probes\skin_range.py
Проводимость забойной грани прототипа (radial_blackoil/grid.py:21):
    T_w = 2π k h / (ln(r_1 / r_w) + s),   r_1 — центр первой ячейки.
При s = −ln(r_1/r_w) знаменатель обнуляется, при меньших s — T_w < 0.
Печатается ln(r_1/r_w) сетки baseline и итог расчёта (24 ч, p_wf = 6 МПа) при разных s.
Случаи — через пробу DEBT-051 (vault/issues/debt-051/probes/red_state.py):
configs/baseline.json с одним подменённым полем, каждый случай — отдельный процесс.
"""
import shutil
import sys
from pathlib import Path

PROBES_051 = Path(__file__).resolve().parents[2] / "debt-051" / "probes"
sys.path.insert(0, str(PROBES_051))
import red_state  # noqa: E402  (SOLVER = Path.cwd(), пути к пакету и прототипу)


def ln_r1_rw(config_path: Path) -> float:
    """ln(r_1/r_w) сетки прототипа для конфига: RadialGrid, центры — средние геометрические граней."""
    import json
    import numpy as np
    from radial_blackoil.grid import RadialGrid
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    g = raw["geometry"]
    grid = RadialGrid(g["r_well"], g["R_ext"], g["h"], raw["grid"]["N"], 100.0)
    return float(np.log(grid.centers_m[0] / grid.rw_m))


CASES = {
    "эталон (s = 0)": ("pressure", None),
    "skin = 5": ("pressure", ("numerics", "skin", 5.0)),
    "skin = 50": ("pressure", ("numerics", "skin", 50.0)),
    "skin = 1e3": ("pressure", ("numerics", "skin", 1e3)),
    "skin = 1e6": ("pressure", ("numerics", "skin", 1e6)),
    "skin = -0.01": ("pressure", ("numerics", "skin", -0.01)),
    "skin = -0.5": ("pressure", ("numerics", "skin", -0.5)),
    "skin = -2": ("pressure", ("numerics", "skin", -2.0)),
    "p_wf = 25 МПа (> p0)": ("pressure", ("history", "p_wf", 25e6)),
    "эталон rate_hi": ("rate_hi", None),
    "min_bhp = 25 МПа (> p0), rate_hi": ("rate_hi", ("history", "min_bhp", 25e6)),
}

if __name__ == "__main__":
    red_state.WORK = Path(__file__).resolve().parent / "skin_range_tmp"
    if red_state.WORK.exists():
        shutil.rmtree(red_state.WORK)
    red_state.WORK.mkdir()
    try:
        path = red_state._config_path(red_state.WORK / "grid", "pressure", None)
        print(f"ln(r_1/r_w) сетки baseline: {ln_r1_rw(path):.5g} "
              f"(особая точка T_w: s = −ln(r_1/r_w))")
        red_state.run_cases("S", "skin, p_wf, min_bhp вне физического диапазона", CASES)
    finally:
        shutil.rmtree(red_state.WORK)
