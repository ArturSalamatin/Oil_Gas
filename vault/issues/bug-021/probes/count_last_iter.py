"""BUG-021, проба при планировании: где Ньютон сходится на последнем обновлении, а записан отказом.

Код не меняет: оборачивает методы класса RadialBlackOilModel и считает
- вызовы _newton_fixed_active_set: всего, сошедшихся, отказавших;
- события BUG-021: отказ с iterations == max_iter и ||F||_inf последнего приближения
  не выше допуска atol + rtol*max(||F(z0)||_inf, 1e-9) (допуск — как в самом методе);
- вызовы advance: всего, принятых; шаги advance, внутри которых было событие, и исход шага;
- сборки якобиана и время в них. Вариант 2 не строит якобиан, нужный только для
  проверки сходимости: экономия = число сошедшихся вызовов Ньютона.
Обёртки на результат не влияют: residual без побочных эффектов (кеш запасов DEBT-036 —
по байтам состояния), лишний вызов residual(z0) — только у отказов на max_iter.

Запуск — из каталога numerical_solver, код которого считается:
    .venv\\Scripts\\python <P>\\count_last_iter.py regression [кейс ...]   # по умолчанию все 17
    .venv\\Scripts\\python <P>\\count_last_iter.py gpn [пример ...]        # по умолчанию все examples/*/
    .venv\\Scripts\\python <P>\\count_last_iter.py script <скрипт.py> [аргументы ...]   # чужая проба целиком
"""
import logging
import runpy
import sys
import time
from pathlib import Path

import numpy as np

SOLVER_ROOT = Path.cwd()
PROTO = SOLVER_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3"
sys.path.insert(0, str(PROTO))
sys.path.insert(0, str(SOLVER_ROOT))

import radial_blackoil.blackoil as bo  # noqa: E402

if "--variant" in sys.argv:
    # Подменить метод вариантом плана ДО обёрток: считаем уже исправленный код
    _i = sys.argv.index("--variant"); _v = int(sys.argv[_i + 1]); del sys.argv[_i:_i + 2]
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import planned_code  # noqa: E402
    planned_code.apply(_v)
    print(f"код подменён: вариант {_v}", flush=True)

M = bo.RadialBlackOilModel
orig_newton, orig_jac, orig_adv = M._newton_fixed_active_set, M.finite_difference_jacobian, M.advance
S = {}


def reset():
    S.clear()
    S.update(newton=0, conv=0, fail=0, jac=0, jac_time=0.0, adv=0, adv_conv=0, steps=[], ev=None)


def stage(m):
    if m._line_search_l2:
        return "третья"
    return "исходный" if (m._well_branch is None and m._sg_lower_bound == -0.05) else "запасной"


def newton(self, z0, state_old, dt_s, gas_active, max_iter=15, rtol=1e-8, atol_sm3s=1e-11):
    z, rep = orig_newton(self, z0, state_old, dt_s, gas_active, max_iter=max_iter, rtol=rtol, atol_sm3s=atol_sm3s)
    S["newton"] += 1
    if rep.converged:
        S["conv"] += 1
    else:
        S["fail"] += 1
        if rep.iterations == max_iter:
            f0 = self.residual(np.asarray(z0, float), state_old, dt_s, gas_active)
            tol = atol_sm3s + rtol * max(np.linalg.norm(f0, np.inf), 1e-9)
            if rep.residual_inf <= tol and S["ev"] is not None:
                S["ev"].append((stage(self), self._well_branch, rep.residual_inf, tol))
    return z, rep


def jac(self, *a, **k):
    t = time.perf_counter()
    try:
        return orig_jac(self, *a, **k)
    finally:
        S["jac"] += 1
        S["jac_time"] += time.perf_counter() - t


def advance(self, state_old, dt_s, *a, **k):
    S["ev"] = []
    new, rep = orig_adv(self, state_old, dt_s, *a, **k)
    S["adv"] += 1
    S["adv_conv"] += bool(rep.converged)
    if S["ev"]:
        S["steps"].append((S["adv"], dt_s, bool(rep.converged), list(S["ev"])))
    S["ev"] = None
    return new, rep


M._newton_fixed_active_set, M.finite_difference_jacobian, M.advance = newton, jac, advance


def report(name, wall, status):
    steps = S["steps"]
    rej_fixed = sum(1 for s in steps if not s[2])
    print(f"{name}: {status}, {wall:.1f} с | advance {S['adv']} (принято {S['adv_conv']}) | "
          f"Ньютон {S['newton']} (сошлось {S['conv']}, отказ {S['fail']}) | "
          f"якобианов {S['jac']}, {S['jac_time']:.1f} с; сошедшиеся/якобианы = "
          f"{S['conv'] / max(S['jac'], 1):.3f} | шагов с событием BUG-021: {len(steps)} "
          f"(отклонено {rej_fixed}, принято другой ступенью {len(steps) - rej_fixed})", flush=True)
    for i, dt, ok, ev in steps[:20]:
        evs = "; ".join(f"{st}/{br or '—'} |F|={r:.3e} tol={tol:.3e}" for st, br, r, tol in ev)
        print(f"    advance #{i}: dt = {dt:g} с, шаг {'принят' if ok else 'отклонён'}: {evs}", flush=True)
    if len(steps) > 20:
        print(f"    ... ещё {len(steps) - 20}", flush=True)


REG_CASES = {**{c: PROTO / "regression" / "inputs" / f"{c}.xlsx"
                for c in ['T00', 'T01', 'T02', 'T03', 'T04', 'T06', 'T07', 'T08c', 'T09', 'T10', 'T11']},
             **{c: PROTO / "regression" / "inputs" / "T05" / f"{c}.xlsx"
                for c in ['T05S_N050_DT5m', 'T05S_N100_DT5m', 'T05S_N200_DT5m',
                          'T05T_N100_DT60m', 'T05T_N100_DT10m', 'T05T_N100_DT3m']}}


def run_regression(cases):
    """Модель и расписание — как runner.run_workbook (runner.py:106-117), без записи файлов."""
    from radial_blackoil.input_reader import load_input
    from radial_blackoil.grid import RadialGrid
    from radial_blackoil.rock import CompressibleRock
    from radial_blackoil.state import BlackOilState
    from radial_blackoil.simulation import simulate_schedule
    for c in cases:
        inp = load_input(REG_CASES[c]); p = inp.params
        grid = RadialGrid(float(p['Well radius rw']), float(p['Outer radius re']), float(p['Formation thickness h']),
                          int(p['Grid cells N']), float(p['Absolute permeability']))
        rock = CompressibleRock(float(p['Reference porosity']), float(p['Reference pressure']),
                                float(p['Rock compressibility cr']))
        first = inp.schedule.rows[0]
        initial_bhp = first.bhp_bar if first.mode == 'BHP' else (
            first.min_bhp_bar if first.min_bhp_bar is not None else float(p['Outer-boundary pressure']))
        model = M(grid, rock, inp.pvt, inp.relperm, initial_bhp, float(p['Outer-boundary pressure']),
                  float(p['Initial dissolved gas Rs']), skin=float(p['Well skin']),
                  jacobian_mode=str(p['Jacobian mode']), linear_solver=str(p['Linear solver']))
        state0 = BlackOilState.undersaturated(grid.n, float(p['Initial pressure']), float(p['Initial dissolved gas Rs']))
        reset(); t = time.perf_counter()
        try:
            h = simulate_schedule(model, state0, inp.schedule, float(p['DT initial']) * 60.0,
                                  float(p['DT minimum']), float(p['DTMAX']) * 60.0)
            status = f"принято {h.accepted_steps}, отклонено {h.rejected_steps}"
        except Exception as e:  # noqa: BLE001
            status = f"ОТКАЗ: {e}"
        report(c, time.perf_counter() - t, status)


def run_gpn(examples):
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config
    for ex in examples:
        cfg = load_config(SOLVER_ROOT / "examples" / ex / "config.json")
        sim, s0 = SimulatorFactory.from_config(cfg)
        reset(); t = time.perf_counter()
        try:
            h = sim.run(s0)
            status = f"{h.n_saved} записей"
        except Exception as e:  # noqa: BLE001
            status = f"ОТКАЗ: {e}"
        report(ex, time.perf_counter() - t, status)


if __name__ == "__main__":
    print("код:", Path(bo.__file__).parent, flush=True)
    logging.disable(logging.INFO)
    mode, names = sys.argv[1], sys.argv[2:]
    if mode == "script":
        # Счётчики — за весь прогон скрипта; его собственный вывод печатается как есть
        sys.argv = names
        reset(); t = time.perf_counter()
        try:
            runpy.run_path(names[0], run_name="__main__")
            status = "скрипт завершён"
        except BaseException as e:  # noqa: BLE001 — SystemExit/отказы пробы тоже считаем
            status = f"скрипт прерван: {type(e).__name__}: {e}"
        report(Path(names[0]).name, time.perf_counter() - t, status)
    elif mode == "regression":
        run_regression(names or list(REG_CASES))
    elif mode == "gpn":
        run_gpn(names or sorted(d.name for d in (SOLVER_ROOT / "examples").iterdir()
                                if (d / "config.json").is_file()))
    else:
        raise SystemExit("использование: regression [кейс ...] | gpn [пример ...]")
