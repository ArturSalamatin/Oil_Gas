"""BUG-018: замороженный сценарий для тестов и числа первого шага.

Пишет probes/frozen/bug018_rs500/config.json — пример 20 генератора FEAT-025
в отказной редакции: R_s0 = 500, T0 = 380 К, PVT Стендинга, Кори S_gc = 0.1,
S_or = 0.2, n_g = 3, N = 50, k = 100 мД, p0 = 46.9 МПа, p_wf = 5 МПа, одна
история 1 сут. При реализации файл копируется в numerical_solver/tests/data/.

Затем первый шаг через адаптер (как _first_step в test_prototype_globalization):
без правки и с правкой patch_cap.py (rule=node), N = 50 и 350. Печатает
n_substeps, S_g[0], p[0], cap и число срабатываний; при отказе — текст.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-018\\probes\\freeze_case.py [rule=node]
"""

import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch_cap as pc  # noqa: E402  (подключает пути решателя и генератора)
import make_configs as mc  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

rule = sys.argv[1].split("=", 1)[1] if len(sys.argv) > 1 else "node"
DST = HERE / "frozen" / "bug018_rs500"
DST.mkdir(parents=True, exist_ok=True)
cfg_dict = mc.build("20", mc.SETS["20"], {"S_or": "0.2", "N": "50", "k": "1e-13", "days": "1",
                                          "log": "INFO"})
(DST / "config.json").write_text(json.dumps(cfg_dict, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
print(f"записан {DST / 'config.json'}")

for N in (50, 350):
    for patch in (False, True):
        cfg = load_config(DST / "config.json")
        cfg.grid.N = N
        cfg.output.log_level = "ERROR"
        sim, init = SimulatorFactory.from_config(cfg)
        model = sim._hydro._model
        st = {"cap": pc.cap_of(model.relperm, rule), "max_guess": 0.0, "hits": 0}
        if patch:
            model._advance_phases = types.MethodType(pc.patched_advance_phases(st), model)
        _, dt = sim._schedule.substeps(0)
        tag = f"N = {N:3d}, {'с правкой' if patch else 'без правки'}"
        try:
            res = sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)
            print(f"   {tag}: n_substeps = {res.n_substeps}, S_g[0] = {res.state.Sg[0]:.6f}, "
                  f"p[0] = {res.state.p[0]/1e6:.6f} МПа, cap = {st['cap']}, срабатываний {st['hits']}, "
                  f"max S_g активации {st['max_guess']:.4f}")
        except RuntimeError as e:
            print(f"   {tag}: ОТКАЗ — {str(e)[:70]}…")
