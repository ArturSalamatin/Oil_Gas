# Project reference

## Project Structure

| Folder / file | Contents |
|---|---|
| `simplefied_approaches/cooling_models.tex` | Main document: hierarchy of cooling models (М.1–М.6), from algebraic estimates to PDEs (GORM + temperature) |
| `GORM_2/trapped_gas.tex` | Unconfined filtration with a trapped gas cap (Boussinesq equation + nonlocal gas pressure closure) |
| `method_of_moments_isotermal/integral_relations_method.tex` | Barenblatt integral relations method for two-phase Black Oil filtration |
| `method_of_moments/two_phase_energy.tex` | Two-phase filtration with energy equation – current working formulation |
| `method_of_moments/moments_method.tex` | Method of moments – formulas implemented in code |
| `method_of_moments/src/` | Python solver code (see the Python section) |
| `method_of_moments/tests/` | pytest tests |
| `method_of_moments/configs/` | JSON problem configurations (`baseline.json`, etc.) |
| `method_of_moments/results/` | Output data (.csv, .png) |
| `Постановка/` | Reports and problem formulations (.docx, .pdf) |
| `Refs/` | Literature: Kanevskaya, Basniev, Sharafutdinov, Muskat, OPM Flow Manual and others |
| `Refs/GORM/` | Papers on GORM (Konieczek 1990, Mjaavatten 2008) |
| `black_oil_gas_mass.html` | Interactive note: mass of gas released in the Black Oil model |
| `tools/release.py` | Solver release with both deliverables: version numbers, tag, two wheels, example and documentation archives, README and development handover archive in Releases (`tools/handover.py` in step 3, before push); acceptance only with `--acceptance`; sequence in the docstring (FEAT-038, DEBT-089) |
| `tools/handover.py` | Development handover: snapshot from the release tag, formulation PDF, HTML documentation and archive; called by the release script, or separately for acceptance or rebuilding an existing tag; without a tag uses the latest release; acceptance in an unpacked copy only with `--acceptance`; does not change git (FEAT-031) |
| `tools/acceptance.py` | Acceptance of a copy in a fresh environment; runs `handover.py --acceptance` separately or through `release.py --acceptance` (no acceptance by default); not delivered to the customer (decision 2026-10-19) |

## Physical Problem

Processes modeled:
1. **Oil filtration with dissolved gas** – Darcy's law, relative permeability and PVT properties (Black Oil).
2. **Degassing** – gas evolves from oil when $P < P_{b}$; gas content $R_s(P,T)$ follows the Standing correlation.
3. **Heat transfer** – convection, thermal conduction, Joule–Thomson effect and latent heat of degassing.
4. **Gas cap dynamics** – material balance (0D) or Dupuit approximation (PDE).

Model variants in `simplefied_approaches/cooling_models.tex`:
- М.1: JT estimate (algebraic)
- М.2: Degassing energy balance (algebraic)
- М.3: Steady enthalpy balance (nonlinear equation)
- М.4: Transient enthalpy balance (ODE system)
- М.5: Spatial problem with prescribed pressure (one PDE for T)
- М.6: GORM + degassing + temperature (2–3 PDEs)

Additional approaches:
- Unconfined filtration with trapped gas (GORM_2/)
- Barenblatt integral relations method (method_of_moments_isotermal/)

## Method of moments

### src/ Structure

```
src/
├── pvt/                # Black Oil PVT properties
│   ├── correlations.py # Rs(p,T), Bo, Bg, μ – Standing and other correlations
│   └── black_oil.py    # BlackOilFluid: all PVT + relative permeability in one class
├── profiles/           # Parameterization of p(r), Sg(r), T(r) profiles
│   ├── pressure.py     # Φ(η), dp/dr, γ(rb) – §4.2 moments_method.tex
│   ├── saturation.py   # Sg(r) = Sg,w·(1−η)^β – §4.3
│   └── temperature.py  # Ψ(ζ), ΔTw – §4.4
├── integrals.py        # I_Φ^(n), I_Ψ^(n), I_S^(n) – §5.4, closed-form formulas
├── coefficients.py     # A_ij, F_i – §5.1–5.4, ODE matrix and right-hand side
├── ode_system.py       # Right-hand side for solve_ivp
├── initial.py          # Initial asymptotics §6: rb(tε), Sg,w^eq
├── solver.py           # Wrapper: parameters → solution (rb(t), Sg,w(t), ΔTw(t))
└── main.py             # CLI: JSON config → solution → output
```

### Running

```powershell
cd d:\Lessons\Grants\2026\GPN\Oil_Gas\method_of_moments
.venv\Scripts\python -m pytest tests/ -v          # tests
.venv\Scripts\python src/main.py configs/baseline.json  # solver
```

### Dependencies

`pyproject.toml` in `method_of_moments/`. Installation: `pip install -e ".[dev]"`.

## Literature

Available sources in `Refs/`:
- Каневская – mathematical modeling of reservoir systems
- Баснеев – underground hydromechanics
- Гиматудинов – physics of oil and gas reservoirs
- Шарафутдинов, Канафин, Хабиров (2019) – numerical study of the temperature field in a well with a multilayer system during flow of gas-bearing oil (ПМТФ, vol. 60, no. 5)
- Мирзаджанзаде – fundamentals of gas production technology
- Мускат – flow of homogeneous fluids in porous media
- OPM Flow Reference Manual 2025-10
- Konieczek 1990 (SPE 20722) – Gas Coning, Critical Rate
- Mjaavatten et al. 2008 (SPE 102390) – GORM for an oil rim

When discussing physics and mathematics, cite specific sources.


## numerical_solver (PDE Solver)

New library: FVM on a logarithmic radial grid. Formulation: `numerical_solver/doc/problem_statement.tex`.

Code: `numerical_solver/gpn_multiphase_solver/`. Package name: `gpn_multiphase_solver` (pip: `gpn-multiphase-solver`). Completely independent of `method_of_moments/`.

Run from a config: `python -m gpn_multiphase_solver run <config.json>` (or `gpn-solver run …`); results go to `output/` next to the config (FEAT-030). For an Excel workbook use `run <книга.xlsx>`; its converted input is saved in `output/input/`, and the output directory is cleared before the calculation (FEAT-036).

HTML documentation (FEAT-031): `python -m sphinx -W -b html doc/source doc/build/html` from `numerical_solver/`; the main file `doc/build/html/index.html` contains the README, technical description (package and subpackage docstrings) and public API. Public API inventory: `doc/source/api.rst`; `tests/test_docs.py` checks the docstring rule and a warning-free build. After editing `problem_statement.tex` and building the PDF, run `tools/eq_numbers.py` (label-to-number table for HTML). Development installation: `setup.bat`; acceptance of a copy in a fresh environment: `tools/acceptance.py <копия>` from the root (not delivered to the customer and not included in the snapshot); release with both deliverables: `tools/release.py X.Y.Z [--acceptance]` from the repository root (it calls `tools/handover.py` to build the development handover archive); run `tools/handover.py <метка выпуска>` separately for acceptance or to rebuild the archive for an existing tag.

Architectural decisions, module contracts and sign conventions: `vault/knowledge/decisions/`.

Key notes:
- `архитектура библиотеки numerical_solver.md` – modules, patterns, ABCs
- `словарь-код-физика.md` – correspondence between code variables and physics
- `конвенции-знаков.md` – positive direction = away from well (increasing r)
- `порядок-реализации-модулей.md` – 9 implementation phases

## Test pyramid

Test pyramid (pytest):

| Level | What it tests | Example |
|---|---|---|
| Unit | One isolated module | `test_pvt.py`: Rs(p,T) at known p,T |
| Boundary | Limiting cases | Sg=0, p=pb, T=T0 |
| Consistency | Physical invariants | So+Sg=1, energy balance |
| Integration | solve_ivp with the complete system | `test_solver.py`: rb grows, Sg∈[0,1] |
| Validation | Comparison with a reference | VAL-001: Dupuit, VAL-002: vs PDE |

