"""График PVT-свойств — штатный рисунок pvt.png (FEAT-030: из examples/pvt_plot.py).

PVT-свойства замыкают систему уравнений фильтрации, но в штатном наборе
графиков (p, S_g, T, дебиты) их не видно. Между тем именно они определяют
профиль давления, дебит и положение фронта разгазирования — сильнее, чем
ОФП.

Приоритет по постановке задачи — вязкость mu_o и газосодержание Rs НЕФТЯНОЙ
фазы: первая входит в подвижность lambda_o = k*k_ro/mu_o, второе — в
замыкание GOR = Rs0.

Модуль — оформитель: само построение кривых делегируется ядру библиотеки
(`gpn_multiphase_solver.io.output.plot_pvt_properties`), которое рисует на
переданных осях и пригодно для своих рисунков пользователя; узлы
таблиц — там же, pvt_table_nodes (DEBT-011). Здесь остаётся всё, что знает
про config: извлечение Rs0, подпись модели, рабочий диапазон из history,
компоновка фигуры, запись PNG и печать сводки.

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

# Режим matplotlib модуль не выбирает: это делает команда расчёта
# (cli.configure_batch_run) или вызывающий скрипт (FEAT-030)
import matplotlib.pyplot as plt
import numpy as np

from ..io.output import plot_pvt_properties, pvt_table_nodes

# PNG + SVG/EMF в output/emf/ (FEAT-026); EMF делает пакетом run_case.
from ..io.figures import save_figure


def _get_pvt(config, simulator):
    """PVT, которым считали задачу; без simulator — сборка фабрикой.

    Fallback нужен, чтобы модуль оставался вызываемым и без прогона
    (так его зовут тесты, у которых в кэше только history/grid/config).
    """
    # PVT у того же решателя, что считал задачу (Simulator.pvt, DEBT-011)
    if simulator is not None:
        return simulator.pvt
    from ..factory import create_pvt
    return create_pvt(config)


def _physical_rs(pvt, p: np.ndarray, Rs0: float) -> np.ndarray:
    """Газосодержание при падающем давлении: min(Rs_eq(p), Rs0).

    p >= p_b — нефть недонасыщена, весь газ растворён, Rs держится на Rs0;
    p <  p_b — нефть насыщена, избыток выделился, Rs = Rs_eq(p).
    После восстановления давления в расчёте бывает и недонасыщенная нефть
    ниже p_b (примеры 12, 13b; DEBT-026) — этой кривой она не описывается.
    Та же формула, что в gpn_multiphase_solver.diagnostics.rs.rs_expected; ядро считает её само,
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


# Построение – ядро io.output.plot_pvt_properties; здесь оформление,
# компоновка и сохранение. Панель mu_o(r) снята (FEAT-028): она про
# решение, а не про модель PVT
def plot_pvt(config, history, output_dir: Path, title: str,
             simulator=None) -> Path:
    """Построить рисунок PVT ``pvt.png``: свойства модели по давлению в виде таблицы PVTO и рабочий диапазон давления расчёта.

    Показаны свойства модели, которой считали: у нефти – насыщенная
    кривая и ветви постоянного газосодержания, у газа – по одной кривой;
    рабочий диапазон давления – по всем ячейкам всех записей расчёта, у
    табличной модели отмечены узлы таблицы. Рисунок сохраняется
    функцией :func:`save_figure`.

    Параметры
    ---------
    config : SimulationConfig
        Конфигурация расчёта: начальное газосодержание и подпись модели PVT.
    history : SimulationHistory
        История расчёта: рабочий диапазон давления.
    output_dir : str or pathlib.Path
        Каталог результатов; создаётся, если его нет.
    title : str
        Заголовок рисунка: первая строка, вторая – описание модели PVT.
    simulator : Simulator, optional
        Решатель расчёта: модель PVT берётся у него, и рисунок показывает
        ровно то, что видел решатель; ``None`` – модель строится заново по
        конфигурации (:func:`create_pvt`).

    Возвращает
    ----------
    pathlib.Path
        Путь записанного ``pvt.png``.
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
                        table_nodes=pvt_table_nodes(pvt, Rs0),
                        label=_describe(config))

    fig.suptitle(f"{title}\nPVT — {_describe(config)}", fontsize=10)
    fig.tight_layout()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "pvt.png"
    save_figure(fig, out, dpi=120)
    plt.close(fig)
    return out


# Сигнатура – по конвенции общих модулей (config первым, simulator
# последним, возврат dict); report_relperm возвращает None – выброс
# среди общих модулей, за образец берётся конвенция, а не он
def report_pvt(config, history, simulator=None) -> dict:
    """Напечатать свойства PVT на рабочем диапазоне давления расчёта и вернуть их.

    Печатаются рабочий диапазон давления по всем записям, начальное
    газосодержание и давление насыщения, число узлов таблицы в диапазоне
    и R_s, B_o, mu_o, B_g, mu_g, rho_o, rho_g на краях диапазона и в его
    середине. Набор ключей результата полный при любой конфигурации: у
    однофазного расчёта значения вырождены, но ключи есть.

    Параметры
    ---------
    config : SimulationConfig
        Конфигурация расчёта: начальное газосодержание и модель PVT.
    history : SimulationHistory
        История расчёта: рабочий диапазон давления.
    simulator : Simulator, optional
        Решатель расчёта – источник модели PVT; ``None`` – модель
        строится заново по конфигурации (:func:`create_pvt`).

    Возвращает
    ----------
    dict
        ``pb``, ``p_lo``, ``p_hi`` – давление насыщения и края рабочего
        диапазона, Па; ``Rs0``; ``model``; ``two_phase``;
        ``nodes_in_range``; ``mu_o_lo``, ``mu_o_hi`` (Па·с), ``Bo_lo``,
        ``Bo_hi``, ``Rs_lo``, ``Rs_hi`` – значения на краях диапазона.
    """
    pvt = _get_pvt(config, simulator)
    Rs0 = float(config.initial_conditions.Rs0)

    p_lo, p_hi = _p_range(history)
    pb = float(pvt.pb(np.array([Rs0]))[0])
    two_phase = Rs0 > 0.0

    nodes = pvt_table_nodes(pvt, Rs0)
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
