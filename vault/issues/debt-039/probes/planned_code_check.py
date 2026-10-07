"""DEBT-039: проверка кода плана в памяти, до реализации (база 5ce2168).

Код плана — подклассы PrototypeHydroAdapter и Simulator (тела solve, run, _advance
скопированы из пакета и дополнены строками плана) и накопитель MassBalanceAccumulator.
Поля, которых в пакете ещё нет (HydroResult.int_G_*, SimulationHistory.mass_balance),
ставятся через setattr; код плана читает их getattr(..., None) — в пакете это будут
поля dataclass со значением None по умолчанию.

Режимы (запуск из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-039\\probes\\planned_code_check.py all [пример ...]
    ... retry | stub | short | plot
  all   — все примеры: история кода плана побитово равна исходной (p, Sg, Rs, T, regime,
          t, G_o, G_g, well_data, balance); max отн. невязки массы; время расчёта.
  retry — адаптер с принудительным A-retry: интегралы = сумма по подшагам; баланс шага
          с интегралами и с dt*G последнего подшага.
  stub  — Simulator на двойниках: пробный шаг не в интегралах; двойник без запаса — None;
          запас без интегралов — RuntimeError.
  short — укороченные конфиги 03, 04 (6 ч, N = 25), 16 (2 + 2 ч, N = 25): невязка,
          независимость от структуры истории, время.
  plot  — mass_balance.png кода плана для 16 и 01 в probes/plot_<пример>/.
"""

import copy
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = Path.cwd()
for p in (SOLVER, SOLVER / "examples", SOLVER / "tests",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.simulator import Simulator  # noqa: E402
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter  # noqa: E402
from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator  # noqa: E402
from gpn_multiphase_solver.state import (  # noqa: E402
    SimulationState, SimulationHistory, WellData)
from gpn_multiphase_solver.bc import PressureControl, RateControl  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA, DAY_TO_S, S_TO_DAY  # noqa: E402
from gpn_multiphase_solver.log import user_log, dev_log  # noqa: E402

EX = SOLVER / "examples"


# ═══════════════════ код плана: gpn_multiphase_solver/mass_balance.py ═══════════════════

MASS_KEYS = ("M_o", "M_g", "cum_o_well", "cum_o_ext", "cum_g_well", "cum_g_ext")


class MassBalanceAccumulator:
    def __init__(self):
        self.cum_o_well = 0.0
        self.cum_o_ext = 0.0
        self.cum_g_well = 0.0
        self.cum_g_ext = 0.0

    def add_step(self, hr):
        ints = tuple(getattr(hr, k, None) for k in
                     ("int_G_o_well", "int_G_o_ext", "int_G_g_well", "int_G_g_ext"))
        if None in ints:
            raise RuntimeError(
                "HydroResult без интегралов потоков int_G_*: решатель отдаёт запас "
                "компонентов, но не интегралы — баланс массы не замкнуть (DEBT-039)")
        self.cum_o_well += ints[0]
        self.cum_o_ext += ints[1]
        self.cum_g_well += ints[2]
        self.cum_g_ext += ints[3]

    def snapshot(self, inventories):
        M_o, M_g = inventories
        return {"M_o": M_o, "M_g": M_g,
                "cum_o_well": self.cum_o_well, "cum_o_ext": self.cum_o_ext,
                "cum_g_well": self.cum_g_well, "cum_g_ext": self.cum_g_ext}


# ═══════════════════ код плана: адаптер ═══════════════════

class PlannedAdapter(PrototypeHydroAdapter):
    def component_inventories(self, state):
        from radial_blackoil.state import BlackOilState
        proto_state = BlackOilState(
            pressure_bar=state.p / BAR_TO_PA,
            rs_sm3_sm3=state.Rs.copy(),
            sg=state.Sg.copy(),
            gas_active=(state.regime == 1),
        )
        oil, gas = self._model.component_inventories(proto_state)
        return float(np.sum(oil)), float(np.sum(gas))

    def solve(self, state, dt, bc):
        from radial_blackoil.state import BlackOilState
        well = bc.well
        if isinstance(well, PressureControl):
            self._model.set_bhp_control(well.p_wf / BAR_TO_PA)
        elif isinstance(well, RateControl):
            self._model.set_oil_rate_control(well.q_oil * DAY_TO_S,
                                             well.min_bhp / BAR_TO_PA)
        else:
            raise NotImplementedError
        for attempt in range(self._max_retries + 1):
            n_sub = 2 ** attempt
            dt_sub = dt / n_sub
            success = True
            current_state = state
            # ── план: интегралы попытки ──
            int_o_well = int_o_ext = int_g_well = int_g_ext = 0.0
            for step in range(n_sub):
                proto_state = BlackOilState(
                    pressure_bar=current_state.p / BAR_TO_PA,
                    rs_sm3_sm3=current_state.Rs.copy(),
                    sg=current_state.Sg.copy(),
                    gas_active=(current_state.regime == 1),
                )
                new_proto, report = self._model.advance(proto_state, dt_sub)
                if not report.converged:
                    success = False
                    break
                # ── план: потоки подшага на новом состоянии, знак забоя инвертирован ──
                f = self._model.face_component_fluxes_sm3s(new_proto)
                int_o_well += dt_sub * (-f['oil_well'])
                int_o_ext += dt_sub * f['oil_outer']
                int_g_well += dt_sub * (-f['gas_component_well'])
                int_g_ext += dt_sub * f['gas_component_outer']
                current_state = SimulationState(
                    p=new_proto.pressure_bar * BAR_TO_PA,
                    Sg=new_proto.sg.copy(),
                    Rs=new_proto.rs_sm3_sm3.copy(),
                    T=current_state.T.copy(),
                    regime=np.where(new_proto.gas_active, 1, 2),
                    t=current_state.t + dt_sub,
                )
            if success:
                result = self._build_result(current_state, new_proto, bc, n_substeps=n_sub)
                # пакет: return replace(result, int_G_o_well=..., ...)
                result.int_G_o_well = int_o_well
                result.int_G_o_ext = int_o_ext
                result.int_G_g_well = int_g_well
                result.int_G_g_ext = int_g_ext
                return result
        raise RuntimeError("HydroSolver не сошёлся")


# ═══════════════════ код плана: Simulator ═══════════════════

class PlannedSimulator(Simulator):
    def _mass_snapshot(self, mass, state):
        if mass is None:
            return None
        return mass.snapshot(self._hydro.component_inventories(state))

    def run(self, initial_state):
        history = SimulationHistory()
        history.mass_balance = []          # пакет: поле dataclass
        balance = EnergyBalanceAccumulator(self._grid)
        inv = getattr(self._hydro, "component_inventories", lambda s: None)(initial_state)
        mass = MassBalanceAccumulator() if inv is not None else None
        state = initial_state
        history.append(t=state.t, state=state, hydro=self._zero_hydro(state),
                       well=self._zero_well_data(state))
        history.mass_balance.append(self._mass_snapshot(mass, state))
        for k, interval in enumerate(self._schedule.intervals):
            n_sub, dt = self._schedule.substeps(k)
            for step in range(n_sub):
                state, hydro_result = self._advance(state, dt, interval.bc, balance, mass)
                if step == n_sub - 1:
                    well = WellData(
                        q_o_std=-hydro_result.G_o[0], q_g_std=-hydro_result.G_g[0],
                        m_o_well=self._pvt.rho_o_std * (-hydro_result.G_o[0]),
                        m_g_well=self._pvt.rho_g_std * (-hydro_result.G_g[0]),
                        p_wf=hydro_result.p_wf, T_wf=state.T[0])
                    history.append(t=state.t, state=state, hydro=hydro_result, well=well,
                                   balance=balance.snapshot())
                    history.mass_balance.append(self._mass_snapshot(mass, state))
        return history

    def _advance(self, state, dt, bc, balance, mass, allow_subdivision=True):
        hydro_result = self._hydro.solve(state, dt, bc)
        n_sub = getattr(hydro_result, 'n_substeps', 1)
        if allow_subdivision and n_sub > 1:
            dt_sub = dt / n_sub
            for _ in range(n_sub):
                state, hydro_result = self._advance(state, dt_sub, bc, balance, mass,
                                                    allow_subdivision=False)
            return state, hydro_result
        # ── план: только принятый результат ──
        if mass is not None:
            mass.add_step(hydro_result)
        T_new = self._energy.solve(hydro_result, state, dt, bc, collect=balance)
        new_state = SimulationState(
            p=hydro_result.state.p, Sg=hydro_result.state.Sg, Rs=hydro_result.state.Rs,
            T=T_new, regime=hydro_result.state.regime, t=hydro_result.state.t)
        return new_state, hydro_result


# ═══════════════════ код плана: examples/mass_balance.py ═══════════════════

def compute_mass_balance(history):
    if not history.mass_balance or history.mass_balance[0] is None:
        return None
    out = {k: np.array([s[k] for s in history.mass_balance]) for k in MASS_KEYS}
    out["t"] = np.array(history.times)
    for a in ("o", "g"):
        dM = out[f"M_{a}"] - out[f"M_{a}"][0]
        well, ext = out[f"cum_{a}_well"], out[f"cum_{a}_ext"]
        out[f"dM_{a}"] = dM
        out[f"prod_{a}"] = -well
        out[f"inflow_{a}"] = -ext
        out[f"residual_{a}"] = dM + ext - well
        scale = np.abs(dM) + np.abs(well) + np.abs(ext)
        scale = np.where(scale > 0.0, scale, 1.0)
        out[f"rel_residual_{a}"] = np.abs(out[f"residual_{a}"]) / scale
    return out


def plot_mass_balance(history, config, output_dir):
    bal = compute_mass_balance(history)
    if bal is None:
        print("Баланс массы не считается: решатель не отдаёт запас компонентов")
        return None
    t_days = bal["t"] * S_TO_DAY
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})
    for col, (a, name) in enumerate((("o", "Нефтяной компонент"),
                                     ("g", "Газовый компонент"))):
        ax1, ax2 = axes[0, col], axes[1, col]
        ax1.plot(t_days, bal[f"dM_{a}"], 'k-', linewidth=2,
                 label=r"$\Delta M$ (изменение запаса)")
        ax1.plot(t_days, bal[f"prod_{a}"], 'r-', linewidth=3, alpha=0.5,
                 label="добыча через забой (кумул.)")
        ax1.plot(t_days, bal[f"inflow_{a}"], 'b--', linewidth=1.5,
                 label="приток через контур (кумул.)")
        ax1.plot(t_days, bal[f"inflow_{a}"] - bal[f"prod_{a}"], 'g:', linewidth=1.5,
                 label="приток − добыча")
        ax1.set_ylabel("Объём, м³ст")
        ax1.set_title(name)
        ax1.legend(fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))
        ax2.plot(t_days, bal[f"rel_residual_{a}"], 'k-', linewidth=1)
        ax2.set_xlabel("Время, сут")
        ax2.set_ylabel(r"|невязка| / $\Sigma$|членов|")
        ax2.grid(True, alpha=0.3)
        ax2.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))
    fig.suptitle(f"Баланс массы компонентов — {Path(config.config_dir).name}")
    fig.tight_layout()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "mass_balance.png"
    fig.savefig(out_path, dpi=130)       # пакет: save_figure (PNG + SVG для EMF)
    plt.close(fig)
    print(f"Сохранён: {out_path}")
    print("Баланс массы компонентов, м3ст:")
    for a, name in (("o", "Нефть"), ("g", "Газ  ")):
        print(f"  {name}: dM = {bal[f'dM_{a}'][-1]:+.4e}, добыча = {bal[f'prod_{a}'][-1]:+.4e}, "
              f"приток с контура = {bal[f'inflow_{a}'][-1]:+.4e}")
        print(f"         невязка финал = {bal[f'residual_{a}'][-1]:+.4e} "
              f"({bal[f'rel_residual_{a}'][-1]:.2e}), max по записям "
              f"{float(np.max(bal[f'rel_residual_{a}'])):.2e}")
    return bal


# ═══════════════════ проверки ═══════════════════

def build(cfg, planned):
    sim, init = SimulatorFactory.from_config(cfg)
    if planned:
        sim.__class__ = PlannedSimulator
        sim._hydro.__class__ = PlannedAdapter
    return sim, init


def same_history(a, b):
    diff = []
    if a.times != b.times:
        diff.append("t")
    for f in ("p", "Sg", "Rs", "T", "regime"):
        if not all(np.array_equal(getattr(x, f), getattr(y, f)) for x, y in zip(a.states, b.states)):
            diff.append(f)
    for f in ("G_o", "G_g", "G_free_gas", "Q_o", "Q_g", "m_o", "m_g"):
        if not all(np.array_equal(getattr(x, f), getattr(y, f))
                   for x, y in zip(a.hydro_results, b.hydro_results)):
            diff.append(f)
    if a.well_data != b.well_data:
        diff.append("well_data")
    if a.balance != b.balance:
        diff.append("balance")
    return diff


def check_all(names):
    names = names or sorted(d.name for d in EX.iterdir() if (d / "config.json").is_file())
    rows = []
    for name in names:
        cfg = load_config(EX / name / "config.json")
        cfg.output.log_level = "WARNING"
        sim, init = build(cfg, False)
        t0 = time.perf_counter(); h0 = sim.run(init); w0 = time.perf_counter() - t0
        sim, init = build(cfg, True)
        t0 = time.perf_counter(); h1 = sim.run(init); w1 = time.perf_counter() - t0
        diff = same_history(h0, h1)
        bal = compute_mass_balance(h1)
        mo = float(np.max(bal["rel_residual_o"])); mg = float(np.max(bal["rel_residual_g"]))
        rows.append((name, diff, mo, mg, w0, w1))
        print(f"{name:28s} история {'побитово' if not diff else 'РАЗЛИЧИЕ ' + str(diff)}; "
              f"max отн. невязки: нефть {mo:.2e}, газ {mg:.2e}; расчёт {w0:.1f} -> {w1:.1f} с",
              flush=True)
        if name in ("16_well_shut_in", "01_single_phase_no_jt"):
            plot_mass_balance(h1, cfg, HERE / f"plot_{name[:2]}")
    print(f"\nразличий историй: {sum(1 for r in rows if r[1])}; max невязки: нефть "
          f"{max(r[2] for r in rows):.2e}, газ {max(r[3] for r in rows):.2e}; "
          f"время {sum(r[4] for r in rows):.1f} -> {sum(r[5] for r in rows):.1f} с")


def check_retry():
    from radial_blackoil.state import BlackOilState
    cfg = load_config(EX / "04_table_table" / "config.json")
    cfg.grid.N = 25
    cfg.output.log_level = "WARNING"
    sim, init = build(cfg, True)
    adapter = sim._hydro
    bc = sim._schedule.intervals[0].bc
    dt = 3600.0
    real = adapter._model.advance
    calls = []

    def failing_first(ps, dts, *a, **k):
        calls.append(dts)
        if len(calls) == 1:
            class R:            # отчёт отказа: адаптер читает converged, iterations, residual_inf
                converged = False; iterations = 0; residual_inf = 1.0
            return ps, R()
        return real(ps, dts, *a, **k)

    adapter._model.advance = failing_first
    hr = adapter.solve(init, dt, bc)
    adapter._model.advance = real
    print(f"вызовы advance: {calls}; n_substeps = {hr.n_substeps}")

    # Независимо: свежая модель, два подшага dt/2, потоки после каждого
    sim2, _ = build(cfg, True)
    m2 = sim2._hydro._model
    m2.set_bhp_control(bc.well.p_wf / BAR_TO_PA)
    ps = BlackOilState(pressure_bar=init.p / BAR_TO_PA, rs_sm3_sm3=init.Rs.copy(),
                       sg=init.Sg.copy(), gas_active=(init.regime == 1))
    io_w = io_e = 0.0
    G0 = []
    for _ in range(2):
        ps, rep = m2.advance(ps, dt / 2)
        f = m2.face_component_fluxes_sm3s(ps)
        io_w += dt / 2 * (-f['oil_well']); io_e += dt / 2 * f['oil_outer']
        G0.append(-f['oil_well'])
    print(f"int_G_o_well: адаптер {hr.int_G_o_well:.15e}, независимо {io_w:.15e}, "
          f"равны побитово: {hr.int_G_o_well == io_w}; int_G_o_ext равны: {hr.int_G_o_ext == io_e}")
    print(f"G_o[0] подшагов: {G0[0]:.6e}, {G0[1]:.6e}; HydroResult.G_o[0] = {hr.G_o[0]:.6e} "
          f"(= последнему: {hr.G_o[0] == G0[1]})")
    Mo0, Mg0 = adapter.component_inventories(init)
    Mo1, Mg1 = adapter.component_inventories(hr.state)
    for lab, dM, iw, ie, Gw, Ge in (
            ("нефть", Mo1 - Mo0, hr.int_G_o_well, hr.int_G_o_ext, hr.G_o[0], hr.G_o[-1]),
            ("газ", Mg1 - Mg0, hr.int_G_g_well, hr.int_G_g_ext, hr.G_g[0], hr.G_g[-1])):
        r_int = abs(dM + ie - iw) / (abs(dM) + abs(iw) + abs(ie))
        r_last = abs(dM + dt * Ge - dt * Gw) / (abs(dM) + abs(dt * Gw) + abs(dt * Ge))
        print(f"  {lab}: невязка шага с интегралами {r_int:.2e}; с dt*G последнего подшага {r_last:.2e}")

    # Без дробления: интеграл = dt*G[0] побитово
    sim3, init3 = build(cfg, True)
    hr3 = sim3._hydro.solve(init3, dt, bc)
    print(f"без дробления: n_substeps = {hr3.n_substeps}; int_G_o_well == dt*G_o[0]: "
          f"{hr3.int_G_o_well == dt * hr3.G_o[0]}; int_G_g_ext == dt*G_g[N]: "
          f"{hr3.int_G_g_ext == dt * hr3.G_g[-1]}")
    inv = sim3._hydro.component_inventories(init3)
    ps = BlackOilState(pressure_bar=init3.p / BAR_TO_PA, rs_sm3_sm3=init3.Rs.copy(),
                       sg=init3.Sg.copy(), gas_active=(init3.regime == 1))
    o, g = sim3._hydro._model.component_inventories(ps)
    print(f"запас: адаптер {inv}, прототип {(float(np.sum(o)), float(np.sum(g)))}")


def check_stub():
    # У прототипа свой каталог tests: пакет tests GPN — из numerical_solver, первым в пути
    sys.path.insert(0, str(SOLVER))
    sys.modules.pop("tests", None)
    from tests._doubles import LogProfileHydroStub, SubdividingHydroStub
    import tests.test_simulator as ts

    class IntegralStub(LogProfileHydroStub):
        def solve(self, state, dt, bc):
            r = super().solve(state, dt, bc)
            r.int_G_o_well = dt * r.G_o[0]; r.int_G_o_ext = dt * r.G_o[-1]
            r.int_G_g_well = dt * r.G_g[0]; r.int_G_g_ext = dt * r.G_g[-1]
            return r

        def component_inventories(self, state):
            return (0.0, 0.0)

    class SubdividingPlanned(SubdividingHydroStub):
        def solve(self, state, dt, bc):
            r = self._inner.solve(state, dt, bc)
            self.dt_calls.append(dt)
            n = self._n_substeps if len(self.dt_calls) == 1 else 1
            r2 = replace(r, n_substeps=n)
            for k in ("int_G_o_well", "int_G_o_ext", "int_G_g_well", "int_G_g_ext"):
                setattr(r2, k, getattr(r, k, None))     # пакет: replace сохраняет поля сам
            return r2

        def component_inventories(self, state):      # план: делегирование в _doubles
            return self._inner.component_inventories(state)

    grid, pvt, inner, energy, _ = ts._make_simulator()
    stub = IntegralStub(grid, pvt, inner._relperm)
    hydro = SubdividingPlanned(stub, n_substeps=2)
    sched = ts._single_interval_schedule(dt_hist=3600.0, dt_int=3600.0)
    sim = PlannedSimulator(grid, hydro, energy, pvt, sched)
    h = sim.run(ts._initial_state())
    G0 = h.hydro_results[-1].G_o[0]
    cum = h.mass_balance[-1]["cum_o_well"]
    print(f"пробный шаг: dt вызовов {hydro.dt_calls}; cum_o_well = {cum:.10e}, 3600*G = "
          f"{3600 * G0:.10e} (rel {abs(cum / (3600 * G0) - 1):.1e}), 5400*G = {5400 * G0:.10e}")

    # Аудит: вложенное дробление — двойник сообщает n_substeps = 2 на КАЖДОМ вызове
    class NestedPlanned(SubdividingPlanned):
        def solve(self, state, dt, bc):
            r = self._inner.solve(state, dt, bc)
            self.dt_calls.append(dt)
            r2 = replace(r, n_substeps=self._n_substeps)
            for k in ("int_G_o_well", "int_G_o_ext", "int_G_g_well", "int_G_g_ext"):
                setattr(r2, k, getattr(r, k, None))
            return r2

    hydro = NestedPlanned(stub, n_substeps=2)
    sim = PlannedSimulator(grid, hydro, energy, pvt, sched)
    h = sim.run(ts._initial_state())
    G0 = h.hydro_results[-1].G_o[0]
    cum = h.mass_balance[-1]["cum_o_well"]
    print(f"вложенное дробление: dt вызовов {hydro.dt_calls}; cum_o_well = {cum:.10e}, "
          f"3600*G = {3600 * G0:.10e}, равны: {cum == 3600 * G0}")

    sim = PlannedSimulator(grid, LogProfileHydroStub(grid, pvt, inner._relperm), energy, pvt,
                           ts._single_interval_schedule(dt_hist=7200.0, dt_int=3600.0))
    h = sim.run(ts._initial_state())
    print(f"двойник без запаса: mass_balance = {h.mass_balance}")

    class InvOnly(LogProfileHydroStub):
        def component_inventories(self, state):
            return (1.0, 1.0)
    sim = PlannedSimulator(grid, InvOnly(grid, pvt, inner._relperm), energy, pvt,
                           ts._single_interval_schedule(dt_hist=3600.0, dt_int=3600.0))
    try:
        sim.run(ts._initial_state())
        print("запас без интегралов: исключения НЕТ")
    except RuntimeError as e:
        print(f"запас без интегралов: RuntimeError: {e}")


def short_cfg(example, n_intervals=1):
    cfg = load_config(EX / example / "config.json")
    cfg.grid.N = 25
    iv = copy.deepcopy(cfg.time.history[0])
    cfg.time.history = [copy.deepcopy(iv) for _ in range(n_intervals)]
    for hh in cfg.time.history:
        hh.dt = 21600.0 / n_intervals
    cfg.output.log_level = "WARNING"
    return cfg


def check_short():
    for ex in ("03_standing_corey", "04_table_table"):
        res = {}
        for n in (1, 6):
            sim, init = build(short_cfg(ex, n), True)
            t0 = time.perf_counter(); h = sim.run(init); w = time.perf_counter() - t0
            bal = compute_mass_balance(h)
            res[n] = (h, bal)
            print(f"{ex} ({n} инт.): max отн. невязки нефть {np.max(bal['rel_residual_o']):.2e}, "
                  f"газ {np.max(bal['rel_residual_g']):.2e}; {w:.2f} с")
        a, b = res[1][0].mass_balance[-1], res[6][0].mass_balance[-1]
        print(f"  финальный снимок 1 инт. == 6 инт.: {a == b}; "
              f"max rel разница {max(abs(a[k] - b[k]) / max(abs(a[k]), 1e-300) for k in MASS_KEYS):.1e}")

    src = EX / "16_well_shut_in" / "config.json"
    raw = json.loads(src.read_text(encoding="utf-8"))
    prod = {"control": "pressure", "p_wf": 6.0e6}
    shut = {"control": "rate", "q_oil": 0.0, "min_bhp": 101325.0}
    raw["time"]["history"] = [{"dt": 300.0, "repeat": 24, **prod},
                              {"dt": 300.0, "repeat": 24, **shut}]
    raw["time"]["dt_integration"] = 300.0
    path = HERE / "_short16.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    cfg = load_config(path)
    cfg.config_dir = src.parent
    cfg.grid.N = 25
    cfg.output.log_level = "WARNING"
    sim, init = build(cfg, True)
    t0 = time.perf_counter(); h = sim.run(init); w = time.perf_counter() - t0
    path.unlink()
    bal = compute_mass_balance(h)
    cw = bal["cum_o_well"]
    print(f"16 (2+2 ч): max отн. невязки нефть {np.max(bal['rel_residual_o']):.2e}, газ "
          f"{np.max(bal['rel_residual_g']):.2e}; cum_o_well на останове постоянен: "
          f"{bool(np.all(cw[24:] == cw[24]))}; cum_g_well тоже: "
          f"{bool(np.all(bal['cum_g_well'][24:] == bal['cum_g_well'][24]))}; "
          f"dM_o на останове {bal['dM_o'][-1] - bal['dM_o'][24]:+.3e}, приток с контура "
          f"{bal['inflow_o'][-1] - bal['inflow_o'][24]:+.3e} м3ст; {w:.2f} с")


def check_fixture():
    """Тесты плана для адаптера на настройке фикстур tests/test_prototype_adapter.py."""
    sys.path.insert(0, str(SOLVER))
    sys.modules.pop("tests", None)
    import tests.test_prototype_adapter as tpa
    from radial_blackoil.grid import RadialGrid
    from radial_blackoil.rock import CompressibleRock
    from radial_blackoil.pvt import BlackOilPVT
    from radial_blackoil.relperm import TabulatedRelPerm
    from radial_blackoil.blackoil import RadialBlackOilModel
    from radial_blackoil.state import BlackOilState
    from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
    from gpn_multiphase_solver.pvt.prototype_adapter import PrototypePVTAdapter
    from gpn_multiphase_solver.state import BoundaryConditions

    def make():
        ppvt = BlackOilPVT(tpa.OIL_ROWS, tpa.GAS_ROWS)
        model = RadialBlackOilModel(
            grid=RadialGrid(tpa.R_WELL, tpa.R_EXT, tpa.H, tpa.N, tpa.K_MD),
            rock=CompressibleRock(phi_ref=tpa.PHI, p_ref_bar=tpa.P0_BAR, cr_per_bar=0.0),
            pvt=ppvt, relperm=TabulatedRelPerm(tpa.SG_TAB, tpa.KRO_TAB, tpa.KRG_TAB),
            p_bhp_bar=tpa.P_WF_BAR, p_outer_bar=tpa.P0_BAR,
            outer_rs_sm3_sm3=tpa.RS0, skin=0.0)
        ad = PlannedAdapter(model, LogRadialGrid(r_well=tpa.R_WELL, R_ext=tpa.R_EXT, h=tpa.H,
                                                 N=tpa.N, k=tpa.K_PERM),
                            PrototypePVTAdapter(ppvt, rho_o_std=tpa.RHO_O_STD,
                                                rho_g_std=tpa.RHO_G_STD))
        return ad

    N, DT = tpa.N, tpa.DT
    init = SimulationState(p=np.full(N, tpa.P0_PA), Sg=np.zeros(N), Rs=np.full(N, tpa.RS0),
                           T=np.full(N, tpa.T0), regime=np.full(N, 2, dtype=int), t=0.0)
    bc = BoundaryConditions(well=PressureControl(tpa.P_WF_PA), p_ext=tpa.P0_PA,
                            T_ext=tpa.T0, Rs_ext=tpa.RS0, Sg_ext=0.0)

    def rel_step(ad, hr, use_int):
        (Mo0, Mg0), (Mo1, Mg1) = ad.component_inventories(init), ad.component_inventories(hr.state)
        out = []
        for dM, iw, ie, Gw, Ge in ((Mo1 - Mo0, hr.int_G_o_well, hr.int_G_o_ext, hr.G_o[0], hr.G_o[-1]),
                                   (Mg1 - Mg0, hr.int_G_g_well, hr.int_G_g_ext, hr.G_g[0], hr.G_g[-1])):
            w, e = (iw, ie) if use_int else (DT * Gw, DT * Ge)
            out.append(abs(dM + e - w) / (abs(dM) + abs(w) + abs(e)))
        return out

    ad = make()
    hr = ad.solve(init, DT, bc)
    print(f"фикстура без дробления: n_substeps {hr.n_substeps}; int == DT*G: "
          f"{[hr.int_G_o_well == DT * hr.G_o[0], hr.int_G_o_ext == DT * hr.G_o[-1], hr.int_G_g_well == DT * hr.G_g[0], hr.int_G_g_ext == DT * hr.G_g[-1]]}; "
          f"невязка шага {rel_step(ad, hr, True)}; S_g max {hr.state.Sg.max():.3e}")

    ad = make()
    real = ad._model.advance
    calls = []

    def failing_first(ps, dts, *a, **k):
        calls.append(dts)
        if len(calls) == 1:
            class R:
                converged = False; iterations = 0; residual_inf = 1.0
            return ps, R()
        return real(ps, dts, *a, **k)
    ad._model.advance = failing_first
    hr = ad.solve(init, DT, bc)
    ad._model.advance = real
    # Независимо: свежий адаптер, два шага DT/2 его же solve
    ad2 = make()
    h1 = ad2.solve(init, DT / 2, bc)
    h2 = ad2.solve(h1.state, DT / 2, bc)
    s = h1.int_G_o_well + h2.int_G_o_well
    print(f"фикстура с дроблением: вызовы {calls}; n_substeps {hr.n_substeps}; int_G_o_well "
          f"{hr.int_G_o_well:.15e} vs два solve(DT/2) {s:.15e} (равны: {hr.int_G_o_well == s}); "
          f"int_G_g_ext равны: {hr.int_G_g_ext == h1.int_G_g_ext + h2.int_G_g_ext}")
    print(f"  невязка шага: с интегралами {rel_step(ad, hr, True)}, с DT*G последнего подшага "
          f"{rel_step(ad, hr, False)}")
    # Как в тесте плана: два solve(DT/2) того же адаптера после снятия подмены
    g1 = ad.solve(init, DT / 2, bc)
    g2 = ad.solve(g1.state, DT / 2, bc)
    print(f"  тот же адаптер, два solve(DT/2): равны побитово "
          f"{[hr.int_G_o_well == g1.int_G_o_well + g2.int_G_o_well, hr.int_G_o_ext == g1.int_G_o_ext + g2.int_G_o_ext, hr.int_G_g_well == g1.int_G_g_well + g2.int_G_g_well, hr.int_G_g_ext == g1.int_G_g_ext + g2.int_G_g_ext]}")


def check_plot():
    for name in ("16_well_shut_in", "01_single_phase_no_jt"):
        cfg = load_config(EX / name / "config.json")
        cfg.output.log_level = "WARNING"
        sim, init = build(cfg, True)
        plot_mass_balance(sim.run(init), cfg, HERE / f"plot_{name[:2]}")


if __name__ == "__main__":
    user_log.setLevel("WARNING"); dev_log.setLevel("WARNING")
    mode = sys.argv[1]
    {"all": lambda: check_all(sys.argv[2:]), "retry": check_retry, "stub": check_stub,
     "short": check_short, "plot": check_plot, "fixture": check_fixture}[mode]()
