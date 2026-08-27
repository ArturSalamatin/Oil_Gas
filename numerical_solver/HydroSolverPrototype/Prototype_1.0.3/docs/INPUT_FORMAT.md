# Input workbook format

Required sheets:

- `MODEL`
- `SCHEDULE`
- `OIL_PVT`
- `GAS_PVT`
- `RELPERM`

`COMMENTS` is documentation only and is ignored by the solver.

## MODEL

Contains reservoir, grid and numerical settings. The supported production setup includes `N`, geometry, permeability, porosity/rock compressibility, initial/outer pressure, initial Rs, skin, simulation time, timestep controls, Jacobian mode and linear solver.

The validated standard numerical configuration for the current benchmark family is `N=100`, `DTMAX=60 min`, grouped Jacobian and sparse linear solver.

## SCHEDULE

Every row is simultaneously:

1. an exact integration boundary;
2. a mandatory report time;
3. the control definition for the interval immediately after that boundary.

At a true control-change time, the state saved exactly at the boundary is the state reached under the previous control; the new control acts on the next timestep.

Supported controls:

- `BHP`
- `OIL_RATE`
- optional `Minimum BHP` for rate control.

Repeating the same control at a new time is a normal way to request an exact report point.

## OIL_PVT

ECLIPSE/tNavigator-style PVTO semantics are used. For each fixed-Rs branch, the first/minimum-pressure row is the saturated point `Pb(Rs)`; subsequent higher-pressure rows are undersaturated fixed-Rs properties.

## Out-of-range behavior

There is no linear extrapolation. Endpoint values / endpoint branches are used (`clamp`) and the accepted-state exceedance is recorded as a warning in `run_summary`.
