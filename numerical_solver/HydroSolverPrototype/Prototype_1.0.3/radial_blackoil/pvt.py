import numpy as np

class BlackOilPVT:
    """ECLIPSE-style PVTO oil plus tabular gas PVT.

    First row of each fixed-Rs branch is the saturated point Pb(Rs).
    For undersaturated oil, interpolation is performed in pressure-above-bubble
    coordinate before interpolation between adjacent Rs branches. This is the
    validated 1.0.3 interpolation; implementation is vectorized only for speed.
    """
    def __init__(self, oil_rows, gas_rows):
        rs_unique=sorted(set(float(r[0]) for r in oil_rows))
        self.branches={}
        self._branch_arrays={}
        for rs in rs_unique:
            b=sorted([(float(p),float(bo),float(mu)) for r,p,bo,mu in oil_rows if float(r)==rs])
            self.branches[rs]=b
            p0=b[0][0]
            self._branch_arrays[rs]=(
                np.array([x[0]-p0 for x in b],float),
                np.array([x[1] for x in b],float),
                np.array([x[2] for x in b],float),
            )
        self.rs_values=np.array(rs_unique,float)
        self.pb=np.array([self.branches[r][0][0] for r in rs_unique],float)
        self.bo_sat=np.array([self.branches[r][0][1] for r in rs_unique],float)
        self.mu_sat=np.array([self.branches[r][0][2] for r in rs_unique],float)
        self.max_rs=float(self.rs_values[-1]); self.bubble_point_max_rs_bar=float(self.pb[-1])
        self.gp=np.array([float(r[0]) for r in gas_rows]); self.gbg=np.array([float(r[1]) for r in gas_rows]); self.gmu=np.array([float(r[2]) for r in gas_rows])
        if len(self.gp)<2 or np.any(np.diff(self.gp)<=0): raise ValueError('GAS_PVT pressure must be strictly increasing with >=2 rows')

    def rs_sat(self,p):
        return np.interp(np.asarray(p,float),self.pb,self.rs_values)
    def pb_of_rs(self,rs):
        return np.interp(np.asarray(rs,float),self.rs_values,self.pb)
    def max_pressure_of_rs(self,rs):
        rr=np.clip(np.asarray(rs,float),self.rs_values[0],self.rs_values[-1])
        tops=np.array([self.branches[r][-1][0] for r in self.rs_values],float)
        return np.interp(rr,self.rs_values,tops)
    def _branch_prop_delta(self, rs_branch, delta_p, which):
        x,bo,mu=self._branch_arrays[float(rs_branch)]
        return np.interp(delta_p,x,bo if which=='bo' else mu)
    def _oil_prop(self,p,rs,which):
        p_arr,rs_arr=np.broadcast_arrays(np.asarray(p,float),np.asarray(rs,float))
        shape=p_arr.shape; pf=p_arr.ravel(); rf=rs_arr.ravel(); out=np.empty_like(pf,dtype=float)
        # PVTO is evaluated from fixed-Rs branches. At p below Pb(Rs), the
        # branch is clamped to its first (saturated) point. For a gas-active
        # state Rs=Rs_sat(p), this is exactly the saturated locus. This
        # extension is also important for a fixed-active-set Newton trial that
        # temporarily crosses the phase boundary before the active set switches.
        # Explicit endpoint clamp in Rs; no extrapolation between/above PVTO branches.
        rr=np.clip(rf,self.rs_values[0],self.rs_values[-1])
        j=np.searchsorted(self.rs_values,rr,side='right')-1
        j=np.clip(j,0,len(self.rs_values)-2)
        for jj in np.unique(j):
            loc=(j==jj); ids=np.nonzero(loc)[0]
            r0,r1=self.rs_values[jj],self.rs_values[jj+1]
            rrj=rr[loc]; ppj=pf[loc]
            w=(rrj-r0)/(r1-r0)
            pbq=self.pb[jj]+w*(self.pb[jj+1]-self.pb[jj])
            dp=np.maximum(ppj-pbq,0.0)
            v0=self._branch_prop_delta(r0,dp,which); v1=self._branch_prop_delta(r1,dp,which)
            out[ids]=v0+w*(v1-v0)
        return out.reshape(shape)
    def bo(self,p,rs): return self._oil_prop(p,rs,'bo')
    def mu_o(self,p,rs): return self._oil_prop(p,rs,'mu')
    def bg(self,p): return np.interp(np.asarray(p,float),self.gp,self.gbg)
    def mu_g(self,p): return np.interp(np.asarray(p,float),self.gp,self.gmu)
