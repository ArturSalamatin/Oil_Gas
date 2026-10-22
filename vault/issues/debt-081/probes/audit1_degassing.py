"""DEBT-081, аудит 1: искажает ли "N": true дебит при разгазировании.

План (§1.2) утверждал без замера: при разгазировании одна ячейка искажает и
дебит. Пример 01 однофазный — там дебит совпал с контролем. Здесь пример 03
(Стендинг + Кори, R_s0 = 50, p_wf = 8 МПа < p_b), 2 ч, N = 150 против true.

Запуск из numerical_solver/ основного каталога (код до правки — true проходит):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-081\\probes\\audit1_degassing.py
Вывод — audit1_degassing.out.txt рядом со скриптом.
"""
import json
import sys
from pathlib import Path

SOLVER = Path.cwd()
sys.path.insert(0, str(SOLVER))

import gpn_multiphase_solver                                   # noqa: E402
from gpn_multiphase_solver.io.config import load_config        # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory     # noqa: E402

HERE = Path(__file__).resolve().parent
SRC = SOLVER / "examples" / "03_standing_corey" / "config.json"
lines = []


def say(s=""):
    print(s)
    lines.append(s)


say(f"пакет: {Path(gpn_multiphase_solver.__file__).parent}")
raw0 = json.loads(SRC.read_text(encoding="utf-8"))
p_wf = raw0["time"]["history"][0]["p_wf"]
raw0["time"]["history"] = [{"duration": 7200.0, "dt_out": 3600.0,
                            "control": "pressure", "p_wf": p_wf}]
say(f"конфиг: {SRC.relative_to(SOLVER)}, история 2 ч, p_wf = {p_wf / 1e6:g} МПа")
say()

for value in (150, True):
    raw = json.loads(json.dumps(raw0))
    raw["grid"]["N"] = value
    tmp = HERE / "_audit1_tmp.json"
    tmp.write_text(json.dumps(raw), encoding="utf-8")
    try:
        cfg = load_config(tmp)
        sim, initial = SimulatorFactory.from_config(cfg)
        hist = sim.run(initial)
    finally:
        tmp.unlink(missing_ok=True)
    w = hist.well_data[-1]
    st = hist.states[-1]
    # ГФ у забоя — q_g/q_o при ст. у., м³ст/м³ст
    say(f"N = {value!r:5} ячеек {st.p.shape[0]:3}: q_o = {w.q_o_std * 86400:8.3f} м³ст/сут, "
        f"ГФ = {w.q_g_std / w.q_o_std:7.3f}, S_g[0] = {st.Sg[0]:.4f}, "
        f"T_wf = {w.T_wf:.4f} К в r_0 = {sim.grid.r_centers[0]:.4f} м")

(HERE / "audit1_degassing.out.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
