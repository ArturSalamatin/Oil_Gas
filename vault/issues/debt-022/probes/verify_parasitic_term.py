"""Аудит DEBT-022: действительно ли `T*dPhi_dr` — причина расхождения 1.11 К?

План утверждает: ОДУ расходится с ядром на 1.111 К (пример 03), и причина —
дивергентная правая часть, в которой есть член T*dPhi_dr, отсутствующий в
адвективной постановке.

ПРОВЕРКА. Решить то же ОДУ ДВАЖДЫ: как есть (с T*dPhi_dr) и без этого члена.
Если план прав, вторая версия должна быть заметно ближе к ядру.

Это не проверка «формула верна» — это проверка причинно-следственной связи,
на которой стоит решение об удалении. Если убрать T*dPhi_dr и согласие НЕ
улучшится, значит причина расхождения другая, и вывод плана неверен.
"""
import sys
from pathlib import Path
import numpy as np

EX = Path(r"D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\examples")
sys.path.insert(0, str(EX))
sys.path.insert(0, str(EX / "03_standing_corey"))
_PROTO = EX.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO) not in sys.path:
    sys.path.insert(0, str(_PROTO))

import temperature_ode as tode
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory

cfg = load_config(EX / "03_standing_corey" / "config.json")
cfg.output.log_level = "ERROR"
sim, initial = SimulatorFactory.from_config(cfg)
history = sim.run(initial)
grid, solver = sim._grid, sim._energy

STEP = 24
r_c = grid.r_centers
T_num = history.states[STEP].T

# ── Как есть (дивергентная, с T*dPhi_dr) ──
sols = tode.solve_ode_at_steps(history, cfg, grid, solver, steps=[STEP])
r_o, T_o = sols[STEP]
err_div = np.max(np.abs(T_num - np.interp(r_c, r_o, T_o)))

# ── Без T*dPhi_dr: патчим интерполянт Phi так, чтобы производная = 0 ──
# solve_ode_at_steps берёт dPhi_dr как ip['Phi'](x, 1)/r. Подменяем объект
# Phi на обёртку, которая возвращает значение как есть, а производную — ноль.
_orig_build = tode._build_interpolants

class _ZeroDerivPhi:
    def __init__(self, inner):
        self._inner = inner
    def __call__(self, x, nu=0):
        if nu == 0:
            return self._inner(x)
        return np.zeros_like(np.asarray(x, dtype=float))

def _patched(*a, **kw):
    ip = _orig_build(*a, **kw)
    ip = dict(ip)
    ip['Phi'] = _ZeroDerivPhi(ip['Phi'])
    return ip

tode._build_interpolants = _patched
sols2 = tode.solve_ode_at_steps(history, cfg, grid, solver, steps=[STEP])
tode._build_interpolants = _orig_build
r_a, T_a = sols2[STEP]
err_adv = np.max(np.abs(T_num - np.interp(r_c, r_a, T_a)))

print(f"\nПример 03, шаг {STEP}")
print(f"  ОДУ как есть (с T*dPhi_dr):      max|dT| = {err_div:.4f} K")
print(f"  ОДУ без T*dPhi_dr:               max|dT| = {err_adv:.4f} K")
print(f"  улучшение: {err_div/err_adv:.2f}x" if err_adv > 0 else "")
print(f"\nПлан утверждает 1.1110 K для первого варианта.")
print(f"Совпадает: {abs(err_div - 1.1110) < 0.01}")
