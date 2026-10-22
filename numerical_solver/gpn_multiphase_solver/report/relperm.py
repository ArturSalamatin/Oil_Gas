"""График относительных фазовых проницаемостей — штатный рисунок relperm.png (FEAT-030: из examples/relperm_plot.py).

Кривые ОФП замыкают систему уравнений фильтрации, но в штатном наборе
графиков (p, S_g, T, дебиты) их не видно. Между тем именно они объясняют,
почему при одинаковом давлении примеры дают разную насыщенность: в стационаре
насыщенность находится из локального условия GOR = Rs0 (см.
03/README, п. 2), и обращается там как раз отношение k_rg/k_ro.

Модуль работает с ЛЮБОЙ моделью ОФП — и с аналитической (Corey), и с
табличной. Кривые берутся у того же объекта `RelPermModel`, который считал
задачу (объект решателя `Simulator.relperm`, без решателя — фабрика
`create_relperm`), поэтому график показывает ровно то, что видел решатель,
а не повторную реализацию формул или CSV.

Само построение — gpn_multiphase_solver.io.output.plot_relperm_curves
(DEBT-011); здесь подпись модели по конфигу, рабочий диапазон из истории,
запись PNG и печать.

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

# Режим matplotlib модуль не выбирает: это делает команда расчёта
# (cli.configure_batch_run) или вызывающий скрипт (FEAT-030)
import matplotlib.pyplot as plt
import numpy as np

# PNG + SVG/EMF в output/emf/ (FEAT-026); EMF делает пакетом run_case.
from ..io.figures import save_figure
from ..io.output import plot_relperm_curves


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
    """Построить рисунок ОФП ``relperm.png``: кривые модели и рабочий диапазон газонасыщенности расчёта.

    Кривые k_ro(S_g), k_rg(S_g) рисуются на всём диапазоне насыщенности и
    отдельной панелью – в увеличенном масштабе на рабочем диапазоне
    расчёта, где проходит граница подвижного газа; у табличной модели
    отмечены узлы таблицы. У однофазного расчёта панель одна. Рисунок
    сохраняется функцией :func:`save_figure`: PNG и, если вывод
    векторных рисунков не выключен, SVG в подкаталоге ``emf/``.

    Параметры
    ---------
    config : SimulationConfig
        Конфигурация расчёта: модель ОФП и подпись к ней.
    history : SimulationHistory
        История расчёта: диапазон газонасыщенности по всем ячейкам всех записей.
    output_dir : str or pathlib.Path
        Каталог результатов; создаётся, если его нет.
    title : str
        Заголовок рисунка: первая строка, вторая – описание модели ОФП.
    relperm : RelPermModel, optional
        Модель ОФП расчёта (``simulator.relperm``); ``None`` – строится
        заново по конфигурации (:func:`create_relperm`).

    Возвращает
    ----------
    pathlib.Path
        Путь записанного ``relperm.png``.
    """
    if relperm is None:
        from ..factory import create_relperm
        relperm = create_relperm(config)

    axes = plot_relperm_curves(relperm, _sg_range(history),
                               title=f"{title}\nОФП — {_describe(config)}")
    fig = axes[0, 0].figure

    fig.tight_layout()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "relperm.png"
    save_figure(fig, out, dpi=120)
    plt.close(fig)
    return out


# Отношение k_rg/k_ro печатается отдельно: именно оно, а не сами кривые,
# входит в замыкание GOR = Rs0 и определяет насыщенность в стационаре
def report_relperm(config, history, relperm=None) -> None:
    """Напечатать ОФП на рабочем диапазоне газонасыщенности расчёта.

    Печатает k_ro, k_rg и их отношение при S_g = 0, на середине и на
    наибольшей газонасыщенности расчёта; у однофазного расчёта — одну
    строку о том, что ОФП не задействованы.

    Параметры
    ---------
    config : SimulationConfig
        Конфигурация расчёта.
    history : SimulationHistory
        История расчёта: диапазон газонасыщенности по всем записям.
    relperm : RelPermModel, optional
        Модель ОФП расчёта (``simulator.relperm``); ``None`` — строится
        заново по конфигурации (:func:`create_relperm`).
    """
    if relperm is None:
        from ..factory import create_relperm
        relperm = create_relperm(config)

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
