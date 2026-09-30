"""PrototypeHydroAdapter — обёртка RadialBlackOilModel → HydroSolver.

Конвертирует:
  - давление: Па ↔ бар (на входе и выходе)
  - режим: gas_active ↔ regime
  - управление: WellControl → set_bhp_control
  - забойное давление: bhp_bar прототипа → HydroResult.p_wf (Па)

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
from ..bc import PressureControl
from ..units import BAR_TO_PA
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
        well = bc.well
        if isinstance(well, PressureControl):
            self._model.set_bhp_control(well.p_wf / BAR_TO_PA)
        else:
            raise NotImplementedError(
                f"PrototypeHydroAdapter поддерживает только PressureControl, "
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

        # Подсказка называет обе известные первопричины (DEBT-007, BUG-003).
        # Про dt_integration намеренно не пишем: при высокой Sg уменьшение dt
        # не помогает — A-retry уже дробит шаг внутри с тем же лимитом.
        raise RuntimeError(
            f"HydroSolver не сошёлся после {2**self._max_retries} подшагов "
            f"(dt_sub={dt / 2**self._max_retries:.2e} s). "
            f"Увеличьте numerics.max_retries (сейчас {self._max_retries}). "
            f"Более мелкие подшаги требуются при корреляционном PVT "
            f"(нелинейность B_g) и при высокой газонасыщенности "
            f"(обе фазы малоподвижны одновременно).")

    def _build_result(self, new_state: SimulationState,
                      new_proto, bc: BoundaryConditions,
                      n_substeps: int = 1) -> HydroResult:
        """Шаги 5–8: извлечь потоки из прототипа, вычислить Q, u, m, Gm.

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

        # ── Шаг 7: Q, u, m из PVT (единый self._pvt) ──
        p = new_state.p
        Rs = new_state.Rs

        Bo = self._pvt.Bo(p, Rs)
        Bg = self._pvt.Bg(p)
        rho_o = self._pvt.rho_o(p, Rs)
        rho_g = self._pvt.rho_g(p)

        face_area = 2.0 * np.pi * self._grid.h * self._grid.r_faces

        Q_o = np.empty(N + 1)
        Q_g = np.empty(N + 1)
        u_o = np.empty(N + 1)
        u_g = np.empty(N + 1)
        m_o = np.empty(N + 1)
        m_g = np.empty(N + 1)

        # Внутренние грани: upstream по знаку G_o
        for f in range(1, N):
            up = f if G_o[f] < 0 else f - 1
            Q_o[f] = G_o[f] * Bo[up]
            Q_g[f] = G_free_gas[f] * Bg[up]
            u_o[f] = Q_o[f] / face_area[f]
            u_g[f] = Q_g[f] / face_area[f]
            m_o[f] = rho_o[up] * Q_o[f]
            m_g[f] = rho_g[up] * Q_g[f]

        # Забой (f=0): upstream = ячейка 0
        Q_o[0] = G_o[0] * Bo[0]
        Q_g[0] = G_free_gas[0] * Bg[0]
        u_o[0] = Q_o[0] / face_area[0]
        u_g[0] = Q_g[0] / face_area[0]
        m_o[0] = rho_o[0] * Q_o[0]
        m_g[0] = rho_g[0] * Q_g[0]

        # Контур (f=N): upstream зависит от направления
        if G_o[N] < 0:
            # Типичный приток из контура → upstream = контур
            p_ext_a = np.array([bc.p_ext])
            Rs_ext_a = np.array([bc.Rs_ext])
            Bo_up_N = self._pvt.Bo(p_ext_a, Rs_ext_a)[0]
            Bg_up_N = self._pvt.Bg(p_ext_a)[0]
            rho_o_up_N = self._pvt.rho_o(p_ext_a, Rs_ext_a)[0]
            rho_g_up_N = self._pvt.rho_g(p_ext_a)[0]
        else:
            # Отток из пласта → upstream = ячейка N-1
            Bo_up_N = Bo[N - 1]
            Bg_up_N = Bg[N - 1]
            rho_o_up_N = rho_o[N - 1]
            rho_g_up_N = rho_g[N - 1]

        Q_o[N] = G_o[N] * Bo_up_N
        Q_g[N] = G_free_gas[N] * Bg_up_N
        u_o[N] = Q_o[N] / face_area[N]
        u_g[N] = Q_g[N] / face_area[N]
        m_o[N] = rho_o_up_N * Q_o[N]
        m_g[N] = rho_g_up_N * Q_g[N]

        # ── Шаг 8: покомпонентные массовые расходы и сборка ──
        Gm_o = self._pvt.rho_o_std * G_o
        Gm_g = self._pvt.rho_g_std * G_g

        # ── Шаг 9: фактическое забойное давление ──
        # Результат шага при любом управлении: при OIL_RATE прототип
        # выражает p_bhp из уравнения притока (blackoil.py, _well_fluxes),
        # при BHP и p[0] <= уставки скважина закрыта и p_bhp = p[0].
        # well_rates считает на том же new_proto, что и потоки выше.
        p_wf = self._model.well_rates(new_proto)['bhp_bar'] * BAR_TO_PA

        return HydroResult(
            state=new_state,
            G_o=G_o, G_g=G_g, G_free_gas=G_free_gas,
            Q_o=Q_o, Q_g=Q_g,
            u_o=u_o, u_g=u_g,
            m_o=m_o, m_g=m_g,
            Gm_o=Gm_o, Gm_g=Gm_g,
            p_wf=p_wf,
            n_substeps=n_substeps,
        )
