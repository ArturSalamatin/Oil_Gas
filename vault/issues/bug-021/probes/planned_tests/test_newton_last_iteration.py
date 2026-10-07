import unittest, numpy as np
from tests.helpers import model_and_state

# BUG-021: _newton_fixed_active_set tested convergence only at the top of an
# iteration, before the update, so a solve that converged on update max_iter was
# reported as failed (T05S_N200_DT5m, dt = 3.75 s: 15 iterations, ||F||_inf =
# 4.2e-16, the step rejected and halved).  Every new iterate is tested now, on the
# residual the line search has already evaluated.  One Newton solve on a fixed
# phase set: 8 oil-only cells, BHP 100 bar against 200 bar, dt = 1 h.
DT=3600.0

def _solve(max_iter,z0=None):
    """(model, state, z0, z, report, Jacobian calls, tolerance) of one solve from the initial state."""
    _,m,s=model_and_state(n=8); mask=s.gas_active
    z0=m.pack(s,mask) if z0 is None else z0
    f0=m.residual(z0,s,DT,mask); tol=1e-11+1e-8*max(np.linalg.norm(f0,np.inf),1e-9)   # defaults of the method
    calls=[0]; jac=m.finite_difference_jacobian
    def counted(*a,**k): calls[0]+=1; return jac(*a,**k)
    m.finite_difference_jacobian=counted
    z,rep=m._newton_fixed_active_set(z0,s,DT,mask,max_iter=max_iter)
    return m,s,z0,z,rep,calls[0],tol

class NewtonLastIterationTests(unittest.TestCase):
    def test_converged_on_last_allowed_update(self):
        # With the default limit the solve converges in k updates.  With max_iter = k
        # it makes the same k updates, and the last iterate must be accepted: before
        # the fix it came back converged=False with ||F||_inf below the tolerance.
        *_,z_ref,ref,_,_=_solve(15); k=ref.iterations
        self.assertTrue(ref.converged); self.assertGreaterEqual(k,2)
        *_,z,rep,_,tol=_solve(k)
        self.assertTrue(rep.converged); self.assertEqual(rep.iterations,k)
        self.assertLessEqual(rep.residual_inf,tol); self.assertEqual(rep.residual_inf,ref.residual_inf)
        self.assertTrue(np.array_equal(z,z_ref))
    def test_one_update_short_still_fails(self):
        # The limit is not relaxed: with max_iter = k-1 the solve stops one update
        # short, above the tolerance, and reports a failure after k-1 iterations.
        *_,ref,_,_=_solve(15); k=ref.iterations
        *_,rep,_,tol=_solve(k-1)
        self.assertFalse(rep.converged); self.assertEqual(rep.iterations,k-1); self.assertGreater(rep.residual_inf,tol)
    def test_no_jacobian_built_only_to_detect_convergence(self):
        # The residual of the accepted line-search point is bitwise the f0 that a
        # Jacobian call at that point returns, so a solve converged in k updates
        # builds k Jacobians; before the fix it built one more, only to see ||F||.
        *_,ref,calls,_=_solve(15)
        self.assertTrue(ref.converged); self.assertEqual(calls,ref.iterations)
    def test_converged_start_returns_at_once(self):
        # A start that already meets the tolerance returns unchanged with 0 iterations
        # and no Jacobian.  advance() relies on it: in the BHP fallback the 'shut'
        # branch of an unchanged state converges in 0 iterations (DEBT-030 probe).
        *_,z_ref,ref,_,_=_solve(15)
        *_,z0,z,rep,calls,tol=_solve(15,z0=z_ref.copy())
        self.assertLessEqual(ref.residual_inf,tol)   # precondition: the converged point is a converged start
        self.assertTrue(rep.converged); self.assertEqual(rep.iterations,0); self.assertEqual(calls,0)
        self.assertTrue(np.array_equal(z,z0))

if __name__=='__main__': unittest.main()
