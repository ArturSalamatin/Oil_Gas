"""Проверка: можно ли погасить D_j дискретным балансом масс (BUG-012).

ВОПРОС. Адвективная форма уравнения энергии получена подстановкой
уравнений массы в дивергентную. На дискретном уровне подстановка законна
ровно настолько, насколько дискретный аналог div(ρu) выражается через
дискретные балансы масс, которые схема замыкает. Скрипт измеряет, так ли
это, и разделяет вклад двух причин.

ЧТО ИЗМЕРЯЕТСЯ. Раскладываем D_j = Φ_{j+1/2} − Φ_{j−1/2} на две части,
каждая — отдельная причина ненулевого D:

  (1) ДИСБАЛАНС ФАЗОВЫХ РАСХОДОВ. Величина
          dQ_j = Σ_α (ρc_p)_α^fix · (Q_α,{j+1/2} − Q_α,{j−1/2})
      с ЗАМОРОЖЕННЫМ (ρc_p)_α — одним и тем же для всех ячеек. Здесь
      свойства не дрейфуют, поэтому остаётся чистая дивергенция фазовых
      расходов. Она НЕ обязана быть нулём: схема замыкает балансы
      компонентов (G^o, G^g), а не фаз, и объём фазы не сохраняется —
      нефть при разгазировании теряет объём, газ приобретает.

  (2) ДРЕЙФ СВОЙСТВ. Остаток D_j − dQ_j — вклад от того, что
      ρ_α c_p,α меняется от ячейки к ячейке (BUG-012 называет это
      физической причиной масштаба: ρ_o c_p,o ~ 1.4e6 против
      ρ_g c_p,g ~ 5e4).

ЗАЧЕМ. Если доминирует (2), лечится осреднением ρc_p на грань (как
сделано в InjectorGPN — именно это и вывело на BUG-012). Если доминирует
(1), осреднение не поможет: дивергенция фазового расхода останется, и
никакой выбор свойств на грани её не уберёт. От этого зависит, имеет ли
смысл вариант 3 (переписать Φ через компонентные потоки).

Контрольная величина для (1): невязка КОМПОНЕНТНОГО баланса,
    F^o_j = накопление^o_j + G^o_{j+1/2} − G^o_{j−1/2},
которую схема действительно гонит к нулю Ньютоном. Если она машинно мала,
а dQ_j — нет, то это прямое доказательство: фазовая дивергенция не
следует из компонентного баланса.
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

        Phi = Phi_o + Phi_g
        D = Phi[1:] - Phi[:-1]                      # [N], Вт/К

        # (1) Тот же D, но со ЗАМОРОЖЕННЫМИ свойствами: берём значения
        # из первой ячейки и применяем ко всем граням. Дрейф свойств
        # исключён, остаётся дивергенция фазовых расходов.
        rcp_o_fix = float(props['rho_o'][0] * props['c_p_o'][0])
        rcp_g_fix = float(props['rho_g'][0] * props['c_p_g'][0])
        Q_o = hydro_result.Q_o
        Q_g = hydro_result.Q_g
        Phi_fix = rcp_o_fix * Q_o + rcp_g_fix * Q_g
        dQ = Phi_fix[1:] - Phi_fix[:-1]             # [N], Вт/К

        # (2) Остаток — вклад дрейфа свойств
        drift = D - dQ

        records.append(dict(
            t=state_prev.t,
            D_max=float(np.max(np.abs(D))),
            dQ_max=float(np.max(np.abs(dQ))),
            drift_max=float(np.max(np.abs(drift))),
            # Масштаб для сравнения: |Φ| на забойной грани
            Phi_scale=float(np.max(np.abs(Phi))),
        ))

    solver.matrix_probe = probe
    simulator.run(initial)
    solver.matrix_probe = None
    return records


if __name__ == "__main__":
    examples = sys.argv[1:] or ["08_degassing_jt", "10_deep_degassing",
                                "01_single_phase_no_jt"]
    print(f"{'пример':>26} {'max|D|':>11} {'max|dQ|':>11} {'max|дрейф|':>11} "
          f"{'dQ/D':>7} {'дрейф/D':>8}")
    print('-' * 80)
    for ex in examples:
        rec = measure(ex)
        D = max(r['D_max'] for r in rec)
        dQ = max(r['dQ_max'] for r in rec)
        dr = max(r['drift_max'] for r in rec)
        print(f"{ex:>26} {D:11.4e} {dQ:11.4e} {dr:11.4e} "
              f"{dQ / D if D else 0:7.3f} {dr / D if D else 0:8.3f}")
    print("\n  dQ    — дивергенция фазовых расходов при замороженных ρc_p")
    print("  дрейф — вклад изменения ρc_p от ячейки к ячейке")
    print("  Если dQ/D велико — осреднение ρc_p на грань не спасёт:")
    print("  фазовый объём не сохраняется, и это не лечится выбором свойств.")
