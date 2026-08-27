import unittest
from tests.helpers import model_and_state
from radial_blackoil.schedule import Schedule,ScheduleRow
from radial_blackoil.simulation import simulate_schedule

class MaterialBalanceTests(unittest.TestCase):
    def _hist(self):
        _,m,s=model_and_state(n=6,p0=200,bhp=150); sch=Schedule([ScheduleRow(0,'BHP',150),ScheduleRow(.02,'BHP',150)],.02); return simulate_schedule(m,s,sch,60,1e-5,300)
    def test_material_balance_records_initial_and_final(self): h=self._hist(); self.assertEqual(len(h.material_balance),2); self.assertEqual(h.material_balance[0]['time_day'],0)
    def test_oil_balance_small(self): h=self._hist(); self.assertLess(abs(h.material_balance[-1]['oil_balance_error_pct_initial']),1e-5)
    def test_gas_balance_small(self): h=self._hist(); self.assertLess(abs(h.material_balance[-1]['gas_balance_error_pct_initial']),1e-5)
    def test_gas_inventory_breakdown_sums(self): h=self._hist(); x=h.material_balance[-1]; self.assertAlmostEqual(x['gas_current_total_sm3'],x['gas_current_dissolved_sm3']+x['gas_current_free_sm3'],10)

if __name__=='__main__': unittest.main()
