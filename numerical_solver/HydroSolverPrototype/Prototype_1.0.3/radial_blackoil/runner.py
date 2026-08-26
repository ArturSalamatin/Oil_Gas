from pathlib import Path
import csv,json,time,hashlib,math,traceback
import numpy as np
from .input_reader import load_input
from .grid import RadialGrid
from .rock import CompressibleRock
from .state import BlackOilState
from .blackoil import RadialBlackOilModel
from .simulation import simulate_schedule, SimulationFailure, RunHistory
from .units import DAY_TO_S
from .build_info import VERSION, BUILD_ID, INPUT_FORMAT_VERSION
from .output_artifacts import write_additional_outputs

MB_TOL_PCT=1e-4

def _sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def _write_history(out,grid,hist):
    with open(out/'profiles.csv','w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['time_day','cell','radius_m','pressure_bar','Sg','Rs'])
        for td,s in hist.report_states:
            for i in range(grid.n): w.writerow([td,i+1,grid.centers_m[i],s.pressure_bar[i],s.sg[i],s.rs_sm3_sm3[i]])
    with open(out/'rates.csv','w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['time_day','oil_rate_sm3_day','gas_rate_sm3_day','GOR_sm3_sm3','BHP_bar','control_mode','constraint_active'])
        for td,r,bhp in hist.report_rates:
            w.writerow([td,r['oil_sm3_s']*DAY_TO_S,r['total_gas_sm3_s']*DAY_TO_S,r['gor_sm3_sm3'],bhp,r.get('control_mode'),r.get('constraint_active')])
    with open(out/'step_log.csv','w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['time_s_or_start','dt_s','accepted','newton_iterations','active_set_iterations','phase_switches','residual_inf']); w.writerows(hist.step_log)
    cols=['time_day','oil_initial_sm3','oil_current_sm3','oil_produced_well_sm3','oil_outer_net_out_sm3','oil_balance_error_sm3','oil_balance_error_pct_initial',
          'gas_initial_sm3','gas_current_total_sm3','gas_current_dissolved_sm3','gas_current_free_sm3','gas_produced_well_sm3','gas_outer_net_out_sm3','gas_balance_error_sm3','gas_balance_error_pct_initial']
    with open(out/'material_balance.csv','w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(hist.material_balance)
    write_additional_outputs(out,grid,hist)

def _report_control_qc(inp,hist):
    issues=[]
    for td,r,_ in hist.report_rates:
        if td==0: ctrl=inp.schedule.rows[0]
        else: ctrl=inp.schedule.control_for_interval_starting_at(max(0.0,td*DAY_TO_S-1e-6))
        qo=r['oil_sm3_s']*DAY_TO_S; qg=r['total_gas_sm3_s']*DAY_TO_S
        if qo < -1e-10 or qg < -1e-8: issues.append(f't={td:g} d: producer has negative production rate')
        if ctrl.mode=='BHP':
            # A producer may float below target only when shut in; otherwise target BHP must be exact.
            if qo>1e-10 and abs(r['bhp_bar']-float(ctrl.bhp_bar))>1e-8:
                issues.append(f't={td:g} d: BHP control mismatch')
        elif ctrl.mode=='OIL_RATE':
            if not r.get('constraint_active',False) and abs(qo-float(ctrl.oil_rate_sm3_day))>1e-8:
                issues.append(f't={td:g} d: oil-rate control mismatch')
            if r.get('constraint_active',False) and ctrl.min_bhp_bar is not None and qo>1e-10 and abs(r['bhp_bar']-float(ctrl.min_bhp_bar))>1e-8:
                issues.append(f't={td:g} d: minimum-BHP constraint mismatch')
    return issues

def _build_summary(path,out,p,inp,hist,wall,status,error=None,failure=None):
    requested=[float(x) for x in inp.schedule.report_days]
    actual=[float(x[0]) for x in hist.report_states]
    report_ok=len(requested)==len(actual) and all(abs(a-b)<1e-10 for a,b in zip(requested,actual))
    mb_o=max([abs(float(x['oil_balance_error_pct_initial'])) for x in hist.material_balance] or [0.0])
    mb_g=max([abs(float(x['gas_balance_error_pct_initial'])) for x in hist.material_balance] or [0.0])
    control_issues=_report_control_qc(inp,hist)
    sanity=list(hist.sanity_issues)+control_issues
    if not report_ok: sanity.append('requested report times do not match written report times')
    qc={
        'report_times_pass':report_ok,
        'state_and_control_pass':len(sanity)==0,
        'state_and_control_issues':sanity[:50],
        'material_balance_pass':mb_o<=MB_TOL_PCT and mb_g<=MB_TOL_PCT,
        'material_balance_tolerance_pct_initial':MB_TOL_PCT,
        'max_abs_oil_balance_error_pct_initial':mb_o,
        'max_abs_gas_balance_error_pct_initial':mb_g,
    }
    summary={
        'status':status,'prototype_version':VERSION,'build_id':BUILD_ID,'input_format_version':INPUT_FORMAT_VERSION,
        'input':str(Path(path).resolve()),'input_filename':Path(path).name,'input_sha256':_sha256(path),
        'output':str(Path(out).resolve()),'wall_seconds':wall,
        'model':{'grid_cells_N':int(float(p['Grid cells N'])),'simulation_time_day':float(p['Simulation time']),'dt_initial_min':float(p['DT initial']),
                 'dt_min_s':float(p['DT minimum']),'dtmax_min':float(p['DTMAX']),'jacobian_mode':str(p['Jacobian mode']),'linear_solver':str(p['Linear solver'])},
        'accepted_steps':hist.accepted_steps,'rejected_steps':hist.rejected_steps,
        'pb_max_rs_bar':inp.pvt.bubble_point_max_rs_bar,
        'requested_report_days':requested,'report_days':actual,'schedule_rows_drive_reports':True,
        'warnings':hist.warnings,'warning_count':len(hist.warnings),'qc':qc,
    }
    if error is not None: summary['error']=str(error)
    if failure is not None:
        summary['failure']={'time_day':failure.time_s/DAY_TO_S,'last_attempt_dt_s':failure.last_dt_s}
        if failure.last_report is not None:
            summary['failure'].update({'newton_iterations':failure.last_report.iterations,'active_set_iterations':failure.last_report.active_set_iterations,
                                       'phase_switches':failure.last_report.phase_switches,'residual_inf':failure.last_report.residual_inf})
    return summary

def _write_summary(out,summary):
    txt=json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False)
    (out/'run_summary.json').write_text(txt,encoding='utf-8'); (out/'summary.json').write_text(txt,encoding='utf-8')
    lines=[f"Prototype {summary['prototype_version']} | build {summary['build_id']}",f"STATUS: {summary['status']}",f"Input: {summary['input_filename']}",f"Output: {summary['output']}",
           f"Accepted/rejected steps: {summary['accepted_steps']}/{summary['rejected_steps']}",f"Wall time: {summary['wall_seconds']:.6g} s",
           f"Material balance max errors: oil={summary['qc']['max_abs_oil_balance_error_pct_initial']:.6g}% initial, gas={summary['qc']['max_abs_gas_balance_error_pct_initial']:.6g}% initial",
           f"QC report/state/material: {summary['qc']['report_times_pass']}/{summary['qc']['state_and_control_pass']}/{summary['qc']['material_balance_pass']}"]
    if summary.get('warnings'):
        lines.append('WARNINGS:'); lines += ['- '+x for x in summary['warnings']]
    if summary.get('error'): lines += ['ERROR: '+summary['error']]
    (out/'run_summary.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def run_workbook(path,outdir):
    path=Path(path); inp=load_input(path); p=inp.params; out=Path(outdir); out.mkdir(parents=True,exist_ok=True)
    grid=RadialGrid(float(p['Well radius rw']),float(p['Outer radius re']),float(p['Formation thickness h']),int(p['Grid cells N']),float(p['Absolute permeability']))
    rock=CompressibleRock(float(p['Reference porosity']),float(p['Reference pressure']),float(p['Rock compressibility cr']))
    first=inp.schedule.rows[0]
    initial_bhp=first.bhp_bar if first.mode=='BHP' else (first.min_bhp_bar if first.min_bhp_bar is not None else float(p['Outer-boundary pressure']))
    model=RadialBlackOilModel(grid,rock,inp.pvt,inp.relperm,initial_bhp,float(p['Outer-boundary pressure']),float(p['Initial dissolved gas Rs']),skin=float(p['Well skin']),jacobian_mode=str(p['Jacobian mode']),linear_solver=str(p['Linear solver']))
    state0=BlackOilState.undersaturated(grid.n,float(p['Initial pressure']),float(p['Initial dissolved gas Rs']))
    dt0=float(p['DT initial'])*60.0; dtmin=float(p['DT minimum']); dtmax=float(p['DTMAX'])*60.0
    tic=time.perf_counter()
    try:
        hist=simulate_schedule(model,state0,inp.schedule,dt0,dtmin,dtmax); wall=time.perf_counter()-tic
        _write_history(out,grid,hist); summary=_build_summary(path,out,p,inp,hist,wall,'SUCCESS'); _write_summary(out,summary); return summary
    except SimulationFailure as e:
        wall=time.perf_counter()-tic; hist=e.history
        _write_history(out,grid,hist); summary=_build_summary(path,out,p,inp,hist,wall,'FAILED',e,e); _write_summary(out,summary)
        raise
