from pathlib import Path
import numpy as np
from radial_blackoil.input_reader import load_input
from radial_blackoil.grid import RadialGrid
from radial_blackoil.rock import CompressibleRock
from radial_blackoil.blackoil import RadialBlackOilModel
from radial_blackoil.state import BlackOilState

ROOT=Path(__file__).resolve().parents[1]

def model_and_state(n=12,bhp=100.0,p0=200.0,case='Nabor_1b.xlsx',jacobian='grouped',linear='sparse'):
    inp=load_input(ROOT/'tests'/'fixtures'/case); p=inp.params
    g=RadialGrid(float(p['Well radius rw']),float(p['Outer radius re']),float(p['Formation thickness h']),n,float(p['Absolute permeability']))
    r=CompressibleRock(float(p['Reference porosity']),float(p['Reference pressure']),float(p['Rock compressibility cr']))
    m=RadialBlackOilModel(g,r,inp.pvt,inp.relperm,bhp,float(p['Outer-boundary pressure']),float(p['Initial dissolved gas Rs']),skin=float(p['Well skin']),jacobian_mode=jacobian,linear_solver=linear)
    s=BlackOilState.undersaturated(g.n,p0,float(p['Initial dissolved gas Rs']))
    return inp,m,s
