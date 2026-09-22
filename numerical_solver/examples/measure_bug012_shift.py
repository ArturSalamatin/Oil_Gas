"""Оценка сдвига температуры от дефекта формы (BUG-012).

Вопрос, на который отвечает скрипт: насколько изменится T после
исправления? Прямой ответ дал бы прогон исправленного кода, но до правки
нужна оценка — она задаёт критерий приёмки («сдвиг ожидается ~X К»).

Оценка снизу. Лишний член T_j·D_j [Вт] в уравнении ячейки конкурирует
с накопительным cap_j = V_j(ρcp)_eff/Δt [Вт/К]. Если бы он был
единственным нескомпенсированным вкладом, то за один шаг он сдвигал бы
температуру ячейки на

    δT_j = T_j·D_j / cap_j     [К]

Это оценка за ОДИН шаг. На стационаре сдвиг уравновешивается конвекцией
и кондукцией, поэтому итоговый сдвиг решения меньше δT за шаг, но того же
масштаба, если член систематичен (а он систематичен: D_j не меняет знак,
пока направление потока и профиль ρcp не меняются).

Вторая оценка — стационарная. На установившемся режиме накопление равно
нулю, и лишний член уравновешивается конвекцией:

    δT_стац ≈ T_j·D_j / |Φ_j|

то есть перепад температуры, который конвекция должна создать, чтобы
скомпенсировать паразитный вклад.

Обе величины — оценки порядка, а не предсказание. Точный сдвиг даст
сравнение прогонов до и после правки.
"""

import sys
from pathlib import Path

import numpy as np

EXAMPLES_DIR = Path(__file__).parent
sys.path.insert(0, str(EXAMPLES_DIR))

_PROTO_ROOT = EXAMPLES_DIR.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROTO_ROOT))

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config


def measure(example: str):
    cfg = load_config(EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)

    solver = simulator._energy
    grid = solver._grid
    N = grid.N
    V = grid.volumes

    records = []

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        p = hydro_result.state.p
        Sg = hydro_result.state.Sg
        Rs = hydro_result.state.Rs
        So = 1.0 - Sg

        props = solver.compute_cell_properties(p, Sg, Rs, So, T_old)
        ext = solver._ext_properties(bc)
        _, _, Phi_o, Phi_g = solver.compute_convective_coefficients(
            hydro_result.Q_o, hydro_result.Q_g,
            props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'], N, ext)

        Phi = Phi_o + Phi_g                  # [N+1], Вт/К
        D = Phi[1:N + 1] - Phi[0:N]          # [N], дискретный div(Φ)
        extra = T_old * D                     # [N], Вт — лишний член

        cap = V * props['rho_cp_eff'] / dt    # [N], Вт/К

        # Сдвиг за один шаг, если член ничем не скомпенсирован
        dT_step = np.abs(extra) / cap

        # Стационарная оценка: паразитный член / масштаб конвекции.
        # Берём |Φ| на грани, ближней к скважине (там конвекция сильнейшая).
        Phi_scale = np.maximum(np.abs(Phi[0:N]), np.abs(Phi[1:N + 1]))
        with np.errstate(divide='ignore', invalid='ignore'):
            dT_stat = np.where(Phi_scale > 0, np.abs(extra) / Phi_scale, 0.0)

        # Номера ячеек обязательны: максимум |extra| в ваттах и максимум
        # сдвига температуры достигаются в РАЗНЫХ ячейках. |extra| велик
        # у контура (большой объём ячейки на логарифмической сетке), а
        # сдвиг T — у забоя, где объём наименьший и cap мал. Без номера
        # ячейки величина в ваттах вводит в заблуждение.
        records.append(dict(
            t=state_prev.t, dt=dt,
            dT_step_max=float(np.max(dT_step)),
            dT_step_cell=int(np.argmax(dT_step)),
            dT_stat_max=float(np.max(dT_stat)),
            dT_stat_cell=int(np.argmax(dT_stat)),
            extra_max=float(np.max(np.abs(extra))),
            extra_cell=int(np.argmax(np.abs(extra))),
            # Профиль T для справки: сдвиг надо сравнивать с самим ΔT_w
            dTw=float(T_old[0] - T_old[-1]),
        ))

    solver.matrix_probe = probe
    simulator.run(initial)
    solver.matrix_probe = None
    return records


if __name__ == "__main__":
    examples = sys.argv[1:] or ["07_degassing_adiabatic_only", "08_degassing_jt",
                                "10_deep_degassing", "11_degassing_at_boundary"]
    print(f"{'пример':>30} {'max δT шаг, К':>14} {'ячейка':>7} "
          f"{'max δT стац, К':>15} {'ячейка':>7} {'ΔT_w итог, К':>13}")
    print('-' * 92)
    for ex in examples:
        rec = measure(ex)
        step = max(rec, key=lambda r: r['dT_step_max'])
        stat = max(rec, key=lambda r: r['dT_stat_max'])
        print(f"{ex:>30} {step['dT_step_max']:14.4f} {step['dT_step_cell']:7d} "
              f"{stat['dT_stat_max']:15.4f} {stat['dT_stat_cell']:7d} "
              f"{rec[-1]['dTw']:13.4f}")
    print("\n  δT шаг  — сдвиг T за один шаг, если член ничем не скомпенсирован")
    print("  δT стац — паразитный член / масштаб конвекции (перепад T,")
    print("            который конвекция должна создать для компенсации)")
    print("  Обе величины — оценки ПОРЯДКА сверху. Точный сдвиг даёт")
    print("  сравнение прогонов до и после правки.")
