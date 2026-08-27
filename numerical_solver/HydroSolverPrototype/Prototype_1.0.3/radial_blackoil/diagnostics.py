"""Lightweight runtime diagnostics for Prototype 1.0.3."""
from __future__ import annotations
import math
import numpy as np


def state_sanity(state, tol=1e-9):
    p=np.asarray(state.pressure_bar,float); sg=np.asarray(state.sg,float); rs=np.asarray(state.rs_sm3_sm3,float)
    issues=[]
    if not (np.all(np.isfinite(p)) and np.all(np.isfinite(sg)) and np.all(np.isfinite(rs))): issues.append('state contains NaN/Inf')
    if np.any(p<=0): issues.append('pressure <= 0 bar')
    if np.any(sg < -tol) or np.any(sg > 1.0+tol): issues.append('Sg outside [0,1]')
    if np.any(rs < -tol): issues.append('Rs < 0')
    return issues


def _range_tol(x):
    """Ignore machine-roundoff-sized endpoint excursions in diagnostics."""
    return 1e-9*max(1.0, abs(float(x)))


def pvt_range_warnings(model,state):
    """Return warnings for ACCEPTED states only. Evaluation itself always clamps."""
    p=np.asarray(state.pressure_bar,float); rs=np.asarray(state.rs_sm3_sm3,float)
    w=[]; pvt=model.pvt; rp=model.relperm
    pmin=float(np.min(p)); pmax=float(np.max(p)); rmin=float(np.min(rs)); rmax=float(np.max(rs))
    if pmin < pvt.gp[0]-_range_tol(pvt.gp[0]):
        w.append(f'GAS_PVT pressure below table: min P={pmin:.8g} bar, table min={pvt.gp[0]:.8g} bar. Endpoint value used; no extrapolation.')
    if pmax > pvt.gp[-1]+_range_tol(pvt.gp[-1]):
        w.append(f'GAS_PVT pressure above table: max P={pmax:.8g} bar, table max={pvt.gp[-1]:.8g} bar. Endpoint value used; no extrapolation.')
    if rmin < pvt.rs_values[0]-_range_tol(pvt.rs_values[0]):
        w.append(f'OIL_PVT Rs below table: min Rs={rmin:.8g}, table min={pvt.rs_values[0]:.8g}. Endpoint branch used; no extrapolation.')
    if rmax > pvt.rs_values[-1]+_range_tol(pvt.rs_values[-1]):
        w.append(f'OIL_PVT Rs above table: max Rs={rmax:.8g}, table max={pvt.rs_values[-1]:.8g}. Endpoint branch used; no extrapolation.')
    # Gas-active saturated locus is defined only over the supplied Pb(Rs) anchors.
    ga=np.asarray(state.gas_active,bool)
    if np.any(ga):
        pg=p[ga]
        if np.min(pg) < pvt.pb[0]-_range_tol(pvt.pb[0]):
            w.append(f'OIL_PVT saturated locus below table: gas-active min P={np.min(pg):.8g} bar, min Pb={pvt.pb[0]:.8g} bar. Endpoint Rs used; no extrapolation.')
        if np.max(pg) > pvt.pb[-1]+_range_tol(pvt.pb[-1]):
            w.append(f'OIL_PVT saturated locus above table: gas-active max P={np.max(pg):.8g} bar, max Pb={pvt.pb[-1]:.8g} bar. Endpoint Rs used; no extrapolation.')
    # Check fixed-Rs branch high-pressure coverage for accepted oil states.
    pmax_branch=pvt.max_pressure_of_rs(rs)
    if np.any(p > pmax_branch + 1e-9*np.maximum(1.0,np.abs(pmax_branch))):
        excess=np.max(p-pmax_branch)
        w.append(f'OIL_PVT branch pressure above supplied range by up to {excess:.8g} bar. Endpoint branch property used; no extrapolation.')
    sg=np.asarray(state.sg,float)
    if np.min(sg) < rp.sg[0]-_range_tol(rp.sg[0]):
        w.append(f'RELPERM Sg below table: min Sg={np.min(sg):.8g}, table min={rp.sg[0]:.8g}. Endpoint value used; no extrapolation.')
    if np.max(sg) > rp.sg[-1]+_range_tol(rp.sg[-1]):
        w.append(f'RELPERM Sg above table: max Sg={np.max(sg):.8g}, table max={rp.sg[-1]:.8g}. Endpoint value used; no extrapolation.')
    return w


def unique_warnings(items):
    # Keep one representative per warning category to prevent run_summary flooding.
    categories=(
        'GAS_PVT pressure below table','GAS_PVT pressure above table',
        'OIL_PVT Rs below table','OIL_PVT Rs above table',
        'OIL_PVT saturated locus below table','OIL_PVT saturated locus above table',
        'OIL_PVT branch pressure above supplied range',
        'RELPERM Sg below table','RELPERM Sg above table')
    out=[]; seen=set()
    for s in items:
        key=next((c for c in categories if s.startswith(c)),s.split(':',1)[0])
        if key not in seen: seen.add(key); out.append(s)
    return out
