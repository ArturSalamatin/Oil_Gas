from dataclasses import dataclass
import numpy as np
from .units import DAY_TO_S
from .diagnostics import state_sanity, pvt_range_warnings, unique_warnings

@dataclass
class RunHistory:
    report_states: list
    report_rates: list
    step_log: list
    accepted_steps: int
    rejected_steps: int
    material_balance: list
    warnings: list
    sanity_issues: list

class SimulationFailure(RuntimeError):
    def __init__(self,message,history,time_s,last_dt_s=None,last_report=None):
        super().__init__(message); self.history=history; self.time_s=float(time_s)
        self.last_dt_s=None if last_dt_s is None else float(last_dt_s); self.last_report=last_report


def _grow_dt(dt, report):
    if report.iterations >= 10: return dt*0.75
    if report.iterations >= 6: return dt*1.15
    return dt*1.5

def _apply_control(model,row):
    if row.mode=='BHP': model.set_bhp_control(row.bhp_bar)
    elif row.mode=='OIL_RATE': model.set_oil_rate_control(row.oil_rate_sm3_day,row.min_bhp_bar)
    else: raise ValueError(f'unsupported control mode {row.mode!r}')

def _inventory_breakdown(model,state):
    p=np.asarray(state.pressure_bar,float); sg=np.asarray(state.sg,float); so=1.0-sg
    bo,_=model.oil_properties(state); bg,_=model.gas_properties(state)
    pv=model.rock.pore_volume_m3(model.grid.bulk_volumes_m3,p)
    oil=float(np.sum(pv*so/bo))
    gd=float(np.sum(pv*state.rs_sm3_sm3*so/bo))
    gf=float(np.sum(pv*sg/bg))
    return oil,gd,gf

def simulate_schedule(model,state0,schedule,dt_initial_s,dt_min_s,dt_max_s):
    """Integrate with exact SCHEDULE boundaries; every row is a report time."""
    state=state0.copy(); t=0.0; dt=float(dt_initial_s); dtmin=float(dt_min_s); dtmax=float(dt_max_s)
    report_states=[(0.0,state.copy())]; report_rates=[]; step_log=[]; acc=rej=0
    warnings=[]; sanity=[]
    diagnostics_supported=hasattr(state,'pressure_bar') and hasattr(model,'pvt') and hasattr(model,'relperm')
    balance_supported=diagnostics_supported and hasattr(model,'oil_properties') and hasattr(model,'gas_properties')
    if balance_supported: oi0,gdi0,gfi0=_inventory_breakdown(model,state); gi0=gdi0+gfi0
    else: oi0=gdi0=gfi0=gi0=0.0
    cum_ow=cum_gw=cum_oo=cum_go=0.0
    material=[]
    def add_diagnostics(td,s):
        nonlocal warnings,sanity
        if diagnostics_supported:
            sanity.extend([f't={td:g} d: {x}' for x in state_sanity(s)])
            warnings.extend(pvt_range_warnings(model,s))
    def add_material(td,s):
        if not balance_supported: return
        oi,gdi,gfi=_inventory_breakdown(model,s); gi=gdi+gfi
        ob=oi-oi0+cum_ow+cum_oo; gb=gi-gi0+cum_gw+cum_go
        material.append({
            'time_day':td,'oil_initial_sm3':oi0,'oil_current_sm3':oi,
            'oil_produced_well_sm3':cum_ow,'oil_outer_net_out_sm3':cum_oo,
            'oil_balance_error_sm3':ob,'oil_balance_error_pct_initial':100.0*ob/max(abs(oi0),1e-30),
            'gas_initial_sm3':gi0,'gas_current_total_sm3':gi,'gas_current_dissolved_sm3':gdi,'gas_current_free_sm3':gfi,
            'gas_produced_well_sm3':cum_gw,'gas_outer_net_out_sm3':cum_go,
            'gas_balance_error_sm3':gb,'gas_balance_error_pct_initial':100.0*gb/max(abs(gi0),1e-30),
        })
    row0=schedule.rows[0]; _apply_control(model,row0)
    r0=model.well_rates(state); report_rates.append((0.0,r0,r0['bhp_bar'])); add_diagnostics(0.0,state); add_material(0.0,state)
    report_targets={round(r.time_day*DAY_TO_S,9):r for r in schedule.rows[1:]}
    total=schedule.total_time_day*DAY_TO_S
    last_rep=None
    while t < total-1e-9:
        current=schedule.control_for_interval_starting_at(t); _apply_control(model,current)
        boundary=schedule.next_boundary_s(t); attempt=min(dt,dtmax,boundary-t,total-t)
        if attempt <= 0:
            h=RunHistory(report_states,report_rates,step_log,acc,rej,material,unique_warnings(warnings),sanity)
            raise SimulationFailure('non-positive timestep',h,t,attempt,last_rep)
        new,rep=model.advance(state,attempt); last_rep=rep
        if not rep.converged:
            rej+=1; step_log.append((t,attempt,False,rep.iterations,rep.active_set_iterations,rep.phase_switches,rep.residual_inf))
            dt=attempt*0.5
            if dt < dtmin:
                h=RunHistory(report_states,report_rates,step_log,acc,rej,material,unique_warnings(warnings),sanity)
                raise SimulationFailure(f'DTMIN reached at t={t/DAY_TO_S:g} day',h,t,attempt,rep)
            continue
        # Accepted backward-Euler flux is evaluated at the new state.
        if balance_supported:
            f=model.face_component_fluxes_sm3s(new)
            cum_ow += attempt*float(f['oil_well']); cum_gw += attempt*float(f['gas_component_well'])
            cum_oo += attempt*float(f['oil_outer']); cum_go += attempt*float(f['gas_component_outer'])
        state=new; t+=attempt; acc+=1
        # Cheap accepted-step diagnostics: catch transient range/sanity issues, not Newton trial excursions.
        if diagnostics_supported:
            warnings.extend(pvt_range_warnings(model,state))
            sanity.extend([f't={t/DAY_TO_S:g} d: {x}' for x in state_sanity(state)])
        step_log.append((t,attempt,True,rep.iterations,rep.active_set_iterations,rep.phase_switches,rep.residual_inf))
        dt=min(dtmax,max(dtmin,_grow_dt(attempt,rep)))
        key=round(t,9)
        if key in report_targets:
            td=t/DAY_TO_S; report_states.append((td,state.copy()))
            rr=model.well_rates(state); report_rates.append((td,rr,rr['bhp_bar']))
            add_diagnostics(td,state); add_material(td,state)
            _apply_control(model,report_targets[key])
    return RunHistory(report_states,report_rates,step_log,acc,rej,material,unique_warnings(warnings),sanity)
