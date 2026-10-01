"""Prototype 1 two-component radial black-oil model.

Physics and Newton/active-set logic are unchanged from the validated Prototype 1
formulation. Version 1.0.3 keeps the grouped finite-difference Jacobian and
supports sparse or dense linear algebra as a numerical backend choice.
Local changes (GPN project, BUG-014): when the original step fails, advance()
retries with the BHP well branch as an outer active constraint and no lower
bound on Sg of two-phase cells.
"""
from dataclasses import dataclass
import numpy as np
from scipy.linalg import solve as dense_solve
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu
from .state import BlackOilState
from .units import BAR_TO_PA, CP_TO_PA_S

@dataclass
class BlackOilNewtonReport:
    converged: bool
    iterations: int
    residual_inf: float
    active_set_iterations: int = 0
    phase_switches: int = 0
    well_branch: str = ''     # BHP control: branch of the accepted step ('open'/'shut'), BUG-014
    well_switches: int = 0    # branch changes in advance's fallback, BUG-014
    fallback: bool = False    # step solved by advance's fallback, BUG-014
    globalized: bool = False  # advance's third stage ran (||F||_2 line search, Sg step limit), BUG-016

class RadialBlackOilModel:
    def __init__(self, grid, rock, pvt, relperm, p_bhp_bar, p_outer_bar,
                 outer_rs_sm3_sm3, skin=0.0, rs_switch_tol=1e-5,
                 sg_switch_tol=1e-9, gas_residual_scale=None,
                 jacobian_mode='grouped', linear_solver='sparse'):
        self.grid=grid; self.rock=rock; self.pvt=pvt; self.relperm=relperm
        self.p_bhp_bar=float(p_bhp_bar); self.p_outer_bar=float(p_outer_bar)
        self.outer_rs=float(outer_rs_sm3_sm3); self.skin=float(skin)
        self.rs_switch_tol=float(rs_switch_tol); self.sg_switch_tol=float(sg_switch_tol)
        self.gas_residual_scale=float(gas_residual_scale or max(self.outer_rs,1.0))
        # Well-control state. BHP is the default; OIL_RATE is imposed by
        # eliminating BHP algebraically from the well oil-rate equation.
        self.control_mode='BHP'; self.oil_rate_target_sm3_day=None; self.min_bhp_bar=None
        self._last_effective_bhp_bar=self.p_bhp_bar; self._last_constraint_active=False
        # BUG-014: set by advance's fallback only.  _well_branch forces the BHP
        # well branch for the whole nonlinear solve (None -> chosen from p0);
        # _sg_lower_bound is the line-search bound on Sg of two-phase cells.
        self._well_branch=None; self._sg_lower_bound=-0.05
        # BUG-016: set by advance's third stage only.  _line_search_l2 accepts a
        # Newton step on a decrease of ||F||_2 instead of ||F||_inf (the Newton
        # direction is a descent direction of ||F||_2^2, not of ||F||_inf);
        # _sg_step_max limits |dSg| of two-phase cells per Newton update by
        # scaling the whole update (Appleyard-type chop, as ds_max in OPM Flow).
        self._line_search_l2=False; self._sg_step_max=None
        if jacobian_mode not in ('grouped','reference'): raise ValueError("jacobian_mode must be 'grouped' or 'reference'")
        if linear_solver not in ('sparse','dense'): raise ValueError("linear_solver must be 'sparse' or 'dense'")
        self.jacobian_mode=jacobian_mode; self.linear_solver=linear_solver

    def set_bhp_control(self,bhp_bar):
        self.control_mode='BHP'; self.p_bhp_bar=float(bhp_bar)
        self.oil_rate_target_sm3_day=None; self.min_bhp_bar=None
        self._last_effective_bhp_bar=self.p_bhp_bar; self._last_constraint_active=False

    def set_oil_rate_control(self,oil_rate_sm3_day,min_bhp_bar=None):
        q=float(oil_rate_sm3_day)
        if q < 0: raise ValueError('oil-rate target must be non-negative for producer')
        self.control_mode='OIL_RATE'; self.oil_rate_target_sm3_day=q
        self.min_bhp_bar=None if min_bhp_bar is None else float(min_bhp_bar)

    def _well_fluxes(self,state):
        p0=float(state.pressure_bar[0]); rs0=float(state.rs_sm3_sm3[0]); sg0=float(state.sg[0])
        lo,lg=self._phase_mobilities_surface(p0,rs0,sg0); lo=float(lo); lg=float(lg)
        tw=self.grid.well_transmissibility_m3(self.skin)
        if self.control_mode=='OIL_RATE':
            qtarget=float(self.oil_rate_target_sm3_day)/86400.0
            if lo <= 0:
                bhp_req=-np.inf
            else:
                bhp_req=p0-qtarget/(tw*lo*BAR_TO_PA)
            if self.min_bhp_bar is not None and bhp_req < self.min_bhp_bar:
                # Producer-only semantics: a minimum-BHP constraint may reduce
                # production to zero, but it must never reverse the well into
                # injection.  When reservoir pressure is below the BHP floor,
                # the well is shut and its effective BHP floats to p0.
                if p0 <= float(self.min_bhp_bar):
                    bhp=p0; qow=0.0; qgfw=0.0
                else:
                    bhp=float(self.min_bhp_bar); dpw=p0-bhp
                    qow=float(tw*lo*dpw*BAR_TO_PA); qgfw=float(tw*lg*dpw*BAR_TO_PA)
                self._last_constraint_active=True
            else:
                bhp=float(bhp_req); dpw=p0-bhp
                qow=qtarget; qgfw=float(tw*lg*dpw*BAR_TO_PA)
                self._last_constraint_active=False
            self._last_effective_bhp_bar=bhp
        else:
            # BHP-controlled producer.  If the requested BHP is above the
            # current reservoir pressure, enforcing it would inject fluid.
            # A producer instead shuts in until p0 rises above the target.
            target=float(self.p_bhp_bar)
            # BUG-014: in advance's fallback the branch is fixed for the whole
            # Newton solve.  Choosing it from the current iterate put Newton on
            # the branch where the step had no consistent solution.
            branch=self._well_branch
            if branch is None: branch='shut' if p0 <= target else 'open'
            if branch=='shut':
                bhp=p0; qow=0.0; qgfw=0.0
            else:
                # 'open' without the sign check: q < 0 (injection) is allowed on
                # intermediate iterates; advance rejects it after convergence.
                bhp=target; dpw=p0-bhp
                qow=float(tw*lo*dpw*BAR_TO_PA); qgfw=float(tw*lg*dpw*BAR_TO_PA)
            self._last_effective_bhp_bar=bhp; self._last_constraint_active=False
        qgcw=float(rs0*qow+qgfw)
        return qow,qgfw,qgcw

    def pack(self,state,gas_active=None):
        mask=state.gas_active if gas_active is None else np.asarray(gas_active,bool)
        x=np.where(mask,state.sg,state.rs_sm3_sm3)
        return np.concatenate([state.pressure_bar,x])
    def unpack(self,z,gas_active):
        mask=np.asarray(gas_active,dtype=bool); n=self.grid.n; z=np.asarray(z,float)
        p,x=z[:n],z[n:]
        rs=np.where(mask,self.pvt.rs_sat(p),x); sg=np.where(mask,x,0.0)
        return BlackOilState(p,rs,sg,mask.copy())
    def oil_properties(self,state): return self.pvt.bo(state.pressure_bar,state.rs_sm3_sm3),self.pvt.mu_o(state.pressure_bar,state.rs_sm3_sm3)
    def gas_properties(self,state): return self.pvt.bg(state.pressure_bar),self.pvt.mu_g(state.pressure_bar)
    def component_inventories(self,state):
        p,sg=state.pressure_bar,state.sg; so=1.0-sg
        bo,_=self.oil_properties(state); bg,_=self.gas_properties(state)
        pv=self.rock.pore_volume_m3(self.grid.bulk_volumes_m3,p)
        return pv*so/bo, pv*(state.rs_sm3_sm3*so/bo+sg/bg)
    def _phase_mobilities_surface(self,p,rs,sg):
        p=np.asarray(p,float); rs=np.asarray(rs,float); sg=np.asarray(sg,float)
        bo=self.pvt.bo(p,rs); muo=self.pvt.mu_o(p,rs); bg=self.pvt.bg(p); mug=self.pvt.mu_g(p)
        return self.relperm.kro(sg)/(muo*CP_TO_PA_S)/bo, self.relperm.krg(sg)/(mug*CP_TO_PA_S)/bg
    def face_component_fluxes_sm3s(self,state):
        p,rs,sg=state.pressure_bar,state.rs_sm3_sm3,state.sg; n=self.grid.n
        qow,qgfw,qgcw=self._well_fluxes(state)
        if n>1:
            dp=p[:-1]-p[1:]; left=dp>=0
            p_up=np.where(left,p[:-1],p[1:]); rs_up=np.where(left,rs[:-1],rs[1:]); sg_up=np.where(left,sg[:-1],sg[1:])
            lo,lg=self._phase_mobilities_surface(p_up,rs_up,sg_up); T=self.grid.internal_transmissibility_m3
            qoi=T*lo*dp*BAR_TO_PA; qgfi=T*lg*dp*BAR_TO_PA; qgci=rs_up*qoi+qgfi
        else: qoi=qgfi=qgci=np.empty(0)
        dpo=p[-1]-self.p_outer_bar
        p_up,rs_up,sg_up=(p[-1],rs[-1],sg[-1]) if dpo>=0 else (self.p_outer_bar,self.outer_rs,0.0)
        lo,lg=self._phase_mobilities_surface(p_up,rs_up,sg_up); To=self.grid.outer_transmissibility_m3
        qoo=float(To*lo*dpo*BAR_TO_PA); qgfo=float(To*lg*dpo*BAR_TO_PA); qgco=float(rs_up*qoo+qgfo)
        return {'oil_well':qow,'free_gas_well':qgfw,'gas_component_well':qgcw,'oil_internal':qoi,'free_gas_internal':qgfi,'gas_component_internal':qgci,'oil_outer':qoo,'free_gas_outer':qgfo,'gas_component_outer':qgco}
    def net_component_outflow(self,state):
        f=self.face_component_fluxes_sm3s(state); oil=np.zeros(self.grid.n); gas=np.zeros(self.grid.n)
        oil[0]+=f['oil_well']; gas[0]+=f['gas_component_well']
        if self.grid.n>1:
            oil[:-1]+=f['oil_internal']; oil[1:]-=f['oil_internal']; gas[:-1]+=f['gas_component_internal']; gas[1:]-=f['gas_component_internal']
        oil[-1]+=f['oil_outer']; gas[-1]+=f['gas_component_outer']; return oil,gas
    def physical_residual(self,z,state_old,dt_s,gas_active):
        new=self.unpack(z,gas_active); oi1,gi1=self.component_inventories(new); oi0,gi0=self.component_inventories(state_old); qo,qg=self.net_component_outflow(new)
        return np.concatenate([(oi1-oi0)/float(dt_s)+qo,(gi1-gi0)/float(dt_s)+qg])
    def residual(self,z,state_old,dt_s,gas_active):
        r=self.physical_residual(z,state_old,dt_s,gas_active); r[self.grid.n:]/=self.gas_residual_scale; return r
    def _pressure_fd_step(self,p_bar,gas_active,p_rel_step=1e-6,p_abs_step=1e-4):
        """One-sided pressure perturbation that stays on the same PVTO-saturation segment.

        For gas-active cells Rs=Rs_sat(p).  Rs_sat is piecewise linear and has
        derivative kinks at the saturated PVTO pressure knots.  A blindly
        positive finite-difference perturbation can straddle a kink (most
        notably the max-Rs bubble point where Rs_sat clamps), corrupting the
        Newton Jacobian exactly as a cell crosses the phase boundary.
        """
        p=float(p_bar); h=max(p_abs_step,p_rel_step*max(abs(p),1.0))
        if not gas_active: return h
        knots=self.pvt.pb; idx=int(np.searchsorted(knots,p,side='left'))
        lower=knots[idx-1] if idx>0 else -np.inf
        upper=knots[idx] if idx<len(knots) else np.inf
        room_minus=p-lower; room_plus=upper-p
        if room_plus <= 1.25*h and room_minus > h: return -h
        if room_minus <= 1.25*h and room_plus > h: return h
        return h

    def finite_difference_jacobian_reference(self,z,state_old,dt_s,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
        z=np.asarray(z,float); f0=self.residual(z,state_old,dt_s,gas_active); J=np.empty((z.size,z.size)); n=self.grid.n
        for j in range(z.size):
            h=self._pressure_fd_step(z[j],bool(gas_active[j]),p_rel_step,p_abs_step) if j<n else (sg_abs_step if gas_active[j-n] else max(rs_abs_step,1e-6*max(abs(z[j]),1.0)))
            zp=z.copy(); zp[j]+=h; J[:,j]=(self.residual(zp,state_old,dt_s,gas_active)-f0)/h
        return J,f0
    def finite_difference_jacobian_grouped(self,z,state_old,dt_s,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
        z=np.asarray(z,float); f0=self.residual(z,state_old,dt_s,gas_active); n=self.grid.n; J=np.zeros((2*n,2*n),float)
        for block in (0,1):
            for color in range(3):
                zp=z.copy(); cols=[]
                for i in range(color,n,3):
                    j=i if block==0 else n+i
                    h=self._pressure_fd_step(z[j],bool(gas_active[i]),p_rel_step,p_abs_step) if block==0 else (sg_abs_step if gas_active[i] else max(rs_abs_step,1e-6*max(abs(z[j]),1.0)))
                    zp[j]+=h; cols.append((i,j,h))
                df=self.residual(zp,state_old,dt_s,gas_active)-f0
                for i,j,h in cols:
                    rows=np.arange(max(0,i-1),min(n,i+2)); J[rows,j]=df[rows]/h; J[n+rows,j]=df[n+rows]/h
        return J,f0
    def finite_difference_jacobian(self,*args,**kwargs):
        return self.finite_difference_jacobian_reference(*args,**kwargs) if self.jacobian_mode=='reference' else self.finite_difference_jacobian_grouped(*args,**kwargs)
    def _linear_solve(self,J,b):
        if self.linear_solver=='sparse': return splu(csc_matrix(J)).solve(b)
        return dense_solve(J,b,assume_a='gen',check_finite=True)
    def _trial_is_reasonable(self,z,gas_active):
        n=self.grid.n; p=z[:n]; x=z[n:]
        if not np.all(np.isfinite(z)) or np.any(p<=1.0): return False
        if np.any(x[~gas_active]<-1e-8) or np.any(x[~gas_active]>self.pvt.max_rs*1.5): return False
        # BUG-014: the lower bound on Sg of two-phase cells is an attribute.  The
        # original algorithm keeps -0.05; advance's fallback sets None (method of
        # negative saturations): Sg < 0 is a smooth extension of the cell
        # equations (inventories linear in Sg, PVT independent of Sg, relperm
        # tables clamp at the first row), and the phase active set switches such
        # cells after convergence.  With -0.05 every trial was rejected when free
        # gas dissolved in a whole zone (BHP raised above p0).
        lo=self._sg_lower_bound
        if (lo is not None and np.any(x[gas_active]<lo)) or np.any(x[gas_active]>0.98): return False
        return True
    def _newton_fixed_active_set(self,z0,state_old,dt_s,gas_active,max_iter=15,rtol=1e-8,atol_sm3s=1e-11):
        z=np.asarray(z0,float).copy(); f_initial=self.residual(z,state_old,dt_s,gas_active); scale=max(np.linalg.norm(f_initial,np.inf),1e-9)
        # BUG-016: norm of the line search; the convergence test stays on ||F||_inf.
        # With defaults the comparison is norm(ft,inf)<nrm, bitwise as before.
        merit=(lambda v: np.linalg.norm(v)) if self._line_search_l2 else (lambda v: np.linalg.norm(v,np.inf))
        for it in range(1,max_iter+1):
            J,f=self.finite_difference_jacobian(z,state_old,dt_s,gas_active); nrm=np.linalg.norm(f,np.inf)
            if nrm<=atol_sm3s+rtol*scale: return z,BlackOilNewtonReport(True,it-1,float(nrm))
            try: dz=self._linear_solve(J,-f)
            except Exception: return z,BlackOilNewtonReport(False,it,float(nrm))
            if self._sg_step_max is not None:
                # BUG-016: scale the whole update (p and Sg together, the Newton
                # direction is kept) so that |dSg| of two-phase cells <= limit
                dsg=np.abs(dz[self.grid.n:][gas_active])
                if dsg.size and dsg.max()>self._sg_step_max: dz=dz*(self._sg_step_max/dsg.max())
            mf=merit(f); alpha=1.0; accepted=False
            for _ in range(12):
                trial=z+alpha*dz
                if self._trial_is_reasonable(trial,gas_active):
                    ft=self.residual(trial,state_old,dt_s,gas_active)
                    if merit(ft)<mf: z=trial; accepted=True; break
                alpha*=0.5
            if not accepted: return z,BlackOilNewtonReport(False,it,float(nrm))
        f=self.residual(z,state_old,dt_s,gas_active); return z,BlackOilNewtonReport(False,max_iter,float(np.linalg.norm(f,np.inf)))
    def advance(self,state_old,dt_s,max_active_iter=12,max_newton=15):
        """One implicit step: the original algorithm; on failure a fallback with the
        BHP well branch as an outer constraint and no lower bound on Sg (BUG-014);
        if that fails too, the fallback again with a globalized Newton (BUG-016)."""
        new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
        if rep.converged:
            if self.control_mode=='BHP':
                # branch the automatic rule takes on the accepted state
                p0=float(new.pressure_bar[0])
                rep.well_branch='shut' if p0<=float(self.p_bhp_bar) else 'open'
            return new,rep
        # Fallback only: where the original algorithm converges, results stay
        # bitwise; with the bound removed always, deep drawdowns needed more
        # step splitting than before (BUG-014 audit).
        new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton)
        if rep.converged: return new,rep
        # Third stage (BUG-016), only where the fallback fails too, so every step
        # the first two stages solve stays bitwise.  Mass phase activation with a
        # closed-flash Sg guess (0.55-0.71 at Rs0 = 150 against 0.22 in the
        # solution) stalls the ||F||_inf line search; step splitting does not help.
        # Measured alternatives: in the fallback itself example 03 got worse, in
        # every step example 10 got worse (plan BUG-016, 1.3).
        self._line_search_l2=True; self._sg_step_max=0.2
        try:
            new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton)
            rep.globalized=True; return new,rep
        finally:
            self._line_search_l2=False; self._sg_step_max=None
    def _fallback(self,state_old,dt_s,max_active_iter,max_newton):
        """BUG-014 fallback: no lower bound on Sg; BHP control fixes the well branch
        (start from the old state's branch, accept a consistent result only, try the
        other branch once); OIL_RATE control: a plain retry without the Sg bound."""
        self._sg_lower_bound=None
        try:
            if self.control_mode!='BHP':
                new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
                rep.fallback=True; return new,rep
            target=float(self.p_bhp_bar)
            # Start from the branch of the old state; shut-in steps start on 'shut'.
            branch='shut' if float(state_old.pressure_bar[0])<=target else 'open'
            tried=[]
            while True:
                tried.append(branch); self._well_branch=branch
                new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
                rep.fallback=True; rep.well_branch=branch; rep.well_switches=len(tried)-1
                if rep.converged:
                    p0=float(new.pressure_bar[0])
                    # open: q = WI*lambda*(p0-target) >= 0; shut: p0 <= target
                    if (p0>=target) if branch=='open' else (p0<=target): return new,rep
                # Newton failed or the branch is inconsistent: the other branch, once
                other='open' if branch=='shut' else 'shut'
                if other in tried:
                    rep.converged=False; return new,rep
                branch=other
        finally:
            self._sg_lower_bound=-0.05; self._well_branch=None
    def _advance_phases(self,state_old,dt_s,max_active_iter=12,max_newton=15):
        """Phase active-set loop (unchanged Prototype 1 logic)."""
        state_old=state_old.copy(); mask=state_old.gas_active.copy(); guess=state_old.copy(); total_switches=total_newton=0
        for aset in range(1,max_active_iter+1):
            z,report=self._newton_fixed_active_set(self.pack(guess,mask),state_old,dt_s,mask,max_iter=max_newton); total_newton+=report.iterations
            if not report.converged:
                report.active_set_iterations=aset; report.phase_switches=total_switches; return guess,report
            trial=self.unpack(z,mask); rs_sat=self.pvt.rs_sat(trial.pressure_bar)
            activate=(~mask)&(trial.rs_sm3_sm3>rs_sat+self.rs_switch_tol); deactivate=mask&(trial.sg<-self.sg_switch_tol)
            ns=int(np.count_nonzero(activate)+np.count_nonzero(deactivate)); total_switches+=ns
            if ns==0:
                tiny=mask&(trial.sg<0)&(trial.sg>=-self.sg_switch_tol); trial.sg[tiny]=0.0; trial.gas_active=mask.copy(); report.iterations=total_newton; report.active_set_iterations=aset; report.phase_switches=total_switches; return trial,report
            newmask=mask.copy(); newmask[activate]=True; newmask[deactivate]=False; guess=trial.copy(); guess.gas_active=newmask.copy()
            if np.any(activate):
                pa=guess.pressure_bar[activate]; rtot=guess.rs_sm3_sm3[activate].copy(); rsat=self.pvt.rs_sat(pa); bo=self.pvt.bo(pa,rsat); bg=self.pvt.bg(pa); d=np.maximum(rtot-rsat,0.0)
                guess.sg[activate]=np.maximum(d*bg/(bo+d*bg),1e-8); guess.rs_sm3_sm3[activate]=rsat
            if np.any(deactivate): guess.sg[deactivate]=0.0; guess.rs_sm3_sm3[deactivate]=self.pvt.rs_sat(guess.pressure_bar[deactivate])
            mask=newmask
        r=self.residual(self.pack(guess,mask),state_old,dt_s,mask); return guess,BlackOilNewtonReport(False,total_newton,float(np.linalg.norm(r,np.inf)),max_active_iter,total_switches)
    def well_rates(self,state):
        f=self.face_component_fluxes_sm3s(state); qo=f['oil_well']; qgf=f['free_gas_well']; qgt=f['gas_component_well']
        return {'oil_sm3_s':qo,'free_gas_sm3_s':qgf,'dissolved_gas_sm3_s':qgt-qgf,'total_gas_sm3_s':qgt,
                'gor_sm3_sm3':qgt/qo if qo>0 else np.nan,'bhp_bar':float(self._last_effective_bhp_bar),
                'control_mode':self.control_mode,'constraint_active':bool(self._last_constraint_active)}
    def step_global_balance(self,state_old,state_new,dt_s):
        oi0,gi0=self.component_inventories(state_old); oi1,gi1=self.component_inventories(state_new); f=self.face_component_fluxes_sm3s(state_new)
        return float(np.sum(oi1-oi0)+dt_s*(f['oil_well']+f['oil_outer'])),float(np.sum(gi1-gi0)+dt_s*(f['gas_component_well']+f['gas_component_outer']))
