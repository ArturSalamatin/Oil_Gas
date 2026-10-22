"""Проба плана DEBT-085: перехват рисунков балансов подменой save_figure и их подписи до правки.

Запуск из корня репозитория:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-085\\probes\\plan_capture_titles.py
"""

import io
import contextlib
import os
import sys
import tempfile
from pathlib import Path

SOLVER = Path.cwd() / "numerical_solver"
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))
os.environ["GPN_EXAMPLES_EMF"] = "0"

import matplotlib  # noqa: E402
matplotlib.use("Agg")

import gpn_multiphase_solver  # noqa: E402
from gpn_multiphase_solver.energy.balance import CUMULATIVE_KEYS  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.io.figures import save_figure  # noqa: E402
from gpn_multiphase_solver.report import energy_balance, mass_balance  # noqa: E402
from gpn_multiphase_solver.state import SimulationHistory  # noqa: E402

print("Пакет:", gpn_multiphase_solver.__file__)

figures = {}


def keep(fig, path, dpi):
    """Запомнить рисунок по имени файла, затем записать как обычно."""
    figures[Path(path).name] = fig
    return save_figure(fig, path, dpi)


energy_balance.save_figure = keep
mass_balance.save_figure = keep

# История из двух записей – как _energy_history и test_compute_mass_balance_closes
zero = dict.fromkeys(CUMULATIVE_KEYS, 0.0)
last = dict(delta_E=5.0, cum_adiab=1.0, cum_conv=2.0, cum_jt=-1.0, cum_deg=0.5, cum_cond=2.0)
snaps = [dict(M_o=100.0, M_g=0.0, cum_o_well=0.0, cum_o_ext=0.0, cum_g_well=0.0, cum_g_ext=0.0),
         dict(M_o=90.0, M_g=0.0, cum_o_well=-12.0, cum_o_ext=-2.0, cum_g_well=0.0, cum_g_ext=0.0)]
history = SimulationHistory(times=[0.0, 10.0], balance=[zero, last], mass_balance=snaps)

# Конфигурация примера 02: output.title задан, каталог – 02_single_phase_jt
cfg = load_config(SOLVER / "examples" / "02_single_phase_jt" / "config.json")
print("output.title:", cfg.output.title)
with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
    energy_balance.plot_energy_balance(history, None, cfg, Path(tmp))
    mass_balance.plot_mass_balance(cfg, history, Path(tmp))

print("energy_balance.png:", repr(figures["energy_balance.png"].axes[0].get_title()))
print("mass_balance.png:  ", repr(figures["mass_balance.png"]._suptitle.get_text()))
