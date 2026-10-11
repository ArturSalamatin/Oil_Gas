"""DEBT-023, аудит: плагин pytest — эмуляция шага 1 плана без правки конфигов.

load_config для examples/{03…09, 04a}/config.json возвращает конфиг с
λ = 1.5 / 0.14 / 0.04, как после шага 1. Остальные конфиги (01, 02, 10–21,
tests/data, configs/) не трогаются. Подмена ставится до импорта тестовых
модулей (-p грузит плагин до сбора), поэтому `from … import load_config`
в тестах и примерах получает обёртку.

Запуск (из numerical_solver):
    $env:PYTHONPATH = "..\\vault\\issues\\debt-023\\probes"
    .venv\\Scripts\\python -m pytest tests/ -q -p lambda_plugin
"""

from pathlib import Path

import gpn_multiphase_solver.io.config as _cfg_mod

TARGET = {"03_standing_corey", "04_table_table", "04a_high_gas_saturation",
          "05_standing_table_rp", "06_table_corey_rp",
          "07_degassing_adiabatic_only", "08_degassing_jt",
          "09_degassing_latent_heat"}
LAM = (1.5, 0.14, 0.04)
HITS = set()

_orig = _cfg_mod.load_config


def _patched(path, *args, **kwargs):
    cfg = _orig(path, *args, **kwargs)
    p = Path(path)
    if p.parent.name in TARGET and p.parent.parent.name == "examples":
        cfg.rock.lambda_solid, cfg.rock.lambda_oil, cfg.rock.lambda_gas = LAM
        HITS.add(p.parent.name)
    return cfg


_cfg_mod.load_config = _patched


def pytest_terminal_summary(terminalreporter):
    terminalreporter.write_line(
        f"[lambda_plugin] подмена λ сработала для {len(HITS)} примеров: {sorted(HITS)}")
