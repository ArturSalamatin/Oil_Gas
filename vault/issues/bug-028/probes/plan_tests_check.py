"""BUG-028 (/audit-plan): тесты плана (§3.3) на исходном коде и на коде шага 2 плана.

Код шага 2 («После:», с пределом max_active_iter + N) переписан ниже дословно, вместе
со строками 597-602, которые план опускает. Тесты A1-A4, B1, C1-C3, D1 — функции с
assert, как их задаёт план; печатается «ok» или текст отказа. Ожидание плана: на
исходном коде A1-A4, C1, C3, D1 — отказ, B1, C2 — ok; на коде плана — всё ok.
Пакет не правится: код плана ставится подменой метода класса.

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P orig|plan
"""

import copy
import sys
import time
import traceback
from pathlib import Path

import numpy as np

SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.blackoil import BlackOilNewtonReport, RadialBlackOilModel  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402
from tests.test_prototype_cell_tolerance import _build  # noqa: E402

EXAMPLES = SOLVER_ROOT / "examples"


# ── Код шага 2 плана, дословно ──
def _advance_phases_plan(self,state_old,dt_s,max_active_iter=12,max_newton=15):
    """Phase active-set loop (Prototype 1 logic); max_active_iter counts the passes that switch gas on (BUG-028)."""
    # BUG-020: inside the fourth stage of advance the BUG-014 fallback (well branches)
    # runs the Newton with phase switches inside it instead of this loop
    if self._phase_switching: return self._newton_switching(state_old,dt_s)
    state_old=state_old.copy(); mask=state_old.gas_active.copy(); guess=state_old.copy(); total_switches=total_newton=0
    aset=counted=0; max_passes=max_active_iter+self.grid.n
    while counted<max_active_iter and aset<max_passes:
        aset+=1
        z,report=self._newton_fixed_active_set(self.pack(guess,mask),state_old,dt_s,mask,max_iter=max_newton); total_newton+=report.iterations
        if not report.converged:
            report.active_set_iterations=aset; report.phase_switches=total_switches; return guess,report
        trial=self.unpack(z,mask); rs_sat=self.pvt.rs_sat(trial.pressure_bar)
        activate=(~mask)&(trial.rs_sm3_sm3>rs_sat+self.rs_switch_tol); deactivate=mask&(trial.sg<-self.sg_switch_tol)
        ns=int(np.count_nonzero(activate)+np.count_nonzero(deactivate)); total_switches+=ns
        if ns==0:
            tiny=mask&(trial.sg<0)&(trial.sg>=-self.sg_switch_tol); trial.sg[tiny]=0.0; trial.gas_active=mask.copy(); report.iterations=total_newton; report.active_set_iterations=aset; report.phase_switches=total_switches; return trial,report
        if np.any(activate): counted+=1   # BUG-028: only a pass that switches gas on is counted
        newmask=mask.copy(); newmask[activate]=True; newmask[deactivate]=False; guess=trial.copy(); guess.gas_active=newmask.copy()
        if np.any(activate):
            pa=guess.pressure_bar[activate]; rtot=guess.rs_sm3_sm3[activate].copy(); rsat=self.pvt.rs_sat(pa); bo=self.pvt.bo(pa,rsat); bg=self.pvt.bg(pa); d=np.maximum(rtot-rsat,0.0)
            sg0=np.maximum(d*bg/(bo+d*bg),1e-8)
            # BUG-018: keep the guess where oil is still mobile; np.minimum
            # returns sg0 bitwise wherever it is below the cap
            if self.sg_activation_cap is not None: sg0=np.minimum(sg0,self.sg_activation_cap)
            guess.sg[activate]=sg0; guess.rs_sm3_sm3[activate]=rsat
        if np.any(deactivate): guess.sg[deactivate]=0.0; guess.rs_sm3_sm3[deactivate]=self.pvt.rs_sat(guess.pressure_bar[deactivate])
        mask=newmask
    r=self.residual(self.pack(guess,mask),state_old,dt_s,mask)
    return guess,BlackOilNewtonReport(False,total_newton,float(np.linalg.norm(r,np.inf)),aset,total_switches,
                                      cell_measure=self._cell_measure(r,self._cell_weights(state_old,dt_s)),
                                      exit_reason='active_set')


# ── Модели ──
def factory_model(name):
    """Модель фабрики примера и начальное состояние прототипа, управление — как ставит адаптер."""
    cfg = load_config(EXAMPLES / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    model.set_bhp_control(cfg.time.history[0].p_wf / BAR_TO_PA)
    ps = BlackOilState(pressure_bar=init.p / BAR_TO_PA, rs_sm3_sm3=init.Rs.copy(),
                       sg=init.Sg.copy(), gas_active=(init.regime == 1))
    return model, ps


def scripted(model, script):
    """Подменный Ньютон §3.3: каждый вызов берёт следующий элемент script."""
    it = iter(script)

    def fake(z0, state_old, dt_s, gas_active, max_iter=15):
        step = next(it)
        n = model.grid.n
        p = state_old.pressure_bar
        rs_sat = model.pvt.rs_sat(p)
        x = np.where(gas_active, 0.1, rs_sat - 1.0)
        if step[0] == "on":
            idx = np.asarray(list(step[1]))
            x[idx] = rs_sat[idx] + 1.0
        elif step[0] == "off_edge":
            act = np.flatnonzero(gas_active)
            if act.size:
                x[act.max()] = -1e-3
        assert x.size == n
        return np.concatenate([p, x]), BlackOilNewtonReport(True, 1, 0.0)

    model._newton_fixed_active_set = fake


def forever_off():
    while True:
        yield ("off_edge",)


# ── Тесты плана ──
def test_A(cases):
    out = {}
    for name, dt, passes, cells, p0 in cases:
        model, ps = MODELS[name]
        new, rep = model.advance(ps, dt)
        ok = (rep.converged and not rep.fallback and rep.active_set_iterations == passes
              and int(new.gas_active.sum()) == cells and abs(new.pressure_bar[0] - p0) <= 0.01
              and np.all((new.sg >= 0) & (new.sg <= 1)))
        out[f"A {name} {dt:g}"] = "ok" if ok else (
            f"converged={rep.converged} fallback={rep.fallback} passes={rep.active_set_iterations} "
            f"cells={int(new.gas_active.sum())} p0={new.pressure_bar[0]:.4f} exit={rep.exit_reason}")
    return out


def test_B1():
    out = {}
    model, ps = MODELS["19_rs150_cooling"]
    for dt in (0.01, 86400.0):
        _, rep = model._advance_phases(ps, dt, max_active_iter=1)
        ok = (rep.exit_reason == "active_set" and rep.active_set_iterations == 1 and rep.phase_switches == 342)
        out[f"B1 {dt:g}"] = "ok" if ok else f"{rep.exit_reason} {rep.active_set_iterations} {rep.phase_switches}"
    return out


def test_C():
    out = {}
    model, s = _build(12)
    try:
        scripted(model, [("on", range(6))] + [("off_edge",)] * 5 + [("none",)])
        new, rep = model._advance_phases(s, 3600.0, max_active_iter=2)
        ok = (rep.converged and rep.active_set_iterations == 7 and rep.phase_switches == 11
              and list(np.flatnonzero(new.gas_active)) == [0])
        out["C1"] = "ok" if ok else f"{rep.converged} {rep.exit_reason} {rep.active_set_iterations} {rep.phase_switches}"

        scripted(model, [("on", [k]) for k in range(12)])
        _, rep = model._advance_phases(s, 3600.0, max_active_iter=3)
        ok = (not rep.converged and rep.exit_reason == "active_set" and rep.active_set_iterations == 3
              and rep.phase_switches == 3)
        out["C2"] = "ok" if ok else f"{rep.converged} {rep.exit_reason} {rep.active_set_iterations} {rep.phase_switches}"

        def script3():
            yield ("on", range(12))
            for _ in range(12):
                yield ("off_edge",)
            yield ("on", range(12))
            yield from forever_off()
        scripted(model, script3())
        _, rep = model._advance_phases(s, 3600.0, max_active_iter=3)
        ok = (not rep.converged and rep.exit_reason == "active_set" and rep.active_set_iterations == 15
              and rep.phase_switches == 37)
        out["C3"] = "ok" if ok else f"{rep.converged} {rep.exit_reason} {rep.active_set_iterations} {rep.phase_switches}"
    finally:
        del model._newton_fixed_active_set
    return out


def test_D1():
    cfg = load_config(EXAMPLES / "19_rs150_cooling" / "config.json")
    first = copy.deepcopy(cfg.time.history[0])
    first.dt = 1.0
    cfg.time.history = [first]
    cfg.time.dt_integration = 1.0
    cfg.numerics.max_retries = 0
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    try:
        hist = sim.run(init)
    except RuntimeError as exc:
        return {"D1": f"RuntimeError: {str(exc)[-90:]}"}
    st = hist.states[-1]
    ok = abs(st.p[0] / BAR_TO_PA - 38.38) <= 0.01 and int((st.regime == 1).sum()) == 98
    return {"D1": "ok" if ok else f"p0={st.p[0] / BAR_TO_PA:.4f} cells={int((st.regime == 1).sum())}"}


MODELS = {}


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    mode = sys.argv[1]
    if mode == "plan":
        RadialBlackOilModel._advance_phases = _advance_phases_plan
    for name in ("19_rs150_cooling", "21_rs100_cooling"):
        MODELS[name] = factory_model(name)
    t0 = time.perf_counter()
    res = {}
    for f, args in ((test_A, ([("19_rs150_cooling", 0.01, 182, 30, 78.13), ("19_rs150_cooling", 1.0, 62, 98, 38.38),
                                ("19_rs150_cooling", 5.27, 41, 129, 34.84), ("21_rs100_cooling", 1.0, 78, 82, 36.28)],)),
                    (test_B1, ()), (test_C, ()), (test_D1, ())):
        try:
            res.update(f(*args))
        except Exception:
            res[f.__name__] = "ИСКЛЮЧЕНИЕ " + traceback.format_exc().splitlines()[-1]
    for k, v in res.items():
        print(f"  {mode}: {k}: {v}", flush=True)
    print(f"  время {time.perf_counter() - t0:.1f} с", flush=True)


if __name__ == "__main__":
    main()
