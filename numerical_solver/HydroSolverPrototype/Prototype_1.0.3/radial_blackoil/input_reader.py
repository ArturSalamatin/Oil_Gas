from dataclasses import dataclass
from pathlib import Path
from .xlsxio import read_workbook_tables
from .pvt import BlackOilPVT
from .relperm import TabulatedRelPerm
from .schedule import Schedule, ScheduleRow

class InputValidationError(ValueError): pass

@dataclass
class ModelInput:
    path: Path
    params: dict
    pvt: BlackOilPVT
    relperm: TabulatedRelPerm
    schedule: Schedule

def _table(rows,name,required_headers):
    if not rows: raise InputValidationError(f'{name}: empty sheet')
    h=[str(x).strip() if x is not None else '' for x in rows[0]]
    idx={x:i for i,x in enumerate(h)}
    missing=[x for x in required_headers if x not in idx]
    if missing: raise InputValidationError(f'{name}: missing columns {missing}')
    return idx,rows[1:]

def load_input(path):
    path=Path(path); sheets=read_workbook_tables(path)
    required=['MODEL','SCHEDULE','OIL_PVT','GAS_PVT','RELPERM']
    miss=[s for s in required if s not in sheets]
    if miss: raise InputValidationError(f'missing sheets: {miss}')
    idx,rows=_table(sheets['MODEL'],'MODEL',['Parameter','Value','Unit'])
    p={}
    for r in rows:
        if len(r)<=idx['Parameter'] or r[idx['Parameter']] in (None,''): continue
        key=str(r[idx['Parameter']]).strip(); val=r[idx['Value']] if len(r)>idx['Value'] else None
        p[key]=val
    reqp=['Initial pressure','Outer-boundary pressure','Initial dissolved gas Rs','Well radius rw','Outer radius re','Formation thickness h','Absolute permeability','Reference porosity','Reference pressure','Rock compressibility cr','Well skin','Grid cells N','Simulation time','DT initial','DT minimum','DTMAX','Jacobian mode','Linear solver']
    missing=[x for x in reqp if x not in p]
    if missing: raise InputValidationError(f'MODEL: missing parameters {missing}')

    # Cheap top-level validation for production inputs.
    numeric_positive=['Initial pressure','Outer-boundary pressure','Well radius rw','Outer radius re','Formation thickness h','Absolute permeability','Reference porosity','Reference pressure','Grid cells N','Simulation time','DT initial','DT minimum','DTMAX']
    for key in numeric_positive:
        try: v=float(p[key])
        except Exception as e: raise InputValidationError(f'MODEL: {key} must be numeric') from e
        if v<=0: raise InputValidationError(f'MODEL: {key} must be > 0')
    if float(p['Well radius rw']) >= float(p['Outer radius re']): raise InputValidationError('MODEL: Well radius rw must be < Outer radius re')
    if not (0 < float(p['Reference porosity']) <= 1): raise InputValidationError('MODEL: Reference porosity must be in (0,1]')
    if float(p['Rock compressibility cr']) < 0: raise InputValidationError('MODEL: Rock compressibility cr must be >= 0')
    if int(float(p['Grid cells N'])) != float(p['Grid cells N']): raise InputValidationError('MODEL: Grid cells N must be an integer')
    if str(p['Jacobian mode']).strip() not in ('grouped','reference'): raise InputValidationError("MODEL: Jacobian mode must be 'grouped' or 'reference'")
    if str(p['Linear solver']).strip() not in ('sparse','dense'): raise InputValidationError("MODEL: Linear solver must be 'sparse' or 'dense'")

    idx,rows=_table(sheets['OIL_PVT'],'OIL_PVT',['Rs, Sm3/Sm3','Pressure, bar(a)','Bo, rm3/Sm3','mu_o, cP'])
    oil=[]
    for r in rows:
        try: oil.append(tuple(float(r[idx[k]]) for k in ['Rs, Sm3/Sm3','Pressure, bar(a)','Bo, rm3/Sm3','mu_o, cP']))
        except (TypeError,ValueError,IndexError): continue
    if not oil: raise InputValidationError('OIL_PVT: no numeric rows')
    # Validate Eclipse PVTO branch ordering.
    for rs in sorted(set(x[0] for x in oil)):
        pp=[x[1] for x in oil if x[0]==rs]
        if len(pp)<2: raise InputValidationError(f'OIL_PVT: Rs={rs:g} needs >=2 rows')
        if any(b<=a for a,b in zip(pp,pp[1:])): raise InputValidationError(f'OIL_PVT: pressure must increase inside Rs={rs:g} branch')

    idx,rows=_table(sheets['GAS_PVT'],'GAS_PVT',['Pressure, bar(a)','Bg, rm3/Sm3','mu_g, cP'])
    gas=[]
    for r in rows:
        try: gas.append(tuple(float(r[idx[k]]) for k in ['Pressure, bar(a)','Bg, rm3/Sm3','mu_g, cP']))
        except (TypeError,ValueError,IndexError): continue
    if len(gas)<2: raise InputValidationError('GAS_PVT: needs >=2 numeric rows')
    if any(gas[i+1][0] <= gas[i][0] for i in range(len(gas)-1)): raise InputValidationError('GAS_PVT: pressure must be strictly increasing')
    if any(bg<=0 or mu<=0 for _,bg,mu in gas): raise InputValidationError('GAS_PVT: Bg and mu_g must be > 0')
    idx,rows=_table(sheets['RELPERM'],'RELPERM',['Sg','kro','krg'])
    rel=[]
    for r in rows:
        try: rel.append(tuple(float(r[idx[k]]) for k in ['Sg','kro','krg']))
        except (TypeError,ValueError,IndexError): continue

    if len(rel)<2: raise InputValidationError('RELPERM: needs >=2 numeric rows')
    if any(not (0<=sg<=1) for sg,_,_ in rel): raise InputValidationError('RELPERM: Sg must be in [0,1]')
    if any(kro<0 or krg<0 for _,kro,krg in rel): raise InputValidationError('RELPERM: kro and krg must be >= 0')
    idx,rows=_table(sheets['SCHEDULE'],'SCHEDULE',['Time, day','Control mode','BHP target, bar(a)','Oil-rate target, Sm3/day','Minimum BHP, bar(a)'])
    sch=[]
    for r in rows:
        if len(r)<=idx['Time, day'] or r[idx['Time, day']] in (None,''): continue
        def get(col):
            j=idx[col]; return None if j>=len(r) or r[j] in (None,'') else r[j]
        t=float(get('Time, day')); mode=str(get('Control mode')).strip().upper()
        bhp=get('BHP target, bar(a)'); qo=get('Oil-rate target, Sm3/day'); mb=get('Minimum BHP, bar(a)')
        if mode=='BHP':
            if bhp is None: raise InputValidationError(f'SCHEDULE t={t}: BHP target required')
            if qo is not None or mb is not None: raise InputValidationError(f'SCHEDULE t={t}: oil-rate/min-BHP must be blank in BHP mode')
        elif mode=='OIL_RATE':
            if qo is None: raise InputValidationError(f'SCHEDULE t={t}: oil-rate target required')
            if bhp is not None: raise InputValidationError(f'SCHEDULE t={t}: BHP target must be blank in OIL_RATE mode')
        else: raise InputValidationError(f'SCHEDULE t={t}: unsupported Control mode {mode!r}')
        sch.append(ScheduleRow(t,mode,None if bhp is None else float(bhp),None if qo is None else float(qo),None if mb is None else float(mb)))
    schedule=Schedule(sch,float(p['Simulation time']))
    return ModelInput(path,p,BlackOilPVT(oil,gas),TabulatedRelPerm(*zip(*rel)),schedule)
