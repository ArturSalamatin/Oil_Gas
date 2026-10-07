"""DEBT-030, проба при планировании: тест прототипа из плана — до правки падает, после проходит.

Сценарий теста: tests.helpers.model_and_state(n=100, bhp=100, p0=200, case=<вход>),
первый шаг dt = 60 с. Проверяется, отказывают ли на нём все три ступени advance
(фикстура Nabor_1b и вход регрессии T04) и совпадает ли отчёт отказа по плану с
отчётом исходного алгоритма. advance по плану подставляется в экземпляр модели.

Запуск из numerical_solver/HydroSolverPrototype/Prototype_1.0.3:
    ..\\..\\.venv\\Scripts\\python <путь>\\planned_tests_check.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

import radial_blackoil.blackoil as bo                      # noqa: E402
from tests.helpers import model_and_state                   # noqa: E402
from trace_stages import advance_planned, fmt               # noqa: E402

print(f"код: {Path(bo.__file__).parent}")

# Фикстура Nabor_1b на n = 12, 50, 100 первый шаг 60 с решает исходным алгоритмом
# (первый прогон пробы) — нужен вход T04: те же параметры, другие таблицы ОФП.
# Абсолютный путь в case: ROOT/'tests'/'fixtures'/<абсолютный> == <абсолютный> (pathlib).
T04 = Path.cwd() / "regression" / "inputs" / "T04.xlsx"
for case, n in (("Nabor_1b.xlsx", 100), (T04, 100)):
    t0 = time.perf_counter()
    _, ref, s0 = model_and_state(n=n, bhp=100.0, p0=200.0, case=case)
    _, orig = ref._advance_phases(s0, 60.0)
    t_orig = time.perf_counter() - t0
    _, now_m, _ = model_and_state(n=n, bhp=100.0, p0=200.0, case=case)
    t1 = time.perf_counter()
    _, now = now_m.advance(s0, 60.0)
    t_adv = time.perf_counter() - t1
    _, plan_m, _ = model_and_state(n=n, bhp=100.0, p0=200.0, case=case)
    _, plan = advance_planned.__get__(plan_m)(s0, 60.0)
    same = (plan.iterations, plan.active_set_iterations, plan.phase_switches, plan.residual_inf) == \
           (orig.iterations, orig.active_set_iterations, orig.phase_switches, orig.residual_inf)
    print(f"{Path(case).name}, n = {n} (исходный {t_orig:.1f} с, advance {t_adv:.1f} с)")
    print(f"   исходный        : {fmt(orig)}")
    print(f"   advance сейчас  : {fmt(now)} fb={now.fallback} gl={now.globalized}")
    print(f"   advance по плану: {fmt(plan)} fb={plan.fallback} gl={plan.globalized}  "
          f"поля Ньютона == исходный: {same}")
