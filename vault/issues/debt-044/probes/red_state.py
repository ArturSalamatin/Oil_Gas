r"""DEBT-044: что делает фабрика с недопустимыми значениями CSV-таблиц до правки (красное состояние).

Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-044\probes\red_state.py
Каждый случай — configs/table_pvt с одной подменённой таблицей, при p_wf = 15 МПа
(штатный, = p_b) и 10 МПа (газовая зона у забоя). Если from_config проходит,
делается run (24 ч по 1 ч, N = 20) и печатается итог последнего состояния.
Рабочий каталог red_state_tmp/ создаётся рядом и удаляется в конце.
"""
import shutil
import sys
import traceback
import warnings
from pathlib import Path

import numpy as np

# Проверяемый код — из текущего каталога (numerical_solver/ основного каталога
# или worktree), а не от расположения пробы
SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver import factory                         # noqa: E402
from gpn_multiphase_solver.io.config import load_config          # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory       # noqa: E402

print(f"Код: {Path(factory.__file__).resolve()}")

TABLE_CONFIG = SOLVER / "configs" / "table_pvt" / "config.json"
WORK = Path(__file__).resolve().parent / "red_state_tmp"

# Таблицы configs/table_pvt (Rs0 = 30, p0 = 20 МПа, p_wf = 15 МПа)
OIL_H = "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
OIL_0 = "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
OIL_30 = "30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"
GAS_H = "pressure_Pa,Bg,mu_g_Pa_s\n"
GAS_1, GAS_2, GAS_3 = ("5000000,0.020,0.000012\n", "15000000,0.008,0.000014\n",
                       "30000000,0.004,0.000018\n")
RP_H = "Sg,kro,krg\n"
RP_ROWS = ["0.0,1.0,0.0\n", "0.1,0.8,0.01\n", "0.2,0.6,0.05\n",
           "0.4,0.3,0.2\n", "0.6,0.1,0.5\n", "0.8,0.0,0.8\n"]


def rp(replace: dict[int, str] | None = None, rows: list[str] | None = None) -> str:
    """relperm.csv configs/table_pvt с заменой строк данных по индексу."""
    rows = list(RP_ROWS if rows is None else rows)
    for i, line in (replace or {}).items():
        rows[i] = line
    return RP_H + "".join(rows)


CASES = {
    "эталон (без подмены)": dict(),
    # ── Газ ──
    "gas_bg_zero":        dict(gas=GAS_H + GAS_1 + "15000000,0.0,0.000014\n" + GAS_3),
    "gas_bg_negative":    dict(gas=GAS_H + GAS_1 + "15000000,-0.008,0.000014\n" + GAS_3),
    "gas_mu_zero":        dict(gas=GAS_H + GAS_1 + "15000000,0.008,0\n" + GAS_3),
    "gas_mu_negative":    dict(gas=GAS_H + GAS_1 + "15000000,0.008,-0.000014\n" + GAS_3),
    "gas_p_negative":     dict(gas=GAS_H + "-5000000,0.020,0.000012\n" + GAS_2 + GAS_3),
    "gas_header_only":    dict(gas=GAS_H),
    "gas_one_row":        dict(gas=GAS_H + GAS_2),
    "gas_p_not_increasing": dict(gas=GAS_H + GAS_2 + GAS_1 + GAS_3),
    # ── ОФП ──
    "rp_sg_negative":     dict(rp=rp({0: "-0.1,1.0,0.0\n"})),
    "rp_sg_above_one":    dict(rp=rp({5: "1.2,0.0,0.8\n"})),
    "rp_kro_negative":    dict(rp=rp({5: "0.8,-0.1,0.8\n"})),
    "rp_kro_above_one":   dict(rp=rp({0: "0.0,1.2,0.0\n"})),
    "rp_krg_negative":    dict(rp=rp({1: "0.1,0.8,-0.01\n"})),
    "rp_krg_above_one":   dict(rp=rp({5: "0.8,0.0,1.2\n"})),
    "rp_header_only":     dict(rp=RP_H),
    "rp_one_row":         dict(rp=rp(rows=["0.0,1.0,0.0\n"])),
    "rp_sg_not_increasing": dict(rp=rp({2: "0.4,0.3,0.2\n", 3: "0.2,0.6,0.05\n"})),
    # ── Нефть ──
    "oil_bo_zero":        dict(oil=OIL_H + OIL_0 + "30.0,15000000,0.0,0.0015\n30.0,30000000,1.18,0.0016\n"),
    "oil_bo_negative":    dict(oil=OIL_H + OIL_0 + "30.0,15000000,-1.20,0.0015\n30.0,30000000,1.18,0.0016\n"),
    "oil_mu_zero":        dict(oil=OIL_H + OIL_0 + "30.0,15000000,1.20,0\n30.0,30000000,1.18,0.0016\n"),
    "oil_mu_negative":    dict(oil=OIL_H + OIL_0 + "30.0,15000000,1.20,-0.0015\n30.0,30000000,1.18,0.0016\n"),
    "oil_rs_negative":    dict(oil=OIL_H + "-5.0,4000000,1.02,0.0031\n-5.0,30000000,1.01,0.0033\n"
                               + OIL_0 + OIL_30),
    "oil_p_negative":     dict(oil=OIL_H + "0.0,-5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n" + OIL_30),
    "oil_one_branch":     dict(oil=OIL_H + OIL_30),
}


def _config_with(tmp, p_wf, oil=None, gas=None, rp=None):
    """TABLE_CONFIG с подменёнными CSV в каталоге tmp и забойным давлением p_wf, Па."""
    tmp.mkdir()
    for fname in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
        shutil.copy(TABLE_CONFIG.parent / fname, tmp / fname)
    for fname, text in (("oil_pvt.csv", oil), ("gas_pvt.csv", gas), ("relperm.csv", rp)):
        if text is not None:
            (tmp / fname).write_text(text, encoding="utf-8")
    config = load_config(TABLE_CONFIG)
    config.config_dir = tmp
    for h in config.time.history:
        h.p_wf = p_wf
    return config


def _where(e):
    tb = traceback.extract_tb(e.__traceback__)[-1]
    return f"{Path(tb.filename).name}:{tb.lineno}"


def run_cases(p_wf):
    print(f"\n== from_config и run: configs/table_pvt, одна таблица подменена, p_wf = {p_wf / 1e6:g} МПа")
    for i, (name, kw) in enumerate(CASES.items()):
        config = _config_with(WORK / f"{p_wf:.0f}_{i}", p_wf, **kw)
        stage = "from_config"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                sim, state = SimulatorFactory.from_config(config)
                stage = "run"
                hist = sim.run(state)
                s = hist.states[-1]
                finite = all(np.all(np.isfinite(a)) for a in (s.p, s.Sg, s.T))
                out = (f"ПРОШЛИ: t = {hist.times[-1] / 3600:g} ч, p {s.p.min() / 1e6:.4g}…"
                       f"{s.p.max() / 1e6:.4g} МПа, S_g max {s.Sg.max():.4g}, "
                       f"T {s.T.min():.5g}…{s.T.max():.5g} К, конечны: {finite}")
            except Exception as e:
                msg = str(e).splitlines()[0] if str(e) else ""
                out = f"{stage}: {type(e).__name__}: {msg[:150]}  [{_where(e)}]"
        warn = sorted({f"{w.category.__name__}: {str(w.message)[:60]}" for w in caught
                       if not issubclass(w.category, DeprecationWarning)})
        print(f"{name:22s} {out}")
        for w in warn[:3]:
            print(f"{'':22s}   предупреждение {w}")


if __name__ == "__main__":
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()
    try:
        # 15 МПа = p_b(Rs0 = 30): штатный режим configs/table_pvt, газа почти нет;
        # 10 МПа < p_b: у забоя газовая зона, в счёт входят B_g, mu_g и ОФП газа
        run_cases(15e6)
        run_cases(10e6)
    finally:
        shutil.rmtree(WORK)
