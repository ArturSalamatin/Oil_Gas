"""SimulatorFactory — создание Simulator из SimulationConfig.

Единственное место, где создаются конкретные классы.
Остальной код работает с абстракциями (Grid, HydroSolver, EnergySolver, HydroPVT).

from_config(config) → (Simulator, initial_state)
"""

import csv
from pathlib import Path

import numpy as np

from .grid.log_radial import LogRadialGrid
from .pvt.standing import StandingFullPVT
from .pvt.relperm import CoreyRP
from .pvt.table_full import TableFullPVT
from .pvt.prototype_adapter import PrototypePVTAdapter, PrototypeRPAdapter
from .pvt.hydro_to_blackoil_adapter import HydroPVTtoBlackOilAdapter
from .hydro.prototype_adapter import PrototypeHydroAdapter
from .energy.tridiag import TridiagEnergySolver
from .state import SimulationState, BoundaryConditions
from .bc import PressureControl, RateControl
from .simulator import Simulator, TimeSchedule, ScheduleInterval
from .io.config import SimulationConfig
from .units import BAR_TO_PA, CP_TO_PA_S, M2_TO_MD
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

        # 4. HydroSolver — всегда PrototypeHydroAdapter (Newton-солвер прототипа)
        hydro = _create_prototype_hydro(config, grid, pvt, relperm)

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
    elif pc.model == "table":
        # CSV → BlackOilPVT (прототип) → PrototypePVTAdapter → TableFullPVT
        oil_rows = _read_oil_pvt_csv(config.config_dir / pc.oil_pvt_file)
        gas_rows = _read_gas_pvt_csv(config.config_dir / pc.gas_pvt_file)

        from radial_blackoil.pvt import BlackOilPVT
        proto_pvt = BlackOilPVT(oil_rows, gas_rows)

        proto_adapter = PrototypePVTAdapter(proto_pvt, pc.rho_o_std, pc.rho_g_std)
        return TableFullPVT(
            hydro=proto_adapter,
            c_p_oil=tc.c_p_oil,
            c_p_gas=tc.c_p_gas,
            mu_JT_oil=tc.mu_JT_oil,
            mu_JT_gas=tc.mu_JT_gas,
            L_degas=tc.L_degas,
        )
    else:
        raise ValueError(f"PVT model '{pc.model}' не поддерживается. "
                         f"Доступные: 'standing', 'table'.")


def _create_relperm(config: SimulationConfig):
    """Создать RelPermModel по config.relperm.model."""
    rc = config.relperm

    if rc.model == "corey":
        return CoreyRP(
            S_or=rc.S_or, S_gc=rc.S_gc,
            n_o=rc.n_o, n_g=rc.n_g,
            kro_max=rc.kro_max, krg_max=rc.krg_max,
        )
    elif rc.model == "table":
        # CSV → TabulatedRelPerm (прототип) → PrototypeRPAdapter
        Sg, kro, krg = _read_relperm_csv(config.config_dir / rc.file)

        from radial_blackoil.relperm import TabulatedRelPerm
        proto_rp = TabulatedRelPerm(Sg, kro, krg)
        return PrototypeRPAdapter(proto_rp)
    else:
        raise ValueError(f"RelPerm model '{rc.model}' не поддерживается. "
                         f"Доступные: 'corey', 'table'.")


def _create_prototype_hydro(config: SimulationConfig, grid, pvt, relperm):
    """Создать PrototypeHydroAdapter из любого PVT (табличного или аналитического).

    Для табличного PVT (TableFullPVT) — извлекает BlackOilPVT из обёрток.
    Для аналитического (StandingFullPVT) — оборачивает через HydroPVTtoBlackOilAdapter.
    Согласованность: один объект HydroPVT разделяется между прототипом и нашими модулями
    (см. vault/knowledge/decisions/согласованность-pvt-hydro.md).
    """
    from radial_blackoil.grid import RadialGrid
    from radial_blackoil.rock import CompressibleRock
    from radial_blackoil.blackoil import RadialBlackOilModel

    ic = config.initial_conditions

    # proto_pvt: BlackOilPVT для RadialBlackOilModel
    proto_pvt = _get_or_create_proto_pvt(pvt, ic.p0)

    # proto_rp: TabulatedRelPerm для RadialBlackOilModel
    proto_rp = _get_or_create_proto_rp(relperm)

    gc = config.geometry
    rc = config.rock
    nc = config.numerics

    # Сетка прототипа (k в мД)
    proto_grid = RadialGrid(gc.r_well, gc.R_ext, gc.h, config.grid.N,
                            rc.permeability * M2_TO_MD)

    # Порода прототипа (p_ref в бар, cr в 1/бар)
    proto_rock = CompressibleRock(
        phi_ref=rc.porosity,
        p_ref_bar=ic.p0 / BAR_TO_PA,
        cr_per_bar=rc.compressibility * BAR_TO_PA,
    )

    # p_bhp: первый интервал, p_outer: начальное пластовое
    # Режим первого интервала истории. Это оценка p_bhp для инициализации
    # прототипа, а не управление скважиной по ходу расчёта (им занимается
    # WellControl каждого интервала), поэтому первого интервала достаточно
    # даже при расписании из десятков интервалов (DEBT-013).
    # При заданном дебите p_wf в конфиге нет — берём min_bhp (обязателен при
    # control='rate', FEAT-020); до первого solve() значение не используется.
    h0 = config.time.history[0]
    p_bhp_bar = (h0.p_wf if h0.control == "pressure" else h0.min_bhp) / BAR_TO_PA
    p_outer_bar = ic.p0 / BAR_TO_PA

    model = RadialBlackOilModel(
        grid=proto_grid, rock=proto_rock,
        pvt=proto_pvt, relperm=proto_rp,
        p_bhp_bar=p_bhp_bar, p_outer_bar=p_outer_bar,
        outer_rs_sm3_sm3=ic.Rs0,
        skin=nc.skin,
        jacobian_mode=nc.jacobian_mode,
        linear_solver=nc.linear_solver,
    )

    # our_pvt: HydroPVT для PrototypeHydroAdapter (пересчёт потоков)
    our_pvt = pvt._hydro if hasattr(pvt, '_hydro') else pvt
    return PrototypeHydroAdapter(model, grid, our_pvt,
                                 max_retries=nc.max_retries)


def _get_or_create_proto_pvt(pvt, p0: float):
    """Получить BlackOilPVT для RadialBlackOilModel.

    Табличный путь: TableFullPVT → PrototypePVTAdapter → BlackOilPVT (извлечь).
    Аналитический путь (Standing и др.): обернуть HydroPVT через адаптер.
    """
    if hasattr(pvt, '_hydro') and hasattr(pvt._hydro, '_pvt'):
        return pvt._hydro._pvt

    return HydroPVTtoBlackOilAdapter(pvt, p_max_pa=p0)


def _get_or_create_proto_rp(relperm):
    """Получить TabulatedRelPerm для RadialBlackOilModel.

    PrototypeRPAdapter — извлечь TabulatedRelPerm.
    CoreyRP — протабулировать на сетке Sg.
    """
    if hasattr(relperm, '_rp'):
        return relperm._rp

    from radial_blackoil.relperm import TabulatedRelPerm
    Sg = np.linspace(0.0, 1.0, 101)
    kro = relperm.kro(Sg)
    krg = relperm.krg(Sg)
    return TabulatedRelPerm(Sg, kro, krg)


# ── CSV-ридеры ──────────────────────────────────────────────

def _read_oil_pvt_csv(csv_path: Path) -> list[tuple]:
    """Прочитать oil_pvt.csv (SI) → [(Rs, p_bar, Bo, mu_cP), ...].

    CSV: Rs_sm3_sm3, pressure_Pa, Bo, mu_o_Pa_s.
    Конвертация: p Па→бар, μ Па·с→сП.
    """
    if not csv_path.exists():
        raise ValueError(f"Файл oil PVT не найден: {csv_path}")

    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # заголовок
        for line in reader:
            if len(line) < 4:
                continue
            try:
                Rs = float(line[0])
                p_bar = float(line[1]) / BAR_TO_PA
                Bo = float(line[2])
                mu_cP = float(line[3]) / CP_TO_PA_S
            except ValueError:
                continue
            rows.append((Rs, p_bar, Bo, mu_cP))
    return rows


def _read_gas_pvt_csv(csv_path: Path) -> list[tuple]:
    """Прочитать gas_pvt.csv (SI) → [(p_bar, Bg, mu_cP), ...].

    CSV: pressure_Pa, Bg, mu_g_Pa_s.
    Конвертация: p Па→бар, μ Па·с→сП.
    """
    if not csv_path.exists():
        raise ValueError(f"Файл gas PVT не найден: {csv_path}")

    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # заголовок
        for line in reader:
            if len(line) < 3:
                continue
            try:
                p_bar = float(line[0]) / BAR_TO_PA
                Bg = float(line[1])
                mu_cP = float(line[2]) / CP_TO_PA_S
            except ValueError:
                continue
            rows.append((p_bar, Bg, mu_cP))
    return rows


def _read_relperm_csv(csv_path: Path) -> tuple[list, list, list]:
    """Прочитать relperm.csv → (Sg, kro, krg).

    CSV: Sg, kro, krg. Безразмерные, конвертация не нужна.
    """
    if not csv_path.exists():
        raise ValueError(f"Файл relperm не найден: {csv_path}")

    Sg, kro, krg = [], [], []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # заголовок
        for line in reader:
            if len(line) < 3:
                continue
            try:
                Sg.append(float(line[0]))
                kro.append(float(line[1]))
                krg.append(float(line[2]))
            except ValueError:
                continue
    return Sg, kro, krg


def _create_schedule(config: SimulationConfig) -> TimeSchedule:
    """Создать TimeSchedule из TimeConfig + InitialConfig.

    Преобразует HistoryInterval (данные из JSON) → ScheduleInterval (runtime):
      HistoryInterval.control + p_wf / q_oil, min_bhp → WellControl → BoundaryConditions.
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
    """Создать WellControl из HistoryInterval (control проверен в _validate)."""
    if hist.control == "pressure":
        return PressureControl(hist.p_wf)
    if hist.control == "rate":
        return RateControl(hist.q_oil, hist.min_bhp)
    raise ValueError(
        f"history[{index}]: control='{hist.control}' не поддерживается. "
        f"Доступные: 'pressure', 'rate'.")
