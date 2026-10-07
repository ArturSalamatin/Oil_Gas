"""BUG-019, шаг 2: T0, T1, T2, T5, T5б на замороженном состоянии (t = 1 сут).

Обозначения: z_old — состояние на 1 сут; z* — последняя итерация при Δt = 168.75 с
(провал линейного поиска); dz = −J⁻¹f, как в _linear_solve.

T0  линейное решение: r_lin, обратная ошибка, cond(J) без и с выравниванием, шум невязки
T1  раскраска: grouped против reference по блокам
T2  тест Тейлора вдоль dz на всех итерациях; шум e_шум(ε) и погрешность якобиана e_J
T5  ход итераций, пересечения узлов таблицы ОФП, зацикливание
T5б существование решения шага 168.75 с: Ньютон из z_mid = z_old + ½(z_337 − z_old) и из z_337

Запуск (из numerical_solver), после freeze.py:
    .venv\\Scripts\\python ..\\vault\\issues\\bug-019\\probes\\diagnose.py
"""

import numpy as np

import common as c

model, cfg = c.make_model()
st = c.load_state()
n = model.grid.n
mask = st.gas_active.copy()
S_GC = cfg.relperm.S_gc
r_fail = c.trace_newton(model, st, c.DT_FAIL)
r_ok = c.trace_newton(model, st, c.DT_OK)
assert r_fail["outcome"] == "провал линейного поиска" and r_ok["outcome"] == "сошёлся"
z_old = model.pack(st, mask)
z_star = r_fail["its"][-1]["z"]

EPS_LS = [2.0 ** -m for m in range(12)]          # ровно те α, что перебирает поиск
EPS_SMALL = [10.0 ** -k for k in range(4, 11)]
EPS = sorted(set(EPS_LS + EPS_SMALL), reverse=True)


def F(z, dt):
    return model.residual(z, st, dt, mask)


def jac_central(z, dt):
    """Центральная разность с той же раскраской и теми же |h|, что grouped (blackoil.py:204-216)."""
    J = np.zeros((2 * n, 2 * n))
    for block in (0, 1):
        for color in range(3):
            zp, zm, cols = z.copy(), z.copy(), []
            for i in range(color, n, 3):
                j = i if block == 0 else n + i
                if block == 0:
                    h = abs(model._pressure_fd_step(z[j], bool(mask[i])))
                else:
                    h = 1e-7 if mask[i] else max(1e-5, 1e-6 * max(abs(z[j]), 1.0))
                zp[j] += h; zm[j] -= h; cols.append((i, j, h))
            df = F(zp, dt) - F(zm, dt)
            for i, j, h in cols:
                rows = np.arange(max(0, i - 1), min(n, i + 2))
                J[rows, j] = df[rows] / (2 * h); J[n + rows, j] = df[n + rows] / (2 * h)
    return J


def ninf(v):
    return float(np.max(np.abs(v)))


# ═════════════ T0 ═════════════
def t0(it, dt, label):
    J, f, dz = it["J"], it["f"], it["dz"]
    res = J @ dz + f
    r_lin = ninf(res) / ninf(f)
    bwd = ninf(res) / (float(np.max(np.sum(np.abs(J), axis=1))) * ninf(dz) + ninf(f))
    dr = 1.0 / np.max(np.abs(J), axis=1)
    Jr = J * dr[:, None]
    dc = 1.0 / np.max(np.abs(Jr), axis=0)
    S = c.noise_rows(model, it["z"], st, dt, mask)
    print(f"  {label}: r_lin {r_lin:.2e}, обратная ошибка {bwd:.2e}, cond(J) {np.linalg.cond(J):.2e}, "
          f"cond после выравнивания {np.linalg.cond(Jr * dc[None, :]):.2e}, "
          f"||f|| {ninf(f):.3e}, шум ||S|| {ninf(S):.2e} (допуск 1.34e-11)")


print("═══ T0. Линейное решение ═══")
t0(r_fail["its"][-1], c.DT_FAIL, "168.75 с, z*   ")
t0(r_fail["its"][0], c.DT_FAIL, "168.75 с, k = 0")
for k in (0, 1, len(r_ok["its"]) - 2):
    t0(r_ok["its"][k], c.DT_OK, f"337.5 с,  k = {k}")

# ═════════════ T1 ═════════════
print("\n═══ T1. Раскраска (grouped против reference) в z* ═══")
J_g = r_fail["its"][-1]["J"]
J_r, _ = model.finite_difference_jacobian_reference(z_star, st, c.DT_FAIL, mask)
for name, sl in (("pp", np.s_[:n, :n]), ("pX", np.s_[:n, n:]), ("Xp", np.s_[n:, :n]), ("XX", np.s_[n:, n:])):
    d = np.max(np.abs(J_g[sl] - J_r[sl]))
    print(f"  {name}: max|ΔJ| = {d:.3e}, max|ΔJ|/max|J| = {d / np.max(np.abs(J_r[sl])):.3e}")


# ═════════════ T2 ═════════════
def t2(it, dt):
    """Тейлор вдоль dz: R(ε) = F(z+ε·dz) − f − ε·J·dz."""
    z, f, dz, J = it["z"], it["f"], it["dz"], it["J"]
    Jdz = J @ dz
    S = c.noise_rows(model, z, st, dt, mask)
    e_J = ninf((J - jac_central(z, dt)) @ dz) / ninf(Jdz)
    rows = []
    for e in EPS:
        zt = z + e * dz
        Ft = F(zt, dt)
        R = Ft - f - e * Jdz
        rows.append(dict(eps=e, e=ninf(R) / (e * ninf(Jdz)), e_noise=2 * ninf(S) / (e * ninf(Jdz)),
                         m_inf=ninf(Ft) / ninf(f), m2=np.linalg.norm(Ft) / np.linalg.norm(f),
                         ok=model._trial_is_reasonable(zt, mask), arg=int(np.argmax(np.abs(R)))))
    # Повтор линейного поиска: первое α = 2^-m с допустимой точкой и m_inf < 1
    acc = next((r["eps"] for r in rows if r["eps"] in EPS_LS and r["ok"] and r["m_inf"] < 1), None)
    return rows, e_J, acc


def print_t2(rows, e_J, acc, alpha, label):
    print(f"\n  {label}: e_J = {e_J:.2e}; повтор поиска даёт α = {acc}, Ньютон принял {alpha}")
    print(f"  {'ε':>10} {'e(ε)':>9} {'e_шум':>9} {'m∞':>9} {'m2':>9} {'1−ε':>9} доп. макс. R")
    for r in rows:
        i, eq = c.where(r["arg"], n)
        print(f"  {r['eps']:10.3e} {r['e']:9.2e} {r['e_noise']:9.2e} {r['m_inf']:9.6f} {r['m2']:9.6f} "
              f"{1 - r['eps']:9.6f} {'да' if r['ok'] else 'НЕТ':>4} {eq} {i} (S_g {st.sg[i] if mask[i] else float('nan'):.4f})")


print("\n═══ T2. Тейлор вдоль направления Ньютона ═══")
t2_all = {}
for label, r, dt in (("168.75 с", r_fail, c.DT_FAIL), ("337.5 с", r_ok, c.DT_OK)):
    for k, it in enumerate(r["its"][:-1] if label == "337.5 с" else r["its"]):
        rows, e_J, acc = t2(it, dt)
        t2_all[(label, k)] = (rows, e_J, acc)
        full = (label == "168.75 с" and k in (0, len(r["its"]) - 1)) or (label == "337.5 с" and k == 0)
        if full:
            print_t2(rows, e_J, acc, it["alpha"], f"{label}, k = {k}")
print("\n  Сводка по итерациям: e(ε) при ε = 1, 2^-3, 2^-6, 2^-11, 1e-4, 1e-5, 1e-6; min e; e_J")
for (label, k), (rows, e_J, acc) in t2_all.items():
    by = {r["eps"]: r for r in rows}
    sel = [1.0, 2.0 ** -3, 2.0 ** -6, 2.0 ** -11, 1e-4, 1e-5, 1e-6]
    emin = min(rows, key=lambda r: r["e"])
    print(f"  {label} k={k}: " + " ".join(f"{by[e]['e']:.1e}" for e in sel)
          + f" | min {emin['e']:.1e} при ε={emin['eps']:.0e} | e_J {e_J:.1e} | α повт. {acc}")


# ═════════════ T5 ═════════════
def seg(sg):
    return np.floor(sg / c.SG_STEP + 1e-12).astype(int)


def t5(r, label):
    print(f"\n  {label}: {r['outcome']}")
    its = r["its"]
    print(f"  {'k':>2} {'||f||∞':>10} {'макс.':>14} {'S_g':>8} {'p, бар':>9} {'α':>10} узлов пересечено / из них S_gc")
    for k, it in enumerate(its):
        a = int(np.argmax(np.abs(it["f"])))
        i, eq = c.where(a, n)
        sg_k = it["z"][n:]
        line = f"  {k:2d} {ninf(it['f']):10.4e} {eq + ' ' + str(i):>14} {sg_k[i] if mask[i] else float('nan'):8.4f} {it['z'][i]:9.4f}"
        if it["alpha"] is not None:
            sg_next = its[k + 1]["z"][n:]
            cross = mask & (seg(sg_k) != seg(sg_next))
            cgc = mask & ((sg_k - S_GC) * (sg_next - S_GC) < 0)
            line += f" {it['alpha']:10.3e} {int(cross.sum())} / {int(cgc.sum())}"
        print(line)
    # Зацикливание: знак шага S_g чередуется и ячейка возвращается на прежний отрезок таблицы
    steps = np.array([its[k + 1]["z"][n:] - its[k]["z"][n:] for k in range(len(its) - 1)])
    segs = np.array([seg(it["z"][n:]) for it in its])
    flips = np.sum(np.diff(np.sign(steps), axis=0) != 0, axis=0) if len(steps) > 1 else np.zeros(n)
    back = np.array([len(set(segs[:, i])) < len(segs[:, i]) and len(set(segs[:, i])) > 1 for i in range(n)])
    cyc = np.where(mask & (flips >= 2) & back)[0]
    print(f"  ячеек со сменой знака шага S_g ≥ 2 раз и возвратом на отрезок: {cyc.size}"
          + (f" — {cyc[:15].tolist()}" if cyc.size else ""))
    near = mask & (np.abs(st.sg - S_GC) < 0.02)
    print(f"  ячеек у S_gc (|S_g − 0.1| < 0.02) в z_old: {int(near.sum())}, индексы {np.where(near)[0].tolist()[:20]}")


print("\n═══ T5. Ход итераций ═══")
t5(r_fail, "168.75 с")
t5(r_ok, "337.5 с")

# ═════════════ T5б ═════════════
print("\n═══ T5б. Существует ли решение шага 168.75 с ═══")
z_337 = r_ok["z_end"]
results = {}
for name, z0 in (("z_mid", z_old + 0.5 * (z_337 - z_old)), ("z_337", z_337.copy())):
    r = c.trace_newton(model, st, c.DT_FAIL, z0=z0)
    results[name] = r
    print(f"  из {name}: {r['outcome']}, итераций {r['rep'].iterations}, ||F||∞ {r['rep'].residual_inf:.3e}, "
          f"α: {[None if it['alpha'] is None else round(it['alpha'], 6) for it in r['its']]}")
sol = next((r["z_end"] for r in results.values() if r["outcome"] == "сошёлся"), None)
if sol is not None:
    dp = z_star[:n] - sol[:n]
    dsg = np.where(mask, z_star[n:] - sol[n:], 0.0)
    top = np.argsort(-np.abs(dsg))[:10]
    print(f"  z* против решения: max|Δp| {ninf(dp):.4e} бар (ячейка {int(np.argmax(np.abs(dp)))}), "
          f"max|ΔS_g| {ninf(dsg):.4e}")
    print(f"  ||z_old − решение||: max|Δp| {ninf(z_old[:n] - sol[:n]):.4e} бар, "
          f"max|ΔS_g| {ninf(np.where(mask, z_old[n:] - sol[n:], 0)):.4e}")
    print("  ячейки с наибольшим |ΔS_g| (z* − решение):")
    for i in top:
        print(f"    i={i:3d} r={model.grid.centers_m[i]:8.3f} м "
              f"S_g: z_old {z_old[n + i]:.5f}, z* {z_star[n + i]:.5f}, решение {sol[n + i]:.5f}; "
              f"p: z* {z_star[i]:.4f}, решение {sol[i]:.4f} бар")

np.savez_compressed(c.HERE / "diagnose_iters.npz",
                    **{f"fail_z{k}": it["z"] for k, it in enumerate(r_fail["its"])},
                    **{f"fail_f{k}": it["f"] for k, it in enumerate(r_fail["its"])},
                    **{f"fail_dz{k}": it["dz"] for k, it in enumerate(r_fail["its"])},
                    **{f"ok_z{k}": it["z"] for k, it in enumerate(r_ok["its"])},
                    J_star=J_g, z_old=z_old, z_337=z_337,
                    sol=sol if sol is not None else np.array([]))

# ── График e(ε) ──
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

fig, ax = plt.subplots(figsize=(7, 5))
for (label, k), style in ((("168.75 с", len(r_fail["its"]) - 1), "C3-o"), (("168.75 с", 0), "C1-s"),
                          (("337.5 с", 0), "C0-^")):
    rows = t2_all[(label, k)][0]
    eps = [r["eps"] for r in rows]
    ax.loglog(eps, [r["e"] for r in rows], style, ms=4, label=f"e(ε), {label}, k = {k}")
    ax.loglog(eps, [r["e_noise"] for r in rows], style[:2] + ":", lw=1, label=f"шум, {label}, k = {k}")
ax.loglog([1e-6, 1], [1e-6, 1], "k--", lw=0.8, label="наклон 1")
ax.set_xlabel("ε (доля шага Ньютона)")
ax.set_ylabel("e(ε) = ||R||∞ / ||ε·J·dz||∞")
ax.legend(fontsize=7)
ax.grid(True, which="both", alpha=0.3)
fig.tight_layout()
fig.savefig(c.HERE / "t2_taylor.png", dpi=130)
print("\nграфик: t2_taylor.png")
