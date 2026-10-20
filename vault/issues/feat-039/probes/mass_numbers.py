"""FEAT-039 (планирование): таблицы баланса массы README 16, 17, 22 с шестью значащими цифрами.

Аргумент emul – эмуляция FEAT-039 (feat039_emul): интервал 0 – смена управления.

Запуск из numerical_solver/ (P – путь к скрипту): .venv\\Scripts\\python P [emul]
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from start_series import config_path  # noqa: E402

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.mass_balance import compute_mass_balance  # noqa: E402
from gpn_multiphase_solver.energy.balance import compute_energy_balance  # noqa: E402

if sys.argv[1:] == ["emul"]:
    import feat039_emul
    feat039_emul.pytest_configure(None)

for name in ("16_well_shut_in", "17_shut_in_strong_cooling", "22_workbook_input"):
    cfg = load_config(config_path(name))
    cfg.output.log_level = "ERROR"
    sim, s0 = SimulatorFactory.from_config(cfg)
    hist = sim.run(s0)
    mb = compute_mass_balance(hist)
    for a in ("o", "g"):
        print(f"{name} {a}: dM {mb[f'dM_{a}'][-1]:.6g}, добыча {mb[f'prod_{a}'][-1]:.6g}, "
              f"приток {mb[f'inflow_{a}'][-1]:.6g}, отн. невязка финал {mb[f'rel_residual_{a}'][-1]:.4g}, "
              f"max {np.max(mb[f'rel_residual_{a}']):.4g}", flush=True)
    # Таблица невязки баланса энергии examples/README.md: max по записям и член теплопроводности
    eb = compute_energy_balance(hist)
    print(f"{name}: энергия – отн. невязка max {np.nanmax(eb['rel_residual']):.3g}, "
          f"E_конд {eb['cum_cond'][-1]:.4g} Дж", flush=True)
    # test_wellbore_rs_never_decreases (17): наименьшее изменение R_s(r_w) между записями останова
    rs = np.array([s.Rs[0] for s in hist.states])
    print(f"{name}: min ΔR_s(r_w) между записями 16..53 {np.min(np.diff(rs[16:])):.3g}", flush=True)
