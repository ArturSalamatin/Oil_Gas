"""Стационарная асимптотика температуры — общая проверка для всех примеров.

Проверка опирается на структуру уравнения энергии и НЕ использует ни вид
k_r(S_g), ни источник PVT — поэтому применима к любому примеру. Различия
между примерами (Кори или таблица, Standing или таблица) в результат не
входят вообще: формула ниже собирается из численных Φ, J, R, которые
берутся у того же решателя, что считал задачу.

В примере 02 (однофазном) стационарный предел имел замкнутый вид
    T(r) = T_ext + mu_JT·[p(r) - p_ext],
потому что скорость сокращалась. В двухфазной зоне так не выходит: к JT
добавляется скрытая теплота дегазации, а конвективный коэффициент
Φ = Σ_α ρ_α cp_α Q_α меняется по r, потому что часть нефти переходит в газ.

ТОЧНАЯ ФОРМУЛА. Стационарное уравнение схемы при λ = 0 и dp/dt = 0
(см. tridiag.py, assemble_tridiag) для ячейки j:

    (Φ T)_{j+1} - (Φ T)_j = J_{j+1} - J_j + V_j·Q_deg,j,

где J = Σ_α mu_JT,α Φ_α p — поток Джоуля–Томсона, а Q_deg = -L·mdot.
В стационаре временная часть mdot равна нулю, остаётся конвективная:
mdot = -ρ_g,ст·(R_{j+1} - R_j)/V_j, R_f = <G^o·Rs>_f. Значит

    V_j·Q_deg,j = L·ρ_g,ст·(R_{j+1} - R_j),

и правая часть тоже дивергентна. Суммируя от грани f до контура N,
все внутренние слагаемые телескопируются:

    Φ_N T_ext - Φ_f T_f = (J_N - J_f) + L·ρ_g,ст·(R_N - R_f),

откуда ЯВНО

    T_f = [ Φ_N T_ext - J_N + J_f - L·ρ_g,ст·(R_N - R_f) ] / Φ_f.

Формула точна для схемы, но требует численных Φ, J, R — это не замкнутое
выражение через p(r). Её ценность в другом: она разлагает перепад
температуры на физические вклады, см. decompose_two_phase().

ОДНОФАЗНАЯ ЗОНА. Там S_g = 0, Φ_g = 0, R = G^o·Rs0 постоянно (Rs = Rs0),
поэтому член дегазации выпадает, Φ_o сокращается, и формула вырождается
ровно в асимптотику примера 02:

    T(r) = T_ext + mu_JT,o·[p(r) - p_ext].

ГРАНИЦЫ ПРИМЕНИМОСТИ — ДВА УСЛОВИЯ, И ОБА ПРОВЕРЯЕМЫ.

  1. λ = 0. Телескопирование не учитывает кондуктивный поток. При λ ≠ 0
     остаётся поправка, и расхождение формулы со схемой не убывает с
     сеткой. Из десяти примеров λ ≠ 0 только у 10_deep_degassing
     (λ_solid = 1.5, λ_oil = 0.14, λ_gas = 0.04) — там эта проверка не
     применима, и report_asymptotics это сообщает, а не молча печатает
     большое расхождение.

  2. Стационар. На штатных 3 сутках релаксация T не завершена, и
     расхождение формулы с расчётом отражает именно это, а не дефект
     вывода. Проверено прогоном на длинных временах (см.
     05_standing_table_rp/check_asymptotics_relaxation.py): 3.889e-01 К
     на 3 сутках → 5.064e-02 на 30 → 1.231e-03 на 100 → 7.3e-11 на 400.
     Падение до машинного нуля и подтверждает точность формулы.

ПОЧЕМУ ПРОФИЛЬ T В ДВУХФАЗНОЙ ЗОНЕ ПОЧТИ ПЛОСКИЙ. Разложение перепада
между забоем и фронтом даёт три вклада, два охлаждающих и один греющий:
Джоуль–Томсон и скрытая теплота тянут вниз, а изменение Φ — вверх.
По мере разгазирования часть массы переходит в газ, у которого cp вдвое
меньше, поэтому |Φ| падает, и та же энергия соответствует более высокой
температуре. Плоский профиль — не признак слабости эффектов, а результат
их взаимного погашения. Конкретные числа печатает report_asymptotics();
для примера 03 на стационаре они таковы: ДТ -0.6607 К, скрытая теплота
-0.6348 К, изменение Φ +1.3066 К, итог +0.0112 К.

Запуск для конкретного примера:
    cd numerical_solver
    .venv\\Scripts\\python examples\\temperature_asymptotics.py 03
"""

import sys
from pathlib import Path

import numpy as np

_EXAMPLES = Path(__file__).resolve().parent
_ROOT = _EXAMPLES.parent
for _p in (str(_ROOT), str(_EXAMPLES),
           str(_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Порог «в ячейке есть газ». Тот же, что в two_phase_analytics.SG_EPS,
# но импортировать оттуда нельзя: эта проверка применима и к однофазным
# примерам 01/02, где two_phase_analytics не используется вовсе.
SG_EPS = 1e-12


def _pvt_of(simulator):
    """PVT-объект, которым считалась задача (конвенция closed_form._prepare).

    Берём у решателя, а не создаём заново: проверка обязана видеть ровно
    те свойства, что стояли в расчёте.
    """
    return simulator._energy._pvt


def _face_coefficients(config, history, grid, simulator):
    """Φ, J, R на всех гранях — ровно как их собирает tridiag.py.

    Возвращает (Phi, Phi_o, Phi_g, J, R_conv), все [N+1].
    Выше по потоку: при потоке к скважине (Q < 0) для грани f — ячейка f.
    На контурной грани при притоке — контур, свойства из ГУ
    (eq:bc_props_ext, DEBT-017), как и состав для R_conv (DEBT-009).

    Формулы обязаны совпадать с ядром: расхождение диагностики со схемой
    породило BUG-004 и увело расследование в сторону.
    """
    pvt = _pvt_of(simulator)
    N = grid.N
    st = history.states[-1]
    hr = history.hydro_results[-1]
    p, Sg, Rs, T = st.p, st.Sg, st.Rs, st.T
    Q_o, Q_g, G_o = hr.Q_o, hr.Q_g, hr.G_o

    rho_o = pvt.rho_o(p, Rs)
    rho_g = pvt.rho_g(p)
    cp_o = pvt.c_p_oil(p, T)
    cp_g = pvt.c_p_gas(p, T)
    mu_JT_o = pvt.mu_JT_oil(p, T)
    mu_JT_g = pvt.mu_JT_gas(p, T)

    Phi_o = np.zeros(N + 1)
    Phi_g = np.zeros(N + 1)
    J = np.zeros(N + 1)

    # ── Внутренние грани ──
    for f in range(1, N):
        up_o = f - 1 if Q_o[f] >= 0 else f
        Phi_o[f] = rho_o[up_o] * cp_o[up_o] * Q_o[f]
        up_g = f - 1 if Q_g[f] >= 0 else f
        Phi_g[f] = rho_g[up_g] * cp_g[up_g] * Q_g[f]

        # <Φ·p>_f: положительная часть берёт p слева, отрицательная — справа
        Po_p, Po_m = max(Phi_o[f], 0.0), min(Phi_o[f], 0.0)
        Pg_p, Pg_m = max(Phi_g[f], 0.0), min(Phi_g[f], 0.0)
        J[f] = (mu_JT_o[up_o] * (Po_p * p[f - 1] + Po_m * p[f])
                + mu_JT_g[up_g] * (Pg_p * p[f - 1] + Pg_m * p[f]))

    # ── Забой (f=0): upstream = ячейка 0 ──
    Phi_o[0] = rho_o[0] * cp_o[0] * Q_o[0]
    Phi_g[0] = rho_g[0] * cp_g[0] * Q_g[0]
    J[0] = (mu_JT_o[0] * Phi_o[0] + mu_JT_g[0] * Phi_g[0]) * p[0]

    # ── Контур (f=N): выше по потоку зависит от знака расхода ──
    # При оттоке (Q >= 0) — ячейка N-1, при штатном притоке (Q < 0) —
    # контур, где свойства заданы ГУ (eq:bc_props_ext, DEBT-017). То же
    # правило, что для R_conv ниже (DEBT-009) и в tridiag.py.
    # Прежняя редакция брала ячейку N-1 безусловно для Φ и J — при
    # притоке это домножало расход, посчитанный по условиям контура,
    # на свойства другого состояния.
    ic = config.initial_conditions
    p_ext_a = np.array([ic.p0])
    T_ext_a = np.array([ic.T0])
    Rs_ext_a = np.array([ic.Rs0])
    rho_o_ext = pvt.rho_o(p_ext_a, Rs_ext_a)[0]
    rho_g_ext = pvt.rho_g(p_ext_a)[0]
    cp_o_ext = pvt.c_p_oil(p_ext_a, T_ext_a)[0]
    cp_g_ext = pvt.c_p_gas(p_ext_a, T_ext_a)[0]
    mu_o_ext = pvt.mu_JT_oil(p_ext_a, T_ext_a)[0]
    mu_g_ext = pvt.mu_JT_gas(p_ext_a, T_ext_a)[0]

    if Q_o[N] >= 0:
        Phi_o[N] = rho_o[-1] * cp_o[-1] * Q_o[N]
        mu_o_N, p_o_N = mu_JT_o[-1], p[-1]
    else:
        Phi_o[N] = rho_o_ext * cp_o_ext * Q_o[N]
        mu_o_N, p_o_N = mu_o_ext, ic.p0

    if Q_g[N] >= 0:
        Phi_g[N] = rho_g[-1] * cp_g[-1] * Q_g[N]
        mu_g_N, p_g_N = mu_JT_g[-1], p[-1]
    else:
        # На контуре Sg = 0, поэтому Q_g[N] = 0 и вклад нулевой при
        # любых ρ_g, c_p_g; формула выписана полностью — верна и при Sg_ext > 0
        Phi_g[N] = rho_g_ext * cp_g_ext * Q_g[N]
        mu_g_N, p_g_N = mu_g_ext, ic.p0

    # Множитель p раскрыт по фазам: при притоке он контурный, а знак
    # Q_o и Q_g в общем случае может различаться (фазы текут врозь)
    J[N] = mu_o_N * Phi_o[N] * p_o_N + mu_g_N * Phi_g[N] * p_g_N

    # ── R_f = <G^o·Rs>_f — поток растворённого газа ──
    R_conv = np.zeros(N + 1)
    for f in range(1, N):
        Go_p, Go_m = max(G_o[f], 0.0), min(G_o[f], 0.0)
        R_conv[f] = Go_p * Rs[f - 1] + Go_m * Rs[f]
    R_conv[0] = G_o[0] * Rs[0]
    # Контур: при оттоке upstream = ячейка N-1, при притоке — состав ГУ
    # (eq. bc_Sg_ext). Безусловный Rs[-1] завышал бы поток растворённого
    # газа при разгазировании у контура — DEBT-009.
    Rs_ext = config.initial_conditions.Rs0
    R_conv[N] = G_o[N] * (Rs[-1] if G_o[N] >= 0 else Rs_ext)

    return Phi_o + Phi_g, Phi_o, Phi_g, J, R_conv


def stationary_face_temperature(config, history, grid, simulator):
    """Точная стационарная T на гранях по телескопической формуле.

    Возвращает (T_pred, T_num) — оба [N+1].
    T_num — численная температура на грани по upwind: при потоке к скважине
    это T правой ячейки, на контуре — T_ext.

    ВАЖНО: формула верна только при λ = 0 и на стационаре (см. докстринг
    модуля, «Границы применимости»). Расхождение на штатных 3 сутках
    отражает незавершённую релаксацию T, а не дефект вывода.
    """
    pvt = _pvt_of(simulator)
    N = grid.N
    T_ext = config.initial_conditions.T0
    L = config.thermal.L_degas
    rho_g_std = pvt.rho_g_std

    Phi, _, _, J, R = _face_coefficients(config, history, grid, simulator)

    T_pred = np.empty(N + 1)
    for f in range(N + 1):
        T_pred[f] = (Phi[N] * T_ext - J[N] + J[f]
                     - L * rho_g_std * (R[N] - R[f])) / Phi[f]

    T_num = np.empty(N + 1)
    T_num[:N] = history.states[-1].T[:N]   # upstream = правая ячейка
    T_num[N] = T_ext                       # контур: приток извне
    return T_pred, T_num


def single_phase_asymptote(config, history):
    """Асимптотика примера 02: T = T_ext + mu_JT,o·(p - p_ext), [N].

    Опорная точка — центр последней ячейки, а не r = R_e: ГУ Дирихле держит
    T_ext за контуром, где p = p_0, тогда как численный профиль отсчитывается
    от центра ячейки. Та же оговорка, что в примере 02.
    """
    p = history.states[-1].p
    return config.initial_conditions.T0 + config.thermal.mu_JT_oil * (p - p[-1])


def decompose_two_phase(config, history, grid, simulator,
                        f_well=0, f_front=None):
    """Разложить перепад T между забоем и фронтом на физические вклады.

    Возвращает dict с ключами jt, latent, phi_change, sum, actual (все К),
    либо None, если газа в области нет (однофазный пример).

    Перепад dT = T(забой) - T(фронт) получается из телескопической формулы
    делением на Φ(забой):
        dT = -(J_фронт - J_забой)/Φ_забой          — Джоуля–Томсона
             -L·ρ_g,ст·(R_фронт - R_забой)/Φ_забой — скрытая теплота
             + T_фронт·(Φ_фронт - Φ_забой)/Φ_забой — изменение Φ
    """
    pvt = _pvt_of(simulator)
    T = history.states[-1].T
    Sg = history.states[-1].Sg
    L = config.thermal.L_degas
    rho_g_std = pvt.rho_g_std

    if f_front is None:
        # Последняя грань, за которой ещё есть газ: индекс последней
        # двухфазной ячейки. Sg > 0 только в зоне разгазирования.
        gas_cells = np.where(Sg > SG_EPS)[0]
        if len(gas_cells) == 0:
            return None
        f_front = int(gas_cells[-1])

    Phi, _, _, J, R = _face_coefficients(config, history, grid, simulator)

    dJ = J[f_front] - J[f_well]
    dDeg = L * rho_g_std * (R[f_front] - R[f_well])
    dPhi = Phi[f_front] - Phi[f_well]

    jt = -dJ / Phi[f_well]
    latent = -dDeg / Phi[f_well]
    phi_change = T[f_front] * dPhi / Phi[f_well]

    return dict(jt=jt, latent=latent, phi_change=phi_change,
                sum=jt + latent + phi_change,
                actual=T[f_well] - T[f_front],
                f_front=f_front)


def has_conduction(config) -> bool:
    """Включена ли теплопроводность — формула её не учитывает.

    Не ветвление «считать или нет член», а признак применимости всей
    проверки: телескопирование выведено при λ = 0, при λ ≠ 0 оно неверно
    как таковое. Из десяти примеров это только 10_deep_degassing.
    """
    rock = config.rock
    return bool(rock.lambda_solid or rock.lambda_oil or rock.lambda_gas)


def report_asymptotics(config, history, grid, simulator) -> dict:
    """Печать стационарных проверок. Возвращает сводку."""
    if has_conduction(config):
        rock = config.rock
        print("── Стационарная асимптотика температуры ──")
        print(f"  не проверяется: в конфиге λ ≠ 0 "
              f"(solid={rock.lambda_solid}, oil={rock.lambda_oil}, "
              f"gas={rock.lambda_gas}) — телескопическая формула выведена "
              f"при λ = 0 и здесь неприменима")
        return dict(applicable=False, err_face=np.nan, err_1ph=np.nan,
                    decomposition=None, T_asymptote=None)

    Sg = history.states[-1].Sg
    T = history.states[-1].T
    mask1 = Sg <= SG_EPS

    print("── Стационарная асимптотика температуры ──")

    T_pred, T_num = stationary_face_temperature(config, history, grid,
                                                simulator)
    err_face = float(np.max(np.abs(T_pred[:grid.N] - T_num[:grid.N])))
    print(f"  телескопическая формула на гранях: max|T_форм - T_числ| = "
          f"{err_face:.3e} К")
    print(f"    (λ=0 в конфиге, поэтому формула точна для схемы; остаток — "
          f"незавершённая релаксация T, убывает до 1e-11 К за 400 сут)")

    T_as = single_phase_asymptote(config, history)
    err_1ph = (float(np.max(np.abs(T[mask1] - T_as[mask1]))) if mask1.any()
               else np.nan)
    print(f"  однофазная асимптотика T = T_ext + μ_JT(p - p_ext): "
          f"max|ΔT| = {err_1ph:.4f} К")
    print(f"    (за 3 суток релаксация не завершена — как в примере 02)")

    dec = decompose_two_phase(config, history, grid, simulator)
    if dec is not None:
        print(f"  разложение перепада T (забой ↔ фронт, грань "
              f"{dec['f_front']}):")
        print(f"    Джоуль–Томсон    {dec['jt']:+8.4f} К")
        print(f"    скрытая теплота  {dec['latent']:+8.4f} К")
        print(f"    изменение Φ      {dec['phi_change']:+8.4f} К")
        print(f"    сумма            {dec['sum']:+8.4f} К   "
              f"фактически {dec['actual']:+8.4f} К")

    return dict(applicable=True, err_face=err_face, err_1ph=err_1ph,
                decomposition=dec, T_asymptote=T_as)


def _resolve_example(name_or_prefix: str) -> Path:
    """examples/<имя>/ по полному имени или числовому префиксу ('03').

    Пользователю не нужно печатать '03_standing_corey' целиком.
    Ошибка при отсутствии или неоднозначности префикса.
    """
    exact = _EXAMPLES / name_or_prefix
    if exact.is_dir():
        return exact
    matches = sorted(d for d in _EXAMPLES.iterdir()
                     if d.is_dir() and d.name.startswith(name_or_prefix))
    if not matches:
        raise SystemExit(f"нет примера '{name_or_prefix}'")
    if len(matches) > 1:
        raise SystemExit(f"неоднозначно: {[m.name for m in matches]}")
    return matches[0]


# ── Автономный запуск ──
if __name__ == "__main__":
    from gpn_multiphase_solver.io.config import load_config
    from gpn_multiphase_solver.factory import SimulatorFactory

    if len(sys.argv) < 2:
        raise SystemExit(
            "укажите пример: python examples\\temperature_asymptotics.py 03")

    folder = _resolve_example(sys.argv[1])
    config = load_config(folder / "config.json")
    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)

    report_asymptotics(config, history, sim._grid, sim)
