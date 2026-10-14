"""BUG-028 (/plan-fix): вариант 1 — проходы набора фаз, которые только снимают газ, в лимит не считаются.

Копия RadialBlackOilModel._advance_phases (blackoil.py, база 209326d) с одним отличием:
счётчик counted растёт только на проходах с включением газа. Проход без включений
строго сужает набор фаз, таких подряд не больше N — цикл конечен. Где исходный цикл
сходится или отказывает за <= max_active_iter проходов, итерации те же побитово:
проход k <= max_active_iter идёт в обоих (counted <= k - 1).

install() подменяет метод класса; события — вызовы, где проходов стало больше
max_active_iter (только там вариант расходится с исходным), — в EVENTS и, если
задан путь, построчно в файл (JSON).
"""

import json
import os

import numpy as np

from radial_blackoil.blackoil import BlackOilNewtonReport, RadialBlackOilModel

EVENTS = []
CONTEXT = {}    # пробы дописывают сюда t подшага, ветку и т. п. — уходит в событие
_LOG = {"path": None}
_ORIG = RadialBlackOilModel._advance_phases


def _event(dt_s, aset, counted, total_newton, converged, reason, n_active):
    ev = dict(CONTEXT, dt=float(dt_s), passes=int(aset), counted=int(counted), newton=int(total_newton),
              converged=bool(converged), exit=reason, two_phase=int(n_active))
    EVENTS.append(ev)
    if _LOG["path"]:
        with open(_LOG["path"], "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def advance_phases_v1(self, state_old, dt_s, max_active_iter=12, max_newton=15):
    """Цикл набора фаз; проходы без включения газа в лимит max_active_iter не считаются."""
    if self._phase_switching: return self._newton_switching(state_old, dt_s)
    state_old = state_old.copy(); mask = state_old.gas_active.copy(); guess = state_old.copy(); total_switches = total_newton = 0
    aset = counted = 0
    while counted < max_active_iter:
        aset += 1
        z, report = self._newton_fixed_active_set(self.pack(guess, mask), state_old, dt_s, mask, max_iter=max_newton); total_newton += report.iterations
        if not report.converged:
            report.active_set_iterations = aset; report.phase_switches = total_switches
            if aset > max_active_iter: _event(dt_s, aset, counted, total_newton, False, report.exit_reason, int(mask.sum()))
            return guess, report
        trial = self.unpack(z, mask); rs_sat = self.pvt.rs_sat(trial.pressure_bar)
        activate = (~mask) & (trial.rs_sm3_sm3 > rs_sat + self.rs_switch_tol); deactivate = mask & (trial.sg < -self.sg_switch_tol)
        ns = int(np.count_nonzero(activate) + np.count_nonzero(deactivate)); total_switches += ns
        if ns == 0:
            tiny = mask & (trial.sg < 0) & (trial.sg >= -self.sg_switch_tol); trial.sg[tiny] = 0.0; trial.gas_active = mask.copy(); report.iterations = total_newton; report.active_set_iterations = aset; report.phase_switches = total_switches
            if aset > max_active_iter: _event(dt_s, aset, counted, total_newton, True, "converged", int(mask.sum()))
            return trial, report
        # BUG-028: только проход с включением газа расходует лимит
        if np.any(activate): counted += 1
        newmask = mask.copy(); newmask[activate] = True; newmask[deactivate] = False; guess = trial.copy(); guess.gas_active = newmask.copy()
        if np.any(activate):
            pa = guess.pressure_bar[activate]; rtot = guess.rs_sm3_sm3[activate].copy(); rsat = self.pvt.rs_sat(pa); bo = self.pvt.bo(pa, rsat); bg = self.pvt.bg(pa); d = np.maximum(rtot - rsat, 0.0)
            sg0 = np.maximum(d * bg / (bo + d * bg), 1e-8)
            if self.sg_activation_cap is not None: sg0 = np.minimum(sg0, self.sg_activation_cap)
            guess.sg[activate] = sg0; guess.rs_sm3_sm3[activate] = rsat
        if np.any(deactivate): guess.sg[deactivate] = 0.0; guess.rs_sm3_sm3[deactivate] = self.pvt.rs_sat(guess.pressure_bar[deactivate])
        mask = newmask
    r = self.residual(self.pack(guess, mask), state_old, dt_s, mask)
    if aset > max_active_iter: _event(dt_s, aset, counted, total_newton, False, "active_set", int(mask.sum()))
    return guess, BlackOilNewtonReport(False, total_newton, float(np.linalg.norm(r, np.inf)), aset, total_switches,
                                       cell_measure=self._cell_measure(r, self._cell_weights(state_old, dt_s)),
                                       exit_reason='active_set')


def install(log_path=None):
    """Подменить метод класса вариантом 1; log_path — файл событий (дописывается)."""
    _LOG["path"] = log_path
    RadialBlackOilModel._advance_phases = advance_phases_v1


def uninstall():
    RadialBlackOilModel._advance_phases = _ORIG


if os.environ.get("BUG028_V1") == "1":
    install(os.environ.get("BUG028_LOG"))
