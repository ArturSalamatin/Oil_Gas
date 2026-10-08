"""DEBT-015, аудит: код шага 3 плана дословно — подменой, без правки рабочего кода.

Подменяет: HydroConvergenceError (в hydro/base.py), PrototypeHydroAdapter.__init__/solve,
Simulator.__init__ (max_retries), Simulator._advance, Simulator._failure_message,
SimulatorFactory.from_config (max_retries → Simulator). Поле HydroResult.n_substeps
остаётся (как после шага 3 плана). Используется как плагин pytest (-p plan_code) и
импортом из проб.

Запуск из numerical_solver:
    $env:PYTHONPATH = "..\\vault\\issues\\debt-015\\probes;."
    .venv\\Scripts\\python -m pytest -p plan_code tests/ -m "not slow" -q
"""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

_SOLVER = Path.cwd()
# Каталог numerical_solver — впереди прототипа: у прототипа свой пакет tests
for _p in (_SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3", _SOLVER):
    while str(_p) in sys.path:
        sys.path.remove(str(_p))
    sys.path.insert(0, str(_p))

import gpn_multiphase_solver.hydro.base as _base  # noqa: E402
import gpn_multiphase_solver.hydro.prototype_adapter as _pa  # noqa: E402
import gpn_multiphase_solver.simulator as _sim  # noqa: E402
import gpn_multiphase_solver.factory as _fac  # noqa: E402
from gpn_multiphase_solver.state import (  # noqa: E402
    SimulationState, HydroResult, BoundaryConditions)
from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator  # noqa: E402
from gpn_multiphase_solver.mass_balance import MassBalanceAccumulator  # noqa: E402
from gpn_multiphase_solver.bc import PressureControl, RateControl  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA, DAY_TO_S  # noqa: E402
from gpn_multiphase_solver.log import user_log, dev_log  # noqa: E402


# ── Шаг 2 плана ──
class HydroConvergenceError(RuntimeError):
    """Шаг гидродинамики не сошёлся при данном dt; шаг дробит Simulator (DEBT-015)."""


_base.HydroConvergenceError = HydroConvergenceError


# ── Шаг 3.1 плана: адаптер ──
_orig_ad_init = _pa.PrototypeHydroAdapter.__init__


def _ad_init(self, model, grid, pvt, **_ignored):
    # План: __init__(self, model, grid, pvt) без max_retries; фабрика базы ещё
    # передаёт max_retries — здесь он отбрасывается, атрибута _max_retries нет.
    self._model = model
    self._grid = grid
    self._pvt = pvt


def solve(self, state: SimulationState, dt: float,
          bc: BoundaryConditions) -> HydroResult:
    """Один шаг advance без дробления; не сошёлся — HydroConvergenceError (DEBT-015)."""
    from radial_blackoil.state import BlackOilState

    # ── Шаг 1: управление скважиной ── (без изменений, из базы)
    well = bc.well
    if isinstance(well, PressureControl):
        self._model.set_bhp_control(well.p_wf / BAR_TO_PA)
    elif isinstance(well, RateControl):
        self._model.set_oil_rate_control(well.q_oil * DAY_TO_S,
                                         well.min_bhp / BAR_TO_PA)
    else:
        raise NotImplementedError(
            f"PrototypeHydroAdapter поддерживает PressureControl и RateControl, "
            f"получено {type(well).__name__}")

    # ── Шаг 2: SimulationState (Па) → BlackOilState (бар) ──
    proto_state = BlackOilState(
        pressure_bar=state.p / BAR_TO_PA,
        rs_sm3_sm3=state.Rs.copy(),
        sg=state.Sg.copy(),
        gas_active=(state.regime == 1),
    )

    # ── Шаг 3: advance ──
    new_proto, report = self._model.advance(proto_state, dt)
    if not report.converged:
        raise HydroConvergenceError(
            f"advance не сошёлся: dt = {dt:.3e} с, "
            f"t = {state.t / DAY_TO_S:.4f} сут, итераций {report.iterations}, "
            f"невязка {report.residual_inf:.2e}")

    # ── Шаг 4: BlackOilState (бар) → SimulationState (Па) ──
    new_state = SimulationState(
        p=new_proto.pressure_bar * BAR_TO_PA,
        Sg=new_proto.sg.copy(),
        Rs=new_proto.rs_sm3_sm3.copy(),
        T=state.T.copy(),                # гидро не трогает T
        regime=np.where(new_proto.gas_active, 1, 2),
        t=state.t + dt,
    )

    f = self._model.face_component_fluxes_sm3s(new_proto)
    result = self._build_result(new_state, new_proto, bc)
    return replace(result,
                   int_G_o_well=dt * (-f['oil_well']),
                   int_G_o_ext=dt * f['oil_outer'],
                   int_G_g_well=dt * (-f['gas_component_well']),
                   int_G_g_ext=dt * f['gas_component_outer'])


_pa.PrototypeHydroAdapter.__init__ = _ad_init
_pa.PrototypeHydroAdapter.solve = solve


# ── Шаг 3.2 плана: Simulator ──
_orig_sim_init = _sim.Simulator.__init__


def _sim_init(self, grid, hydro, energy, pvt, schedule, output_config=None,
              max_retries: int = 9):
    _orig_sim_init(self, grid, hydro, energy, pvt, schedule, output_config)
    self._max_retries = int(max_retries)


def _advance(self, state: SimulationState, dt: float,
             bc: BoundaryConditions,
             balance: EnergyBalanceAccumulator,
             mass: MassBalanceAccumulator | None
             ) -> tuple[SimulationState, HydroResult]:
    """Шаг dt: подшаги гидро → энергия; не сошедшийся подшаг делится пополам (DEBT-015)."""
    n_units = 2 ** self._max_retries
    done = 0              # пройдено единиц
    size = n_units        # текущий подшаг, единиц; всегда степень двойки
    n_ok = n_fail = 0
    h_min_ok = dt
    while done < n_units:
        h = dt / (n_units // size)

        try:
            hydro_result = self._hydro.solve(state, h, bc)
        except HydroConvergenceError as exc:
            n_fail += 1
            dev_log.debug(f"  подшаг {h:.3e} с не сошёлся: {exc}")
            if size == 1:
                raise RuntimeError(self._failure_message(state, dt)) from exc
            size //= 2
            continue

        if mass is not None:
            mass.add_step(hydro_result)

        T_new = self._energy.solve(
            hydro_result, state, h, bc, collect=balance)

        state = SimulationState(
            p=hydro_result.state.p,
            Sg=hydro_result.state.Sg,
            Rs=hydro_result.state.Rs,
            T=T_new,
            regime=hydro_result.state.regime,
            t=hydro_result.state.t,
        )
        n_ok += 1
        h_min_ok = min(h_min_ok, h)
        done += size
        if done < n_units and done % (2 * size) == 0:
            size *= 2

    if n_fail > 0:
        user_log.info(
            f"Шаг {dt:.3g} с раздроблен: подшагов {n_ok}, наименьший "
            f"{h_min_ok:.3g} с, отказов гидродинамики {n_fail}")
    return state, hydro_result


def _failure_message(self, state: SimulationState, dt: float) -> str:
    """Текст отказа: факты подшага, на котором исчерпано дробление (BUG-018, DEBT-015)."""
    n_units = 2 ** self._max_retries
    n_two = int(np.count_nonzero(state.regime == 1))
    return (
        f"HydroSolver не сошёлся при дроблении шага до dt/{n_units} = "
        f"{dt / n_units:.2e} с на подшаге с t = {state.t / DAY_TO_S:.4f} сут: "
        f"двухфазных ячеек {n_two} из {state.p.size}, "
        f"max S_g = {float(np.max(state.Sg)):.3f}. "
        f"Наименьший подшаг — time.dt_integration / 2**numerics.max_retries "
        f"(сейчас max_retries = {self._max_retries}, допустимо до 20). "
        f"Если отказ вызван величиной шага, поможет больший "
        f"numerics.max_retries или меньший time.dt_integration; если шаг "
        f"не сходится и при мелких подшагах, причина не в его величине.")


_sim.Simulator.__init__ = _sim_init
_sim.Simulator._advance = _advance
_sim.Simulator._failure_message = _failure_message


# ── Шаг 3.3 плана: фабрика передаёт max_retries в Simulator ──
_orig_from_config = _fac.SimulatorFactory.from_config


def _from_config(config):
    sim, init = _orig_from_config(config)
    sim._max_retries = int(config.numerics.max_retries)
    return sim, init


_fac.SimulatorFactory.from_config = staticmethod(_from_config)
