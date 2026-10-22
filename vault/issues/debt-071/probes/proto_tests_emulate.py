"""DEBT-071: тесты прототипа шага 1 плана на функции плана, подставленной в памяти.

Тела тестов — дословно из плана (шаг 1, п. 3), relperm_range_warnings — копия кода плана
(standing_relperm_scan.relperm_range_warnings). Запуск из
numerical_solver/HydroSolverPrototype/Prototype_1.0.3:
    ..\\..\\.venv\\Scripts\\python ..\\..\\..\\vault\\issues\\debt-071\\probes\\proto_tests_emulate.py
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import radial_blackoil.diagnostics as diag  # noqa: E402
import radial_blackoil  # noqa: E402
from tests.helpers import model_and_state  # noqa: E402

# standing_relperm_scan импортирует gpn_multiphase_solver — он в том же venv
from standing_relperm_scan import relperm_range_warnings  # noqa: E402

diag.relperm_range_warnings = relperm_range_warnings
from radial_blackoil.diagnostics import pvt_range_warnings, warning_category  # noqa: E402

print(f"прототип: {Path(radial_blackoil.__file__).parent}")


class PlanTests(unittest.TestCase):
    # ── Дословно из плана, шаг 1, п. 3 ──
    # DEBT-071 (GPN project): the relperm part of the range check is callable alone -- the GPN
    # adapter on the Standing correlation path has a relperm table but no PVT tables (no gp).
    def test_relperm_warnings_close_pvt_range_warnings(self):
        _,m,s=model_and_state(p0=350); s.sg[0]=0.9; w=pvt_range_warnings(m,s); r=relperm_range_warnings(m,s)
        self.assertEqual(r,['RELPERM Sg above table: max Sg=0.9, table max=0.85. Endpoint value used; no extrapolation.'])
        self.assertEqual(w[-1:],r); self.assertTrue(any(x.startswith('GAS_PVT pressure above') for x in w))
    def test_relperm_warnings_need_no_pvt(self):
        _,m,s=model_and_state(); s.sg[0]=-0.01; stub=SimpleNamespace(relperm=m.relperm)
        self.assertEqual([warning_category(x) for x in relperm_range_warnings(stub,s)],['RELPERM Sg below table'])
        with self.assertRaises(AttributeError): pvt_range_warnings(stub,s)


if __name__ == "__main__":
    unittest.main()
