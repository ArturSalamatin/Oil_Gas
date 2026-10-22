r"""DEBT-038: код плана подменой — _check_pvto_branches шага 3 между чтением CSV и BlackOilPVT.

Обёртка _read_oil_pvt_csv вызывает проверку сразу после чтения — то же место,
что вызов в _create_pvt по плану (до BlackOilPVT и _check_rs0_in_table).
Проверяет регулярные выражения тестов шага 2 и все oil_pvt.csv проекта.
Запуск из numerical_solver/:  .venv\Scripts\python ..\vault\issues\debt-038\probes\plan_check.py
"""
import re
import shutil
import sys
from pathlib import Path

SOLVER = Path(__file__).resolve().parents[4] / "numerical_solver"
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver import factory                        # noqa: E402
from gpn_multiphase_solver.io.config import load_config          # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA                # noqa: E402


# ── Функция шага 3 плана, дословно ──
def _check_pvto_branches(oil_rows: list[tuple], oil_pvt_file: str) -> None:
    """Ветви PVTO: ≥ 2 строк, давление растёт, p_b растёт с R_s, иначе ValueError (DEBT-038)."""
    if not oil_rows:
        raise ValueError(f"{oil_pvt_file}: нет ни одной числовой строки.")
    branches: dict[float, list[float]] = {}
    for Rs, p_bar, _, _ in oil_rows:
        branches.setdefault(Rs, []).append(p_bar)
    for Rs, p_bar in sorted(branches.items()):
        p_mpa = [p * BAR_TO_PA / 1e6 for p in p_bar]   # только для сообщений
        if len(p_bar) < 2:
            raise ValueError(
                f"{oil_pvt_file}: ветвь R_s = {Rs:g} м³ст/м³ст из одной строки "
                f"(p = {p_mpa[0]:g} МПа). Нужно не меньше двух: насыщенная точка "
                f"p_b(R_s) и хотя бы одна строка выше p_b — иначе B_o, μ_o "
                f"недонасыщенной нефти не заданы.")
        for k in range(1, len(p_bar)):
            if p_bar[k] <= p_bar[k - 1]:
                raise ValueError(
                    f"{oil_pvt_file}: в ветви R_s = {Rs:g} м³ст/м³ст давление "
                    f"не растёт строго: {p_mpa[k]:g} МПа после {p_mpa[k - 1]:g} МПа "
                    f"(строки {k} и {k + 1} ветви). Первая строка ветви — "
                    f"насыщенная точка p_b(R_s), дальше давление растёт.")
    rs_sorted = sorted(branches)
    for Rs_lo, Rs_hi in zip(rs_sorted, rs_sorted[1:]):
        pb_lo, pb_hi = branches[Rs_lo][0], branches[Rs_hi][0]
        if pb_hi <= pb_lo:
            raise ValueError(
                f"{oil_pvt_file}: давление насыщения не растёт с R_s: "
                f"p_b = {pb_hi * BAR_TO_PA / 1e6:g} МПа у ветви R_s = {Rs_hi:g} "
                f"при p_b = {pb_lo * BAR_TO_PA / 1e6:g} МПа у ветви R_s = {Rs_lo:g} "
                f"м³ст/м³ст. p_b — давление первой строки ветви.")


_original_reader = factory._read_oil_pvt_csv


def _reader_with_check(csv_path):
    rows = _original_reader(csv_path)
    _check_pvto_branches(rows, csv_path.name)   # в плане — pc.oil_pvt_file (имя из конфига)
    return rows


factory._read_oil_pvt_csv = _reader_with_check

TABLE_CONFIG = SOLVER / "configs" / "table_pvt" / "config.json"
WORK = Path(__file__).resolve().parent / "plan_check_tmp"
HEADER = "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
BRANCH_0 = "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
BRANCH_30 = "30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"

# (таблица, регулярные выражения тестов шага 2; None — from_config не бросает)
CASES = {
    "one_row_middle": (HEADER + BRANCH_0 + "15.0,10000000,1.12,0.0022\n" + BRANCH_30,
                       [r"R_s = 15 м³ст/м³ст из одной строки \(p = 10 МПа\)", r"^oil_pvt\.csv:"]),
    "one_row_last": (HEADER + BRANCH_0 + "30.0,15000000,1.20,0.0015\n",
                     [r"R_s = 30 м³ст/м³ст из одной строки"]),
    "repeated_pressure": (HEADER + BRANCH_0 + ("30.0,15000000,1.20,0.0015\n30.0,20000000,1.19,0.00152\n"
                                               "30.0,20000000,1.185,0.00153\n30.0,30000000,1.18,0.0016\n"),
                          ["не растёт строго", re.escape("20 МПа после 20 МПа (строки 2 и 3 ветви)")]),
    "out_of_order": (HEADER + BRANCH_0 + ("30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"
                                          "30.0,20000000,1.19,0.00152\n"),
                     [r"20 МПа после 30 МПа \(строки 2 и 3 ветви\)"]),
    "rs_typo": (HEADER + BRANCH_0 + ("30.0,15000000,1.20,0.0015\n30.01,22000000,1.19,0.00155\n"
                                     "30.0,30000000,1.18,0.0016\n"),
                [r"R_s = 30\.01 м³ст/м³ст из одной строки"]),
    "empty": (HEADER, ["oil_pvt.csv: нет ни одной числовой строки"]),
    "bubble_point_order": (HEADER + BRANCH_0 + "15.0,20000000,1.12,0.0022\n15.0,30000000,1.11,0.0023\n"
                           + BRANCH_30,
                           ["давление насыщения не растёт с R_s",
                            re.escape("p_b = 15 МПа у ветви R_s = 30"),
                            re.escape("p_b = 20 МПа у ветви R_s = 15")]),
    "interleaved": (HEADER + ("0.0,5000000,1.05,0.003\n30.0,15000000,1.20,0.0015\n"
                              "0.0,30000000,1.04,0.0032\n30.0,30000000,1.18,0.0016\n"), None),
}

WORK.mkdir(exist_ok=True)
for name in ("gas_pvt.csv", "relperm.csv"):
    shutil.copy(TABLE_CONFIG.parent / name, WORK / name)
ok = True
for case, (text, patterns) in CASES.items():
    (WORK / "oil_pvt.csv").write_text(text, encoding="utf-8")
    config = load_config(TABLE_CONFIG)
    config.config_dir = WORK
    try:
        factory.SimulatorFactory.from_config(config)
        msg = None
    except ValueError as e:
        msg = str(e)
    if patterns is None:
        good = msg is None
    else:
        good = msg is not None and all(re.search(p, msg) for p in patterns)
    ok &= good
    print(f"{'OK ' if good else 'BAD'} {case:18s} {msg}")
shutil.rmtree(WORK)

# Все таблицы проекта проходят проверку
n = 0
for f in sorted(SOLVER.glob("**/oil_pvt*.csv")):
    if ".venv" in f.parts:
        continue
    _check_pvto_branches(_original_reader(f), f.name)
    n += 1
print(f"таблиц проекта прошли проверку: {n}")
print("ИТОГ:", "все случаи как в плане" if ok else "РАСХОЖДЕНИЕ")
