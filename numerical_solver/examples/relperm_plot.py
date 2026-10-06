"""График относительных фазовых проницаемостей — общий для всех примеров.

Кривые ОФП замыкают систему уравнений фильтрации, но в штатном наборе
графиков (p, S_g, T, дебиты) их не видно. Между тем именно они объясняют,
почему при одинаковом давлении примеры дают разную насыщенность: в стационаре
насыщенность находится из локального условия GOR = Rs0 (см.
03/README, п. 2), и обращается там как раз отношение k_rg/k_ro.

Модуль работает с ЛЮБОЙ моделью ОФП — и с аналитической (Corey), и с
табличной. Кривые берутся у того же объекта `RelPermModel`, который считал
задачу (через `factory._create_relperm`), поэтому график показывает ровно то,
что видел решатель, а не повторную реализацию формул или CSV.

Что на графике:

  панель 1 — k_ro(S_g) и k_rg(S_g) на всём диапазоне; для табличной модели
             дополнительно отмечены узлы таблицы (между ними интерполяция
             линейна, в самих узлах — изломы, которые напрямую переходят
             в изломы подвижности);
  панель 2 — увеличение на РАБОЧЕМ диапазоне: расчёт обычно использует лишь
             малую часть кривой, и на общем масштабе не видно, что там
             происходит. Для примеров с S_g ~ 0.01 это принципиально:
             у Corey с порогом S_gc газ в этом диапазоне ещё неподвижен.

Однофазные сценарии (Rs0 = 0) газа не имеют вовсе; для них рисуется только
панель 1 с пометкой, что рабочий диапазон вырожден в точку S_g = 0.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# PNG + SVG/EMF в output/emf/ (FEAT-026); EMF делает пакетом run_example.
from figure_io import save_figure  # noqa: E402


def _table_nodes(relperm):
    """Узлы таблицы (Sg, kro, krg), если модель табличная, иначе None.

    PrototypeRPAdapter оборачивает TabulatedRelPerm прототипа в `_rp`;
    там узлы лежат в полях sg / kro_tab / krg_tab (radial_blackoil/relperm.py).
    У аналитических моделей (CoreyRP) выделенных точек нет — возвращаем None.
    """
    proto = getattr(relperm, "_rp", None)
    if proto is None or not hasattr(proto, "sg"):
        return None
    return (np.asarray(proto.sg, float),
            np.asarray(proto.kro_tab, float),
            np.asarray(proto.krg_tab, float))


def _sg_range(history) -> tuple[float, float]:
    """Рабочий диапазон S_g: min и max по всем ячейкам всех записей истории."""
    # По ВСЕЙ истории: газ мог выделиться и раствориться обратно (останов
    # скважины, пример 16 — S_g ≡ 0 на последней записи при S_g до 0.048 за
    # добычу) или пройти пиком в первые сутки (11, 12, 13b). Последняя
    # запись объявила бы такой расчёт однофазным (FEAT-019).
    sg = np.concatenate([s.Sg for s in history.states])
    return float(sg.min()), float(sg.max())


def _describe(config) -> str:
    """Подпись модели ОФП по конфигу — что именно нарисовано."""
    rp = config.relperm
    if rp.model == "corey":
        return (f"Corey: $S_{{or}}$={rp.S_or}, $S_{{gc}}$={rp.S_gc}, "
                f"$n_o$={rp.n_o}, $n_g$={rp.n_g}, "
                f"$k_{{ro}}^{{max}}$={rp.kro_max}, $k_{{rg}}^{{max}}$={rp.krg_max}")
    if rp.model == "table":
        return f"таблица из {rp.file} (линейная интерполяция)"
    return f"модель: {rp.model}"


def plot_relperm(config, history, output_dir: Path, title: str,
                 relperm=None) -> Path:
    """Построить relperm.png: кривые ОФП + рабочий диапазон расчёта.

    config   — SimulatorConfig (нужен для сборки ОФП и подписи модели)
    history  — SimulationHistory; по всем записям берётся диапазон S_g
    relperm  — готовая модель ОФП; если None, собирается фабрикой

    Возвращает путь к сохранённому PNG.
    """
    if relperm is None:
        from gpn_multiphase_solver.factory import _create_relperm
        relperm = _create_relperm(config)

    Sg_lo, Sg_hi = _sg_range(history)
    # Однофазный сценарий: газ не выделялся вовсе, увеличивать нечего.
    two_phase = Sg_hi > 1e-12

    nodes = _table_nodes(relperm)
    S = np.linspace(0.0, 1.0, 1000)
    kro, krg = relperm.kro(S), relperm.krg(S)

    n_panels = 2 if two_phase else 1
    fig, axes = plt.subplots(1, n_panels, figsize=(6.5 * n_panels, 5),
                             squeeze=False)
    ax1 = axes[0, 0]

    # ── Панель 1: кривые целиком ─────────────────────────────────
    ax1.plot(S, kro, "-", color="C3", lw=2, label=r"$k_{ro}$ (нефть)")
    ax1.plot(S, krg, "-", color="C0", lw=2, label=r"$k_{rg}$ (газ)")

    if nodes is not None:
        # Узлы показываем только для табличной модели: у аналитической
        # никаких выделенных точек нет, и маркеры вводили бы в заблуждение.
        Sn, kron, krgn = nodes
        ax1.plot(Sn, kron, "o", color="C3", ms=6, zorder=5)
        ax1.plot(Sn, krgn, "o", color="C0", ms=6, zorder=5,
                 label="узлы таблицы")

    if two_phase:
        ax1.axvspan(Sg_lo, Sg_hi, color="C2", alpha=0.18,
                    label=rf"рабочий диапазон: $S_g \leq {Sg_hi:.4f}$")
    else:
        ax1.axvline(0.0, color="C2", lw=2,
                    label="однофазный расчёт: $S_g \\equiv 0$")

    ax1.set_xlabel("$S_g$")
    ax1.set_ylabel("относительная проницаемость")
    ax1.set_title(f"{title}\nОФП — {_describe(config)}", fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=8)

    # ── Панель 2: увеличение на рабочем диапазоне ────────────────
    if two_phase:
        ax2 = axes[0, 1]
        # Показываем немного шире достигнутого максимума, чтобы видеть,
        # куда кривая идёт дальше; но не больше, чем до 0.15 — иначе
        # рабочая зона снова станет неразличимой.
        #
        # Кламп 0.15 нужен примерам с S_g ~ 0.01: без него рабочая зона
        # сжимается в неразличимую полоску. Но при высокой насыщенности
        # (S_g ~ 0.7) он, наоборот, обрезает рабочий диапазон и выносит
        # маркер S_g^max за границы осей — поэтому потолок не ниже самого
        # S_g^max с запасом 15 %. Порог переключения S_g^max = 0.1304:
        # ниже него действует кламп 0.15.
        S_hi_plot = min(max(Sg_hi * 3.0, 0.02), max(0.15, min(1.0, Sg_hi * 1.15)))
        Sz = np.linspace(0.0, S_hi_plot, 500)

        # Две оси: в рабочем диапазоне k_ro ~ 1, а k_rg ~ 1e-3, и на одной
        # шкале газовая кривая ложится на ноль неотличимо от прямой.
        # Правая ось (k_rg) — та величина, ради которой график и строится:
        # именно её поведение у малых S_g различает модели ОФП.
        ax2b = ax2.twinx()
        ax2.plot(Sz, relperm.kro(Sz), "-", color="C3", lw=2,
                 label=r"$k_{ro}$ (левая ось)")
        ax2b.plot(Sz, relperm.krg(Sz), "-", color="C0", lw=2,
                  label=r"$k_{rg}$ (правая ось)")

        if nodes is not None:
            Sn, kron, krgn = nodes
            inside = Sn <= S_hi_plot
            ax2.plot(Sn[inside], kron[inside], "o", color="C3", ms=6, zorder=5)
            ax2b.plot(Sn[inside], krgn[inside], "o", color="C0", ms=6, zorder=5)

        ax2.axvspan(Sg_lo, Sg_hi, color="C2", alpha=0.18)
        ax2.axvline(Sg_hi, color="C2", lw=1.2, ls="--",
                    label=rf"$S_g^{{max}}$ = {Sg_hi:.5f}")

        # Значения на рабочем максимуме: именно они определяют подвижности,
        # а через них — дебит и распределение потоков между фазами.
        kro_w = float(relperm.kro(np.array([Sg_hi]))[0])
        krg_w = float(relperm.krg(np.array([Sg_hi]))[0])
        ax2.plot([Sg_hi], [kro_w], "s", color="C3", ms=7, zorder=6)
        ax2b.plot([Sg_hi], [krg_w], "s", color="C0", ms=7, zorder=6)
        ax2.set_title(f"Рабочий диапазон расчёта\n"
                      f"$k_{{ro}}$({Sg_hi:.4f}) = {kro_w:.4f},   "
                      f"$k_{{rg}}$({Sg_hi:.4f}) = {krg_w:.3e}", fontsize=9)

        ax2.set_xlim(0.0, S_hi_plot)
        ax2.set_xlabel("$S_g$")
        ax2.set_ylabel(r"$k_{ro}$ (нефть)", color="C3")
        ax2b.set_ylabel(r"$k_{rg}$ (газ)", color="C0")
        ax2.tick_params(axis="y", labelcolor="C3")
        ax2b.tick_params(axis="y", labelcolor="C0")
        # Обе шкалы от нуля: иначе автомасштаб скрывает, насколько k_rg мала
        # в абсолютном выражении.
        ax2.set_ylim(bottom=0.0)
        ax2b.set_ylim(bottom=0.0)
        ax2.grid(True, alpha=0.3)

        # Легенды двух осей объединяем — иначе получаются две коробки.
        h1, l1 = ax2.get_legend_handles_labels()
        h2, l2 = ax2b.get_legend_handles_labels()
        ax2.legend(h1 + h2, l1 + l2, fontsize=8, loc="center right")

    fig.tight_layout()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "relperm.png"
    save_figure(fig, out, dpi=120)
    plt.close(fig)
    return out


def report_relperm(config, history, relperm=None) -> None:
    """Печать характеристик ОФП на рабочем диапазоне.

    Отношение k_rg/k_ro печатается отдельно: именно оно, а не сами кривые,
    входит в замыкание GOR = Rs0 и определяет насыщенность в стационаре.
    """
    if relperm is None:
        from gpn_multiphase_solver.factory import _create_relperm
        relperm = _create_relperm(config)

    Sg_lo, Sg_hi = _sg_range(history)

    print(f"── ОФП: {config.relperm.model} ──")
    if Sg_hi <= 1e-12:
        print("  расчёт однофазный (S_g ≡ 0), ОФП не задействованы:"
              " k_ro = k_ro(0), k_rg = 0")
        return

    print(f"  рабочий диапазон: S_g = {Sg_lo:.6f} … {Sg_hi:.6f}")
    print(f"  {'S_g':>10} {'k_ro':>12} {'k_rg':>12} {'k_rg/k_ro':>12}")
    for s in (0.0, Sg_hi / 2.0, Sg_hi):
        a = np.array([s])
        o, g = float(relperm.kro(a)[0]), float(relperm.krg(a)[0])
        ratio = f"{g / o:.4e}" if o > 0 else "inf"
        print(f"  {s:10.6f} {o:12.5f} {g:12.4e} {ratio:>12}")
