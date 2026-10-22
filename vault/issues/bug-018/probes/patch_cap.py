"""BUG-018: проба исправления — ограничение S_g активации в _advance_phases.

Копия RadialBlackOilModel._advance_phases (blackoil.py:298-316) с одной
правкой: S_g «закрытого сосуда» у активируемых ячеек ограничена сверху
значением cap. Подменяется в памяти (types.MethodType), файл прототипа не
меняется. cap вычисляется по таблице ОФП прототипа (TabulatedRelPerm):
  rule=node — наибольший узел таблицы, где k_ro > 0 (нефть ещё подвижна);
  rule=epsX — S_g первого узла с k_ro = 0 минус X (например eps0.05).
Если в таблице нет узла с k_ro = 0 — ограничения нет.

Режимы:
  examples [имя ...]       — все примеры (или перечисленные): cap, max S_g
                             активации, число срабатываний; для примеров со
                             срабатываниями — сверка с расчётом без правки;
  cases                    — отказные конфиги BUG-018 (генератор FEAT-025),
                             30 сут: сходимость, вызовы advance, T и S_g у забоя.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-018\\probes\\patch_cap.py rule=node examples
    .venv\\Scripts\\python ..\\vault\\issues\\bug-018\\probes\\patch_cap.py rule=node cases
"""

import json
import sys
import time
import types
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
FEAT025 = HERE.parents[1] / "feat-025" / "probes"
for p in (SOLVER, SOLVER / "tests", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3", FEAT025):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import make_configs as mc  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.blackoil import BlackOilNewtonReport  # noqa: E402

EXAMPLES = SOLVER / "examples"


def cap_of(relperm, rule):
    """Верхняя граница S_g активации по таблице ОФП прототипа; None — без ограничения."""
    sg = np.asarray(getattr(relperm, "sg", []), float)
    kro = np.asarray(getattr(relperm, "kro_tab", []), float)
    zero = np.flatnonzero(kro <= 0.0)
    if sg.size == 0 or zero.size == 0 or zero[0] == 0:
        return None
    j = int(zero[0])                       # первый узел, где нефть неподвижна
    if rule == "node":
        return float(sg[j - 1])            # последний узел с k_ro > 0
    return float(sg[j] - float(rule[3:]))  # epsX


def patched_advance_phases(stats):
    """_advance_phases прототипа с ограничением S_g активации (stats — журнал)."""
    def _advance_phases(self, state_old, dt_s, max_active_iter=12, max_newton=15):
        state_old = state_old.copy(); mask = state_old.gas_active.copy(); guess = state_old.copy(); total_switches = total_newton = 0
        for aset in range(1, max_active_iter + 1):
            z, report = self._newton_fixed_active_set(self.pack(guess, mask), state_old, dt_s, mask, max_iter=max_newton); total_newton += report.iterations
            if not report.converged:
                report.active_set_iterations = aset; report.phase_switches = total_switches; return guess, report
            trial = self.unpack(z, mask); rs_sat = self.pvt.rs_sat(trial.pressure_bar)
            activate = (~mask) & (trial.rs_sm3_sm3 > rs_sat + self.rs_switch_tol); deactivate = mask & (trial.sg < -self.sg_switch_tol)
            ns = int(np.count_nonzero(activate) + np.count_nonzero(deactivate)); total_switches += ns
            if ns == 0:
                tiny = mask & (trial.sg < 0) & (trial.sg >= -self.sg_switch_tol); trial.sg[tiny] = 0.0; trial.gas_active = mask.copy(); report.iterations = total_newton; report.active_set_iterations = aset; report.phase_switches = total_switches; return trial, report
            newmask = mask.copy(); newmask[activate] = True; newmask[deactivate] = False; guess = trial.copy(); guess.gas_active = newmask.copy()
            if np.any(activate):
                pa = guess.pressure_bar[activate]; rtot = guess.rs_sm3_sm3[activate].copy(); rsat = self.pvt.rs_sat(pa); bo = self.pvt.bo(pa, rsat); bg = self.pvt.bg(pa); d = np.maximum(rtot - rsat, 0.0)
                sg0 = np.maximum(d * bg / (bo + d * bg), 1e-8)
                # ── правка BUG-018: S_g «закрытого сосуда» не выше cap ──
                stats["max_guess"] = max(stats["max_guess"], float(sg0.max()))
                if stats["cap"] is not None:
                    hit = sg0 > stats["cap"]
                    stats["hits"] += int(hit.sum())
                    sg0 = np.minimum(sg0, stats["cap"])
                guess.sg[activate] = sg0; guess.rs_sm3_sm3[activate] = rsat
            if np.any(deactivate): guess.sg[deactivate] = 0.0; guess.rs_sm3_sm3[deactivate] = self.pvt.rs_sat(guess.pressure_bar[deactivate])
            mask = newmask
        r = self.residual(self.pack(guess, mask), state_old, dt_s, mask); return guess, BlackOilNewtonReport(False, total_newton, float(np.linalg.norm(r, np.inf)), max_active_iter, total_switches)
    return _advance_phases


def build(cfg_path, rule, patch=True):
    cfg = load_config(cfg_path)
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    stats = {"cap": cap_of(model.relperm, rule), "max_guess": 0.0, "hits": 0, "advance": 0}
    if patch:
        model._advance_phases = types.MethodType(patched_advance_phases(stats), model)
    orig = model.advance

    def advance(*a, **kw):
        stats["advance"] += 1
        return orig(*a, **kw)

    model.advance = advance
    return cfg, sim, init, stats


def same(h1, h2):
    """Побитовое совпадение всех записей: p, S_g, R_s, T, дебиты."""
    for a, b in zip(h1.states, h2.states):
        for k in ("p", "Sg", "Rs", "T"):
            if not np.array_equal(getattr(a, k), getattr(b, k)):
                return False
    return all(w1.q_o_std == w2.q_o_std and w1.q_g_std == w2.q_g_std
               for w1, w2 in zip(h1.well_data, h2.well_data))


def run_examples(rule, names):
    import test_examples as te
    names = names or te.ALL_EXAMPLES
    for nm in names:
        t0 = time.perf_counter()
        cfg, sim, init, st = build(EXAMPLES / nm / "config.json", rule)
        h = sim.run(init)
        line = (f"{nm:28s} cap = {st['cap']}, max S_g активации = {st['max_guess']:.4f}, "
                f"срабатываний {st['hits']}, вызовов advance {st['advance']}, {time.perf_counter()-t0:.0f} с")
        if st["hits"]:
            _, sim0, init0, _ = build(EXAMPLES / nm / "config.json", rule, patch=False)
            h0 = sim0.run(init0)
            line += f"; побитово с исходным: {same(h, h0)}"
        print(line, flush=True)


CASES = [
    # (подпись, пример генератора, переопределения, p_wf МПа или None)
    ("20: S_or 0.2, N 50, k 100 мД, p_wf 5", "20", dict(S_or="0.2", N="50", k="1e-13"), None),
    ("20: S_or 0.2, N 50, k 100 мД, p_wf 8", "20", dict(S_or="0.2", N="50", k="1e-13"), 8.0),
    ("20: S_or 0.2, N 350, k 30 мД, p_wf 5", "20", dict(S_or="0.2"), None),
    ("19: S_or 0.2, N 350, k 10 мД, p_wf 3", "19", dict(S_or="0.2"), None),
    ("21: S_or 0.2, N 350, k 10 мД, p_wf 3", "21", dict(S_or="0.2"), None),
    ("20: S_or 0.1, N 50, k 100 мД, p_wf 5", "20", dict(S_or="0.1", N="50", k="1e-13"), None),
]


def run_cases(rule):
    d = HERE / "cfg_patch"
    d.mkdir(exist_ok=True)
    for label, ex, over, pwf in CASES:
        s = dict(mc.SETS[ex])
        if pwf is not None:
            s["p_wf"] = pwf * 1e6
        (d / "config.json").write_text(json.dumps(mc.build(ex, s, {**over, "log": "ERROR"}), indent=2,
                                                  ensure_ascii=False), encoding="utf-8")
        cfg, sim, init, st = build(d / "config.json", rule)
        t0 = time.perf_counter()
        try:
            h = sim.run(init)
            w = h.states[-1]
            print(f"{label}: cap = {st['cap']}, СОШЁЛСЯ, вызовов advance {st['advance']} на "
                  f"{len(cfg.time.history)} интервалов, срабатываний {st['hits']}, "
                  f"max S_g активации {st['max_guess']:.3f}; 30 сут: T(r_w) = {w.T[0]:.3f} К, "
                  f"S_g(r_w) = {w.Sg[0]:.4f}; {time.perf_counter()-t0:.0f} с", flush=True)
        except RuntimeError as e:
            print(f"{label}: cap = {st['cap']}, ОТКАЗ ({str(e)[:50]}…), вызовов advance {st['advance']}, "
                  f"срабатываний {st['hits']}", flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    rule = "node"
    if args and args[0].startswith("rule="):
        rule = args.pop(0).split("=", 1)[1]
    mode = args.pop(0)
    if mode == "examples":
        run_examples(rule, args)
    else:
        run_cases(rule)
