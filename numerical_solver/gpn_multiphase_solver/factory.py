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
from .pvt.consistency import (
    gas_compressibility, negative_intervals,
    saturated_oil_compressibility, undersaturated_oil_compressibility,
)
from .hydro.prototype_adapter import PrototypeHydroAdapter
from .energy.tridiag import TridiagEnergySolver
from .state import SimulationState, BoundaryConditions
from .bc import PressureControl, RateControl
from .simulator import Simulator, TimeSchedule, ScheduleInterval
from .io.config import SimulationConfig
from .units import BAR_TO_PA, CP_TO_PA_S, M2_TO_MD
from .log import setup_logging, user_log


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
        _check_undersaturated_start(config.initial_conditions, pvt)
        # BUG-019: отрицательная сжимаемость нефти или газа — предупреждение
        _warn_negative_compressibility(config, pvt)

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

        # BUG-017: таблица обязана покрывать Rs0. BlackOilPVT не экстраполирует:
        # B_o, μ_o берутся с крайней ветки, R_s^sat(p) и p_b(R_s) обрезаются, а
        # запас газа в ячейке считается с полным Rs0. Выше последней ветки нефть
        # «пересыщена» при любом давлении — отказ первого шага или нефизичный
        # скачок давления (111 МПа при Rs0 = 40 на ветках 0/30); ниже первой —
        # молча не разгазируется. Проверка — до проверки пересыщения в
        # from_config: там p_b(Rs0) обрезан и сообщение было бы ложным.
        _check_rs0_in_table(ic.Rs0, proto_pvt.rs_values, pc.oil_pvt_file)

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


def _check_rs0_in_table(Rs0: float, rs_values, oil_pvt_file: str) -> None:
    """Rs0 внутри диапазона веток PVTO-таблицы, иначе ValueError (BUG-017)."""
    rs_lo, rs_hi = float(rs_values[0]), float(rs_values[-1])
    # Границы включаются: Rs0 ровно на крайней ветке — штатный случай
    # (Rs0 = 30 на ветках 0/30 у 13 табличных примеров).
    if not rs_lo <= Rs0 <= rs_hi:
        raise ValueError(
            f"Rs0 = {Rs0:g} м³ст/м³ст вне диапазона таблицы {oil_pvt_file}: "
            f"ветки R_s от {rs_lo:g} до {rs_hi:g} м³ст/м³ст. Таблица не "
            f"экстраполируется — добавьте ветки, покрывающие Rs0, или задайте "
            f"Rs0 в этих пределах.")


# Допуск пересыщения на старте, м³ст/м³ст, — rs_switch_tol решателя
# (RadialBlackOilModel, blackoil.py:32; фабрика его не меняет): проверка
# отвергает ровно те состояния, которые решатель при давлении p0 счёл бы
# пересыщенными. Округление ввода не мешает: p0 на 1 Па ниже p_b даёт избыток
# ~6e-6 (Стендинг, Rs0 = 50) и 3e-6 (таблица 0/30).
_RS0_SUPERSAT_TOL = 1e-5


def _check_undersaturated_start(ic, pvt) -> None:
    """Начальное состояние недонасыщенное: Rs0 <= Rs_eq(p0), иначе ValueError (BUG-017)."""
    # Начальное состояние всегда однофазное (S_g = 0, шаг 8 from_config) —
    # инициализации со свободным газом нет. При Rs0 > Rs_eq(p0) решатель на
    # первом шаге выделяет избыток «в закрытом сосуде», и давление молча
    # скачет почти до p_b(Rs0) (Стендинг, Rs0 = 80, p0 = 10 МПа: 13.78 МПа
    # за час). Критерий через Rs_eq(p0), а не p0 >= p_b(Rs0): у дегазированной
    # нефти табличное p_b(0) условно (5 МПа в демо-таблице), а Rs_eq(p0) = 0 =
    # Rs0 при любом p0 ниже — пересыщения нет.
    Rs_eq = float(pvt.Rs_eq(np.array([ic.p0]))[0])
    if ic.Rs0 > Rs_eq + _RS0_SUPERSAT_TOL:
        pb = float(pvt.pb(np.array([ic.Rs0]))[0])
        raise ValueError(
            f"Начальное состояние пересыщено газом: Rs0 = {ic.Rs0:g} м³ст/м³ст "
            f"больше равновесного Rs_eq(p0) = {Rs_eq:.6g} при p0 = "
            f"{ic.p0 / 1e6:.6g} МПа (давление насыщения p_b(Rs0) = "
            f"{pb / 1e6:.6g} МПа). Решатель стартует только из однофазного "
            f"состояния (S_g = 0): задайте p0 >= p_b(Rs0) или уменьшите Rs0.")


def _warn_negative_compressibility(config: SimulationConfig, pvt) -> None:
    """Предупредить о c < 0 нефти или газа (BUG-019). Ур. (eq:c_ot) problem_statement.tex."""
    # Условия (A2)-(A3) Peszyńska 2006 (Coats 1999, SPE 49774): при
    # отрицательной сжимаемости коэффициент C_p уравнения давления
    # (eq:Cp, eq:c_ot problem_statement.tex) в части ячеек меньше нуля, и
    # задача некорректна: якобиан шага вырождается на последовательности Δt,
    # шаг не сходится или результат зависит от шага. Как в ECLIPSE («Negative
    # Compressibility Found») — предупреждение, расчёт продолжается.
    # Конфиг BUG-019 (прежний пример 20: Стендинг, R_s0 = 500): c_ot < 0 при
    # p > 34.55 МПа.
    ic = config.initial_conditions
    # Нижняя граница — наименьшее забойное давление истории: при добыче
    # давление в пласте ниже него не опускается. При управлении дебитом
    # p_wf не задано — берём min_bhp (обязателен при control='rate', FEAT-020).
    p_lo = min(h.p_wf if h.control == "pressure" else h.min_bhp
               for h in config.time.history)
    p_b = float(pvt.pb(np.array([ic.Rs0]))[0])
    checks = []
    # Насыщенные состояния (нефть + свободный газ) — только при p <= p_b(Rs0):
    # растворённого газа больше Rs0 в задаче нет (закачки нет). Rs0 = 0 —
    # дегазированная нефть, свободного газа не бывает.
    if ic.Rs0 > 0.0 and p_b > p_lo:
        checks.append((
            "насыщенной нефти с выделяющимся газом c_ot = (B_g·dR_s/dp − dB_o/dp)/B_o",
            lambda p: saturated_oil_compressibility(pvt, p), p_lo, p_b))
        checks.append((
            "газа c_g = −(1/B_g)·dB_g/dp",
            lambda p: gas_compressibility(pvt, p), p_lo, p_b))
    # Недонасыщенная нефть с R_s = Rs0 — от p_b(Rs0) (или p_lo, если оно выше)
    # до p0: при добыче давление выше начального не поднимается.
    p_u = max(p_b, p_lo)
    if ic.p0 > p_u:
        checks.append((
            f"недонасыщенной нефти c_o = −(1/B_o)·∂B_o/∂p при R_s = {ic.Rs0:g}",
            lambda p: undersaturated_oil_compressibility(pvt, p, ic.Rs0), p_u, ic.p0))
    for name, c_of_p, lo, hi in checks:
        for p1, p2, c_min in negative_intervals(c_of_p, lo, hi):
            user_log.warning(
                f"PVT несогласована: отрицательная сжимаемость {name} при p от "
                f"{p1 / 1e6:.4g} до {p2 / 1e6:.4g} МПа (min {c_min:.3g} 1/Па). "
                f"Коэффициент уравнения давления C_p может стать отрицательным "
                f"(problem_statement.tex, eq:c_ot): возможны отказы шага и "
                f"зависимость результата от шага по времени. Расчёт продолжается.")


def _warn_initial_table_range(model, ic) -> None:
    """Предупреждения pvt_range_warnings прототипа для начального состояния (BUG-017)."""
    from radial_blackoil.state import BlackOilState
    from radial_blackoil.diagnostics import pvt_range_warnings

    # Начальное состояние однородно (p0, Rs0, S_g = 0, газ неактивен), а
    # pvt_range_warnings смотрит только min/max — одной ячейки достаточно.
    state = BlackOilState.undersaturated(1, ic.p0 / BAR_TO_PA, ic.Rs0)
    for warning in pvt_range_warnings(model, state):
        user_log.warning(f"Начальное состояние вне таблиц: {warning}")


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

    # Выход начального состояния за PVT- и ОФП-таблицы (BUG-017): прототип
    # берёт свойства с краёв таблиц без экстраполяции и молча. Только
    # табличная PVT: у HydroPVTtoBlackOilAdapter (Стендинг) нет газовой
    # таблицы gp — pvt_range_warnings упал бы AttributeError.
    if isinstance(pvt, TableFullPVT):
        _warn_initial_table_range(model, ic)

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
