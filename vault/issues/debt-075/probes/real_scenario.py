"""DEBT-075: сценарий замера DEBT-073 без порога S_g <= 0.98 — где сработает проверка состояния.

Пример 05 (Стендинг), таблица ОФП до S_g = 0.01 (k_ro = 0.98 на краю;
vault/issues/debt-071/probes/relperm_to_001.csv), первые 6 ч. Порог 0.98 прототипа снят
в памяти в обоих местах (_trial_is_reasonable, _newton_switching) — как в
vault/issues/debt-073/probes/sg_bound_scan.py. Без проверки расчёт доходит до S_g[0] = 311.

Режимы:
    emulate — проверки в Simulator ещё нет: обёртка PrototypeHydroAdapter.solve бросает
              RuntimeError на первом принятом состоянии с S_g вне [0, 1] (то же место, что у
              проверки варианта 1: сразу после hydro.solve, до энергии);
    real    — обёртки нет: отказ обязан дать сама проверка DEBT-075 в Simulator._advance.

Фабрика после DEBT-073 отвергает такую таблицу (_check_relperm_table): проверка таблиц
здесь отключена подменой в памяти — таблица монотонна, остальное в ней допустимо.

Запуск из numerical_solver/ (в worktree — с PYTHONPATH на worktree):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-075\\probes\\real_scenario.py emulate
    .venv\\Scripts\\python ..\\vault\\issues\\debt-075\\probes\\real_scenario.py real
"""
import inspect
import logging
import sys
import textwrap
from pathlib import Path

import numpy as np

import gpn_multiphase_solver
import gpn_multiphase_solver.factory as factory
import radial_blackoil
import radial_blackoil.blackoil as bo
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.io.config import load_config

SOLVER = Path.cwd()
HERE = Path(__file__).resolve().parent
RELPERM = HERE.parent.parent / "debt-071" / "probes" / "relperm_to_001.csv"
print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
print(f"прототип: {Path(radial_blackoil.__file__).parent}", flush=True)

mode = sys.argv[1] if len(sys.argv) > 1 else "emulate"
assert mode in ("emulate", "real"), mode

# ── Порог 0.98 → inf в обоих методах (подмена в памяти, файлы прототипа не меняются) ──
for name in ("_trial_is_reasonable", "_newton_switching"):
    src = textwrap.dedent(inspect.getsource(getattr(bo.RadialBlackOilModel, name)))
    assert "0.98" in src, name
    ns = {}
    exec(compile(src.replace("0.98", "float('inf')"), f"<{name}>", "exec"), bo.__dict__, ns)
    setattr(bo.RadialBlackOilModel, name, ns[name])

# ── Проверка таблиц ОФП фабрики (DEBT-044, DEBT-073) отключена ──
factory._check_relperm_table = lambda *args, **kwargs: None

# ── Учёт принятых состояний; в режиме emulate — отказ на первом S_g вне [0, 1] ──
TRACE = []
_orig_solve = PrototypeHydroAdapter.solve


def solve(self, state, dt, bc):
    res = _orig_solve(self, state, dt, bc)
    sg = res.state.Sg
    TRACE.append((res.state.t, dt, float(sg[0]), float(np.max(sg))))
    if mode == "emulate":
        bad = ~(np.isfinite(sg) & (sg >= 0.0) & (sg <= 1.0))
        if bad.any():
            j = int(np.argmax(bad))
            raise RuntimeError(
                f"[эмуляция] S_g вне [0, 1] после шага гидродинамики dt = {dt:g} с к "
                f"t = {res.state.t:g} с: ячейка {j}, S_g = {sg[j]:.6g}; "
                f"таких ячеек {int(np.count_nonzero(bad))} из {sg.size}")
    return res


PrototypeHydroAdapter.solve = solve

cfg = load_config(SOLVER / "examples" / "05_standing_table_rp" / "config.json")
cfg.relperm.model = "table"
cfg.relperm.file = str(RELPERM)
cfg.time.history = cfg.time.history[:6]       # 6 интервалов по 1 ч
print(f"режим: {mode}; ОФП: {RELPERM.name}; интервалов {len(cfg.time.history)}", flush=True)
try:
    sim, s0 = SimulatorFactory.from_config(cfg)
    logging.getLogger("gpn_multiphase_solver").setLevel(logging.ERROR)
    sim.run(s0)
    print("расчёт дошёл до конца")
except Exception as exc:  # noqa: BLE001 — проба: печать причины
    print(f"отказ ({type(exc).__name__}): {exc}")
print(f"принятых подшагов: {len(TRACE)}")
for t, dt, sg0, sgmax in TRACE[:5]:
    print(f"  t = {t:9.2f} с, dt = {dt:8.2f} с, S_g[0] = {sg0:.6f}, max S_g = {sgmax:.6f}")
