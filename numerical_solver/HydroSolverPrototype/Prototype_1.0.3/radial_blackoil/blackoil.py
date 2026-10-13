"""Prototype 1 two-component radial black-oil model.

Physics and Newton/active-set logic are unchanged from the validated Prototype 1
formulation. Version 1.0.3 keeps the grouped finite-difference Jacobian and
supports sparse or dense linear algebra as a numerical backend choice.
Local changes (GPN project, BUG-014): when the original step fails, advance()
retries with the BHP well branch as an outer active constraint and no lower
bound on Sg of two-phase cells.
BUG-018: the closed-flash Sg guess of a cell switching to two-phase is capped
at the largest relperm-table Sg where kro > 0 (sg_activation_cap).
DEBT-033: the grouped Jacobian is assembled vectorized, directly as a CSC matrix
(bitwise the former dense one); _linear_solve takes sparse or dense J.
DEBT-036: component_inventories uses Bo, Bg only; the old-state inventories are
computed once per step (_old_inventories); faces take Bo, mu_o from pvt.bo_mu_o
where the PVT has it.
DEBT-030: when all three stages of advance() fail, the report carries the Newton
fields of the original algorithm, not those of the last fallback attempt.
BUG-021: _newton_fixed_active_set tests convergence on every new iterate, the
last one included, on the residual its line search has evaluated; no Jacobian
is built only to detect convergence.
BUG-020: a fourth stage of advance() (phase_switching_stage, off by default): the
BUG-014 fallback with _newton_switching -- phase switches after every Newton
iteration, per-cell update limits, no line search, upstream cells held on faces
whose flow direction flips.
DEBT-040: under BHP control the fallback does not try the 'open' well branch
where it cannot be consistent (outer and all old cell pressures <= p_wf).
BUG-022: a per-cell convergence test (constructor argument cell_tol, off by
default): a Newton solve also needs max_c |F_c,i|*dt/PV_i <= cell_tol in every
cell i (PV_i: pore volume of state_old), besides the absolute test.
BUG-024: the fourth stage limits the Rs update of undersaturated cells,
|dRs| <= dr_rel*Rs_sat(p) (dr_rel = 0.2, as ds_max for Sg).
DEBT-048: the fourth stage is callable alone (advance_fourth_stage); the GPN adapter
calls it on shut-in steps that follow two steps the fourth stage solved.
DEBT-054: the Newton report says why a solve stopped (exit_reason), with the absolute
tolerance of its test (residual_tol) and the per-cell measure (cell_measure) on the
residual it reports; a failed fourth-stage Newton reports the iterations it ran,
not max_iter (DEBT-061).
BUG-025: the absolute Newton tolerance is not below the round-off floor of the storage
term, max(atol, ROUNDOFF_KAPPA*eps*M_max/dt) (_absolute_tol): a shut-in step shorter than
~0.05 s after production with a developed gas zone failed every stage of advance.
"""
from dataclasses import dataclass, replace
import numpy as np
from scipy.linalg import solve as dense_solve
from scipy.sparse import coo_matrix, csc_matrix, issparse
from scipy.sparse.linalg import splu
from .state import BlackOilState
from .units import BAR_TO_PA, CP_TO_PA_S

# BUG-025: machine epsilon and the factor of the round-off floor of the absolute Newton
# tolerance (_absolute_tol)
_EPS=float(np.finfo(float).eps)
ROUNDOFF_KAPPA=4.0

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
    phase_switching: bool = False  # advance's fourth stage ran (phase switches inside Newton), BUG-020
    # DEBT-054: why the Newton stopped and how far it was from each convergence test, on
    # the residual of residual_inf.  residual_tol -- max(atol, round-off floor) + rtol*scale of
    # the absolute test (BUG-025)
    # (None: exit 'active_set', the residual of a guess no Newton solved); cell_measure --
    # max_c |F_c,i|*dt/PV_i of the per-cell test, BUG-022 (None: the test is off);
    # exit_reason -- 'converged', 'line_search', 'linear_solver', 'max_iter', 'nonfinite',
    # 'active_set', 'sg_bound' (fourth stage: a root with two-phase Sg > 0.98), 'branch'
    # (_fallback: the Newton converged on an inconsistent BHP branch); '' -- not set.
    residual_tol: float | None = None
    cell_measure: float | None = None
    exit_reason: str = ''

def _sg_activation_cap(relperm):
    """BUG-018: cap of the closed-flash Sg guess -- last relperm-table Sg node with kro > 0, else None."""
    sg=np.asarray(getattr(relperm,'sg',()),float); kro=np.asarray(getattr(relperm,'kro_tab',()),float)
    zero=np.flatnonzero(kro<=0.0)
    if sg.size==0 or zero.size==0 or zero[0]==0: return None
    return float(sg[zero[0]-1])

class RadialBlackOilModel:
    def __init__(self, grid, rock, pvt, relperm, p_bhp_bar, p_outer_bar,
                 outer_rs_sm3_sm3, skin=0.0, rs_switch_tol=1e-5,
                 sg_switch_tol=1e-9, gas_residual_scale=None,
                 jacobian_mode='grouped', linear_solver='sparse',
                 phase_switching_stage=False, cell_tol=None):
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
        # BUG-018: a cell switching to two-phase starts Newton from the closed-
        # flash Sg (all released gas stays in the cell, no flow during the step).
        # With high Rs0 and a deep drawdown it exceeds 1 - S_or near the well
        # (0.91 at Rs0 = 500, p_wf = 5 MPa against 0.41 in the solution), and
        # Newton started there does not reach the solution: a guess capped at
        # 0.79 converges, at 0.81 fails (S_or = 0.2).  The cap moves only the
        # starting point; the equations and the converged state are unchanged
        # (plan BUG-018, 2.2).  None: the table gives no cap (_sg_activation_cap).
        self.sg_activation_cap=_sg_activation_cap(relperm)
        if jacobian_mode not in ('grouped','reference'): raise ValueError("jacobian_mode must be 'grouped' or 'reference'")
        if linear_solver not in ('sparse','dense'): raise ValueError("linear_solver must be 'sparse' or 'dense'")
        self.jacobian_mode=jacobian_mode; self.linear_solver=linear_solver
        # DEBT-036: (key, oil, gas) inventories of the last state_old of physical_residual (_old_inventories)
        self._old_inventories_cache=None
        # BUG-020: fourth stage of advance (_newton_switching), off by default so that the
        # prototype's own runs and its regression golden stay bitwise; the GPN factory turns
        # it on.  _phase_switching routes _advance_phases to the fourth-stage Newton;
        # _upwind_frozen/_upwind_left hold the upstream cell of internal faces during it
        # (None outside it, face_component_fluxes_sm3s then picks it by the pressure drop).
        self.phase_switching_stage=bool(phase_switching_stage); self._phase_switching=False
        self._upwind_frozen=None; self._upwind_left=None
        # BUG-022: per-cell convergence test, off by default so that the prototype's own
        # runs and its regression golden stay bitwise; the GPN factory turns it on.  The
        # absolute test ||F||_inf <= atol + rtol*||F0||_inf (m3st/s) is one for all cells;
        # on the log grid the well cell has ~(r_w/r_e)^2 of the outer cell's pore volume,
        # and the same residual there is a ~1e6 times larger relative error (GPN example
        # 17: Rs of the shut-in well cell wandered by +-0.015 a day, where it can only grow).
        # With cell_tol a solve also needs max_c |F_c,i|*dt/PV_i <= cell_tol in every cell i
        # (the gas rows divided by gas_residual_scale, as in residual).  For an undersaturated
        # cell upstream of no face (the shut-in well cell) its Rs enters the storage only, and
        # the Rs error of a step is estimated by cell_tol*Bo*(gas_residual_scale + Rs).  Far
        # below ~eps_mach*PV_max/PV_min the test is not met and steps are split (GPN example
        # 17 at cell_tol = 1e-10: 214 rejected steps against 47; the mechanism is not
        # established -- both the line search and the stage-4 Newton stall).
        if cell_tol is not None and not 0.0<float(cell_tol)<np.inf:
            raise ValueError('cell_tol must be a positive finite number or None')
        self.cell_tol=None if cell_tol is None else float(cell_tol)

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
        # DEBT-036: Bo and Bg only; oil_properties/gas_properties would evaluate mu_o, mu_g as well
        bo=self.pvt.bo(p,state.rs_sm3_sm3); bg=self.pvt.bg(p)
        pv=self.rock.pore_volume_m3(self.grid.bulk_volumes_m3,p)
        return pv*so/bo, pv*(state.rs_sm3_sm3*so/bo+sg/bg)
    def _old_inventories(self,state_old):
        """Inventories of state_old, recomputed only when its p, Rs or Sg change (DEBT-036)."""
        # Within a step every residual (7 per Jacobian plus the line search) has the same state_old.
        # The key is the bytes of p, Rs, Sg, not the object: a state changed in place gets fresh
        # inventories, equal bytes give bitwise the same ones (key 1.8 us at N = 350 against
        # 0.1-0.6 ms for the inventories).  grid, rock and pvt are fixed for the model's life.
        # The returned arrays are the cached ones: callers must not modify them in place.
        key=(state_old.pressure_bar.tobytes(),state_old.rs_sm3_sm3.tobytes(),state_old.sg.tobytes())
        c=self._old_inventories_cache
        if c is None or c[0]!=key:
            c=self._old_inventories_cache=(key,)+tuple(self.component_inventories(state_old))
        return c[1],c[2]
    def _phase_mobilities_surface(self,p,rs,sg):
        p=np.asarray(p,float); rs=np.asarray(rs,float); sg=np.asarray(sg,float)
        # DEBT-036: Bo and mu_o from one PVTO pass where the PVT has it (BlackOilPVT); the
        # Standing adapter (HydroPVTtoBlackOilAdapter) has bo and mu_o only
        bo_mu_o=getattr(self.pvt,'bo_mu_o',None)
        bo,muo=bo_mu_o(p,rs) if bo_mu_o is not None else (self.pvt.bo(p,rs),self.pvt.mu_o(p,rs))
        bg=self.pvt.bg(p); mug=self.pvt.mu_g(p)
        return self.relperm.kro(sg)/(muo*CP_TO_PA_S)/bo, self.relperm.krg(sg)/(mug*CP_TO_PA_S)/bg
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
    def net_component_outflow(self,state):
        f=self.face_component_fluxes_sm3s(state); oil=np.zeros(self.grid.n); gas=np.zeros(self.grid.n)
        oil[0]+=f['oil_well']; gas[0]+=f['gas_component_well']
        if self.grid.n>1:
            oil[:-1]+=f['oil_internal']; oil[1:]-=f['oil_internal']; gas[:-1]+=f['gas_component_internal']; gas[1:]-=f['gas_component_internal']
        oil[-1]+=f['oil_outer']; gas[-1]+=f['gas_component_outer']; return oil,gas
    def physical_residual(self,z,state_old,dt_s,gas_active):
        new=self.unpack(z,gas_active); oi1,gi1=self.component_inventories(new); oi0,gi0=self._old_inventories(state_old); qo,qg=self.net_component_outflow(new)
        return np.concatenate([(oi1-oi0)/float(dt_s)+qo,(gi1-gi0)/float(dt_s)+qg])
    def residual(self,z,state_old,dt_s,gas_active):
        r=self.physical_residual(z,state_old,dt_s,gas_active); r[self.grid.n:]/=self.gas_residual_scale; return r
    def _cell_weights(self,state_old,dt_s):
        """BUG-022: dt/PV_i of the per-cell convergence test (pore volume of state_old); None when the test is off."""
        if self.cell_tol is None: return None
        return float(dt_s)/self.rock.pore_volume_m3(self.grid.bulk_volumes_m3,state_old.pressure_bar)
    def _cell_measure(self,f,w):
        """BUG-022, DEBT-054: max_c |f_c,i|*dt/PV_i over the oil and gas rows of f = residual(); None when the test is off."""
        if w is None: return None
        n=self.grid.n
        return max(float(np.max(np.abs(f[:n])*w)),float(np.max(np.abs(f[n:])*w)))
    def _cells_converged(self,f,w):
        """BUG-022: max_c |f_c,i|*dt/PV_i <= cell_tol over the oil and gas rows of f = residual(); True when the test is off."""
        # the same operations as before DEBT-054, so the test is bitwise unchanged
        m=self._cell_measure(f,w)
        return m is None or m<=self.cell_tol
    def _newton_report(self,converged,iterations,nrm,tol,f,w,reason,**fields):
        """DEBT-054: report of a Newton solve -- ||F||_inf, its absolute tolerance, the per-cell measure of the same f, the exit reason."""
        return BlackOilNewtonReport(converged,iterations,float(nrm),
                                    residual_tol=None if tol is None else float(tol),
                                    cell_measure=self._cell_measure(f,w),exit_reason=reason,**fields)
    def _absolute_tol(self,state_old,dt_s,atol_sm3s):
        """BUG-025: atol of the absolute Newton test, not below the round-off floor ROUNDOFF_KAPPA*eps*M_max/dt of the storage term."""
        # The storage term of the residual is (M_new - M_old)/dt in m3st/s, each inventory
        # carries a round-off error ~eps*M, and the residual does not go below ~eps*M_max/dt
        # (the largest cell of state_old; oil rows, gas rows / gas_residual_scale as in
        # residual).  At short steps this is above atol = 1e-11, the bound grows with the
        # largest cell: GPN bug020_rs150 (N = 350, r_e = 200 m, M_max = 7.2e3 m3st), shut-in
        # after 10 days of production -- the line search stalled at |F|*dt = 5-7e-13 m3st for
        # dt = 1e-2...1e-4 s and no stage of advance converged at any split; GPN example 15
        # (N = 50, M_max = 5.5e4) -- a production substep of 0.44 s failed the same way.
        # The measured stall is (0.07-0.7)*eps*M_max (R_ext = 800...50 m): cells
        # whose state did not change carry no round-off, so eps*M_max is an upper estimate.
        # ROUNDOFF_KAPPA = 4 keeps a margin of 6 over it.  Where the floor is below atol, max
        # returns atol itself and the solve is bitwise the former one: so in every GPN example
        # and every regression case (smallest atol*dt/(eps*M_max): 34, T05S_N200_DT5m; 63,
        # GPN example 18).  A solve accepted at the floor errs by at most ROUNDOFF_KAPPA*eps*M_max m3st.
        oi0,gi0=self._old_inventories(state_old)
        m=max(float(np.max(np.abs(oi0))),float(np.max(np.abs(gi0)))/self.gas_residual_scale)
        return max(atol_sm3s,ROUNDOFF_KAPPA*_EPS*m/float(dt_s))
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
    def _fd_steps(self,z,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
        """DEBT-033: finite-difference steps of all 2n unknowns at once (pressure block, then Rs/Sg)."""
        # Elementwise the same float64 arithmetic as _pressure_fd_step and the Rs/Sg
        # step rule of the column loop, hence bitwise the same steps.
        z=np.asarray(z,float); mask=np.asarray(gas_active,dtype=bool); n=self.grid.n
        p,x=z[:n],z[n:]
        h=np.maximum(p_abs_step,p_rel_step*np.maximum(np.abs(p),1.0))
        knots=np.asarray(self.pvt.pb,float)
        if knots.size:
            # Gas-active cells: step down where the step up would straddle the next
            # Rs_sat(p) knot (see _pressure_fd_step); its second rule returns +h,
            # the default, and needs no counterpart here.
            idx=np.searchsorted(knots,p,side='left')
            lower=np.where(idx>0,knots[np.maximum(idx-1,0)],-np.inf)
            upper=np.where(idx<knots.size,knots[np.minimum(idx,knots.size-1)],np.inf)
            down=mask&(upper-p<=1.25*h)&(p-lower>h)
            h=np.where(down,-h,h)
        hx=np.where(mask,sg_abs_step,np.maximum(rs_abs_step,1e-6*np.maximum(np.abs(x),1.0)))
        return np.concatenate([h,hx])

    def finite_difference_jacobian_reference(self,z,state_old,dt_s,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
        z=np.asarray(z,float); f0=self.residual(z,state_old,dt_s,gas_active); J=np.empty((z.size,z.size)); n=self.grid.n
        for j in range(z.size):
            h=self._pressure_fd_step(z[j],bool(gas_active[j]),p_rel_step,p_abs_step) if j<n else (sg_abs_step if gas_active[j-n] else max(rs_abs_step,1e-6*max(abs(z[j]),1.0)))
            zp=z.copy(); zp[j]+=h; J[:,j]=(self.residual(zp,state_old,dt_s,gas_active)-f0)/h
        return J,f0
    def finite_difference_jacobian_grouped(self,z,state_old,dt_s,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
        """Coloured finite-difference Jacobian as a CSC matrix, bitwise csc_matrix() of the reference one (DEBT-033)."""
        # The residual of cell i depends on cells i-1, i, i+1 only, so cells i, i+3,
        # i+6, ... are perturbed together: 2 blocks x 3 colours = 6 residual
        # evaluations.  Steps, residual evaluations and their order, and the entries
        # df/h are those of the former per-cell loop (DEBT-033 probe: bitwise equal
        # to the reference on 488 Newton states of five GPN examples).
        z=np.asarray(z,float); f0=self.residual(z,state_old,dt_s,gas_active); n=self.grid.n
        h=self._fd_steps(z,gas_active,p_rel_step,p_abs_step,rs_abs_step,sg_abs_step)
        rows=[]; cols=[]; vals=[]
        for block in (0,1):
            for color in range(3):
                cells=np.arange(color,n,3); j=cells+block*n; hj=h[j]
                zp=z.copy(); zp[j]+=hj
                df=self.residual(zp,state_old,dt_s,gas_active)-f0
                for d in (-1,0,1):
                    # oil (row r) and gas (row n+r) residuals of the neighbour r=i+d
                    ok=(cells+d>=0)&(cells+d<n); r=cells[ok]+d; c=j[ok]; hc=hj[ok]
                    rows+=[r,n+r]; cols+=[c,c]; vals+=[df[r]/hc,df[n+r]/hc]
        J=coo_matrix((np.concatenate(vals),(np.concatenate(rows),np.concatenate(cols))),shape=(2*n,2*n)).tocsc()
        # csc_matrix(dense) of the former loop dropped exact zeros (downstream
        # entries, dkrg/dSg = 0 below Sgc).  Explicit zeros would change the sparsity
        # pattern, SuperLU's column ordering and the Newton step at round-off level.
        J.eliminate_zeros()
        return J,f0
    def finite_difference_jacobian(self,*args,**kwargs):
        # DEBT-033: grouped returns a CSC matrix, reference a dense array; _linear_solve takes both
        return self.finite_difference_jacobian_reference(*args,**kwargs) if self.jacobian_mode=='reference' else self.finite_difference_jacobian_grouped(*args,**kwargs)
    def _linear_solve(self,J,b):
        if self.linear_solver=='sparse': return splu(J if issparse(J) else csc_matrix(J)).solve(b)
        return dense_solve(J.toarray() if issparse(J) else J,b,assume_a='gen',check_finite=True)
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
        z=np.asarray(z0,float).copy(); f=self.residual(z,state_old,dt_s,gas_active); nrm=np.linalg.norm(f,np.inf)
        # BUG-025: atol not below the round-off floor of the storage term (_absolute_tol)
        scale=max(nrm,1e-9); tol=self._absolute_tol(state_old,dt_s,atol_sm3s)+rtol*scale
        # BUG-022: dt/PV_i of the per-cell test (None when it is off); a solve converges only
        # when every cell meets it too, else it fails and advance tries its next stage
        w=self._cell_weights(state_old,dt_s)
        # BUG-016: norm of the line search; the convergence test stays on ||F||_inf.
        # With defaults the comparison is norm(ft,inf)<nrm, bitwise as before.
        merit=(lambda v: np.linalg.norm(v)) if self._line_search_l2 else (lambda v: np.linalg.norm(v,np.inf))
        # BUG-021: convergence is tested on every new iterate, the last one included.
        # It used to be tested at the top of the next iteration only, so a solve that
        # converged on update max_iter was reported as failed.  f is residual(z),
        # bitwise the f0 that the Jacobian call returns at the same z: wherever the
        # solve converged before, iterates and reports are unchanged, and the
        # Jacobian that was built only to detect convergence is no longer built.
        # DEBT-054: every report carries the absolute tolerance, the per-cell measure of f
        # (the residual of the z it returns: the Jacobian call returns residual(z) at the same
        # z, see BUG-021 above; a rejected trial leaves f untouched) and why the solve stopped.
        # A failure at iteration it reports it (the failed iteration counted), as before.
        if nrm<=tol and self._cells_converged(f,w): return z,self._newton_report(True,0,nrm,tol,f,w,'converged')
        for it in range(1,max_iter+1):
            J,f=self.finite_difference_jacobian(z,state_old,dt_s,gas_active)
            try: dz=self._linear_solve(J,-f)
            except Exception: return z,self._newton_report(False,it,nrm,tol,f,w,'linear_solver')
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
                    if merit(ft)<mf: z=trial; f=ft; accepted=True; break
                alpha*=0.5
            if not accepted: return z,self._newton_report(False,it,nrm,tol,f,w,'line_search')
            nrm=np.linalg.norm(f,np.inf)
            if nrm<=tol and self._cells_converged(f,w): return z,self._newton_report(True,it,nrm,tol,f,w,'converged')
        return z,self._newton_report(False,max_iter,nrm,tol,f,w,'max_iter')
    def advance(self,state_old,dt_s,max_active_iter=12,max_newton=15):
        """One implicit step: the original algorithm; on failure a fallback with the
        BHP well branch as an outer constraint and no lower bound on Sg (BUG-014);
        if that fails too, the fallback again with a globalized Newton (BUG-016);
        if that fails too and phase_switching_stage is on, the fallback with phase
        switches inside Newton (BUG-020) -- advance_fourth_stage.
        If all stages fail, the report carries the original algorithm's Newton (DEBT-030),
        with its tolerance, per-cell measure and exit reason (DEBT-054)."""
        new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
        if rep.converged:
            if self.control_mode=='BHP':
                # branch the automatic rule takes on the accepted state
                p0=float(new.pressure_bar[0])
                rep.well_branch='shut' if p0<=float(self.p_bhp_bar) else 'open'
            return new,rep
        orig=rep  # DEBT-030: reported if the fallback and the third stage fail too
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
            rep.globalized=True
        finally:
            self._line_search_l2=False; self._sg_step_max=None
        if rep.converged: return new,rep
        if self.phase_switching_stage:
            # Fourth stage (BUG-020), only where the first three fail, so every step they
            # solve stays bitwise: the BUG-014 fallback (well branches, consistency check)
            # with _advance_phases routed to _newton_switching.  Shut-in after production
            # with a developed gas zone (examples 19-21: Sg near the well 0.4) failed all
            # three; see _newton_switching for the mechanism.
            new,rep=self.advance_fourth_stage(state_old,dt_s,max_active_iter,max_newton)
            if rep.converged: return new,rep
        if not rep.converged:
            # DEBT-030: the last attempt is often the BHP 'shut' branch, which
            # "converges" in 0 iterations with ||F|| = 0 on an unchanged state and
            # is dropped as inconsistent; its report made every rejected step in
            # step_log.csv read "0 iterations, residual 0".  Report the original
            # algorithm's Newton instead (as before BUG-014); the branch fields
            # (well_branch, well_switches, fallback, globalized) stay the last
            # attempt's.  Accepted steps are untouched (_grow_dt reads them).
            # DEBT-054: the absolute tolerance, the per-cell measure and the exit reason are
            # Newton fields too -- the original algorithm's, consistent with its residual.
            rep=replace(rep,iterations=orig.iterations,residual_inf=orig.residual_inf,
                        active_set_iterations=orig.active_set_iterations,
                        phase_switches=orig.phase_switches,
                        residual_tol=orig.residual_tol,cell_measure=orig.cell_measure,
                        exit_reason=orig.exit_reason)
        return new,rep
    def advance_fourth_stage(self,state_old,dt_s,max_active_iter=12,max_newton=15):
        """The fourth stage of advance alone (BUG-020, DEBT-048): the BUG-014 fallback with
        phase switches inside Newton; its own report, also when it fails."""
        # DEBT-048: the GPN adapter calls it directly on shut-in steps that follow two steps
        # the fourth stage solved, skipping the first three stages, which fail there.  A step
        # solved here is bitwise the step advance solves after the first three stages fail:
        # every attribute set here and in _fallback is restored in finally, and between
        # solves the model keeps only the old-state inventories cache, a function of
        # state_old.  Independent of phase_switching_stage: the flag only adds this stage
        # to advance.
        self._phase_switching=True
        try:
            new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton)
            rep.globalized=True; rep.phase_switching=True
        finally:
            self._phase_switching=False
        return new,rep
    def _fallback(self,state_old,dt_s,max_active_iter,max_newton):
        """BUG-014 fallback: no lower bound on Sg; BHP control fixes the well branch
        (start from the old state's branch, accept a consistent result only, try the
        other branch once, 'open' only where it can be consistent, DEBT-040);
        OIL_RATE control: a plain retry without the Sg bound."""
        self._sg_lower_bound=None
        try:
            if self.control_mode!='BHP':
                new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
                rep.fallback=True; return new,rep
            target=float(self.p_bhp_bar)
            # Start from the branch of the old state; shut-in steps start on 'shut'.
            branch='shut' if float(state_old.pressure_bar[0])<=target else 'open'
            # DEBT-040: 'open' is accepted only with p0 >= target (production, q >= 0).
            # With the outer pressure and every old cell pressure <= target, a producing
            # well and the outer boundary raise no cell above target (maximum principle
            # of the pressure equation), so p0 <= target and 'open' cannot be consistent.
            # Not proved for black oil with phase switches (c_t < 0 at Newton overshoots);
            # measured: shut-in with BHP raised to the outer pressure after production
            # (GPN example 20, 3 days) tried 'open' 1488 times, accepted it 0 times, and
            # it took 38 % of the shut-in time.  A wrong guess here could only reject a
            # step, never accept an inconsistent one.
            open_hopeless=self.p_outer_bar<=target and float(np.max(state_old.pressure_bar))<=target
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
                if other in tried or (other=='open' and open_hopeless):
                    # DEBT-054: a Newton that converged on an inconsistent branch failed by the
                    # branch, not by the Newton; a failed Newton keeps its own exit reason
                    if rep.converged: rep.exit_reason='branch'
                    rep.converged=False; return new,rep
                branch=other
        finally:
            self._sg_lower_bound=-0.05; self._well_branch=None
    def _advance_phases(self,state_old,dt_s,max_active_iter=12,max_newton=15):
        """Phase active-set loop (unchanged Prototype 1 logic)."""
        # BUG-020: inside the fourth stage of advance the BUG-014 fallback (well branches)
        # runs the Newton with phase switches inside it instead of this loop
        if self._phase_switching: return self._newton_switching(state_old,dt_s)
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
                sg0=np.maximum(d*bg/(bo+d*bg),1e-8)
                # BUG-018: keep the guess where oil is still mobile; np.minimum
                # returns sg0 bitwise wherever it is below the cap
                if self.sg_activation_cap is not None: sg0=np.minimum(sg0,self.sg_activation_cap)
                guess.sg[activate]=sg0; guess.rs_sm3_sm3[activate]=rsat
            if np.any(deactivate): guess.sg[deactivate]=0.0; guess.rs_sm3_sm3[deactivate]=self.pvt.rs_sat(guess.pressure_bar[deactivate])
            mask=newmask
        # DEBT-054: the phase loop ran out; r is the residual of the guess with the new phase set,
        # which no Newton solved -- no absolute tolerance, the per-cell measure of r
        r=self.residual(self.pack(guess,mask),state_old,dt_s,mask)
        return guess,BlackOilNewtonReport(False,total_newton,float(np.linalg.norm(r,np.inf)),max_active_iter,total_switches,
                                          cell_measure=self._cell_measure(r,self._cell_weights(state_old,dt_s)),
                                          exit_reason='active_set')
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
    def _newton_switching(self,state_old,dt_s,max_iter=40,rtol=1e-8,atol_sm3s=1e-11,dp_rel=0.3,ds_max=0.2,flips_to_freeze=2,dr_rel=0.2):
        """BUG-020 fourth stage: Newton with phase switches after every iteration, per-cell update limits (p, Sg; Rs -- BUG-024), no line search."""
        # Shut-in after production with a developed gas zone.  The well cell is upstream of no
        # face once the well is shut, and its gas storage per unit Sg, 1/Bg - Rs/Bo, is small at
        # low pressure (7.4 at 51 bar against 38.9 at 200 bar, example 20): the first Newton
        # direction asks |dSg| ~ 0.7*dt[s].  The bound -0.05 rejects every trial, no bound sends
        # Sg to -23...-1137 (c_t < 0 there), the third stage scales the whole update by
        # 0.2/|dSg| and the pressure crawls.  Here a cell leaves the two-phase set as soon as
        # an iterate takes its Sg below 0, and the limits act per cell (dpMaxRel, dsMax of OPM
        # Flow; the Rs of undersaturated cells since BUG-024, see the update below).  No line
        # search: after the per-cell limit the update is not a descent direction of ||F||, and
        # the search stopped at the first iteration (plan BUG-020, 1.4).
        # Later steps: in the stagnant undersaturated zone near the shut well the pressure is
        # level to 1e-3 bar, the upstream cell of 1-11 faces flips every iteration and the
        # Newton converges linearly (26 iterations against 15); faces that flipped twice keep
        # their upstream cell until convergence, then a polish without holding returns the
        # original upwind scheme.
        state_old=state_old.copy(); n=self.grid.n; nf=max(n-1,0)
        mask=state_old.gas_active.copy(); z=self.pack(state_old,mask)
        # BUG-025: atol not below the round-off floor of the storage term (_absolute_tol)
        scale=max(np.linalg.norm(self.residual(z,state_old,dt_s,mask),np.inf),1e-9); tol=self._absolute_tol(state_old,dt_s,atol_sm3s)+rtol*scale
        # BUG-022: dt/PV_i of the per-cell test, None when it is off
        w=self._cell_weights(state_old,dt_s)
        switched=total=0; flips=np.zeros(nf,int); prev=None; polish=False
        # DEBT-054, DEBT-061: why the loop stopped; a pass with it > max_iter breaks on the limit
        reason='max_iter'
        self._upwind_frozen=np.zeros(nf,bool); self._upwind_left=np.zeros(nf,bool)
        try:
            # one pass more than max_iter: the residual after the last update is checked too
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
                        # BUG-022: and the per-cell test; not met -- iterate on (up to max_iter)
                        if self._cells_converged(f,w):
                            new=self.unpack(z,mask); new.sg[mask&(new.sg<0)]=0.0
                            # same bound as _trial_is_reasonable: no root with Sg > 0.98
                            ok=not np.any(new.sg[mask]>0.98)
                            return new,self._newton_report(ok,it-1,nrm,tol,f,w,'converged' if ok else 'sg_bound',
                                                           active_set_iterations=1,phase_switches=total)
                    else:
                        # converged with a held upstream cell the solution contradicts: polish
                        # without holding, so the result solves the original upwind scheme
                        self._upwind_frozen=None; polish=True; continue
                if it>max_iter: break
                try: dz=self._linear_solve(J,-f)
                except Exception: reason='linear_solver'; break
                # per-cell limits; Rs of undersaturated cells >= 0, pressure >= 1 bar
                x=z[n:]; lim=dp_rel*np.maximum(p,1.0)
                pn=np.maximum(p+np.clip(dz[:n],-lim,lim),1.0+1e-6)
                # BUG-024: |dRs| of undersaturated cells <= dr_rel*Rs_sat(p) -- the analogue of
                # ds_max: a share of the admissible range 0 <= Rs <= Rs_sat(p).  Unlimited, the
                # first shut-in hours after production with a developed gas zone (GPN config 20,
                # q_oil = 0) gave |dRs| up to 1.7e4 per iteration; the cut at Rs = 0 then either
                # stalled the Newton (a cell near the well held at Rs = 0, ||F|| constant for 30
                # iterations) or sent it into chaos (p up to 433 bar, mass phase switches), and
                # whether a daily step passed at dt/512 depended on round-off of earlier steps.
                # dr_rel 0.1-0.5 passes, 1.0 fails (plan BUG-024, 1.3-1.5).  Steps below the
                # limit are bitwise the former ones (np.clip returns them unchanged).
                lim_rs=dr_rel*np.maximum(self.pvt.rs_sat(p),1.0)
                xn=np.where(mask,x+np.clip(dz[n:],-ds_max,ds_max),np.maximum(x+np.clip(dz[n:],-lim_rs,lim_rs),0.0))
                if not (np.all(np.isfinite(pn)) and np.all(np.isfinite(xn))): reason='nonfinite'; break
                xn,mask,switched=self._switch_phases(pn,xn,mask); total+=switched
                z=np.concatenate([pn,xn])
            # DEBT-061: the passes it ran minus one, as the converged report above -- not max_iter,
            # which a break after a linear-solver failure or a non-finite update reported too.
            # f is evaluated here, before finally drops the held upstream cells: residual_inf and
            # the per-cell measure are of the scheme the Newton was solving (DEBT-054)
            f=self.residual(z,state_old,dt_s,mask)
            return self.unpack(z,mask),self._newton_report(False,it-1,np.linalg.norm(f,np.inf),tol,f,w,reason,
                                                           active_set_iterations=1,phase_switches=total)
        finally:
            self._upwind_frozen=None; self._upwind_left=None
    def well_rates(self,state):
        f=self.face_component_fluxes_sm3s(state); qo=f['oil_well']; qgf=f['free_gas_well']; qgt=f['gas_component_well']
        return {'oil_sm3_s':qo,'free_gas_sm3_s':qgf,'dissolved_gas_sm3_s':qgt-qgf,'total_gas_sm3_s':qgt,
                'gor_sm3_sm3':qgt/qo if qo>0 else np.nan,'bhp_bar':float(self._last_effective_bhp_bar),
                'control_mode':self.control_mode,'constraint_active':bool(self._last_constraint_active)}
    def step_global_balance(self,state_old,state_new,dt_s):
        oi0,gi0=self.component_inventories(state_old); oi1,gi1=self.component_inventories(state_new); f=self.face_component_fluxes_sm3s(state_new)
        return float(np.sum(oi1-oi0)+dt_s*(f['oil_well']+f['oil_outer'])),float(np.sum(gi1-gi0)+dt_s*(f['gas_component_well']+f['gas_component_outer']))
