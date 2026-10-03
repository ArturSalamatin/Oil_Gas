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
        self._build_interp_tables()

    def rs_sat(self,p):
        return np.interp(np.asarray(p,float),self.pb,self.rs_values)
    def pb_of_rs(self,rs):
        return np.interp(np.asarray(rs,float),self.rs_values,self.pb)
    def max_pressure_of_rs(self,rs):
        rr=np.clip(np.asarray(rs,float),self.rs_values[0],self.rs_values[-1])
        tops=np.array([self.branches[r][-1][0] for r in self.rs_values],float)
        return np.interp(rr,self.rs_values,tops)
    def _build_interp_tables(self):
        """DEBT-036: tables of _oil_props, all cells at once (bitwise the former per-segment np.interp)."""
        # Bo, mu_o interpolate between two Rs branches; with one branch the former code divided 0/0
        if self.rs_values.size<2: raise ValueError(f'OIL_PVT needs >=2 Rs branches, got {self.rs_values.size}')
        # Row i of branch k: (x_i, Bo_i, Bo slope, mu_i, mu slope) on [x_i, x_i+1], x = p - Pb of the
        # branch; the slopes are np.interp's own (y[i+1]-y[i])/(x[i+1]-x[i]).  The last row of a branch
        # and the padding of shorter branches are its top: (x_last, Bo_last, 0, mu_last, 0).
        br=[self._branch_arrays[float(r)] for r in self.rs_values]
        m=max(x.size for x,_,_ in br); rows=np.zeros((len(br),m,5))
        for k,(x,bo,mu) in enumerate(br):
            L=x.size
            rows[k,:,0]=x[-1]; rows[k,:,1]=bo[-1]; rows[k,:,3]=mu[-1]
            rows[k,:L,0]=x; rows[k,:L,1]=bo; rows[k,:L,3]=mu
            rows[k,:L-1,2]=(bo[1:]-bo[:-1])/(x[1:]-x[:-1]); rows[k,:L-1,4]=(mu[1:]-mu[:-1])/(x[1:]-x[:-1])
        self._rows=rows; self._x_top=rows[:,-1,0]
        # Union U of the knots of all branches.  No knot of any branch lies inside [U_u, U_u+1), so
        # for dp there the row of branch k is fixed: _row_of[k,u] = count(x_k <= U_u) - 1.  One
        # exact searchsorted over U replaces a search per branch.
        self._x_union=np.unique(np.concatenate([x for x,_,_ in br]))
        self._row_of=np.array([np.searchsorted(x,self._x_union,side='right')-1 for x,_,_ in br])
        # Segment j = [Rs_j, Rs_j+1]: (Rs_j, Rs_j+1 - Rs_j, Pb_j, Pb_j+1 - Pb_j), the differences
        # the per-segment loop formed
        rs,pb=self.rs_values,self.pb
        self._segments=np.stack([rs[:-1],rs[1:]-rs[:-1],pb[:-1],pb[1:]-pb[:-1]],axis=1)
    _BO=(1,2); _MU=(3,4)   # (value, slope) columns of _rows for Bo and mu_o
    def _oil_props(self,p,rs,columns):
        """PVTO oil properties of all cells at once, one per (value, slope) column pair of _rows (DEBT-036)."""
        p_arr,rs_arr=np.broadcast_arrays(np.asarray(p,float),np.asarray(rs,float))
        shape=p_arr.shape; pf=p_arr.ravel(); rf=rs_arr.ravel()
        # PVTO is evaluated from fixed-Rs branches. At p below Pb(Rs), the
        # branch is clamped to its first (saturated) point. For a gas-active
        # state Rs=Rs_sat(p), this is exactly the saturated locus. This
        # extension is also important for a fixed-active-set Newton trial that
        # temporarily crosses the phase boundary before the active set switches.
        # Explicit endpoint clamp in Rs; no extrapolation between/above PVTO branches.
        rr=np.clip(rf,self.rs_values[0],self.rs_values[-1])
        j=np.searchsorted(self.rs_values,rr,side='right')-1
        j=np.clip(j,0,len(self.rs_values)-2)
        # Rs weight and Pb(Rs) on the segment of each cell, as the per-segment loop formed them
        seg=self._segments[j]
        w=(rr-seg[:,0])/seg[:,1]
        dp=np.maximum(pf-(seg[:,2]+w*seg[:,3]),0.0)
        # dp >= 0 = U_0, so u >= 0; NaN sorts last and stays NaN through the formula below
        u=np.searchsorted(self._x_union,dp,side='right')-1
        sides=[]
        for k in (j,j+1):
            row=self._rows[k,self._row_of[k,u]]; top=dp>=self._x_top[k]
            # np.interp: slope*(x - x_i) + y_i inside the branch, its last value at and above the top
            sides.append([np.where(top,row[:,cy],row[:,cs]*(dp-row[:,0])+row[:,cy]) for cy,cs in columns])
        return [(v0+w*(v1-v0)).reshape(shape) for v0,v1 in zip(*sides)]
    def bo(self,p,rs): return self._oil_props(p,rs,(self._BO,))[0]
    def mu_o(self,p,rs): return self._oil_props(p,rs,(self._MU,))[0]
    def bg(self,p): return np.interp(np.asarray(p,float),self.gp,self.gbg)
    def mu_g(self,p): return np.interp(np.asarray(p,float),self.gp,self.gmu)
