"""BUG-019: черновик проверки PVT не меняет расчёт — пример 20 (конфиг из git HEAD) побитово.

Повод: полный прогон с плагином (plan_impl_full_tests.txt) дал 3 отказа тестов
примера 20 — во время прогона в рабочей копии изменили его config.json
(k, p0, Rs0). Здесь исходный конфиг берётся из HEAD (`git show`), рабочая
копия не трогается. Два расчёта 30 сут: без черновика и с подменой
factory._create_pvt (как plan_impl_plugin.py) — сравнение всех сохранённых
состояний и данных скважины.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-019\\probes\\draft_no_change.py
"""

import json
import logging
import subprocess

import numpy as np

import common as c
from gpn_multiphase_solver import factory
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

OUT = c.HERE / "ex20_head"
OUT.mkdir(exist_ok=True)
text = subprocess.run(["git", "-C", str(c.SOLVER.parent), "show",
                       "HEAD:numerical_solver/examples/20_rs500_cooling/config.json"],
                      capture_output=True, check=True).stdout.decode("utf-8")
d = json.loads(text)
print(f"HEAD: k = {d['rock']['permeability']}, p0 = {d['initial_conditions']['p0']}, "
      f"Rs0 = {d['initial_conditions']['Rs0']}")
d["output"]["log_level"] = "WARNING"
(OUT / "config.json").write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def run():
    sim, init = SimulatorFactory.from_config(load_config(OUT / "config.json"))
    return sim.run(init)


recs = []
h = logging.Handler()
h.emit = recs.append
logging.getLogger("gpn_multiphase_solver").addHandler(h)

base = run()
n_warn_base = len([r for r in recs if r.levelno >= logging.WARNING])

import consistency_draft  # noqa: E402
import sys  # noqa: E402
sys.modules["gpn_multiphase_solver.pvt.consistency"] = consistency_draft
from factory_draft import _warn_negative_compressibility  # noqa: E402
orig = factory._create_pvt


def _create_pvt(config):
    pvt = orig(config)
    _warn_negative_compressibility(config, pvt)
    return pvt


factory._create_pvt = _create_pvt
recs.clear()
drafted = run()
warns = [r.getMessage() for r in recs if r.levelno >= logging.WARNING]

print(f"предупреждений: без черновика {n_warn_base}, с черновиком {len(warns)}")
for w in warns:
    print(f"   {w[:140]}…")
same = len(base.states) == len(drafted.states)
for a, b in zip(base.states, drafted.states):
    same &= all(np.array_equal(getattr(a, f), getattr(b, f)) for f in ("p", "Sg", "Rs", "T", "regime"))
for a, b in zip(base.well_data, drafted.well_data):
    same &= (a.q_o_std == b.q_o_std and a.q_g_std == b.q_g_std and a.T_wf == b.T_wf and a.p_wf == b.p_wf)
print(f"состояний {len(base.states)}; все поля и данные скважины совпадают побитово: {same}")
print(f"T(r_w) на 30 сут: {base.well_data[-1].T_wf:.3f} К")
