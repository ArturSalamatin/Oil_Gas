"""DEBT-040, аудит: регрессия прототипа на коде шага 2 плана без правки файлов.

run_regression.py запускает каждый кейс отдельным процессом (sys.executable,
окружение наследуется). Этот каталог в PYTHONPATH → sitecustomize импортируется
в каждом процессе и после загрузки radial_blackoil.blackoil подменяет
RadialBlackOilModel._fallback блоком «стало» шага 2 (plan_code.fallback_after).
Журнал regression_patch.out.txt (не .log — *.log игнорируется git): процесс, кейс, число вызовов _fallback при BHP и
сколько из них — при условии пропуска ветки «открыта».

    $env:PYTHONPATH = "<пробы>\\regression_hook;<пробы>"
"""

import atexit
import importlib.abc
import importlib.machinery
import os
import sys
import textwrap
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / "regression_patch.out.txt"
STATS = {"bhp_fallback": 0, "hopeless": 0}


def _patch(module):
    import plan_code
    np = module.np
    ns = {"np": np}
    exec(textwrap.dedent(plan_code.fallback_after()), ns)
    fb = ns["_fallback"]

    def logged(self, state_old, dt_s, max_active_iter, max_newton):
        if self.control_mode == 'BHP':
            STATS["bhp_fallback"] += 1
            t = float(self.p_bhp_bar)
            if self.p_outer_bar <= t and float(np.max(state_old.pressure_bar)) <= t:
                STATS["hopeless"] += 1
        return fb(self, state_old, dt_s, max_active_iter, max_newton)

    module.RadialBlackOilModel._fallback = logged

    def report():
        case = next((a for a in sys.argv[1:] if not a.startswith("-")), "?")
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"pid {os.getpid()} {Path(case).name}: подмена есть; _fallback при BHP "
                    f"{STATS['bhp_fallback']}, из них при условии пропуска {STATS['hopeless']}\n")
    atexit.register(report)


class _Hook(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name != "radial_blackoil.blackoil":
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        if spec is None:
            return None
        orig = spec.loader.exec_module

        def exec_module(module):
            orig(module)
            _patch(module)
        spec.loader.exec_module = exec_module
        return spec


sys.meta_path.insert(0, _Hook())
