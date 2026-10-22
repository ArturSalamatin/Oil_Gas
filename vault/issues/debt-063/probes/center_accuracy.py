"""DEBT-063, проба: какой центр ячейки точнее — √(r_{j-1/2}·r_{j+1/2}) или exp<ln r>.

Однофазный упругий приток к скважине, безразмерно (η = k/(φμc_t) = 1, Δp = 1):
    ∂p/∂t = (1/r) ∂/∂r (r ∂p/∂r),  p(r_w) = 0,  p(R) = 1,  p(r, 0) = 1.
Метод конечных объёмов на логарифмической сетке, двухточечный поток с
проводимостью 1/ln(r_{j+1}/r_j), граничные — 1/ln(r_0/r_w), 1/ln(R/r_{N-1}).
Обе схемы отличаются ТОЛЬКО центрами. По времени — точно: система
A·dp/dt = L·p + b линейна, после симметризации y = A^{1/2}p матрица
A^{-1/2} L A^{-1/2} трёхдиагональна и симметрична, решение — через её
собственные пары (eigh_tridiagonal). Ошибки по времени нет.

Эталон — N = 2000 (грани вложены: N делит 2000). Метрики на моменты t:
  q     — дебит (поток через забойную грань), отн. ошибка;
  ⟨p⟩   — max |p_j − среднее эталона по ячейке j| (что FVM хранит в ячейке);
  p(r_j) — max |p_j − эталон в точке r_j| (что рисует график p(r)).
Стационар (t → ∞) — профиль Дюпюи: обе схемы воспроизводят его в своих
центрах точно (проверяется отдельно).

Запуск из numerical_solver/:  .venv\\Scripts\\python -u ..\\vault\\issues\\debt-063\\probes\\center_accuracy.py
"""

import numpy as np
from scipy.linalg import eigh_tridiagonal
from scipy.sparse import diags

RW, R = 0.1, 50.0
TIMES = np.array([0.01, 0.1, 1.0, 10.0, 100.0, 1000.0])
N_REF = 2000


def centers(f, kind):
    """Центры ячеек: geo — √(ab) (прототип), log — exp<ln r> (eq:cell_center)."""
    a, b = f[:-1], f[1:]
    if kind == "geo":
        return np.sqrt(a * b)
    x = (a / b) ** 2
    return b * np.sqrt(np.exp(-x * np.log(x) / (1.0 - x) - 1.0))


def solve(N, kind):
    """Решение в моменты TIMES: (грани, центры, p[len(TIMES), N], q[len(TIMES)])."""
    f = np.geomspace(RW, R, N + 1)
    c = centers(f, kind)
    A = 0.5 * (f[1:] ** 2 - f[:-1] ** 2)          # V_j / (2πh)
    Ti = 1.0 / np.log(c[1:] / c[:-1])              # внутренние грани
    Tw = 1.0 / np.log(c[0] / RW)                   # забойная грань
    Te = 1.0 / np.log(R / c[-1])                   # контур
    main = np.zeros(N)
    main[:-1] -= Ti
    main[1:] -= Ti
    main[0] -= Tw
    main[-1] -= Te
    # Стационар L·p_ss = −b: p(r_w) = 0, p(R) = 1 входят через b
    from scipy.sparse.linalg import spsolve
    b = np.zeros(N)
    b[-1] = Te * 1.0
    p_ss = spsolve(diags([Ti, main, Ti], [-1, 0, 1], format="csc"), -b)
    # y = A^{1/2}(p − p_ss): dy/dt = S y, S = A^{-1/2} L A^{-1/2} — трёхдиагональна
    sA = np.sqrt(A)
    lam, V = eigh_tridiagonal(main / A, Ti / (sA[:-1] * sA[1:]))
    w0 = V.T @ (sA * (1.0 - p_ss))                 # начальное p = 1
    p = p_ss + ((np.exp(np.outer(TIMES, lam)) * w0) @ V.T) / sA
    q = Tw * p[:, 0]                               # приток к скважине, > 0
    return f, c, p, q


def steady_check(N, kind):
    """Стационар: решить L p = −b и сравнить с Дюпюи в своих центрах."""
    from scipy.sparse.linalg import spsolve
    f = np.geomspace(RW, R, N + 1)
    c = centers(f, kind)
    Ti = 1.0 / np.log(c[1:] / c[:-1])
    Tw = 1.0 / np.log(c[0] / RW)
    Te = 1.0 / np.log(R / c[-1])
    main = np.zeros(N)
    main[:-1] -= Ti
    main[1:] -= Ti
    main[0] -= Tw
    main[-1] -= Te
    L = diags([Ti, main, Ti], [-1, 0, 1], format="csc")
    b = np.zeros(N)
    b[-1] = Te
    p = spsolve(L, -b)
    dup = np.log(c / RW) / np.log(R / RW)
    q = Tw * p[0]
    return np.max(np.abs(p - dup)), abs(q * np.log(R / RW) - 1.0)


print("Стационар (Дюпюи): max|p_j − p_Дюпюи(r_j)|, отн. ошибка дебита")
for kind in ("geo", "log"):
    for N in (5, 20, 100):
        dp, dq = steady_check(N, kind)
        print(f"  {kind:3s} N={N:4d}: {dp:.1e}  {dq:.1e}")

ref = {k: solve(N_REF, k) for k in ("geo", "log")}
fr, _, _, _ = ref["log"]
Ar = 0.5 * (fr[1:] ** 2 - fr[:-1] ** 2)
q_gap = np.max(np.abs(ref["geo"][3] / ref["log"][3] - 1.0))
print(f"\nЭталоны N={N_REF} geo и log: max отн. разница дебита {q_gap:.1e}")
_, cr, pr, qr = ref["log"]

for N in (20, 50, 100, 200):
    k = N_REF // N
    print(f"\nN = {N}  (h = ln(R/r_w)/N = {np.log(R / RW) / N:.4f}, h²/6 = "
          f"{(np.log(R / RW) / N) ** 2 / 6:.1e})")
    print("      t   | отн. ошибка q    | max |p_j − ⟨p⟩_ячейки| | max |p_j − p(r_j)|")
    print("          |   geo     log    |   geo      log         |   geo      log")
    res = {}
    for kind in ("geo", "log"):
        f, c, p, q = solve(N, kind)
        eq = np.abs(q / qr - 1.0)
        # Среднее эталона по ячейке грубой сетки (грани вложены)
        avg = (pr * Ar).reshape(len(TIMES), N, k).sum(axis=2) / (
            Ar.reshape(N, k).sum(axis=1))
        e_avg = np.max(np.abs(p - avg), axis=1)
        # Эталон в точке r_j: интерполяция по ln r между узлами эталона
        e_pt = np.array([np.max(np.abs(p[i] - np.interp(np.log(c), np.log(cr), pr[i])))
                         for i in range(len(TIMES))])
        res[kind] = (eq, e_avg, e_pt)
    for i, t in enumerate(TIMES):
        g, l = res["geo"], res["log"]
        print(f"  {t:7.2f} | {g[0][i]:.1e} {l[0][i]:.1e} | {g[1][i]:.1e} {l[1][i]:.1e}"
              f"      | {g[2][i]:.1e} {l[2][i]:.1e}")
