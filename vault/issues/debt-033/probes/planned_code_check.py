"""DEBT-033, верификация плана: код шагов 2–3 плана подменой методов в памяти (файлы прототипа
не меняются) — тесты плана, побитовое сравнение историй примеров с исходным кодом, замер.

Запуск — из каталога numerical_solver:
    .venv\\Scripts\\python d:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\vault\\issues\\debt-033\\probes\\planned_code_check.py [пример ...]
"""
import sys
import time
from pathlib import Path

import numpy as np
from scipy.linalg import solve as dense_solve
from scipy.sparse import coo_matrix, csc_matrix, issparse
from scipy.sparse.linalg import splu

SOLVER_ROOT = Path.cwd()
PROTO = SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
sys.path.insert(0, str(PROTO))
sys.path.insert(0, str(SOLVER_ROOT))

import radial_blackoil.blackoil as B  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

M = B.RadialBlackOilModel


# ── Код плана (шаги 2–3), дословно ──
def _fd_steps(self,z,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
    z=np.asarray(z,float); mask=np.asarray(gas_active,dtype=bool); n=self.grid.n
    p,x=z[:n],z[n:]
    h=np.maximum(p_abs_step,p_rel_step*np.maximum(np.abs(p),1.0))
    knots=np.asarray(self.pvt.pb,float)
    if knots.size:
        idx=np.searchsorted(knots,p,side='left')
        lower=np.where(idx>0,knots[np.maximum(idx-1,0)],-np.inf)
        upper=np.where(idx<knots.size,knots[np.minimum(idx,knots.size-1)],np.inf)
        down=mask&(upper-p<=1.25*h)&(p-lower>h)
        h=np.where(down,-h,h)
    hx=np.where(mask,sg_abs_step,np.maximum(rs_abs_step,1e-6*np.maximum(np.abs(x),1.0)))
    return np.concatenate([h,hx])


def grouped_new(self,z,state_old,dt_s,gas_active,p_rel_step=1e-6,p_abs_step=1e-4,rs_abs_step=1e-5,sg_abs_step=1e-7):
    z=np.asarray(z,float); f0=self.residual(z,state_old,dt_s,gas_active); n=self.grid.n
    h=self._fd_steps(z,gas_active,p_rel_step,p_abs_step,rs_abs_step,sg_abs_step)
    rows=[]; cols=[]; vals=[]
    for block in (0,1):
        for color in range(3):
            cells=np.arange(color,n,3); j=cells+block*n; hj=h[j]
            zp=z.copy(); zp[j]+=hj
            df=self.residual(zp,state_old,dt_s,gas_active)-f0
            for d in (-1,0,1):
                ok=(cells+d>=0)&(cells+d<n); r=cells[ok]+d; c=j[ok]; hc=hj[ok]
                rows+=[r,n+r]; cols+=[c,c]; vals+=[df[r]/hc,df[n+r]/hc]
    J=coo_matrix((np.concatenate(vals),(np.concatenate(rows),np.concatenate(cols))),shape=(2*n,2*n)).tocsc()
    J.eliminate_zeros()
    return J,f0


def linear_solve_new(self,J,b):
    if self.linear_solver=='sparse': return splu(J if issparse(J) else csc_matrix(J)).solve(b)
    return dense_solve(J.toarray() if issparse(J) else J,b,assume_a='gen',check_finite=True)


ORIG = (M.finite_difference_jacobian_grouped, M._linear_solve)


def patch(on):
    if on:
        M._fd_steps = _fd_steps
        M.finite_difference_jacobian_grouped, M._linear_solve = grouped_new, linear_solve_new
    else:
        M.finite_difference_jacobian_grouped, M._linear_solve = ORIG


def planned_tests():
    """Утверждения трёх тестов плана (фикстура Nabor_1b)."""
    sys.path.insert(0, str(PROTO))
    import os
    cwd = os.getcwd(); os.chdir(PROTO)
    try:
        from tests.helpers import model_and_state
    finally:
        os.chdir(cwd)
    patch(True)
    # test_fd_steps_equal_scalar_rule
    _, m0, _ = model_and_state(n=3); knots = np.asarray(m0.pvt.pb, float)
    hk = np.maximum(1e-4, 1e-6*np.maximum(np.abs(knots), 1.0))
    offs = np.array([-2, -1.3, -1.25, -1, -0.5, 0, 0.5, 1, 1.25, 1.3, 2])
    p = np.concatenate([(knots[:, None]+offs*hk[:, None]).ravel(), [0.5, 1.0, knots[-1]+10.0, 300.0]])
    n = p.size; _, m, _ = model_and_state(n=n); flipped = []
    for mask in (np.ones(n, bool), np.arange(n) % 2 == 0):
        x = np.where(mask, 0.02, np.resize([0.5, 30.0, 120.0], n)); h = m._fd_steps(np.concatenate([p, x]), mask)
        hp = np.array([m._pressure_fd_step(pi, bool(gi)) for pi, gi in zip(p, mask)])
        hx = np.array([1e-7 if gi else max(1e-5, 1e-6*max(abs(xi), 1.0)) for xi, gi in zip(x, mask)])
        assert np.array_equal(h, np.concatenate([hp, hx])); flipped.append(np.any(hp < 0))
    assert flipped[0]
    print(f"test_fd_steps_equal_scalar_rule: OK (n={n}, отрицательных шагов {int(np.sum(m._fd_steps(np.concatenate([p, np.full(n, 0.02)]), np.ones(n, bool))[:n] < 0))})")
    # test_grouped_is_csc_bitwise_reference
    def states():
        _, m, s = model_and_state(n=7); yield m, s, s.gas_active.copy()
        for sg in (0.02, 0.0):
            _, m, s = model_and_state(n=7, p0=160); mask = np.zeros(7, bool); mask[:3] = True
            s.gas_active = mask; s.sg[:3] = sg; s.rs_sm3_sm3[:3] = m.pvt.rs_sat(s.pressure_bar[:3]); yield m, s, mask
    for m, s, mask in states():
        z = m.pack(s, mask); n = m.grid.n
        Jg, _ = m.finite_difference_jacobian_grouped(z, s, 60, mask); Jr, _ = m.finite_difference_jacobian_reference(z, s, 60, mask)
        assert issparse(Jg) and Jg.format == 'csc'
        assert np.array_equal(Jg.toarray(), Jr)
        R = csc_matrix(Jr)
        for a in ('indptr', 'indices', 'data'): assert np.array_equal(getattr(Jg, a), getattr(R, a)), a
        assert Jg.nnz < 4*(3*n-2)
    print("test_grouped_is_csc_bitwise_reference: OK")
    # test_step_bitwise_grouped_vs_reference
    for dt in (60.0, 3600.0):
        _, mg, s = model_and_state(n=8, jacobian='grouped'); _, mr, _ = model_and_state(n=8, jacobian='reference')
        a, ra = mg.advance(s, dt); b, rb = mr.advance(s, dt)
        assert ra.converged and rb.converged and ra.iterations == rb.iterations and ra.phase_switches > 0
        for f in ('pressure_bar', 'rs_sm3_sm3', 'sg', 'gas_active'): assert np.array_equal(getattr(a, f), getattr(b, f)), f
    print("test_step_bitwise_grouped_vs_reference: OK")
    # Прежние тесты с .toarray() и плотный путь
    _, ms, s = model_and_state(n=8, linear='sparse'); _, md, _ = model_and_state(n=8, linear='dense')
    a, ra = ms.advance(s, 60); b, rb = md.advance(s, 60)
    assert ra.converged and rb.converged and np.max(abs(a.pressure_bar-b.pressure_bar)) < 1e-8
    print("test_sparse_dense_same_step (плотный путь с CSC): OK")
    patch(False)


def run(ex):
    cfg = load_config(SOLVER_ROOT / "examples" / ex / "config.json")
    sim, s0 = SimulatorFactory.from_config(cfg)
    t = time.perf_counter(); h = sim.run(s0); wall = time.perf_counter() - t
    arrays = [np.array([getattr(s, f) for s in h.states]) for f in ("p", "Sg", "Rs", "T", "regime")]
    arrays += [np.array(h.times), np.array([r.G_o for r in h.hydro_results[1:]]), np.array([r.G_g for r in h.hydro_results[1:]])]
    return arrays, wall


planned_tests()
for ex in sys.argv[1:] or ["04_table_table", "15_oil_rate_ramp_up", "13b_pwf_alternating", "20_rs300_cooling", "14_high_gor_cooling"]:
    patch(False); a, w0 = run(ex)
    patch(True); b, w1 = run(ex)
    same = all(x.shape == y.shape and np.array_equal(x, y) for x, y in zip(a, b))
    print(f"{ex}: истории {'побитово' if same else 'РАЗЛИЧИЕ'}; время {w0:.2f} → {w1:.2f} с (×{w0 / w1:.2f})")
patch(False)
