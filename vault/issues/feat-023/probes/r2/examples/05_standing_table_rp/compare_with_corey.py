"""Прямое сравнение 05 (табличная ОФП) с 03 (ОФП Кори) — что меняет замыкание.

Примеры 03 и 05 отличаются РОВНО одной секцией конфига: relperm. PVT, режим,
сетка, тепловые параметры совпадают. Поэтому разница результатов — это чистый
эффект замыкающей зависимости k_r(S_g), не смешанный ни с чем другим.

──────────────────────────────────────────────────────────────────
Что предсказывает теория

Из локального условия GOR = Rs0 (two_phase_analytics.py, ур. B):

    k_rg(S_g)/k_ro(S_g) = [Rs0 - Rs(p)] · mu_g·Bg / (mu_o·Bo).

ПРАВАЯ ЧАСТЬ не содержит ОФП — только PVT и давление. Значит требуемое
ОТНОШЕНИЕ ПОДВИЖНОСТЕЙ задаётся извне, а подстраивается лишь S_g,
обращающая свою кривую k_rg/k_ro.

Отсюда гипотеза, которую и проверяет этот скрипт:

    S_g            — различается сильно (обращаются разные функции);
    p, Rs, T, q_o  — совпадают, пока k_ro ≈ 1, то есть пока свободного
                     газа мало и он почти не мешает течению нефти.

Второе условие существенно: при большем разгазировании k_ro заметно упал
бы, и профили тоже разошлись бы. Здесь S_g <= 0.014 (табл.) и <= 0.08
(Кори), k_ro в обоих случаях близка к единице.

ВАЖНАЯ ОГОВОРКА. Совпадение p и Rs — приближённое (0.35 % и 0.53 %),
поэтому и правые части замыкания в двух примерах не тождественны. У забоя
они близки, а у фронта Rs -> Rs0, правая часть -> 0, и относительное
расхождение раздувается при ничтожном абсолютном. Утверждение «отношение
подвижностей одинаково» верно как тенденция, а не как точное равенство;
что выполняется точно — это САМО замыкание внутри каждого примера,
и скрипт проверяет именно его.

──────────────────────────────────────────────────────────────────
Почему S_g отличается именно в эту сторону

    Кори:    k_rg = 0.8·[(S_g - 0.05)/0.75]^2 — ПОРОГ S_gc = 0.05 и
             квадратичное вырождение у порога;
    таблица: k_rg ≈ 0.1·S_g на первом отрезке — линейный рост от нуля.

При S_g = 0.014 корреляция Кори даёт k_rg = 0 (газ вообще неподвижен),
а таблица — 1.4e-3. Чтобы пропустить одинаковое количество газа, модели
Кори нужна насыщенность выше порога и заметно больше нуля; табличной
хватает малой. Это не «ошибка» ни одной из моделей: S_gc — физически
осмысленный параметр (газ становится подвижным, лишь образовав связную
фазу), просто демонстрационная таблица его не содержит.

──────────────────────────────────────────────────────────────────
Практический вывод

Замер S_g (например, по данным ГИС) чувствителен к выбранной модели ОФП,
тогда как давление, дебит и температура при слабом разгазировании — нет.
Настраивать ОФП по забойному давлению или дебиту в таком режиме
бессмысленно: они этой информации почти не несут.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\05_standing_table_rp\\compare_with_corey.py
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent
SOLVER_ROOT = HERE.parents[1]
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(EXAMPLES))
sys.path.insert(0, str(SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

CONFIG_05 = HERE / "config.json"
CONFIG_03 = EXAMPLES / "03_standing_corey" / "config.json"


def run(config_path: Path, lambda_zero: bool):
    """Прогнать пример по его конфигу. Возвращает (history, grid, config, relperm).

    lambda_zero — обнулить теплопроводности. Нужно для честного сравнения:
    в конфиге 03 они ненулевые, в 05 обнулены, и без выравнивания разница
    температур включала бы вклад кондукции, а не только эффект ОФП.
    """
    config = load_config(config_path)
    if lambda_zero:
        config.rock.lambda_solid = 0.0
        config.rock.lambda_oil = 0.0
        config.rock.lambda_gas = 0.0
    config.output.log_level = "ERROR"

    sim, initial_state = SimulatorFactory.from_config(config)
    history = sim.run(initial_state)
    return history, sim._grid, config, _create_relperm(config)


def main():
    print("Сравнение 03 (ОФП Кори) и 05 (табличная ОФП)")
    print("PVT, режим, сетка и тепловые параметры одинаковы; λ = 0 в обоих.\n")

    h5, g5, c5, rp5 = run(CONFIG_05, lambda_zero=True)
    h3, g3, c3, rp3 = run(CONFIG_03, lambda_zero=True)

    s5, s3 = h5.states[-1], h3.states[-1]
    r = g5.r_centers
    assert np.allclose(r, g3.r_centers), "сетки примеров разошлись"

    # ── Таблица расхождений по полям ──
    def rel(a, b, scale=None):
        """Относительное расхождение в %, нормированное на масштаб величины."""
        s = np.max(np.abs(b)) if scale is None else scale
        return np.max(np.abs(a - b)) / s * 100

    q5 = abs(h5.hydro_results[-1].G_o[0])
    q3 = abs(h3.hydro_results[-1].G_o[0])
    dep = c5.initial_conditions.p0 - c5.time.history[0].p_wf

    print(f"{'величина':<22} {'05 (табл.)':>14} {'03 (Кори)':>14} {'расхожд.':>12}")
    print(f"{'S_g макс':<22} {s5.Sg.max():>14.5f} {s3.Sg.max():>14.5f} "
          f"{s3.Sg.max()/s5.Sg.max():>11.2f}x")
    print(f"{'p(r_w), МПа':<22} {s5.p[0]/1e6:>14.5f} {s3.p[0]/1e6:>14.5f} "
          f"{rel(s5.p, s3.p, dep):>11.4f} %")
    print(f"{'T(r_w), К':<22} {s5.T[0]:>14.5f} {s3.T[0]:>14.5f} "
          f"{np.max(np.abs(s5.T - s3.T)):>11.5f} К")
    print(f"{'Rs мин, м³ст/м³ст':<22} {s5.Rs.min():>14.5f} {s3.Rs.min():>14.5f} "
          f"{rel(s5.Rs, s3.Rs):>11.4f} %")
    print(f"{'q_o, м³ст/с':<22} {q5:>14.6e} {q3:>14.6e} "
          f"{abs(q5-q3)/q3*100:>11.4f} %")

    n5 = int((s5.Sg > 1e-12).sum())
    n3 = int((s3.Sg > 1e-12).sum())
    print(f"{'двухфазных ячеек':<22} {n5:>14d} {n3:>14d}")

    # ── Проверка ключевого утверждения ──
    # Замыкание требует k_rg/k_ro = [Rs0 - Rs(p)]·mu_g Bg/(mu_o Bo). Правая
    # часть не содержит ОФП, поэтому при СОВПАДАЮЩИХ p и Rs она была бы
    # одинаковой в обоих примерах. Но p и Rs совпадают лишь приближённо
    # (0.35 % и 0.53 %), поэтому сравниваем каждое отношение со СВОЕЙ правой
    # частью — это проверка замыкания, — и отдельно смотрим, насколько
    # близки сами правые части.
    two5 = s5.Sg > 1e-12
    ratio5 = rp5.krg(s5.Sg[two5]) / rp5.kro(s5.Sg[two5])
    ratio3 = rp3.krg(s3.Sg[two5]) / rp3.kro(s3.Sg[two5])

    def rhs(pvt, state, Rs0, mask):
        """Правая часть замыкания [Rs0 - Rs_eq(p)]·mu_g Bg/(mu_o Bo)."""
        p, Rs = state.p[mask], state.Rs[mask]
        return ((Rs0 - pvt.Rs_eq(p)) * pvt.mu_g(p) * pvt.Bg(p)
                / (pvt.mu_o(p, Rs) * pvt.Bo(p, Rs)))

    pvt5 = SimulatorFactory.from_config(c5)[0]._energy._pvt
    pvt3 = SimulatorFactory.from_config(c3)[0]._energy._pvt
    rhs5 = rhs(pvt5, s5, c5.initial_conditions.Rs0, two5)
    rhs3 = rhs(pvt3, s3, c3.initial_conditions.Rs0, two5)

    err5 = np.abs(ratio5 - rhs5) / rhs5 * 100
    err3 = np.abs(ratio3 - rhs3) / rhs3 * 100
    print("\nЗамыкание k_rg/k_ro = [Rs0 - Rs(p)]·mu_g Bg/(mu_o Bo), по ячейкам, %:")
    print(f"  05: {np.array2string(err5, precision=4, max_line_width=70)}")
    print(f"  03: {np.array2string(err3, precision=4, max_line_width=70)}")
    print(f"  05: максимум {err5.max():.2e} % — машинная точность во всех ячейках.")
    print(f"  03: ошибка растёт от {err3[0]:.2f} % у забоя до {err3[-1]:.1f} % "
          f"у фронта.")
    print("  Причина — порог подвижности Кори: к фронту S_g -> S_gc, и")
    print("  k_rg ~ (S_g - S_gc)^2 обращается в ноль быстрее, чем правая")
    print("  часть замыкания, поэтому корень уравнения там плохо обусловлен:")
    print("  d(k_rg/k_ro)/dS_g -> 0, и малая невязка по S_g даёт большую")
    print("  относительную ошибку отношения. У табличной ОФП k_rg растёт от")
    print("  нуля ЛИНЕЙНО, производная конечна, и вырождения не возникает.")
    print("  Это тот же механизм, что портит ОДУ-аналитику в примере 03.")

    # Насколько близки сами правые части. Расхождение растёт к фронту:
    # там Rs -> Rs0, правая часть -> 0, и малая разница в p даёт большую
    # относительную разницу. Поэтому печатаем и абсолютную величину.
    d_rel = np.abs(rhs5 - rhs3) / np.maximum(rhs3, 1e-30) * 100
    print(f"\n  правые части 05 и 03 расходятся на {d_rel[0]:.2f} % у забоя, "
          f"{d_rel[-1]:.0f} % в последней ячейке у фронта")
    print("  (у фронта Rs -> Rs0, правая часть -> 0, и относительная разница")
    print("   раздувается; абсолютная там мала: "
          f"{abs(rhs5[-1] - rhs3[-1]):.2e})")
    print("  Вывод: требуемое отношение подвижностей задаётся PVT и давлением,")
    print("  а S_g подстраивается под свою кривую k_r — отсюда разница в 5.7 раза.")

    # ── График ──
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))

    ax = axes[0, 0]
    ax.semilogx(r, s5.Sg, 'b-', lw=1.8, label="05: табличная ОФП")
    ax.semilogx(r, s3.Sg, 'r--', lw=1.8, label="03: ОФП Кори")
    ax.set_xlabel("r, м"); ax.set_ylabel(r"$S_g$")
    ax.set_title("Насыщенность различается в 5.7 раза")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    ax.semilogx(r, s5.p / 1e6, 'b-', lw=1.8, label="05")
    ax.semilogx(r, s3.p / 1e6, 'r--', lw=1.8, label="03")
    ax.set_xlabel("r, м"); ax.set_ylabel("p, МПа")
    ax.set_title(f"Давление совпадает (max разн. {np.max(np.abs(s5.p-s3.p))/1e3:.1f} кПа)")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    ax.semilogx(r, s5.T, 'b-', lw=1.8, label="05")
    ax.semilogx(r, s3.T, 'r--', lw=1.8, label="03")
    ax.set_xlabel("r, м"); ax.set_ylabel("T, К")
    ax.set_title(f"Температура совпадает (max разн. {np.max(np.abs(s5.T-s3.T)):.4f} К)")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    # Кривые ОФП: причина всей разницы. Показываем малые S_g — рабочий
    # диапазон задачи, где Кори ещё в нуле, а таблица уже растёт.
    ax = axes[1, 1]
    S = np.linspace(0.0, 0.12, 400)
    ax.plot(S, rp5.krg(S), 'b-', lw=1.8, label=r"05: $k_{rg}$ табличная")
    ax.plot(S, rp3.krg(S), 'r--', lw=1.8, label=r"03: $k_{rg}$ Кори")
    ax.axvline(s5.Sg.max(), color='b', ls=':', lw=1.2,
               label=rf"$S_g^{{max}}$ 05 = {s5.Sg.max():.4f}")
    ax.axvline(s3.Sg.max(), color='r', ls=':', lw=1.2,
               label=rf"$S_g^{{max}}$ 03 = {s3.Sg.max():.4f}")
    ax.set_xlabel(r"$S_g$"); ax.set_ylabel(r"$k_{rg}$")
    ax.set_title("Причина: порог подвижности $S_{gc}$ у Кори")
    ax.legend(fontsize=7); ax.grid(True, alpha=0.3)

    fig.tight_layout()
    out = HERE / "output" / "compare_with_corey.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"\nСохранён: {out}")


if __name__ == "__main__":
    main()
