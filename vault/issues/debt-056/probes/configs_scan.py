r"""DEBT-056: конфиги проекта против проверок скина и забойного давления.

Запуск из numerical_solver/ (основного каталога или worktree):
    .venv\Scripts\python ..\vault\issues\debt-056\probes\configs_scan.py
Каждый JSON с секциями time и initial_conditions (кроме скрытых каталогов
и HydroSolverPrototype):
1) сырые значения — skin ≠ 0; p_wf (control = pressure) или min_bhp
   (control = rate) ≥ p0 в объектах time.history;
2) load_config — отказ или записи журнала уровня WARNING и выше.
Печатаются только конфиги с замечаниями; итог — число конфигов и замечаний.
До DEBT-056 и после него ожидается одно и то же: замечаний нет.
"""
import json
import logging
import sys
from pathlib import Path

# Проверяемый код — из текущего каталога (numerical_solver/ основного каталога
# или worktree), а не от расположения пробы
SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
sys.path.insert(0, str(SOLVER))

from gpn_multiphase_solver.io import config as config_module  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402


class _Collect(logging.Handler):
    """Собирает тексты записей журнала уровня WARNING и выше."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _raw_notes(raw: dict) -> list[str]:
    """Замечания по сырым значениям JSON: skin ≠ 0, p_wf / min_bhp ≥ p0."""
    notes = []
    p0 = raw["initial_conditions"].get("p0")
    skin = raw.get("numerics", {}).get("skin", 0.0)
    if skin != 0:
        notes.append(f"skin = {skin}")
    for i, entry in enumerate(raw["time"].get("history", [])):
        control = entry.get("control", "pressure")
        level = entry.get("p_wf") if control == "pressure" else entry.get("min_bhp")
        if level is not None and p0 is not None and level >= p0:
            notes.append(f"history[{i}]: {control}, {level} ≥ p0 = {p0}, "
                         f"q_oil = {entry.get('q_oil')}")
    return notes


def main() -> None:
    print(f"код: {Path(config_module.__file__).resolve()}")
    handler = _Collect()
    logging.getLogger("gpn_multiphase_solver").addHandler(handler)
    n_configs = n_flagged = 0
    for path in sorted(SOLVER.rglob("*.json")):
        rel = path.relative_to(SOLVER)
        if any(part.startswith(".") for part in rel.parts) or rel.parts[0] == "HydroSolverPrototype":
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(raw, dict) or "time" not in raw or "initial_conditions" not in raw:
            continue
        n_configs += 1
        notes = _raw_notes(raw)
        handler.messages.clear()
        try:
            load_config(path)
        except ValueError as e:
            notes.append(f"load_config: ValueError: {str(e)[:200]}")
        notes += [f"WARNING: {m[:200]}" for m in handler.messages]
        if notes:
            n_flagged += 1
            print(f"{rel}:")
            for note in notes:
                print(f"    {note}")
    print(f"конфигов: {n_configs}, с замечаниями: {n_flagged}")


if __name__ == "__main__":
    main()
