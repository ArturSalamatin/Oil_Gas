"""TridiagEnergySolver — уравнение энергии, прогонка Томаса.

Неявная схема по T: a[j]·T[j-1] + b[j]·T[j] + c[j]·T[j+1] = d[j].
Коэффициенты: eq:tridiag_a … eq:tridiag_d в problem_statement.tex.
Решение: scipy.linalg.solve_banded (LAPACK dgbsv), O(N).

СЛАУ решается в отклонениях θ = T − T_ext (DEBT-043): матрица та же,
правая часть собирается от T^n − T_ext, T^{n+1} = θ^{n+1} + T_ext.
В абсолютной T округления сборки и прогонки ~ε·cap·T давали невязку
баланса энергии до 1e-10; в отклонениях — ~1e-15 (см. solve).

ФОРМА ДИСКРЕТИЗАЦИИ — АДВЕКТИВНАЯ (BUG-012). Три пространственных члена
уравнения энергии имеют в постановке одну структуру: скорость, скалярно
умноженная на градиент скаляра, — и все три собираются одинаково, как
вклады граней с РАЗНОСТЬЮ переносимой величины:

    конвекция  Φ^±·ΔT     eq:energy_conv_face
    JT         μ_JT·Φ^±·Δp  eq:QJT_disc
    дегазация  G^{o,±}·ΔRs  eq:mdot_conv_face

Дивергентная сборка (разность потоков через грани) дискретизировала бы
div(Φ·T) вместо Φ·∂T/∂r и давала лишний член T_j·D_j, где
D_j = Φ_{j+1/2} − Φ_{j−1/2}. На сетке он в нуль не обращается: балансы
масс замкнуты по компонентным потокам G^o, G^g, а Φ построен на фазовых
расходах Q_α и содержит множитель ρ·c_p, не входящий ни в один баланс.
Физически D_j отражает сжимаемость, а работа расширения газа уже учтена
дважды — адиабатическим членом и JT.

Кондуктивный член, напротив, остаётся дивергентным: он и в исходном
уравнении стоит под знаком дивергенции, div(λ∇T).

Следствие: сумма конвективных вкладов по ячейкам НЕ сворачивается к
разности потоков через забой и контур — внутренние грани больше не
уничтожаются взаимно. Интегральный баланс энергии считается
суммированием по ячейкам (см. energy/balance.py).

ГУ:
  - Забой (f=0): ∂T/∂r = 0 (Нейман) — кондуктивный поток = 0 (Q_T[0] = 0),
    и конвективного вклада забойная грань не даёт (нет перепада T).
    Но JT-вклад там НЕ нулевой: давление p_wf задано на грани.
  - Контур (f=N): T = T_ext (Дирихле)

Величины на гранях — массивы [N+1] по номеру грани f (грань f разделяет
ячейки f-1 и f): Φ±, Φ_α, Q_T (DEBT-020).

Splitting: p, Sg, Rs заморожены из hydro_result; T — единственная неизвестная.
"""

from typing import TYPE_CHECKING

import numpy as np
from scipy.linalg import solve_banded

from .base import EnergySolver
from ..state import BoundaryConditions, HydroResult, SimulationState
from ..grid.base import Grid
from ..pvt.base import FullPVT
from ..io.config import RockConfig

if TYPE_CHECKING:
    from .balance import EnergyBalanceAccumulator


class TridiagEnergySolver(EnergySolver):
    """Уравнение энергии: конвекция + теплопроводность + JT + адиабатика + дегазация."""

    def __init__(self, grid: Grid, pvt: FullPVT, rock: RockConfig,
                 p_ref: float | None = None):
        self._grid = grid
        self._pvt = pvt
        self._rock = rock
        # Опорное давление закона пористости φ(p) = φ0·exp(c_r·(p − p_ref))
        # (eq:porosity): rock.porosity задана при p_ref. Фабрика передаёт
        # начальное p0 — то же, что получает порода прототипа (factory.py,
        # CompressibleRock): энергия и гидродинамика считают один поровый
        # объём (DEBT-057). При c_r = 0 пористость от p_ref не зависит.
        # rock = None допустим: тесты сверки матрицы создают решатель только
        # ради методов, которым порода не нужна.
        if rock is not None and rock.compressibility != 0.0 and p_ref is None:
            raise ValueError(
                f"TridiagEnergySolver: rock.compressibility = {rock.compressibility} "
                "≠ 0 — нужно p_ref, давление, при котором задана rock.porosity "
                "(фабрика передаёт initial_conditions.p0)")
        self._p_ref = p_ref
        # Проба коэффициентов СЛАУ (DEBT-016). None в production коде;
        # тест выставляет колбэк, чтобы сверить a, b, c, d с эталоном,
        # собранным независимо по problem_statement.tex. Отдаются именно
        # те значения, что уходят в solve_banded_system, — пересобирать
        # их снаружи нельзя, это повторило бы ошибку BUG-004.
        self.matrix_probe = None

    def solve(self, hydro_result: HydroResult,
              state_prev: SimulationState,
              dt: float, bc: BoundaryConditions,
              collect: "EnergyBalanceAccumulator | None" = None) -> np.ndarray:
        N = self._grid.N

        # Граничные условия на контуре: T_ext — Дирихле по температуре,
        # Rs_ext — состав притока (eq:bc_Sg_ext: R_s|_ext = R_s^0).
        # p_ext используется ниже, в _ext_properties (eq:bc_props_ext).
        T_ext = bc.T_ext
        Rs_ext = bc.Rs_ext

        # Состояние после гидро-шага (замороженные коэффициенты)
        p = hydro_result.state.p
        Sg = hydro_result.state.Sg
        Rs = hydro_result.state.Rs
        So = 1.0 - Sg
        T_old = state_prev.T
        p_old = state_prev.p
        Rs_old = state_prev.Rs

        Q_o = hydro_result.Q_o
        Q_g = hydro_result.Q_g
        G_o = hydro_result.G_o

        # Подшаг 1–2: PVT + эффективные свойства
        props = self.compute_cell_properties(p, Sg, Rs, So, T_old)

        # Свойства контура — выше по потоку при притоке (DEBT-017).
        # Считаются один раз на шаг и передаются в оба метода, которые
        # трогают контурную грань: единый источник, иначе Φ и J
        # разойдутся между собой.
        ext = self._ext_properties(bc)

        # Подшаг 3: конвективные коэффициенты Φ на гранях
        Phi_plus, Phi_minus, Phi_o, Phi_g = self.compute_convective_coefficients(
            Q_o, Q_g, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'], N, ext)

        # Подшаг 4: кондуктивная проводимость граней, Q_T [N+1]
        Q_T = self.compute_conductive_transmissibility(props['lambda_eff'], N)

        # Подшаг 5: источники (JT, адиабатический, дегазация)
        # p_wf — фактическое давление на забойной грани после гидро-шага.
        # Берётся из HydroResult, как все гидродинамические величины
        # (FEAT-020): при управлении по дебиту оно известно только после
        # шага. В JT-вклад забойной грани входит с весом Φ⁺ (eq:QJT_disc):
        # при добыче Φ < 0 и вклад нулевой — p_wf влияет на T только при
        # притоке через забой (BUG-015, DEBT-019).
        p_wf = hydro_result.p_wf
        J_jt = self.compute_jt(
            Q_o, Q_g, Phi_o, Phi_g, props['mu_JT_o'], props['mu_JT_g'],
            p, N, ext, p_wf)
        Q_ad = self.compute_adiabatic(
            So, Sg, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'],
            props['mu_JT_o'], props['mu_JT_g'], p, p_old, dt)
        Q_deg = self.compute_degassing(
            So, Sg, Rs, Rs_old, props['Bo'], G_o, props['L'], dt, N, Rs_ext,
            p=p)

        # ── Отсчёт температуры от T_ref = T_ext (DEBT-043) ──
        # СЛАУ решается в отклонениях θ = T − T_ref. Схема та же
        # (eq:tridiag_a…eq:tridiag_d): матрица от T не зависит, а правая
        # часть аффинна по (T^n, T_ext), поэтому assemble_tridiag, получив
        # T^n − T_ref и T_ext − T_ref = 0, сразу даёт d − A·T_ref без
        # вычитания больших чисел. Зачем: в абсолютной T ~ 350 K округления
        # сборки (cap·T_old в d, сумма коэффициентов в b) и обратная ошибка
        # прогонки — порядка ε·cap·T на ячейку, в θ — ε·cap·|θ|. Невязка
        # баланса энергии падает с 1e-14…1e-10 до 0…5e-15, решение
        # сдвигается не больше чем на 4e-11 K (замер 2026-10-07).
        # Свойства (props выше) по-прежнему считаются по абсолютной T_old.
        T_ref = T_ext
        # Точно (лемма Штербенца): T_old и T_ref одного порядка.
        theta_old = T_old - T_ref
        theta_ext = T_ext - T_ref    # = 0.0

        # Баланс энергии накапливается здесь, а не постобработкой (DEBT-013):
        # передаём ровно те коэффициенты, которые следующей строкой уходят
        # в СЛАУ. Восстановить их по разреженной истории нельзя (см. шапку
        # balance.py), а пересчитать заново — значит повторить BUG-004.
        # Температуры — в тех же отклонениях, что и СЛАУ (θ_ext здесь, θ^{n+1}
        # и θ^n после решения): накопитель инвариантен к общему сдвигу —
        # все его члены либо разности T, либо от T не зависят.
        if collect is not None:
            collect.add_substep(
                hydro_result=hydro_result, state_prev=state_prev, dt=dt,
                props=props, Phi_o=Phi_o, Phi_g=Phi_g,
                # Накопителю нужна только контурная грань: внутренние
                # телескопируются, забойная равна нулю (balance.py,
                # add_accumulation).
                Q_T_ext=Q_T[N], J_jt=J_jt, Q_ad=Q_ad, Q_deg=Q_deg,
                T_ext=theta_ext)

        # Подшаг 6: сборка СЛАУ — в отклонениях от T_ref
        a, b, c, d = self.assemble_tridiag(
            N, dt, theta_old, theta_ext,
            props['rho_cp_eff'], Q_T,
            Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)

        # Проба (DEBT-016): dt передаётся ФАКТИЧЕСКИЙ — тот, с которым
        # собрана матрица. При дроблении шага Simulator вызывает solve с
        # подшагом h = dt/2**k (BUG-010, DEBT-015); шаг расписания здесь уже
        # не при чём, а cap = V·(ρcp)/dt зависит именно от подшага.
        # d — в отклонениях от T_ref (DEBT-043): эталон проба сдвигает
        # тем же T_ref; T_old — абсолютная, как в состоянии.
        if self.matrix_probe is not None:
            self.matrix_probe(a=a, b=b, c=c, d=d, dt=dt,
                              T_old=T_old, T_ref=T_ref,
                              hydro_result=hydro_result,
                              state_prev=state_prev, bc=bc)

        # Подшаг 7: решение прогонкой — отклонения θ^{n+1}
        theta_new = self.solve_banded_system(a, b, c, d, N)

        # Накопление ΔE и кондуктивный член требуют T^{n+1}, поэтому
        # считаются после решения СЛАУ. (ρcp)_eff — та же, что стоит
        # в матрице как cap_j: баланс использует коэффициенты схемы,
        # а не свою версию (DEBT-013).
        # Передаются θ, а НЕ записанная T^{n+1} = θ^{n+1} + T_ref (DEBT-043):
        # запись в абсолютной T округляет на ε·T/2 в ячейке, и ΔE по
        # записанным полям вернул бы шум ε·cap·T, от которого сдвиг избавил.
        if collect is not None:
            collect.add_accumulation(theta_new, theta_old,
                                     props['rho_cp_eff'], dt)

        return theta_new + T_ref

    # ──────────────────────────────────────────────────────
    # Пористость φ(p) — поровый объём гидродинамики (DEBT-057)
    # ──────────────────────────────────────────────────────

    def porosity(self, p):
        """Пористость φ(p) = φ0·exp(c_r·(p − p_ref)) в ячейках. Ур. (eq:porosity)."""
        rock = self._rock
        # c_r = 0: скаляр rock.porosity — те же операции, что до DEBT-057,
        # поэтому расчёты с c_r = 0 побитово прежние; p не нужно.
        if rock.compressibility == 0.0:
            return rock.porosity
        if p is None:
            raise ValueError(
                "TridiagEnergySolver.porosity: при rock.compressibility ≠ 0 "
                "нужно давление p в ячейках")
        # Та же формула, что у CompressibleRock прототипа (там в барах):
        # запасы компонентов гидродинамики — V·φ(p)·S_α/B_α
        return rock.porosity * np.exp(rock.compressibility * (p - self._p_ref))

    # ──────────────────────────────────────────────────────
    # Подшаг 1–2: PVT + эффективные свойства в ячейках
    # ──────────────────────────────────────────────────────

    def compute_cell_properties(self, p, Sg, Rs, So, T_old):
        """Тепловые PVT и вспомогательные величины в ячейках.

        Ур. (eq:main_rhocpeff), (eq:lambda_eff).
        """
        pvt = self._pvt
        rock = self._rock
        # Флюид — поровый объём φ(p^{n+1}), как в запасах гидродинамики;
        # скелет — (1 − φ0)(ρc_p)_s: его масса в ячейке постоянна, и от p
        # теплоёмкость скелета не зависит (DEBT-057, eq:rock_dt).
        # λ_eff — эмпирическое замыкание при φ0 (eq:lambda_eff).
        phi0 = rock.porosity
        phi = self.porosity(p)

        Bo = pvt.Bo(p, Rs)
        rho_o = pvt.rho_o(p, Rs)
        rho_g = pvt.rho_g(p)
        c_p_o = pvt.c_p_oil(p, T_old)
        c_p_g = pvt.c_p_gas(p, T_old)
        mu_JT_o = pvt.mu_JT_oil(p, T_old)
        mu_JT_g = pvt.mu_JT_gas(p, T_old)
        L = pvt.L_degas(p, T_old)

        # Эффективная теплоёмкость (eq:main_rhocpeff), Дж/(м³·К)
        rho_cp_eff = ((1 - phi0) * rock.rho_cp_solid
                      + phi * (So * rho_o * c_p_o + Sg * rho_g * c_p_g))

        # Эффективная теплопроводность (eq:lambda_eff), Вт/(м·К)
        lambda_eff = ((1 - phi0) * rock.lambda_solid
                      + phi0 * (So * rock.lambda_oil + Sg * rock.lambda_gas))

        return dict(
            Bo=Bo, rho_o=rho_o, rho_g=rho_g,
            c_p_o=c_p_o, c_p_g=c_p_g,
            mu_JT_o=mu_JT_o, mu_JT_g=mu_JT_g, L=L,
            rho_cp_eff=rho_cp_eff, lambda_eff=lambda_eff)

    def _ext_properties(self, bc: BoundaryConditions) -> dict:
        """Свойства фаз при условиях контура. Ур. (eq:bc_props_ext).

        На контуре задано: p = p_ext, T = T_ext, Rs = Rs_ext, Sg = 0
        (eq:bc_Sg_ext). При притоке через грань N выше по потоку
        находится контур, поэтому ρ, c_p и μ_JT берутся здесь, а не
        из ячейки N-1 (DEBT-017).

        Sg на контуре не участвует: ни одна тепловая PVT-величина от
        насыщенности не зависит — она входит в поток через k_rg внутри
        Q_g, который приходит готовым из hydro_result.

        PVT принимает массивы, поэтому скаляры оборачиваем и берём [0]
        — как в fluxes.py (свойства контура). Значения одни на весь шаг, считаются
        один раз в solve и передаются в оба метода: единый источник,
        иначе Φ и J разойдутся между собой.
        """
        pvt = self._pvt
        p_a = np.array([bc.p_ext])
        T_a = np.array([bc.T_ext])
        Rs_a = np.array([bc.Rs_ext])

        return dict(
            p=bc.p_ext,
            rho_o=pvt.rho_o(p_a, Rs_a)[0],
            rho_g=pvt.rho_g(p_a)[0],
            c_p_o=pvt.c_p_oil(p_a, T_a)[0],
            c_p_g=pvt.c_p_gas(p_a, T_a)[0],
            mu_JT_o=pvt.mu_JT_oil(p_a, T_a)[0],
            mu_JT_g=pvt.mu_JT_gas(p_a, T_a)[0])

    # ──────────────────────────────────────────────────────
    # Подшаг 3: конвективные коэффициенты Φ на гранях
    # ──────────────────────────────────────────────────────

    def compute_convective_coefficients(self, Q_o, Q_g, rho_o, rho_g,
                                          c_p_o, c_p_g, N, ext):
        """Φ_α[f] = ρ_α_up · c_p_α_up · Q_α[f] (определение под eq:energy_conv_face).
        Против потока раздельно по каждой фазе (по знаку Q_α).
        ext — свойства контура из _ext_properties (eq:bc_props_ext).
        Возвращает Φ⁺, Φ⁻, Φ_o, Φ_g — все [N+1].
        """
        Phi_o = np.zeros(N + 1)
        Phi_g = np.zeros(N + 1)

        # Внутренние грани. Грань f разделяет ячейки f-1 (слева) и f (справа).
        # Конвенция знаков: Q >= 0 — течение от скважины, слева направо, выше
        # по потоку левая ячейка f-1; Q < 0 — к скважине, выше по потоку f.
        # Ноль отнесён к левой ветке (>=): при Q = 0 вклад нулевой, выбор
        # ячейки ни на что не влияет.
        f = np.arange(1, N)
        up_o = np.where(Q_o[f] >= 0, f - 1, f)
        up_g = np.where(Q_g[f] >= 0, f - 1, f)

        Phi_o[f] = rho_o[up_o] * c_p_o[up_o] * Q_o[f]
        Phi_g[f] = rho_g[up_g] * c_p_g[up_g] * Q_g[f]

        # Забой (f=0): upstream = ячейка 0
        Phi_o[0] = rho_o[0] * c_p_o[0] * Q_o[0]
        Phi_g[0] = rho_g[0] * c_p_g[0] * Q_g[0]

        # ── Контур (f=N) ── ур. (eq:bc_props_ext)
        # Выше по потоку зависит от знака расхода, как и на внутренних
        # гранях: Q >= 0 — отток наружу, свойства из ячейки N-1;
        # Q < 0 (штатный приток) — выше по потоку контур, свойства при
        # условиях ГУ. Брать N-1 при притоке нельзя: Q_α уже посчитан
        # гидродинамикой по условиям контура (fluxes.py, phase_fluxes_from_components), и
        # произведение ρ·c_p·Q вышло бы из двух разных состояний.
        # Тот же разбор знака, что в compute_degassing (DEBT-009).
        if Q_o[N] >= 0:
            Phi_o[N] = rho_o[N - 1] * c_p_o[N - 1] * Q_o[N]
        else:
            Phi_o[N] = ext['rho_o'] * ext['c_p_o'] * Q_o[N]

        if Q_g[N] >= 0:
            Phi_g[N] = rho_g[N - 1] * c_p_g[N - 1] * Q_g[N]
        else:
            # Свободного газа на контуре нет (Sg|ext = 0, k_rg = 0),
            # поэтому Q_g[N] = 0 и вклад нулевой при любых ρ_g, c_p_g.
            # Значения всё равно считаются по формуле, а не подставляются
            # нулём: ветвь останется верной, если появится конфиг
            # с Sg_ext > 0.
            Phi_g[N] = ext['rho_g'] * ext['c_p_g'] * Q_g[N]

        Phi_plus = np.maximum(Phi_o, 0) + np.maximum(Phi_g, 0)
        Phi_minus = np.minimum(Phi_o, 0) + np.minimum(Phi_g, 0)

        return Phi_plus, Phi_minus, Phi_o, Phi_g

    # ──────────────────────────────────────────────────────
    # Подшаг 4: кондуктивная проводимость граней
    # ──────────────────────────────────────────────────────

    def compute_conductive_transmissibility(self, lambda_eff, N):
        """Проводимости граней Q_T [N+1], Вт/К. Ур. (eq:heat_cond_disc) problem_statement.tex."""
        grid = self._grid

        # Индекс — номер грани, как у Phi_plus/Phi_minus (DEBT-020): грань f
        # разделяет ячейки f-1 и f.
        #   Q_T[0] = 0       — забой, ГУ Неймана (ssec:bc_disc): кондуктивного
        #                      потока в скважину нет при любой T за гранью;
        #   Q_T[1..N-1]      — внутренние грани;
        #   Q_T[N]           — контур.
        Q_T = np.zeros(N + 1)

        # Внутренние грани. При N = 1 их нет: веса сетки и срезы λ пустые,
        # срез Q_T[1:1] тоже — отдельная ветвь не нужна.
        w_L = grid.log_weights_left    # ln(r_face / r_center_left)
        w_R = grid.log_weights_right   # ln(r_center_right / r_face)
        lam_L = lambda_eff[:-1]
        lam_R = lambda_eff[1:]
        # Последовательные кольцевые сопротивления: R = w/λ, Q_T = 2πh / ΣR.
        # При λ = 0 (конфиг без теплопроводности) сопротивление бесконечно,
        # а проводимость — ноль. Считаем через errstate, чтобы промежуточные
        # inf не печатали предупреждение: 2πh/inf = 0 — верный ответ.
        with np.errstate(divide='ignore'):
            R_series = w_L / lam_L + w_R / lam_R
            Q_T[1:N] = 2.0 * np.pi * grid.h / R_series

        # Контур: λ_face = λ_eff[N-1] (нет ячейки за контуром)
        geom_ext = 2.0 * np.pi * grid.h / np.log(
            grid.R_ext / grid.r_centers[-1])
        Q_T[N] = geom_ext * lambda_eff[-1]

        return Q_T

    # ──────────────────────────────────────────────────────
    # Подшаг 5a: JT-вклад (eq:QJT_disc, адвективная форма)
    # ──────────────────────────────────────────────────────

    def compute_jt(self, Q_o, Q_g, Phi_o, Phi_g, mu_JT_o, mu_JT_g, p, N, ext,
                   p_wf):
        """Вклад JT в адвективной форме. Ур. (eq:QJT_disc).

        J_jt[j] = Σ_α [ μ_JT_α^{j-1/2}·Φ_α⁺_{j-1/2}·(p[j] − p[j-1])
                      + μ_JT_α^{j+1/2}·Φ_α⁻_{j+1/2}·(p[j+1] − p[j]) ]  [Вт]

        Каждое слагаемое содержит ПЕРЕПАД давления на грани, а не само p:
        источник (eq:main_QJT_muJT) записан поточечно, через градиент
        давления. Прежняя форма J_jt[j] = J_face[j+1] − J_face[j] с
        J_face = Σ_α μ_JT·<Φ_α·p> дискретизировала div(μ_JT·Φ·p) и давала
        лишний член μ_JT·p[j]·D_j (BUG-012).

        При однородном p член обращается в нуль тождественно.

        p_wf — давление на забойной грани (HydroResult.p_wf). В отличие от
        температуры и состава, давление за забоем известно, поэтому
        забойная грань даёт НЕнулевой вклад: перепад (p[0] − p_wf) реален
        и создаёт дросселирование. Поправки на полушаг не требуется —
        длина пути учтена в Φ через проводимость грани.

        ext — свойства контура из _ext_properties (eq:bc_props_ext).
        Возвращает J_jt [N].
        """
        # Давление «за гранью» для каждой из N+1 граней:
        #   грань 0   — забой, p_wf шага (HydroResult.p_wf);
        #   грань f   — центр ячейки f-1 слева и ячейки f справа;
        #   грань N   — контур, значение из ГУ (ext['p']).
        p_left = np.concatenate(([p_wf], p))        # [N+1]: слева от грани
        p_right = np.concatenate((p, [ext['p']]))   # [N+1]: справа от грани

        # Ячейка выше по потоку — та же, что в compute_convective_coefficients
        # (раздельно по фазам, по знаку Q_α). Для забойной грани upstream —
        # ячейка 0 при любом знаке: слева ячеек нет.
        f = np.arange(1, N)
        up_o = np.zeros(N + 1, dtype=int)
        up_g = np.zeros(N + 1, dtype=int)
        up_o[f] = np.where(Q_o[f] >= 0, f - 1, f)
        up_g[f] = np.where(Q_g[f] >= 0, f - 1, f)
        up_o[N] = N - 1
        up_g[N] = N - 1

        mu_o_face = mu_JT_o[up_o]
        mu_g_face = mu_JT_g[up_g]

        # ── Контур ── ур. (eq:bc_props_ext)
        # При притоке μ_JT берётся при условиях контура. Признак — знак
        # Q_α (не Φ_α): он тождественно тот же, так как Φ_α = ρ_α·c_p_α·Q_α
        # и ρ·c_p > 0, но по Q согласовано с Φ и с compute_degassing —
        # один критерий во всех трёх местах. DEBT-017.
        if Q_o[N] < 0:
            mu_o_face[N] = ext['mu_JT_o']
        if Q_g[N] < 0:
            mu_g_face[N] = ext['mu_JT_g']

        # Вклад левой грани j (Φ⁺ > 0) и правой грани j+1 (Φ⁻ < 0).
        # Индексы: для ячейки j левая грань имеет индекс j, правая — j+1.
        Phi_o_p = np.maximum(Phi_o, 0.0)
        Phi_g_p = np.maximum(Phi_g, 0.0)
        Phi_o_m = np.minimum(Phi_o, 0.0)
        Phi_g_m = np.minimum(Phi_g, 0.0)

        dp_left = p - p_left[0:N]          # [N]: p[j] − (значение слева)
        dp_right = p_right[1:N + 1] - p    # [N]: (значение справа) − p[j]

        J_jt = (mu_o_face[0:N] * Phi_o_p[0:N] * dp_left
                + mu_g_face[0:N] * Phi_g_p[0:N] * dp_left
                + mu_o_face[1:N + 1] * Phi_o_m[1:N + 1] * dp_right
                + mu_g_face[1:N + 1] * Phi_g_m[1:N + 1] * dp_right)

        return J_jt

    # ──────────────────────────────────────────────────────
    # Подшаг 5b: адиабатический эффект (eq:Qad_disc; φ = φ(p^{n+1}), DEBT-057)
    # ──────────────────────────────────────────────────────

    def compute_adiabatic(self, So, Sg, rho_o, rho_g, c_p_o, c_p_g,
                            mu_JT_o, mu_JT_g, p, p_old, dt):
        """Q_ad[j] = φ(p)·Σ_α S_α·(1 + ρ_α·cp_α·μ_JT_α)·dp/dt, Вт/м³. Ур. (eq:Qad_disc)."""
        # Сжимаемость породы — только через φ(p): членов c_r·(p + (ρc_p)_s·T)
        # в Q_ad нет (eq:rock_dt, DEBT-057)
        phi = self.porosity(p)
        dp_dt = (p - p_old) / dt
        return phi * (
            So * (1.0 + rho_o * c_p_o * mu_JT_o) * dp_dt
            + Sg * (1.0 + rho_g * c_p_g * mu_JT_g) * dp_dt)

    # ──────────────────────────────────────────────────────
    # Подшаг 5c: теплота дегазации (eq:Qdeg_disc, eq:mdot_disc,
    # eq:mdot_conv_face — адвективная пространственная часть)
    # ──────────────────────────────────────────────────────

    def compute_degassing(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext,
                          p=None):
        """Q_deg[j] = -L · mdot[j], Вт/м³. Ур. (eq:mdot_disc), (eq:mdot_conv_face).

        Пространственная часть — в АДВЕКТИВНОЙ форме (BUG-012):

            R_adv[j] = G^o⁺_{j-1/2}·(Rs[j] − Rs[j-1])
                     + G^o⁻_{j+1/2}·(Rs[j+1] − Rs[j])

        Каждое слагаемое содержит РАЗНОСТЬ Rs на грани: источник
        (u_o/B_o)·∂Rs/∂r записан поточечно, через градиент состава.
        Прежняя форма (R_conv[f+1] − R_conv[f]) с R_conv = <G^o·Rs>
        дискретизировала div(G^o·Rs) и давала лишний член
        Rs[j]·(G^o_{j+1/2} − G^o_{j-1/2}).

        При однородном Rs член обращается в нуль тождественно — это и есть
        утверждение постановки о том, что в однофазной зоне (Rs = Rs0)
        mdot = 0 автоматически.

        Где берётся B_o: во временном члене из текущей ячейки, в
        пространственном множитель 1/B_o сидит внутри G^o и снесён по
        потоку. Асимметрия намеренная: временной член — ЗАПАС нефти в
        ячейке, пространственный — ПОТОК через грань. Пространственная
        часть воспроизводит дискретное тождество Лейбница для потоков
        точно (невязка ~1e-15); вариант с общим множителем 1/B_o[j]
        даёт ~5e-3.

        Временная часть берёт запас нефти φ·S_o/B_o слоя n+1, как все
        величины шага. Выделение газа гидродинамики (неявный перенос с
        R_s^{n+1}) соответствует запасу слоя n, поэтому ṁ отличается от
        него на −ρ_g^ст·ΔR_s·Δ(φ·S_o/B_o)/Δt в ячейке — первый порядок
        по Δt. Слой n не взят: остатки той же природы в накоплении и Q_ad
        больше и противоположного знака (DEBT-066, отложена; постановка —
        абзац о временной части после eq:mdot_disc).

        Rs_ext — состав притока с контура (eq:bc_Sg_ext): R_s|_ext = R_s^0.
        """
        # Запас нефти во временной части — с пористостью φ(p^{n+1}) (eq:porosity),
        # как в запасах гидродинамики (DEBT-057); при c_r = 0 p не нужно.
        phi = self.porosity(p)
        V = self._grid.volumes
        rho_g_std = self._pvt.rho_g_std

        # Временная часть — запас нефти слоя n+1 (eq:mdot_disc). С балансом
        # массы гидродинамики точно согласован запас слоя n; разница первого
        # порядка по Δt, слой n не взят — см. докстринг (DEBT-066).
        mdot_time = -rho_g_std * phi * So / Bo * (Rs - Rs_old) / dt

        # Пространственная часть: перенос Rs потоком нефтяного компонента.
        # Расщепление по знаку G^o — тот же критерий, что в
        # compute_convective_coefficients и compute_jt.
        Gp = np.maximum(G_o, 0.0)
        Gm = np.minimum(G_o, 0.0)

        # Состав соседей. Слева от ячейки 0 ячейки нет и ГУ по Rs на забое
        # тоже нет, поэтому ячейка назначается сама себе левым соседом:
        # разность Rs[0] − Rs[0] = 0, и забойная грань вклада не даёт при
        # ЛЮБОМ знаке потока. Отдельной ветви для этого не требуется.
        # Справа от ячейки N-1 — контур, состав задан ГУ (eq:bc_Sg_ext).
        # Брать Rs[N-1] нельзя: при p_{N-1} < p_b это состав дегазированной
        # нефти вместо состава притока (DEBT-009).
        Rs_left = np.concatenate(([Rs[0]], Rs[:-1]))
        Rs_right = np.concatenate((Rs[1:], [Rs_ext]))

        R_adv = Gp[0:N] * (Rs - Rs_left) + Gm[1:N + 1] * (Rs_right - Rs)

        mdot_conv = -rho_g_std * R_adv / V
        mdot = mdot_time + mdot_conv
        return -L * mdot

    # ──────────────────────────────────────────────────────
    # Подшаг 6: сборка трёхдиагональной СЛАУ
    # (eq:tridiag_a … eq:tridiag_d, адвективная форма)
    # ──────────────────────────────────────────────────────

    def assemble_tridiag(self, N, dt, T_old, T_ext,
                         rho_cp_eff, Q_T,
                         Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg):
        """Коэффициенты a, b, c, d с ГУ. Ур. (eq:tridiag_a)–(eq:tridiag_d) problem_statement.tex."""
        V = self._grid.volumes

        cap = V * rho_cp_eff / dt  # [N], Вт/К — накопительный член

        # ── Все строки по eq:tridiag_a … eq:tridiag_c ──
        # Ячейка j ограничена гранями j (слева) и j+1 (справа). Q_T и Φ±
        # индексируются номером грани [N+1], поэтому срез [:-1] — левые
        # грани ячеек, [1:] — правые. Q_T[0] = 0 (Нейман на забое), и общие
        # формулы верны на всех строках, включая j = 0 и N = 1: отдельной
        # ветви для одной ячейки нет (DEBT-020). Граничные условия ниже —
        # точечные поправки к собранным массивам; при N = 1 они относятся к
        # одной строке и складываются, а не затирают друг друга.
        #
        # Порядок сложения в b тот же, что в прежнем цикле по ячейкам, а в
        # строку 0 прибавляется точный ноль Q_T[0]: результат побитово
        # прежний (проба vault/issues/debt-020/probes, все 23 примера).
        a = -Q_T[:-1] - Phi_plus[:-1]
        c = -Q_T[1:] + Phi_minus[1:]

        # Адвективная форма (BUG-012, eq:tridiag_b): Φ⁺ с ЛЕВОЙ грани j,
        # Φ⁻ с ПРАВОЙ грани j+1 — те же грани, что в a[j] и c[j].
        # Дивергентная версия брала противоположные (Φ⁺ справа, Φ⁻
        # слева), и разность двух версий b[j] равна ровно
        # D_j = Φ_{j+1/2} − Φ_{j−1/2} — паразитному члену T_j·D_j,
        # дублирующему работу расширения газа (она уже в Q_ad и J_jt).
        b = cap + Q_T[:-1]
        b += Q_T[1:]
        # Φ⁺ забойной грани (индекс 0) в b[0] не входит — см. ГУ забоя
        b[1:] += Phi_plus[1:N]
        b -= Phi_minus[1:]

        d = cap * T_old + J_jt + V * (Q_ad + Q_deg)

        # ── ГУ забой (j=0): ∂T/∂r = 0 (Нейман, кондуктивный поток = 0) ──
        # Кондуктивный вклад грани 0 уже нулевой: Q_T[0] = 0.
        # Конвективного вклада забойная грань (индекс 0) не даёт вовсе:
        # слева ячейки нет, а условие Неймана означает отсутствие перепада
        # T через эту грань. В адвективной форме каждое слагаемое
        # пропорционально разности T соседей, поэтому член грани 0
        # тождественно нулевой — Φ⁺[0] не входит ни в a[0], ни в b[0]
        # (выше: b[1:]). Физически: вынос флюида с T_0 не создаёт члена при
        # неизвестных — перенос без градиента. Втекание через забой
        # (Phi_plus[0] > 0) для данной постановки не определено — см. DEBT-019.
        a[0] = 0.0

        # ── ГУ контур (j=N-1): T = T_ext (Дирихле) ──
        # Вклад контурной грани: (Q_T[N] − Phi_minus[N])·(T_ext − T_{N-1}).
        # Множитель при T_{N-1} уже в b[N-1] (общая формула), известная
        # T_ext уходит в правую часть, связи справа нет.
        # d[N-1] пересобирается целиком, а не дополняется: порядок
        # слагаемых — прежний (побитово).
        c[N - 1] = 0.0
        d[N - 1] = (cap[N - 1] * T_old[N - 1]
                    + Q_T[N] * T_ext
                    + (-Phi_minus[N]) * T_ext
                    + J_jt[N - 1]
                    + V[N - 1] * (Q_ad[N - 1] + Q_deg[N - 1]))

        return a, b, c, d

    # ──────────────────────────────────────────────────────
    # Подшаг 7: решение прогонкой
    # ──────────────────────────────────────────────────────

    @staticmethod
    def solve_banded_system(a, b, c, d, N):
        """Решение трёхдиагональной СЛАУ через LAPACK dgbsv."""
        ab = np.zeros((3, N))
        ab[0, 1:] = c[:-1]    # верхняя диагональ
        ab[1, :] = b           # главная диагональ
        ab[2, :-1] = a[1:]     # нижняя диагональ
        return solve_banded((1, 1), ab, d)
