"""DEBT-076: нулевая и отрицательная плотность при ст. у. на пути Стендинга — отказ фабрики без имени поля.

Запуск из numerical_solver/:
    set PYTHONIOENCODING=utf-8
    .venv\\Scripts\\python ..\\vault\\issues\\debt-076\\probes\\density_sign_standing.py

Конфиг примера 03 (pvt.model = "standing"). Значение pvt.rho_o_std /
pvt.rho_g_std подменяется в словаре после json.load — файлы не создаются.
Печать: где и с каким сообщением отказ (load_config или from_config).
Плотности входят в корреляции Стендинга: γ_API = 141.5/(ρ_o,ст/ρ_w) − 131.5,
γ_g = ρ_g,ст/ρ_воздуха (pvt/standing.py, _api_gravity, _gas_specific_gravity).
"""
import json
import logging
import warnings
from pathlib import Path

SOLVER = Path.cwd()
print(f"каталог решателя: {SOLVER}")

logging.disable(logging.CRITICAL)
warnings.simplefilter("ignore")
import gpn_multiphase_solver.io.config as c  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402

CONFIG = SOLVER / "examples" / "03_standing_corey" / "config.json"
CASES = (("rho_o_std", -850.0), ("rho_o_std", 0.0),
         ("rho_g_std", -0.85), ("rho_g_std", 0.0))

orig = json.load
try:
    for key, val in CASES:
        def patched(fp, key=key, val=val):
            d = orig(fp)
            d["pvt"][key] = val
            return d
        c.json.load = patched
        stage = "load_config"
        try:
            cfg = c.load_config(CONFIG)        # отказа нет: знак плотности не проверяется
            stage = "from_config"
            SimulatorFactory.from_config(cfg)
            print(f"pvt.{key} = {val}: load_config и from_config без отказа")
        except Exception as e:
            print(f"pvt.{key} = {val}: отказ в {stage}: {type(e).__name__}: {e}")
finally:
    c.json.load = orig
