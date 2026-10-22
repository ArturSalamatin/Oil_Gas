"""DEBT-027, эмуляция кода плана в памяти (файлы пакета и прототипа не меняются).

install() подменяет:
  - radial_blackoil.diagnostics.pvt_range_warnings — копия функции прототипа с параметром
    free_gas_sg (шаг 1 плана); без параметра — прежний текст побитово;
  - radial_blackoil.diagnostics.warning_category — новая функция шага 1;
  - PrototypeHydroAdapter: метод warn_table_range (шаг 2) и вызов после сошедшегося solve.
    Отличие от кода плана: состояние для проверки собирается из result.state (p в Па / BAR_TO_PA),
    а не берётся new_proto — давление может отличаться на 1 ulp, на пороги и 8 значащих цифр
    текста это не влияет;
  - factory: флаг check_table_range у адаптера и начальная проверка через адаптер (шаг 3).
scenarios() — сценарии будущих тестов на configs/table_pvt и примере 04a (первые 3 ч).
Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\debt-027\\probes\\emulate_debt027.py
"""
import logging
from pathlib import Path

import numpy as np

import radial_blackoil.diagnostics as diag
from radial_blackoil.diagnostics import _range_tol

import gpn_multiphase_solver
import gpn_multiphase_solver.factory as factory
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
from gpn_multiphase_solver.pvt.table_full import TableFullPVT
from gpn_multiphase_solver.units import BAR_TO_PA, DAY_TO_S
from gpn_multiphase_solver.log import user_log

FREE_GAS_SG = 1e-6


# ── Шаг 1: прототип, diagnostics.py ──
def pvt_range_warnings(model, state, free_gas_sg=None):
    p = np.asarray(state.pressure_bar, float); rs = np.asarray(state.rs_sm3_sm3, float)
    w = []; pvt = model.pvt; rp = model.relperm
    pmin = float(np.min(p)); pmax = float(np.max(p)); rmin = float(np.min(rs)); rmax = float(np.max(rs))
    if pmin < pvt.gp[0] - _range_tol(pvt.gp[0]):
        w.append(f'GAS_PVT pressure below table: min P={pmin:.8g} bar, table min={pvt.gp[0]:.8g} bar. Endpoint value used; no extrapolation.')
    if pmax > pvt.gp[-1] + _range_tol(pvt.gp[-1]):
        w.append(f'GAS_PVT pressure above table: max P={pmax:.8g} bar, table max={pvt.gp[-1]:.8g} bar. Endpoint value used; no extrapolation.')
    if rmin < pvt.rs_values[0] - _range_tol(pvt.rs_values[0]):
        w.append(f'OIL_PVT Rs below table: min Rs={rmin:.8g}, table min={pvt.rs_values[0]:.8g}. Endpoint branch used; no extrapolation.')
    if rmax > pvt.rs_values[-1] + _range_tol(pvt.rs_values[-1]):
        w.append(f'OIL_PVT Rs above table: max Rs={rmax:.8g}, table max={pvt.rs_values[-1]:.8g}. Endpoint branch used; no extrapolation.')
    ga = np.asarray(state.gas_active, bool)
    if np.any(ga):
        pg = p[ga]
        if np.min(pg) < pvt.pb[0] - _range_tol(pvt.pb[0]):
            w.append(f'OIL_PVT saturated locus below table: gas-active min P={np.min(pg):.8g} bar, min Pb={pvt.pb[0]:.8g} bar. Endpoint Rs used; no extrapolation.')
        top = pvt.pb[-1] + _range_tol(pvt.pb[-1])
        if free_gas_sg is None:
            if np.max(pg) > top:
                w.append(f'OIL_PVT saturated locus above table: gas-active max P={np.max(pg):.8g} bar, max Pb={pvt.pb[-1]:.8g} bar. Endpoint Rs used; no extrapolation.')
        else:
            sgc = np.asarray(state.sg, float)
            hot = ga & (sgc > free_gas_sg) & (p > top)
            if np.any(hot):
                w.append(f'OIL_PVT saturated locus above table: free gas Sg up to {np.max(sgc[hot]):.3g} at P up to {np.max(p[hot]):.8g} bar, max Pb={pvt.pb[-1]:.8g} bar. Endpoint Rs used, the gas cannot dissolve; no extrapolation.')
    pmax_branch = pvt.max_pressure_of_rs(rs)
    if np.any(p > pmax_branch + 1e-9 * np.maximum(1.0, np.abs(pmax_branch))):
        excess = np.max(p - pmax_branch)
        w.append(f'OIL_PVT branch pressure above supplied range by up to {excess:.8g} bar. Endpoint branch property used; no extrapolation.')
    sg = np.asarray(state.sg, float)
    if np.min(sg) < rp.sg[0] - _range_tol(rp.sg[0]):
        w.append(f'RELPERM Sg below table: min Sg={np.min(sg):.8g}, table min={rp.sg[0]:.8g}. Endpoint value used; no extrapolation.')
    if np.max(sg) > rp.sg[-1] + _range_tol(rp.sg[-1]):
        w.append(f'RELPERM Sg above table: max Sg={np.max(sg):.8g}, table max={rp.sg[-1]:.8g}. Endpoint value used; no extrapolation.')
    return w


WARNING_CATEGORIES = (
    'GAS_PVT pressure below table', 'GAS_PVT pressure above table',
    'OIL_PVT Rs below table', 'OIL_PVT Rs above table',
    'OIL_PVT saturated locus below table', 'OIL_PVT saturated locus above table',
    'OIL_PVT branch pressure above supplied range',
    'RELPERM Sg below table', 'RELPERM Sg above table')


def warning_category(s):
    return next((c for c in WARNING_CATEGORIES if s.startswith(c)), s.split(':', 1)[0])


# ── Шаг 2: адаптер ──
def warn_table_range(self, proto_state, t):
    if not getattr(self, "_check_table_range", False):
        return
    for warning in diag.pvt_range_warnings(self._model, proto_state, free_gas_sg=FREE_GAS_SG):
        category = diag.warning_category(warning)
        if category in self._range_categories:
            continue
        self._range_categories.add(category)
        where = ("Начальное состояние" if t == 0.0
                 else f"Состояние при t = {t / DAY_TO_S:.4g} сут")
        user_log.warning(f"{where} вне таблиц: {warning}")


def install(prototype_only=False):
    """prototype_only — только шаг 1 (прототип): состояние между шагами 1 и 2 плана."""
    from radial_blackoil.state import BlackOilState
    import gpn_multiphase_solver.hydro.prototype_adapter as adapter_module
    diag.pvt_range_warnings = pvt_range_warnings
    diag.warning_category = warning_category
    if prototype_only:
        return
    adapter_module.FREE_GAS_SG = FREE_GAS_SG
    PrototypeHydroAdapter.warn_table_range = warn_table_range
    orig_solve = PrototypeHydroAdapter.solve

    def solve(self, state, dt, bc):
        res = orig_solve(self, state, dt, bc)
        s = res.state
        proto = BlackOilState(pressure_bar=s.p / BAR_TO_PA, rs_sm3_sm3=s.Rs.copy(),
                              sg=s.Sg.copy(), gas_active=(s.regime == 1))
        self.warn_table_range(proto, state.t + dt)
        return res

    PrototypeHydroAdapter.solve = solve

    # ── Шаг 3: фабрика ──
    factory._warn_initial_table_range = lambda model, ic: None
    orig_create = factory._create_prototype_hydro

    def create(config, grid, pvt, relperm):
        adapter = orig_create(config, grid, pvt, relperm)
        adapter._check_table_range = isinstance(pvt, TableFullPVT)
        adapter._range_categories = set()
        ic = config.initial_conditions
        adapter.warn_table_range(BlackOilState.undersaturated(1, ic.p0 / BAR_TO_PA, ic.Rs0), 0.0)
        return adapter

    factory._create_prototype_hydro = create


def scenarios():
    from gpn_multiphase_solver.io.config import load_config
    from gpn_multiphase_solver.factory import SimulatorFactory
    solver = Path.cwd()
    records = []

    class Collect(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("gpn_multiphase_solver")
    logger.addHandler(Collect(level=logging.WARNING))
    table = solver / "configs" / "table_pvt" / "config.json"
    cases = [("table_pvt штатный (p_wf = 15 МПа)", table, None, None, None),
             ("table_pvt p_wf = 8 МПа", table, 8e6, None, None),
             ("table_pvt p_wf = 2 МПа", table, 2e6, None, None),
             ("table_pvt p0 = 32 МПа", table, None, 32e6, None),
             ("04a, первые 3 ч", solver / "examples" / "04a_high_gas_saturation" / "config.json", None, None, 36)]
    for label, path, p_wf, p0, n_int in cases:
        records.clear()
        cfg = load_config(path)
        if n_int is not None:
            cfg.time.history = cfg.time.history[:n_int]
        if p_wf is not None:
            for h in cfg.time.history:
                h.p_wf = p_wf
        if p0 is not None:
            cfg.initial_conditions.p0 = p0
        sim, s0 = SimulatorFactory.from_config(cfg)
        logger.setLevel(logging.WARNING)
        sim.run(s0)
        print(f"\n=== {label}: записей WARNING {len(records)} ===")
        for r in records:
            print(f"   {r.getMessage()}")


if __name__ == "__main__":
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    install()
    scenarios()
