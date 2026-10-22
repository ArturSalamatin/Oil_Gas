import unittest, numpy as np
from scipy.sparse import csc_matrix, issparse
from tests.helpers import model_and_state

class GroupedJacobianTests(unittest.TestCase):
    def test_grouped_equals_reference_oil_only(self):
        _,m,s=model_and_state(n=7); z=m.pack(s); Jg,f=m.finite_difference_jacobian_grouped(z,s,60,s.gas_active); Jr,_=m.finite_difference_jacobian_reference(z,s,60,s.gas_active); self.assertLess(np.max(abs(Jg.toarray()-Jr)),1e-8)
    def test_grouped_equals_reference_mixed_active(self):
        _,m,s=model_and_state(n=7,p0=160); mask=np.zeros(7,bool); mask[:3]=True; s.gas_active=mask; s.sg[:3]=0.02; s.rs_sm3_sm3[:3]=m.pvt.rs_sat(s.pressure_bar[:3]); z=m.pack(s); Jg,_=m.finite_difference_jacobian_grouped(z,s,60,mask); Jr,_=m.finite_difference_jacobian_reference(z,s,60,mask); self.assertLess(np.max(abs(Jg.toarray()-Jr)),2e-7)
    def test_one_step_grouped_reference_same(self):
        _,mg,s=model_and_state(n=8,jacobian='grouped'); _,mr,_=model_and_state(n=8,jacobian='reference'); a,rg=mg.advance(s,60); b,rr=mr.advance(s,60); self.assertTrue(rg.converged and rr.converged); self.assertLess(np.max(abs(a.pressure_bar-b.pressure_bar)),1e-7); self.assertLess(np.max(abs(a.rs_sm3_sm3-b.rs_sm3_sm3)),1e-7)
    def test_sparse_dense_same_step(self):
        _,ms,s=model_and_state(n=8,linear='sparse'); _,md,_=model_and_state(n=8,linear='dense'); a,ra=ms.advance(s,60); b,rb=md.advance(s,60); self.assertTrue(ra.converged and rb.converged); self.assertLess(np.max(abs(a.pressure_bar-b.pressure_bar)),1e-8)

# DEBT-033: the grouped Jacobian is assembled vectorized, directly as a CSC matrix.
# It must stay bitwise the former matrix: the Newton steps and the prototype
# regression against golden/ (abs 2e-7 / rel 2e-10) depend on it.  The bitwise
# reference is the column-by-column mode: the former dense grouped matrix equalled
# it bitwise on 488 Newton states of five GPN examples (DEBT-033 probe).
def _jacobian_states():
    """Oil-only, mixed (Sg = 0.02 and 0), mixed with two-phase cells just below a PVTO knot."""
    # Oil-only: downstream band entries are exact zeros.  Sg = 0: krg = 0 at the first
    # relperm-table row.  Below a knot: the pressure step of those cells is negative
    # (_pressure_fd_step steps down instead of straddling the Rs_sat(p) kink).
    _,m,s=model_and_state(n=7); yield m,s,s.gas_active.copy()
    for sg in (0.02,0.0):
        _,m,s=model_and_state(n=7,p0=160); mask=np.zeros(7,bool); mask[:3]=True
        s.gas_active=mask; s.sg[:3]=sg; s.rs_sm3_sm3[:3]=m.pvt.rs_sat(s.pressure_bar[:3]); yield m,s,mask
    _,m,s=model_and_state(n=7,p0=160); mask=np.zeros(7,bool); mask[:3]=True
    k=float(m.pvt.pb[-2]); s.pressure_bar[:3]=k-0.5*max(1e-4,1e-6*k)
    s.gas_active=mask; s.sg[:3]=0.02; s.rs_sm3_sm3[:3]=m.pvt.rs_sat(s.pressure_bar[:3]); yield m,s,mask

class GroupedJacobianSparseTests(unittest.TestCase):
    def test_fd_steps_equal_scalar_rule(self):
        # _fd_steps gives bitwise the steps of _pressure_fd_step (one-sided step at the
        # Rs_sat(p) knots) and of the Rs/Sg rule of the column loop.  Pressures straddle
        # every PVTO knot at 0.5...2 steps, where the step direction flips; Rs below
        # and above 1 hits both branches of max(|Rs|, 1).
        _,m0,_=model_and_state(n=3); knots=np.asarray(m0.pvt.pb,float)
        hk=np.maximum(1e-4,1e-6*np.maximum(np.abs(knots),1.0))
        offs=np.array([-2,-1.3,-1.25,-1,-0.5,0,0.5,1,1.25,1.3,2])
        p=np.concatenate([(knots[:,None]+offs*hk[:,None]).ravel(),[0.5,1.0,knots[-1]+10.0,300.0]])
        n=p.size; _,m,_=model_and_state(n=n); flipped=[]
        for mask in (np.ones(n,bool),np.arange(n)%2==0):
            x=np.where(mask,0.02,np.resize([0.5,30.0,120.0],n)); h=m._fd_steps(np.concatenate([p,x]),mask)
            hp=np.array([m._pressure_fd_step(pi,bool(gi)) for pi,gi in zip(p,mask)])
            hx=np.array([1e-7 if gi else max(1e-5,1e-6*max(abs(xi),1.0)) for xi,gi in zip(x,mask)])
            self.assertTrue(np.array_equal(h,np.concatenate([hp,hx]))); flipped.append(np.any(hp<0))
        self.assertTrue(flipped[0])   # the knot rule was exercised, not only the default +h
    def test_grouped_is_csc_bitwise_reference(self):
        # Values: bitwise the column-by-column reference.  Structure: the same CSC arrays
        # as csc_matrix(dense), which the former _linear_solve passed to splu -- explicit
        # zeros would change SuperLU's column ordering and the step at round-off level.
        negative=False
        for m,s,mask in _jacobian_states():
            z=m.pack(s,mask); n=m.grid.n
            Jg,_=m.finite_difference_jacobian_grouped(z,s,60,mask); Jr,_=m.finite_difference_jacobian_reference(z,s,60,mask)
            self.assertTrue(issparse(Jg) and Jg.format=='csc')
            self.assertTrue(np.array_equal(Jg.toarray(),Jr))
            R=csc_matrix(Jr)
            for a in ('indptr','indices','data'): self.assertTrue(np.array_equal(getattr(Jg,a),getattr(R,a)),a)
            self.assertLess(Jg.nnz,4*(3*n-2))   # the band holds exact zeros: eliminate_zeros is exercised
            negative|=bool(np.any(m._fd_steps(z,mask)[:n]<0))
        self.assertTrue(negative)   # some state used negative pressure steps (below a PVTO knot)
    def test_step_bitwise_grouped_vs_reference(self):
        # Whole implicit steps with phase switches: the grouped path (CSC straight to
        # splu) and the reference path (dense, csc_matrix in _linear_solve) must give
        # bitwise the same state and the same Newton iteration count.
        for dt in (60.0,3600.0):
            _,mg,s=model_and_state(n=8,jacobian='grouped'); _,mr,_=model_and_state(n=8,jacobian='reference')
            a,ra=mg.advance(s,dt); b,rb=mr.advance(s,dt)
            self.assertTrue(ra.converged and rb.converged); self.assertEqual(ra.iterations,rb.iterations)
            self.assertGreater(ra.phase_switches,0)   # the active-set loop ran, not one plain Newton solve
            for f in ('pressure_bar','rs_sm3_sm3','sg','gas_active'): self.assertTrue(np.array_equal(getattr(a,f),getattr(b,f)),f)

if __name__=='__main__': unittest.main()
