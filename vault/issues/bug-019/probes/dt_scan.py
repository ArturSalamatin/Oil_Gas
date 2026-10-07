"""BUG-019, T7б: исход шага из состояния на 1 сут в зависимости от Δt и вырожденные Δt.

compressibility.py нашёл: в 40 ячейках (i = 308…347) полная сжимаемость c_t < 0,
и J(z_old, Δt) = A/Δt + B вырождается на последовательности Δt (…, 167.6, 211.5, 277.4,
382, 561.8, 909.1, 1712, 4300, 24380 с). Проверка: на сетке Δt от 10 с до 1 сут —
исход исходного алгоритма (Ньютон с фиксированным набором фаз) и полного advance
(все три ступени); расстояние до ближайшего вырожденного Δt.

Попутно (к гипотезе (в) и DEBT-033): поэлементная погрешность конечно-разностного
якобиана — grouped (вперёд) против центральной разности, в z_old и z*.

Запуск (из numerical_solver), после freeze.py:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-019\\probes\\dt_scan.py
"""

import numpy as np
from scipy.linalg import eig

import common as c
from common import jac_central

model, cfg = c.make_model()
st = c.load_state()
n = model.grid.n
mask = st.gas_active.copy()
z_old = model.pack(st, mask)

# ── Вырожденные Δt в z_old (как в compressibility.py, п. 3) ──
J1, _ = model.finite_difference_jacobian(z_old, st, c.DT_FAIL, mask)
J2, _ = model.finite_difference_jacobian(z_old, st, c.DT_OK, mask)
A = (J1 - J2) / (1 / c.DT_FAIL - 1 / c.DT_OK)
B = J1 - A / c.DT_FAIL
lam = eig(A, -B, right=False)
sing = np.sort(lam[np.isfinite(lam) & (np.abs(lam.imag) <= 1e-6 * np.abs(lam.real)) & (lam.real > 0)].real)
# Значения ~1e18 — численная бесконечность: B (Δt → ∞) вырожден, потому что потоки
# не зависят от S_g ячеек ниже S_gc (k_ro = 1 и k_rg = 0 на полке таблицы).
print(f"собственных значений > 1e12 с (бесконечность): {int(np.sum(sing > 1e12))}")
sing = sing[sing < 1e12]
print(f"наибольшее конечное вырожденное Δt: {sing.max():.4g} с")


def dist(dt):
    """Логарифмическое расстояние до ближайшего вырожденного Δt, в долях соседнего интервала."""
    k = np.searchsorted(sing, dt)
    lo = sing[k - 1] if k > 0 else None
    hi = sing[k] if k < sing.size else None
    if lo is None or hi is None:
        return np.nan, (lo if hi is None else hi)
    near = lo if np.log(dt / lo) < np.log(hi / dt) else hi
    return float(min(np.log(dt / lo), np.log(hi / dt)) / np.log(hi / lo)), near


# ── Сетка Δt ──
dts = np.unique(np.concatenate([np.geomspace(10.0, c.DAY, 81), [c.DAY / 2 ** m for m in range(10)]]))
rows = []
for dt in dts:
    r = c.trace_newton(model, st, dt)
    new, rep = model.advance(st.copy(), dt)
    d, near = dist(dt)
    rows.append((dt, r["outcome"], r["rep"].iterations, r["rep"].residual_inf, rep.converged,
                 bool(getattr(rep, "fallback", False)), bool(getattr(rep, "globalized", False)), d, near))

print("Δt — шаг; d — расстояние до ближайшего вырожденного Δt в долях интервала между соседними (0 — на нём, 0.5 — посередине)")
print(f"{'Δt, с':>10} {'исходный алгоритм':>26} {'||F||∞':>10} {'advance':>14} {'d':>6} {'ближайшее':>10}")
for dt, out, it, res, conv, fb, gl, d, near in rows:
    stage = ("3-я ступень" if gl else "запасной" if fb else "исходный") if conv else "ОТКАЗ"
    mark = " ← A-retry" if np.any(np.isclose(dt, [c.DAY / 2 ** m for m in range(10)])) else ""
    print(f"{dt:10.2f} {out + f' ({it})':>26} {res:10.2e} {stage:>14} {d:6.3f} {near:10.4g}{mark}")

# Сводка: доля отказов в зависимости от d
small = np.array([r[0] for r in rows]) < sing.max()
d_arr = np.array([r[7] for r in rows])
ok_orig = np.array([r[1] == "сошёлся" for r in rows])
ok_adv = np.array([r[4] for r in rows])
for lo, hi in ((0, 0.1), (0.1, 0.25), (0.25, 0.5)):
    sel = small & (d_arr >= lo) & (d_arr < hi + 1e-12)
    print(f"Δt < {sing.max():.4g} с, d ∈ [{lo}, {hi}]: шагов {int(sel.sum())}, сошлось: исходный {int(ok_orig[sel].sum())}, "
          f"advance {int(ok_adv[sel].sum())}")
sel = ~small
print(f"Δt ≥ {sing.max():.4g} с: шагов {int(sel.sum())}, сошлось: исходный {int(ok_orig[sel].sum())}, advance {int(ok_adv[sel].sum())}")

# ── Поэлементная погрешность якобиана (к гипотезе (в)) ──
r_fail = c.trace_newton(model, st, c.DT_FAIL)
print("\nПоэлементно: grouped (разность вперёд) против центральной разности")
for name, z, J in (("z_old", z_old, J1), ("z*", r_fail["its"][-1]["z"], r_fail["its"][-1]["J"])):
    Jc = jac_central(model, st, mask, z, c.DT_FAIL)
    for bn, sl in (("pp", np.s_[:n, :n]), ("pX", np.s_[:n, n:]), ("Xp", np.s_[n:, :n]), ("XX", np.s_[n:, n:])):
        d = np.abs(J[sl] - Jc[sl])
        big = np.abs(Jc[sl]) > 1e-6 * np.max(np.abs(Jc[sl]))
        print(f"  {name} {bn}: max|ΔJ|/max|J| = {d.max() / np.max(np.abs(Jc[sl])):.2e}; "
              f"max относит. по значимым элементам = {np.max(d[big] / np.abs(Jc[sl][big])):.2e}")

# ── График ──
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

fig, ax = plt.subplots(figsize=(9, 3.6))
for s in sing[(sing > 5) & (sing < 2e5)]:
    ax.axvline(s, color="0.75", lw=0.8)
for dt, out, *_ in rows:
    ax.plot(dt, 1, "o", color="C2" if out == "сошёлся" else "C3", ms=5)
for dt, _, _, _, conv, *_ in rows:
    ax.plot(dt, 0, "s", color="C2" if conv else "C3", ms=5)
ax.set_xscale("log")
ax.set_yticks([0, 1], ["advance\n(3 ступени)", "исходный\nалгоритм"])
ax.set_ylim(-0.6, 1.6)
ax.set_xlabel("Δt, с (серые линии — Δt, при которых J(z_old) вырожден)")
ax.set_title("Шаг из состояния на 1 сут: зелёный — сошёлся, красный — отказ", fontsize=10)
fig.tight_layout()
fig.savefig(c.HERE / "dt_scan.png", dpi=130)
print("\nграфик: dt_scan.png")
