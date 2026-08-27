import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / 'regression'
INPUTS = REG / 'inputs'
GOLDEN = REG / 'golden'

MAIN_CASES = ['T00','T01','T02','T03','T04','T06','T07','T08c','T09','T10','T11']
T05_CASES = [
    'T05S_N050_DT5m', 'T05S_N100_DT5m', 'T05S_N200_DT5m',
    'T05T_N100_DT60m', 'T05T_N100_DT10m', 'T05T_N100_DT3m',
]
CSV_FILES = ['profiles.csv','rates.csv','material_balance.csv']
ABS_TOL = 2e-7
REL_TOL = 2e-10


def _is_float(s):
    try:
        float(s)
        return True
    except Exception:
        return False


def compare_csv(golden_path, new_path):
    with open(golden_path, newline='', encoding='utf-8') as f:
        g = list(csv.reader(f))
    with open(new_path, newline='', encoding='utf-8') as f:
        n = list(csv.reader(f))
    if len(g) != len(n):
        return False, f'row count {len(n)} != golden {len(g)}'
    if not g:
        return True, ''
    if g[0] != n[0]:
        return False, 'header mismatch'
    max_abs = 0.0
    max_rel = 0.0
    for i, (gr, nr) in enumerate(zip(g[1:], n[1:]), start=2):
        if len(gr) != len(nr):
            return False, f'row {i} column count mismatch'
        for j, (a, b) in enumerate(zip(gr, nr), start=1):
            # NaN is a legitimate GOR value during shut-in.
            if a.lower() == 'nan' and b.lower() == 'nan':
                continue
            if _is_float(a) and _is_float(b):
                x, y = float(a), float(b)
                if math.isnan(x) and math.isnan(y):
                    continue
                da = abs(x-y)
                dr = da / max(abs(x), abs(y), 1.0)
                max_abs = max(max_abs, da)
                max_rel = max(max_rel, dr)
                if da > ABS_TOL and dr > REL_TOL:
                    return False, f'row {i} col {j}: {y} != golden {x} (abs={da:.3g}, rel={dr:.3g})'
            elif a != b:
                return False, f'row {i} col {j}: {b!r} != golden {a!r}'
    return True, f'max_abs={max_abs:.3g}, max_rel={max_rel:.3g}'


def compare_summary(golden_path, new_path):
    g = json.loads(Path(golden_path).read_text(encoding='utf-8'))
    n = json.loads(Path(new_path).read_text(encoding='utf-8'))
    required_equal = ['status','prototype_version','build_id','input_format_version','accepted_steps','rejected_steps','warning_count']
    for k in required_equal:
        if n.get(k) != g.get(k):
            return False, f'{k}: {n.get(k)!r} != golden {g.get(k)!r}'
    if n.get('warnings') != g.get('warnings'):
        return False, 'warning text differs from golden'
    for k in ['report_times_pass','state_and_control_pass','material_balance_pass']:
        if n.get('qc',{}).get(k) is not True:
            return False, f'QC {k} is not PASS'
    if n.get('report_days') != g.get('report_days'):
        return False, 'report days differ from golden'
    return True, ''


def run_one(case, input_path, golden_dir, output_dir):
    if output_dir.exists():
        shutil.rmtree(output_dir)
    cmd = [sys.executable, str(ROOT/'run_prototype.py'), str(input_path), '--output', str(output_dir)]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        return False, f'run failed rc={proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}'
    for name in CSV_FILES:
        ok, msg = compare_csv(golden_dir/name, output_dir/name)
        if not ok:
            return False, f'{name}: {msg}'
    ok, msg = compare_summary(golden_dir/'run_summary.json', output_dir/'run_summary.json')
    if not ok:
        return False, f'run_summary.json: {msg}'
    return True, 'golden output reproduced; QC PASS'


def main():
    ap = argparse.ArgumentParser(description='Frozen Prototype 1.0.3 numerical-core production regression')
    ap.add_argument('--quick', action='store_true', help='run T00-T04 and T06-T11; omit expensive T05 convergence block')
    ap.add_argument('--case', action='append', choices=MAIN_CASES + ['T05'] + T05_CASES,
                    help='run only selected case; may be repeated')
    ap.add_argument('--output-root', default=None)
    args = ap.parse_args()

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    outroot = Path(args.output_root) if args.output_root else ROOT/'OUTPUT'/f'REGRESSION_{stamp}'
    outroot.mkdir(parents=True, exist_ok=True)

    if args.case:
        selected = args.case
    else:
        selected = MAIN_CASES + ([] if args.quick else ['T05'])

    jobs=[]
    for c in selected:
        if c == 'T05':
            for sc in T05_CASES:
                jobs.append((sc, INPUTS/'T05'/f'{sc}.xlsx', GOLDEN/'T05'/sc, outroot/'T05'/sc))
        elif c in T05_CASES:
            jobs.append((c, INPUTS/'T05'/f'{c}.xlsx', GOLDEN/'T05'/c, outroot/'T05'/c))
        else:
            jobs.append((c, INPUTS/f'{c}.xlsx', GOLDEN/c, outroot/c))

    results=[]
    for name, inp, gold, out in jobs:
        print(f'[{name}] running...', flush=True)
        ok, msg = run_one(name, inp, gold, out)
        results.append((name,ok,msg))
        print(f'[{name}] {"PASS" if ok else "FAIL"}: {msg}', flush=True)
        if not ok:
            # continue to show all failures rather than stop on first one
            pass

    print('\n=== REGRESSION SUMMARY ===')
    for name,ok,msg in results:
        print(f'{name:20s} {"PASS" if ok else "FAIL"}')
    failures=[x for x in results if not x[1]]
    print(f'Passed {len(results)-len(failures)}/{len(results)} jobs')
    print(f'Outputs: {outroot}')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
