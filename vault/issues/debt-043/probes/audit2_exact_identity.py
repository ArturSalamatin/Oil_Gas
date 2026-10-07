"""DEBT-043, аудит 2: верна ли посылка «невязка — шум округления», и верно ли отвергнут вариант 1.

На каждом подшаге энергии, по тем же значениям double, что ушли в решатель:

  acc_ex  — невязка шага по формулам НАКОПИТЕЛЯ в точной арифметике (Fraction):
            ΔE − (adiab + conv + jt + deg + cond) с Φ± накопителя;
  mat_ex  — dt·Σ_j (A·T^{n+1} − d)_j, матрица собрана ТОЧНО по входам assemble_tridiag;
  mat_fl  — dt·Σ_j (A·T^{n+1} − d)_j по собранным в double a, b, c, d (обратная ошибка прогонки).

  acc_ex − mat_ex  — структурное расхождение формул накопителя и матрицы: ДЕФЕКТ, если ≠ 0;
  mat_ex − mat_fl  — округление сборки;
  res_fp − acc_ex  — округление самого накопителя (кумулятивные суммы).

Переигровка в отклонениях θ = T − T_ref (T_ref = T_ext подшага): та же матрица,
правая часть cap·θ_old + источники (граничные члены с T_ext − T_ref = 0), решение
solve_banded, шесть сумм копятся в double как в накопителе — невязка, которую
показал бы вариант 1 с ΔE по θ (а не по записанной T).

Запуск (из корня проекта):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-043\\probes\\audit2_exact_identity.py [пример ...]
    $env:DEBT043_SOLVER = "<дерево>\\numerical_solver"   # другое дерево (worktree BUG-020)
"""

import os
import sys
from fractions import Fraction as Fr
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = Path(os.environ.get("DEBT043_SOLVER", HERE.parents[3] / "numerical_solver")).resolve()
for p in (SOLVER, SOLVER / "examples", SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator  # noqa: E402
from scipy.linalg import solve_banded  # noqa: E402

EPS = float(np.finfo(float).eps)


def F(x):
    return Fr(float(x))


def exact_assemble(N, dt, T_old, T_ext, rho, QTi, QTe, Pp, Pm, J, Qad, Qdeg, V):
    """Повтор assemble_tridiag (tridiag.py:481-557, N > 1) в точной арифметике."""
    a = [Fr(0)] * N
    b = [Fr(0)] * N
    c = [Fr(0)] * N
    d = [Fr(0)] * N
    cap = [F(V[j]) * F(rho[j]) / F(dt) for j in range(N)]
    for j in range(1, N - 1):
        QL, QR = F(QTi[j - 1]), F(QTi[j])
        a[j] = -QL - F(Pp[j])
        c[j] = -QR + F(Pm[j + 1])
        b[j] = cap[j] + QL + QR + F(Pp[j]) - F(Pm[j + 1])
        d[j] = cap[j] * F(T_old[j]) + F(J[j]) + F(V[j]) * (F(Qad[j]) + F(Qdeg[j]))
    QR0 = F(QTi[0])
    c[0] = -QR0 + F(Pm[1])
    b[0] = cap[0] + QR0 - F(Pm[1])
    d[0] = cap[0] * F(T_old[0]) + F(J[0]) + F(V[0]) * (F(Qad[0]) + F(Qdeg[0]))
    QLN = F(QTi[-1])
    a[N - 1] = -QLN - F(Pp[N - 1])
    b[N - 1] = cap[N - 1] + QLN + F(QTe) + F(Pp[N - 1]) - F(Pm[N])
    d[N - 1] = (cap[N - 1] * F(T_old[N - 1]) + F(QTe) * F(T_ext) + (-F(Pm[N])) * F(T_ext)
                + F(J[N - 1]) + F(V[N - 1]) * (F(Qad[N - 1]) + F(Qdeg[N - 1])))
    return a, b, c, d


def row_sum(a, b, c, d, T):
    """Σ_j (a_j T_{j-1} + b_j T_j + c_j T_{j+1} − d_j), всё точно; a, b, c, d — Fraction или double."""
    N = len(T)
    Tf = [F(t) for t in T]
    s = Fr(0)
    for j in range(N):
        s += (a[j] if isinstance(a[j], Fr) else F(a[j])) * Tf[j - 1] if j > 0 else 0
        s += (b[j] if isinstance(b[j], Fr) else F(b[j])) * Tf[j]
        if j < N - 1:
            s += (c[j] if isinstance(c[j], Fr) else F(c[j])) * Tf[j + 1]
        s -= d[j] if isinstance(d[j], Fr) else F(d[j])
    return s


def acc_exact(T_new, T_old, rho, V, Pp, Pm, QTe, Text, J, Qad, Qdeg, dt):
    """Невязка шага по формулам накопителя (balance.py:221-340) в точной арифметике."""
    N = len(T_new)
    Tn = [F(t) for t in T_new]
    To = [F(t) for t in T_old]
    dtf = F(dt)
    dE = sum(F(rho[j]) * F(V[j]) * (Tn[j] - To[j]) for j in range(N))
    TL = [Tn[0]] + Tn[:-1]
    TR = Tn[1:] + [F(Text)]
    conv = -sum(F(Pp[j]) * (Tn[j] - TL[j]) + F(Pm[j + 1]) * (TR[j] - Tn[j]) for j in range(N)) * dtf
    jt = sum(F(x) for x in J) * dtf
    adiab = sum(F(V[j]) * F(Qad[j]) for j in range(N)) * dtf
    deg = sum(F(V[j]) * F(Qdeg[j]) for j in range(N)) * dtf
    cond = F(QTe) * (F(Text) - Tn[N - 1]) * dtf
    return dE - (adiab + conv + jt + deg + cond)


def theta_step(ins, V, sums):
    """Подшаг в отклонениях θ = T − T_ext; суммы копятся в double, как в накопителе."""
    N, dt, T_old, T_ext = ins["N"], ins["dt"], ins["T_old"], ins["T_ext"]
    rho, Pp, Pm, QTe = ins["rho"], ins["Pp"], ins["Pm"], ins["QTe"]
    J, Qad, Qdeg = ins["J"], ins["Qad"], ins["Qdeg"]
    th_old = T_old - T_ext                       # точно (Штербенц: T_old и T_ext близки)
    cap = V * rho / dt
    d = cap * th_old + J + V * (Qad + Qdeg)      # граничные члены ·(T_ext − T_ref) = 0
    a, b, c = ins["a"], ins["b"], ins["c"]       # матрица та же
    ab = np.zeros((3, N))
    ab[0, 1:] = c[:-1]
    ab[1, :] = b
    ab[2, :-1] = a[1:]
    th = solve_banded((1, 1), ab, d)
    TL = np.concatenate(([th[0]], th[:-1]))
    TR = np.concatenate((th[1:], [0.0]))
    Fc = Pp[0:N] * (th - TL) + Pm[1:N + 1] * (TR - th)
    sums["dE"] += float(np.sum(rho * V * (th - th_old)))
    sums["conv"] += -float(np.sum(Fc)) * dt
    sums["jt"] += float(np.sum(J)) * dt
    sums["adiab"] += float(np.sum(V * Qad)) * dt
    sums["deg"] += float(np.sum(V * Qdeg)) * dt
    sums["cond"] += float(QTe * (0.0 - th[N - 1]) * dt)
    sums["bound"] += EPS * float(np.sum(rho * V * np.abs(th)))
    return float(np.max(np.abs(th + T_ext - ins["T_new"])))


def run(name):
    cfg = load_config(SOLVER / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg)
    en = sim._energy
    V = sim._grid.volumes
    ins = {}
    orig_asm = en.assemble_tridiag
    orig_solve = en.solve_banded_system

    def asm(N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal, Q_T_ext, Phi_plus, Phi_minus,
            J_jt, Q_ad, Q_deg):
        a, b, c, d = orig_asm(N, dt, T_old, T_ext, rho_cp_eff, Q_T_internal, Q_T_ext,
                              Phi_plus, Phi_minus, J_jt, Q_ad, Q_deg)
        ins.update(N=N, dt=dt, T_old=T_old.copy(), T_ext=T_ext, rho=rho_cp_eff.copy(),
                   QTi=np.array(Q_T_internal, copy=True), QTe=Q_T_ext, Pp=Phi_plus.copy(),
                   Pm=Phi_minus.copy(), J=J_jt.copy(), Qad=Q_ad.copy(), Qdeg=Q_deg.copy(),
                   a=a.copy(), b=b.copy(), c=c.copy(), d=d.copy())
        return a, b, c, d

    def solve(a, b, c, d, N):
        T = orig_solve(a, b, c, d, N)
        ins["T_new"] = T.copy()
        return T

    en.assemble_tridiag = asm
    en.solve_banded_system = solve

    orig_acc = EnergyBalanceAccumulator.add_accumulation
    st = dict(prev=0.0, n=0, struct_max=Fr(0), struct_nonzero=0, sum_acc_round=0.0,
              sum_asm=0.0, sum_slae=0.0, sum_res=0.0, max_th_dev=0.0, bound=0.0)
    th_sums = dict(dE=0.0, conv=0.0, jt=0.0, adiab=0.0, deg=0.0, cond=0.0, bound=0.0)

    def add_accumulation(self, T_new, T_prev, rho_cp_eff, dt):
        Pp_acc, Pm_acc = self._Phi_plus.copy(), self._Phi_minus.copy()
        QTe_acc, Text_acc = self._Q_T_ext, self._T_ext
        orig_acc(self, T_new, T_prev, rho_cp_eff, dt)
        now = self.delta_E - (self.cum_adiab + self.cum_conv + self.cum_jt
                              + self.cum_deg + self.cum_cond)
        res = now - st["prev"]
        st["prev"] = now
        ex_acc = acc_exact(T_new, T_prev, rho_cp_eff, V, Pp_acc, Pm_acc, QTe_acc, Text_acc,
                           ins["J"], ins["Qad"], ins["Qdeg"], dt)
        ea = exact_assemble(ins["N"], ins["dt"], ins["T_old"], ins["T_ext"], ins["rho"],
                            ins["QTi"], ins["QTe"], ins["Pp"], ins["Pm"], ins["J"],
                            ins["Qad"], ins["Qdeg"], V)
        ex_mat = row_sum(*ea, T_new) * F(dt)
        fl_mat = row_sum(ins["a"], ins["b"], ins["c"], ins["d"], T_new) * F(dt)
        struct = ex_acc - ex_mat
        if struct != 0:
            st["struct_nonzero"] += 1
            st["struct_max"] = max(st["struct_max"], abs(struct))
        st["sum_acc_round"] += res - float(ex_acc)
        st["sum_asm"] += float(ex_mat - fl_mat)
        st["sum_slae"] += float(fl_mat)
        st["sum_res"] += res
        st["bound"] += EPS * float(np.sum(rho_cp_eff * V * T_new))
        st["n"] += 1
        st["max_th_dev"] = max(st["max_th_dev"], theta_step(ins, V, th_sums))

    EnergyBalanceAccumulator.add_accumulation = add_accumulation
    try:
        sim.run(init)
    finally:
        EnergyBalanceAccumulator.add_accumulation = orig_acc

    th_res = th_sums["dE"] - (th_sums["adiab"] + th_sums["conv"] + th_sums["jt"]
                              + th_sums["deg"] + th_sums["cond"])
    norm = sum(abs(th_sums[k]) for k in ("dE", "adiab", "conv", "jt", "deg", "cond"))
    print(f"\n=== {name}: подшагов {st['n']} ===", flush=True)
    print(f"  структурное расхождение накопитель − матрица (точно): ненулевых подшагов "
          f"{st['struct_nonzero']}, max {float(st['struct_max']):.3e} Дж")
    print(f"  невязка (Т-форма, как сейчас): {st['sum_res']:+.4e} Дж = прогонка {st['sum_slae']:+.4e}"
          f" + сборка {st['sum_asm']:+.4e} + накопитель {st['sum_acc_round']:+.4e};"
          f" B {st['bound']:.3e} Дж; отн. {abs(st['sum_res'])/norm:.2e}")
    print(f"  невязка в отклонениях θ (вариант 1): {th_res:+.4e} Дж; отн. {abs(th_res)/norm:.2e};"
          f" B_θ = Σε·Σ(ρc)V|θ| {th_sums['bound']:.3e} Дж; выигрыш ×{abs(st['sum_res'])/max(abs(th_res),1e-300):.0f}")
    print(f"  max|θ + T_ext − T^(n+1)| по подшагам {st['max_th_dev']:.2e} К "
          f"(решение в θ = решение в T до округления)", flush=True)


if __name__ == "__main__":
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    for nm in (sys.argv[1:] or ["16_well_shut_in", "13b_pwf_alternating", "01_single_phase_no_jt",
                                "04a_high_gas_saturation", "21_rs100_cooling"]):
        run(nm)
