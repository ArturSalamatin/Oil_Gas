r"""DEBT-044: таблицы и конфиги проекта проходят проверки допустимости значений.

Запуск из numerical_solver/ (после правки шага 3 плана):
  .venv\Scripts\python ..\vault\issues\debt-044\probes\tables_check.py

1. Каждая из CSV-таблиц проекта: ридер фабрики (пределы столбцов) и проверка
   таблицы целиком (_check_pvto_branches, _check_gas_pvt_table, _check_relperm_table).
2. Каждый config.json проекта с табличным PVT или ОФП: SimulatorFactory.from_config.
Функции берутся из модуля factory в момент вызова: plan_check.py вызывает
check_all() после подмены кода в памяти.
"""
import sys
from pathlib import Path

# Проверяемый код — из текущего каталога (numerical_solver/ основного каталога
# или worktree), а не от расположения пробы
SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/ (основного каталога или worktree), не из {SOLVER}")
sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"))

from gpn_multiphase_solver import factory                         # noqa: E402
from gpn_multiphase_solver.io.config import load_config          # noqa: E402

NAMES = ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv")
SKIP_DIRS = {".venv", "HydroSolverPrototype", ".worktrees", ".pytest_cache"}


def _found(name):
    return sorted(p for p in SOLVER.rglob(name)
                  if not SKIP_DIRS & set(p.relative_to(SOLVER).parts))


def check_table(p):
    """Ридер и проверка таблицы целиком; None или текст отказа."""
    try:
        if p.name == "oil_pvt.csv":
            factory._check_pvto_branches(factory._read_oil_pvt_csv(p), p.name)
        elif p.name == "gas_pvt.csv":
            factory._check_gas_pvt_table(factory._read_gas_pvt_csv(p), p.name)
        else:
            Sg, _, _ = factory._read_relperm_csv(p)
            factory._check_relperm_table(Sg, p.name)
    except ValueError as e:
        return str(e)
    return None


def check_all():
    print(f"Код: {Path(factory.__file__).resolve()}")
    tables = [p for n in NAMES for p in _found(n)]
    counts = {n: sum(p.name == n for p in tables) for n in NAMES}
    bad = [(p, check_table(p)) for p in tables]
    bad = [(p, m) for p, m in bad if m]
    print(f"Таблиц: {len(tables)} {counts}, отвергнуто: {len(bad)}")
    for p, m in bad:
        print(f"  {p.relative_to(SOLVER)}: {m}")

    n_table, n_fail, n_skip = 0, 0, 0
    for cfg in _found("config.json"):
        try:
            config = load_config(cfg)
        except Exception:
            n_skip += 1                       # не конфиг решателя
            continue
        if config.pvt.model != "table" and config.relperm.model != "table":
            continue
        n_table += 1
        try:
            factory.SimulatorFactory.from_config(config)
        except Exception as e:
            n_fail += 1
            print(f"  {cfg.relative_to(SOLVER)}: {type(e).__name__}: {str(e)[:150]}")
    print(f"Конфигов с табличным PVT или ОФП: {n_table}, from_config отказал: {n_fail} "
          f"(не конфиги решателя: {n_skip})")
    return len(bad) + n_fail


if __name__ == "__main__":
    sys.exit(1 if check_all() else 0)
