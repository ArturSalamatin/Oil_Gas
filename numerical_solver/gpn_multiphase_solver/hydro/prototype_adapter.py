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

A-retry: при расходимости Newton автоматически дробит dt.
Глубина дробления — numerics.max_retries (2**max_retries подшагов).
См. P1-адаптер-единицы.md, P4-адаптивный-шаг.md.
"""

import numpy as np

from .base import HydroSolver
from ..state import SimulationState, HydroResult, BoundaryConditions
from ..grid.base import Grid
from ..pvt.base import HydroPVT
from ..bc import PressureControl, RateControl
from ..units import BAR_TO_PA, DAY_TO_S
from ..fluxes import phase_fluxes_from_components
from ..log import user_log, dev_log


class PrototypeHydroAdapter(HydroSolver):
    """Adapter: RadialBlackOilModel (бар) → HydroSolver (Па)."""

    def __init__(self, model, grid: Grid, pvt: HydroPVT,
                 max_retries: int = 9):
        """
        model       — RadialBlackOilModel, уже сконфигурированный
        grid        — наш Grid (LogRadialGrid)
        pvt         — наш HydroPVT (PrototypePVTAdapter, обёртка того же BlackOilPVT)
        max_retries — максимум удвоений подшагов при расходимости
                      (9 → до 512 подшагов); задаётся через numerics.max_retries
        """
        self._model = model
        self._grid = grid
        self._pvt = pvt
        self._max_retries = int(max_retries)

    def solve(self, state: SimulationState, dt: float,
              bc: BoundaryConditions) -> HydroResult:
        """Один шаг гидродинамики с A-retry.

        При расходимости автоматически дробит dt на подшаги (2, 4, 8, 16, 32).
        Снаружи — чёрный ящик: state_n → state_{n+1} за dt.
        """
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

        # ── A-retry: подшаги при расходимости ──
        for attempt in range(self._max_retries + 1):
            n_sub = 2 ** attempt
            dt_sub = dt / n_sub

            dev_log.debug(
                f"Hydro attempt {attempt+1}/{self._max_retries+1}: "
                f"{n_sub} substep(s), dt_sub={dt_sub:.2e} s")

            success = True
            current_state = state

            for step in range(n_sub):
                # Шаг 2: SimulationState (Па) → BlackOilState (бар)
                proto_state = BlackOilState(
                    pressure_bar=current_state.p / BAR_TO_PA,
                    rs_sm3_sm3=current_state.Rs.copy(),
                    sg=current_state.Sg.copy(),
                    gas_active=(current_state.regime == 1),
                )

                # Шаг 3: advance
                new_proto, report = self._model.advance(proto_state, dt_sub)

                if not report.converged:
                    dev_log.debug(
                        f"  Substep {step+1}/{n_sub} failed: "
                        f"iters={report.iterations}, res={report.residual_inf:.2e}")
                    success = False
                    break

                # Шаг 4: BlackOilState (бар) → SimulationState (Па)
                current_state = SimulationState(
                    p=new_proto.pressure_bar * BAR_TO_PA,
                    Sg=new_proto.sg.copy(),
                    Rs=new_proto.rs_sm3_sm3.copy(),
                    T=current_state.T.copy(),        # гидро не трогает T
                    regime=np.where(new_proto.gas_active, 1, 2),
                    t=current_state.t + dt_sub,
                )

            if success:
                if attempt > 0:
                    # Сообщаем и о дроблении шага энергии: Simulator повторит
                    # интервал тем же числом подшагов (BUG-010), и это видимо
                    # сказывается на времени расчёта.
                    user_log.info(
                        f"Hydro: converged after {n_sub} substeps "
                        f"(dt_sub={dt_sub:.2e} s); "
                        f"шаг энергии раздроблен на {n_sub} подшагов")

                # Шаг 5–8: потоки и сборка HydroResult.
                # n_sub уходит наружу: энергия обязана пройти столько же
                # подшагов, иначе расщепление применяется на шаге, который
                # гидродинамика признала неустойчивым (BUG-010).
                return self._build_result(current_state, new_proto, bc,
                                          n_substeps=n_sub)

        # Сообщение — факты, а не догадка о причине. Отказ бывает из-за
        # величины шага (DEBT-007, BUG-003: тогда помогает дробление глубже) и
        # не из-за неё (BUG-017 и BUG-018 до исправления, BUG-019: шаг не
        # сходится и при 512-4096 подшагах) — адаптер их не различает.
        # Начало «HydroSolver не сошёлся после N подшагов» цитируют README
        # примеров 03, 06, 07, 10 — не менять. Про dt_integration не пишем:
        # A-retry уже дробит шаг внутри с тем же лимитом.
        n_two = int(np.count_nonzero(state.regime == 1))
        raise RuntimeError(
            f"HydroSolver не сошёлся после {2**self._max_retries} подшагов "
            f"(dt_sub={dt / 2**self._max_retries:.2e} s) на шаге с "
            f"t = {state.t / DAY_TO_S:.4f} сут: двухфазных ячеек {n_two} из "
            f"{state.p.size}, max S_g = {float(np.max(state.Sg)):.3f}. "
            f"Если отказ вызван величиной шага, поможет больший "
            f"numerics.max_retries (сейчас {self._max_retries}, допустимо "
            f"до 20); если шаг не сходится и при мелких подшагах, причина "
            f"не в его величине.")

    def _build_result(self, new_state: SimulationState,
                      new_proto, bc: BoundaryConditions,
                      n_substeps: int = 1) -> HydroResult:
        """Шаги 5–9: потоки компонентов из прототипа, Q, u, m, Gm — общим шагом fluxes.py.

        n_substeps — фактическое дробление A-retry, уходит в HydroResult
        для синхронного дробления шага энергии (BUG-010).
        """
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
                                            p_wf, n_substeps=n_substeps)
