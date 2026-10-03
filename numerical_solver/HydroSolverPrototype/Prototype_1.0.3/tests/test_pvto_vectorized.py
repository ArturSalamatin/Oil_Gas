import unittest, numpy as np
from radial_blackoil.pvt import BlackOilPVT
from radial_blackoil.units import CP_TO_PA_S
from tests.helpers import model_and_state

# DEBT-036: BlackOilPVT interpolates PVTO for all cells at once (_oil_props).  Bo and mu_o enter
# every residual of the Newton solve and, through the GPN adapter, the energy equation: they must
# stay bitwise the former per-segment loop with np.interp per branch, reproduced below verbatim.
# The prototype regression against golden/ (abs 2e-7 / rel 2e-10) depends on it.
def _former_oil_prop(pvt,p,rs,which):
    """BlackOilPVT._oil_prop with _branch_prop_delta before DEBT-036, verbatim."""
    p_arr,rs_arr=np.broadcast_arrays(np.asarray(p,float),np.asarray(rs,float))
    shape=p_arr.shape; pf=p_arr.ravel(); rf=rs_arr.ravel(); out=np.empty_like(pf,dtype=float)
    rr=np.clip(rf,pvt.rs_values[0],pvt.rs_values[-1])
    j=np.searchsorted(pvt.rs_values,rr,side='right')-1
    j=np.clip(j,0,len(pvt.rs_values)-2)
    for jj in np.unique(j):
        loc=(j==jj); ids=np.nonzero(loc)[0]
        r0,r1=pvt.rs_values[jj],pvt.rs_values[jj+1]
        rrj=rr[loc]; ppj=pf[loc]
        w=(rrj-r0)/(r1-r0)
        pbq=pvt.pb[jj]+w*(pvt.pb[jj+1]-pvt.pb[jj])
        dp=np.maximum(ppj-pbq,0.0)
        def branch(rs_branch):
            x,bo,mu=pvt._branch_arrays[float(rs_branch)]
            return np.interp(dp,x,bo if which=='bo' else mu)
        v0=branch(r0); v1=branch(r1)
        out[ids]=v0+w*(v1-v0)
    return out.reshape(shape)

GAS=[(1.0,0.9,0.011),(400.0,0.003,0.03)]

def _irregular_table():
    """7 Rs branches of 2...8 rows with uneven pressure steps: knots of different branches interleave."""
    rng=np.random.default_rng(7); rows=[]
    for k,rs in enumerate((0.0,15.0,40.0,41.5,90.0,150.0,260.0)):
        pb=20.0+1.1*rs; d=np.concatenate([[0.0],np.cumsum(rng.uniform(3.0,40.0,k+1))])
        rows+=[(rs,pb+x,1.05+0.0012*rs-1e-4*x,2.0-0.004*rs+3e-3*x) for x in d]
    return BlackOilPVT(rows,GAS)

def _tables():
    """Fixture Nabor_1b (6 branches of 5 rows), the irregular table, a table with a one-row branch."""
    inp,_,_=model_and_state(n=3)
    # A one-row branch (Rs = 30): the GPN CSV reader does not forbid it; np.interp returns its only value
    one_row=BlackOilPVT([(0,20,1.05,3.0),(0,80,1.04,3.1),(30,120,1.2,1.5),(60,170,1.3,1.2),(60,260,1.28,1.4)],GAS)
    return (('Nabor_1b',inp.pvt),('irregular',_irregular_table()),('one-row branch',one_row))

def _points(pvt):
    """Grid p x Rs through the special points, random pairs, NaN and +inf."""
    # Rs: the branches exactly and one ulp off them, segment midpoints, outside the table (end
    # branches are used, no extrapolation).  p: every PVTO knot pressure exactly and one ulp off it
    # (at Rs of a branch dp then hits its knots exactly), 7.5 bar above the knots, p below Pb, far
    # above the branch tops.
    rng=np.random.default_rng(36); rs_v=pvt.rs_values; lo,hi=rs_v[0],rs_v[-1]
    rs_pts=np.concatenate([rs_v,np.nextafter(rs_v,np.inf),np.nextafter(rs_v,-np.inf),0.5*(rs_v[1:]+rs_v[:-1]),[lo-5.0,hi+5.0],rng.uniform(lo-5.0,hi+5.0,20)])
    knots=np.array([r[0] for k in rs_v for r in pvt.branches[float(k)]])
    p_pts=np.concatenate([knots,np.nextafter(knots,np.inf),np.nextafter(knots,-np.inf),knots+7.5,[1.0,knots.max()+100.0],rng.uniform(1.0,knots.max()+50.0,50)])
    P,R=np.meshgrid(p_pts,rs_pts)
    p=np.concatenate([P.ravel(),rng.uniform(1.0,knots.max()+50.0,5000),[np.nan,100.0,np.inf]])
    rs=np.concatenate([R.ravel(),rng.uniform(lo-5.0,hi+5.0,5000),[lo,np.nan,hi]])
    return p,rs

class PvtoVectorizedTests(unittest.TestCase):
    def test_bo_mu_bitwise_former_loop(self):
        # Bitwise the former loop on every point of _points, including NaN (NaN as before) and
        # p = +inf (the branch top, as np.interp).  At +inf the discarded branch of np.where computes
        # 0*inf: the RuntimeWarning is silenced, the value is not used.
        for name,pvt in _tables():
            p,rs=_points(pvt)
            with np.errstate(invalid='ignore'):
                for which,f in (('bo',pvt.bo),('mu',pvt.mu_o)):
                    self.assertEqual(f(p,rs).tobytes(),_former_oil_prop(pvt,p,rs,which).tobytes(),f'{name} {which}')
    def test_shapes_as_before(self):
        # The well and outer faces call with scalars (0-d result), two_phase_analytics.py with a scalar
        # p and an array Rs; 2-D input keeps its shape; empty input gives an empty result
        for name,pvt in _tables():
            p,rs=_points(pvt)
            for pp,rr in ((150.0,30.0),(np.float64(p[9]),np.array(rs[9])),(float(p[5]),rs[:20]),(p[:20],float(rs[3])),(p[:12].reshape(3,4),rs[:12].reshape(3,4))):
                a=pvt.mu_o(pp,rr); b=_former_oil_prop(pvt,pp,rr,'mu')
                self.assertEqual((a.shape,a.tobytes()),(b.shape,b.tobytes()),name)
            self.assertEqual(pvt.bo(np.empty(0),np.empty(0)).shape,(0,))
    def test_single_rs_branch_rejected(self):
        # One Rs branch: the former code divided 0/0 between the branch and itself (NaN Bo, mu_o in
        # every cell, the run failed later); now the table is rejected when built
        with self.assertRaisesRegex(ValueError,'Rs branches'):
            BlackOilPVT([(10,50,1.1,2.0),(10,100,1.09,2.1)],GAS)
    def test_bo_mu_o_one_pass(self):
        # bo_mu_o shares the segment and row search of Bo and mu_o: bitwise bo and mu_o called apart
        for name,pvt in _tables():
            p,rs=_points(pvt)
            with np.errstate(invalid='ignore'):
                bo,mu=pvt.bo_mu_o(p,rs)
                self.assertEqual(bo.tobytes(),pvt.bo(p,rs).tobytes(),name); self.assertEqual(mu.tobytes(),pvt.mu_o(p,rs).tobytes(),name)
    def test_mobilities_one_pvto_pass(self):
        # _phase_mobilities_surface takes Bo and mu_o from one bo_mu_o call where the PVT has it
        # (BlackOilPVT); the mobilities are bitwise those from bo and mu_o
        _,m,s=model_and_state(n=5,p0=160); p,rs,sg=s.pressure_bar,s.rs_sm3_sm3,np.full(5,0.05)
        calls=[]; real=m.pvt
        class Spy:
            def __getattr__(self,name):
                calls.append(name); return getattr(real,name)
        m.pvt=Spy(); lo,lg=m._phase_mobilities_surface(p,rs,sg); m.pvt=real
        self.assertIn('bo_mu_o',calls); self.assertNotIn('mu_o',calls)
        lo_ref=m.relperm.kro(sg)/(real.mu_o(p,rs)*CP_TO_PA_S)/real.bo(p,rs); lg_ref=m.relperm.krg(sg)/(real.mu_g(p)*CP_TO_PA_S)/real.bg(p)
        self.assertEqual(lo.tobytes(),lo_ref.tobytes()); self.assertEqual(lg.tobytes(),lg_ref.tobytes())
        # A PVT without bo_mu_o (as the Standing adapter): bo and mu_o apart, the same mobilities
        class NoOnePass:
            def __getattr__(self,name):
                if name=='bo_mu_o': raise AttributeError(name)
                return getattr(real,name)
        m.pvt=NoOnePass(); lo2,lg2=m._phase_mobilities_surface(p,rs,sg); m.pvt=real
        self.assertEqual(lo2.tobytes(),lo_ref.tobytes()); self.assertEqual(lg2.tobytes(),lg_ref.tobytes())

if __name__=='__main__': unittest.main()
