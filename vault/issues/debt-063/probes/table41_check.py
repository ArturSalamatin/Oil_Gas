"""DEBT-063, аудит: строки «Было» таблицы 4.1 плана — ровно одна в файле; «Станет» — нет.

Пары (файл, было, станет) переписаны из таблицы 4.1 плана (в файле —
«|», не «\\|»). Для таблиц из нескольких правок в одной строке — по
паре на правку. Перед реализацией: «было» найдено 1 раз, «станет» — 0
раз (иначе Edit не найдёт или заменит не то). После шага 4 — наоборот:
`python table41_check.py after`.

Запуск из numerical_solver/:  python ..\\vault\\issues\\debt-063\\probes\\table41_check.py [after]
"""
import sys
from pathlib import Path

SOLVER = Path.cwd()
EX = SOLVER / "examples"
AFTER = sys.argv[1:] == ["after"]

PAIRS = [
    ("03_standing_corey/README.md", "**0.1979 м**", "**0.1978 м**"),
    ("03_standing_corey/README.md", "8.00 кПа (0.067 % депрессии)", "7.45 кПа (0.062 % депрессии)"),
    ("03_standing_corey/README.md", "| $S_g^{max}$ | 0.08151 |", "| $S_g^{max}$ | 0.08152 |"),
    ("03_standing_corey/README.md", "| 0.1971 | 0.1979 | 0.4 % |", "| 0.1971 | 0.1978 | 0.4 % |"),
    ("03_standing_corey/README.md", r"= 0.1979\ \text{м}", r"= 0.1978\ \text{м}"),
    ("03_standing_corey/README.md", r"= 1.5\cdot10^{-8}\ \text{Па}", r"= 7.5\cdot10^{-9}\ \text{Па}"),
    ("03_standing_corey/README.md", r"$1.3\cdot10^{-8}$ | $2.3\cdot10^{-4}$ | 0.20214",
     r"$9.3\cdot10^{-9}$ | $2.3\cdot10^{-4}$ | 0.20008"),
    ("03_standing_corey/README.md", "| 0.19957 |", "| 0.19905 |"),
    ("03_standing_corey/README.md", r"$7.4\cdot10^{-9}$ | $2.2\cdot10^{-3}$ | 0.19824",
     r"$1.7\cdot10^{-8}$ | $2.2\cdot10^{-3}$ | 0.19811"),
    ("03_standing_corey/README.md", r"$1.5\cdot10^{-8}$ | $1.8\cdot10^{-3}$ | 0.19790",
     r"$7.5\cdot10^{-9}$ | $1.8\cdot10^{-3}$ | 0.19785"),
    ("03_standing_corey/README.md", r"$7.4\cdot10^{-9}$ | $2.4\cdot10^{-3}$ | 0.19772",
     r"$1.3\cdot10^{-8}$ | $2.4\cdot10^{-3}$ | 0.19769"),
    ("03_standing_corey/README.md", "$r_b$, $q_o$ и $T(r_w)$ сходятся монотонно, первым порядком:",
     "$r_b$, $q_o$ и $T(r_w)$ сходятся монотонно, первым порядком (у $r_b$ — с $N = 50$: "
     "приращения 0.00094 и 0.00042 м при удвоениях; на паре 25 → 50 — 0.00103 м):"),
    ("04_table_table/README.md", "**2.637 м**", "**2.630 м**"),
    ("04_table_table/README.md", "27.95 кПа (0.233 % депрессии)", "23.58 кПа (0.197 % депрессии)"),
    ("04_table_table/README.md", "| $S_g^{max}$ | 0.01468 |", "| $S_g^{max}$ | 0.01470 |"),
    ("04_table_table/README.md", "| 2.594 | 2.637 | 1.7 % |", "| 2.594 | 2.630 | 1.4 % |"),
    ("04_table_table/README.md", "| 63.9 | 2.694 | 351.4966 |", "| 46.3 | 2.666 | 351.4966 |"),
    ("04_table_table/README.md", "| 28.0 | 2.637 | 351.4915 |", "| 23.6 | 2.630 | 351.4915 |"),
    ("04_table_table/README.md", "| 13.1 | 2.614 | 351.4888 |", "| 12.0 | 2.612 | 351.4884 |"),
    ("04_table_table/README.md", "| 8.5 | 2.606 | 351.4877 |", "| 8.0 | 2.606 | 351.4872 |"),
    ("04_table_table/README.md", "0.0051 и 0.0027 К при удвоениях", "0.0051 и 0.0031 К при удвоениях"),
    # Докстринг: столбец «макс|dp|» таблицы ряда (выравнивание сохраняется)
    ("04_table_table/grid_convergence.py", "0.878 %                     63.9",
     "0.878 %                     46.3"),
    ("04_table_table/grid_convergence.py", "1.96         28.0", "1.96         23.6"),
    ("04_table_table/grid_convergence.py", "1.98         13.1", "1.98         12.0"),
    ("04_table_table/grid_convergence.py", "1.50          8.5", "1.50          8.0"),
    ("04_table_table/grid_convergence.py", "(2.694 -> 2.637 -> 2.614 ->", "(2.666 -> 2.630 -> 2.612 ->"),
    ("04_table_table/grid_convergence.py", "приращения 0.0051 и 0.0027 К при", "приращения 0.0051 и 0.0031 К при"),
    ("04_table_table/grid_convergence.py", "замер 2026-09-29", "замер 2026-10-11, DEBT-063"),
    ("04a_high_gas_saturation/README.md", "1.508 м расчёт", "1.507 м расчёт"),
    ("04a_high_gas_saturation/README.md", "35.9 кПа (0.224 % депрессии)", "35.0 кПа (0.218 % депрессии)"),
    ("04a_high_gas_saturation/README.md", "| 1.476 | 1.508 | 2.1 % |", "| 1.476 | 1.507 | 2.1 % |"),
    ("05_standing_table_rp/README.md", "| 0.2039 м |", "| 0.2034 м |"),
    ("05_standing_table_rp/README.md", "0.20390 м vs 0.20390 м (0.00 %)", "0.20337 м vs 0.20337 м (0.00 %)"),
    ("05_standing_table_rp/README.md", r"= 3.7\times10^{-9}$ Па", r"= 1.3\times10^{-8}$ Па"),
    ("05_standing_table_rp/README.md", r"отн. разность $2.3\times10^{-15}$", r"отн. разность $9.7\times10^{-16}$"),
    ("05_standing_table_rp/closed_form_convergence.py", "по давлению —\n16 кПа.", "по давлению —\n11 кПа."),
    ("06_table_corey_rp/README.md", "| 2.49 м |", "| 2.48 м |"),
    ("07_degassing_adiabatic_only/README.md", "| фронт $r_b$ | 2.64 м |", "| фронт $r_b$ | 2.63 м |"),
    ("09_degassing_latent_heat/README.md", "| фронт $r_b$ | 2.64 м |", "| фронт $r_b$ | 2.63 м |"),
    ("09_degassing_latent_heat/README.md", "$r < r_b = 2.64$ м", "$r < r_b = 2.63$ м"),
    ("10_deep_degassing/README.md", "| $r_b$, м | 3.58 |", "| $r_b$, м | 3.57 |"),
    ("10_deep_degassing/README.md", "$r_b = 3.58$ м", "$r_b = 3.57$ м"),
    ("12_large_drainage_radius/README.md", "63 кПа (0.67 % депрессии)", "59 кПа (0.62 % депрессии)"),
    ("13a_pwf_ramp_down/README.md", "59.00 кПа (0.621 % депрессии 9.5 МПа)", "54.76 кПа (0.576 % депрессии 9.5 МПа)"),
    ("15_oil_rate_ramp_up/README.md", "463.97 кПа (5.21 % депрессии 8.9 МПа)", "458.12 кПа (5.14 % депрессии 8.9 МПа)"),
    ("README.md", "464 кПа (5.2 % депрессии)", "458 кПа (5.1 % депрессии)"),
    ("README.md", "фронт — 0.20 против 2.64 м", "фронт — 0.20 против 2.63 м"),
    ("02_single_phase_jt/README.md", "| 0.0036 К | 0.0034 К | 0.0032 К |", "| 0.0035 К | 0.0033 К | 0.0031 К |"),
    ("11_degassing_at_boundary/README.md", "$r_{N-1} = 47.11$ м", "$r_{N-1} = 46.99$ м"),
    ("12_large_drainage_radius/README.md", "центр 186.08 м", "центр 185.36 м"),
    ("13a_pwf_ramp_down/README.md", "центр 186.08 м", "центр 185.36 м"),
    ("13b_pwf_alternating/README.md", "центр 186.08 м", "центр 185.36 м"),
    ("15_oil_rate_ramp_up/README.md", "центр 186.08 м", "центр 185.36 м"),
    ("16_well_shut_in/README.md", "центр 186.08 м", "центр 185.36 м"),
    ("12_large_drainage_radius/README.md", "(117.9 м)", "(117.5 м)"),
    ("12_large_drainage_radius/README.md",
     "Ячейка с центром 117.9 м лежит сразу за стационарным фронтом (117.6 м).",
     "Ячейка с центром 117.5 м лежит у стационарного фронта (117.6 м), в 0.1 м внутри него."),
    ("12_large_drainage_radius/README.md", "ячейка\nза фронтом попадает", "ячейка\nу фронта попадает"),
    ("13a_pwf_ramp_down/README.md", "до 117.9 м (14.5 сут)", "до 117.5 м (14.5 сут)"),
    ("13b_pwf_alternating/README.md", "от 0.9 до 75 м", "от 0.9 до 74 м"),
    ("13b_pwf_alternating/README.md", "0.9–75 м", "0.9–74 м"),
    ("README.md", "0.9–75 м нефть недонасыщена", "0.9–74 м нефть недонасыщена"),
    ("../tests/test_examples.py", "ячейки (186.08 м) лежит", "ячейки (185.36 м) лежит"),
    ("../tests/test_examples.py", "30 ячеек на 0.9-75 м", "30 ячеек на 0.9-74 м"),
    ("12_large_drainage_radius/README.md", r"$7.6\cdot10^{-16}$; кондуктивный член",
     r"$4.5\cdot10^{-17}$; кондуктивный член"),
    ("12_large_drainage_radius/README.md", r"$E_{конд} = +6.16\cdot10^{6}$ Дж.", r"$E_{конд} = +5.85\cdot10^{6}$ Дж."),
    ("13a_pwf_ramp_down/README.md", r"$4.1\cdot10^{-16}$; кондуктивный член $E_{конд} = +3.63\cdot10^{6}$ Дж.",
     r"$1.0\cdot10^{-16}$; кондуктивный член $E_{конд} = +3.45\cdot10^{6}$ Дж."),
    ("13b_pwf_alternating/README.md", r"| $-3.0636\cdot10^{10}$ |", r"| $-3.0637\cdot10^{10}$ |"),
    ("13b_pwf_alternating/README.md", r"| $+9.17\cdot10^{6}$ |", r"| $+8.70\cdot10^{6}$ |"),
    ("14_high_gor_cooling/README.md", r"$1.8\cdot10^{-17}$", r"$2.9\cdot10^{-16}$"),
    ("14_high_gor_cooling/README.md", r"$-9.98\cdot10^{8}$", r"$-9.92\cdot10^{8}$"),
    ("15_oil_rate_ramp_up/README.md", r"$5.4\cdot10^{-16}$", r"$1.6\cdot10^{-16}$"),
    ("16_well_shut_in/README.md", r"| $+2.0\cdot10^{5}$ | $-6.3\cdot10^{5}$ |", r"| $+1.9\cdot10^{5}$ | $-6.0\cdot10^{5}$ |"),
    ("17_shut_in_strong_cooling/README.md", r"| $+5.7\cdot10^{5}$ | $-6.1\cdot10^{6}$ |",
     r"| $+5.7\cdot10^{5}$ | $-6.0\cdot10^{6}$ |"),
    ("18_prototype_input/README.md", r"$+5.1\cdot10^{6}$ Дж; невязка $3.6\cdot10^{-15}$",
     r"$+5.0\cdot10^{6}$ Дж; невязка $4.9\cdot10^{-15}$"),
    ("19_rs150_cooling/README.md", r"$+8.68\cdot10^{6}$", r"$+8.62\cdot10^{6}$"),
    ("20_rs300_cooling/README.md", r"$+8.7806\cdot10^{6}$", r"$+8.7306\cdot10^{6}$"),
    ("21_rs100_cooling/README.md", r"$+7.28\cdot10^{6}$", r"$+7.23\cdot10^{6}$"),
]
# Аудит 1: радиусы центров в столбцах таблиц («фронт, м», «газ до, м») —
# пары из table_radii_pairs.out.txt (подстрока «| соседняя | число |» или вся строка)
_RAW = (Path(__file__).resolve().parent / "table_radii_pairs.out.txt").read_text(
    encoding="utf-8-sig")             # выход записан через Tee-Object — с BOM
import ast  # noqa: E402
import warnings  # noqa: E402
with warnings.catch_warnings():       # «\cdot» в строках — не управляющая последовательность
    warnings.simplefilter("ignore", SyntaxWarning)
    _ITEMS = ast.literal_eval("[" + _RAW + "]")
for item in _ITEMS:
    rel, _n, was, becomes, _cnt = item
    PAIRS.append((rel, was, becomes))
# Сводная таблица баланса энергии: строка примера — «невязка | теплопроводность»
SUMMARY = {
    "10": (r"$5.7\cdot10^{-16}$ | $+1.36\cdot10^{6}$", r"$4.1\cdot10^{-16}$ | $+1.31\cdot10^{6}$"),
    "11": (r"$4.6\cdot10^{-17}$ | $+1.53\cdot10^{6}$", r"$9.1\cdot10^{-17}$ | $+1.47\cdot10^{6}$"),
    "12": (r"$7.6\cdot10^{-16}$ | $+6.16\cdot10^{6}$", r"$4.5\cdot10^{-17}$ | $+5.85\cdot10^{6}$"),
    "13a": (r"$4.1\cdot10^{-16}$ | $+3.63\cdot10^{6}$", r"$1.0\cdot10^{-16}$ | $+3.45\cdot10^{6}$"),
    "13b": (r"$1.4\cdot10^{-15}$ | $+9.17\cdot10^{6}$", r"$1.8\cdot10^{-15}$ | $+8.70\cdot10^{6}$"),
    "14": (r"$1.8\cdot10^{-17}$ | $-9.98\cdot10^{8}$", r"$2.9\cdot10^{-16}$ | $-9.92\cdot10^{8}$"),
    "15": (r"$5.4\cdot10^{-16}$ | $+3.03\cdot10^{6}$", r"$1.6\cdot10^{-16}$ | $+2.88\cdot10^{6}$"),
    "16": (r"$1.8\cdot10^{-15}$ | $+5.53\cdot10^{6}$", r"$4.4\cdot10^{-15}$ | $+5.25\cdot10^{6}$"),
    "17": (r"$3.4\cdot10^{-15}$ | $+6.86\cdot10^{6}$", r"$2.5\cdot10^{-15}$ | $+6.78\cdot10^{6}$"),
    "18": (r"$3.6\cdot10^{-15}$ | $+5.14\cdot10^{6}$", r"$4.9\cdot10^{-15}$ | $+5.02\cdot10^{6}$"),
    "19": (r"$5.0\cdot10^{-17}$ | $+8.68\cdot10^{6}$", r"0 | $+8.62\cdot10^{6}$"),
    "20": (r"$5.6\cdot10^{-17}$ | $+8.78\cdot10^{6}$", r"$5.6\cdot10^{-17}$ | $+8.73\cdot10^{6}$"),
    "21": (r"$4.5\cdot10^{-17}$ | $+7.28\cdot10^{6}$", r"$9.0\cdot10^{-17}$ | $+7.23\cdot10^{6}$"),
}

def summary_row(lines, ex):
    """Строка таблицы баланса энергии сводного README для примера ex."""
    # У примера есть и строки других таблиц («| **13b** | **60 с** |…»);
    # у этой — коэффициенты теплопроводности
    return [s for s in lines if s.startswith(f"| **{ex}** |")
            and ("1.5 / 0.14 / 0.04" in s or "2.5 / 0.13 / 0.05" in s)]


def main():
    bad = 0
    for rel, old, new in PAIRS:
        text = (EX / rel).read_text(encoding="utf-8")
        n_old, n_new = text.count(old), text.count(new)
        want_old, want_new = (0, 1) if AFTER else (1, 0)
        if (n_old, n_new) != (want_old, want_new):
            bad += 1
            print(f"! {rel}: «было» {n_old}×, «станет» {n_new}× — {old[:60]!r}")
    summary = (EX / "README.md").read_text(encoding="utf-8").splitlines()
    for ex, (old, new) in SUMMARY.items():
        rows = summary_row(summary, ex)
        ok = len(rows) == 1 and (new if AFTER else old) in rows[0]
        if not ok:
            bad += 1
            print(f"! README.md, сводная таблица, {ex}: строк {len(rows)}; {rows[:1]}")
    print(f"пар: {len(PAIRS)} + строк сводной таблицы: {len(SUMMARY)}; нарушений: {bad} "
          f"({'после' if AFTER else 'до'} шага 4)")


if __name__ == "__main__":
    main()
