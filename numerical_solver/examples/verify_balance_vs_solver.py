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
        # bc — граничные условия (контракт EnergySolver.solve).
        # collect — накопитель баланса; simulator передаёт его
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
        # Phi и J не так, как схема, и дала бы ложную невязку баланса.
        ext = self._ext_properties(bc)
        Phi_plus, Phi_minus, Phi_o, Phi_g = \
            self.compute_convective_coefficients(
                Q_o, Q_g, props['rho_o'], props['rho_g'],
                props['c_p_o'], props['c_p_g'], N, ext)
        # p_wf — давление на забойной грани: в адвективной форме JT-вклад
        # этой грани равен μ_JT·Φ⁻·(p[0] − p_wf) и без него не считается
        # (BUG-012). Берётся так же, как в solve: из HydroResult (FEAT-020).
        p_wf = hydro_result.p_wf
        J_jt = self.compute_jt(Q_o, Q_g, Phi_o, Phi_g,
                               props['mu_JT_o'], props['mu_JT_g'], p, N, ext,
                               p_wf)
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

        # Конвекция в АДВЕКТИВНОЙ форме: вклад каждой грани —
        # произведение Φ на РАЗНОСТЬ температур, и сумма по ячейкам к
        # двум крайним граням не сворачивается. Поэтому вклад считается
        # почленно, а не как -(flux[N] - flux[0]).
        #
        # Соседи по тем же соглашениям, что в assemble_tridiag: слева от
        # ячейки 0 — она сама (забойная грань вклада не даёт, ГУ Неймана),
        # справа от N-1 — T_ext (ГУ Дирихле).
        T_left = np.concatenate(([T_new[0]], T_new[:-1]))    # [N]: T_{j-1}
        T_right = np.concatenate((T_new[1:], [T_ext]))        # [N]: T_{j+1}
        F = (Phi_plus[0:N] * (T_new - T_left)
             + Phi_minus[1:N + 1] * (T_right - T_new))
        # F_j стоит в левой части уравнения рядом с накоплением, поэтому
        # вклад конвекции в энергию области равен -ΣF_j.
        E_conv = float(-np.sum(F) * dt)

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
    # Та же нормировка, что в energy_balance.compute_balance — сумма модулей
    # всех членов: иначе «отн.» решателя и скрипта были бы разными числами.
    scale = max(abs(acc) + abs(conv) + abs(jt) + abs(ad) + abs(deg), 1e-30)

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
