"""SimulatorFactory — создание Simulator из SimulationConfig.

Единственное место, где создаются конкретные классы.
Остальной код работает с абстракциями (Grid, HydroSolver, EnergySolver, HydroPVT).

from_config(config) → (Simulator, initial_state)
"""

import numpy as np

from .grid.log_radial import LogRadialGrid
from .pvt.standing import StandingFullPVT
from .pvt.relperm import CoreyRP
from .hydro.analytical import AnalyticalHydroSolver
from .energy.tridiag import TridiagEnergySolver
from .state import SimulationState, BoundaryConditions
from .bc import PressureControl
from .simulator import Simulator, TimeSchedule, ScheduleInterval
from .io.config import SimulationConfig
from .log import setup_logging


class SimulatorFactory:
    """Фабрика: SimulationConfig → (Simulator, initial_state)."""

    @staticmethod
    def from_config(config: SimulationConfig) -> tuple[Simulator, SimulationState]:
        """Создать Simulator и начальное состояние из конфига.

        Возвращает (simulator, initial_state).
        Запуск: history = simulator.run(initial_state).
        """
        # Логирование
        setup_logging(config.output.log_level)

        # 1. Grid
        grid = LogRadialGrid(
            r_well=config.geometry.r_well,
            R_ext=config.geometry.R_ext,
            h=config.geometry.h,
            N=config.grid.N,
            k=config.rock.permeability,
        )

        # 2. PVT (FullPVT — гидро + тепловые)
        pvt = _create_pvt(config)

        # 3. RelPerm
        relperm = _create_relperm(config)

        # 4. HydroSolver
        hydro = AnalyticalHydroSolver(grid, pvt, relperm)

        # 5. EnergySolver
        energy = TridiagEnergySolver(grid, pvt, config.rock)

        # 6. TimeSchedule (runtime-расписание с BoundaryConditions)
        schedule = _create_schedule(config)

        # 7. Simulator
        simulator = Simulator(
            grid=grid, hydro=hydro, energy=energy, pvt=pvt,
            schedule=schedule, output_config=config.output)

        # 8. Начальное состояние
        ic = config.initial_conditions
        initial_state = SimulationState(
            p=np.full(grid.N, ic.p0),
            Sg=np.zeros(grid.N),
            Rs=np.full(grid.N, ic.Rs0),
            T=np.full(grid.N, ic.T0),
            regime=np.full(grid.N, 2, dtype=int),
            t=0.0,
        )

        return simulator, initial_state


# ── Помощники (внутренние функции модуля) ────────────────────

def _create_pvt(config: SimulationConfig):
    """Создать FullPVT по config.pvt.model."""
    pc = config.pvt
    tc = config.thermal
    ic = config.initial_conditions

    if pc.model == "standing":
        return StandingFullPVT(
            rho_o_std=pc.rho_o_std,
            rho_g_std=pc.rho_g_std,
            T0=ic.T0,
            Rs0=ic.Rs0,
            co_undersaturated=pc.co_undersaturated,
            c_p_oil=tc.c_p_oil,
            c_p_gas=tc.c_p_gas,
            mu_JT_oil_val=tc.mu_JT_oil,
            mu_JT_gas_val=tc.mu_JT_gas,
            L_degas_val=tc.L_degas,
        )
    else:
        raise ValueError(f"PVT model '{pc.model}' не поддерживается. "
                         f"Доступные: 'standing'.")


def _create_relperm(config: SimulationConfig):
    """Создать RelPermModel по config.relperm.model."""
    rc = config.relperm

    if rc.model == "corey":
        return CoreyRP(
            S_or=rc.S_or, S_gc=rc.S_gc,
            n_o=rc.n_o, n_g=rc.n_g,
            kro_max=rc.kro_max, krg_max=rc.krg_max,
        )
    else:
        raise ValueError(f"RelPerm model '{rc.model}' не поддерживается. "
                         f"Доступные: 'corey'.")


def _create_schedule(config: SimulationConfig) -> TimeSchedule:
    """Создать TimeSchedule из TimeConfig + InitialConfig.

    Преобразует HistoryInterval (данные из JSON) → ScheduleInterval (runtime):
      HistoryInterval.control + p_wf → PressureControl → BoundaryConditions.
    """
    ic = config.initial_conditions

    intervals = []
    for i, hist in enumerate(config.time.history):
        well_control = _create_well_control(hist, i)
        bc = BoundaryConditions(
            well=well_control,
            p_ext=ic.p0,       # давление на контуре = начальное пластовое
            T_ext=ic.T0,       # температура на контуре = начальная пластовая
            Rs_ext=ic.Rs0,     # газосодержание притока = начальное
            Sg_ext=0.0,        # однофазный приток с контура
        )
        intervals.append(ScheduleInterval(dt=hist.dt, bc=bc))

    return TimeSchedule(
        dt_integration=config.time.dt_integration,
        intervals=intervals,
    )


def _create_well_control(hist, index: int):
    """Создать WellControl из HistoryInterval."""
    if hist.control == "pressure":
        return PressureControl(hist.p_wf)
    else:
        raise ValueError(
            f"history[{index}]: control='{hist.control}' не поддерживается. "
            f"Доступные: 'pressure'.")
