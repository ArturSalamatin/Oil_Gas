"""Аудит FEAT-023, раунд 2: буквальный код тестов и main.py из плана — через pytest.

Из файла плана извлекаются блоки кода: тест флага (шаг 3.1), класс Q
(шаг 5), main.py (шаг 4.2). Собирается изолированный каталог r2/:
  r2/examples/example_runner.py      — копия с флагом (из flag/, audit_flag.py)
  r2/examples/05_standing_table_rp/  — копия примера 05 (тест флага)
  r2/examples/13b_pwf_alternating/   — config и CSV из cfg_13b/, main.py из плана
  r2/test_r2.py                      — шапка как в tests/test_examples.py
                                       (EXAMPLES_DIR, _pvt_of_config, results
                                       только для 13b) + буквальный код плана
Реальные examples/ добавлены в sys.path ПОСЛЕ r2/examples — для общих модулей
(closed_form, rs_analytics, ...), которые копия example_runner импортирует.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-023\\probes\\audit_r2_literal.py
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\feat-023\\probes\\r2\\test_r2.py -q -p no:cacheprovider
"""

import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOLVER = ROOT / "numerical_solver"
EX = SOLVER / "examples"
PLAN = ROOT / "vault" / "plans" / "feat-023 alternating-bhp-example.md"

plan = PLAN.read_text(encoding="utf-8")
blocks = re.findall(r"```python\n(.*?)```", plan, flags=re.S)


def pick(start):
    found = [b for b in blocks if b.lstrip().startswith(start)]
    assert len(found) == 1, (start, len(found))
    return found[0]


flag_test = pick("def test_steady_state_false_skips_steady_analytics")
class_q = pick("# ═══")
main_py = pick('"""Сценарий 13b')
assert "class TestPwfAlternating" in class_q

R2 = HERE / "r2"
if R2.exists():
    shutil.rmtree(R2)
ex = R2 / "examples"
ex.mkdir(parents=True)
shutil.copyfile(HERE / "flag" / "example_runner.py", ex / "example_runner.py")
shutil.copytree(EX / "05_standing_table_rp", ex / "05_standing_table_rp",
                ignore=shutil.ignore_patterns("output", "__pycache__"))
d13 = ex / "13b_pwf_alternating"
d13.mkdir()
for f in ("config.json", "oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
    shutil.copyfile(HERE / "cfg_13b" / f, d13 / f)
(d13 / "main.py").write_text(main_py, encoding="utf-8")

header = f'''import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, r"{SOLVER / 'HydroSolverPrototype' / 'Prototype_1.0.3'}")
sys.path.append(r"{EX}")          # общие модули examples/ — после копии

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

EXAMPLES_DIR = Path(r"{ex}")


def _pvt_of_config(cfg):
    from gpn_multiphase_solver.factory import _create_pvt
    return _create_pvt(cfg)


@pytest.fixture(scope="session")
def results():
    name = "13b_pwf_alternating"
    cfg = load_config(EXAMPLES_DIR / name / "config.json")
    cfg.output.log_level = "ERROR"
    simulator, initial = SimulatorFactory.from_config(cfg)
    history = simulator.run(initial)
    final = history.states[-1]
    return {{name: {{
        "history": history, "grid": simulator._grid, "config": cfg,
        "Rs0": cfg.initial_conditions.Rs0, "p": final.p, "T": final.T,
        "Sg": final.Sg, "Rs": final.Rs, "T_well": float(final.T[0]),
        "q_o": np.array([w.q_o_std for w in history.well_data]),
        "q_g": np.array([w.q_g_std for w in history.well_data]),
    }}}}


'''
(R2 / "test_r2.py").write_text(header + flag_test + "\n\n" + class_q, encoding="utf-8")
print("собрано:", R2)
print("длина строк > 100 в тестах и main.py:",
      [(i + 1, len(s)) for i, s in enumerate((flag_test + class_q + main_py).splitlines())
       if len(s) > 100])
