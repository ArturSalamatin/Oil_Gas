"""Аналитическая проверка Rs(r) — общая для всех примеров с растворённым газом.

В модели Black Oil газосодержание не имеет собственной динамики: нет ни
уравнения релаксации, ни кинетики выделения. Оно алгебраически следует
за давлением,

    Rs(r) = min( Rs_eq(p(r)), Rs0 ),

где Rs_eq — равновесное газосодержание насыщенной нефти (у примеров 03, 05
это корреляция Стендинга, у 04, 06-10 — интерполяция ветвей PVTO-таблицы).
Смысл двух ветвей минимума:

  p >= pb   нефть недонасыщена, весь газ растворён, Rs держится на Rs0;
  p <  pb   нефть насыщена, избыток газа выделился, Rs = Rs_eq(p) < Rs0.

Проверка НЕ ЗАВИСИТ ОТ ВИДА ОФП и от тепловых параметров: в неё входят
только PVT и поле давления. Поэтому один и тот же код применим ко всем
сценариям с Rs0 > 0 — и с аналитическим PVT, и с табличным.

Что она ловит. Расхождение означало бы одно из двух:
  * схема выделяет газ не мгновенно (появилась паразитная релаксация либо
    рассогласование Rs с p внутри шага Ньютона);
  * PVT в энергетическом блоке отличается от PVT гидродинамики — тогда
    Rs_eq(p), посчитанное здесь, не совпадёт с тем, что применил решатель.

Оба дефекта не видны на профилях p и Sg, поэтому проверка не избыточна.
Ожидаемая точность — уровень машинного нуля (1e-14 и ниже): обе величины
считаются одной и той же функцией от одного и того же p.
"""

from __future__ import annotations

import numpy as np


def rs_expected(config, pvt, p):
    """Равновесное Rs при давлении p: min(Rs_eq(p), Rs0), [N]."""
    return np.minimum(pvt.Rs_eq(p), config.initial_conditions.Rs0)


def rs_error(config, history, pvt):
    """Отклонение численного Rs от равновесного.

    Возвращает (max_abs, max_rel) — абсолютную и относительную ошибки.
    Относительная нормируется на Rs0, а не поячеечно: у фронта Rs -> Rs0,
    а не к нулю, поэтому деление на Rs0 даёт устойчивую меру.
    """
    st = history.states[-1]
    Rs_ana = rs_expected(config, pvt, st.p)
    d = np.abs(Rs_ana - st.Rs)
    Rs0 = config.initial_conditions.Rs0
    return float(d.max()), float(d.max() / Rs0) if Rs0 > 0 else 0.0


def _degassed_cells(config, history, pvt):
    """Маска ячеек, где газ выделился (p < pb), и само pb."""
    Rs0 = config.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    return history.states[-1].p < pb, pb


def front_radius(config, history, grid, pvt):
    """Радиус фронта разгазирования: интерполяция условия p(r_b) = pb.

    Брать центр последней ячейки с p < pb нельзя: фронт лежит ВНУТРИ ячейки,
    и такая оценка систематически занижает r_b. На логарифмической сетке
    ячейки к периферии широкие, и занижение доходит до 9.5 % (пример 04,
    где фронт на 2.6 м). Поэтому интерполируем ln r по p между соседними
    ячейками — профиль логарифмичен, интерполяция именно по ln r.

    np.interp здесь не годится: он требует возрастающий массив узлов, а p
    и ln r монотонны в противоположные стороны, и он молча вернёт мусор.
    """
    p = history.states[-1].p
    r = grid.r_centers
    _below, pb = _degassed_cells(config, history, pvt)

    j = int(np.searchsorted(p, pb))          # p возрастает с ростом r
    if not (0 < j < len(p)):
        return np.nan
    w = (pb - p[j - 1]) / (p[j] - p[j - 1])
    return float(np.exp(np.log(r[j - 1]) + w * (np.log(r[j]) - np.log(r[j - 1]))))


def make_overlay_rs(config):
    """Собрать overlay-функцию для example_runner, замкнув на неё config.

    Хук вызывается как overlay(ax, history, grid, simulator) и своего config
    не получает, а Simulator его не хранит — поэтому конфиг замыкается здесь.
    Так один и тот же код годится для любого примера без обёрток в нём.
    """
    def overlay(ax, history, grid, simulator):
        _draw_rs(ax, history, grid, simulator, config)
    return overlay


def _draw_rs(ax, history, grid, simulator, config):
    """Наложить Rs = min(Rs_eq(p), Rs0) на профиль газосодержания.

    Вызывается после отрисовки численных кривых, поэтому отдельного PNG
    не создаётся — точки ложатся в rs_profiles.png.
    """
    pvt = simulator._energy._pvt

    p = history.states[-1].p
    Rs0 = config.initial_conditions.Rs0
    Rs_ana = rs_expected(config, pvt, p)

    ax.semilogx(grid.r_centers, Rs_ana, 'ko', markersize=4,
                markerfacecolor='none', zorder=5,
                label=r"$R_s = \min(R_s^{eq}(p),\ R_{s,0})$")

    # Линия Rs0 и фронт: правее фронта нефть недонасыщена и Rs строго равно
    # Rs0, левее — идёт разгазирование. Излом кривой лежит ровно на p = pb.
    ax.axhline(Rs0, color='gray', linestyle='-.', linewidth=1.0,
               label=rf"$R_{{s,0}}$ = {Rs0:.0f} м³ст/м³ст")

    r_b = front_radius(config, history, grid, pvt)
    if np.isfinite(r_b):
        ax.axvline(r_b, color='gray', linestyle=':', linewidth=1.5,
                   label=rf"фронт $r_b$ = {r_b:.3f} м")


def report_rs(config, history, pvt) -> dict:
    """Печать проверки Rs в консоль. Возвращает сводку."""
    Rs0 = config.initial_conditions.Rs0
    if Rs0 <= 0.0:
        print("── Rs: сценарий однофазный (Rs0 = 0), проверять нечего ──")
        return dict(max_abs=0.0, max_rel=0.0)

    st = history.states[-1]
    d_abs, d_rel = rs_error(config, history, pvt)
    below, pb = _degassed_cells(config, history, pvt)
    has_gas = st.Sg > 1e-12

    print("── Rs = min(Rs_eq(p), Rs0): равновесие без кинетики ──")
    print(f"  max|Rs_числ - Rs_равн| = {d_abs:.3e} м³ст/м³ст "
          f"({d_rel * 100:.2e} % от Rs0)")
    print(f"  Rs: {st.Rs.min():.4f} … {st.Rs.max():.4f} при Rs0 = {Rs0:.1f}, "
          f"pb = {pb / 1e6:.4f} МПа")

    # Множества «p < pb» и «есть свободный газ» обязаны совпадать: газ
    # выделяется ровно там, где давление упало ниже точки насыщения.
    # Расхождение указывало бы на задержку или гистерезис в схеме.
    same = np.array_equal(np.where(below)[0], np.where(has_gas)[0])
    print(f"  ячеек с p < pb: {int(below.sum())}, с Sg > 0: {int(has_gas.sum())}"
          f" — совпадают: {same}")

    return dict(max_abs=d_abs, max_rel=d_rel, cells_below_pb=int(below.sum()),
                sets_match=same, pb=pb)
