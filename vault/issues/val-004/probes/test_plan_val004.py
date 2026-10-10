# КОПИЯ кода плана VAL-004, раздел 5.1, для проверки при планировании и аудите.
# Отличия: путь к прототипу в sys.path и CFG — от numerical_solver/ (cwd).
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P.cwd() / "HydroSolverPrototype" / "Prototype_1.0.3"))
_sys.path.insert(0, str(_P.cwd()))

"""VAL-004: сходимость по шагу времени на останове скважины из развитой газовой зоны.

Сценарий — замороженный конфиг tests/data/bug020_rs150 (его же берёт
test_prototype_phase_switching.py): N = 350, Стендинг, R_s0 = 150, 10 сут
добычи при p_wf = 3 МПа (интервал 1 сут — один шаг), затем q_oil = 0.

Первый час останова — 10 нарастающих шагов 3600/2**9, 3600/2**9,
3600/2**8, ..., 1800 с (сумма ровно 3600 с). В прогоне k каждый делится
на 2**k: k = 4, 5, 6 — первый шаг 0.44, 0.22, 0.11 с, наибольший 112.5,
56.25, 28.125 с. Все шаги прогонов k и k+1 отличаются ровно вдвое —
применимы формулы Рунге и Ричардсона.

Почему нарастающие шаги, а не равномерные: T(r_w) помнит первые секунды
останова, и равномерное сгущение выходит на первый порядок по T только
при шаге <= 2 с (минуты счёта). Нарастающие шаги разрешают начало
мелкими шагами, а дальше идут крупными.

Схема — первого порядка по времени: неявная гидродинамика, энергия на
замороженных p^{n+1}, S_g^{n+1} (problem_statement.tex, ssec:time_scheme;
eq:Qad_disc, eq:mdot_disc, eq:energy_disc_full). Локальное дробление шага
(DEBT-015) проверяется отдельно: серия 4 с отказом первой попытки каждого
интервала должна совпасть с серией 5.

План: vault/plans/val-004 shutin-timestep-convergence.md; замеры —
vault/issues/val-004/probes/limits.out.txt.
"""

import copy
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.hydro.base import HydroConvergenceError
from gpn_multiphase_solver.io.config import load_config

# ~80 с: четыре расчёта, 160 + 320 + 640 + 320 шагов останова при N = 350
pytestmark = pytest.mark.slow

CFG = Path.cwd() / "tests" / "data" / "bug020_rs150" / "config.json"
DAY = 86400.0
HOUR = 3600.0
BAR = 1e5
N_PROD = 10          # интервалов добычи в конфиге, по 1 сут
M_FIRST = 9          # первый шаг останова до сгущения — 3600/2**9 = 7.03 с
K_SERIES = (4, 5, 6)

# Предел Δt -> 0 по РАВНОМЕРНОМУ сгущению того же часа (шаг 3.52, 1.76,
# 0.88 с; Ричардсон при q = 1 по двум последним) — независимый путь к тому
# же пределу. Замер планирования (база c0ec060):
# vault/issues/val-004/probes/limits.out.txt. Пересчёт (~6 мин, из
# numerical_solver/): dt_series.py 1 10 12, затем limits.py.
P_LIM = 185.4611262   # бар
T_LIM = 398.0232431   # К

# Порядок: теоретический 1 (неявный Эйлер) +- 0.1; замер 0.994 (p), 0.998 (T).
ORDER_BAND = (0.9, 1.1)
# Совпадение пределов двух серий: замер 2.5e-4 бар и 4.1e-5 К; неопределённость
# пределов — 3.3e-4 бар (нарастающая серия) и 2.3e-4 К (равномерная). Без
# экстраполяции k = 6 отстоит от пределов на 0.040 бар и 1.1e-3 К — больше
# допусков: проверка различает «предел» и «последний прогон».
P_LIM_TOL = 1e-3      # бар
T_LIM_TOL = 5e-4      # К


def _shutin_history(cfg, k):
    """Добыча из конфига + первый час останова нарастающими шагами, каждый поделён на 2**k."""
    hist = cfg.time.history
    assert len(hist) == N_PROD + 1, "сценарий bug020_rs150 изменился"
    prod, shut = hist[:N_PROD], hist[N_PROD]
    base = [HOUR / 2 ** M_FIRST] + [HOUR / 2 ** j for j in range(M_FIRST, 0, -1)]
    assert sum(base) == HOUR   # двоичные дроби: сумма точная
    tail = []
    for H in base:
        for _ in range(2 ** k):
            x = copy.deepcopy(shut)
            x.dt = H / 2 ** k
            tail.append(x)
    return list(prod) + tail


def _run(k):
    """Серия k: состояния на конец добычи и через 1 ч останова, отказы на останове."""
    cfg = load_config(CFG)
    cfg.time.history = _shutin_history(cfg, k)
    # dt_integration = 1 сут длиннее любого интервала останова: каждый
    # интервал — ровно один шаг, если гидродинамика сошлась
    # (TimeSchedule.substeps: n_sub = 1). Добыча — те же суточные шаги.
    assert cfg.time.dt_integration >= HOUR
    sim, s0 = SimulatorFactory.from_config(cfg)

    # Отказ гидродинамики запускает локальное дробление (DEBT-015): шаги
    # перестают быть заданными, и формулы Рунге неприменимы. Обёртка
    # считает отказы на останове (на старте останова шаги 112.5–1800 с не
    # сходятся — план VAL-004, раздел 1.2).
    fails = []
    solve = sim._hydro.solve

    def counting(state, dt, bc):
        try:
            return solve(state, dt, bc)
        except HydroConvergenceError:
            if state.t >= N_PROD * DAY - 1e-6:
                fails.append((state.t, dt))
            raise

    sim._hydro.solve = counting
    hist = sim.run(s0)
    return {
        "prod": hist.states[N_PROD],     # конец добычи, t = 10 сут
        "end": hist.states[-1],          # t = 10 сут + 1 ч
        "t_end": hist.times[-1],
        "n_records": len(hist.times),
        "fails": fails,
    }


def _run_forced_split(k):
    """Серия k с отказом первой попытки каждого интервала останова — шаг делит Simulator."""
    cfg = load_config(CFG)
    cfg.time.history = _shutin_history(cfg, k)
    # Начало и длина каждого интервала останова. Первая попытка интервала —
    # вызов с state.t = начало и dt = длина; подшаги H/2 под условие не
    # попадают (второй начинается не на границе интервала, первый короче).
    t0 = N_PROD * DAY
    starts = {}
    for iv in cfg.time.history[N_PROD:]:
        starts[t0] = iv.dt
        t0 += iv.dt
    sim, s0 = SimulatorFactory.from_config(cfg)
    solve = sim._hydro.solve
    forced = []

    def failing_first(state, dt, bc):
        if starts.get(state.t) == dt:
            forced.append(state.t)
            raise HydroConvergenceError("принудительный отказ первой попытки (VAL-004)")
        return solve(state, dt, bc)

    sim._hydro.solve = failing_first
    hist = sim.run(s0)
    return {"end": hist.states[-1], "n_forced": len(forced), "n_records": len(hist.times)}


@pytest.fixture(scope="module")
def series():
    """Три прогона k = 4, 5, 6 (~56 с)."""
    return {k: _run(k) for k in K_SERIES}


def _order(u4, u5, u6):
    """Порядок по Рунге log2((u5 - u4)/(u6 - u5)); приращения — одного знака."""
    d1, d2 = u5 - u4, u6 - u5
    assert d1 * d2 > 0, f"приращения разного знака: {d1:.3e}, {d2:.3e}"
    return float(np.log2(d1 / d2))


class TestShutinTimestepConvergence:
    """Первый час останова: первый порядок по Δt и предел, не зависящий от расстановки шагов."""

    def test_series_preconditions(self, series):
        """Шаги — ровно заданные (без дробления), добыча во всех прогонах одна и та же.

        Без этого разности прогонов содержат не только ошибку шага по
        времени: дробление меняет цепочку шагов, другая добыча — начальное
        состояние останова. Если после правки решателя (DEBT-048, BUG-024,
        BUG-025, FEAT-032) появились отказы — перемерить серию (план, П4).
        """
        prod0 = series[K_SERIES[0]]["prod"]
        for k, r in series.items():
            assert r["fails"] == [], f"k = {k}: отказы гидродинамики (t, dt): {r['fails'][:5]}"
            # начальная запись + 10 суток добычи + 10·2**k шагов останова
            assert r["n_records"] == 1 + N_PROD + 10 * 2 ** k
            assert r["t_end"] == pytest.approx(N_PROD * DAY + HOUR, abs=1e-6)
            for f in ("p", "Sg", "Rs", "T", "regime"):
                assert np.array_equal(getattr(r["prod"], f), getattr(prod0, f)), (k, f)

    @pytest.mark.parametrize("field, scale", [("p", BAR), ("T", 1.0)])
    def test_wellbore_first_order(self, series, field, scale):
        """p(r_w) и T(r_w) через 1 ч останова сходятся с первым порядком (замер 0.994 и 0.998).

        Ловит член, не исчезающий при Δt -> 0 (ошибка на каждом шаге):
        разности перестают уменьшаться вдвое. Инъекция И2 плана: +1e-6 К на
        шаг -> q_T = 0.74.
        """
        u = [getattr(series[k]["end"], field)[0] / scale for k in K_SERIES]
        q = _order(*u)
        assert ORDER_BAND[0] <= q <= ORDER_BAND[1], (
            f"{field}(r_w): q = {q:.4f}, значения {u}")

    @pytest.mark.parametrize("field", ["p", "T", "Sg"])
    def test_profile_first_order(self, series, field):
        """Профили p, T, S_g: порядок по max-норме разностей (замер 0.994, 0.998, 1.012).

        Сетка во всех прогонах одна — разности без интерполяции. R_s не
        проверяется: у забоя его задаёт первый шаг останова, порядок 0.90
        (предасимптотика, BUG-026).
        """
        a, b, c = (np.asarray(getattr(series[k]["end"], field)) for k in K_SERIES)
        d1 = float(np.max(np.abs(b - a)))
        d2 = float(np.max(np.abs(c - b)))
        q = float(np.log2(d1 / d2))
        assert ORDER_BAND[0] <= q <= ORDER_BAND[1], (
            f"{field}: max|Δ| {d1:.3e} -> {d2:.3e}, q = {q:.4f}")

    @pytest.mark.parametrize("field, scale, ref, tol", [
        ("p", BAR, P_LIM, P_LIM_TOL),
        ("T", 1.0, T_LIM, T_LIM_TOL),
    ])
    def test_limit_matches_uniform_refinement(self, series, field, scale, ref, tol):
        """Предел Ричардсона нарастающей серии = пределу равномерной (замер 2.5e-4 бар, 4.1e-5 К).

        Две разные расстановки шагов ведут к одному пределу Δt -> 0.
        Порядок этого не гарантирует: схема, согласованная с другим
        уравнением, тоже сходится с первым порядком, но к другому пределу
        (инъекция И1 плана: адиабатический член ×1/1.1 — q прежний,
        предел T сдвинут на −0.025 К).
        """
        u5 = getattr(series[5]["end"], field)[0] / scale
        u6 = getattr(series[6]["end"], field)[0] / scale
        lim = 2.0 * u6 - u5          # Ричардсон при q = 1
        assert abs(lim - ref) <= tol, (
            f"{field}(r_w): предел {lim:.7f}, эталон {ref:.7f}, "
            f"разница {lim - ref:+.2e} > {tol:.0e}")

    def test_local_subdivision_equals_finer_series(self, series):
        """Локальное дробление: серия 4 с отказом первой попытки = серия 5 побитово.

        Отказ первой попытки каждого интервала заставляет Simulator._advance
        (DEBT-015) решить интервал двумя подшагами H/2 — гидродинамика и
        энергия на каждом. Серия 5 — те же подшаги отдельными интервалами
        истории. Ловит: энергию не по подшагам гидродинамики (BUG-010),
        неверную длину или время подшага, запись истории на подшаге. Замер
        аудита: 160 отказов, p, S_g, R_s, T, режим — побитово
        (vault/issues/val-004/probes/forced_split.out.txt).
        """
        r = _run_forced_split(4)
        assert r["n_forced"] == 10 * 2 ** 4
        # запись — на конце интервала истории, не подшага
        assert r["n_records"] == 1 + N_PROD + 10 * 2 ** 4
        ref = series[5]["end"]
        for f in ("p", "Sg", "Rs", "T", "regime"):
            a = np.asarray(getattr(r["end"], f), float)
            b = np.asarray(getattr(ref, f), float)
            assert np.array_equal(a, b), f"{f}: max|Δ| = {np.max(np.abs(a - b)):.3e}"
