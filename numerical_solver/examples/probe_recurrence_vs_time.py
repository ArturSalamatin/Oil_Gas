"""Спадает ли невязка стационарной рекуррентности со временем (DEBT-022).

ПОВОД. probe_recurrence_relaxation.py показал: невязка 0.43–0.47 К целиком
объясняется отброшенным накоплением cap_j·(T_j − T_j^{n-1}). Подставить его
из численного решения нельзя — тогда T_j стоит и слева, и справа, и
проверка вырождается в тождество «прогонка решила ту систему, которую ей
дали». Невязка 1e-11 К в таком тесте — машинный нуль solve_banded, а не
точность физики.

ОСТАЁТСЯ ПУТЬ (а): довести расчёт до установления T, чтобы накопление стало
мало ФИЗИЧЕСКИ. Тогда стационарная формула применима без подстановок, и
сравнение с ней — честная проверка коэффициентов Phi, J, Q_deg.

ЧТО ИЗМЕРЯЕТ СКРИПТ. Невязку стационарной рекуррентности (БЕЗ накопления)
на растущих временах расчёта. Если она спадает — путь (а) работает, и
вопрос лишь в цене. Если выходит на полку — T не релаксирует к стационару,
и стационарной проверки для этих конфигов не существует вовсе.

Дополнительно печатается max|T^n − T^(n-1)| — прямая мера незавершённости
релаксации, и cap·dT — тот самый отброшенный член в ваттах.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\probe_recurrence_vs_time.py
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


def measure(example: str, n_steps: int):
    """Прогон на n_steps шагов по 3600 с. Возвращает снимок последнего шага."""
    cfg = load_config(EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"

    # Расписание из одной записи, повторённой n_steps раз: тот же режим,
    # просто дольше. Управление и p_wf берём из первой записи конфига.
    first = cfg.time.history[0]
    cfg.time.history = [type(first)(**{**vars(first), 'dt': 3600.0})
                        for _ in range(n_steps)]

    simulator, initial = SimulatorFactory.from_config(cfg)
    solver = simulator._energy
    grid = solver._grid
    N = grid.N
    V = grid.volumes

    snap = {}

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        st = hydro_result.state
        props = solver.compute_cell_properties(
            st.p, st.Sg, st.Rs, 1.0 - st.Sg, T_old)
        ext = solver._ext_properties(bc)
        Phi_plus, Phi_minus, Phi_o, Phi_g = \
            solver.compute_convective_coefficients(
                hydro_result.Q_o, hydro_result.Q_g,
                props['rho_o'], props['rho_g'],
                props['c_p_o'], props['c_p_g'], N, ext)

        p_wf = hydro_result.p_wf    # фактическое давление шага (FEAT-020)
        J_jt = solver.compute_jt(
            hydro_result.Q_o, hydro_result.Q_g, Phi_o, Phi_g,
            props['mu_JT_o'], props['mu_JT_g'], st.p, N, ext, p_wf)
        Q_deg = solver.compute_degassing(
            1.0 - st.Sg, st.Sg, st.Rs, state_prev.Rs, props['Bo'],
            hydro_result.G_o, props['L'], dt, N, bc.Rs_ext)
        cap = b - (Phi_plus[0:N] - Phi_minus[1:N + 1])

        snap.update(
            Phi_minus=Phi_minus.copy(), J_jt=J_jt.copy(),
            Q_deg=Q_deg.copy(), V=V.copy(), cap=np.asarray(cap).copy(),
            T_old=np.asarray(T_old).copy(), T_ext=float(bc.T_ext), N=N)

    solver.matrix_probe = probe
    history = simulator.run(initial)
    solver.matrix_probe = None
    snap['T_num'] = history.states[-1].T.copy()
    snap['dT_last'] = float(np.max(np.abs(
        history.states[-1].T - history.states[-2].T)))
    snap['t_end'] = float(history.times[-1])
    return snap


def stationary_err(s):
    """Невязка СТАЦИОНАРНОЙ рекуррентности — накопление НЕ подставляется."""
    N, V = s['N'], s['V']
    Phi_minus, J_jt, Q_deg = s['Phi_minus'], s['J_jt'], s['Q_deg']

    T = np.empty(N)
    T_next = s['T_ext']
    for j in range(N - 1, -1, -1):
        denom = Phi_minus[j + 1]
        if denom == 0.0:
            return np.nan
        T[j] = T_next - (J_jt[j] + V[j] * Q_deg[j]) / denom
        T_next = T[j]
    return float(np.max(np.abs(T - s['T_num'])))


if __name__ == "__main__":
    examples = sys.argv[1:] or ["09_degassing_latent_heat", "03_standing_corey"]
    # 72 шага = штатные 3 сутки; далее до 40 суток
    step_counts = [72, 168, 360, 720, 960]

    for ex in examples:
        print(f"\n{'=' * 76}\n{ex}\n{'=' * 76}")
        print(f"{'шагов':>7} {'t, сут':>8} {'max|dT| за шаг':>16} "
              f"{'max|cap·dT|, Вт':>17} {'невязка стац., К':>18}")
        for n in step_counts:
            s = measure(ex, n)
            cap_dT = float(np.max(np.abs(s['cap'] * (s['T_num'] - s['T_old']))))
            print(f"{n:>7} {s['t_end'] / 86400:>8.2f} {s['dT_last']:>16.3e} "
                  f"{cap_dT:>17.4g} {stationary_err(s):>18.4e}")
