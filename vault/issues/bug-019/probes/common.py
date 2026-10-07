"""BUG-019: общее для проб — модель примера 20 при k = 10 мД и состояние на 1 сут.

Подключает пакет решателя и прототип через sys.path (вне pytest их подключает
tests/conftest.py). Код прототипа и библиотеки не меняется: все подмены —
на экземпляре модели и снимаются после вызова.
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
FEAT025 = HERE.parents[1] / "feat-025" / "probes"
for _p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3", FEAT025):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
from radial_blackoil.state import BlackOilState  # noqa: E402

FROZEN = HERE / "frozen"
DAY = 86400.0
DT_FAIL = DAY / 512     # 168.75 с: шаг из состояния на 1 сут не сходится
DT_OK = DAY / 256       # 337.5 с: сходится — образец «нормального» поведения
SG_STEP = 0.01          # шаг таблицы Кори для прототипа (factory.py:305, 101 узел)
ETA = np.finfo(float).eps


def make_model():
    """Модель прототипа из замороженного конфига; управление — p_wf интервала 1."""
    cfg = load_config(FROZEN / "config.json")
    sim, _ = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    # Как адаптер перед каждым интервалом (prototype_adapter.py:63-64)
    model.set_bhp_control(cfg.time.history[1].p_wf / BAR_TO_PA)
    return model, cfg


def load_state():
    """Состояние, с которым адаптер начал интервал 1 (t = 1 сут), в единицах прототипа."""
    d = np.load(FROZEN / "state_t1.npz")
    return BlackOilState(pressure_bar=d["p"] / BAR_TO_PA, rs_sm3_sm3=d["Rs"].copy(),
                         sg=d["Sg"].copy(), gas_active=(d["regime"] == 1))


def assert_original_stage(model):
    """Атрибуты исходного алгоритма (blackoil.py:56, :62): не запасной путь и не 3-я ступень."""
    assert model._sg_lower_bound == -0.05 and model._well_branch is None
    assert model._line_search_l2 is False and model._sg_step_max is None


def trace_newton(model, st, dt, z0=None):
    """Ньютон исходного алгоритма с фиксированным набором фаз и журнал итераций.

    Вызывается _newton_fixed_active_set напрямую: через advance после отказа
    пошли бы запасные ступени. Итерации перехватываются подменой
    finite_difference_jacobian на экземпляре (tests/test_prototype_well_branch.py:234-247):
    он вызывается на каждой итерации с текущей точкой z и возвращает (J, f).
    В исходном алгоритме z_{k+1} = z_k + α_k·dz_k (ограничения |ΔS_g| нет),
    поэтому α_k восстанавливается точно.
    """
    assert_original_stage(model)
    mask = st.gas_active.copy()
    if z0 is None:
        z0 = model.pack(st, mask)
    rec = []
    orig = model.finite_difference_jacobian

    def recording(z, state_old, dt_s, gas_active, *a, **kw):
        J, f = orig(z, state_old, dt_s, gas_active, *a, **kw)
        rec.append((np.array(z, float), J, np.array(f, float)))
        return J, f

    model.finite_difference_jacobian = recording
    try:
        z_end, rep = model._newton_fixed_active_set(np.asarray(z0, float).copy(), st, dt, mask)
    finally:
        del model.finite_difference_jacobian      # вернуть метод класса

    its = []
    for k, (z, J, f) in enumerate(rec):
        dz = model._linear_solve(J, -f)          # то же решение, что в Ньютоне
        alpha = fit = None
        if k + 1 < len(rec):
            step = rec[k + 1][0] - z
            alpha = float(step @ dz / (dz @ dz))
            fit = float(np.max(np.abs(step - alpha * dz)) / max(np.max(np.abs(step)), 1e-300))
        its.append(dict(z=z, J=J, f=f, dz=dz, alpha=alpha, fit=fit))
    scale = max(float(np.max(np.abs(its[0]["f"]))), 1e-9)
    tol = 1e-11 + 1e-8 * scale                    # критерий blackoil.py:243
    if rep.converged:
        outcome = "сошёлся"
    elif rep.iterations >= 15:
        outcome = "лимит итераций"
    else:
        outcome = "провал линейного поиска"
    return dict(z_end=z_end, rep=rep, its=its, mask=mask, tol=tol, outcome=outcome)


def noise_rows(model, z, st, dt, mask):
    """Порог округления невязки по строкам: η·(|запас_new| + |запас_old|)/Δt + η·Σ|потоков граней|.

    Газовые строки делятся на gas_residual_scale, как в residual (blackoil.py:178).
    Оценка снизу: ошибки PVT-формул не учтены.
    """
    n = model.grid.n
    new = model.unpack(z, mask)
    oi1, gi1 = model.component_inventories(new)
    oi0, gi0 = model.component_inventories(st)
    fl = model.face_component_fluxes_sm3s(new)
    so = np.zeros(n); sg_ = np.zeros(n)
    so[0] += abs(fl["oil_well"]); sg_[0] += abs(fl["gas_component_well"])
    so[:-1] += np.abs(fl["oil_internal"]); so[1:] += np.abs(fl["oil_internal"])
    sg_[:-1] += np.abs(fl["gas_component_internal"]); sg_[1:] += np.abs(fl["gas_component_internal"])
    so[-1] += abs(fl["oil_outer"]); sg_[-1] += abs(fl["gas_component_outer"])
    oil = ETA * ((np.abs(oi1) + np.abs(oi0)) / dt + so)
    gas = ETA * ((np.abs(gi1) + np.abs(gi0)) / dt + sg_) / model.gas_residual_scale
    return np.concatenate([oil, gas])


def jac_central(model, st, mask, z, dt):
    """Центральная разность с той же раскраской и теми же |h|, что grouped (blackoil.py:204-216)."""
    n = model.grid.n
    J = np.zeros((2 * n, 2 * n))
    for block in (0, 1):
        for color in range(3):
            zp, zm, cols = z.copy(), z.copy(), []
            for i in range(color, n, 3):
                j = i if block == 0 else n + i
                if block == 0:
                    h = abs(model._pressure_fd_step(z[j], bool(mask[i])))
                else:
                    h = 1e-7 if mask[i] else max(1e-5, 1e-6 * max(abs(z[j]), 1.0))
                zp[j] += h; zm[j] -= h; cols.append((i, j, h))
            df = model.residual(zp, st, dt, mask) - model.residual(zm, st, dt, mask)
            for i, j, h in cols:
                rows = np.arange(max(0, i - 1), min(n, i + 2))
                J[rows, j] = df[rows] / (2 * h); J[n + rows, j] = df[n + rows] / (2 * h)
    return J


def c_o_sat(pvt, p_bar, h=1e-3):
    """Сжимаемость насыщенной нефти с выделяющимся газом (B_g·dR_s/dp − dB_o/dp)/B_o, 1/бар."""
    p = np.asarray(p_bar, float)
    drs = (pvt.rs_sat(p + h) - pvt.rs_sat(p - h)) / (2 * h)
    dbo = (pvt.bo(p + h, pvt.rs_sat(p + h)) - pvt.bo(p - h, pvt.rs_sat(p - h))) / (2 * h)
    return (pvt.bg(p) * drs - dbo) / pvt.bo(p, pvt.rs_sat(p))


def c_g(pvt, p_bar, h=1e-3):
    """Сжимаемость свободного газа −(1/B_g)·dB_g/dp, 1/бар."""
    p = np.asarray(p_bar, float)
    return -(pvt.bg(p + h) - pvt.bg(p - h)) / (2 * h) / pvt.bg(p)


def c_t_cells(pvt, p_bar, sg, mask):
    """Полная сжимаемость двухфазных ячеек (1 − S_g)·c_o,sat + S_g·c_g (c_r = 0), 1/бар; NaN — однофазные."""
    sg = np.where(mask, sg, 0.0)
    return np.where(mask, (1 - sg) * c_o_sat(pvt, p_bar) + sg * c_g(pvt, p_bar), np.nan)


def singular_dts(model, st, mask, z, dt1=DT_FAIL, dt2=DT_OK):
    """Δt > 0, при которых J(z, Δt) = A/Δt + B вырожден (без численной бесконечности > 1e12 с)."""
    from scipy.linalg import eig
    J1, _ = model.finite_difference_jacobian(z, st, dt1, mask)
    J2, _ = model.finite_difference_jacobian(z, st, dt2, mask)
    A = (J1 - J2) / (1 / dt1 - 1 / dt2)
    B = J1 - A / dt1
    lam = eig(A, -B, right=False)
    ok = np.isfinite(lam) & (np.abs(lam.imag) <= 1e-6 * np.abs(lam.real)) & (lam.real > 0) & (lam.real < 1e12)
    return np.sort(lam[ok].real)


def where(k, n):
    """Строка невязки → (ячейка, уравнение)."""
    return (k, "нефть") if k < n else (k - n, "газ")
