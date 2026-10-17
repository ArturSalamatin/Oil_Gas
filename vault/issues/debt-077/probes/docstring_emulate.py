"""Эмуляция шага 2 плана DEBT-077 в памяти: «До» найден ровно один раз, модуль после замены компилируется и импортируется.

Запуск из корня репозитория или worktree:
    numerical_solver/.venv/Scripts/python -I vault/issues/debt-077/probes/docstring_emulate.py
Файлы не меняются.
"""

import sys
import types
from pathlib import Path

ROOT = Path.cwd()
BASE = ROOT / "numerical_solver/gpn_multiphase_solver/hydro/base.py"

BEFORE = """\
    Один шаг: (state, dt, bc) → HydroResult.
    Конкретные реализации:
      - PrototypeHydroAdapter (обёртка прототипа коллеги)
      - NewtonHydroSolver (собственный блочный Ньютон, будущее)
"""
AFTER = """\
    Один шаг: (state, dt, bc) → HydroResult.
    Реализация — PrototypeHydroAdapter (обёртка прототипа коллеги);
    собственного решателя нет и не планируется (DEBT-077).
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    text = BASE.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    before, after = BEFORE.replace("\n", nl), AFTER.replace("\n", nl)
    n = text.count(before)
    assert n == 1, f"«До» найден {n} раз"
    new = text.replace(before, after)
    # Компиляция и исполнение как модуля пакета (относительный импорт ..state)
    sys.path.insert(0, str(ROOT / "numerical_solver"))
    import gpn_multiphase_solver.hydro as pkg
    mod = types.ModuleType("gpn_multiphase_solver.hydro.base", None)
    mod.__package__ = "gpn_multiphase_solver.hydro"
    exec(compile(new, str(BASE), "exec"), mod.__dict__)
    doc = mod.HydroSolver.__doc__
    print(f"«До» — 1 вхождение; модуль исполняется; NewtonHydroSolver в докстринге: "
          f"{'есть' if 'NewtonHydroSolver' in doc else 'нет'}; строк в файле: "
          f"{len(text.splitlines())} → {len(new.splitlines())}")
    del pkg


if __name__ == "__main__":
    main()
