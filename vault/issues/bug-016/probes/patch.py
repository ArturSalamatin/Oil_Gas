"""BUG-016: правки глобализации Ньютона прототипа — подмена методов RadialBlackOilModel.

install(mode, cap, chop) заменяет на уровне КЛАССА (действует на все модели,
созданные фабрикой):
  _newton_fixed_active_set — линейный поиск по ||F||_2 вместо ||F||_inf;
                             необязательный ограничитель |dS_g| <= chop за итерацию;
  _advance_phases          — начальное S_g активации <= cap.
mode:
  "none"     — исходный алгоритм (копии методов побитово равны оригиналу);
  "always"   — правки на каждом шаге;
  "fallback" — правки только в запасном пути advance (признак — self._sg_lower_bound
               is None: его выставляет только запасной путь BUG-014).
Критерий сходимости Ньютона (||F||_inf <= atol + rtol*scale) не меняется.

Счётчики вызовов advance — COUNT (сколько вызовов, отказов, запасных путей).
"""

import os
import sys
from pathlib import Path

import numpy as np

# Дерево numerical_solver: по умолчанию — основной каталог; для сверки
# реализации в worktree — $env:BUG016_NS (вместе с $env:PYTHONPATH на тот же
# каталог, чтобы и gpn_multiphase_solver брался оттуда)
NS = Path(os.environ.get("BUG016_NS") or Path(__file__).resolve().parents[4] / "numerical_solver")
sys.path.insert(0, str(NS / "HydroSolverPrototype" / "Prototype_1.0.3"))
from radial_blackoil import blackoil as bo  # noqa: E402

M = bo.RadialBlackOilModel
_ORIG_ADVANCE = M.advance
CFG = {"mode": "none", "cap": None, "chop": None}
COUNT = {"advance": 0, "failed": 0, "fallback_ok": 0}


def _on(self):
    """Включены ли правки на этом вызове."""
    if CFG["mode"] == "always":
        return True
    return CFG["mode"] == "fallback" and self._sg_lower_bound is None


def newton(self, z0, state_old, dt_s, gas_active, max_iter=15, rtol=1e-8, atol_sm3s=1e-11):
    """Копия _newton_fixed_active_set (blackoil.py:211-226) с переключаемой нормой поиска."""
    on = _on(self)
    # inf_norm — проверка ограничителя chop без смены нормы поиска
    l2 = on and not CFG.get("inf_norm", False)
    merit = (lambda f: np.linalg.norm(f)) if l2 else (lambda f: np.linalg.norm(f, np.inf))
    n = self.grid.n
    z = np.asarray(z0, float).copy()
    f_initial = self.residual(z, state_old, dt_s, gas_active)
    scale = max(np.linalg.norm(f_initial, np.inf), 1e-9)
    for it in range(1, max_iter + 1):
        J, f = self.finite_difference_jacobian(z, state_old, dt_s, gas_active)
        nrm = np.linalg.norm(f, np.inf)
        if nrm <= atol_sm3s + rtol * scale:
            return z, bo.BlackOilNewtonReport(True, it - 1, float(nrm))
        try:
            dz = self._linear_solve(J, -f)
        except Exception:
            return z, bo.BlackOilNewtonReport(False, it, float(nrm))
        if on and CFG["chop"] is not None:
            # Ограничитель приращения: весь шаг масштабируется так, чтобы
            # max|dS_g| по двухфазным ячейкам не превышал chop
            dsg = np.abs(dz[n:][gas_active])
            if dsg.size and dsg.max() > CFG["chop"]:
                dz = dz * (CFG["chop"] / dsg.max())
        mf = merit(f)
        alpha = 1.0
        accepted = False
        for _ in range(12):
            trial = z + alpha * dz
            if self._trial_is_reasonable(trial, gas_active):
                ft = self.residual(trial, state_old, dt_s, gas_active)
                if merit(ft) < mf:
                    z = trial
                    accepted = True
                    break
            alpha *= 0.5
        if not accepted:
            return z, bo.BlackOilNewtonReport(False, it, float(nrm))
    f = self.residual(z, state_old, dt_s, gas_active)
    return z, bo.BlackOilNewtonReport(False, max_iter, float(np.linalg.norm(f, np.inf)))


def advance_phases(self, state_old, dt_s, max_active_iter=12, max_newton=15):
    """Копия _advance_phases (blackoil.py:264-282); при правках — S_g активации <= cap."""
    state_old = state_old.copy()
    mask = state_old.gas_active.copy()
    guess = state_old.copy()
    total_switches = total_newton = 0
    for aset in range(1, max_active_iter + 1):
        z, report = self._newton_fixed_active_set(self.pack(guess, mask), state_old, dt_s, mask,
                                                  max_iter=max_newton)
        total_newton += report.iterations
        if not report.converged:
            report.active_set_iterations = aset
            report.phase_switches = total_switches
            return guess, report
        trial = self.unpack(z, mask)
        rs_sat = self.pvt.rs_sat(trial.pressure_bar)
        activate = (~mask) & (trial.rs_sm3_sm3 > rs_sat + self.rs_switch_tol)
        deactivate = mask & (trial.sg < -self.sg_switch_tol)
        ns = int(np.count_nonzero(activate) + np.count_nonzero(deactivate))
        total_switches += ns
        if ns == 0:
            tiny = mask & (trial.sg < 0) & (trial.sg >= -self.sg_switch_tol)
            trial.sg[tiny] = 0.0
            trial.gas_active = mask.copy()
            report.iterations = total_newton
            report.active_set_iterations = aset
            report.phase_switches = total_switches
            return trial, report
        newmask = mask.copy()
        newmask[activate] = True
        newmask[deactivate] = False
        guess = trial.copy()
        guess.gas_active = newmask.copy()
        if np.any(activate):
            pa = guess.pressure_bar[activate]
            rtot = guess.rs_sm3_sm3[activate].copy()
            rsat = self.pvt.rs_sat(pa)
            bo_, bg = self.pvt.bo(pa, rsat), self.pvt.bg(pa)
            d = np.maximum(rtot - rsat, 0.0)
            sg0 = np.maximum(d * bg / (bo_ + d * bg), 1e-8)
            if _on(self) and CFG["cap"] is not None:
                sg0 = np.minimum(sg0, CFG["cap"])
            guess.sg[activate] = sg0
            guess.rs_sm3_sm3[activate] = rsat
        if np.any(deactivate):
            guess.sg[deactivate] = 0.0
            guess.rs_sm3_sm3[deactivate] = self.pvt.rs_sat(guess.pressure_bar[deactivate])
        mask = newmask
    r = self.residual(self.pack(guess, mask), state_old, dt_s, mask)
    return guess, bo.BlackOilNewtonReport(False, total_newton, float(np.linalg.norm(r, np.inf)),
                                          max_active_iter, total_switches)


def advance(self, state_old, dt_s, max_active_iter=12, max_newton=15):
    """Исходный advance + счётчики; в режиме tier3 — третья ступень при отказе обеих."""
    if CFG["mode"] == "tier3":
        # Ступени 1-2: исходный алгоритм и запасной путь BUG-014 без правок.
        # try/finally: тесты BUG-014 бросают исключения изнутри advance — без
        # восстановления режим оставался "none" до конца сессии pytest.
        try:
            CFG["mode"] = "none"
            new, rep = _ORIG_ADVANCE(self, state_old, dt_s, max_active_iter, max_newton)
            if not rep.converged:
                # Ступень 3: запасной путь BUG-014 с правками BUG-016 (исходная
                # попытка внутри повторяется без правок — в пробе это лишь цена)
                CFG["mode"] = "fallback"
                new, rep = _ORIG_ADVANCE(self, state_old, dt_s, max_active_iter, max_newton)
                if rep.converged:
                    COUNT["tier3_ok"] = COUNT.get("tier3_ok", 0) + 1
        finally:
            CFG["mode"] = "tier3"
    else:
        new, rep = _ORIG_ADVANCE(self, state_old, dt_s, max_active_iter, max_newton)
    COUNT["advance"] += 1
    if not rep.converged:
        COUNT["failed"] += 1
    elif getattr(rep, "fallback", False):
        COUNT["fallback_ok"] += 1
    return new, rep


def install(mode="none", cap=0.3, chop=None):
    CFG.update(mode=mode, cap=cap, chop=chop)
    M._newton_fixed_active_set = newton
    M._advance_phases = advance_phases
    M.advance = advance
