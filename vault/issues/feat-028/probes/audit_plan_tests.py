"""Аудит FEAT-028: тексты тестов плана дословно против кода шага 1 плана.

Код шага 1 и тесты извлекаются из vault/plans/feat-028 pvto-style-pvt-plot.md
(блоки ```python), код подменяет функции в gpn_multiphase_solver.io.output
в памяти — файлы репозитория не меняются. _pvt_table_nodes оформителя
дополняется ключом p_branch по коду шага 3.

Не проверяются здесь (требуют правок шага 3 в файлах): тест 13
test_formatter_delegates_drawing_to_core, тест 14 test_plot_pvt_layout_2x3.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\feat-028\\probes\\audit_plan_tests.py
"""
import re
import sys
import textwrap
import traceback
from pathlib import Path

import numpy as np
import pytest
import matplotlib
matplotlib.use("Agg")

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[4]
NS = ROOT / "numerical_solver"
sys.path.insert(0, str(NS / "HydroSolverPrototype" / "Prototype_1.0.3"))
sys.path.insert(0, str(NS / "examples"))
sys.path.insert(0, str(NS))

import gpn_multiphase_solver.io.output as out  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.factory import _create_pvt  # noqa: E402
from gpn_multiphase_solver.pvt.standing import StandingFullPVT  # noqa: E402
from gpn_multiphase_solver.units import BAR_TO_PA  # noqa: E402
import pvt_plot  # noqa: E402

plan = (ROOT / "vault" / "plans" / "feat-028 pvto-style-pvt-plot.md").read_text(encoding="utf-8")
# Блоки внутри пунктов списка сдвинуты на 3 пробела — общий отступ снимается
# для функций модуля; методы тестов ищутся в сырых блоках по своему отступу.
raw_blocks = re.findall(r"```python\n(.*?)```", plan, re.S)
blocks = [textwrap.dedent(b) for b in raw_blocks]

# ── Код шага 1 → в модуль ядра ──
core = next(b for b in blocks if "def _round_rs_rows" in b and "def plot_pvt_properties" in b)
exec(compile(core, "plan:step1", "exec"), out.__dict__)

# ── _pvt_table_nodes по шагу 3: + p_branch ──
_orig_nodes = pvt_plot._pvt_table_nodes


def _nodes_step3(pvt, Rs0):
    nodes = _orig_nodes(pvt, Rs0)
    if nodes is None:
        return None
    proto = pvt._hydro._pvt
    rs_near = min(proto.rs_values, key=lambda r: abs(r - Rs0))
    p_branch = np.array([x[0] for x in proto.branches[rs_near]], float) * BAR_TO_PA
    nodes["p_branch"] = p_branch if np.isclose(rs_near, Rs0) else np.empty(0)
    return nodes


pvt_plot._pvt_table_nodes = _nodes_step3

# ── Пространство имён тестов: как в test_output.py / test_examples.py ──
EXAMPLES_DIR = NS / "examples"
ns = dict(np=np, pytest=pytest, StandingFullPVT=StandingFullPVT, load_config=load_config,
          plot_pvt_properties=out.plot_pvt_properties, _round_rs_rows=out._round_rs_rows,
          _pvto_rows=out._pvto_rows, EXAMPLES_DIR=EXAMPLES_DIR,
          _pvt_module=lambda: pvt_plot, _pvt_of_config=_create_pvt)

# Вспомогательные функции плана (шаг 2 п. 3, шаг 4 п. 1).
for b in blocks:
    for name in ("_pvto_lines", "_standing_pvt", "_table_pvto_axes"):
        m = re.search(rf"^def {name}\(.*?(?=^\S|\Z)", b, re.S | re.M)
        if m:
            exec(compile(m.group(0), f"plan:{name}", "exec"), ns)

# Тесты: методы классов (отступ 4) — вынимаются и вызываются с self=None.
SKIP = {"test_formatter_delegates_drawing_to_core", "test_plot_pvt_layout_2x3"}
tests = {}
for b in raw_blocks:
    for m in re.finditer(r"^( +)def (test_\w+)\(self.*?(?=^\1def |\Z)", b, re.S | re.M):
        name = m.group(2)
        if name in SKIP or "def plot_pvt_properties" in b:
            continue
        code = textwrap.dedent(m.group(0))
        exec(compile(code, f"plan:{name}", "exec"), ns)
        tests[name] = ns[name]

ok, bad = [], []
for name, fn in tests.items():
    try:
        fn(None)
        ok.append(name)
    except Exception:
        bad.append(name)
        print(f"FAIL {name}\n{traceback.format_exc()}")

print("\n".join("OK   " + n for n in ok))
print(f"\nпрошло {len(ok)}, упало {len(bad)} из {len(tests)}; пропущены: {sorted(SKIP)}")

# ── Все 20 примеров: ядро шага 1 без исключений и предупреждений ──
# Ось — по конфигу (min p_wf … p0; у 15 с управлением по дебиту p_wf нет —
# берётся min_bhp, иначе 6 МПа). Реальная ось по состоянию уже, ветвей не больше.
import warnings  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

print("\n── все примеры ──")
for cfg_path in sorted(EXAMPLES_DIR.glob("*/config.json")):
    cfg = load_config(cfg_path)
    pvt = _create_pvt(cfg)
    Rs0 = float(cfg.initial_conditions.Rs0)
    pw = [h.p_wf for h in cfg.time.history if getattr(h, "p_wf", None) is not None]
    p_lo = min(pw) if pw else 6e6
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        fig, axes = plt.subplots(2, 3)
        out.plot_pvt_properties(pvt, Rs0, (p_lo, cfg.initial_conditions.p0), axes=axes,
                                table_nodes=pvt_plot._pvt_table_nodes(pvt, Rs0))
        fig.tight_layout()
        n = [len(ns["_pvto_lines"](axes[0, 0], g))
             for g in ("pvto_saturated", "pvto_saturated_extrap", "pvto_branch", "pvto_rs0")]
        plt.close(fig)
    msgs = sorted({str(x.message)[:60] for x in w})
    print(f"  {cfg_path.parent.name:28s} насыщ/экстр/ветви/Rs0 = {n}; предупреждений {len(w)} {msgs}")
