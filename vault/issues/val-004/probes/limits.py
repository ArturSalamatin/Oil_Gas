"""VAL-004 (планирование): порядок по Рунге и пределы Ричардсона по сохранённым профилям dt_series.py.

Читает npz рядом со скриптом (их пишет dt_series.py; в git не идут):
    dt_series_W1h_k0-9.npz, dt_series_W1h_k10-12.npz  — 1 ч, равномерно 3600/2**k
    dt_series_W1h_k0-5_g9.npz, dt_series_W1h_k4-6_g9.npz — 1 ч, нарастающие шаги
    dt_series_W24h_k0-5.npz, dt_series_W24h_k0-4_g9.npz — сутки
Запуск из numerical_solver/: .venv\\Scripts\\python ..\\vault\\issues\\val-004\\probes\\limits.py
"""

from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BAR = 1e5
UNIT = {"p": "бар", "T": "К", "Rs": "м³/м³"}
SCALE = {"p": BAR, "T": 1.0, "Rs": 1.0}


def series(files, mark):
    """{k: {поле: профиль}} на отметке mark ('1h' или 'W') из нескольких npz."""
    out = {}
    for name in files:
        z = np.load(HERE / name)
        for key in z.files:
            k, rest = key.split("_", 1)
            if rest.startswith(mark + "_"):
                out.setdefault(int(k[1:]), {})[rest[len(mark) + 1:]] = z[key]
    return out


def runge(u):
    """Порядок q = log2((u1-u0)/(u2-u1)) и пределы Ричардсона при q и при q = 1."""
    d1, d2 = u[1] - u[0], u[2] - u[1]
    q = np.log2(d1 / d2) if d1 * d2 > 0 else float("nan")
    lim_q = u[2] + d2 / (2 ** q - 1) if np.isfinite(q) else float("nan")
    return q, lim_q, u[2] + d2


def main():
    uni = series(["dt_series_W1h_k0-9.npz", "dt_series_W1h_k10-12.npz"], "1h")
    grd = series(["dt_series_W1h_k0-5_g9.npz", "dt_series_W1h_k4-6_g9.npz"], "1h")
    lim = {}
    for f in ("p", "T", "Rs"):
        sc = SCALE[f]
        print(f"=== {f}(r_w) на 1 ч останова, {UNIT[f]}")
        u = {k: uni[k][f][0] / sc for k in sorted(uni)}
        for k in sorted(u):
            tail = ""
            if k >= 2:
                q, _, _ = runge([u[k - 2], u[k - 1], u[k]])
                tail = f"  q(k={k - 2}..{k}) = {q:.4f}"
            print(f"  равномерно k={k:2d} h={3600 / 2 ** k:9.4f} с: {u[k]:.7f}{tail}")
        q, lq, l1 = runge([u[10], u[11], u[12]])
        print(f"  предел по k=10..12: q = {q:.4f}, при q: {lq:.7f}, при q = 1: {l1:.7f}")
        g = {k: grd[k][f][0] / sc for k in sorted(grd)}
        for k in sorted(g):
            print(f"  нарастающие k={k}: {g[k]:.7f}")
        qg, lqg, l1g = runge([g[4], g[5], g[6]])
        print(f"  предел по нарастающим k=4..6: q = {qg:.4f}, при q: {lqg:.7f}, при q = 1: {l1g:.7f}")
        print(f"  расхождение пределов (q = 1): {l1g - l1:+.2e}; при измеренных q: {lqg - lq:+.2e}")
        ref = lqg if f == "Rs" else l1   # R_s: равномерная серия не сходится — предел по нарастающим
        lim[f] = ref
        print(f"  ошибка одного шага 3600 с: {u[0] - ref:+.4f}; шага 7 с: {u[9] - ref:+.4f}; "
              f"нарастающих k=4: {g[4] - ref:+.4f}")
    # Профили: max-норма разностей соседних сгущений (сетка одна — без интерполяции)
    print("=== профили, max|u_k - u_(k+1)| и порядок")
    for name, d, ks in (("равномерно", uni, range(9, 13)), ("нарастающие", grd, range(4, 7))):
        for f in ("p", "T", "Sg", "Rs"):
            ks = list(ks)
            dd = [np.max(np.abs(d[ks[i + 1]][f] - d[ks[i]][f])) / SCALE.get(f, 1.0)
                  for i in range(len(ks) - 1)]
            qs = [np.log2(dd[i] / dd[i + 1]) for i in range(len(dd) - 1)]
            print(f"  {name:11s} {f:2s}: " + ", ".join(f"{x:.3e}" for x in dd)
                  + " | q: " + ", ".join(f"{x:.3f}" for x in qs))
    # Сутки: серии с дроблением (фактические шаги неравномерны) — только оценка
    u24 = series(["dt_series_W24h_k0-5.npz"], "W")
    g24 = series(["dt_series_W24h_k0-4_g9.npz"], "W")
    print("=== сутки останова (оценка; шаги дробились — см. *.out.txt)")
    for f in ("p", "T"):
        sc = SCALE[f]
        a = [u24[k][f][0] / sc for k in sorted(u24)]
        b = [g24[k][f][0] / sc for k in sorted(g24)]
        print(f"  {f}: равномерно " + ", ".join(f"{x:.4f}" for x in a))
        print(f"  {f}: нарастающие " + ", ".join(f"{x:.4f}" for x in b))
    p_lim24 = 2 * u24[5]["p"][0] / BAR - u24[4]["p"][0] / BAR
    print(f"  p(24 ч): предел по равномерным k=4,5 при q = 1 — {p_lim24:.4f} бар; "
          f"ошибка практики (k=0) {u24[0]['p'][0] / BAR - p_lim24:+.4f} бар")
    t_lim24 = g24[4]["T"][0]
    print(f"  T(24 ч): нарастающие k=4 — {t_lim24:.4f} К (последнее приращение 0.0012 К); "
          f"ошибка практики (k=0) {u24[0]['T'][0] - t_lim24:+.4f} К (оценка снизу по модулю)")


if __name__ == "__main__":
    main()
