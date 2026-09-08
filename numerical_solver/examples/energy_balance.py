"""Баланс энергии во времени — общая проверка для всех примеров.

Проверка интегральная: она не зависит ни от вида ОФП, ни от источника PVT,
ни от того, какие тепловые эффекты включены в конфиге. Смысл один — схема
не должна терять и создавать энергию. Компоненты (кумулятивные, от t=0 до
t_n):

  ΔE(t)     — изменение запаса тепловой энергии в области
  adiab(t)  — адиабатический источник, φ·Σ_α S_α (1 + ρ_α cp_α μ_JT,α) dp/dt
  conv(t)   — чистая конвекция через забой и контур (обе фазы)
  jt(t)     — источник Джоуля–Томсона (обе фазы)
  deg(t)    — скрытая теплота дегазации, -L·mdot
  cond(t)   — кондуктивный поток через контур
  невязка   — ΔE - (adiab + conv + jt + deg + cond)

Формулы повторяют то, что собирает TridiagEnergySolver.assemble_tridiag.
Суммирование по всем ячейкам телескопирует дивергентные члены (JT и
конвекцию) до разности потоков на забое и контуре; недивергентные
(адиабатика, дегазация) суммируются по объёму.

ВСЕ ЧЛЕНЫ СЧИТАЮТСЯ БЕЗУСЛОВНО. Никаких ветвлений «этот член нужен только
если в конфиге λ ≠ 0 / L ≠ 0 / μ_JT ≠ 0»: член входит в формулу всегда и
обнуляется арифметикой, когда соответствующий коэффициент равен нулю.
Возвращаемый dict тоже всегда содержит ПОЛНЫЙ набор ключей — нулевые
массивы вместо отсутствующих.

Это не стилистика, а следствие BUG-004/FEAT-016. Копия этого скрипта у
примера 03 утверждала: «кондуктивного члена нет, он и не нужен — в конфиге
λ = 0». Для 03 это верно, но проверка применяется ко всем десяти примерам,
а у 10_deep_degassing λ ≠ 0. Девять примеров с λ = 0 маскировали пропуск
члена у десятого: 8.6 % невязки и порядок сходимости 0.751 вместо 0.980.
Проверка «нужен ли член» не должна зависеть от того, посмотрел ли автор
скрипта в конфиг.

(ρcp)_eff НЕ считается постоянной: она зависит от S_g и от PVT, поэтому ΔE
считается с поячеечными свойствами на каждом шаге. В однофазных примерах
01 и 02 величина действительно постоянна, и прежние копии там пользовались
скаляром — но поячеечный расчёт даёт тот же результат (расхождение ~1e-6 Дж
при невязке ~3e+6 Дж, измерено в BUG-004), а условного упрощения не требует.

НАКОПЛЕНИЕ СЧИТАЕТСЯ ПО ПРИРАЩЕНИЯМ, а не как разность запасов от t=0
(BUG-004). Схема дискретизует Σ V (ρcp)^{n} (T^{n} - T^{n-1}): множитель
cap_j = V_j (ρcp)^{n}_j / dt стоит и в матрице, и в правой части. Разность
запасов Σ V [(ρcp)^K T^K - (ρcp)^0 T^0] отличается от неё на член
Σ_n Σ_j V T^{n-1} [(ρcp)^n - (ρcp)^{n-1}] — дрейф свойств, умноженный на
абсолютную температуру. На табличном PVT этот дрейф систематичен (B_g там
кусочно-линеен по трём узлам вместо гладкой гиперболы) и давал 20 %
невязки, не убывающей с шагом по времени.

Три функции:
  compute_balance()        — считает компоненты, возвращает dict
  plot_energy_balance()    — строит график поверх compute_balance()
  report_energy_balance()  — обёртка для run_example (конвенция общих модулей)

Запуск для конкретного примера:
    cd numerical_solver
    .venv\\Scripts\\python examples\\energy_balance.py 03
"""

import sys
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_EXAMPLES = Path(__file__).resolve().parent
_ROOT = _EXAMPLES.parent
for _p in (str(_ROOT), str(_EXAMPLES),
           str(_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _cell_properties(pvt, rock, p, Sg, Rs, T):
    """(ρcp)_eff и покомпонентные PVT в ячейках — как в tridiag.py (eq. 5)."""
    phi = rock.porosity
    So = 1.0 - Sg
    rho_o = pvt.rho_o(p, Rs)
    rho_g = pvt.rho_g(p)
    cp_o = pvt.c_p_oil(p, T)
    cp_g = pvt.c_p_gas(p, T)
    rho_cp_eff = ((1 - phi) * rock.rho_cp_solid
                  + phi * (So * rho_o * cp_o + Sg * rho_g * cp_g))
    return rho_o, rho_g, cp_o, cp_g, rho_cp_eff


def compute_balance(history, grid, config):
    """Покомпонентный баланс энергии по сохранённой истории.

    Возвращает dict с массивами длины n_steps:
      t, delta_E, cum_adiab, cum_conv, cum_jt, cum_deg, cum_cond,
      total, residual, rel_residual

    Набор ключей ПОЛНЫЙ всегда, независимо от конфига: члены, физически
    отсутствующие в сценарии, приходят нулевыми массивами.
    """
    from gpn_multiphase_solver.factory import SimulatorFactory

    # pvt и rock нужны для (ρcp)_eff, Φ, μ_JT и L. Пересобираем фабрикой —
    # это дёшево, прогон не повторяется.
    sim, _ = SimulatorFactory.from_config(config)
    pvt = sim._energy._pvt
    rock = sim._energy._rock

    # Накопление суммируется по сохранённым шагам: пропуск шагов
    # (save_every > 1) сделал бы сумму приращений неполной.
    if getattr(config.output, "save_every", 1) != 1:
        raise ValueError(
            "compute_balance требует save_every = 1: баланс суммирует "
            "приращения по шагам, пропущенные шаги нарушают сумму")

    N = grid.N
    V = grid.volumes
    phi = rock.porosity
    T_ext = config.initial_conditions.T0
    rho_g_std = pvt.rho_g_std

    n_steps = len(history.times)
    t_arr = np.array(history.times)

    delta_E = np.zeros(n_steps)
    cum_conv = np.zeros(n_steps)
    cum_adiab = np.zeros(n_steps)
    cum_jt = np.zeros(n_steps)
    cum_deg = np.zeros(n_steps)
    cum_cond = np.zeros(n_steps)

    for n in range(n_steps):
        st = history.states[n]

        if n == 0:
            # На нулевом шаге приращения ещё нет: ΔE(0) = 0 по определению.
            # PVT здесь не считаем — результат всё равно не используется.
            delta_E[n] = 0.0
            continue

        _, _, _, _, rho_cp_n = _cell_properties(
            pvt, rock, st.p, st.Sg, st.Rs, st.T)

        # Накопление берётся ТОЧНО так, как его дискретизует схема
        # (eq. 33-36): cap_j = V_j (ρcp)^{n}_j / dt стоит в матрице и в
        # правой части ОДНИМ И ТЕМ ЖЕ множителем, поэтому шаговый вклад —
        # это V (ρcp)^{n} (T^{n} - T^{n-1}), а НЕ разность запасов
        # V[(ρcp)^n T^n - (ρcp)^{n-1} T^{n-1}].
        # Разница между ними — член Σ V T^{n-1} [(ρcp)^n - (ρcp)^{n-1}],
        # который на табличном PVT давал 20 % невязки (BUG-004): свойства
        # дрейфуют систематически, и дрейф умножается на абсолютную
        # T ~ 350 K, а не на приращение ΔT ~ 1 K.
        #
        # (ρcp)_eff берём на st.T, решатель — на T_old (tridiag.py:51).
        # Сейчас это эквивалентно: c_p и μ_JT в обоих PVT — константы
        # (standing.py:160-173, table_full.py:38-42), ρ от T не зависит.
        # Если тепловые свойства станут функциями T, здесь надо будет
        # перейти на st_prev.T, иначе баланс разойдётся с решателем.
        delta_E[n] = delta_E[n - 1] + np.sum(
            rho_cp_n * V * (st.T - history.states[n - 1].T))

        dt_step = t_arr[n] - t_arr[n - 1]
        st_prev = history.states[n - 1]
        hydro = history.hydro_results[n]

        p, Sg, Rs, T_prev = st.p, st.Sg, st.Rs, st_prev.T
        So = 1.0 - Sg
        Q_o, Q_g, G_o = hydro.Q_o, hydro.Q_g, hydro.G_o

        rho_o, rho_g, cp_o, cp_g, _ = _cell_properties(
            pvt, rock, p, Sg, Rs, T_prev)
        mu_JT_o = pvt.mu_JT_oil(p, T_prev)
        mu_JT_g = pvt.mu_JT_gas(p, T_prev)
        L = pvt.L_degas(p, T_prev)

        # ── Конвекция (обе фазы) ──
        # Φ_α = ρ_α cp_α Q_α (eq. 23). Знак: Q < 0 (поток к скважине) ⇒ Φ < 0.
        # Φ на ВСЕХ гранях, upstream раздельно по каждой фазе — как в
        # tridiag.compute_convective_coefficients. Телескопировать по двум
        # крайним граням нельзя: при противотоке фаз (Φ_o и Φ_g разных
        # знаков на одной грани) сумма Φ⁺/Φ⁻ не сводится к разности
        # крайних потоков.
        Phi_o = np.zeros(N + 1)
        Phi_g = np.zeros(N + 1)
        for f in range(1, N):
            up_o = f - 1 if Q_o[f] >= 0 else f
            Phi_o[f] = rho_o[up_o] * cp_o[up_o] * Q_o[f]
            up_g = f - 1 if Q_g[f] >= 0 else f
            Phi_g[f] = rho_g[up_g] * cp_g[up_g] * Q_g[f]
        # Забой (f=0): upstream — ячейка 0. Контур (f=N): upstream — N-1.
        Phi_o[0] = rho_o[0] * cp_o[0] * Q_o[0]
        Phi_g[0] = rho_g[0] * cp_g[0] * Q_g[0]
        Phi_o[N] = rho_o[-1] * cp_o[-1] * Q_o[N]
        Phi_g[N] = rho_g[-1] * cp_g[-1] * Q_g[N]

        Phi_plus = np.maximum(Phi_o, 0.0) + np.maximum(Phi_g, 0.0)
        Phi_minus = np.minimum(Phi_o, 0.0) + np.minimum(Phi_g, 0.0)

        # Поток энтальпии через грань f: Φ⁺ несёт T ячейки слева (f-1),
        # Φ⁻ — T ячейки справа (f). За контуром (f=N) справа — T_ext,
        # за забоем (f=0) слева — та же ячейка 0 (ГУ Неймана, ∂T/∂r = 0).
        T_left = np.concatenate(([T_prev[0]], T_prev))          # [N+1]
        T_right = np.concatenate((T_prev, [T_ext]))             # [N+1]
        flux = Phi_plus * T_left + Phi_minus * T_right
        # Чистая конвекция в область: -(поток через контур - через забой).
        net_conv = -(flux[N] - flux[0]) * dt_step

        # ── Джоуль–Томсон (обе фазы) ──
        # J_face = Σ_α μ_JT,α Φ_α p_up; сумма по ячейкам телескопируется
        # до J_face[N] - J_face[0]. Φ теперь массивы по граням: забой —
        # индекс 0, контур — индекс N.
        # При μ_JT = 0 (примеры 01, 07, 09) член обнуляется сам.
        J_well = (mu_JT_o[0] * Phi_o[0] + mu_JT_g[0] * Phi_g[0]) * p[0]
        J_ext = (mu_JT_o[-1] * Phi_o[N] + mu_JT_g[-1] * Phi_g[N]) * p[-1]
        jt_step = (J_ext - J_well) * dt_step

        # ── Адиабатика (обе фазы) ──
        # Q_ad = φ Σ_α S_α (1 + ρ_α cp_α μ_JT,α) dp/dt, Вт/м³ (eq. 29).
        dp = st.p - st_prev.p
        adiab_step = phi * np.sum(
            V * (So * (1.0 + rho_o * cp_o * mu_JT_o)
                 + Sg * (1.0 + rho_g * cp_g * mu_JT_g)) * dp)

        # ── Скрытая теплота дегазации ──
        # Q_deg = -L·mdot, mdot = временная + конвективная части (eq. 31).
        # При L = 0 (примеры 01, 02, 07, 08) член обнуляется сам.
        # Временная: газ, вышедший из раствора в самой ячейке за шаг.
        mdot_time = (-rho_g_std * phi * So / pvt.Bo(p, Rs)
                     * (Rs - st_prev.Rs) / dt_step)
        # Конвективная: дивергенция потока растворённого газа <G^o·Rs>.
        R_conv = np.zeros(N + 1)
        for f in range(1, N):
            Go_p, Go_m = max(G_o[f], 0.0), min(G_o[f], 0.0)
            R_conv[f] = Go_p * Rs[f - 1] + Go_m * Rs[f]
        R_conv[0] = G_o[0] * Rs[0]
        R_conv[N] = (G_o[N] * Rs[N - 1] if G_o[N] >= 0
                     else G_o[N] * st_prev.Rs[-1])
        mdot_conv = -rho_g_std * (R_conv[1:] - R_conv[:-1]) / V
        mdot = mdot_time + mdot_conv
        deg_step = np.sum(-L * mdot * V) * dt_step

        cum_conv[n] = cum_conv[n - 1] + net_conv
        cum_adiab[n] = cum_adiab[n - 1] + adiab_step
        cum_jt[n] = cum_jt[n - 1] + jt_step
        cum_deg[n] = cum_deg[n - 1] + deg_step

    total = cum_conv + cum_adiab + cum_jt + cum_deg + cum_cond
    residual = delta_E - total

    # Нормируем на больший из масштабов: на первых шагах ΔE ещё мало,
    # и деление на него дало бы ложный всплеск невязки.
    scale = np.maximum(np.abs(delta_E), np.abs(total))
    scale = np.where(scale < 1e-10, 1.0, scale)

    return dict(
        t=t_arr, delta_E=delta_E,
        cum_adiab=cum_adiab, cum_conv=cum_conv,
        cum_jt=cum_jt, cum_deg=cum_deg, cum_cond=cum_cond,
        total=total, residual=residual,
        rel_residual=np.abs(residual) / scale,
    )


def plot_energy_balance(history, grid, config, output_dir: Path):
    """Построить график баланса энергии и вернуть финальную отн. невязку."""
    bal = compute_balance(history, grid, config)
    t_hours = bal["t"] / 3600.0

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})

    ax1.plot(t_hours, bal["delta_E"], 'k-', linewidth=2,
             label=r"$\Delta E$ (накопление)")
    ax1.plot(t_hours, bal["cum_adiab"], 'b--', linewidth=1.5,
             label="адиабатика (кумул.)")
    ax1.plot(t_hours, bal["cum_conv"], 'r--', linewidth=1.5,
             label="чистая конвекция (кумул.)")
    ax1.plot(t_hours, bal["cum_jt"], 'm--', linewidth=1.5,
             label="Джоуль–Томсон (кумул.)")
    ax1.plot(t_hours, bal["cum_deg"], 'c--', linewidth=1.5,
             label="скрытая теплота (кумул.)")
    # Кондукция рисуется всегда: при λ = 0 кривая лежит на нуле, и это
    # наглядно показывает, что член учтён, а не забыт.
    ax1.plot(t_hours, bal["cum_cond"], color='olive', linestyle='--',
             linewidth=1.5, label="теплопроводность (кумул.)")
    ax1.plot(t_hours, bal["total"], 'g:', linewidth=1.5,
             label="сумма источников")
    ax1.set_ylabel("Энергия, Дж")
    ax1.legend(fontsize=9)
    # Имя примера берём из пути к конфигу: жёстко прописанный номер
    # в общем модуле был бы неверен для девяти примеров из десяти.
    ax1.set_title(f"Баланс энергии — {Path(config.config_dir).name}")
    ax1.grid(True, alpha=0.3)
    ax1.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

    ax2.plot(t_hours, bal["rel_residual"], 'k-', linewidth=1)
    ax2.set_xlabel("Время, ч")
    ax2.set_ylabel(r"|невязка| / |$\Delta E$|")
    ax2.set_title("Относительная невязка баланса")
    ax2.grid(True, alpha=0.3)
    ax2.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

    fig.tight_layout()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "energy_balance.png"
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"Сохранён: {out_path}")

    final_rel = abs(bal["residual"][-1] / (abs(bal["delta_E"][-1]) + 1e-30))
    print(f"  ΔE финал          = {bal['delta_E'][-1]:+.4e} Дж")
    print(f"  Адиабатика финал  = {bal['cum_adiab'][-1]:+.4e} Дж")
    print(f"  Конвекция финал   = {bal['cum_conv'][-1]:+.4e} Дж")
    print(f"  Джоуль-Томсон     = {bal['cum_jt'][-1]:+.4e} Дж")
    print(f"  Скрытая теплота   = {bal['cum_deg'][-1]:+.4e} Дж")
    print(f"  Теплопроводность  = {bal['cum_cond'][-1]:+.4e} Дж")
    print(f"  Невязка финал     = {bal['residual'][-1]:+.4e} Дж  "
          f"({final_rel:.2e})")
    return final_rel


def report_energy_balance(config, history, grid, simulator) -> dict:
    """Баланс энергии для run_example — конвенция общих модулей.

    simulator в расчёте не участвует: compute_balance пересобирает нужные
    объекты сам по config (фабрика дешёвая, прогон не повторяется).
    Аргумент принимается ради единообразия вызова из run_example.
    """
    bal = compute_balance(history, grid, config)

    print("── Баланс энергии ──")
    print(f"  ΔE финал = {bal['delta_E'][-1]:+.4e} Дж, "
          f"сумма источников = {bal['total'][-1]:+.4e} Дж")
    print(f"  относительная невязка = {bal['rel_residual'][-1]:.4e}")
    print(f"    (остаток — ошибка расщепления O(Δt): гидро-шаг замораживает "
          f"T, тепловой шаг — p и S_g)")
    return bal


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
            "укажите пример: python examples\\energy_balance.py 03")

    folder = _resolve_example(sys.argv[1])
    config = load_config(folder / "config.json")
    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)

    plot_energy_balance(history, sim._grid, config, folder / "output")
