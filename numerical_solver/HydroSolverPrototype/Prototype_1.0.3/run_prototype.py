import argparse,sys
from pathlib import Path
from radial_blackoil.runner import run_workbook
from radial_blackoil.simulation import SimulationFailure
from radial_blackoil.input_reader import InputValidationError
from radial_blackoil.build_info import VERSION

ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=f'Prototype {VERSION} radial black-oil solver')
p.add_argument('input_xlsx'); p.add_argument('--output',default=None)
a=p.parse_args()
inp=Path(a.input_xlsx)
out=Path(a.output) if a.output else ROOT/'OUTPUT'/inp.stem
try:
    s=run_workbook(inp,out); print(f"SUCCESS: {out}"); print(f"run_summary: {out/'run_summary.json'}")
except InputValidationError as e:
    print(f'INPUT ERROR: {e}',file=sys.stderr); sys.exit(2)
except SimulationFailure as e:
    print(f'CALCULATION FAILED: {e}',file=sys.stderr); print(f'Partial results: {out}',file=sys.stderr); sys.exit(3)
