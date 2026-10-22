"""Аудит FEAT-021: стенд для прогона тестов на конфиге примера 12 без правки проекта.

Собирает рядом с собой:
  examples/12_large_drainage_radius/  — config.json (копия 11 с R_ext=200, p0=15.5e6),
                                        три CSV из 11, main.py, черновой README;
  test_examples_probe.py              — копия tests/test_examples.py, списки сужены до 12,
                                        дописан класс TestLargeDrainageRadius из плана;
  test_energy_matrix_probe.py         — копия tests/test_energy_matrix_examples.py, списки → 12;
  conftest.py                         — sys.path: пакет, examples/, прототип radial_blackoil.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-021\\probes\\build_probe.py
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\feat-021\\probes -q -p no:cacheprovider
"""

import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
SRC = SOLVER / "examples" / "11_degassing_at_boundary"
NAME = "12_large_drainage_radius"
DST = HERE / "examples" / NAME

DST.mkdir(parents=True, exist_ok=True)
for f in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
    shutil.copyfile(SRC / f, DST / f)

cfg = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
cfg["geometry"]["R_ext"] = 200.0
cfg["initial_conditions"]["p0"] = 15500000.0
# История: 15 интервалов по 1 сут; dt_integration остаётся 3600 с
iv = dict(cfg["time"]["history"][0], dt=86400.0)
cfg["time"]["history"] = [dict(iv) for _ in range(15)]
(DST / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

# main.py как в плане, но example_runner берётся из настоящей папки examples/
(DST / "main.py").write_text(f'''"""Проба: сценарий 12."""
import sys
from pathlib import Path
sys.path.insert(0, r"{SOLVER / 'examples'}")
from example_runner import run_example  # noqa: E402
if __name__ == "__main__":
    here = Path(__file__).parent
    run_example(config_path=here / "config.json", output_dir=here / "output",
                title="12: большая область дренирования")
''', encoding="utf-8")

# Черновой README: только обязательные для TestReadme фразы
(DST / "README.md").write_text(
    "# 12 — проба\n\n## Как увеличить газонасыщенность\n\n## Как модифицировать\n\n"
    "`PrototypeHydroAdapter`, `TridiagEnergySolver`\n", encoding="utf-8")

(HERE / "conftest.py").write_text(f'''import sys
for p in (r"{SOLVER}", r"{SOLVER / 'examples'}",
          r"{SOLVER / 'HydroSolverPrototype' / 'Prototype_1.0.3'}"):
    if p not in sys.path:
        sys.path.insert(0, p)
''', encoding="utf-8")

LIST_12 = f'["{NAME}"]\n'

# ── test_examples ──
t = (SOLVER / "tests" / "test_examples.py").read_text(encoding="utf-8")
t = t.replace('EXAMPLES_DIR = Path(__file__).parent.parent / "examples"',
              'EXAMPLES_DIR = Path(__file__).parent / "examples"')
t = re.sub(r"ALL_EXAMPLES = \[.*?\]\n", "ALL_EXAMPLES = " + LIST_12, t, count=1, flags=re.S)
t = re.sub(r"NEEDS_SG_SECTION = \[.*?\]\n", "NEEDS_SG_SECTION = " + LIST_12, t, count=1,
           flags=re.S)
t += '''

# ═══════════════════════════════════════════════════════════
# L. Сценарий 12: большая область дренирования (FEAT-021) — код из плана
# ═══════════════════════════════════════════════════════════

class TestLargeDrainageRadius:
    NAME = "12_large_drainage_radius"

    def test_boundary_cell_stays_single_phase(self, results):
        r = results[self.NAME]
        for n, st in enumerate(r["history"].states):
            assert st.Sg[-1] == 0.0, \\
                f"шаг {n}: S_g[N-1] = {st.Sg[-1]:.3e}, контурная ячейка двухфазна"
            assert abs(st.Rs[-1] - r["Rs0"]) < 1e-10, \\
                f"шаг {n}: R_s[N-1] = {st.Rs[-1]} отличается от R_s^0 = {r['Rs0']}"

    def test_gor_relaxes_toward_Rs0_from_above(self, results):
        r = results[self.NAME]
        gor = r["q_g"][1:] / r["q_o"][1:]
        assert np.all(np.diff(gor) < 0.0), f"GOR не убывает монотонно: {gor}"
        assert gor[-1] > r["Rs0"], \\
            f"GOR = {gor[-1]:.3f} на конце <= R_s0 = {r['Rs0']}: режим уже стационарен"
'''
(HERE / "test_examples_probe.py").write_text(t, encoding="utf-8")

# ── test_energy_matrix_examples ──
m = (SOLVER / "tests" / "test_energy_matrix_examples.py").read_text(encoding="utf-8")
m = m.replace('EXAMPLES_DIR = Path(__file__).parent.parent / "examples"',
              'EXAMPLES_DIR = Path(__file__).parent / "examples"')
m = re.sub(r"ALL_EXAMPLES = \[.*?\]\n", "ALL_EXAMPLES = " + LIST_12, m, count=1, flags=re.S)
m = re.sub(r"SUBDIVIDING_EXAMPLES = \[.*?\]\n", "SUBDIVIDING_EXAMPLES = " + LIST_12, m,
           count=1, flags=re.S)
(HERE / "test_energy_matrix_probe.py").write_text(m, encoding="utf-8")

print("стенд собран:", HERE)
