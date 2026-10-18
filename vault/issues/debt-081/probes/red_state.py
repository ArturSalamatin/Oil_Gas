"""DEBT-081: что делают load_config, фабрика и расчёт при нецелом grid.N.

Запуск из numerical_solver/ (основной каталог, worktree или копия plan_emulate.py):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-081\\probes\\red_state.py [имя вывода]
Пакет и пример берутся из текущего каталога. Вывод — рядом со скриптом:
red_state.out.txt по умолчанию; после правки — имя аргументом
(green_state.out.txt), чтобы не затереть замер «до».

Конфиг — examples/01_single_phase_no_jt/config.json (без CSV), история
укорочена до 2 ч (2 записи по 1 ч): этого хватает, чтобы показать, что расчёт
идёт и на какой сетке.
"""
import json
import sys
import traceback
from pathlib import Path

SOLVER = Path.cwd()
sys.path.insert(0, str(SOLVER))

import gpn_multiphase_solver                                   # noqa: E402
from gpn_multiphase_solver.io.config import load_config        # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory     # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / (sys.argv[1] if len(sys.argv) > 1 else "red_state.out.txt")
SRC = SOLVER / "examples" / "01_single_phase_no_jt" / "config.json"

# 150 — контроль (значение примера); NaN — уже ловит DEBT-051; None (null) —
# добавлен аудитом 1: поле int, значение не float — DEBT-051 его не проверяет
CASES = [150, True, False, "100", None, 100.0, 100.5, 0, -1, float("nan")]

lines = []


def say(s=""):
    print(s)
    lines.append(s)


say(f"пакет: {Path(gpn_multiphase_solver.__file__).parent}")
say(f"конфиг: {SRC.relative_to(SOLVER)}, история 2 ч, p_wf = 15 МПа")
say()

raw0 = json.loads(SRC.read_text(encoding="utf-8"))
raw0["time"]["history"] = [{"duration": 7200.0, "dt_out": 3600.0,
                            "control": "pressure", "p_wf": 15e6}]

for value in CASES:
    raw = json.loads(json.dumps(raw0))
    raw["grid"]["N"] = value
    tmp = HERE / "_red_state_tmp.json"
    tmp.write_text(json.dumps(raw), encoding="utf-8")
    head = f"N = {value!r:7}"
    try:
        try:
            cfg = load_config(tmp)
        except Exception as e:                                   # noqa: BLE001
            say(f"{head} load_config: {type(e).__name__}: {e}")
            continue
        try:
            sim, initial = SimulatorFactory.from_config(cfg)
        except Exception as e:                                   # noqa: BLE001
            say(f"{head} load_config пропустил (cfg.grid.N = {cfg.grid.N!r}); "
                f"from_config: {type(e).__name__}: {e}")
            continue
        try:
            hist = sim.run(initial)
        except Exception as e:                                   # noqa: BLE001
            say(f"{head} run: {type(e).__name__}: {e}")
            say(traceback.format_exc(limit=2))
            continue
        w = hist.well_data[-1]
        # T_wf — температура центра ячейки 0 (BUG-015): на одной ячейке это
        # r_0 = sqrt(r_w·R_ext), а не окрестность забоя
        say(f"{head} load_config пропустил (cfg.grid.N = {cfg.grid.N!r}); "
            f"расчёт 2 ч: ячеек {hist.states[-1].p.shape[0]}, "
            f"q_o = {w.q_o_std * 86400:.3f} м³ст/сут, T_wf = {w.T_wf:.4f} К "
            f"в r_0 = {sim.grid.r_centers[0]:.4f} м")
    finally:
        tmp.unlink(missing_ok=True)

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
