"""BUG-022, аудит раунд 2: число для теста проверки на старте (_newton_fixed_active_set, :327).

Nabor_1b, N = 12, dt = 3600 с: решение базы z_base (абсолютный критерий выполнен за 2 итерации,
мера ячеек 2.33e-8 > 1e-8). Старт Ньютона с z_base при atol_sm3s = 1e-6 — абсолютный критерий
выполнен сразу: без условия — 0 итераций; с условием (эмуляция плана, 1e-8) — итерации до
меры <= 1e-8. Вывод — unit_start.out.txt.
Запуск (из numerical_solver): .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\unit_start.py
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import unit_check as u  # noqa: E402  (печатает свои строки)

DT = 3600.0
u.use("0")
m, s = u.build(12)
z_base, r_base = m._newton_fixed_active_set(m.pack(s), s, DT, s.gas_active)
mb = u.measure(m, s, m.unpack(z_base, s.gas_active), DT)
rows = [f"база N=12: итераций {r_base.iterations}, мера {mb:.3e}"]
for v in ("0", "pv1e-8"):
    u.use(v)
    m2, s2 = u.build(12)
    z, rep = m2._newton_fixed_active_set(z_base.copy(), s2, DT, s2.gas_active, atol_sm3s=1e-6)
    rows.append(f"[{v}] старт с z_base, atol 1e-6: сошлось {rep.converged}, итераций {rep.iterations}, "
                f"мера {u.measure(m2, s2, m2.unpack(z, s2.gas_active), DT):.3e}, побитово z_base {np.array_equal(z, z_base)}")
text = "\n".join(rows)
print(text)
(HERE / "unit_start.out.txt").write_text(text + "\n", encoding="utf-8")
