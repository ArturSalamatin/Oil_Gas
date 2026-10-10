"""PrototypeHydroAdapter — обёртка RadialBlackOilModel → HydroSolver.

Конвертирует:
  - давление: Па ↔ бар (на входе и выходе)
  - режим: gas_active ↔ regime
  - управление: PressureControl → set_bhp_control (Па → бар),
    RateControl → set_oil_rate_control (м³ст/с → м³ст/сут, Па → бар)
  - забойное давление: bhp_bar прототипа → HydroResult.p_wf (Па)

Q, u, m, Gm из потоков компонентов — общий шаг
fluxes.phase_fluxes_from_components, тот же, что у compute_fluxes
(DEBT-028): выбор ячейки выше по потоку — по перепаду давления, как
в прототипе.

НЕ конвертирует:
  - Rs, Sg (безразмерные)
  - Потоки G (м³ст/с — уже SI в прототипе)
  - dt (секунды)

Знаки: инверсия ТОЛЬКО well-потоков (прототип: outflow+, мы: outflow−).
Internal и outer — без инверсии.

Дробления нет: solve — один вызов advance. Не сошёлся —
HydroConvergenceError; шаг дробит Simulator (DEBT-015, P4-адаптивный-шаг.md).
См. P1-адаптер-единицы.md.

Баланс массы (DEBT-039): component_inventories — запас компонентов
функцией прототипа; HydroResult.int_G_* — интегралы потоков через забой
и контур за шаг (подшаг один — dt·G того же состояния).
"""

from dataclasses import replace

import numpy as np

from .base import HydroSolver, HydroConvergenceError
from ..state import SimulationState, HydroResult, BoundaryConditions
from ..grid.base import Grid
from ..pvt.base import HydroPVT
from ..bc import PressureControl, RateControl
from ..units import BAR_TO_PA, DAY_TO_S
from ..fluxes import phase_fluxes_from_components


class PrototypeHydroAdapter(HydroSolver):
    """Adapter: RadialBlackOilModel (бар) → HydroSolver (Па)."""

    def __init__(self, model, grid: Grid, pvt: HydroPVT):
        """
        model       — RadialBlackOilModel, уже сконфигурированный
        grid        — наш Grid (LogRadialGrid)
        pvt         — наш HydroPVT; фабрика передаёт тот же FullPVT, что решателю энергии (DEBT-006)
        """
        self._model = model
        self._grid = grid
        self._pvt = pvt

    def component_inventories(self, state: SimulationState) -> tuple[float, float]:
        """Запас компонентов функцией прототипа, м³ст. Ур. (eq:residual_oil), (eq:residual_gas)."""
        from radial_blackoil.state import BlackOilState

        # Запас берётся у прототипа, а не пересчитывается здесь: те же
        # пористость (rock.py), B_o, B_g и объёмы его сетки, что в невязке
        # Ньютона. Пересчёт своими формулами — механизм BUG-004: баланс
        # сверялся бы не со схемой, а с её копией.
        proto_state = BlackOilState(
            pressure_bar=state.p / BAR_TO_PA,
            rs_sm3_sm3=state.Rs.copy(),
            sg=state.Sg.copy(),
            gas_active=(state.regime == 1),
        )
        oil, gas = self._model.component_inventories(proto_state)
        return float(np.sum(oil)), float(np.sum(gas))

    def solve(self, state: SimulationState, dt: float,
              bc: BoundaryConditions) -> HydroResult:
        """Один шаг advance без дробления; не сошёлся — HydroConvergenceError (DEBT-015)."""
        from radial_blackoil.state import BlackOilState

        # ── Шаг 1: управление скважиной ──
        # Прототип ждёт бар и м³ст/сут; конфиг и WellControl — в СИ.
        well = bc.well
        if isinstance(well, PressureControl):
            self._model.set_bhp_control(well.p_wf / BAR_TO_PA)
        elif isinstance(well, RateControl):
            # Дебит нефти: p_bhp выражается из уравнения притока внутри
            # Ньютона (blackoil.py, _well_fluxes; eq:bc_rate_pwf); min_bhp —
            # нижняя граница, при p[0] <= min_bhp скважина закрыта.
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
            # Дробит шаг Simulator (DEBT-015): делит пополам только этот
            # подшаг и повторяет его из того же состояния. Здесь — факты
            # отказа для журнала; текст для пользователя — в Simulator.
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

        # Интегралы потоков компонентов через забой и контур за шаг, м³ст
        # (DEBT-039). Потоки — на новом состоянии, как в невязке Ньютона
        # (неявная схема). Знаки: у прототипа отток к скважине положителен —
        # инверсия только на забое, как в _build_result: при добыче
        # int_*_well < 0, при притоке с контура int_*_ext < 0. Подшаг один,
        # поэтому интеграл равен dt·G того же состояния.
        f = self._model.face_component_fluxes_sm3s(new_proto)
        result = self._build_result(new_state, new_proto, bc)
        return replace(result,
                       int_G_o_well=dt * (-f['oil_well']),
                       int_G_o_ext=dt * f['oil_outer'],
                       int_G_g_well=dt * (-f['gas_component_well']),
                       int_G_g_ext=dt * f['gas_component_outer'])

    def _build_result(self, new_state: SimulationState,
                      new_proto, bc: BoundaryConditions) -> HydroResult:
        """Шаги 5–9: потоки компонентов из прототипа, Q, u, m, Gm — общим шагом fluxes.py."""
        N = self._grid.N

        # ── Шаг 5+6: потоки + согласование знаков ──
        fluxes = self._model.face_component_fluxes_sm3s(new_proto)

        # G_o: нефтяной компонент, м³ст/с
        # Инверсия ТОЛЬКО well (прототип: outflow+ = к скважине, мы: outflow− = к скважине)
        G_o = np.empty(N + 1)
        G_o[0] = -fluxes['oil_well']
        G_o[1:N] = fluxes['oil_internal']
        G_o[N] = fluxes['oil_outer']

        # G_g: полный газовый компонент (растворённый + свободный), м³ст/с
        G_g = np.empty(N + 1)
        G_g[0] = -fluxes['gas_component_well']
        G_g[1:N] = fluxes['gas_component_internal']
        G_g[N] = fluxes['gas_component_outer']

        # G_free_gas: только свободный газ, м³ст/с
        G_free_gas = np.empty(N + 1)
        G_free_gas[0] = -fluxes['free_gas_well']
        G_free_gas[1:N] = fluxes['free_gas_internal']
        G_free_gas[N] = fluxes['free_gas_outer']

        # ── Шаг 9: фактическое забойное давление ──
        # Результат шага при любом управлении: при OIL_RATE прототип
        # выражает p_bhp из уравнения притока (blackoil.py, _well_fluxes),
        # при BHP и p[0] <= уставки скважина закрыта и p_bhp = p[0].
        # well_rates считает на том же new_proto, что и потоки выше.
        p_wf = self._model.well_rates(new_proto)['bhp_bar'] * BAR_TO_PA

        # ── Шаги 7–8: Q, u, m, Gm — общий шаг с путём тестов (DEBT-028) ──
        # Тот же код, что у compute_fluxes: правило выбора ячейки выше по
        # потоку и формулы записаны в одном месте (fluxes.py).
        return phase_fluxes_from_components(G_o, G_g, G_free_gas,
                                            new_state, self._grid, self._pvt, bc,
                                            p_wf)
