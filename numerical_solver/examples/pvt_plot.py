"""График PVT-свойств — общий для всех примеров.

PVT-свойства замыкают систему уравнений фильтрации, но в штатном наборе
графиков (p, S_g, T, дебиты) их не видно. Между тем именно они определяют
профиль давления, дебит и положение фронта разгазирования — сильнее, чем
ОФП.

Приоритет по постановке задачи — вязкость mu_o и газосодержание Rs НЕФТЯНОЙ
фазы: первая входит в подвижность lambda_o = k*k_ro/mu_o, второе — в
замыкание GOR = Rs0.

Модуль — оформитель: само построение кривых делегируется ядру библиотеки
(`gpn_multiphase_solver.io.output.plot_pvt_properties`), чтобы та же функция
была доступна пользователю установленного пакета, а не только тому, кто
выгрузил репозиторий целиком (examples/ в дистрибутив не входит). Здесь
остаётся всё, что знает про config: извлечение Rs0, подпись модели, рабочий
диапазон из history, компоновка фигуры, запись PNG и печать сводки.

Что на графике (сетка 2x4):

  mu_o(p), Bo(p) — до трёх кривых:
      насыщенная    Rs = Rs_eq(p)              — тонкий пунктир
      недонасыщ.    Rs = Rs0 = const           — тонкий пунктир
      физическая    Rs = min(Rs_eq(p), Rs0)    — жирная сплошная
    Ветви рисуются только на «чужой» половине от p_b: на «своей» их
    полностью перекрыла бы физическая кривая, которая по построению
    min(...) с одной из них совпадает. Ветвь, совпадающая с физической
    тождественно, не рисуется вовсе — у табличного PVT выше p_b это
    насыщенная ветвь (Rs_eq == Rs0), и запись в легенде без линии
    читалась бы как дефект отрисовки.

  Rs(p)          — физическая кривая, Rs_eq(p) и горизонталь Rs0;
  mu_g(p), Bg(p) — по одной кривой; у табличного PVT Bg кусочно-линейна,
                   у Стендинга — гипербола p_ст*T0/(T_ст*p);
  плотности      — rho_o и rho_g на двух осях (twinx): нефть 730…800,
                   газ 40…140 кг/м³, на одной оси газовая нечитаема;
  mu_o(r)        — вязкость В ЯЧЕЙКАХ по последнему состоянию: насколько
                   узка зона, где свойство меняется (см. _plot_mu_o_spatial).

У моделей Стендинга при co_undersaturated = 0 (так во всех конфигах
примеров) Bo и mu_o от давления не зависят вовсе — считаются только по Rs.
Недонасыщенная ветвь выходит строго горизонтальной; это свойство модели,
а не дефект, и подпись панели об этом сообщает.

Однофазные сценарии: Rs0 = 0, p_b = -0.176 МПа (вне физической
области), ветви вырождены — физическая кривая тождественно совпадает
с недонасыщенной, а насыщенная нефизична (Rs_eq доходит до 138 м³ст/м³ст
при физическом Rs ≡ 0) и растянула бы ось. Поэтому при Rs0 = 0 ветви не
рисуются, а вертикаль p_b не наносится.

Отличие от существующего rs_profiles.png. Оба графика про Rs, но по разным
осям и про разное:

  rs_profiles.png — Rs по РАДИУСУ: где в пласте газ вышел из раствора,
                    где фронт r_b. Это про РЕШЕНИЕ задачи.
  панель Rs здесь — Rs по ДАВЛЕНИЮ: как Rs зависит от p, где p_b,
                    насколько груба таблица. Это про МОДЕЛЬ, которой
                    задачу решали.

Дублирования нет; панель mu_o(r) связывает две картины — у PVT Стендинга
радиус 90 % вариации вязкости практически совпадает с радиусом фронта
разгазирования, потому что mu_o там зависит только от Rs, а Rs меняется
ровно в разгазированной зоне.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from gpn_multiphase_solver.io.output import plot_pvt_properties  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402

# PVT берём у того же решателя, что считал задачу; помощник уже есть —
# заводить второй способ доступа к одному объекту незачем.
from temperature_asymptotics import _pvt_of  # noqa: E402
# PNG + SVG/EMF в output/emf/ (FEAT-026); EMF делает пакетом run_example.
from figure_io import save_figure  # noqa: E402


def _get_pvt(config, simulator):
    """PVT, которым считали задачу; без simulator — сборка фабрикой.

    Fallback нужен, чтобы модуль оставался вызываемым и без прогона
    (так его зовут тесты, у которых в кэше только history/grid/config).
    """
    if simulator is not None:
        return _pvt_of(simulator)
    from gpn_multiphase_solver.factory import _create_pvt
    return _create_pvt(config)


def _physical_rs(pvt, p: np.ndarray, Rs0: float) -> np.ndarray:
    """Газосодержание, реально бывшее в расчёте: min(Rs_eq(p), Rs0).

    p >= p_b — нефть недонасыщена, весь газ растворён, Rs держится на Rs0;
    p <  p_b — нефть насыщена, избыток выделился, Rs = Rs_eq(p).
    Та же формула, что в rs_analytics.rs_expected; ядро считает её само,
    здесь она нужна для сводки и для ординат узлов таблицы.
    """
    return np.minimum(pvt.Rs_eq(p), Rs0)


def _describe(config) -> str:
    """Подпись модели PVT по конфигу — что именно нарисовано."""
    pc = config.pvt
    if pc.model == "standing":
        s = (f"Standing/Beggs-Robinson, "
             f"$c_o$ = {pc.co_undersaturated:.3g} 1/Па")
        if pc.co_undersaturated == 0.0:
            # Иначе горизонтальная недонасыщенная ветвь читается как ошибка.
            s += r" ($B_o$ и $\mu_o$ от $p$ не зависят)"
        return s
    if pc.model == "table":
        return (f"таблицы {pc.oil_pvt_file}, {pc.gas_pvt_file} "
                f"(линейная интерполяция)")
    return f"модель: {pc.model}"


def _pvt_table_nodes(pvt, Rs0: float):
    """Узлы табличного PVT в Па, раздельно по фазам, иначе None.

    Цепочка обёрток: TableFullPVT._hydro -> PrototypePVTAdapter._pvt ->
    BlackOilPVT прототипа, где всё лежит в БАРАХ (поля gp, pb, branches).
    У аналитического PVT (Standing) выделенных точек нет — возвращаем None,
    маркеры на гладкой корреляции вводили бы в заблуждение.

    Ключи раздельные, потому что наборы разные по природе и идут на разные
    панели: газовая таблица — на mu_g/Bg, точки насыщения веток и узлы
    рисуемой ветки — на mu_o/Bo/Rs.

    Ординаты узлов здесь НЕ возвращаются: недонасыщенная ветка
    интерполируется по dp = p - pb(Rs), а не по p, поэтому значения
    считаются вызовом PVT в точке узла (это делает ядро).
    """
    hydro = getattr(pvt, "_hydro", None)
    proto = getattr(hydro, "_pvt", None) if hydro is not None else None
    if proto is None or not hasattr(proto, "gp"):
        return None

    p_gas = np.asarray(proto.gp, float) * BAR_TO_PA        # газовая таблица
    p_sat = np.asarray(proto.pb, float) * BAR_TO_PA        # точки насыщения
    # Узлы той ветки, что рисуется недонасыщенной (Rs = Rs0); в branches
    # они лежат в АБСОЛЮТНЫХ давлениях, а не в dp.
    rs_values = np.asarray(proto.rs_values, float)
    rs_near = min(proto.rs_values, key=lambda r: abs(r - Rs0))
    p_branch = np.array([x[0] for x in proto.branches[rs_near]],
                        float) * BAR_TO_PA

    return {
        "p_gas": p_gas,
        "p_oil": np.unique(np.concatenate([p_sat, p_branch])),
        "rs_values": rs_values,
    }


def _nodes_in_range(nodes, p_lo: float, p_hi: float) -> int:
    """Сколько узлов таблицы попало в рабочий диапазон давлений.

    Одна реализация на модуль: график и сводка обязаны сообщать одно
    число. Аналитический PVT узлов не имеет — тогда 0.
    """
    if nodes is None:
        return 0
    p_all = np.unique(np.concatenate([nodes["p_gas"], nodes["p_oil"]]))
    return int(np.sum((p_all >= p_lo) & (p_all <= p_hi)))


def _plot_mu_o_spatial(ax, pvt, history, grid, Rs0: float) -> None:
    """Вязкость нефти В ЯЧЕЙКАХ — то, что реально применял решатель.

    Панели mu_o(p) показывают свойство модели; эта — картину в пласте.
    Для ПЗП-задачи важно, НАСКОЛЬКО УЗКА зона повышенной вязкости:
    вся вариация может укладываться в доли метра при радиусе дренирования
    в десятки метров, и на графике по давлению это не видно.

    Rs берётся ИЗ СОСТОЯНИЯ, а не пересчитывается по Rs_eq(p): в зоне
    разгазирования это дало бы другую кривую.
    """
    st = history.states[-1]
    r = grid.r_centers
    mu = pvt.mu_o(st.p, st.Rs)
    pb = float(pvt.pb(np.array([Rs0]))[0])

    # semilogx — сетка логарифмическая, как во всех профильных графиках;
    # маркеры показывают дискретизацию.
    ax.semilogx(r, mu, "o-", ms=3, lw=1.5, color="C3")

    # Зона разгазирования: ниже p_b выделяется газ, mu_o растёт.
    # У однофазных примеров p_b < 0, ячеек ниже нет — заливки не будет.
    below = st.p < pb
    if below.any():
        ax.axvspan(r[0], r[below].max(), color="C1", alpha=0.2,
                   label=f"$p<p_b$: {int(below.sum())} ячеек, "
                         f"r < {r[below].max():.2f} м")

    # Радиус, внутри которого накоплено 90 % полной вариации mu_o.
    # Именно он отвечает на вопрос «насколько тонка зона».
    # У однофазных примеров вариация ровно 0 — условие защищает от
    # деления на ноль, и остаётся корректная плоская линия.
    var = np.abs(np.diff(mu))
    tot = float(var.sum())
    if tot > 0:
        k90 = int(np.searchsorted(np.cumsum(var) / tot, 0.9)) + 1
        k90 = min(k90, len(r) - 1)
        ax.axvline(r[k90], color="k", ls="--", lw=1.2,
                   label=f"90 % вариации: r < {r[k90]:.2f} м ({k90} яч.)")

    ax.set_xlabel("r, м")
    ax.set_ylabel(r"$\mu_o$, Па·с")
    ax.set_title("вязкость в ячейках (последнее состояние)", fontsize=8)
    ax.grid(True, alpha=0.3)
    # На однофазных примерах ни заливки, ни вертикали нет — легенда вышла бы
    # пустой рамкой.
    if ax.get_legend_handles_labels()[0]:
        ax.legend(fontsize=7)


def plot_pvt(config, history, output_dir: Path, title: str,
             simulator=None, grid=None) -> Path:
    """Построить pvt.png: свойства PVT по давлению + вязкость по радиусу.

    config    — SimulatorConfig (Rs0 и подпись модели)
    history   — SimulationHistory; из последнего состояния берётся рабочий
                диапазон давлений и вязкость в ячейках
    simulator — решатель; PVT берётся у него, чтобы график показывал ровно
                то, что видел решатель. Если None, PVT собирается фабрикой
    grid      — сетка для пространственной панели mu_o(r); если None,
                берётся у simulator, а без обоих панель не строится

    Само построение кривых по давлению делегируется ядру
    (gpn_multiphase_solver.io.output.plot_pvt_properties); здесь только
    оформление, пространственная панель, компоновка и сохранение.

    Возвращает путь к сохранённому PNG.
    """
    pvt = _get_pvt(config, simulator)
    Rs0 = float(config.initial_conditions.Rs0)

    # Рабочий диапазон — ФАКТИЧЕСКИЙ, из состояния, а не p_wf/p0 из конфига:
    # забойное давление достигается на грани, и центр первой ячейки всегда
    # выше p_wf.
    p_state = history.states[-1].p
    p_lo, p_hi = float(p_state.min()), float(p_state.max())

    if grid is None and simulator is not None:
        grid = getattr(simulator, "_grid", None)
    n_cols = 4 if grid is not None else 3
    fig, axes = plt.subplots(2, n_cols, figsize=(4.6 * n_cols, 9))

    plot_pvt_properties(pvt, Rs0, (p_lo, p_hi),
                        axes=axes[:, :3],
                        table_nodes=_pvt_table_nodes(pvt, Rs0),
                        label=_describe(config))

    if grid is not None:
        _plot_mu_o_spatial(axes[0, 3], pvt, history, grid, Rs0)
        # Вторая ячейка четвёртого столбца не используется: панель
        # пространственная одна, а плодить графики ради симметрии незачем.
        axes[1, 3].axis("off")

    fig.suptitle(f"{title}\nPVT — {_describe(config)}", fontsize=10)
    fig.tight_layout()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "pvt.png"
    save_figure(fig, out, dpi=120)
    plt.close(fig)
    return out


def report_pvt(config, history, simulator=None) -> dict:
    """Печать характеристик PVT на рабочем диапазоне + словарь величин.

    Сигнатура — по конвенции общих модулей (config первым, simulator
    последним, возврат dict). report_relperm возвращает None и является
    выбросом среди общих модулей — за образец берётся конвенция, а не он.

    Набор ключей ПОЛНЫЙ всегда, независимо от конфига: у однофазных
    сценариев значения вырождены (two_phase=False, nodes_in_range=0), но
    ключи присутствуют — иначе вызывающий код на них падает.
    """
    pvt = _get_pvt(config, simulator)
    Rs0 = float(config.initial_conditions.Rs0)

    p_state = history.states[-1].p
    p_lo, p_hi = float(p_state.min()), float(p_state.max())
    pb = float(pvt.pb(np.array([Rs0]))[0])
    two_phase = Rs0 > 0.0

    nodes = _pvt_table_nodes(pvt, Rs0)
    n_in_range = _nodes_in_range(nodes, p_lo, p_hi)

    # Три опорные точки: края рабочего диапазона и середина.
    p_pts = np.array([p_lo, 0.5 * (p_lo + p_hi), p_hi])
    Rs_pts = _physical_rs(pvt, p_pts, Rs0)
    Bo_pts = pvt.Bo(p_pts, Rs_pts)
    mu_o_pts = pvt.mu_o(p_pts, Rs_pts)
    Bg_pts = pvt.Bg(p_pts)
    mu_g_pts = pvt.mu_g(p_pts)
    # Плотности — вызовами PVT, а не своей формулой (\eqref{eq:rho_oil}).
    rho_o_pts = pvt.rho_o(p_pts, Rs_pts)
    rho_g_pts = pvt.rho_g(p_pts)

    print(f"── PVT: {config.pvt.model} ──")
    print(f"  рабочий диапазон: p = {p_lo / 1e6:.4f} … {p_hi / 1e6:.4f} МПа")
    if two_phase:
        print(f"  Rs0 = {Rs0:.4g} м³ст/м³ст,  p_b = {pb / 1e6:.4f} МПа "
              f"({'в рабочем диапазоне' if p_lo <= pb <= p_hi else 'вне диапазона'})")
    else:
        print(f"  Rs0 = 0 — расчёт однофазный, весь газ растворён;")
        print(f"  p_b = {pb / 1e6:.4f} МПа — вне физической области "
              f"(формула Стендинга при Rs = 0 даёт отрицательное значение),")
        print(f"  ниже показаны B_o и mu_o при Rs ≡ 0.")
    if nodes is not None:
        print(f"  узлов таблицы в рабочем диапазоне: {n_in_range}")
    else:
        print("  PVT аналитический — выделенных узлов нет")

    print(f"  {'p, МПа':>9} {'Rs':>10} {'Bo':>9} {'mu_o, Па·с':>12} "
          f"{'Bg':>10} {'mu_g, Па·с':>12} {'rho_o':>9} {'rho_g':>9}")
    for i in range(len(p_pts)):
        print(f"  {p_pts[i] / 1e6:9.4f} {Rs_pts[i]:10.4f} {Bo_pts[i]:9.5f} "
              f"{mu_o_pts[i]:12.4e} {Bg_pts[i]:10.5f} {mu_g_pts[i]:12.4e} "
              f"{rho_o_pts[i]:9.2f} {rho_g_pts[i]:9.2f}")

    # Все величины — Python float, не np.float64: иначе сравнение в тестах
    # печатает шум.
    return {
        "pb": pb,
        "p_lo": p_lo,
        "p_hi": p_hi,
        "Rs0": Rs0,
        "model": config.pvt.model,
        "two_phase": two_phase,
        "nodes_in_range": n_in_range,
        "mu_o_lo": float(mu_o_pts[0]),
        "mu_o_hi": float(mu_o_pts[-1]),
        "Bo_lo": float(Bo_pts[0]),
        "Bo_hi": float(Bo_pts[-1]),
        "Rs_lo": float(Rs_pts[0]),
        "Rs_hi": float(Rs_pts[-1]),
    }
