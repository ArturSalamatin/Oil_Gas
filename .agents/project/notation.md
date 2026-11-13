# Project notation

## Symbols and Notation

This is the common symbol dictionary for all project documents. Follow it when creating new sections and documents.

### Coordinates and Time

| Symbol | Meaning |
|---|---|
| $r$ | radial coordinate (distance from well axis), m |
| $x$ | horizontal coordinate (perpendicular to the well, in GORM), m |
| $z$ | vertical coordinate (upward from the bottom), m |
| $t$ | time, s |

### Pressure and Temperature

| Symbol | Meaning |
|---|---|
| $p$ | pressure, Pa |
| $p_b$ | bubble-point pressure |
| $p_{wf}$ | bottomhole pressure |
| $p_0$ | initial reservoir pressure; in `numerical_solver/doc/problem_statement.tex` reservoir pressure is $p_{\text{пл}}$, while $p_0$, $T_0$ are values in cell 0 at the well (DEBT-070) |
| $T$ | temperature, K |
| $T_{\text{пл}}$ | undisturbed reservoir temperature |

### Phases and Saturations

| Symbol | Meaning |
|---|---|
| subscript $o$ | oil (liquid) phase |
| subscript $g$ | gas phase |
| subscript ст | standard conditions |
| $S_o$, $S_g$ | saturations (volume fractions); $S_o + S_g = 1$ |
| $x_g$ | mass fraction of free gas |

### PVT Properties

| Symbol | Meaning |
|---|---|
| $R_s(p,T)$ | gas content, м³ст/м³ст oil |
| $B_o(p)$ | oil formation volume factor |
| $B_g(p)$ | gas formation volume factor |
| $\rho_o$, $\rho_g$ | phase densities at reservoir conditions, kg/m³ |
| $\mu_o$, $\mu_g$ | phase viscosities, Pa·s |
| $c_{p,o}$, $c_{p,g}$ | specific heat capacities, J/(kg·K) |

### Porous Medium

| Symbol | Meaning |
|---|---|
| $\phi$ | porosity |
| $k$ | absolute permeability, m² |
| $k_{ro}$, $k_{rg}$ | relative phase permeabilities |
| $\lambda_{\text{eff}}$ | effective thermal conductivity (fluid + rock), W/(m·K) |
| $(\rho c_p)_s$ | volumetric heat capacity of the rock skeleton, J/(m³·K) |

### Thermodynamics

| Symbol | Meaning |
|---|---|
| $h_o$, $h_g$ | phase specific enthalpies, J/kg |
| $h_{\text{mix}}$ | mixture specific enthalpy, J/kg |
| $L$ | specific heat of degassing (vaporization), J/kg of gas |
| $\mu_{\text{JT}}$ | Joule–Thomson coefficient, K/Pa |
| $\alpha$ | thermal expansion coefficient, K⁻¹ |

### Well and Reservoir Geometry

| Symbol | Meaning |
|---|---|
| $r_w$ | well radius, m |
| $r_e$ | outer reservoir boundary radius, m |
| $h$ | oil layer thickness (in GORM), m |
| $H$ | reservoir roof height, m |
| $W$ | drainage area half-width, m |


For the sign convention, see AGENTS.md and vault/knowledge/decisions/.
