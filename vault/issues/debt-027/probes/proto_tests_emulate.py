"""DEBT-027, проба при /plan-improve: тесты шага 1 (tests/test_pvt_clamp.py прототипа) на эмулированной функции.

Фикстура прототипа tests/helpers.model_and_state (книга Nabor_1b.xlsx, 12 ячеек, p0 = 200 бар).
Ячейка 0 переводится в газовый режим при p = max p_b + 1 бар с S_g = 0 (ячейка фронта) или
S_g = 0.02 (свободный газ). Печать: max p_b, диапазон газовой таблицы, категории предупреждений.
Запуск из numerical_solver/HydroSolverPrototype/Prototype_1.0.3:
  ..\\..\\.venv\\Scripts\\python ..\\..\\..\\vault\\issues\\debt-027\\probes\\proto_tests_emulate.py
"""
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tests.helpers import model_and_state  # noqa: E402
import emulate_debt027 as emu  # noqa: E402

_, m, s = model_and_state(p0=200)
print(f"max p_b = {m.pvt.pb[-1]:g} бар, газовая таблица {m.pvt.gp[0]:g}–{m.pvt.gp[-1]:g} бар, "
      f"R_s ветвей {m.pvt.rs_values[0]:g}–{m.pvt.rs_values[-1]:g}, R_s0 = {s.rs_sm3_sm3[0]:g}")
print("исходное состояние:", [emu.warning_category(w) for w in emu.pvt_range_warnings(m, s)])
s.gas_active[0] = True
s.pressure_bar[0] = m.pvt.pb[-1] + 1.0
for sg in (0.0, 0.02):
    s.sg[0] = sg
    for fg in (None, 1e-6):
        w = emu.pvt_range_warnings(m, s, free_gas_sg=fg)
        print(f"S_g = {sg:g}, free_gas_sg = {fg}: {[x for x in w if x.startswith('OIL_PVT saturated locus above')]}")
a = 'OIL_PVT branch pressure above supplied range by up to 1 bar. Endpoint branch property used; no extrapolation.'
b = 'OIL_PVT branch pressure above supplied range by up to 2 bar. Endpoint branch property used; no extrapolation.'
print("категории:", emu.warning_category(a) == emu.warning_category(b), emu.warning_category(a))
