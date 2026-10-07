"""DEBT-036, верификация плана: код шагов плана подменой методов в памяти (файлы прототипа не меняются).

Запуск — из каталога numerical_solver, код которого проверяется (основного или worktree):
    $P = "d:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\vault\\issues\\debt-036\\probes"
    .venv\\Scripts\\python $P\\planned_code_check.py unit [--planned]    # B_o, μ_o побитово против прежнего цикла, все таблицы проекта
    .venv\\Scripts\\python $P\\planned_code_check.py cache [--planned]   # кеш запасов старого состояния
    .venv\\Scripts\\python $P\\planned_code_check.py bench               # время невязки на состояниях Ньютона 14, 04, 20 по этапам
    .venv\\Scripts\\python $P\\planned_code_check.py history [пример ...] # истории: исходный код против кода плана, время
    .venv\\Scripts\\python $P\\planned_code_check.py proto_tests         # тесты прототипа с кодом плана

--planned: проверять код плана (подмена в памяти); без ключа — код из файлов (после реализации).
Этапы (шаги плана): 1 — запасы без μ; 2 — запасы старого состояния один раз на шаг;
3 — интерполяция PVTO массивами; 4 — B_o и μ_o за один проход. DEBT036_VARIANTS (по умолчанию 1234).
"""
import os
import sys
import time
from pathlib import Path

import numpy as np

SOLVER_ROOT = Path.cwd()
if not (SOLVER_ROOT / "gpn_multiphase_solver").is_dir():
    raise SystemExit("запускать из каталога numerical_solver (основного или worktree)")
# DEBT036_PROTO — другой каталог прототипа (копия с применённым планом, apply_plan.py); по умолчанию — дерева запуска
PROTO = Path(os.environ.get("DEBT036_PROTO") or SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")
sys.path.insert(0, str(PROTO))
sys.path.insert(0, str(SOLVER_ROOT))

import radial_blackoil.blackoil as B  # noqa: E402
import radial_blackoil.pvt as PV  # noqa: E402
import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory, _read_oil_pvt_csv, _read_gas_pvt_csv  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from radial_blackoil.input_reader import load_input  # noqa: E402

print("код:", Path(B.__file__).parent, "|", Path(gpn_multiphase_solver.__file__).parent, flush=True)

M = B.RadialBlackOilModel
PVT = PV.BlackOilPVT
CP_TO_PA_S = B.CP_TO_PA_S


# ── Эталон: прежний _oil_prop (pvt.py:40-64 на c1f18ab), дословно ──
def ref_branch_prop_delta(self, rs_branch, delta_p, which):
    x,bo,mu=self._branch_arrays[float(rs_branch)]
    return np.interp(delta_p,x,bo if which=='bo' else mu)


def ref_oil_prop(self,p,rs,which):
    p_arr,rs_arr=np.broadcast_arrays(np.asarray(p,float),np.asarray(rs,float))
    shape=p_arr.shape; pf=p_arr.ravel(); rf=rs_arr.ravel(); out=np.empty_like(pf,dtype=float)
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
        v0=ref_branch_prop_delta(self,r0,dp,which); v1=ref_branch_prop_delta(self,r1,dp,which)
        out[ids]=v0+w*(v1-v0)
    return out.reshape(shape)


# ── Код плана, шаг 4–5: pvt.py ──
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


_BO, _MU = (1, 2), (3, 4)   # (value, slope) columns of _rows


def _oil_props(self,p,rs,columns):
    """PVTO oil properties of all cells at once, one per (value, slope) column pair of _rows (DEBT-036)."""
    p_arr,rs_arr=np.broadcast_arrays(np.asarray(p,float),np.asarray(rs,float))
    shape=p_arr.shape; pf=p_arr.ravel(); rf=rs_arr.ravel()
    rr=np.clip(rf,self.rs_values[0],self.rs_values[-1])
    j=np.searchsorted(self.rs_values,rr,side='right')-1
    j=np.clip(j,0,len(self.rs_values)-2)
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


def plan_oil_prop(self,p,rs,which): return _oil_props(self,p,rs,(_BO if which=='bo' else _MU,))[0]
def plan_bo(self,p,rs): return _oil_props(self,p,rs,(_BO,))[0]
def plan_mu_o(self,p,rs): return _oil_props(self,p,rs,(_MU,))[0]
def plan_bo_mu_o(self,p,rs):
    bo,mu=_oil_props(self,p,rs,(_BO,_MU)); return bo,mu


# ── Код плана, шаги 2–3, 5: blackoil.py ──
def plan_component_inventories(self,state):
    p,sg=state.pressure_bar,state.sg; so=1.0-sg
    # DEBT-036: Bo and Bg only; oil_properties/gas_properties would evaluate mu_o, mu_g as well
    bo=self.pvt.bo(p,state.rs_sm3_sm3); bg=self.pvt.bg(p)
    pv=self.rock.pore_volume_m3(self.grid.bulk_volumes_m3,p)
    return pv*so/bo, pv*(state.rs_sm3_sm3*so/bo+sg/bg)


def plan_old_inventories(self,state_old):
    """Inventories of state_old, recomputed only when its p, Rs or Sg change (DEBT-036)."""
    key=(state_old.pressure_bar.tobytes(),state_old.rs_sm3_sm3.tobytes(),state_old.sg.tobytes())
    c=getattr(self,'_old_inventories_cache',None)
    if c is None or c[0]!=key:
        c=self._old_inventories_cache=(key,)+tuple(self.component_inventories(state_old))
    return c[1],c[2]


def plan_physical_residual(self,z,state_old,dt_s,gas_active):
    new=self.unpack(z,gas_active); oi1,gi1=self.component_inventories(new); oi0,gi0=self._old_inventories(state_old); qo,qg=self.net_component_outflow(new)
    return np.concatenate([(oi1-oi0)/float(dt_s)+qo,(gi1-gi0)/float(dt_s)+qg])


def plan_mobilities(self,p,rs,sg):
    p=np.asarray(p,float); rs=np.asarray(rs,float); sg=np.asarray(sg,float)
    bo_mu_o=getattr(self.pvt,'bo_mu_o',None)
    bo,muo=bo_mu_o(p,rs) if bo_mu_o is not None else (self.pvt.bo(p,rs),self.pvt.mu_o(p,rs))
    bg=self.pvt.bg(p); mug=self.pvt.mu_g(p)
    return self.relperm.kro(sg)/(muo*CP_TO_PA_S)/bo, self.relperm.krg(sg)/(mug*CP_TO_PA_S)/bg


# После шага 4 плана _oil_prop в файлах нет: getattr с None, иначе проба падает при импорте
ORIG = {name: getattr(PVT, name, None) for name in ("__init__", "_oil_prop", "bo", "mu_o")}
ORIG.update({name: getattr(M, name) for name in ("component_inventories", "physical_residual", "_phase_mobilities_surface")})
PLANNED = [False]


def _init_with_tables(self, *a, **k):
    ORIG["__init__"](self, *a, **k); _build_interp_tables(self)


def patch(variants):
    """Код плана для этапов variants ("" — исходный код файлов)."""
    v = set(variants); PLANNED[0] = bool(v)
    PVT.__init__ = _init_with_tables if v & {"3", "4"} else ORIG["__init__"]
    M.component_inventories = plan_component_inventories if "1" in v else ORIG["component_inventories"]
    M.physical_residual = plan_physical_residual if "2" in v else ORIG["physical_residual"]
    if "2" in v: M._old_inventories = plan_old_inventories
    elif hasattr(M, "_old_inventories") and M._old_inventories is plan_old_inventories: del M._old_inventories
    if "3" in v:
        PVT._oil_prop, PVT.bo, PVT.mu_o = plan_oil_prop, plan_bo, plan_mu_o
    else:
        PVT.bo, PVT.mu_o = ORIG["bo"], ORIG["mu_o"]
        if ORIG["_oil_prop"] is not None: PVT._oil_prop = ORIG["_oil_prop"]
        elif "_oil_prop" in PVT.__dict__: del PVT._oil_prop
    if "4" in v:
        PVT.bo_mu_o = plan_bo_mu_o; M._phase_mobilities_surface = plan_mobilities
    else:
        if getattr(PVT, "bo_mu_o", None) is plan_bo_mu_o: del PVT.bo_mu_o
        M._phase_mobilities_surface = ORIG["_phase_mobilities_surface"]


def ensure_tables(pvt):
    if PLANNED[0] and isinstance(pvt, PVT) and not hasattr(pvt, "_rows"): _build_interp_tables(pvt)


def bits(a):
    a = np.ascontiguousarray(np.asarray(a, float)); return a.shape, a.tobytes()


def variants_env():
    return os.environ.get("DEBT036_VARIANTS", "1234")


# ── unit: B_o, μ_o побитово против прежнего цикла на всех таблицах проекта ──
def all_tables():
    for d in sorted((SOLVER_ROOT / "examples").iterdir()):
        if (d / "oil_pvt.csv").is_file():
            yield d.name, PVT(_read_oil_pvt_csv(d / "oil_pvt.csv"), _read_gas_pvt_csv(d / "gas_pvt.csv"))
    for f in sorted((PROTO / "regression" / "inputs").glob("*.xlsx")) + sorted((PROTO / "tests" / "fixtures").glob("*.xlsx")):
        yield f.name, load_input(f).pvt
    gas = [(1.0, 0.9, 0.011), (400.0, 0.003, 0.03)]
    # Ветвь из одной строки (CSV-путь фабрики это не запрещает): np.interp по одной точке
    yield "ветвь из 1 строки", PVT([(0, 20, 1.05, 3.0), (0, 80, 1.04, 3.1), (30, 120, 1.2, 1.5), (60, 170, 1.3, 1.2), (60, 260, 1.28, 1.4)], gas)
    # Ветви 2…8 строк с неравными шагами: узлы разных ветвей перемежаются (таблица теста плана)
    rng = np.random.default_rng(7); rows = []
    for k, rs in enumerate((0.0, 15.0, 40.0, 41.5, 90.0, 150.0, 260.0)):
        pb = 20.0 + 1.1 * rs; d = np.concatenate([[0.0], np.cumsum(rng.uniform(3.0, 40.0, k + 1))])
        rows += [(rs, pb + x, 1.05 + 0.0012 * rs - 1e-4 * x, 2.0 - 0.004 * rs + 3e-3 * x) for x in d]
    yield "неравные ветви 2–8 строк", PVT(rows, gas)


def test_points(pvt, rng):
    rs_v = pvt.rs_values; lo, hi = rs_v[0], rs_v[-1]
    rs_pts = np.concatenate([rs_v, 0.5 * (rs_v[1:] + rs_v[:-1]), np.nextafter(rs_v, np.inf), np.nextafter(rs_v, -np.inf),
                             [lo - 5.0, hi + 5.0, 0.0], rng.uniform(lo - 5.0, hi + 5.0, 60)])
    knots = np.concatenate([np.array([r[0] for r in pvt.branches[float(k)]]) for k in rs_v])
    tops = np.array([pvt.branches[float(k)][-1][0] for k in rs_v])
    p_pts = np.concatenate([knots, np.nextafter(knots, np.inf), np.nextafter(knots, -np.inf), 0.5 * (knots[1:] + knots[:-1]),
                            tops + 10.0, [1.0, 1e-3, knots.max() + 500.0], rng.uniform(1.0, knots.max() + 50.0, 300)])
    P, R = np.meshgrid(p_pts, rs_pts)
    pr = rng.uniform(1.0, knots.max() + 50.0, 100000); rr = rng.uniform(lo - 5.0, hi + 5.0, 100000)
    # NaN в p и в Rs: прежний код даёт NaN, новый — тот же NaN; +inf и 1e300 — верх ветви
    return (np.concatenate([P.ravel(), pr, [np.nan, 100.0, np.nan, np.inf, 1e300]]),
            np.concatenate([R.ravel(), rr, [lo, np.nan, np.nan, lo, hi]]))


def unit():
    rng = np.random.default_rng(36); total = 0; ntab = 0
    for name, pvt in all_tables():
        ensure_tables(pvt)
        p, rs = test_points(pvt, rng)
        ref_bo, ref_mu = ref_oil_prop(pvt, p, rs, "bo"), ref_oil_prop(pvt, p, rs, "mu")
        with np.errstate(invalid="ignore"):   # 0*inf в отброшенной ветви np.where при p = inf
            bo, mu = pvt.bo(p, rs), pvt.mu_o(p, rs)
            assert bits(bo) == bits(ref_bo), f"{name} bo: max|Δ| {np.nanmax(np.abs(bo - ref_bo))}"
            assert bits(mu) == bits(ref_mu), f"{name} mu: max|Δ| {np.nanmax(np.abs(mu - ref_mu))}"
            if hasattr(pvt, "bo_mu_o"):
                bo2, mu2 = pvt.bo_mu_o(p, rs); assert bits(bo2) == bits(ref_bo) and bits(mu2) == bits(ref_mu)
        # Скаляр, 0-d, пустой массив: форма и значения как у прежнего
        for ps, rss in ((float(p[7]), float(rs[7])), (np.float64(p[9]), np.array(rs[9]))):
            assert bits(ref_oil_prop(pvt, ps, rss, "bo")) == bits(pvt.bo(ps, rss))
        assert pvt.mu_o(np.empty(0), np.empty(0)).shape == (0,)
        # Двумерный вход и разные формы (скаляр p, массив Rs — так зовёт two_phase_analytics.py)
        for ps, rss in ((p[:12].reshape(3, 4), rs[:12].reshape(3, 4)), (float(p[5]), rs[:20]), (p[:20], float(rs[3]))):
            assert bits(ref_oil_prop(pvt, ps, rss, "mu")) == bits(pvt.mu_o(ps, rss))
        nb = [len(pvt.branches[float(k)]) for k in pvt.rs_values]
        total += p.size; ntab += 1
        print(f"  {name}: ветвей {len(nb)} (строк {min(nb)}–{max(nb)}), точек {p.size}: побитово")
    print(f"unit: OK, таблиц {ntab}, точек {total}, код {'плана' if PLANNED[0] else 'файлов'}")


# ── cache: запасы старого состояния ──
def proto_helpers():
    # tests — пакет и у numerical_solver, и у прототипа: прототип первым в sys.path
    sys.path.insert(0, str(PROTO)); sys.modules.pop("tests", None)
    cwd = os.getcwd(); os.chdir(PROTO)
    try:
        from tests.helpers import model_and_state
    finally:
        os.chdir(cwd)
    return model_and_state


def cache():
    model_and_state = proto_helpers()
    _, m, s = model_and_state(n=9, p0=160)
    mask = np.zeros(9, bool); mask[:4] = True
    s.gas_active = mask; s.sg[:4] = 0.03; s.rs_sm3_sm3[:4] = m.pvt.rs_sat(s.pressure_bar[:4])
    z = m.pack(s, mask); ensure_tables(m.pvt)
    ref = lambda zz, st: ORIG["physical_residual"](m, zz, st, 60.0, mask)
    # Ссылка — исходная невязка с исходными запасами: подмена отключается на время вызова
    def ref_call(zz, st):
        saved = (M.component_inventories, M.physical_residual)
        M.component_inventories, M.physical_residual = ORIG["component_inventories"], ORIG["physical_residual"]
        try: return ref(zz, st)
        finally: M.component_inventories, M.physical_residual = saved
    for d in (0.0, 1e-3, -2e-3):
        assert bits(m.physical_residual(z + d, s, 60.0, mask)) == bits(ref_call(z + d, s))
    calls = [0]; inner = M.component_inventories
    def counting(self, st): calls[0] += 1; return inner(self, st)
    M.component_inventories = counting
    try:
        for d in (0.0, 1e-3, -2e-3): m.physical_residual(z + d, s, 60.0, mask)
    finally:
        M.component_inventories = inner
    s.pressure_bar[2] += 0.7   # изменение на месте — запасы должны пересчитаться
    stale = bits(m.physical_residual(z, s, 60.0, mask)) != bits(ref_call(z, s))
    print(f"cache: невязка побитово; component_inventories за 3 вызова невязки — {calls[0]} раз "
          f"(без кеша 6, с кешем 3); после изменения state_old на месте — {'УСТАРЕВШЕЕ' if stale else 'пересчитано'}")
    a = np.random.default_rng(1).uniform(50, 300, 350); b = a.copy(); c = a.copy()
    t = time.perf_counter()
    for _ in range(20000): (a.tobytes(), b.tobytes(), c.tobytes()) == (a.tobytes(), b.tobytes(), c.tobytes())
    print(f"cache: ключ — 3 tobytes и сравнение при N = 350: {(time.perf_counter() - t) / 20000 * 1e6 / 2:.1f} мкс")


# ── bench: время невязки на состояниях Ньютона по этапам ──
class _Captured(Exception):
    pass


def capture(ex, k):
    patch(""); orig = M.residual; cnt = [0]; box = {}
    def res(self, z, state_old, dt_s, gas_active):
        cnt[0] += 1
        if cnt[0] == k:
            box.update(m=self, z=np.array(z, float), s=state_old.copy(), dt=dt_s, mask=np.array(gas_active, bool))
            raise _Captured
        return orig(self, z, state_old, dt_s, gas_active)
    M.residual = res
    try:
        cfg = load_config(SOLVER_ROOT / "examples" / ex / "config.json")
        sim, s0 = SimulatorFactory.from_config(cfg)
        try: sim.run(s0)
        except _Captured: pass
    finally:
        M.residual = orig
    if not box: raise SystemExit(f"{ex}: вызовов residual {cnt[0]} < {k}")
    return box


def timeit(f, reps=300):
    f(); ts = []
    for _ in range(reps):
        t = time.perf_counter(); f(); ts.append(time.perf_counter() - t)
    return float(np.median(ts))


def bench():
    for ex, k in (("14_high_gor_cooling", 8000), ("04_table_table", 600), ("20_rs300_cooling", 3000)):
        b = capture(ex, k); m = b["m"]; n = m.grid.n
        line = f"{ex} (N = {n}, двухфазных {int(b['mask'].sum())}, вызов {k}):"; ref = None
        for label, v in (("исходный", ""), ("1", "1"), ("1+2", "12"), ("1+2+3", "123"), ("1+2+3+4", "1234")):
            patch(v); ensure_tables(m.pvt); m._old_inventories_cache = None
            f = lambda: m.residual(b["z"], b["s"], b["dt"], b["mask"])
            r = f(); ref = r if ref is None else ref
            line += f" {label} {timeit(f) * 1e3:.3f} мс{'' if bits(r) == bits(ref) else ' (НЕ побитово)'};"
        if isinstance(m.pvt, PVT):
            st = m.unpack(b["z"], b["mask"]); p, rs = st.pressure_bar, st.rs_sm3_sm3
            patch(""); t_old = timeit(lambda: m.pvt.bo(p, rs)); s_old = timeit(lambda: m.pvt.bo(float(p[0]), float(rs[0])))
            patch("34"); ensure_tables(m.pvt)
            t_new = timeit(lambda: m.pvt.bo(p, rs)); t_both = timeit(lambda: m.pvt.bo_mu_o(p, rs))
            s_new = timeit(lambda: m.pvt.bo(float(p[0]), float(rs[0])))
            line += (f" bo при N: {t_old * 1e6:.0f} → {t_new * 1e6:.0f} мкс, bo_mu_o {t_both * 1e6:.0f} мкс; "
                     f"скаляр {s_old * 1e6:.0f} → {s_new * 1e6:.0f} мкс")
        patch("")
        print(line, flush=True)


# ── history: истории примеров, исходный код против кода плана ──
def run(ex):
    cfg = load_config(SOLVER_ROOT / "examples" / ex / "config.json")
    sim, s0 = SimulatorFactory.from_config(cfg)
    t = time.perf_counter(); h = sim.run(s0); wall = time.perf_counter() - t
    arrays = [np.array([getattr(s, f) for s in h.states]) for f in ("p", "Sg", "Rs", "T", "regime")]
    arrays += [np.array(h.times), np.array([r.G_o for r in h.hydro_results[1:]]), np.array([r.G_g for r in h.hydro_results[1:]])]
    return arrays, wall


def all_examples():
    return sorted(d.name for d in (SOLVER_ROOT / "examples").iterdir() if (d / "config.json").is_file())


def history(examples, variants):
    print(f"этапы: {variants}", flush=True)
    for ex in examples:
        patch(""); a, w0 = run(ex)
        patch(variants); b, w1 = run(ex)
        patch("")
        same = all(x.shape == y.shape and bits(x) == bits(y) for x, y in zip(a, b))
        print(f"{ex}: истории {'побитово' if same else 'РАЗЛИЧИЕ'}; время {w0:.2f} → {w1:.2f} с (×{w0 / w1:.2f})", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "unit"
    rest = [a for a in sys.argv[2:] if not a.startswith("--")]
    if "--planned" in sys.argv: patch(variants_env())
    if cmd == "unit":
        unit()
    elif cmd == "cache":
        cache()
    elif cmd == "bench":
        bench()
    elif cmd == "history":
        history(rest or all_examples(), variants_env())
    elif cmd == "planned_tests":
        # Тесты плана (planned_tests/*.py) на коде плана (--planned) или на коде файлов
        import unittest
        sys.path.insert(0, str(PROTO)); sys.modules.pop("tests", None); os.chdir(PROTO)
        import tests.helpers  # noqa: F401  — пакет tests прототипа до загрузки файлов плана
        here = Path(__file__).resolve().parent / "planned_tests"
        suite = unittest.defaultTestLoader.discover(str(here), top_level_dir=str(here))
        r = unittest.TextTestRunner(verbosity=2).run(suite)
        print(f"planned_tests ({'код плана' if PLANNED[0] else 'код файлов'}): запущено {r.testsRun}, "
              f"ошибок {len(r.errors)}, отказов {len(r.failures)}")
    elif cmd == "proto_tests":
        import unittest
        patch(variants_env())
        sys.path.insert(0, str(PROTO)); sys.modules.pop("tests", None); os.chdir(PROTO)
        r = unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.discover("tests"))
        print(f"proto_tests: запущено {r.testsRun}, ошибок {len(r.errors)}, отказов {len(r.failures)}")
    else:
        raise SystemExit("использование: unit | cache | bench | history [пример ...] | proto_tests  [--planned]")
