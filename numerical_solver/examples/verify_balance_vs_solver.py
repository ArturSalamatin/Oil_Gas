"""Покомпонентная сверка баланса энергии с тем, что реально собирает решатель.

Инструмент диагностики: когда невязка баланса энергии велика, он однозначно
отвечает на вопрос, где дефект:
  (а) в диагностическом скрипте energy_balance.py (пропущен/неверен член),
  (б) в TridiagEnergySolver (схема не сохраняет энергию).

Метод: инструментируем TridiagEnergySolver.solve через monkey-patch, собираем
за каждый шаг ИМЕННО ТЕ суммы, которые фактически попадают в СЛАУ:
    E_acc  = Σ_j cap_j (T_new_j - T_old_j)              — накопление
    E_conv = вклад Φ (конвекция) из коэффициентов a,b,c
    E_jt   = Σ_j J_jt_j · dt
    E_ad   = Σ_j V_j Q_ad_j · dt
    E_deg  = Σ_j V_j Q_deg_j · dt
и сравниваем с тем, что считает compute_balance по истории. Невязка схемы
на уровне 1e-12 означает, что решатель самосогласован и искать надо в
скрипте; почленное расхождение показывает, в каком именно члене.

Так был найден BUG-004: невязка схемы 2.7e-12 при невязке скрипта 0.20, и
всё расхождение сидело в члене накопления (-7.5e+09 Дж из -7.4e+09).

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\verify_balance_vs_solver.py
"""

import sys
from pathlib import Path
import numpy as np

_EXAMPLES = Path(__file__).resolve().parent
_ROOT = _EXAMPLES.parent
# Прототип radial_blackoil подключается conftest-ом только под pytest,
# автономному скрипту приходится делать это самому.
for _p in (str(_ROOT), str(_EXAMPLES), str(_EXAMPLES / "03_standing_corey")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_PROTO = _ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
if _PROTO.exists() and str(_PROTO) not in sys.path:
    sys.path.insert(0, str(_PROTO))

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
import energy_balance as eb


def run_instrumented(config_path):
    """Прогон с перехватом внутренностей TridiagEnergySolver.solve."""
    cfg = load_config(Path(config_path))
    sim, init = SimulatorFactory.from_config(cfg)

    log = []
    orig_solve = TridiagEnergySolver.solve

    def patched(self, hydro_result, state_prev, dt, bc, collect=None):
        # bc вместо T_ext — новый контракт EnergySolver.solve (DEBT-009).
        # collect — накопитель баланса (DEBT-013); simulator передаёт его
        # всегда, поэтому подменяющая функция обязана его принимать
        # и пробрасывать в оригинал.
        T_ext = bc.T_ext
        Rs_ext = bc.Rs_ext
        N = self._grid.N
        V = self._grid.volumes
        p = hydro_result.state.p
        Sg = hydro_result.state.Sg
        Rs = hydro_result.state.Rs
        So = 1.0 - Sg
        T_old = state_prev.T
        p_old = state_prev.p
        Rs_old = state_prev.Rs
        Q_o, Q_g, G_o = hydro_result.Q_o, hydro_result.Q_g, hydro_result.G_o

        props = self.compute_cell_properties(p, Sg, Rs, So, T_old)
        # Свойства контура — выше по потоку при притоке (DEBT-017).
        # Повторяем то, что делает solve: иначе диагностика считала бы
        # Phi и J не так, как схема, и дала бы ложную невязку баланса —
        # ровно тот класс расхождения, который породил BUG-004.
        ext = self._ext_properties(bc)
        Phi_plus, Phi_minus, Phi_o, Phi_g = \
            self.compute_convective_coefficients(
                Q_o, Q_g, props['rho_o'], props['rho_g'],
                props['c_p_o'], props['c_p_g'], N, ext)
        J_jt = self.compute_jt(Q_o, Q_g, Phi_o, Phi_g,
                               props['mu_JT_o'], props['mu_JT_g'], p, N, ext)
        Q_ad = self.compute_adiabatic(
            So, Sg, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'],
            props['mu_JT_o'], props['mu_JT_g'], p, p_old, dt)
        Q_deg = self.compute_degassing(
            So, Sg, Rs, Rs_old, props['Bo'], G_o, props['L'], dt, N, Rs_ext)

        T_new = orig_solve(self, hydro_result, state_prev, dt, bc, collect)

        cap = V * props['rho_cp_eff'] / dt
        # Накопление ровно так, как его дискретизует схема:
        # cap·T_new - cap·T_old, с (ρcp)_eff НОВОГО состояния в обоих членах.
        E_acc = float(np.sum(cap * (T_new - T_old)) * dt)
        E_jt = float(np.sum(J_jt) * dt)
        E_ad = float(np.sum(V * Q_ad) * dt)
        E_deg = float(np.sum(V * Q_deg) * dt)

        # Конвекция: телескопируем поток энтальпии по граням так, как это
        # делает матрица. Φ⁺ несёт T ячейки слева, Φ⁻ — T ячейки справа.
        # Поток через грань f: Φ⁺[f]·T[f-1] + Φ⁻[f]·T[f].
        T_ext_arr = T_ext
        flux = np.zeros(N + 1)
        for f in range(N + 1):
            T_L = T_new[f - 1] if f >= 1 else T_new[0]
            T_R = T_new[f] if f <= N - 1 else T_ext_arr
            flux[f] = Phi_plus[f] * T_L + Phi_minus[f] * T_R
        # Чистая конвекция в ячейки: -(flux_out - flux_in) = -(flux[N]-flux[0])
        E_conv = float(-(flux[N] - flux[0]) * dt)

        log.append(dict(
            t=float(hydro_result.state.t), dt=float(dt),
            E_acc=E_acc, E_conv=E_conv, E_jt=E_jt,
            E_ad=E_ad, E_deg=E_deg,
            resid=E_acc - (E_conv + E_jt + E_ad + E_deg),
        ))
        return T_new

    TridiagEnergySolver.solve = patched
    try:
        history = sim.run(init)
    finally:
        TridiagEnergySolver.solve = orig_solve

    return cfg, sim, history, log


def report(config_path, label):
    cfg, sim, history, log = run_instrumented(config_path)

    # Баланс по решателю: суммируем шаговые вклады.
    acc = sum(r['E_acc'] for r in log)
    conv = sum(r['E_conv'] for r in log)
    jt = sum(r['E_jt'] for r in log)
    ad = sum(r['E_ad'] for r in log)
    deg = sum(r['E_deg'] for r in log)
    src = conv + jt + ad + deg
    scale = max(abs(acc), abs(src), 1e-30)

    # Баланс по скрипту.
    bal = eb.compute_balance(history, sim._grid, cfg)

    print(f"\n=== {label} ===")
    print(f"шагов решателя: {len(log)}, сохранённых: {len(history.times)}")
    print("\n-- ИЗ РЕШАТЕЛЯ (то, что реально в СЛАУ) --")
    print(f"  накопление  = {acc:+.4e} Дж")
    print(f"  конвекция   = {conv:+.4e} Дж")
    print(f"  JT          = {jt:+.4e} Дж")
    print(f"  адиабатика  = {ad:+.4e} Дж")
    print(f"  дегазация   = {deg:+.4e} Дж")
    print(f"  сумма источ = {src:+.4e} Дж")
    print(f"  НЕВЯЗКА СХЕМЫ = {acc - src:+.4e} Дж  (отн. {abs(acc-src)/scale:.3e})")

    print("\n-- ИЗ СКРИПТА energy_balance.py --")
    print(f"  dE          = {bal['delta_E'][-1]:+.4e} Дж")
    print(f"  конвекция   = {bal['cum_conv'][-1]:+.4e} Дж")
    print(f"  JT          = {bal['cum_jt'][-1]:+.4e} Дж")
    print(f"  адиабатика  = {bal['cum_adiab'][-1]:+.4e} Дж")
    print(f"  дегазация   = {bal['cum_deg'][-1]:+.4e} Дж")
    print(f"  НЕВЯЗКА СКРИПТА = {bal['residual'][-1]:+.4e} Дж"
          f"  (отн. {bal['rel_residual'][-1]:.3e})")

    print("\n-- РАСХОЖДЕНИЕ ПОЧЛЕННО (скрипт - решатель) --")
    print(f"  d накопление = {bal['delta_E'][-1] - acc:+.4e}")
    print(f"  d конвекция  = {bal['cum_conv'][-1] - conv:+.4e}")
    print(f"  d JT         = {bal['cum_jt'][-1] - jt:+.4e}")
    print(f"  d адиабатика = {bal['cum_adiab'][-1] - ad:+.4e}")
    print(f"  d дегазация  = {bal['cum_deg'][-1] - deg:+.4e}")

    return dict(acc=acc, src=src, rel_scheme=abs(acc - src) / scale,
                rel_script=float(bal['rel_residual'][-1]))


if __name__ == "__main__":
    r04 = report(_EXAMPLES / "04_table_table" / "config.json",
                 "Пример 04 (табличный PVT)")
    r03 = report(_EXAMPLES / "03_standing_corey" / "config.json",
                 "Пример 03 (Standing)")

    print("\n=== ИТОГ ===")
    print(f"  04: невязка схемы {r04['rel_scheme']:.3e}, "
          f"невязка скрипта {r04['rel_script']:.3e}")
    print(f"  03: невязка схемы {r03['rel_scheme']:.3e}, "
          f"невязка скрипта {r03['rel_script']:.3e}")
    print("\nЕсли невязка СХЕМЫ мала на обоих, а невязка СКРИПТА велика на 04")
    print("  → дефект в скрипте (случай а).")
    print("Если невязка СХЕМЫ велика на 04 → дефект в решателе (случай б).")
