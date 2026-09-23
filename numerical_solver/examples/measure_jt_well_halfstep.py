"""Забойная грань: полушаг по давлению и поправка на него (BUG-012).

ВОПРОС. На внутренних гранях перепад давления берётся между ЦЕНТРАМИ
соседних ячеек, (p_j - p_{j+1}), и проводимость строится на расстоянии
между центрами: ln(r_{j+1}/r_j) (log_radial.py:72-75). На забойной грани
давление p_wf задано НА САМОЙ ГРАНИ, поэтому перепад (p_0 - p_wf)
охватывает лишь ПОЛОВИНУ пути — от центра ячейки 0 до грани, — и
проводимость строится на ln(r_0/r_well) (log_radial.py:80-83).

Требует ли JT-вклад забойной грани поправки на этот полушаг?

ОТВЕТ: нет, и вот почему. Вывод eq:QJT_integral сводит интеграл по
объёму ячейки к интегралу по ДАВЛЕНИЮ:

    integral_V rho·cp·mu_JT·u·(dp/dr) dV = integral mu_JT·Phi·dp

Правая часть зависит только от ПРЕДЕЛОВ по p, а не от геометрического
расстояния, на котором этот перепад набран. Длина пути в формулу
mu_JT·Phi·(перепад) явно не входит — она уже содержится в Phi через
проводимость грани. Для ячейки 0 нижний предел интегрирования — это
давление на забое, потому что именно до забойной грани простирается
ячейка.

ЧТО ПЕЧАТАЕТ СКРИПТ (проверка этого утверждения на числах):

  1. Геометрия: пути ln(r_0/r_w) и ln(r_1/r_0) различаются вдвое.
  2. Проводимости: trans_well / trans_internal обратно пропорционально
     путям — короткий путь компенсируется большей проводимостью.
  3. Расходы Q_o[0] и Q_o[1] в стационаре РАВНЫ (отношение 1.000000):
     произведение (проводимость х перепад) одинаково на обеих гранях.
  4. JT-вклад забойной грани при этом ВДВОЕ МЕНЬШЕ внутренней, и
     отношение совпадает с отношением путей. Это верно физически:
     дросселирование пропорционально пройденному перепаду давления,
     на полушаге перепад вдвое меньше.

Если бы полушаг требовал поправки, п. 3 не выполнялся бы: расходы
разошлись бы, и стационарный поток не сохранялся бы вдоль радиуса.
"""

import sys
from pathlib import Path

import numpy as np

EXAMPLES_DIR = Path(__file__).parent
sys.path.insert(0, str(EXAMPLES_DIR))

_PROTO = EXAMPLES_DIR.parent / "HydroSolverPrototype" / "Prototype_1.0.3"
if str(_PROTO) not in sys.path:
    sys.path.insert(0, str(_PROTO))

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config


def measure(example: str):
    """Снимок величин забойной и первой внутренней грани на первом шаге."""
    cfg = load_config(EXAMPLES_DIR / example / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)

    solver = simulator._energy
    grid = solver._grid
    N = grid.N
    snap = []

    def probe(a, b, c, d, dt, T_old, hydro_result, state_prev, bc):
        if snap:
            return
        st = hydro_result.state
        p = st.p
        props = solver.compute_cell_properties(
            p, st.Sg, st.Rs, 1.0 - st.Sg, T_old)
        ext = solver._ext_properties(bc)
        _, _, Phi_o, _ = solver.compute_convective_coefficients(
            hydro_result.Q_o, hydro_result.Q_g,
            props['rho_o'], props['rho_g'],
            props['c_p_o'], props['c_p_g'], N, ext)

        # Забойное давление задано НА ГРАНИ
        p_wf = bc.well.boundary_pressure(st, grid, solver._pvt, None)

        snap.append(dict(
            rw=float(grid.r_faces[0]),
            r0=float(grid.r_centers[0]),
            r1=float(grid.r_centers[1]),
            T_well=float(grid.trans_well),
            T_int=float(grid.trans_internal[0]),
            p_wf=float(p_wf), p0=float(p[0]), p1=float(p[1]),
            Q0=float(hydro_result.Q_o[0]), Q1=float(hydro_result.Q_o[1]),
            Phi0=float(Phi_o[0]), Phi1=float(Phi_o[1]),
        ))

    solver.matrix_probe = probe
    simulator.run(initial)
    solver.matrix_probe = None
    return snap[0] if snap else None


def report(example, o):
    path_w = np.log(o['r0'] / o['rw'])
    path_i = np.log(o['r1'] / o['r0'])
    dp_w = o['p0'] - o['p_wf']
    dp_i = o['p1'] - o['p0']
    jt_w = o['Phi0'] * dp_w
    jt_i = o['Phi1'] * dp_i

    print(f"\n{'=' * 72}\n{example}\n{'=' * 72}")
    print("1. Геометрия (логарифмические пути)")
    print(f"   забойная грань  ln(r_0/r_w) = {path_w:.5f}   (полушаг)")
    print(f"   внутренняя      ln(r_1/r_0) = {path_i:.5f}   (полный шаг)")
    print(f"   отношение путей = {path_i / path_w:.3f}")

    print("\n2. Проводимости (обратны путям)")
    print(f"   trans_well     = {o['T_well']:.6e}")
    print(f"   trans_internal = {o['T_int']:.6e}")
    print(f"   отношение = {o['T_well'] / o['T_int']:.3f}")

    print("\n3. Расходы: короткий путь компенсирован проводимостью")
    print(f"   Q_o[0] забой      = {o['Q0']:.6e} м³пл/с")
    print(f"   Q_o[1] внутренняя = {o['Q1']:.6e} м³пл/с")
    print(f"   отношение = {o['Q0'] / o['Q1']:.6f}  "
          f"{'<- РАВНЫ, поток сохраняется' if abs(o['Q0'] / o['Q1'] - 1) < 1e-6 else ''}")

    print("\n4. JT-вклад = Phi * (перепад p)")
    print(f"   перепад на забое      = {dp_w:.4e} Па")
    print(f"   перепад на внутренней = {dp_i:.4e} Па")
    print(f"   Phi*dp забой      = {jt_w:.6e}")
    print(f"   Phi*dp внутренняя = {jt_i:.6e}")
    print(f"   отношение = {jt_w / jt_i:.4f}")
    print(f"   отношение путей ln(r_0/r_w)/ln(r_1/r_0) = {path_w / path_i:.4f}")
    print("\n   Вклад забойной грани меньше ровно во столько раз, во сколько")
    print("   короче путь — дросселирование пропорционально пройденному")
    print("   перепаду давления. Поправки на полушаг не требуется: длина")
    print("   пути уже учтена в Phi через проводимость грани.")


if __name__ == "__main__":
    for ex in sys.argv[1:] or ["02_single_phase_jt", "08_degassing_jt"]:
        o = measure(ex)
        if o is None:
            print(f"{ex}: проба не сработала (управление не по давлению?)")
            continue
        report(ex, o)
