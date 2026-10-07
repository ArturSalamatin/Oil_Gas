"""BUG-018: pytest-плагин — код плана (шаг 2) в памяти, для прогона тестов плана до реализации.

Повторяет правки шага 2 плана в blackoil.py без изменения файла:
  - модульная функция _sg_activation_cap(relperm);
  - атрибут модели sg_activation_cap (в __init__);
  - _advance_phases с ограничением S_g активации значением self.sg_activation_cap.
  - текст RuntimeError адаптера (шаг 3) — тот же f-string, подставляется обёрткой solve.

Запуск (из numerical_solver, PowerShell):
    $env:PYTHONPATH = "..\\vault\\issues\\bug-018\\probes"
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\bug-018\\probes\\test_prototype_activation_cap.py -p plan_impl_plugin -v
"""

import numpy as np


def _sg_activation_cap(relperm):
    """BUG-018: largest Sg node of the relperm table where kro > 0; None if kro never reaches 0."""
    sg = np.asarray(getattr(relperm, 'sg', ()), float)
    kro = np.asarray(getattr(relperm, 'kro_tab', ()), float)
    zero = np.flatnonzero(kro <= 0.0)
    if sg.size == 0 or zero.size == 0 or zero[0] == 0:
        return None
    return float(sg[zero[0] - 1])


def pytest_configure(config):
    import patch_cap as pc                      # пути решателя подключает patch_cap
    import radial_blackoil.blackoil as bo
    bo._sg_activation_cap = _sg_activation_cap
    orig_init = bo.RadialBlackOilModel.__init__

    def __init__(self, *a, **kw):
        orig_init(self, *a, **kw)
        self.sg_activation_cap = _sg_activation_cap(self.relperm)

    def _advance_phases(self, *a, **kw):
        # Журнал patch_cap берёт cap из словаря — подставляем текущий атрибут модели,
        # чтобы тесты могли менять self.sg_activation_cap
        st = {"cap": self.sg_activation_cap, "max_guess": 0.0, "hits": 0}
        return pc.patched_advance_phases(st)(self, *a, **kw)

    bo.RadialBlackOilModel.__init__ = __init__
    bo.RadialBlackOilModel._advance_phases = _advance_phases

    # ── Шаг 3: текст ошибки адаптера — тот же f-string, что в плане ──
    from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter
    from gpn_multiphase_solver.units import DAY_TO_S
    orig_solve = PrototypeHydroAdapter.solve

    def solve(self, state, dt, bc):
        try:
            return orig_solve(self, state, dt, bc)
        except RuntimeError as e:
            if not str(e).startswith("HydroSolver не сошёлся"):
                raise
            n_two = int(np.count_nonzero(state.regime == 1))
            raise RuntimeError(
                f"HydroSolver не сошёлся после {2**self._max_retries} подшагов "
                f"(dt_sub={dt / 2**self._max_retries:.2e} s) на шаге с "
                f"t = {state.t / DAY_TO_S:.4f} сут: двухфазных ячеек {n_two} из "
                f"{state.p.size}, max S_g = {float(np.max(state.Sg)):.3f}. "
                f"Если отказ вызван величиной шага, поможет больший "
                f"numerics.max_retries (сейчас {self._max_retries}, допустимо "
                f"до 20); если шаг не сходится и при мелких подшагах, причина "
                f"не в его величине.") from None

    PrototypeHydroAdapter.solve = solve
