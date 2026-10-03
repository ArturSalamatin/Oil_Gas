import unittest, numpy as np
from tests.helpers import model_and_state

# DEBT-036: component_inventories needs Bo and Bg only, and the inventories of the old state are
# computed once per step (_old_inventories).  Both must leave the residual bitwise unchanged: the
# Newton steps and the prototype regression against golden/ (abs 2e-7 / rel 2e-10) depend on it.
def _mixed_state(n=9):
    """Fixture Nabor_1b at p0 = 160 bar: cells 0-3 two-phase (Sg = 0.03, Rs = Rs_sat(p)), the rest oil only."""
    _,m,s=model_and_state(n=n,p0=160); mask=np.zeros(n,bool); mask[:4]=True
    s.gas_active=mask; s.sg[:4]=0.03; s.rs_sm3_sm3[:4]=m.pvt.rs_sat(s.pressure_bar[:4])
    return m,s,mask

class _NoViscosityPVT:
    """The model's PVT without viscosities: a call of mu_o, mu_g or bo_mu_o fails the test."""
    def __init__(self,pvt): self._pvt=pvt
    def __getattr__(self,name):
        if name in ('mu_o','mu_g','bo_mu_o'): raise AssertionError(f'inventories called {name}')
        return getattr(self._pvt,name)

class InventoriesTests(unittest.TestCase):
    def test_inventories_without_viscosities(self):
        # Bo and Bg only: with a PVT that has no viscosities the inventories are still computed and
        # equal bitwise pv*So/Bo, pv*(Rs*So/Bo + Sg/Bg) with the model's own Bo, Bg
        m,s,_=_mixed_state(); p,rs,sg=s.pressure_bar,s.rs_sm3_sm3,s.sg
        pv=m.rock.pore_volume_m3(m.grid.bulk_volumes_m3,p); bo=m.pvt.bo(p,rs); bg=m.pvt.bg(p)
        m.pvt=_NoViscosityPVT(m.pvt); oi,gi=m.component_inventories(s)
        self.assertEqual(oi.tobytes(),(pv*(1.0-sg)/bo).tobytes()); self.assertEqual(gi.tobytes(),(pv*(rs*(1.0-sg)/bo+sg/bg)).tobytes())

if __name__=='__main__': unittest.main()
