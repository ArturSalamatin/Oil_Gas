"""BUG-019, T7: не обращается ли в ноль полная сжимаемость двухфазной ячейки.

Повод — T2 (diagnose.txt): в z* невязка гладкая вдоль dz (e ∝ ε на 5 декадах),
но кривизна огромна (e(1) = 1.5e4), cond(J) после выравнивания в 400 раз хуже,
чем при 337.5 с; невязка максимальна в ячейках с S_g ≈ 0.1 при p ≈ 400 бар.

Гипотеза. Блок накопления ячейки A_i = ∂(запас нефти, запас газа)/∂(p, S_g)
имеет det A_i ∝ c_t — полной сжимаемости:
    c_t = (1 − S_g)·c_o,sat + S_g·c_g + c_r,
    c_o,sat = (B_g·dR_s/dp − dB_o/dp)/B_o   (насыщенная нефть с выделяющимся газом),
    c_g = −(1/B_g)·dB_g/dp = 1/p (идеальный газ), c_r = 0 в конфиге.
Если B_g·dR_s/dp < dB_o/dp (Стендинг при высоких R_s и p), c_o,sat < 0 и при малой
S_g c_t ≤ 0: уравнение для давления теряет «ёмкость», J = A/Δt + B вырождается при
отдельных Δt — тогда исход шага немонотонно зависит от Δt.

Что считается:
1. c_o,sat(p) по PVT модели прототипа; давление p*, где c_o,sat = 0.
2. c_t и det A_i по ячейкам в z_old и z*; где c_t ≤ 0.
3. Δt, при которых J(z, Δt) = A/Δt + B вырожден: обобщённые собственные значения
   пучка (A, −B), A и B — из J при двух Δt в одной точке z.
4. Наименьший сингулярный вектор J в z* при 168.75 с — в каких ячейках сосредоточен.

Запуск (из numerical_solver), после freeze.py:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-019\\probes\\compressibility.py
"""

import numpy as np
from scipy.linalg import eig

import common as c

model, cfg = c.make_model()
st = c.load_state()
n = model.grid.n
mask = st.gas_active.copy()
pvt = model.pvt
r_fail = c.trace_newton(model, st, c.DT_FAIL)
z_old = model.pack(st, mask)
z_star = r_fail["its"][-1]["z"]
J_old_fail = r_fail["its"][0]["J"]
print(f"c_r в конфиге: {cfg.rock.compressibility} 1/Па; S_gc = {cfg.relperm.S_gc}")


# ── 1. c_o,sat(p) ──
def c_o_sat(p_bar, h=1e-3):
    """Сжимаемость насыщенной нефти с выделяющимся газом, 1/бар (минус = объём растёт при росте p)."""
    p = np.asarray(p_bar, float)
    rs = pvt.rs_sat(p)
    drs = (pvt.rs_sat(p + h) - pvt.rs_sat(p - h)) / (2 * h)
    dbo = (pvt.bo(p + h, pvt.rs_sat(p + h)) - pvt.bo(p - h, pvt.rs_sat(p - h))) / (2 * h)
    return (pvt.bg(p) * drs - dbo) / pvt.bo(p, rs)


def c_g(p_bar, h=1e-3):
    p = np.asarray(p_bar, float)
    return -(pvt.bg(p + h) - pvt.bg(p - h)) / (2 * h) / pvt.bg(p)


print("\n═══ 1. Сжимаемость насыщенной нефти по PVT (Стендинг, идеальный газ) ═══")
p_scan = np.linspace(10.0, 469.0, 4591)
co = c_o_sat(p_scan)
neg = p_scan[co < 0]
p_star = float(neg.min()) if neg.size else None
print(f"  c_o,sat < 0 при p ≥ {p_star:.1f} бар" if p_star else "  c_o,sat > 0 на всём диапазоне")
for p in (50, 100, 200, 300, 350, 400, 430, 450, 463.8):
    rs = float(pvt.rs_sat(np.array([p]))[0])
    print(f"  p = {p:6.1f} бар: R_s = {rs:6.1f}, B_o = {float(pvt.bo(np.array([p]), np.array([rs]))[0]):.4f}, "
          f"B_g = {float(pvt.bg(np.array([p]))[0]):.3e}, c_o,sat = {float(c_o_sat(np.array([p]))[0]):+.3e} 1/бар, "
          f"c_g = {float(c_g(np.array([p]))[0]):.3e} 1/бар")


# ── 2. c_t и det A_i по ячейкам ──
def accum_blocks(z):
    """A_i = ∂(запас нефти, запас газа / gas_residual_scale)/∂(p_i, X_i) — центральная разность."""
    det = np.empty(n)
    for i in range(n):
        Ab = np.empty((2, 2))
        for col, j in enumerate((i, n + i)):
            h = 1e-4 if col == 0 else (1e-7 if mask[i] else 1e-5)
            zp, zm = z.copy(), z.copy()
            zp[j] += h; zm[j] -= h
            op, gp = model.component_inventories(model.unpack(zp, mask))
            om, gm = model.component_inventories(model.unpack(zm, mask))
            Ab[0, col] = (op[i] - om[i]) / (2 * h)
            Ab[1, col] = (gp[i] - gm[i]) / (2 * h) / model.gas_residual_scale
        det[i] = np.linalg.det(Ab)
    return det


def c_t_cells(z):
    p, sg = z[:n], np.where(mask, z[n:], 0.0)
    return np.where(mask, (1 - sg) * c_o_sat(p) + sg * c_g(p), np.nan)


print("\n═══ 2. Полная сжимаемость по ячейкам ═══")
r_c = model.grid.centers_m
for name, z in (("z_old", z_old), ("z*", z_star)):
    ct = c_t_cells(z)
    det = accum_blocks(z)
    bad = np.where(mask & (ct <= 0))[0]
    agree = np.all(np.sign(det[mask]) == np.sign(ct[mask]))
    print(f"  {name}: c_t ≤ 0 в {bad.size} из {int(mask.sum())} двухфазных ячеек"
          + (f" (i = {bad.min()}…{bad.max()}, r = {r_c[bad.min()]:.1f}…{r_c[bad.max()]:.1f} м)" if bad.size else "")
          + f"; знак det A_i совпадает со знаком c_t: {agree}")
    sgn = np.sign(ct)
    flips = np.where(mask[:-1] & mask[1:] & (sgn[:-1] != sgn[1:]))[0]
    for i in flips:
        print(f"    смена знака c_t между i = {i} и {i + 1}: S_g {z[n + i]:.4f} → {z[n + i + 1]:.4f}, "
              f"p {z[i]:.2f} → {z[i + 1]:.2f} бар")
print(f"\n  {'i':>4} {'r, м':>8} {'S_g old':>8} {'p old':>8} {'c_t old':>10} {'S_g *':>8} {'p *':>8} {'c_t *':>10}")
ct_o, ct_s = c_t_cells(z_old), c_t_cells(z_star)
for i in list(range(286, 336, 2)) + list(range(336, n)):
    print(f"  {i:4d} {r_c[i]:8.2f} {z_old[n + i]:8.4f} {z_old[i]:8.2f} {ct_o[i]:+10.2e} "
          f"{z_star[n + i]:8.4f} {z_star[i]:8.2f} {ct_s[i]:+10.2e}")


# ── 3. Δt, при которых J = A/Δt + B вырожден ──
def pencil(z, J1, dt1, dt2):
    J2, _ = model.finite_difference_jacobian(z, st, dt2, mask)
    A = (J1 - J2) / (1 / dt1 - 1 / dt2)
    B = J1 - A / dt1
    lam = eig(A, -B, right=False)
    real = lam[np.isfinite(lam) & (np.abs(lam.imag) <= 1e-6 * np.abs(lam.real)) & (lam.real > 0)].real
    return np.sort(real), A, B


print("\n═══ 3. Δt, при которых J(z, Δt) вырожден (положительные вещественные собственные значения пучка) ═══")
retry = [c.DAY / 2 ** m for m in range(10)]
for name, z, J1 in (("z_old", z_old, J_old_fail), ("z*", z_star, r_fail["its"][-1]["J"])):
    dts, A, B = pencil(z, J1, c.DT_FAIL, c.DT_OK)
    print(f"  {name}: {dts.size} значений Δt > 0; в [10 с, 1e6 с]: "
          + ", ".join(f"{d:.4g}" for d in dts[(dts > 10) & (dts < 1e6)]))
    for d in retry:
        Jd = A / d + B
        s = np.linalg.svd(Jd, compute_uv=False)
        near = dts[np.argmin(np.abs(np.log(dts / d)))] if dts.size else np.nan
        print(f"    Δt = {d:9.2f} с: σ_min/σ_max = {s[-1] / s[0]:.2e}; ближайшее вырожденное Δt = {near:.4g} с")

# ── 4. Наименьший сингулярный вектор J в z* ──
print("\n═══ 4. Наименьший сингулярный вектор J(z*, 168.75 с) ═══")
U, s, Vt = np.linalg.svd(r_fail["its"][-1]["J"])
v = Vt[-1]
w = v[:n] ** 2 + v[n:] ** 2
top = np.argsort(-w)[:10]
print(f"  σ_min/σ_max = {s[-1] / s[0]:.2e}, σ_min/σ_(min+1) = {s[-1] / s[-2]:.2e}")
print("  ячейки с наибольшей долей вектора (|v_p|² + |v_X|²):")
for i in top:
    print(f"    i = {i:3d} (r = {r_c[i]:7.2f} м): доля {w[i]:.3f}, S_g* = {z_star[n + i]:.4f}, "
          f"p* = {z_star[i]:.2f} бар, c_t* = {ct_s[i]:+.2e} 1/бар")
