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
        pvt = create_pvt(config)
        _check_undersaturated_start(config.initial_conditions, pvt,
                                    config.numerics.rs_switch_tol)
        # BUG-019: отрицательная сжимаемость нефти или газа — предупреждение
        _warn_negative_compressibility(config, pvt)

        # 3. RelPerm
        relperm = create_relperm(config)

        # 4. HydroSolver — всегда PrototypeHydroAdapter (Newton-солвер прототипа)
        hydro = _create_prototype_hydro(config, grid, pvt, relperm)

        # 5. EnergySolver
        energy = TridiagEnergySolver(grid, pvt, config.rock)

        # 6. TimeSchedule (runtime-расписание с BoundaryConditions)
        schedule = _create_schedule(config)

        # 7. Simulator
        # relperm — тот же объект, что ушёл гидродинамике: Simulator отдаёт
        # его диагностике (DEBT-011)
        simulator = Simulator(
            grid=grid, hydro=hydro, energy=energy, pvt=pvt,
            schedule=schedule, max_retries=config.numerics.max_retries,
            relperm=relperm)

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


# ── Сборка моделей по конфигу и помощники ────────────────────
# create_pvt, create_relperm — публичные (DEBT-011): по ним диагностика и
# примеры получают PVT и ОФП без решателя. Остальное — внутреннее.

def create_pvt(config: SimulationConfig):
    """FullPVT по config.pvt.model; публичная — для диагностики без решателя (DEBT-011)."""
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
            mu_o_undersaturated=pc.mu_o_undersaturated,
        )
    elif pc.model == "table":
        # У таблицы недонасыщенные ветви μ_o заданы самой таблицей (FEAT-027):
        # корреляция Била к ней неприменима, молча игнорировать опцию нельзя.
        if pc.mu_o_undersaturated != "none":
            raise ValueError(
                f"mu_o_undersaturated = {pc.mu_o_undersaturated!r} — только для "
                f"model = 'standing'; у табличного PVT вязкость выше p_b задаёт таблица.")
        # CSV → BlackOilPVT (прототип) → PrototypePVTAdapter → TableFullPVT
        oil_rows = _read_oil_pvt_csv(config.config_dir / pc.oil_pvt_file)
        gas_rows = _read_gas_pvt_csv(config.config_dir / pc.gas_pvt_file)
        # DEBT-038: ветви PVTO — до BlackOilPVT: он их не проверяет, ошибочную
        # таблицу молча интерполирует, а пустую встречает IndexError
        _check_pvto_branches(oil_rows, pc.oil_pvt_file)
        # DEBT-044: число строк и рост давления газа проверяет и BlackOilPVT
        # (pvt.py:32), но на английском и без имени файла
        _check_gas_pvt_table(gas_rows, pc.gas_pvt_file)

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


def _check_pvto_branches(oil_rows: list[tuple], oil_pvt_file: str) -> None:
    """PVTO: ≥ 2 ветвей по ≥ 2 строк, p и p_b(R_s) растут, иначе ValueError (DEBT-038, DEBT-044)."""
    # Правила формата PVTO (OPM Flow Manual, §8.3.245): в ветви — насыщенная
    # точка p_b(R_s) и строки недонасыщенной нефти по возрастанию давления;
    # p_b растёт с R_s. Первые два правила проверяет и XLSX-ридер прототипа
    # (input_reader.py:59-64). BlackOilPVT не проверяет ни одного, и ошибка
    # таблицы молча меняет свойства нефти — а через PrototypePVTAdapter и
    # уравнение энергии:
    #   - ветвь из одной строки: B_o, μ_o выше p_b постоянны (c_o = 0).
    #     OPM такую ветвь допускает (кроме последней) и достраивает по
    #     следующей ветви с недонасыщенными строками (opm-common, LiveOilPvt);
    #     прототип — нет;
    #   - повтор давления: BlackOilPVT сортирует строки по (p, B_o, μ_o), а не
    #     по порядку файла, — скачок B_o в этой точке;
    #   - давление не по возрастанию: сортировка исправила бы его молча, но
    #     XLSX-путь такую таблицу отвергает — правила двух путей одинаковы;
    #   - p_b не растёт с R_s: R_s^sat(p) интерполируется np.interp по узлам
    #     p_b, и при немонотонных узлах кривая разгазирования ломается.
    if not oil_rows:
        # Без строк BlackOilPVT падает IndexError без имени файла
        raise ValueError(f"{oil_pvt_file}: нет ни одной числовой строки.")
    # Ветвь — все строки с одним R_s (точное совпадение, как в BlackOilPVT);
    # давления в барах — как их получает BlackOilPVT, в порядке файла
    branches: dict[float, list[float]] = {}
    for Rs, p_bar, _, _ in oil_rows:
        branches.setdefault(Rs, []).append(p_bar)
    # DEBT-044: B_o, μ_o интерполируются между соседними ветвями R_s; с одной
    # ветвью BlackOilPVT отказывает без имени файла (pvt.py:46)
    if len(branches) < 2:
        Rs = list(branches)[0]
        raise ValueError(
            f"{oil_pvt_file}: одна ветвь R_s = {Rs:g} м³ст/м³ст, нужно не меньше "
            f"двух: B_o и μ_o интерполируются между ветвями R_s. У дегазированной "
            f"нефти (Rs0 = 0) добавьте ветвь с R_s > 0.")
    for Rs, p_bar in sorted(branches.items()):
        p_mpa = [p * BAR_TO_PA / 1e6 for p in p_bar]   # только для сообщений
        if len(p_bar) < 2:
            raise ValueError(
                f"{oil_pvt_file}: ветвь R_s = {Rs:g} м³ст/м³ст из одной строки "
                f"(p = {p_mpa[0]:g} МПа). Нужно не меньше двух: насыщенная точка "
                f"p_b(R_s) и хотя бы одна строка выше p_b — иначе B_o, μ_o "
                f"недонасыщенной нефти не заданы.")
        for k in range(1, len(p_bar)):
            if p_bar[k] <= p_bar[k - 1]:
                raise ValueError(
                    f"{oil_pvt_file}: в ветви R_s = {Rs:g} м³ст/м³ст давление "
                    f"не растёт строго: {p_mpa[k]:g} МПа после {p_mpa[k - 1]:g} МПа "
                    f"(строки {k} и {k + 1} ветви). Первая строка ветви — "
                    f"насыщенная точка p_b(R_s), дальше давление растёт.")
    # p_b — первая строка ветви, после проверок выше это минимум ветви
    rs_sorted = sorted(branches)
    for Rs_lo, Rs_hi in zip(rs_sorted, rs_sorted[1:]):
        pb_lo, pb_hi = branches[Rs_lo][0], branches[Rs_hi][0]
        if pb_hi <= pb_lo:
            raise ValueError(
                f"{oil_pvt_file}: давление насыщения не растёт с R_s: "
                f"p_b = {pb_hi * BAR_TO_PA / 1e6:g} МПа у ветви R_s = {Rs_hi:g} "
                f"при p_b = {pb_lo * BAR_TO_PA / 1e6:g} МПа у ветви R_s = {Rs_lo:g} "
                f"м³ст/м³ст. p_b — давление первой строки ветви.")


def _check_gas_pvt_table(gas_rows: list[tuple], gas_pvt_file: str) -> None:
    """Таблица газа: ≥ 2 строк, давление строго растёт, иначе ValueError (DEBT-044)."""
    # Правила PVDG (OPM Flow Manual, табл. 8.127). Их же проверяют XLSX-ридер
    # прототипа (input_reader.py:71-72) и BlackOilPVT (pvt.py:32) — последний
    # без имени файла. B_g(p), μ_g(p) интерполируются np.interp по давлению,
    # а он не проверяет рост узлов и на нерастущих молча ошибается.
    # Убывание B_g (PVDG его тоже требует) не проверяется: рост B_g — это
    # c_g < 0, о нём предупреждает _warn_negative_compressibility (BUG-019).
    # Значения столбцов (p, B_g, μ_g > 0) проверены при разборе (_GAS_PVT_LIMITS).
    if len(gas_rows) < 2:
        raise ValueError(
            f"{gas_pvt_file}: строк данных {len(gas_rows)}, нужно не меньше двух: "
            f"B_g и μ_g интерполируются по давлению.")
    for k in range(1, len(gas_rows)):
        # давление в барах — как его получает BlackOilPVT; в сообщении — МПа
        p_prev, p_k = gas_rows[k - 1][0], gas_rows[k][0]
        if p_k <= p_prev:
            raise ValueError(
                f"{gas_pvt_file}: давление не растёт строго: "
                f"{p_k * BAR_TO_PA / 1e6:g} МПа после {p_prev * BAR_TO_PA / 1e6:g} МПа. "
                f"Строки — по возрастанию давления.")


def _check_relperm_table(Sg: list, relperm_file: str) -> None:
    """Таблица ОФП: ≥ 2 строк, S_g строго растёт, иначе ValueError (DEBT-044)."""
    # Правила SGOF (OPM Flow Manual, табл. 8.165). Их же проверяет
    # TabulatedRelPerm (relperm.py:5) — без имени файла; k_ro(S_g), k_rg(S_g)
    # интерполируются np.interp по S_g. Пределы S_g, k_r в [0, 1] проверены
    # при разборе (_RELPERM_LIMITS). Монотонность k_r, которую требует SGOF,
    # не проверяется (решение пользователя 2026-10-07, план DEBT-044).
    if len(Sg) < 2:
        raise ValueError(
            f"{relperm_file}: строк данных {len(Sg)}, нужно не меньше двух: "
            f"k_ro и k_rg интерполируются по S_g.")
    for k in range(1, len(Sg)):
        if Sg[k] <= Sg[k - 1]:
            raise ValueError(
                f"{relperm_file}: S_g не растёт строго: {Sg[k]:g} после {Sg[k - 1]:g}. "
                f"Строки — по возрастанию S_g.")


def _check_undersaturated_start(ic, pvt, rs_tol: float) -> None:
    """Начальное состояние недонасыщенное: Rs0 <= Rs_eq(p0) + rs_tol, иначе ValueError (BUG-017)."""
    # Допуск rs_tol, м³ст/м³ст, — numerics.rs_switch_tol, тот же, что фабрика
    # передаёт решателю (DEBT-008): проверка отвергает ровно те состояния,
    # которые решатель при давлении p0 счёл бы пересыщенными. При умолчании
    # 1e-5 округление ввода не мешает: p0 на 1 Па ниже p_b даёт избыток ~6e-6
    # (Стендинг, Rs0 = 50) и 3e-6 (таблица 0/30).
    # Начальное состояние всегда однофазное (S_g = 0, шаг 8 from_config) —
    # инициализации со свободным газом нет. При Rs0 > Rs_eq(p0) решатель на
    # первом шаге выделяет избыток «в закрытом сосуде», и давление молча
    # скачет почти до p_b(Rs0) (Стендинг, Rs0 = 80, p0 = 10 МПа: 13.78 МПа
    # за час). Критерий через Rs_eq(p0), а не p0 >= p_b(Rs0): у дегазированной
    # нефти табличное p_b(0) условно (5 МПа в демо-таблице), а Rs_eq(p0) = 0 =
    # Rs0 при любом p0 ниже — пересыщения нет.
    Rs_eq = float(pvt.Rs_eq(np.array([ic.p0]))[0])
    if ic.Rs0 > Rs_eq + rs_tol:
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


def create_relperm(config: SimulationConfig):
    """RelPermModel по config.relperm.model; публичная — для диагностики без решателя (DEBT-011)."""
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
        # DEBT-044: те же правила проверяет TabulatedRelPerm, но без имени файла
        _check_relperm_table(Sg, rc.file)

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

    # Порода прототипа (p_ref в бар, cr в 1/бар): φ(p) = porosity·exp(c_r·(p − p0)).
    # Опорное давление — начальное p0: rock.porosity задана при p0, поля p_ref
    # в конфиге нет (DEBT-008).
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
        # Допуски переключения фаз (DEBT-008): газ включается в ячейке при
        # Rs > Rs_eq(p) + rs_switch_tol, выключается при Sg < −sg_switch_tol.
        rs_switch_tol=nc.rs_switch_tol,
        sg_switch_tol=nc.sg_switch_tol,
        jacobian_mode=nc.jacobian_mode,
        linear_solver=nc.linear_solver,
        # BUG-020: четвёртая ступень advance — Ньютон с переключением набора фаз
        # на итерациях; включается только после отказа трёх штатных. У прототипа
        # по умолчанию выключена (его эталон регрессии побитовый), в GPN — всегда.
        phase_switching_stage=True,
        # BUG-022: условие сходимости Ньютона по ячейке. У прототипа по умолчанию
        # выключено (его эталон регрессии побитовый), в GPN — порог из конфига.
        cell_tol=nc.newton_cell_tol,
    )

    # Выход начального состояния за PVT- и ОФП-таблицы (BUG-017): прототип
    # берёт свойства с краёв таблиц без экстраполяции и молча. Только
    # табличная PVT: у HydroPVTtoBlackOilAdapter (Стендинг) нет газовой
    # таблицы gp — pvt_range_warnings упал бы AttributeError.
    if isinstance(pvt, TableFullPVT):
        _warn_initial_table_range(model, ic)

    # Пересчёт потоков (Q, u, m) — тем же объектом FullPVT, что у решателя
    # энергии и Simulator (DEBT-006). Прежде табличный путь разворачивал
    # TableFullPVT до PrototypePVTAdapter проверкой поля _hydro через hasattr;
    # числа те же побитово: TableFullPVT делегирует гидро-методы без
    # арифметики, а rho_o, rho_g — общие методы HydroPVT.
    # Лимиты Ньютона (DEBT-008): адаптер передаёт их в каждый вызов advance
    return PrototypeHydroAdapter(model, grid, pvt,
                                 max_newton=nc.newton_max_iter,
                                 max_active_iter=nc.max_active_set_iter)


def _get_or_create_proto_pvt(pvt, p0: float):
    """Получить BlackOilPVT для RadialBlackOilModel.

    Табличный путь: TableFullPVT → PrototypePVTAdapter → BlackOilPVT (извлечь).
    Аналитический путь (Standing и др.): обернуть HydroPVT через адаптер.
    """
    # DEBT-006: ветку выбирает класс, а не наличие приватных полей. Прежняя
    # проверка поля _hydro через hasattr при переименовании поля молча уводила
    # таблицу в ветку адаптера; теперь переименование свойства — AttributeError.
    if isinstance(pvt, TableFullPVT):
        # Тот же объект, что под обёрткой у наших модулей: один источник PVT
        return pvt.hydro.proto_pvt

    return HydroPVTtoBlackOilAdapter(pvt, p_max_pa=p0)


def _get_or_create_proto_rp(relperm):
    """Получить TabulatedRelPerm для RadialBlackOilModel.

    PrototypeRPAdapter — извлечь TabulatedRelPerm.
    CoreyRP — протабулировать на сетке Sg.
    """
    # DEBT-006: ветка — по классу, как у PVT
    if isinstance(relperm, PrototypeRPAdapter):
        # Тот же TabulatedRelPerm: узлы таблицы, а с ними и порог активации
        # газа sg_activation_cap (BUG-018) — из CSV, а не из пересчёта на 101 узел
        return relperm.proto_rp

    from radial_blackoil.relperm import TabulatedRelPerm
    Sg = np.linspace(0.0, 1.0, 101)
    kro = relperm.kro(Sg)
    krg = relperm.krg(Sg)
    return TabulatedRelPerm(Sg, kro, krg)


# ── CSV-ридеры ──────────────────────────────────────────────

# Столбцы CSV-таблиц в порядке чтения. Значения берутся по позиции, поэтому
# заголовок файла обязан совпасть с этим списком (DEBT-042).
_OIL_PVT_COLUMNS = ["Rs_sm3_sm3", "pressure_Pa", "Bo", "mu_o_Pa_s"]
_GAS_PVT_COLUMNS = ["pressure_Pa", "Bg", "mu_g_Pa_s"]
_RELPERM_COLUMNS = ["Sg", "kro", "krg"]

# Допустимые значения столбцов (DEBT-044): пара (текст для сообщения, проверка).
# lambda v: v > 0 — короткая функция: True, если значение v допустимо.
# Проверяется значение из файла, до перевода единиц: сравнение с 0 и 1 от
# единиц не зависит. Почему такие пределы:
#   - B и μ стоят в знаменателях запасов и подвижностей (blackoil.py:162, 182):
#     ноль — деление на ноль, отрицательное значение — отрицательная масса или
#     подвижность (проба vault/issues/debt-044/probes/red_state.py: при B_o < 0
#     расчёт проходит до конца с T = −246 К и без единого сообщения);
#   - давление абсолютное, R_s — объём растворённого газа: меньше нуля не бывают;
#   - S_g, k_ro, k_rg — доли, [0, 1], как в SGOF (OPM Flow Manual, табл. 8.165)
#     и в CoreyRP (k_r,max ≤ 1, pvt/relperm.py:21).
_POSITIVE = ("> 0", lambda v: v > 0)
_NON_NEGATIVE = ("≥ 0", lambda v: v >= 0)
_FRACTION = ("в [0, 1]", lambda v: 0 <= v <= 1)
_OIL_PVT_LIMITS = {"Rs_sm3_sm3": _NON_NEGATIVE, "pressure_Pa": _POSITIVE,
                   "Bo": _POSITIVE, "mu_o_Pa_s": _POSITIVE}
_GAS_PVT_LIMITS = {"pressure_Pa": _POSITIVE, "Bg": _POSITIVE, "mu_g_Pa_s": _POSITIVE}
_RELPERM_LIMITS = {"Sg": _FRACTION, "kro": _FRACTION, "krg": _FRACTION}


def _read_numeric_csv(csv_path: Path, columns: list[str], limits: dict,
                      kind: str) -> list[tuple]:
    """Строки числовой CSV-таблицы в единицах файла; ошибка в строке → ValueError (DEBT-042)."""
    # До DEBT-042 ошибочная строка пропускалась молча, лишние поля
    # отбрасывались: опечатка удаляла строку таблицы, десятичная запятая
    # сдвигала значения на столбец, у ОФП столбцы расходились по длине.
    # Правила:
    #   - заголовок совпадает с columns (пробелы вокруг имён допустимы):
    #     без проверки файл без заголовка терял первую строку данных;
    #   - пустая строка (нет полей или все поля пустые) пропускается;
    #   - в остальных строках полей ровно len(columns), каждое — конечное
    #     число (float() принимает nan и inf, их отсекает np.isfinite);
    #   - значение в пределах столбца limits[col] (DEBT-044): здесь известен
    #     номер строки файла, после разбора он теряется.
    # Правила таблицы целиком (число строк, рост давления и S_g, ветви R_s)
    # проверяют _check_pvto_branches, _check_gas_pvt_table, _check_relperm_table.
    if not csv_path.exists():
        raise ValueError(f"Файл {kind} не найден: {csv_path}")
    name = csv_path.name
    expected = ",".join(columns)
    rows = []
    # utf-8-sig: BOM (его пишут Excel и «Блокнот») не попадает в имя первого
    # столбца; newline="" — режим open, который требует модуль csv
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"{name}: файл пуст, нужен заголовок {expected}.")
        if [h.strip() for h in header] != columns:
            raise ValueError(
                f"{name}: заголовок {','.join(header)!r}, ожидается {expected!r}. "
                f"Столбцы читаются по порядку, поэтому заголовок обязателен. "
                f"Разделитель столбцов — запятая, десятичный разделитель — точка.")
        for line in reader:
            if not any(field.strip() for field in line):
                continue
            # reader.line_num — номер строки файла (заголовок — строка 1)
            where = f"{name}: строка {reader.line_num}"
            if len(line) != len(columns):
                raise ValueError(
                    f"{where}: число полей {len(line)}, а столбцов в заголовке "
                    f"{len(columns)} ({','.join(line)!r}). Частые причины: десятичная "
                    f"запятая (1,20 вместо 1.20), запятая в конце строки, "
                    f"пропущенное значение.")
            values = []
            for col, field in zip(columns, line):
                try:
                    value = float(field)
                except ValueError:
                    raise ValueError(f"{where}, столбец {col}: {field!r} не число.") from None
                if not np.isfinite(value):
                    raise ValueError(f"{where}, столбец {col}: {field!r} — не конечное число.")
                text, ok = limits[col]
                if not ok(value):
                    raise ValueError(f"{where}, столбец {col}: {field!r} — должно быть {text}.")
                values.append(value)
            rows.append(tuple(values))
    return rows


def _read_oil_pvt_csv(csv_path: Path) -> list[tuple]:
    """Прочитать oil_pvt.csv (SI) → [(Rs, p_bar, Bo, mu_cP), ...].

    CSV: Rs_sm3_sm3, pressure_Pa, Bo, mu_o_Pa_s.
    Конвертация: p Па→бар, μ Па·с→сП.
    """
    rows = _read_numeric_csv(csv_path, _OIL_PVT_COLUMNS, _OIL_PVT_LIMITS, "oil PVT")
    return [(Rs, p / BAR_TO_PA, Bo, mu / CP_TO_PA_S) for Rs, p, Bo, mu in rows]


def _read_gas_pvt_csv(csv_path: Path) -> list[tuple]:
    """Прочитать gas_pvt.csv (SI) → [(p_bar, Bg, mu_cP), ...].

    CSV: pressure_Pa, Bg, mu_g_Pa_s.
    Конвертация: p Па→бар, μ Па·с→сП.
    """
    rows = _read_numeric_csv(csv_path, _GAS_PVT_COLUMNS, _GAS_PVT_LIMITS, "gas PVT")
    return [(p / BAR_TO_PA, Bg, mu / CP_TO_PA_S) for p, Bg, mu in rows]


def _read_relperm_csv(csv_path: Path) -> tuple[list, list, list]:
    """Прочитать relperm.csv → (Sg, kro, krg).

    CSV: Sg, kro, krg. Безразмерные, конвертация не нужна.
    """
    rows = _read_numeric_csv(csv_path, _RELPERM_COLUMNS, _RELPERM_LIMITS, "relperm")
    # Столбцы собираются из целых строк: строку с ошибкой разборщик
    # отвергает до записи, поэтому длины Sg, kro, krg совпадают.
    # Не zip(*rows): на таблице из одного заголовка (rows = []) распаковка
    # падает ValueError без имени файла; так — три пустых списка, и отказ
    # с именем файла даёт _check_relperm_table (DEBT-044)
    Sg = [r[0] for r in rows]
    kro = [r[1] for r in rows]
    krg = [r[2] for r in rows]
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
        dt_after_control_change=config.time.dt_after_control_change,
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
