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

Что на графике (сетка 2x3) — как таблица PVTO коммерческих симуляторов
(FEAT-028):

  mu_o(p), Rs(p), Bo(p), rho_o(p) — свойства нефти:
      насыщенная  Rs = Rs_eq(p)                    — красная, вся ось
      ветви       Rs = Rs_i = const, p >= p_b(Rs_i) — тонкие серые,
                  начинаются на насыщенной кривой и идут вправо
      ветвь Rs0   Rs = Rs0                          — жирная зелёная
    Ветви — строки таблицы PVTO у табличного PVT и «круглые» Rs_i
    (шаг 10, 20, 25, 50…, не больше 7 строк на оси) у Стендинга.
    У табличного PVT насыщенная кривая вне [p_b(Rs_min), p_b(Rs_max)] —
    пунктир: прототип там зажимает Rs_eq, это экстраполяция, а не
    данные таблицы. mu_o — в логарифмической шкале: у примера 14
    веер занимает полторы декады.
  mu_g(p), Bg(p) — по одной кривой (газ сухой); у табличного PVT Bg
                   кусочно-линейна, у Стендинга — гипербола p_ст*T0/(T_ст*p);
  плотности      — rho_o (веер) и rho_g на двух осях (twinx): нефть
                   730…800, газ 40…140 кг/м³, на одной оси газовая нечитаема.

У моделей Стендинга при co_undersaturated = 0 (так во всех конфигах
примеров, кроме 20) Bo и mu_o зависят от давления только через Rs: при
фиксированном Rs они от p не зависят. Недонасыщенная ветвь выходит строго
горизонтальной; это свойство модели, а не дефект, и подпись панели об этом
сообщает. При co_undersaturated > 0 Bo выше p_b убывает; mu_o растёт с p
только при pvt.mu_o_undersaturated = "beal" (FEAT-027), иначе горизонтальна.

Однофазные сценарии (Rs0 = 0) рисуются так же: рисунок описывает модель
PVT, а не расчёт. Ветвь Rs0 = 0 — горизонталь через всю ось (у Стендинга
p_b(0) = -0.176 МПа, вне физической области), вертикаль p_b не
наносится; насыщенная кривая растягивает ось Rs до ~140 м³ст/м³ст.

Отличие от существующего rs_profiles.png. Оба графика про Rs, но по разным
осям и про разное:

  rs_profiles.png — Rs по РАДИУСУ: где в пласте газ вышел из раствора,
                    где фронт r_b. Это про РЕШЕНИЕ задачи.
  панель Rs здесь — Rs по ДАВЛЕНИЮ: как Rs зависит от p, где p_b,
                    насколько груба таблица. Это про МОДЕЛЬ, которой
                    задачу решали.

Дублирования нет.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from gpn_multiphase_solver.io.output import plot_pvt_properties  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from gpn_multiphase_solver.pvt.table_full import TableFullPVT  # noqa: E402

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
    from gpn_multiphase_solver.factory import create_pvt
    return create_pvt(config)


def _physical_rs(pvt, p: np.ndarray, Rs0: float) -> np.ndarray:
    """Газосодержание при падающем давлении: min(Rs_eq(p), Rs0).

    p >= p_b — нефть недонасыщена, весь газ растворён, Rs держится на Rs0;
    p <  p_b — нефть насыщена, избыток выделился, Rs = Rs_eq(p).
    После восстановления давления в расчёте бывает и недонасыщенная нефть
    ниже p_b (примеры 12, 13b; DEBT-026) — этой кривой она не описывается.
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
        # Иначе горизонтальная недонасыщенная ветвь читается как ошибка.
        # От p свойства зависят только через Rs: на насыщенной ветви
        # Rs = Rs_eq(p) и кривые идут, на недонасыщенной Rs = Rs0 — горизонталь.
        # Подпись короткая: она же — заголовок панели шириной 4.6 дюйма (шрифт 8).
        beal = pc.mu_o_undersaturated == "beal"
        if beal:
            s += r", $\mu_o$ выше $p_b$ — Бил"
        # Выше p_b при фиксированном Rs горизонтальны: B_o при c_o = 0,
        # μ_o без ветви Била (FEAT-027). Иначе горизонталь читается как ошибка.
        flat = [name for name, is_flat in (("$B_o$", pc.co_undersaturated == 0.0),
                                           (r"$\mu_o$", not beal)) if is_flat]
        if flat:
            s += f" ({', '.join(flat)} от $p$ — только через $R_s$)"
        return s
    if pc.model == "table":
        return (f"таблицы {pc.oil_pvt_file}, {pc.gas_pvt_file} "
                f"(линейная интерполяция)")
    return f"модель: {pc.model}"


def _pvt_table_nodes(pvt, Rs0: float):
    """Узлы табличного PVT в Па, раздельно по фазам, иначе None.

    Цепочка обёрток: TableFullPVT.hydro -> PrototypePVTAdapter.proto_pvt ->
    BlackOilPVT прототипа, где всё лежит в БАРАХ (поля gp, pb, branches).
    У аналитического PVT (Standing) выделенных точек нет — возвращаем None,
    маркеры на гладкой корреляции вводили бы в заблуждение.

    Ключи раздельные, потому что наборы разные по природе и идут на разные
    панели: газовая таблица — на mu_g/Bg, строки PVTO и узлы строки Rs0 —
    на mu_o/Bo/Rs.

    Ординаты узлов здесь НЕ возвращаются: недонасыщенная ветка
    интерполируется по dp = p - pb(Rs), а не по p, поэтому значения
    считаются вызовом PVT в точке узла (это делает ядро).
    """
    # Табличный ли PVT — по классу, BlackOilPVT — через публичные свойства
    # (DEBT-006). Прежде getattr по приватным _hydro, _pvt: их переименование
    # молча убирало бы маркеры узлов с графика.
    if not isinstance(pvt, TableFullPVT):
        return None
    proto = pvt.hydro.proto_pvt

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
        # Для сводки report_pvt (_nodes_in_range); ядро этот ключ не читает.
        "p_oil": np.unique(np.concatenate([p_sat, p_branch])),
        "rs_values": rs_values,
        # Узлы строки Rs0 — на жирной ветви рисунка. Если Rs0 не совпадает
        # со строкой, ветвь интерполирована между строками и собственных
        # узлов не имеет.
        "p_branch": p_branch if np.isclose(rs_near, Rs0) else np.empty(0),
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


def _p_range(history) -> tuple[float, float]:
    """Рабочий диапазон давления, Па: min и max по всем ячейкам всех записей истории."""
    # По ВСЕЙ истории, а не по последней записи: после останова скважины
    # (пример 16) давление выравнивается до p_ext, и последняя запись
    # вырождает диапазон в точку, хотя расчёт прошёл 6.1…15.5 МПа (FEAT-019).
    p = np.concatenate([s.p for s in history.states])
    return float(p.min()), float(p.max())


def plot_pvt(config, history, output_dir: Path, title: str,
             simulator=None) -> Path:
    """Построить pvt.png: свойства PVT по давлению в стиле таблицы PVTO.

    config    — SimulatorConfig (Rs0 и подпись модели)
    history   — SimulationHistory; из последнего состояния берётся рабочий
                диапазон давлений
    simulator — решатель; PVT берётся у него, чтобы график показывал ровно
                то, что видел решатель. Если None, PVT собирается фабрикой

    Само построение делегируется ядру
    (gpn_multiphase_solver.io.output.plot_pvt_properties); здесь только
    оформление, компоновка и сохранение. Панель mu_o(r) снята (FEAT-028):
    она про решение, а не про модель PVT.

    Возвращает путь к сохранённому PNG.
    """
    pvt = _get_pvt(config, simulator)
    Rs0 = float(config.initial_conditions.Rs0)

    # Рабочий диапазон — ФАКТИЧЕСКИЙ, из состояний, а не p_wf/p0 из конфига:
    # забойное давление достигается на грани, и центр первой ячейки всегда
    # выше p_wf. Охват — вся история (_p_range).
    p_lo, p_hi = _p_range(history)

    # Ширина панели прежняя — 4.6 дюйма: на неё рассчитана подпись _describe.
    fig, axes = plt.subplots(2, 3, figsize=(4.6 * 3, 9))
    plot_pvt_properties(pvt, Rs0, (p_lo, p_hi), axes=axes,
                        table_nodes=_pvt_table_nodes(pvt, Rs0),
                        label=_describe(config))

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

    p_lo, p_hi = _p_range(history)
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
