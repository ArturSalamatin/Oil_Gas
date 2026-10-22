"""BUG-022: один вызов _newton_fixed_active_set (набор фаз начального состояния — все без газа).

Фикстура Nabor_1b, отбор p_wf = 100 бар из 200 бар, N = 50, 8, 12, dt = 3600 и 300 с:
база против эмуляции плана (eps = 1e-8) — сошлось, итераций, мера по ячейкам, побитовость.
Числа тестов TestFixedActiveSet плана (раздел 1.10). Печатает и строки unit_check.py
(импорт исполняет его). Вывод — unit_newton_direct.out.txt.
Запуск (из numerical_solver): .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\unit_newton_direct.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import unit_check as u  # noqa: E402  (печатает свои строки)

lines = ["== прямой вызов _newton_fixed_active_set, набор фаз начального состояния"]
for n in (50, 8, 12):
    for dt in (3600.0, 300.0):
        u.use("0")
        m, s = u.build(n)
        za, ra = m._newton_fixed_active_set(m.pack(s), s, dt, s.gas_active)
        a = m.unpack(za, s.gas_active)
        u.use("pv1e-8")
        m2, s2 = u.build(n)
        zb, rb = m2._newton_fixed_active_set(m2.pack(s2), s2, dt, s2.gas_active)
        b = m2.unpack(zb, s2.gas_active)
        lines.append(f"N={n} dt={dt}: база сошлось {ra.converged} итераций {ra.iterations} мера "
                     f"{u.measure(m, s, a, dt):.3e}; 1e-8 сошлось {rb.converged} итераций {rb.iterations} "
                     f"мера {u.measure(m2, s2, b, dt):.3e}; побитово {np.array_equal(za, zb)}; "
                     f"max|dp| {np.max(np.abs(za[:n] - zb[:n])):.2e} бар")
        print(lines[-1], flush=True)
(HERE / "unit_newton_direct.out.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
