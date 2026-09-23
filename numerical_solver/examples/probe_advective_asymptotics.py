"""Есть ли явная формула стационарной T в адвективной схеме (BUG-012, шаг 13а).

ВОПРОС. Прежняя формула temperature_asymptotics.stationary_face_temperature
получена сворачиванием суммы к крайним граням: все три члена были
дивергентны, внутренние слагаемые уничтожались взаимно, и T_f выражалась
явно через величины на грани f и на контуре. В адвективной форме ни один
из трёх членов дивергентным не является, и этот путь закрыт.

ЕСТЬ ЛИ ДРУГОЙ ПУТЬ. Стационарное уравнение схемы при lambda = 0 и
dp/dt = 0 для ячейки j:

    Phi^+_{j-1/2}·(T_j − T_{j-1}) + Phi^-_{j+1/2}·(T_{j+1} − T_j)
        = J_j + V_j·Q_deg,j

При штатном режиме добычи поток всюду направлен к скважине, значит
Phi^+ = 0 на ВСЕХ гранях (замерено: 0 из N+1 граней с Phi^+ > 0).
Остаётся только второй член:

    Phi^-_{j+1/2}·(T_{j+1} − T_j) = J_j + V_j·Q_deg,j

Это РЕКУРРЕНТНОЕ соотношение: зная T_{j+1}, находим T_j одним делением.
Начиная с контура, где T_N = T_ext задано условием Дирихле, можно
пройти к забою и получить весь профиль:

    T_j = T_{j+1} − (J_j + V_j·Q_deg,j) / Phi^-_{j+1/2}

Формула явная, хотя и не замкнутая через p(r) — как и прежняя, она
требует численных Phi, J, Q_deg. Но она СОХРАНЯЕТ главное свойство
прежней: разложение перепада температуры на физические вклады.

ЧТО ПРОВЕРЯЕТ СКРИПТ.
  1. Действительно ли Phi^+ = 0 на всех гранях в штатных конфигах.
  2. Совпадает ли рекуррентная формула с решением схемы на стационаре.
  3. Работает ли разложение на вклады (JT и скрытая теплота).

ГРАНИЦЫ ПРИМЕНИМОСТИ те же, что у прежней формулы: lambda = 0 (иначе
добавится кондуктивный член) и установившийся режим (иначе остаётся
накопление). Дополнительно: Phi^+ = 0, то есть отсутствие оттока от
скважины — при нагнетании формула потребует прохода в другую сторону.

⚠️ УСТАНОВИВШИЙСЯ РЕЖИМ НЕДОСТИЖИМ, И ЭТО РЕШАЮЩЕЕ ОГРАНИЧЕНИЕ (DEBT-022).
Невязка формулы против схемы на штатных конфигах — 0.43–0.47 К, то есть
8–47 % от перепада, а не машинный ноль. Разбор:

  1. Адиабатический член ни при чём: Q_ad = 0 РОВНО, max|p^n - p^(n-1)| = 0
     Па. Гидродинамика вышла на стационар полностью.
  2. Вся невязка — отброшенный член накопления cap_j·(T_j - T_j^{n-1}).
     Стационарна ГИДРОДИНАМИКА, но не ТЕМПЕРАТУРА.

Подставить накопление из численного решения нельзя: тогда T_j стоит в обеих
частях, и проверка вырождается в тождество «прогонка решила ту систему,
которую ей дали» (невязка 1e-11 К — машинный нуль solve_banded, а не
точность физики).

Дождаться установления T тоже нельзя: невязка спадает как t^-0.49
(диффузионно, 1/sqrt(t)), и до 0.01 К понадобилось бы 26 лет модельного
времени — см. probe_recurrence_vs_time.py. Причина физическая: теплоёмкость
скелета (rho c_p)_s = 1.25e6 Дж/(м³·К) на порядки превосходит конвективный
вынос, тепловой фронт ползёт как sqrt(t), а давление устанавливается сразу.

Поэтому скрипт остаётся ДИАГНОСТИКОЙ, а не проверкой ядра: он показывает
разложение перепада на вклады JT и скрытой теплоты, но согласия со схемой
на доступных временах не даёт.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\probe_advective_asymptotics.py 09_degassing_latent_heat
"""

import sys
from pathlib import Path

import numpy as np

EXAMPLES_DIR = Path(__file__).parent
sys.path.insert(0, str(EXAMPLES_DIR))

_PROTO = EXAMPLES_DIR.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO) not in sys.path:
    sys.path.insert(0, str(_PROTO))

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config


def measure(example: str):
    cfg = load_config(EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)

    solver = simulator._energy
    grid = solver._grid
    N = grid.N
    V = grid.volumes

    snap = {}

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        # Берём ПОСЛЕДНИЙ шаг — ближе всего к установившемуся режиму
        st = hydro_result.state
        props = solver.compute_cell_properties(
            st.p, st.Sg, st.Rs, 1.0 - st.Sg, T_old)
        ext = solver._ext_properties(bc)
        Phi_plus, Phi_minus, Phi_o, Phi_g = \
            solver.compute_convective_coefficients(
                hydro_result.Q_o, hydro_result.Q_g,
                props['rho_o'], props['rho_g'],
                props['c_p_o'], props['c_p_g'], N, ext)

        p_wf = bc.well.boundary_pressure(st, grid, solver._pvt, None)
        J_jt = solver.compute_jt(
            hydro_result.Q_o, hydro_result.Q_g, Phi_o, Phi_g,
            props['mu_JT_o'], props['mu_JT_g'], st.p, N, ext, p_wf)
        Q_deg = solver.compute_degassing(
            1.0 - st.Sg, st.Sg, st.Rs, state_prev.Rs, props['Bo'],
            hydro_result.G_o, props['L'], dt, N, bc.Rs_ext)

        snap.update(
            Phi_plus=Phi_plus.copy(), Phi_minus=Phi_minus.copy(),
            J_jt=J_jt.copy(), Q_deg=Q_deg.copy(), V=V.copy(),
            T_ext=float(bc.T_ext), N=N, lam=float(np.max(props['lambda_eff'])))

    solver.matrix_probe = probe
    history = simulator.run(initial)
    solver.matrix_probe = None
    snap['T_num'] = history.states[-1].T.copy()
    return snap


def report(example, s):
    N = s['N']
    Phi_plus, Phi_minus = s['Phi_plus'], s['Phi_minus']
    J_jt, Q_deg, V = s['J_jt'], s['Q_deg'], s['V']
    T_num = s['T_num']

    print(f"\n{'=' * 76}\n{example}\n{'=' * 76}")

    n_pos = int(np.sum(Phi_plus > 0))
    print(f"1. Phi^+ > 0 на {n_pos} гранях из {N + 1}")
    if n_pos:
        print("   ⚠ есть отток от скважины — рекуррентность в одну сторону "
              "неприменима")
    else:
        print("   поток всюду к скважине: остаётся только член правой грани")

    if s['lam'] > 0:
        print(f"\n2. lambda_eff = {s['lam']:.3g} != 0 — формула выведена при")
        print("   lambda = 0 и здесь неприменима (как и прежняя).")
        return

    # ── Рекуррентный проход от контура к забою ──
    # T_j = T_{j+1} − (J_j + V_j·Q_deg,j) / Phi^-_{j+1/2}
    T_rec = np.empty(N)
    T_next = s['T_ext']
    for j in range(N - 1, -1, -1):
        denom = Phi_minus[j + 1]
        if denom == 0.0:
            T_rec[j] = np.nan
            T_next = np.nan
            continue
        T_rec[j] = T_next - (J_jt[j] + V[j] * Q_deg[j]) / denom
        T_next = T_rec[j]

    ok = np.isfinite(T_rec)
    err = np.max(np.abs(T_rec[ok] - T_num[ok])) if ok.any() else np.nan
    scale = max(abs(T_num[0] - s['T_ext']), 1.0)

    print(f"\n3. Рекуррентная формула против решения схемы:")
    print(f"   T_рек(r_w) = {T_rec[0]:.5f} K,  T_числ(r_w) = {T_num[0]:.5f} K")
    print(f"   max|T_рек − T_числ| = {err:.4e} K")
    print(f"   отн. к перепаду ({scale:.3f} K) = {err / scale:.3e}")
    print("   (остаток — незавершённая релаксация, как и у прежней формулы)")

    # ── Разложение перепада забой ↔ контур ──
    # Суммируя рекуррентность от 0 до N-1:
    #   T_0 − T_ext = −Σ_j (J_j + V_j·Q_deg,j) / Phi^-_{j+1/2}
    with np.errstate(divide='ignore', invalid='ignore'):
        contrib_jt = np.where(Phi_minus[1:] != 0,
                              -J_jt / Phi_minus[1:], 0.0)
        contrib_deg = np.where(Phi_minus[1:] != 0,
                               -V * Q_deg / Phi_minus[1:], 0.0)
    print(f"\n4. Разложение перепада T(r_w) − T_ext:")
    print(f"   Джоуль–Томсон      {np.sum(contrib_jt):+9.4f} K")
    print(f"   скрытая теплота    {np.sum(contrib_deg):+9.4f} K")
    print(f"   сумма              {np.sum(contrib_jt) + np.sum(contrib_deg):+9.4f} K")
    print(f"   фактический        {T_num[0] - s['T_ext']:+9.4f} K")
    print("\n   Вклада «изменение Phi» здесь НЕТ: в адвективной форме он")
    print("   не возникает — это и был паразитный член T_j·D_j (BUG-012).")


if __name__ == "__main__":
    for ex in sys.argv[1:] or ["09_degassing_latent_heat", "08_degassing_jt",
                               "03_standing_corey"]:
        report(ex, measure(ex))
