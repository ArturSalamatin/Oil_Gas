"""TridiagEnergySolver — уравнение энергии, прогонка Томаса.

Неявная схема по T: a[j]·T[j-1] + b[j]·T[j] + c[j]·T[j+1] = d[j].
Коэффициенты: eq:tridiag_a … eq:tridiag_d в problem_statement.tex.
Решение: scipy.linalg.solve_banded (LAPACK dgbsv), O(N).

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
  - Забой (f=0): ∂T/∂r = 0 (Нейман) — кондуктивный поток = 0, и
    конвективного вклада забойная грань не даёт (нет перепада T).
    Но JT-вклад там НЕ нулевой: давление p_wf задано на грани.
  - Контур (f=N): T = T_ext (Дирихле)

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

    def __init__(self, grid: Grid, pvt: FullPVT, rock: RockConfig):
        self._grid = grid
        self._pvt = pvt
        self._rock = rock
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
        # Rs_ext — состав притока (eq. bc_Sg_ext: R_s|_ext = R_s^0).
        # p_ext используется ниже, в _ext_properties (eq. bc_props_ext).
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

        # Подшаг 4: кондуктивная проводимость
        Q_T_internal, Q_T_ext = self.compute_conductive_transmissibility(
            props['lambda_eff'], N)

        # Подшаг 5: источники (JT, адиабатический, дегазация)
        J_jt = self.compute_jt(
            Q_o, Q_g, Phi_o, Phi_g, props['mu_JT_o'], props['mu_JT_g'],
            p, N, ext)
        Q_ad = self.compute_adiabatic(
            So, Sg, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'],
            props['mu_JT_o'], props['mu_JT_g'], p, p_old, dt)
        Q_deg = self.compute_degassing(
            So, Sg, Rs, Rs_old, props['Bo'], G_o, props['L'], dt, N, Rs_ext)

        # Баланс энергии накапливается здесь, а не постобработкой (DEBT-013):
        # передаём ровно те коэффициенты, которые следующей строкой уходят
        # в СЛАУ. Восстановить их по разреженной истории нельзя (см. шапку
        # balance.py), а пересчитать заново — значит повторить BUG-004.
        if collect is not None:
            collect.add_substep(
                hydro_result=hydro_result, state_prev=state_prev, dt=dt,
                props=props, Phi_o=Phi_o, Phi_g=Phi_g,
                Q_T_ext=Q_T_ext, J_jt=J_jt, Q_ad=Q_ad, Q_deg=Q_deg,
                T_ext=T_ext)

        # Подшаг 6: сборка СЛАУ
        a, b, c, d = self.assemble_tridiag(
            N, dt, T_old, T_ext,
            props['rho_cp_eff'], Q_T_internal, Q_T_ext,
            Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)

        # Проба (DEBT-016): dt передаётся ФАКТИЧЕСКИЙ — тот, с которым
        # собрана матрица. При A-retry Simulator дробит шаг и вызывает
        # solve с dt_sub = dt/n_sub (BUG-010); шаг расписания здесь уже
        # не при чём, а cap = V·(ρcp)/dt зависит именно от dt_sub.
        if self.matrix_probe is not None:
            self.matrix_probe(a=a, b=b, c=c, d=d, dt=dt,
                              T_old=T_old, hydro_result=hydro_result,
                              state_prev=state_prev, bc=bc)

        # Подшаг 7: решение прогонкой
        T_new = self.solve_banded_system(a, b, c, d, N)

        # Накопление ΔE и кондуктивный член требуют T^{n+1}, поэтому
        # считаются после решения СЛАУ. (ρcp)_eff — та же, что стоит
        # в матрице как cap_j: баланс использует коэффициенты схемы,
        # а не свою версию (DEBT-013).
        if collect is not None:
            collect.add_accumulation(T_new, T_old, props['rho_cp_eff'], dt)

        return T_new

    # ──────────────────────────────────────────────────────
    # Подшаг 1–2: PVT + эффективные свойства в ячейках
    # ──────────────────────────────────────────────────────

    def compute_cell_properties(self, p, Sg, Rs, So, T_old):
        """Тепловые PVT (eq. 5, 7) и вспомогательные величины в ячейках."""
        pvt = self._pvt
        rock = self._rock
        phi = rock.porosity

        Bo = pvt.Bo(p, Rs)
        rho_o = pvt.rho_o(p, Rs)
        rho_g = pvt.rho_g(p)
        c_p_o = pvt.c_p_oil(p, T_old)
        c_p_g = pvt.c_p_gas(p, T_old)
        mu_JT_o = pvt.mu_JT_oil(p, T_old)
        mu_JT_g = pvt.mu_JT_gas(p, T_old)
        L = pvt.L_degas(p, T_old)

        # Эффективная теплоёмкость (eq. 5), Дж/(м³·К)
        rho_cp_eff = ((1 - phi) * rock.rho_cp_solid
                      + phi * (So * rho_o * c_p_o + Sg * rho_g * c_p_g))

        # Эффективная теплопроводность (eq. 7), Вт/(м·К)
        lambda_eff = ((1 - phi) * rock.lambda_solid
                      + phi * (So * rock.lambda_oil + Sg * rock.lambda_gas))

        return dict(
            Bo=Bo, rho_o=rho_o, rho_g=rho_g,
            c_p_o=c_p_o, c_p_g=c_p_g,
            mu_JT_o=mu_JT_o, mu_JT_g=mu_JT_g, L=L,
            rho_cp_eff=rho_cp_eff, lambda_eff=lambda_eff)

    def _ext_properties(self, bc: BoundaryConditions) -> dict:
        """Свойства фаз при условиях контура. Ур. (eq:bc_props_ext).

        На контуре задано: p = p_ext, T = T_ext, Rs = Rs_ext, Sg = 0
        (eq. bc_Sg_ext). При притоке через грань N выше по потоку
        находится контур, поэтому ρ, c_p и μ_JT берутся здесь, а не
        из ячейки N-1 (DEBT-017).

        Sg на контуре не участвует: ни одна тепловая PVT-величина от
        насыщенности не зависит — она входит в поток через k_rg внутри
        Q_g, который приходит готовым из hydro_result.

        PVT принимает массивы, поэтому скаляры оборачиваем и берём [0]
        — как в fluxes.py:47-52. Значения одни на весь шаг, считаются
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
        """Φ_α[f] = ρ_α_up · c_p_α_up · Q_α[f] (eq. 23).
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
        # гидродинамикой по условиям контура (fluxes.py:143-145), и
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
        """Теплопроводность: Q_T = 2πh / (w_L/λ_L + w_R/λ_R).

        Последовательные кольцевые сопротивления R_α = ln(r_face/r_center_α) / (2πh·λ_α).
        Возвращает Q_T_internal [N-1] и Q_T_ext (скаляр).
        """
        grid = self._grid

        # Внутренние грани
        if N > 1:
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
                Q_T_internal = 2.0 * np.pi * grid.h / R_series
        else:
            Q_T_internal = np.empty(0)

        # Контур: λ_face = λ_eff[N-1] (нет ячейки за контуром)
        geom_ext = 2.0 * np.pi * grid.h / np.log(
            grid.R_ext / grid.r_centers[-1])
        Q_T_ext = geom_ext * lambda_eff[-1]

        return Q_T_internal, Q_T_ext

    # ──────────────────────────────────────────────────────
    # Подшаг 5a: JT-поток (eq. 28–29)
    # ──────────────────────────────────────────────────────

    def compute_jt(self, Q_o, Q_g, Phi_o, Phi_g, mu_JT_o, mu_JT_g, p, N, ext):
        """J_face[f] = Σ_α μ_JT_α_up · <Φ_α · p>_f.
        J_jt[j] = J_face[j+1] - J_face[j].
        ext — свойства контура из _ext_properties (eq:bc_props_ext).
        Возвращает J_jt [N].
        """
        J_face = np.zeros(N + 1)

        # Внутренние грани. Выбор ячейки выше по потоку — тот же, что
        # в compute_convective_coefficients (раздельно по фазам).
        # <Φ_α·p>_f = Φ_α⁺·p[f-1] + Φ_α⁻·p[f] — оператор против потока
        # (eq. upstream_operator): при Φ > 0 берётся левая ячейка, при Φ < 0
        # правая; расщепление по знаку делает выбор арифметическим.
        f = np.arange(1, N)
        up_o = np.where(Q_o[f] >= 0, f - 1, f)
        up_g = np.where(Q_g[f] >= 0, f - 1, f)

        J_o = mu_JT_o[up_o] * (np.maximum(Phi_o[f], 0.0) * p[f - 1]
                               + np.minimum(Phi_o[f], 0.0) * p[f])
        J_g = mu_JT_g[up_g] * (np.maximum(Phi_g[f], 0.0) * p[f - 1]
                               + np.minimum(Phi_g[f], 0.0) * p[f])

        J_face[f] = J_o + J_g

        # Забой: <Φ·p> = Φ_well · p[0] (upstream = ячейка 0)
        J_face[0] = (mu_JT_o[0] * Phi_o[0] * p[0]
                     + mu_JT_g[0] * Phi_g[0] * p[0])

        # ── Контур ── ур. (eq:bc_props_ext)
        # Тот же разбор знака, что для Φ выше: при притоке μ_JT и p
        # берутся из ГУ контура. Признак — знак Q_α (не Φ_α): он
        # тождественно тот же, так как Φ_α = ρ_α·c_p_α·Q_α и ρ·c_p > 0,
        # но по Q согласовано с Φ и с compute_degassing — один критерий
        # во всех трёх местах. DEBT-017.
        mu_o_N = mu_JT_o[-1] if Q_o[N] >= 0 else ext['mu_JT_o']
        p_o_N = p[-1] if Q_o[N] >= 0 else ext['p']
        mu_g_N = mu_JT_g[-1] if Q_g[N] >= 0 else ext['mu_JT_g']
        p_g_N = p[-1] if Q_g[N] >= 0 else ext['p']

        J_face[N] = mu_o_N * Phi_o[N] * p_o_N + mu_g_N * Phi_g[N] * p_g_N

        return J_face[1:] - J_face[:-1]

    # ──────────────────────────────────────────────────────
    # Подшаг 5b: адиабатический эффект (eq. 29)
    # ──────────────────────────────────────────────────────

    def compute_adiabatic(self, So, Sg, rho_o, rho_g, c_p_o, c_p_g,
                            mu_JT_o, mu_JT_g, p, p_old, dt):
        """Q_ad[j] = φ · Σ_α S_α · (1 + ρ_α·cp_α·μ_JT_α) · dp/dt, Вт/м³."""
        phi = self._rock.porosity
        dp_dt = (p - p_old) / dt
        return phi * (
            So * (1.0 + rho_o * c_p_o * mu_JT_o) * dp_dt
            + Sg * (1.0 + rho_g * c_p_g * mu_JT_g) * dp_dt)

    # ──────────────────────────────────────────────────────
    # Подшаг 5c: теплота дегазации (eq. 30–31)
    # ──────────────────────────────────────────────────────

    def compute_degassing(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext):
        """Q_deg[j] = -L · mdot[j], Вт/м³.
        mdot — из временной и конвективной частей (eq. 31).
        Rs_ext — состав притока с контура (eq. bc_Sg_ext): R_s|_ext = R_s^0.
        """
        phi = self._rock.porosity
        V = self._grid.volumes
        rho_g_std = self._pvt.rho_g_std

        # Временная часть
        mdot_time = -rho_g_std * phi * So / Bo * (Rs - Rs_old) / dt

        # Конвективная часть: R_conv[f] = <G_o · Rs>_f
        R_conv = np.zeros(N + 1)
        # Внутренние грани: <G^o·Rs>_f = G^o⁺·Rs[f-1] + G^o⁻·Rs[f]
        # (eq. mdot_conv_face + upstream_operator). При оттоке от скважины
        # (G_o > 0) состав берётся из левой ячейки, при притоке — из правой.
        f = np.arange(1, N)
        R_conv[f] = (np.maximum(G_o[f], 0.0) * Rs[f - 1]
                     + np.minimum(G_o[f], 0.0) * Rs[f])
        # Забой
        R_conv[0] = G_o[0] * Rs[0]
        # Контур: upstream зависит от знака потока.
        # Конвенция: G_o > 0 — от скважины (отток), G_o < 0 — приток к скважине.
        if G_o[N] >= 0:
            # Отток наружу: выше по потоку — последняя внутренняя ячейка N-1
            R_conv[N] = G_o[N] * Rs[N - 1]
        else:
            # Приток с контура: выше по потоку — контур, состав задан ГУ
            # (eq. bc_Sg_ext, problem_statement.tex:1469-1472).
            # Брать здесь Rs[N-1] нельзя: при p_{N-1} < p_b это состав
            # дегазированной нефти вместо состава притока (DEBT-009).
            R_conv[N] = G_o[N] * Rs_ext

        mdot_conv = -rho_g_std * (R_conv[1:] - R_conv[:-1]) / V
        mdot = mdot_time + mdot_conv
        return -L * mdot

    # ──────────────────────────────────────────────────────
    # Подшаг 6: сборка трёхдиагональной СЛАУ (eq. 33–36)
    # ──────────────────────────────────────────────────────

    def assemble_tridiag(self, N, dt, T_old, T_ext,
                           rho_cp_eff, Q_T_internal, Q_T_ext,
                           Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg):
        """Собрать коэффициенты a, b, c, d. Применить ГУ. Ур. (eq:tridiag_a)–(eq:tridiag_d)."""
        V = self._grid.volumes

        a = np.zeros(N)
        b = np.zeros(N)
        c = np.zeros(N)
        d = np.zeros(N)

        cap = V * rho_cp_eff / dt  # [N], Вт/К — накопительный член

        # ── Вырожденный случай N = 1 ──
        # Одна ячейка, обе её грани граничные. Левая (забой) конвективного
        # вклада не даёт, правая (контур) даёт его РОВНО ОДИН раз. Ветвь
        # выделена явно: общие блоки ниже писали бы в b[0] дважды, и
        # вторая запись затирала бы первую (постановка, ГУ, случай N = 1).
        if N == 1:
            b[0] = cap[0] + Q_T_ext - Phi_minus[1]
            d[0] = (cap[0] * T_old[0]
                    + Q_T_ext * T_ext
                    + (-Phi_minus[1]) * T_ext
                    + J_jt[0] + V[0] * (Q_ad[0] + Q_deg[0]))
            return a, b, c, d

        # ── Внутренние ячейки (j = 1..N-2) ──
        for j in range(1, N - 1):
            Q_T_L = Q_T_internal[j - 1]
            Q_T_R = Q_T_internal[j]

            a[j] = -Q_T_L - Phi_plus[j]
            c[j] = -Q_T_R + Phi_minus[j + 1]
            # Адвективная форма (BUG-012, eq:tridiag_b): Φ⁺ с ЛЕВОЙ грани j,
            # Φ⁻ с ПРАВОЙ грани j+1 — те же грани, что в a[j] и c[j].
            # Дивергентная версия брала противоположные (Φ⁺ справа, Φ⁻
            # слева), и разность двух версий b[j] равна ровно
            # D_j = Φ_{j+1/2} − Φ_{j−1/2} — паразитному члену T_j·D_j,
            # дублирующему работу расширения газа (она уже в Q_ad и J_jt).
            b[j] = cap[j] + Q_T_L + Q_T_R + Phi_plus[j] - Phi_minus[j + 1]
            d[j] = cap[j] * T_old[j] + J_jt[j] + V[j] * (Q_ad[j] + Q_deg[j])

        # ── ГУ забой (j=0): ∂T/∂r = 0 (Нейман, кондуктивный поток = 0) ──
        # Конвективного вклада забойная грань (индекс 0) не даёт вовсе:
        # слева ячейки нет, а условие Неймана означает отсутствие перепада
        # T через эту грань. В адвективной форме каждое слагаемое
        # пропорционально разности T соседей, поэтому член грани 0
        # тождественно нулевой — из b уходят ОБА слагаемых, что стояли
        # в дивергентной версии (+Phi_plus[0] и -Phi_minus[0]).
        # Физически: вынос флюида с T_0 не создаёт члена при неизвестных —
        # перенос без градиента. Втекание через забой (Phi_plus[0] > 0)
        # для данной постановки не определено — см. DEBT-019.
        Q_T_R0 = Q_T_internal[0]

        a[0] = 0.0
        c[0] = -Q_T_R0 + Phi_minus[1]
        b[0] = cap[0] + Q_T_R0 - Phi_minus[1]
        d[0] = cap[0] * T_old[0] + J_jt[0] + V[0] * (Q_ad[0] + Q_deg[0])

        # ── ГУ контур (j=N-1): T = T_ext (Дирихле) ──
        # Вклад контурной грани: Phi_minus[N]·(T_ext − T_{N-1}). Известная
        # температура уходит в правую часть, поэтому в b остаётся
        # −Phi_minus[N], а в d добавляется (−Phi_minus[N])·T_ext.
        # Слева — вклад грани N-1 по общему правилу.
        Q_T_LN = Q_T_internal[-1]

        a[N - 1] = -Q_T_LN - Phi_plus[N - 1]
        c[N - 1] = 0.0
        b[N - 1] = (cap[N - 1] + Q_T_LN + Q_T_ext
                    + Phi_plus[N - 1] - Phi_minus[N])
        d[N - 1] = (cap[N - 1] * T_old[N - 1]
                    + Q_T_ext * T_ext
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
