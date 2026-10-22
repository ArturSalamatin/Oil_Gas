"""BUG-020: опытная четвёртая ступень advance — общий модуль проб.

install(model, ...) подменяет model.advance на экземпляре: штатный advance;
при его отказе — Ньютон с переключением набора фаз на итерациях:
  - поячеечное ограничение приращений: |dp_i| <= dp_rel p_i, |dSg_i| <= ds_max
    у двухфазных (как dpMaxRel, dsMax в OPM Flow);
  - линейный поиск (ls): 'none' — нет (как OPM Flow); 'l2' — по ||F||_2,
    нет убывания — отказ; 'accept' — нет убывания — полный обрезанный шаг;
  - после каждой итерации — переключение набора фаз в принятой точке:
    S_g < 0 -> однофазная, R_s из сохранения отношения газ/нефть в ячейке;
    R_s > R_s^sat(p) -> двухфазная, S_g «закрытого сосуда» (blackoil.py:363-369);
  - замораживание ячейки «выше по потоку» на внутренних гранях:
    k_freeze > 0 — всех граней с итерации k_freeze (вариант V3 ladder_variants);
    flip_freeze > 0 — только граней, где направление сменилось flip_freeze раз;
    после сходимости, если замороженные направления не совпали с решением, —
    доводка без замораживания (решение — штатной схемы против потока);
  - сходимость: ||F||_inf <= допуск и нет переключений на последней итерации;
    невязка после последней итерации тоже проверяется (не как BUG-021).
Ветка скважины при BHP — по старому состоянию, как в _fallback; несогласованный
результат — отказ (вторую ветку не перебираем: на останове она несогласована).
STATS — счётчики для печати в пробах, TRACE — журнал итераций.
"""

import numpy as np

from radial_blackoil.blackoil import BlackOilNewtonReport
from radial_blackoil.units import BAR_TO_PA as PBAR

DP_REL, DS_MAX, MAX_IT = 0.3, 0.2, 40
STATS = {"calls": 0, "ok": 0, "polish": 0, "iters": []}
TRACE = False


def install(model, k_freeze=0, flip_freeze=2, dp_rel=DP_REL, ds_max=DS_MAX, max_it=MAX_IT, ls="none"):
    n = model.grid.n
    orig_advance = model.advance
    # frozen: грани с замороженным направлением; dir: направление (True — выше по потоку левая ячейка)
    box = {"frozen": None, "dir": None}

    def fluxes(state):
        """Копия face_component_fluxes_sm3s (blackoil.py:156-169) с замороженной ячейкой выше по потоку."""
        self = model
        p, rs, sg = state.pressure_bar, state.rs_sm3_sm3, state.sg
        qow, qgfw, qgcw = self._well_fluxes(state)
        dp = p[:-1] - p[1:]
        left = dp >= 0
        if box["frozen"] is not None:
            left = np.where(box["frozen"], box["dir"], left)
        p_up = np.where(left, p[:-1], p[1:])
        rs_up = np.where(left, rs[:-1], rs[1:])
        sg_up = np.where(left, sg[:-1], sg[1:])
        lo, lg = self._phase_mobilities_surface(p_up, rs_up, sg_up)
        T = self.grid.internal_transmissibility_m3
        qoi = T * lo * dp * PBAR
        qgfi = T * lg * dp * PBAR
        qgci = rs_up * qoi + qgfi
        dpo = p[-1] - self.p_outer_bar
        p_u, rs_u, sg_u = (p[-1], rs[-1], sg[-1]) if dpo >= 0 else (self.p_outer_bar, self.outer_rs, 0.0)
        lo, lg = self._phase_mobilities_surface(p_u, rs_u, sg_u)
        To = self.grid.outer_transmissibility_m3
        qoo = float(To * lo * dpo * PBAR)
        qgfo = float(To * lg * dpo * PBAR)
        qgco = float(rs_u * qoo + qgfo)
        return {'oil_well': qow, 'free_gas_well': qgfw, 'gas_component_well': qgcw, 'oil_internal': qoi,
                'free_gas_internal': qgfi, 'gas_component_internal': qgci, 'oil_outer': qoo,
                'free_gas_outer': qgfo, 'gas_component_outer': qgco}

    model.face_component_fluxes_sm3s = fluxes

    def switch_phases(pn, xn, mask):
        pvt = model.pvt
        rs_sat = pvt.rs_sat(pn)
        deact = mask & (xn < -model.sg_switch_tol)
        act = (~mask) & (xn > rs_sat + model.rs_switch_tol)
        xn = xn.copy()
        if np.any(deact):
            sg = xn[deact]
            bo = pvt.bo(pn[deact], rs_sat[deact])
            bg = pvt.bg(pn[deact])
            xn[deact] = np.maximum(rs_sat[deact] + sg * bo / ((1.0 - sg) * bg), 0.0)
        if np.any(act):
            rsat = rs_sat[act]
            bo = pvt.bo(pn[act], rsat)
            bg = pvt.bg(pn[act])
            d = np.maximum(xn[act] - rsat, 0.0)
            sg0 = np.maximum(d * bg / (bo + d * bg), 1e-8)
            if model.sg_activation_cap is not None:
                sg0 = np.minimum(sg0, model.sg_activation_cap)
            xn[act] = sg0
        m = mask.copy()
        m[deact] = False
        m[act] = True
        return xn, m, int(deact.sum() + act.sum())

    def newton(state_old, dt, rtol=1e-8, atol=1e-11):
        mask = state_old.gas_active.copy()
        z = model.pack(state_old, mask)
        scale = max(np.linalg.norm(model.residual(z, state_old, dt, mask), np.inf), 1e-9)
        tol = atol + rtol * scale
        switched = 0
        freezing = k_freeze > 0 or flip_freeze > 0
        box["frozen"] = None
        flips = np.zeros(n - 1, int)
        prev_dir = None
        polished = False
        try:
            for it in range(1, max_it + 2):
                p = z[:n]
                cur = (p[:-1] - p[1:]) >= 0
                if freezing:
                    if box["frozen"] is None:
                        box["frozen"] = np.zeros(n - 1, bool)
                        box["dir"] = cur.copy()
                    if prev_dir is not None:
                        flips += (cur != prev_dir) & ~box["frozen"]
                    if k_freeze > 0 and it > k_freeze:
                        new_fr = ~box["frozen"]
                    elif flip_freeze > 0:
                        new_fr = (~box["frozen"]) & (flips >= flip_freeze)
                    else:
                        new_fr = np.zeros(n - 1, bool)
                    box["dir"] = np.where(new_fr, cur, box["dir"])
                    box["frozen"] = box["frozen"] | new_fr
                prev_dir = cur
                f = model.residual(z, state_old, dt, mask)
                nrm = np.linalg.norm(f, np.inf)
                if nrm <= tol and switched == 0:
                    fr = box["frozen"]
                    if fr is None or not fr.any() or np.array_equal(box["dir"][fr], cur[fr]):
                        new = model.unpack(z, mask)
                        new.sg[mask & (new.sg < 0)] = 0.0
                        STATS["polish"] += polished
                        return new, BlackOilNewtonReport(True, it - 1, float(nrm))
                    # сошлись с замороженными направлениями, не совпавшими с решением:
                    # доводка без замораживания
                    box["frozen"] = None
                    freezing = False
                    polished = True
                    continue
                if it > max_it:
                    break
                J, f = model.finite_difference_jacobian(z, state_old, dt, mask)
                try:
                    dz = model._linear_solve(J, -f)
                except Exception:
                    break
                x = z[n:]
                lim = dp_rel * np.maximum(p, 1.0)
                dp = np.clip(dz[:n], -lim, lim)
                dx = np.where(mask, np.clip(dz[n:], -ds_max, ds_max), dz[n:])
                mf = np.linalg.norm(f)
                alpha = 1.0
                acc = False
                for _ in range(10 if ls != "none" else 1):
                    pn = np.maximum(p + alpha * dp, 1.0 + 1e-6)
                    xn = np.where(mask, x + alpha * dx, np.maximum(x + alpha * dx, 0.0))
                    trial = np.concatenate([pn, xn])
                    if not np.all(np.isfinite(trial)):
                        alpha *= 0.5
                        continue
                    if ls == "none" or np.linalg.norm(model.residual(trial, state_old, dt, mask)) < mf:
                        acc = True
                        break
                    alpha *= 0.5
                if not acc and ls == "accept":
                    alpha = 1.0
                    pn = np.maximum(p + dp, 1.0 + 1e-6)
                    xn = np.where(mask, x + dx, np.maximum(x + dx, 0.0))
                    acc = bool(np.all(np.isfinite(pn)) and np.all(np.isfinite(xn)))
                if TRACE:
                    nfr = 0 if box["frozen"] is None else int(box["frozen"].sum())
                    print(f"      it {it:2d}: |F| = {nrm:.2e}  alpha = {alpha if acc else 0:.2e}  "
                          f"2ф = {int(mask.sum())}  заморожено граней: {nfr}  p0 = {p[0]:.2f}")
                if not acc:
                    break
                xn, mask, switched = switch_phases(pn, xn, mask)
                z = np.concatenate([pn, xn])
            f = model.residual(z, state_old, dt, mask)
            return model.unpack(z, mask), BlackOilNewtonReport(False, max_it, float(np.linalg.norm(f, np.inf)))
        finally:
            box["frozen"] = None

    def advance(state_old, dt_s, *a, **kw):
        new, rep = orig_advance(state_old, dt_s, *a, **kw)
        if rep.converged:
            return new, rep
        STATS["calls"] += 1
        shut = None
        if model.control_mode == "BHP":
            target = float(model.p_bhp_bar)
            shut = float(state_old.pressure_bar[0]) <= target
            model._well_branch = "shut" if shut else "open"
        try:
            new, rep = newton(state_old, dt_s)
        finally:
            model._well_branch = None
        if rep.converged and shut is not None:
            p0 = float(new.pressure_bar[0])
            if (p0 > target) if shut else (p0 < target):
                rep.converged = False
        if rep.converged:
            STATS["ok"] += 1
            STATS["iters"].append(rep.iterations)
            if shut is not None:
                rep.well_branch = "shut" if shut else "open"
        rep.fallback = True
        rep.globalized = True
        return new, rep

    model.advance = advance
    model._stage4_newton = newton
    return model
