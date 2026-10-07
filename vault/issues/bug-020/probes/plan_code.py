"""BUG-020: код правки прототипа из плана — привязка к экземпляру модели для проверки.

Методы ниже — дословно тексты правок плана (vault/plans/bug-020 ...md, шаг 3):
face_component_fluxes_sm3s с замораживанием ячейки выше по потоку,
_switch_phases, _newton_switching, четвёртая ступень advance. apply(model)
привязывает их к экземпляру (types.MethodType) и включает ступень; advance —
вариант плана на коде ДО DEBT-030 (без блока отчёта общего отказа): на
принятые шаги блок DEBT-030 не влияет.

Использование: import plan_code; plan_code.apply(model)
"""

import types

import numpy as np

from radial_blackoil.blackoil import BlackOilNewtonReport
from radial_blackoil.units import BAR_TO_PA

STATS = {"calls": 0, "ok": 0}


def face_component_fluxes_sm3s(self,state):
    p,rs,sg=state.pressure_bar,state.rs_sm3_sm3,state.sg; n=self.grid.n
    qow,qgfw,qgcw=self._well_fluxes(state)
    if n>1:
        dp=p[:-1]-p[1:]; left=dp>=0
        # BUG-020: the fourth stage holds the upstream cell of faces whose flow
        # direction flipped twice between its Newton iterates (None elsewhere)
        if self._upwind_frozen is not None: left=np.where(self._upwind_frozen,self._upwind_left,left)
        p_up=np.where(left,p[:-1],p[1:]); rs_up=np.where(left,rs[:-1],rs[1:]); sg_up=np.where(left,sg[:-1],sg[1:])
        lo,lg=self._phase_mobilities_surface(p_up,rs_up,sg_up); T=self.grid.internal_transmissibility_m3
        qoi=T*lo*dp*BAR_TO_PA; qgfi=T*lg*dp*BAR_TO_PA; qgci=rs_up*qoi+qgfi
    else: qoi=qgfi=qgci=np.empty(0)
    dpo=p[-1]-self.p_outer_bar
    p_up,rs_up,sg_up=(p[-1],rs[-1],sg[-1]) if dpo>=0 else (self.p_outer_bar,self.outer_rs,0.0)
    lo,lg=self._phase_mobilities_surface(p_up,rs_up,sg_up); To=self.grid.outer_transmissibility_m3
    qoo=float(To*lo*dpo*BAR_TO_PA); qgfo=float(To*lg*dpo*BAR_TO_PA); qgco=float(rs_up*qoo+qgfo)
    return {'oil_well':qow,'free_gas_well':qgfw,'gas_component_well':qgcw,'oil_internal':qoi,'free_gas_internal':qgfi,'gas_component_internal':qgci,'oil_outer':qoo,'free_gas_outer':qgfo,'gas_component_outer':qgco}


def _switch_phases(self,p,x,mask):
    """BUG-020: phase switch at a Newton iterate (p, x) of the fourth stage; returns (x, mask, switches)."""
    rs_sat=self.pvt.rs_sat(p); x=x.copy()
    deact=mask&(x<-self.sg_switch_tol); act=(~mask)&(x>rs_sat+self.rs_switch_tol)
    if np.any(deact):
        # Sg < 0 (method of negative saturations): the cell keeps its gas/oil ratio,
        # (So*Rs_sat/Bo + Sg/Bg)/(So/Bo) = Rs_sat + Sg*Bo/((1-Sg)*Bg) -- the inverse
        # of the closed flash below; clipped at 0 where Sg is far below zero
        sg=x[deact]; pd=p[deact]; bo=self.pvt.bo(pd,rs_sat[deact]); bg=self.pvt.bg(pd)
        x[deact]=np.maximum(rs_sat[deact]+sg*bo/((1.0-sg)*bg),0.0)
    if np.any(act):
        # closed-flash Sg with the BUG-018 cap, as in _advance_phases
        pa=p[act]; rsat=rs_sat[act]; bo=self.pvt.bo(pa,rsat); bg=self.pvt.bg(pa); d=np.maximum(x[act]-rsat,0.0)
        sg0=np.maximum(d*bg/(bo+d*bg),1e-8)
        if self.sg_activation_cap is not None: sg0=np.minimum(sg0,self.sg_activation_cap)
        x[act]=sg0
    m=mask.copy(); m[deact]=False; m[act]=True
    return x,m,int(np.count_nonzero(deact)+np.count_nonzero(act))


def _newton_switching(self,state_old,dt_s,max_iter=40,rtol=1e-8,atol_sm3s=1e-11,dp_rel=0.3,ds_max=0.2,flips_to_freeze=2):
    """BUG-020 fourth stage: Newton with phase switches after every iteration, per-cell update limits, no line search."""
    state_old=state_old.copy(); n=self.grid.n; nf=max(n-1,0)
    mask=state_old.gas_active.copy(); z=self.pack(state_old,mask)
    scale=max(np.linalg.norm(self.residual(z,state_old,dt_s,mask),np.inf),1e-9); tol=atol_sm3s+rtol*scale
    switched=total=0; flips=np.zeros(nf,int); prev=None; polish=False
    self._upwind_frozen=np.zeros(nf,bool); self._upwind_left=np.zeros(nf,bool)
    try:
        for it in range(1,max_iter+2):
            p=z[:n]; left=(p[:-1]-p[1:])>=0
            if not polish:
                # faces whose direction flipped flips_to_freeze times keep their upstream cell
                if prev is not None: flips+=(left!=prev)&~self._upwind_frozen
                fr=(~self._upwind_frozen)&(flips>=flips_to_freeze)
                self._upwind_left=np.where(fr,left,self._upwind_left); self._upwind_frozen=self._upwind_frozen|fr
            prev=left
            J,f=self.finite_difference_jacobian(z,state_old,dt_s,mask); nrm=np.linalg.norm(f,np.inf)
            if nrm<=tol and switched==0:
                fz=self._upwind_frozen
                if fz is None or np.array_equal(self._upwind_left[fz],left[fz]):
                    new=self.unpack(z,mask); new.sg[mask&(new.sg<0)]=0.0
                    # same bound as _trial_is_reasonable: no root with Sg > 0.98
                    ok=not np.any(new.sg[mask]>0.98)
                    return new,BlackOilNewtonReport(ok,it-1,float(nrm),1,total)
                # converged with a held upstream cell the solution contradicts: polish
                # without holding, so the result solves the original upwind scheme
                self._upwind_frozen=None; polish=True; continue
            if it>max_iter: break
            try: dz=self._linear_solve(J,-f)
            except Exception: break
            # per-cell limits (as dpMaxRel, dsMax in OPM Flow); Rs of undersaturated cells >= 0
            x=z[n:]; lim=dp_rel*np.maximum(p,1.0)
            pn=np.maximum(p+np.clip(dz[:n],-lim,lim),1.0+1e-6)
            xn=np.where(mask,x+np.clip(dz[n:],-ds_max,ds_max),np.maximum(x+dz[n:],0.0))
            if not (np.all(np.isfinite(pn)) and np.all(np.isfinite(xn))): break
            xn,mask,switched=self._switch_phases(pn,xn,mask); total+=switched
            z=np.concatenate([pn,xn])
        f=self.residual(z,state_old,dt_s,mask)
        return self.unpack(z,mask),BlackOilNewtonReport(False,max_iter,float(np.linalg.norm(f,np.inf)),1,total)
    finally:
        self._upwind_frozen=None; self._upwind_left=None


def apply(model):
    """Привязать правку плана к экземпляру; ступень 4 — после отказа трёх штатных."""
    model.phase_switching_stage = True
    model._phase_switching = False
    model._upwind_frozen = None
    model._upwind_left = None
    for f in (face_component_fluxes_sm3s, _switch_phases, _newton_switching):
        setattr(model, f.__name__, types.MethodType(f, model))
    orig_phases = model._advance_phases
    orig_advance = model.advance

    def _advance_phases(state_old, dt_s, max_active_iter=12, max_newton=15):
        if model._phase_switching:
            return model._newton_switching(state_old, dt_s)
        return orig_phases(state_old, dt_s, max_active_iter, max_newton)

    def advance(state_old, dt_s, max_active_iter=12, max_newton=15):
        new, rep = orig_advance(state_old, dt_s, max_active_iter, max_newton)
        if rep.converged or not model.phase_switching_stage:
            return new, rep
        STATS["calls"] += 1
        model._phase_switching = True
        try:
            new, rep = model._fallback(state_old, dt_s, max_active_iter, max_newton)
            rep.globalized = True
            rep.phase_switching = True
        finally:
            model._phase_switching = False
        STATS["ok"] += bool(rep.converged)
        return new, rep

    model._advance_phases = _advance_phases
    model.advance = advance
    return model
