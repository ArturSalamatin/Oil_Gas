"""Замер величины лишнего члена T_j·D_j (BUG-012).

Схема собирает конвекцию как разность потоков через грани, то есть
дискретизирует div(Φ·T). Постановка (eq:main_energy_final) записана в
адвективной форме Φ·∂T/∂r. Разность операторов:

    div(Φ·T) − Φ·∇T = T·div(Φ)   →   T_j · D_j,
    D_j = Φ_{j+1/2} − Φ_{j−1/2}   [Вт/К]

Скрипт считает T_j·D_j на каждом шаге и сравнивает с прочими членами
правой части уравнения ячейки: JT (J_jt), адиабатическим (V·Q_ad),
дегазацией (V·Q_deg) и накопительным (cap·ΔT). Все величины в ваттах —
приведены к одной размерности делением/умножением, как в assemble_tridiag.

Почему Φ пересчитывается, а не берётся из пробы: matrix_probe отдаёт
только собранные a,b,c,d, из которых Φ⁺ и Φ⁻ по отдельности не
восстанавливаются (в b_j они уже сложены с cap и кондуктивными членами).
Поэтому Φ считается ТЕМ ЖЕ методом решателя compute_convective_coefficients
на тех же входных данных — не своей копией формулы (иначе это повторило
бы BUG-004: две реализации одной величины расходятся).

Вывод по времени, а не только итог: примеры быстро выходят на стационар,
где все члены малы и отношение теряет смысл. Интересна ранняя стадия.
"""

import sys
from pathlib import Path

import numpy as np

EXAMPLES_DIR = Path(__file__).parent
sys.path.insert(0, str(EXAMPLES_DIR))

# radial_blackoil (прототип коллеги) не установлен в venv — подключается
# через sys.path, как в tests/conftest.py. Нужен примерам с табличным PVT.
_PROTO_ROOT = EXAMPLES_DIR.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROTO_ROOT))

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config


def measure(example: str, n_report: int = 8):
    """Прогнать пример, собрать T·D и прочие члены по шагам.

    Возвращает список словарей: по одной записи на шаг решателя.
    """
    cfg = load_config(EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)

    solver = simulator._energy
    grid = solver._grid
    N = grid.N
    V = grid.volumes

    records = []

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        """Перехват на собранной матрице: все входы шага уже известны."""
        p = hydro_result.state.p
        Sg = hydro_result.state.Sg
        Rs = hydro_result.state.Rs
        So = 1.0 - Sg

        # Те же свойства и Φ, что ушли в матрицу: вызываем методы решателя.
        props = solver.compute_cell_properties(p, Sg, Rs, So, T_old)
        ext = solver._ext_properties(bc)
        Phi_plus, Phi_minus, Phi_o, Phi_g = \
            solver.compute_convective_coefficients(
                hydro_result.Q_o, hydro_result.Q_g,
                props['rho_o'], props['rho_g'],
                props['c_p_o'], props['c_p_g'], N, ext)

        # Полный конвективный коэффициент на грани: Φ = Φ_o + Φ_g [Вт/К].
        # Знак: Q < 0 (поток к скважине) ⇒ Φ < 0 (конвенция знаков проекта).
        Phi = Phi_o + Phi_g

        # D_j = Φ_{j+1/2} − Φ_{j−1/2} — дискретный аналог div(Φ) [Вт/К].
        # Грань j соответствует индексу j (левая), j+1 (правая).
        D = Phi[1:N + 1] - Phi[0:N]

        # Лишний член относительно адвективной формы [Вт].
        extra = T_old * D

        # Прочие члены правой части того же уравнения ячейки [Вт]:
        # p_wf нужен с BUG-012: JT-вклад забойной грани равен
        # μ_JT·Φ⁻·(p[0] − p_wf), давление за забоем — из HydroResult (FEAT-020).
        p_wf = hydro_result.p_wf
        J_jt = solver.compute_jt(
            hydro_result.Q_o, hydro_result.Q_g, Phi_o, Phi_g,
            props['mu_JT_o'], props['mu_JT_g'], p, N, ext, p_wf)
        Q_ad = solver.compute_adiabatic(
            So, Sg, props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'],
            props['mu_JT_o'], props['mu_JT_g'], p, state_prev.p, dt)
        Q_deg = solver.compute_degassing(
            So, Sg, Rs, state_prev.Rs, props['Bo'], hydro_result.G_o,
            props['L'], dt, N, bc.Rs_ext)

        # Накопительный член cap·T = V·(ρcp)_eff/dt · T — масштаб задачи.
        cap = V * props['rho_cp_eff'] / dt

        # Конвективный член целиком (для сравнения: насколько D — поправка
        # к самой конвекции, а не только к источникам).
        conv = Phi_plus[1:N + 1] * T_old + Phi_minus[1:N + 1] * np.r_[T_old[1:], bc.T_ext] \
            - Phi_plus[0:N] * np.r_[T_old[0], T_old[:-1]] - Phi_minus[0:N] * T_old

        # Запас диагонального преобладания: b_j − |a_j| − |c_j|.
        # При D < 0 диагональ ослабляется (побочное следствие BUG-012).
        slack = b - np.abs(a) - np.abs(c)

        records.append(dict(
            t=state_prev.t, dt=dt,
            extra_max=float(np.max(np.abs(extra))),
            jt_max=float(np.max(np.abs(J_jt))),
            ad_max=float(np.max(np.abs(V * Q_ad))),
            deg_max=float(np.max(np.abs(V * Q_deg))),
            conv_max=float(np.max(np.abs(conv))),
            cap_scale=float(np.max(cap)),
            slack_min=float(np.min(slack)),
            dT_max=float(np.max(np.abs(T_old - T_old[-1]))),
        ))

    solver.matrix_probe = probe
    simulator.run(initial)
    solver.matrix_probe = None

    return records


def report(example: str, records: list):
    """Печать: ранние шаги подробно, затем сводка по всему прогону."""
    print(f"\n{'=' * 78}")
    print(f"{example}   шагов: {len(records)}")
    print('=' * 78)

    # Отношение лишнего члена к наибольшему из физических источников.
    def ratio(r):
        base = max(r['jt_max'], r['ad_max'], r['deg_max'])
        return r['extra_max'] / base if base > 0 else np.inf

    print(f"{'t, ч':>8} {'|T·D|, Вт':>12} {'|J_jt|':>12} {'|V·Qad|':>12} "
          f"{'|V·Qdeg|':>12} {'T·D/макс':>10} {'ΔT, К':>8}")
    print('-' * 78)

    n_head = 6
    for r in records[:n_head]:
        print(f"{r['t'] / 3600:8.2f} {r['extra_max']:12.4e} {r['jt_max']:12.4e} "
              f"{r['ad_max']:12.4e} {r['deg_max']:12.4e} "
              f"{ratio(r):10.3f} {r['dT_max']:8.3f}")

    if len(records) > n_head:
        print(f"{'...':>8}")
        r = records[-1]
        print(f"{r['t'] / 3600:8.2f} {r['extra_max']:12.4e} {r['jt_max']:12.4e} "
              f"{r['ad_max']:12.4e} {r['deg_max']:12.4e} "
              f"{ratio(r):10.3f} {r['dT_max']:8.3f}")

    ratios = [ratio(r) for r in records]
    finite = [x for x in ratios if np.isfinite(x)]
    print('-' * 78)
    print(f"  max |T·D| за прогон:        {max(r['extra_max'] for r in records):.4e} Вт")
    print(f"  max |T·D| / макс. источник: {max(finite) if finite else float('nan'):.4f}")
    print(f"  max |T·D| / |конвекция|:    "
          f"{max(r['extra_max'] / r['conv_max'] for r in records if r['conv_max'] > 0):.4f}")
    print(f"  min запас диагонали:        {min(r['slack_min'] for r in records):.4e} Вт/К"
          f"   {'⚠ ОТРИЦАТЕЛЕН' if min(r['slack_min'] for r in records) < 0 else '(> 0, монотонность цела)'}")


if __name__ == "__main__":
    examples = sys.argv[1:] or [
        "07_degassing_adiabatic_only",
        "08_degassing_jt",
        "09_degassing_latent_heat",
        "10_deep_degassing",
        "11_degassing_at_boundary",
    ]
    for ex in examples:
        report(ex, measure(ex))
