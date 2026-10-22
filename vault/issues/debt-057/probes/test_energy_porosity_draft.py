"""Пористость φ(p) в уравнении энергии — та же, что в запасах гидродинамики (DEBT-057).

Гидродинамика (прототип radial_blackoil, CompressibleRock) считает поровый объём
V·φ(p), φ(p) = φ0·exp(c_r·(p − p0)) (eq:porosity). До DEBT-057 энергия брала
постоянную φ0 = rock.porosity: при c_r ≠ 0 теплоёмкость флюида, адиабатический
член и временная часть ṁ считались с другим поровым объёмом, чем баланс массы.
Теперь флюид — φ(p^{n+1}); скелет — (1 − φ0)(ρc_p)_s: масса скелета в ячейке
постоянна (eq:rock_dt); λ_eff — эмпирическое замыкание при φ0 (eq:lambda_eff).

Сжимаемость в тестах — как в примере 18 (книга прототипа): c_r = 4.5e-10 1/Па.
"""

from pathlib import Path

import numpy as np
import pytest
from radial_blackoil.rock import CompressibleRock

from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.io.config import RockConfig, load_config
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.units import BAR_TO_PA

EXAMPLE_18 = Path(__file__).parent.parent / "examples" / "18_prototype_input" / "config.json"

N = 5
P0 = 20e6          # опорное давление пористости — начальное, Па
PHI0 = 0.2
C_R = 4.5e-10      # 1/Па — пример 18
RS0 = 50.0
T0 = 350.0
DT = 3600.0
# Давление в ячейках: Δp до 10 МПа, φ(p)/φ0 − 1 до −0.45 %
P = np.array([10e6, 12e6, 15e6, 18e6, 20e6])


def _rock(c_r=C_R):
    return RockConfig(porosity=PHI0, permeability=1e-13, rho_cp_solid=1.25e6,
                      lambda_solid=1.5, lambda_oil=0.14, lambda_gas=0.04,
                      compressibility=c_r)


def _pvt():
    return StandingFullPVT(rho_o_std=850.0, rho_g_std=0.85, T0=T0, Rs0=RS0,
                           co_undersaturated=0.0, c_p_oil=2000.0, c_p_gas=2850.0,
                           mu_JT_oil_val=-4e-7, mu_JT_gas_val=4e-6,
                           L_degas_val=230000.0)


def _solver(c_r=C_R, p_ref=P0):
    """Решатель энергии на N ячейках; c_r = 0, p_ref = None — прежняя постоянная пористость."""
    grid = LogRadialGrid(0.1, 100.0, 10.0, N, 1e-13)
    return TridiagEnergySolver(grid, _pvt(), _rock(c_r), p_ref=p_ref)


def _phi(p):
    """φ(p) по eq:porosity — независимо от кода решателя."""
    return PHI0 * np.exp(C_R * (p - P0))


# ═══════════════════════════════════════════════════════════
# A. Закон пористости
# ═══════════════════════════════════════════════════════════

class TestPorosityLaw:
    """TridiagEnergySolver.porosity(p) — закон породы прототипа с опорой p0."""

    def test_matches_prototype_rock(self):
        """φ(p) энергии совпадает с CompressibleRock прототипа при той же тройке (φ0, p0, c_r).

        Прототип считает в барах: φ_ref·exp(c_r[1/бар]·(p[бар] − p_ref[бар])).
        Формулы в Па и в барах совпадают до округления — замер пробы DEBT-057
        на примере 18: 2.2e-16. Ловит: другой знак показателя, опорное
        давление не p0, c_r без перевода единиц.
        """
        rock = CompressibleRock(PHI0, P0 / BAR_TO_PA, C_R * BAR_TO_PA)
        np.testing.assert_allclose(_solver().porosity(P), rock.porosity(P / BAR_TO_PA),
                                   rtol=1e-14, atol=0.0)

    def test_zero_compressibility_returns_phi0(self):
        """c_r = 0: φ — скаляр rock.porosity без p_ref; расчёты с c_r = 0 побитово прежние."""
        solver = _solver(c_r=0.0, p_ref=None)
        phi = solver.porosity(P)
        assert np.ndim(phi) == 0 and phi == PHI0

    def test_compressible_requires_p_ref(self):
        """c_r ≠ 0 без p_ref — отказ при создании: опорное давление пористости не определено."""
        grid = LogRadialGrid(0.1, 100.0, 10.0, N, 1e-13)
        with pytest.raises(ValueError, match="p_ref"):
            TridiagEnergySolver(grid, _pvt(), _rock(), p_ref=None)


# ═══════════════════════════════════════════════════════════
# B. Члены уравнения энергии
# ═══════════════════════════════════════════════════════════

class TestEnergyTerms:
    """Где стоит φ(p), а где φ0: (ρc_p)_eff, λ_eff, Q_ad, временная часть ṁ."""

    SG = np.array([0.0, 0.05, 0.1, 0.0, 0.0])

    def _props(self, solver):
        So = 1.0 - self.SG
        return solver.compute_cell_properties(P, self.SG, np.full(N, RS0), So, np.full(N, T0))

    def test_rho_cp_eff_fluid_phi_p_skeleton_phi0(self):
        """(ρc_p)_eff = (1 − φ0)(ρc_p)_s + φ(p)·Σ S_α ρ_α c_p,α; λ_eff от p не зависит.

        eq:main_rhocpeff, eq:lambda_eff. Скелет: масса в ячейке постоянна —
        множитель 1 − φ0, а не 1 − φ(p). λ_eff — замыкание при φ0. Ловит: φ(p)
        у скелета или в λ_eff, φ0 у флюида.
        """
        props = self._props(_solver())
        So = 1.0 - self.SG
        fluid = So * props['rho_o'] * props['c_p_o'] + self.SG * props['rho_g'] * props['c_p_g']
        np.testing.assert_allclose(props['rho_cp_eff'], (1 - PHI0) * 1.25e6 + _phi(P) * fluid,
                                   rtol=1e-14)
        lam0 = self._props(_solver(c_r=0.0, p_ref=None))['lambda_eff']
        np.testing.assert_array_equal(props['lambda_eff'], lam0)

    def test_adiabatic_scales_with_phi_p(self):
        """Q_ad при c_r ≠ 0 — Q_ad при c_r = 0, умноженный на φ(p^{n+1})/φ0 (eq:Qad_disc).

        Членов c_r(p + (ρc_p)_s T) нет — артефакты прежнего вывода (eq:rock_dt):
        сжимаемость входит только через φ(p). Давление старого слоя на 1 МПа выше:
        dp/dt ≠ 0. Ловит: φ0 вместо φ(p), φ(p_old) вместо φ(p_new), возврат
        члена с c_r.
        """
        props = self._props(_solver())
        So = 1.0 - self.SG
        args = (So, self.SG, props['rho_o'], props['rho_g'], props['c_p_o'], props['c_p_g'],
                props['mu_JT_o'], props['mu_JT_g'], P, P + 1e6, DT)
        q = _solver().compute_adiabatic(*args)
        q0 = _solver(c_r=0.0, p_ref=None).compute_adiabatic(*args)
        np.testing.assert_allclose(q, q0 * _phi(P) / PHI0, rtol=1e-14)

    def test_degassing_time_part_scales_with_phi_p(self):
        """Временная часть ṁ — с запасом φ(p^{n+1})·S_o/B_o (eq:mdot_disc).

        G^o = 0 — пространственной части нет, Q_deg пропорционален φ.
        ΔR_s = −5 м³ст/м³ст во всех ячейках. Ловит: φ0 во временной части ṁ.
        """
        props = self._props(_solver())
        So = 1.0 - self.SG
        Rs = np.full(N, RS0)
        args = (So, self.SG, Rs, Rs + 5.0, props['Bo'], np.zeros(N + 1), props['L'], DT, N, RS0)
        q = _solver().compute_degassing(*args, p=P)
        q0 = _solver(c_r=0.0, p_ref=None).compute_degassing(*args)
        assert np.all(q0 != 0.0)
        np.testing.assert_allclose(q, q0 * _phi(P) / PHI0, rtol=1e-14)

    def test_degassing_requires_p_when_compressible(self):
        """c_r ≠ 0, давление не передано — отказ, а не молчаливая φ0."""
        props = self._props(_solver())
        So = 1.0 - self.SG
        Rs = np.full(N, RS0)
        with pytest.raises(ValueError, match="давление"):
            _solver().compute_degassing(So, self.SG, Rs, Rs + 5.0, props['Bo'],
                                        np.zeros(N + 1), props['L'], DT, N, RS0)


# ═══════════════════════════════════════════════════════════
# C. Энергия и гидродинамика: один поровый объём (пример 18)
# ═══════════════════════════════════════════════════════════

class TestHydroConsistency:
    """Конфиг примера 18 (c_r = 4.5e-10): фабрика связывает энергию с породой прототипа."""

    def test_energy_pore_volume_equals_prototype(self):
        """V·φ(p) энергии = поровый объём прототипа на конфиге 18 при Δp до 10 МПа.

        Опорное давление обоих — p0 конфига (factory.py). Замер пробы DEBT-057:
        объёмы ячеек совпадают точно (DEBT-063), φ — до 2.2e-16. Ловит: p_ref
        энергии не p0, потерю передачи p_ref фабрикой, разные объёмы ячеек.
        """
        cfg = load_config(EXAMPLE_18)
        cfg.output.log_level = "ERROR"
        assert cfg.rock.compressibility != 0.0
        sim, _ = SimulatorFactory.from_config(cfg)
        model = sim._hydro._model
        p = np.linspace(10e6, 20e6, cfg.grid.N)
        np.testing.assert_allclose(
            sim.grid.volumes * sim._energy.porosity(p),
            model.rock.pore_volume_m3(model.grid.bulk_volumes_m3, p / BAR_TO_PA),
            rtol=1e-14, atol=0.0)

    def test_mdot_matches_hydro_gas_release(self, monkeypatch):
        """ṁ энергии = выделение газа гидродинамикой − остаток Лейбница (первые сутки примера 18).

        За вызов solve, м³ст: гидродинамика — −[Σ V·Δ(a·R_s) + dt·(F_N − F_0)],
        a = φ(p)·S_o/B_o по пористости прототипа, F = G^o·R_s выше по потоку;
        энергия — Σ V·ṁ·dt/ρ_g,ст. Временная часть ṁ берёт запас a^{n+1},
        поэтому расхождение равно −Σ V·ΔR_s·Δa (DEBT-066). Замер пробы
        DEBT-057 (mdot_short.py, 2 интервала, 25 вызовов solve): после вычета
        остатка с φ(p) — −9.5e-10 выделившегося газа (допуск Ньютона), с φ0 —
        6.7e-4. Ловит: φ0 во временной части ṁ, разную пористость энергии и
        гидродинамики.
        """
        cfg = load_config(EXAMPLE_18)
        cfg.output.log_level = "ERROR"
        cfg.time.history = cfg.time.history[:2]       # 60 с + 86340 с — первые сутки
        sim, init = SimulatorFactory.from_config(cfg)
        energy, model = sim._energy, sim._hydro._model
        V, pvt = sim.grid.volumes, sim.pvt
        acc = dict(hydro=0.0, mdot=0.0, leibniz=0.0)
        last = {}

        orig_deg = energy.compute_degassing

        def degassing(*args, **kwargs):
            out = orig_deg(*args, **kwargs)
            last["mdot"] = -out / args[6]             # Q_deg = −L·ṁ, L — 7-й аргумент
            return out

        orig_solve = energy.solve

        def solve(hydro_result, state_prev, dt, bc, collect=None):
            T = orig_solve(hydro_result, state_prev, dt, bc, collect)
            st, sp = hydro_result.state, state_prev
            a_new = model.rock.porosity(st.p / BAR_TO_PA) * (1 - st.Sg) / pvt.Bo(st.p, st.Rs)
            a_old = model.rock.porosity(sp.p / BAR_TO_PA) * (1 - sp.Sg) / pvt.Bo(sp.p, sp.Rs)
            G = hydro_result.G_o
            # Знаки: G > 0 — от скважины. Забой: добыча, выше по потоку ячейка 0.
            # Контур: приток (G < 0) несёт состав притока R_s0, отток — ячейки N-1.
            F0 = G[0] * st.Rs[0]
            FN = G[-1] * (bc.Rs_ext if G[-1] < 0 else st.Rs[-1])
            acc["hydro"] += -(np.sum(V * (a_new * st.Rs - a_old * sp.Rs)) + dt * (FN - F0))
            acc["mdot"] += np.sum(V * last["mdot"]) * dt / pvt.rho_g_std
            acc["leibniz"] += -np.sum(V * (st.Rs - sp.Rs) * (a_new - a_old))
            return T

        monkeypatch.setattr(energy, "compute_degassing", degassing)
        monkeypatch.setattr(energy, "solve", solve)
        sim.run(init)

        assert acc["hydro"] > 0.0                     # газ выделяется
        gap = (acc["mdot"] - acc["hydro"] - acc["leibniz"]) / acc["hydro"]
        assert abs(gap) < 1e-7, gap
