"""DEBT-014: что делает выборка управления _run_schedule с краткой формой истории примера 03.

tests/test_energy_balance_examples.py:183 берёт управление из history[0],
отбрасывая только ключ dt. Проба повторяет эту строку на объекте краткой
формы, который даст compact_history.py для примера 03, и разворачивает оба
расписания теста FEAT-018 так же, как load_config.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-014\\probes\\red_state.py
"""

import importlib.util
import json
import sys
from pathlib import Path

SOLVER = Path.cwd()
sys.path.insert(0, str(SOLVER))
from gpn_multiphase_solver.io import config as config_mod  # noqa: E402

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("compact_history", HERE / "compact_history.py")
ch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ch)

print(f"пакет: {config_mod.__file__}")
raw = json.loads((SOLVER / "examples/03_standing_corey/config.json").read_text(encoding="utf-8"))
first = ch.compact(raw["time"]["history"])[0]
print(f"history[0] после перевода: {first}")

# Блоки теста test_stepped_schedule_matches_uniform
SCHEDULES = {
    "uniform": [{"dt": 300.0, "repeat": 72}],
    "stepped": [{"duration": 3600.0, "dt_out": 300.0},
                {"duration": 18000.0, "dt_out": 3600.0}],
}

for label, keep in (("сейчас: отбрасывается только dt", lambda k: k != "dt"),
                    ("исправление: отбрасываются все ключи времени",
                     lambda k: k not in config_mod._HISTORY_TIME_KEYS)):
    control = {k: v for k, v in first.items() if keep(k)}
    print(f"\n{label}: control = {control}")
    for name, blocks in SCHEDULES.items():
        history = [{**block, **control} for block in blocks]
        try:
            intervals, _ = config_mod._expand_history(history)
            dts = sorted({iv.dt for iv in intervals})
            print(f"  {name}: {len(intervals)} интервалов, dt = {dts}, "
                  f"сумма {sum(iv.dt for iv in intervals):.0f} с")
        except ValueError as exc:
            print(f"  {name}: ValueError: {exc}")
