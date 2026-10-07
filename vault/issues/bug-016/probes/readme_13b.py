"""BUG-016: таблица «по записям» README 13b — до и после правки, в печатаемых знаках.

Истории — regress/<метка>/13b_pwf_alternating.npz (запись каждые 0.5 сут).
Колонки как в README 13b: q_o, GOR, T(r_w), S_g(r_w), p у забоя, двухфазных
(S_g > 0), недонасыщенных (S_g = 0 и p < p_b, p_b = 15 МПа).

Запуск: python <этот файл> <метка до> <метка после>
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PB = 15.0e6
DAYS = (0.5, 1, 1.5, 2, 5, 7.5, 10, 15, 20, 25, 29, 29.5, 30)


def rows(label):
    d = np.load(HERE / "regress" / label / "13b_pwf_alternating.npz")
    out = {}
    for day in DAYS:
        k = int(round(day * 2))
        sg, p = d["Sg"][k], d["p"][k]
        q_o, q_g = d["q_o"][k], d["q_g"][k]
        out[day] = (f"{q_o:.4e}", f"{q_g / q_o:.2f}", f"{d['T'][k][0]:.3f}", f"{sg[0]:.4f}",
                    f"{p[0] / 1e6:.4f}", str(int((sg > 0).sum())),
                    str(int(((sg == 0) & (p < PB)).sum())))
    return out


def text_numbers(label):
    """Числа из текста README 13b (разделы «Что происходит при переключении»)."""
    d = np.load(HERE / "regress" / label / "13b_pwf_alternating.npz")
    T, p, sg, q_o, q_g, p_wf = d["T"][:, 0], d["p"], d["Sg"], d["q_o"], d["q_g"], d["p_wf"]
    t = np.arange(len(T)) * 0.5               # сут, запись каждые 0.5 сут
    gor = np.where(q_o > 0, q_g / np.where(q_o > 0, q_o, 1.0), np.nan)
    hi = np.isclose(p_wf, 10.75e6)            # записи на сутках при 10.75 МПа
    lo = np.isclose(p_wf, 6.0e6)
    unders = ((sg == 0) & (p < PB)).sum(axis=1)
    ends_hi = [k for k in range(2, len(T), 2) if hi[k]]    # концы суток 10.75
    ends_lo = [k for k in range(2, len(T), 2) if lo[k]]
    k75 = int(7.5 * 2)
    return {
        "q_o 1-е сут (0.5 → 1), 1e-3": f"{q_o[1] * 1e3:.2f} → {q_o[2] * 1e3:.2f}",
        "q_o 2-е сут (1.5 → 2), 1e-3": f"{q_o[3] * 1e3:.2f} → {q_o[4] * 1e3:.2f}",
        "p[0] − p_wf 2-е сут, кПа": f"{(p[3, 0] - p_wf[3]) / 1e3:.0f} → {(p[4, 0] - p_wf[4]) / 1e3:.0f}",
        "недонас. на концах суток 10.75 (сут: n)": " ".join(
            f"{t[k]:g}:{unders[k]}" for k in ends_hi),
        "недонас. на концах суток 6 (max)": str(int(max(unders[k] for k in ends_lo))),
        "GOR при 10.75 с 7.5 сут (min–max)": "{:.1f}–{:.1f}".format(
            np.nanmin(gor[k75:][hi[k75:]]), np.nanmax(gor[k75:][hi[k75:]])),
        "GOR при 6: 0.5 сут → 29 сут": f"{gor[1]:.1f} → {gor[58]:.1f}",
        "T концы суток 6: 1 → 29 сут": f"{T[2]:.3f} → {T[58]:.3f}",
        "T концы суток 10.75: 2 → 30 сут": f"{T[4]:.3f} → {T[60]:.3f}",
        "T min (сут)": f"{T[1:].min():.3f} ({t[1:][np.argmin(T[1:])]:g})",
        "T max (сут)": f"{T[1:].max():.3f} ({t[1:][np.argmax(T[1:])]:g})",
        "30 сут: p[0] МПа, R_s(r_w), q_g": f"{p[60, 0] / 1e6:.3f}, {d['Rs'][60, 0]:.3f}, {q_g[60]:.5f}",
    }


a, b = rows(sys.argv[1]), rows(sys.argv[2])
cols = ("q_o", "GOR", "T(r_w)", "S_g(r_w)", "p забоя", "двухф.", "недонас.")
changed = 0
for day in DAYS:
    diff = [f"{c}: {x} → {y}" for c, x, y in zip(cols, a[day], b[day]) if x != y]
    if diff:
        changed += 1
        print(f"сут {day:>4}: " + "; ".join(diff))
print(f"строк с изменениями: {changed} из {len(DAYS)}")

print("\nЧисла текста README 13b (до | после):")
ta, tb = text_numbers(sys.argv[1]), text_numbers(sys.argv[2])
for k in ta:
    mark = "   " if ta[k] == tb[k] else ">> "
    print(f"{mark}{k}: {ta[k]} | {tb[k]}")
