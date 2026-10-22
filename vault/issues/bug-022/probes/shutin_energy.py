"""BUG-022: таблицы «Откуда тепло на останове» README 16 и 17 — члены баланса энергии по периодам.

Члены energy_balance.compute_balance (кумулятивные), приращения от конца добычи (15 сут)
до конца первых суток останова (16 сут) и до конца расчёта (30 сут); база и эмуляция плана.
Плюс член дегазации за добычу (0 → 15 сут). 4 значащие цифры — README даёт 3.
Запуск (из numerical_solver): .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\shutin_energy.py
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = r'''
import sys
sys.path.insert(0, r"{here}"); sys.path.insert(0, "examples")
import numpy as np, run_mains
run_mains.install_emulation("{v}")
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from energy_balance import compute_balance
DAY = 86400.0
keys = ("delta_E", "cum_adiab", "cum_deg", "cum_jt", "cum_conv", "cum_cond")
for name in ("16_well_shut_in", "17_shut_in_strong_cooling"):
    cfg = load_config(f"examples/{{name}}/config.json"); cfg.output.log_level = "ERROR"
    sim, init = SimulatorFactory.from_config(cfg); h = sim.run(init)
    bal = compute_balance(h, sim._grid, cfg)
    t = np.asarray(h.times) / DAY
    e = int(np.argmin(np.abs(t - 15.0))); d = int(np.argmin(np.abs(t - 16.0)))
    row = " ".join(f"{{k}}: {{bal[k][d] - bal[k][e]:+.4e}} / {{bal[k][-1] - bal[k][e]:+.4e}}" for k in keys)
    print(f"[{v}] {{name}}: сутки 16 / весь останов — {{row}}; дегазация за добычу {{bal['cum_deg'][e]:+.4e}}")
'''
lines = []
for v in ("0", "pv1e-8"):
    r = subprocess.run([sys.executable, "-c", CODE.format(here=HERE, v=v)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    lines += [ln for ln in r.stdout.splitlines() if ln.startswith("[")] or [r.stderr[-2000:]]
text = "\n".join(lines)
print(text)
(HERE / "shutin_energy.out.txt").write_text(text + "\n", encoding="utf-8")
