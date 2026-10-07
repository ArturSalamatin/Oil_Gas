"""Аудит BUG-017: выборочная перепроверка §1.1–1.2 плана на коде до правки.

Первый шаг RadialBlackOilModel.advance(state, 3600 с) из однородного
начального состояния (p0, Rs0, S_g = 0). Rs0/p0 — в памяти, конфиги не меняются.
Замер аудита 2026-10-01 (cc12520): 111.024 / 20.144 / 13.780 / 9.417 МПа.
Только для кода до правки: после BUG-017 все четыре состояния отвергает
from_config (Rs0 = 40, 31 — «вне диапазона таблицы», Стендинг — «пересыщено»).
Запуск (PowerShell) из numerical_solver нужного дерева:
  $env:PYTHONPATH = "HydroSolverPrototype/Prototype_1.0.3;" + (Get-Location).Path
  python <путь к пробам>/spot_first_step.py
"""
import numpy as np
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.units import BAR_TO_PA
from radial_blackoil.state import BlackOilState

CASES = [
    ("examples/12_large_drainage_radius/config.json", 40.0, None),
    ("examples/12_large_drainage_radius/config.json", 31.0, None),
    ("examples/03_standing_corey/config.json", 80.0, 10e6),
    ("examples/03_standing_corey/config.json", 50.0, 9e6),
]
for path, rs0, p0 in CASES:
    c = load_config(path)
    c.initial_conditions.Rs0 = rs0
    if p0 is not None:
        c.initial_conditions.p0 = p0
    sim, _ = SimulatorFactory.from_config(c)
    model = sim._hydro._model
    st = BlackOilState.undersaturated(c.grid.N, c.initial_conditions.p0 / BAR_TO_PA, rs0)
    try:
        new, rep = model.advance(st, 3600.0)
        print(f"{path.split('/')[1]:28s} Rs0={rs0:5g} p0={c.initial_conditions.p0/1e6:5.2f} МПа: "
              f"conv={rep.converged} glob={rep.globalized} p_max={new.pressure_bar.max()*BAR_TO_PA/1e6:.3f} МПа "
              f"Sg={new.sg.min():.3f}…{new.sg.max():.3f}")
    except Exception as e:
        print(f"{path.split('/')[1]:28s} Rs0={rs0:5g}: {type(e).__name__}: {e}")
